// [BTDR:FILE.LIGHTCORE] lighting_core.glsl — deferred lighting terms, shared by lighting.frag (Debug View buffers)
// and composite.frag (the final image, [BTDR:COMP.INLINE]). GGX / Smith / Schlick (UE-style), one directional light
// with contact-hardening soft shadows, image based lighting from the environment atlas.
// needs (before the include): #define LC_BASE / LC_NRM / LC_POS / LC_EMIT <sampler2D> G-Buffer 0 / 1 / 2 / 3,
//   LC_SHADOW <sampler2D> shadow map, ENV_SHARP / ENV_ATLAS for env_lookup (included first)
// [BTDR:LIGHT.SPLIT] four terms so later passes (screen-space, ray traced) can replace the environment terms:
//   direct light + emissive (+ background) | 1 = geometry; environment diffuse; environment specular;
//   env BRDF * spec occlusion | surface weight
vec3 envBRDFApprox(vec3 F0, float rough, float NoV)
{
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
    vec4 r = rough * c0 + c1;
    float a004 = min(r.x * r.x, exp2(-9.28 * NoV)) * r.x + r.y;
    vec2 AB = vec2(-1.04, 1.04) * a004 + r.zw;
    return F0 * AB.x + AB.y;
}
float D_GGX(float a2, float NoH)
{
    float d = (NoH * a2 - NoH) * NoH + 1.0;
    return a2 / (PI * d * d);
}
float V_SmithJointApprox(float a, float NoV, float NoL)
{
    float v = NoL * (NoV * (1.0 - a) + a);
    float l = NoV * (NoL * (1.0 - a) + a);
    return 0.5 / max(v + l, 1e-5);
}
vec3 F_Schlick(vec3 F0, float VoH)
{
    float fc = pow(1.0 - VoH, 5.0);
    return clamp(50.0 * F0.g, 0.0, 1.0) * fc + (1.0 - fc) * F0;
}

// [BTDR:LIGHT.SHADOW] shadow map stores linear distance from the shadow camera plane.
// Blocker search -> penumbra estimate -> PCF on a rotated Vogel disc. All radii are in world units,
// so the result does not depend on shadow map resolution or range.
float sunShadow(vec3 wp, vec3 n, float NoL)
{
    if (uSunPos.w < 0.5) return 1.0;
    vec3 p = wp + n * 0.012;
    vec3 rel = p - uSunPos.xyz;
    vec2 suv = vec2(dot(rel, uSunRight.xyz), dot(rel, uSunUp.xyz)) / uSunRight.w + 0.5;
    float depth = dot(uSunPos.xyz - p, uSunDir.xyz);
    if (suv.x < 0.0 || suv.x > 1.0 || suv.y < 0.0 || suv.y > 1.0) return 1.0;
    float texel = 1.0 / float(textureSize(LC_SHADOW, 0).x);
    float wtex = uSunRight.w * texel;                       // world size of one shadow texel
    float bias = 0.004 + 0.02 * (1.0 - NoL) + wtex * 1.5;
    float soft = max(uSunColor.w, 0.0);
    float ang = fract(hash12(gl_FragCoord.xy) + uFrame.x * 0.618034) * 6.2831853;
    float search = max(0.024 * soft, wtex * 2.0) / uSunRight.w;
    float blockers = 0.0, bsum = 0.0;
    for (int i = 0; i < 12; i++) {
        float r = sqrt((float(i) + 0.5) / 12.0);
        float th = float(i) * 2.39996323 + ang;
        float d = texture(LC_SHADOW, suv + vec2(cos(th), sin(th)) * r * search).r;
        if (d > 0.001 && d < depth - bias) { bsum += d; blockers += 1.0; }
    }
    if (blockers < 0.5) return 1.0;
    float pen = clamp((depth - bsum / blockers) * 0.0376 * soft, wtex * 1.2, max(0.0273 * soft, wtex * 1.2)) / uSunRight.w;
    float lit = 0.0;
    for (int i = 0; i < 24; i++) {
        float r = sqrt((float(i) + 0.5) / 24.0);
        float th = float(i) * 2.39996323 + ang;
        float d = texture(LC_SHADOW, suv + vec2(cos(th), sin(th)) * r * pen).r;
        lit += (d > 0.001 && d < depth - bias) ? 0.0 : 1.0;
    }
    return lit / 24.0;
}

void lightingTerms(vec2 uv, out vec4 oDirect, out vec4 oAmbDiff, out vec4 oAmbSpec, out vec4 oBRDF)
{
    vec4 g0 = texture(LC_BASE, uv);
    vec4 g1 = texture(LC_NRM, uv);
    vec4 g2 = texture(LC_POS, uv);

    // [BTDR:LIGHT.BACKGROUND]
    vec2 ndc = uv * 2.0 - 1.0;
    vec3 rd = normalize(uCamFwd.xyz + ndc.x * uCamFwd.w * uCamRight.xyz + ndc.y * uCamFwd.w / uClip.z * uCamUp.xyz);
    vec3 bg = uView.y > 0.5 ? pow(max(uBgColor.rgb, 0.0), vec3(2.2)) : uBgColor.rgb;
    if (uEnv.z > 0.5) bg = envRadiance(rd, uEnv.w);
    bg *= uBgColor.w;
    if (dot(g1.xyz, g1.xyz) < 0.25) {
        oDirect = vec4(bg, 0.0);
        oAmbDiff = vec4(0.0); oAmbSpec = vec4(0.0); oBRDF = vec4(0.0);
        return;
    }

    vec3 base = g0.rgb;
    float metal = g0.a;
    vec3 N = normalize(g1.xyz);
    float rough = g1.a;
    vec3 wp = g2.xyz + uCamPos.xyz;                  // G-Buffer stores camera-relative position
    float ao = g2.a;
    vec3 emit = texture(LC_EMIT, uv).rgb;

    vec3 V = normalize(-g2.xyz);
    vec3 L = normalize(uSunDir.xyz);
    vec3 H = normalize(V + L);
    float NoV = clamp(abs(dot(N, V)) + 1e-4, 0.0, 1.0);
    float NoL = clamp(dot(N, L), 0.0, 1.0);
    float NoH = clamp(dot(N, H), 0.0, 1.0);
    float VoH = clamp(dot(V, H), 0.0, 1.0);

    vec3 diffuseColor = base * (1.0 - metal);
    vec3 F0 = mix(vec3(0.04), base, metal);
    float a = rough * rough;
    float a2 = a * a;

    vec3 direct = vec3(0.0);
    if (NoL > 0.0 && uSunDir.w > 0.0) {
        float sh = sunShadow(wp, N, NoL);
        vec3 spec = D_GGX(a2, NoH) * V_SmithJointApprox(a, NoV, NoL) * F_Schlick(F0, VoH);
        direct = (diffuseColor / PI + spec) * uSunColor.rgb * uSunDir.w * NoL * sh;
    }

    // [BTDR:LIGHT.IBL]
    vec3 R = reflect(-V, N);
    R = normalize(mix(R, N, a * a));                  // rough reflections bend toward the normal
    vec3 irradiance = envIrradiance(N);
    vec3 prefiltered = envRadiance(R, rough);
    float specOcc = clamp(pow(NoV + ao, exp2(-16.0 * rough - 1.0)) - 1.0 + ao, 0.0, 1.0);
    float horizon = clamp(1.0 + dot(R, N), 0.0, 1.0);
    vec3 brdf = envBRDFApprox(F0, rough, NoV) * specOcc * horizon * horizon;

    // [BTDR:LIGHT.FADE] optional distance fade into the background (seamless floors)
    float fade = uView.w > uView.z ? smoothstep(uView.z, uView.w, length(g2.xyz)) : 0.0;
    float w = 1.0 - fade;
    oDirect = vec4((direct + emit) * w + bg * fade, 1.0);
    oAmbDiff = vec4(diffuseColor * irradiance * ao * w, 1.0);
    oAmbSpec = vec4(prefiltered * brdf * w, 1.0);
    oBRDF = vec4(brdf, w);
}
