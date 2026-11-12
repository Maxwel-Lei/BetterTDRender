// [BTDR:FILE.COMP] composite.frag — combines the split lighting buffers with the screen-space passes.
// 2D inputs: 0 direct (+ emissive, background), 1 env diffuse (x albedo x material AO), 2 env specular,
//            3 env BRDF | weight, 4 SSGI | AO (accumulated), 5 SSR | confidence (accumulated), 6 base | metal,
//            7 normal | roughness, 8 camera-relative position, 9 height-field map (hf_src: depth below topcam),
//            10 traced reflection ratio | valid (rt_src, reduced resolution, accumulated)
// 3D inputs: 0..3 probe grid SH-L1 (probe_src0..3: mean | valid, first moments r / g / b) (M4)
// uSS: x AO strength, y GI strength, z SSR strength (0 = off); uHF / uHF2: height-field AO ([BTDR:UNI.HFAO])
out vec4 fragColor;
#define PROBE_SH0 sTD3DInputs[0]
#define PROBE_SH1 sTD3DInputs[1]
#define PROBE_SH2 sTD3DInputs[2]
#define PROBE_SH3 sTD3DInputs[3]
//#include probe_lookup

// [BTDR:COMP.HFAO] height-field AO (contact AO on the ground): sky visibility from the top-down depth map. For a few directions around the
// point (only those on the side the surface faces), march outwards and keep the highest occluder elevation
// (relative to the surface's own tangent plane, so a slope does not shadow itself); visible sky of a slice =
// 1 - sin^2(elevation) (cosine-weighted). Everything below the top surface counts as solid (a car is a block down
// to the ground): right under objects and right next to them; overhangs are seen from above only.
float hfHeight(vec2 xz)
{
    // topcam looks down -Y: screen right = +X, screen up = -Z
    vec2 uv = vec2(xz.x - uHF.x, uHF.y - xz.y) / uHF.z + 0.5;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return -1e9;
    float d = textureLod(sTD2DInputs[9], uv, 0.0).r;
    return d > 1e-4 ? uHF.w - d : -1e9;
}
float heightFieldAO(vec3 p, vec3 N)
{
    float dist = length(p - uCamPos.xyz);
    vec3 o = p + N * (0.02 + 0.002 * dist);            // off the surface (16-bit position precision)
    float R = uHF2.z;
    int nd = int(uHF2.w + 0.5);
    float rot = hash12(gl_FragCoord.xy + uFrame.x * 7.13) * 6.2831853 / float(nd);   // TAA averages the rotation
    float jit = hash12(gl_FragCoord.yx + uFrame.x * 3.71);
    float vis = 0.0, wsum = 0.0;
    for (int i = 0; i < 8; i++) {
        if (i >= nd) break;
        float a = rot + float(i) * 6.2831853 / float(nd);
        vec2 dir = vec2(cos(a), sin(a));
        float wd = clamp(dot(vec3(dir.x, 0.0, dir.y), N) + N.y, 0.0, 1.0);   // facing up: all; vertical: outwards
        if (wd <= 0.0) continue;
        float slope = N.y > 0.2 ? max(-dot(N.xz, dir) / N.y, 0.0) : 0.0;     // tangent-plane rise per metre
        float ms = 0.0;
        for (int k = 0; k < 4; k++) {
            float t = (float(k) + 0.25 + 0.5 * jit) / 4.0;
            float r = R * t * t + 0.02;                                      // dense near the point
            float dy = hfHeight(o.xz + dir * r) - (o.y + slope * r);
            if (dy > 0.0) ms = max(ms, dy * inversesqrt(dy * dy + r * r));
        }
        vis += (1.0 - ms * ms) * wd;
        wsum += wd;
    }
    return wsum > 0.0 ? vis / wsum : 1.0;
}
void main()
{
    vec2 uv = vUV.st;
    vec4 d = texture(sTD2DInputs[0], uv);
    vec3 ambD = texture(sTD2DInputs[1], uv).rgb;
    vec3 ambS = texture(sTD2DInputs[2], uv).rgb;
    vec4 brdf = texture(sTD2DInputs[3], uv);
    vec4 gi = texture(sTD2DInputs[4], uv);
    vec4 ssr = texture(sTD2DInputs[5], uv);
    vec4 g0 = texture(sTD2DInputs[6], uv);
    float w = brdf.a;                                   // 0 on the background
    vec3 diffuseColor = g0.rgb * (1.0 - g0.a);
    // [BTDR:COMP.AO] screen-space AO only darkens the ambient (environment) terms, never the sun
    float ao = mix(1.0, gi.a, uSS.x * step(1e-4, w));
    float hf = 1.0;
    if (uHF2.x > 0.5 && w > 1e-4) {
        vec3 N = normalize(texture(sTD2DInputs[7], uv).xyz);
        vec3 rp = texture(sTD2DInputs[8], uv).xyz;
        vec3 p = rp + uCamPos.xyz;
        // [BTDR:COMP.HFRECEIVER] receivers only (0.3.4): upward-facing surfaces that are not the top surface of a
        // caster at their own position — the ground under and around objects, the inside of a car under its roof.
        // The objects themselves (sides, hood, roof) are left alone: the height field cannot tell their own
        // overhangs from real occluders, and darkening them looked dirty (0.3.3).
        float top = hfHeight(p.xz);
        bool isTop = top > -1e8 && top - p.y < 0.03 + 0.003 * length(rp);
        if (N.y > 0.6 && !isTop) hf = mix(1.0, heightFieldAO(p, N), uHF2.y);
    }
    float aoD = min(ao, hf);                            // the two overlap at contacts: take the stronger, not both
    float giScale = uSS.y;
    // [BTDR:COMP.PROBES] M4: the probe grid (traced, knows about occlusion off screen) replaces the environment diffuse
    if (uRT.x > 0.5 && w > 1e-4) {
        vec3 N = normalize(texture(sTD2DInputs[7], uv).xyz);
        vec4 g2 = texture(sTD2DInputs[8], uv);
        ambD = diffuseColor * probeIrradiance(g2.xyz + uCamPos.xyz, N) * g2.a * uRT.w;
        giScale *= 0.5;                                 // the probes already carry the large-scale bounce
    }
    vec3 bounce = diffuseColor * gi.rgb * w * giScale;
    vec3 diff = ambD * aoD + bounce;
    // [BTDR:COMP.RTSPEC] M4: traced reflections scale the environment specular by traced / environment
    vec4 rt = texture(sTD2DInputs[10], uv);
    float rtw = clamp(rt.a * uRT.y * uRT4.z, 0.0, 1.0);
    vec3 envS = mix(ambS, ambS * rt.rgb, rtw);
    // [BTDR:COMP.SPEC] SSR replaces the environment reflection where it found a hit
    float c = clamp(ssr.a * uSS.z, 0.0, 1.0) * step(1e-4, w);
    // the environment reflection is occluded by the large-scale term in full (sky seen in a floor under a car);
    // where the reflection is traced the occlusion is already in it
    vec3 spec = mix(envS * mix(1.0, ao, 0.5) * mix(hf, 1.0, rtw), ssr.rgb * brdf.rgb * w, c);
    vec3 col = d.rgb + diff + spec;
    fragColor = vec4(col, d.a);                         // a: 1 = geometry, 0 = background
}
