// [BTDR:FILE.COMP] composite.frag — the deferred lighting ([BTDR:COMP.INLINE]: lighting_core, computed here) combined
// with the screen-space passes, the probe grid and the traced reflections.
// 2D inputs: 0 base | metal, 1 normal | roughness, 2 camera-relative position | AO, 3 shadow map (shadow_src),
//            4 emissive, 5 sharp environment, 6 SSGI | AO (accumulated), 7 SSR | confidence (accumulated),
//            8 height-field map (hf_src: depth below topcam), 9 traced reflection ratio | valid (rt_src, reduced
//            resolution, accumulated)
// 3D inputs: 0 pre-filtered environment atlas, 1..4 probe grid SH-L1 (probe_src0..3: mean | valid, first moments
//            r / g / b) (M4)
// Input extend mode is Repeat (the environment wraps around); inputs that can be smaller than the output (SSGI, SSR,
// traced reflections, height field) clamp their coordinates to the edge texel centres (texHold), = Hold before 0.5.1.
// uSS: x AO strength, y GI strength, z SSR strength (0 = off); uHF / uHF2: height-field AO ([BTDR:UNI.HFAO])
// [BTDR:COMP.INLINE] 0.5.0 and earlier rendered the four lighting terms into four rgba16float buffers (lighting +
// 3 Render Select TOPs) and read them back here: ~130 MB of traffic per 1080p frame and four TOP cooks. The terms
// are now computed in registers; lighting.frag (same code) only cooks for the Debug View.
#define LC_BASE sTD2DInputs[0]
#define LC_NRM sTD2DInputs[1]
#define LC_POS sTD2DInputs[2]
#define LC_SHADOW sTD2DInputs[3]
#define LC_EMIT sTD2DInputs[4]
#define ENV_SHARP sTD2DInputs[5]
#define ENV_ATLAS sTD3DInputs[0]
#define IN_GI sTD2DInputs[6]
#define IN_SSR sTD2DInputs[7]
#define IN_HF sTD2DInputs[8]
#define IN_RT sTD2DInputs[9]
//#include env_lookup
//#include lighting_core
// Hold (clamp-to-edge) sampling for inputs that may be smaller than the output (SSGI / SSR at half resolution on
// Low, traced reflections at 1/4 or 1/6): with Repeat they would blend in the opposite screen edge
vec4 texHold(sampler2D t, vec2 uv)
{
    vec2 r = vec2(textureSize(t, 0));
    return texture(t, clamp(uv, 0.5 / r, 1.0 - 0.5 / r));
}
// [BTDR:COMP.RTUP] (0.8.4) joint bilateral upsampling of the reduced-resolution traced reflections: of the four
// nearest low-resolution texels, keep the ones that sat on the same surface (normal and plane distance of the
// G-Buffer at the texel centre, which is where rt_refl traced from). Plain bilinear blended the ratio of a box top
// into its front face and of the floor into the shadow under a ball: the 4x4-pixel dark blocks of 0.8.3.
vec4 rtUpsample(vec2 uv, vec3 N, vec3 rp)
{
    vec2 r = vec2(textureSize(IN_RT, 0));
    vec2 f = uv * r - 0.5;
    vec2 i0 = floor(f);
    vec2 fr = f - i0;
    float tol = UM(0.02) + 0.02 * length(rp);
    vec4 acc = vec4(0.0), accB = vec4(0.0);
    float ws = 0.0, wsB = 0.0;
    for (int j = 0; j < 2; j++)
        for (int i = 0; i < 2; i++) {
            vec2 tc = clamp((i0 + vec2(i, j) + 0.5) / r, 0.5 / r, 1.0 - 0.5 / r);
            vec4 s = textureLod(IN_RT, tc, 0.0);
            float wb = (i == 1 ? fr.x : 1.0 - fr.x) * (j == 1 ? fr.y : 1.0 - fr.y);
            vec4 nq = textureLod(LC_NRM, tc, 0.0);
            vec3 pq = textureLod(LC_POS, tc, 0.0).xyz;
            float wn = dot(nq.xyz, nq.xyz) > 0.25 ? pow(max(dot(N, normalize(nq.xyz)), 0.0), 16.0) : 0.0;
            float wd = exp(-abs(dot(pq - rp, N)) / tol);
            float w = wb * wn * wd;
            acc += s * w; ws += w;
            accB += s * wb; wsB += wb;
        }
    return ws > 1e-3 ? acc / ws : accB / max(wsB, 1e-6);
}
layout(location = 0) out vec4 fragColor;
// [BTDR:COMP.SSSOUT] second colour buffer, only allocated while a Subsurface slot holds an object (written always:
// a write without a buffer is dropped). Not #if TD_NUM_COLOR_BUFFERS: TD does not recompile when the count changes.
layout(location = 1) out vec4 oSSS;
#define PROBE_SH0 sTD3DInputs[1]
#define PROBE_SH1 sTD3DInputs[2]
#define PROBE_SH2 sTD3DInputs[3]
#define PROBE_SH3 sTD3DInputs[4]
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
    vec2 hr = vec2(textureSize(IN_HF, 0));
    float d = textureLod(IN_HF, clamp(uv, 0.5 / hr, 1.0 - 0.5 / hr), 0.0).r;   // = Hold extend
    return d > 1e-4 ? uHF.w - d : -1e9;
}
float heightFieldAO(vec3 p, vec3 N)
{
    float dist = length(p - uCamPos.xyz);
    vec3 o = p + N * (UM(0.02) + 0.002 * dist);            // off the surface (16-bit position precision)
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
            float r = R * t * t + UM(0.02);                                      // dense near the point
            float dy = hfHeight(o.xz + dir * r) - (o.y + slope * r);
            if (dy > 0.0) ms = max(ms, dy * inversesqrt(dy * dy + r * r));
        }
        vis += (1.0 - ms * ms) * wd;
        wsum += wd;
    }
    return wsum > 0.0 ? vis / wsum : 1.0;
}
// [BTDR:COMP.SSSTRANS] (0.8.0) transmission through a subsurface object, as irradiance (the caller multiplies by the
// diffuse colour). Thickness = how far the sun's light travelled inside: the point's distance from the shadow camera
// minus the depth of the first surface the shadow map saw there (UE's Subsurface model does the same). Sheets (Thin)
// use the slot's thickness and also let the environment through from behind.
vec3 sssTransmission(int k, vec3 wp, vec3 N)
{
    vec4 A = SSS_A(k), B = SSS_B(k), Cc = SSS_C(k);
    if (uSSSG.w < 0.5 || max(B.r, max(B.g, B.b)) <= 0.0) return vec3(0.0);
    vec3 L = normalize(uSunDir.xyz);
    float NoL = dot(N, L);
    vec3 sun = uSunColor.rgb * uSunDir.w / PI;
    if (B.w > 0.5) {                                        // sheet: leaf, paper, lampshade
        float t = exp(-Cc.y / UM(0.002));
        float sh = NoL < 0.0 ? sunShadow(wp, -N, -NoL) : 0.0;
        return B.rgb * t * (sun * max(-NoL, 0.0) * sh + envIrradiance(-N) * 0.5);
    }
    if (uSunPos.w < 0.5 || uSunDir.w <= 0.0) return vec3(0.0);
    float back = clamp(0.3 - 0.7 * NoL, 0.0, 1.0);        // lit side: none; terminator and back: some
    if (back <= 0.0) return vec3(0.0);
    vec3 p = wp - N * UM(0.004);                            // just inside the surface (4 mm)
    vec3 rel = p - uSunPos.xyz;
    vec2 suv = vec2(dot(rel, uSunRight.xyz), dot(rel, uSunUp.xyz)) / uSunRight.w + 0.5;
    if (any(lessThan(suv, vec2(0.0))) || any(greaterThan(suv, vec2(1.0)))) return vec3(0.0);
    float depth = dot(uSunPos.xyz - p, uSunDir.xyz);
    float texel = 1.0 / float(textureSize(LC_SHADOW, 0).x);
    float sum = 0.0, n = 0.0;
    for (int i = 0; i < 4; i++) {
        vec2 o = vec2(i == 1 ? 1.5 : (i == 2 ? -1.5 : 0.0), i == 3 ? 1.5 : (i == 0 ? -1.5 : 0.0)) * texel;
        float d = texture(LC_SHADOW, suv + o).r;
        if (d > 0.001) { sum += d; n += 1.0; }
    }
    if (n < 0.5) return vec3(0.0);
    float thick = max(depth - sum / n, 0.0);
    vec3 dist = max(A.rgb, vec3(1e-5));
    // half of the light that gets through leaves forwards (diffuse transmission through a slab), the rest goes back
    return 0.5 * B.rgb * exp(-thick / dist) * sun * back;
}
void main()
{
    vec2 uv = vUV.st;
    vec4 d, ambD4, ambS4, brdf;
    lightingTerms(uv, d, ambD4, ambS4, brdf);
    vec3 ambD = ambD4.rgb;
    vec3 ambS = ambS4.rgb;
    vec4 gi = texHold(IN_GI, uv);
    vec4 ssr = texHold(IN_SSR, uv);
    vec4 g0 = texture(LC_BASE, uv);
    float w = brdf.a;                                   // 0 on the background
    vec3 diffuseColor = g0.rgb * (1.0 - g0.a);
    // [BTDR:COMP.AO] screen-space AO only darkens the ambient (environment) terms, never the sun
    float ao = mix(1.0, gi.a, uSS.x * step(1e-4, w));
    float hf = 1.0;
    if (uHF2.x > 0.5 && w > 1e-4) {
        vec3 N = normalize(texture(LC_NRM, uv).xyz);
        vec3 rp = texture(LC_POS, uv).xyz;
        vec3 p = rp + uCamPos.xyz;
        // [BTDR:COMP.HFRECEIVER] receivers only (0.3.4): upward-facing surfaces that are not the top surface of a
        // caster at their own position — the ground under and around objects, the inside of a car under its roof.
        // The objects themselves (sides, hood, roof) are left alone: the height field cannot tell their own
        // overhangs from real occluders, and darkening them looked dirty (0.3.3).
        float top = hfHeight(p.xz);
        bool isTop = top > -1e8 && top - p.y < UM(0.03) + 0.003 * length(rp);
        if (N.y > 0.6 && !isTop) hf = mix(1.0, heightFieldAO(p, N), uHF2.y);
    }
    float aoD = min(ao, hf);                            // the two overlap at contacts: take the stronger, not both
    float giScale = uSS.y;
    // [BTDR:COMP.PROBES] M4: the probe grid (traced, knows about occlusion off screen) replaces the environment diffuse
    if (uRT.x > 0.5 && w > 1e-4) {
        vec3 N = normalize(texture(LC_NRM, uv).xyz);
        vec4 g2 = texture(LC_POS, uv);
        ambD = diffuseColor * probeIrradiance(g2.xyz + uCamPos.xyz, N) * g2.a * uRT.w;
        giScale *= 0.5;                                 // the probes already carry the large-scale bounce
    }
    vec3 bounce = diffuseColor * gi.rgb * w * giScale;
    vec3 diff = (ambD + diffuseColor * uAmb.rgb * w) * aoD + bounce;   // [BTDR:COMP.AMBIENT] Ambient Light COMPs
    // [BTDR:COMP.RTSPEC] M4: traced reflections scale the environment specular by traced / environment
    vec4 rt = vec4(1.0, 1.0, 1.0, 0.0);
    if (uRT.y > 0.5 && w > 1e-4) {
        vec4 g1r = texture(LC_NRM, uv);
        rt = rtUpsample(uv, normalize(g1r.xyz), texture(LC_POS, uv).xyz);
    }
    float rtw = clamp(rt.a * uRT.y * uRT4.z, 0.0, 1.0);
    vec3 envS = mix(ambS, ambS * rt.rgb, rtw);
    // [BTDR:COMP.SPEC] SSR replaces the environment reflection where it found a hit
    float c = clamp(ssr.a * uSS.z, 0.0, 1.0) * step(1e-4, w);
    // the environment reflection is occluded by the large-scale term in full (sky seen in a floor under a car);
    // where the reflection is traced the occlusion is already in it
    vec3 spec = mix(envS * mix(1.0, ao, 0.5) * mix(hf, 1.0, rtw), ssr.rgb * brdf.rgb * w, c);
    vec3 col = d.rgb + diff + spec;
    // [BTDR:COMP.SSS] (0.8.0) subsurface objects (RT3.a = 2 + profile): second output = the irradiance the subsurface
    // pass blurs, pre-multiplied by diffuse colour ^ (1 - texture detail), alpha = profile + 1 (0 = not subsurface).
    // The transmission is added to the image here and to the irradiance, so it is scattered too.
    oSSS = vec4(0.0);
    float sid = texture(LC_EMIT, uv).a;
    if (sid > 1.5 && w > 1e-4 && uSSSG.x > 0.5) {
        int k = clamp(int(sid - 2.0 + 0.5), 0, 7);
        vec3 N = normalize(texture(LC_NRM, uv).xyz);
        vec4 g2 = texture(LC_POS, uv);
        vec3 wp = g2.xyz + uCamPos.xyz;
        vec3 envI = uRT.x > 0.5 ? probeIrradiance(wp, N) * g2.a * uRT.w : gEnvIrr * g2.a * w;
        vec3 irr = gSunIrr * w + (envI + uAmb.rgb * w) * aoD + gi.rgb * w * giScale;
        vec3 tr = sssTransmission(k, wp, N) * w;
        col += diffuseColor * tr;
        irr += tr;
        vec4 A = SSS_A(k);
        if (int(uView.x + 0.5) == 18) oSSS = vec4(diffuseColor * tr, float(k + 1));      // Debug View: Transmission
        else if (A.w > 0.0) oSSS = vec4(pow(max(diffuseColor, vec3(1e-4)), vec3(1.0 - SSS_C(k).x)) * irr, float(k + 1));
    }
    fragColor = vec4(col, d.a);                         // a: 1 = geometry, 0 = background
}
