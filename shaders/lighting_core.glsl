// [BTDR:FILE.LIGHTCORE] lighting_core.glsl — deferred lighting terms, shared by lighting.frag (Debug View buffers)
// and composite.frag (the final image, [BTDR:COMP.INLINE]). GGX / Smith / Schlick (UE-style), one directional light
// with contact-hardening soft shadows, image based lighting from the environment atlas.
// needs (before the include): #define LC_BASE / LC_NRM / LC_POS / LC_EMIT <sampler2D> G-Buffer 0 / 1 / 2 / 3,
//   LC_SHADOW <sampler2D> shadow map, ENV_SHARP / ENV_ATLAS for env_lookup (included first)
// [BTDR:LIGHT.SPLIT] four terms so later passes (screen-space, ray traced) can replace the environment terms:
//   direct light + emissive (+ background) | 1 = geometry; environment diffuse; environment specular;
//   env BRDF * spec occlusion | surface weight
vec2 envBRDFApproxAB(float rough, float NoV)
{
    const vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
    const vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
    vec4 r = rough * c0 + c1;
    float a004 = min(r.x * r.x, exp2(-9.28 * NoV)) * r.x + r.y;
    return vec2(-1.04, 1.04) * a004 + r.zw;
}
vec3 envBRDFApprox(vec3 F0, float rough, float NoV)
{
    vec2 AB = envBRDFApproxAB(rough, NoV);
    return F0 * AB.x + AB.y;
}
// [BTDR:LIGHT.ENERGY] (0.8.4) multiple-scattering energy compensation (Kulla & Conty 2017, Turquin 2019; Filament's
// form): single-scattering GGX loses the light that bounces between microfacets, so rough metals render too dark.
// E(roughness, NoV) = directional albedo of GGX + height-correlated Smith for F0 = 1, precomputed offline (Monte Carlo,
// VNDF sampling, 200 000 samples per entry; rows = perceptual roughness 0..1, columns = NoV 0..1, 16 x 16; the NoV = 0 column repeats NoV = 1/15) and read
// bilinearly. factor = 1 + F0 (1 / E - 1). The split-sum approximation's A + B is not used: it overestimates the loss
// at low roughness (+5 percent on a roughness-0.1 metal). Applied to the direct and the environment specular.
const float ESS[256] = float[256](
    0.9999, 0.9999, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
    0.9975, 0.9975, 0.9994, 0.9997, 0.9998, 0.9999, 0.9999, 0.9999, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000,
    0.9604, 0.9604, 0.9892, 0.9952, 0.9974, 0.9983, 0.9988, 0.9991, 0.9992, 0.9994, 0.9994, 0.9995, 0.9996, 0.9996, 0.9996, 0.9996,
    0.9010, 0.9010, 0.9513, 0.9752, 0.9855, 0.9904, 0.9932, 0.9948, 0.9958, 0.9966, 0.9972, 0.9975, 0.9978, 0.9980, 0.9982, 0.9983,
    0.8888, 0.8888, 0.9048, 0.9355, 0.9567, 0.9697, 0.9776, 0.9828, 0.9861, 0.9885, 0.9902, 0.9915, 0.9924, 0.9932, 0.9937, 0.9942,
    0.9004, 0.9004, 0.8810, 0.8956, 0.9165, 0.9345, 0.9482, 0.9583, 0.9657, 0.9711, 0.9751, 0.9782, 0.9806, 0.9825, 0.9840, 0.9853,
    0.9118, 0.9118, 0.8753, 0.8699, 0.8794, 0.8937, 0.9082, 0.9211, 0.9319, 0.9407, 0.9478, 0.9536, 0.9583, 0.9621, 0.9652, 0.9678,
    0.9172, 0.9172, 0.8739, 0.8546, 0.8509, 0.8559, 0.8653, 0.8762, 0.8871, 0.8974, 0.9066, 0.9147, 0.9217, 0.9277, 0.9329, 0.9374,
    0.9165, 0.9165, 0.8695, 0.8418, 0.8276, 0.8228, 0.8241, 0.8293, 0.8366, 0.8448, 0.8534, 0.8618, 0.8699, 0.8773, 0.8842, 0.8904,
    0.9107, 0.9107, 0.8599, 0.8262, 0.8042, 0.7909, 0.7842, 0.7821, 0.7834, 0.7870, 0.7921, 0.7982, 0.8047, 0.8115, 0.8183, 0.8250,
    0.9008, 0.9008, 0.8449, 0.8056, 0.7774, 0.7572, 0.7434, 0.7343, 0.7290, 0.7266, 0.7264, 0.7279, 0.7308, 0.7345, 0.7390, 0.7438,
    0.8878, 0.8878, 0.8250, 0.7800, 0.7460, 0.7198, 0.6996, 0.6841, 0.6724, 0.6638, 0.6577, 0.6537, 0.6513, 0.6504, 0.6505, 0.6517,
    0.8723, 0.8723, 0.8014, 0.7500, 0.7100, 0.6782, 0.6524, 0.6313, 0.6140, 0.5998, 0.5882, 0.5787, 0.5710, 0.5649, 0.5600, 0.5563,
    0.8549, 0.8549, 0.7748, 0.7163, 0.6705, 0.6334, 0.6027, 0.5768, 0.5548, 0.5359, 0.5196, 0.5054, 0.4930, 0.4822, 0.4728, 0.4643,
    0.8358, 0.8358, 0.7460, 0.6803, 0.6287, 0.5867, 0.5516, 0.5216, 0.4956, 0.4731, 0.4531, 0.4354, 0.4195, 0.4053, 0.3925, 0.3808,
    0.8157, 0.8157, 0.7157, 0.6428, 0.5858, 0.5393, 0.5003, 0.4671, 0.4382, 0.4129, 0.3905, 0.3705, 0.3526, 0.3364, 0.3216, 0.3083);
float essLookup(float rough, float NoV)
{
    vec2 c = clamp(vec2(rough, NoV), 0.0, 1.0) * 15.0;
    ivec2 i = min(ivec2(c), ivec2(14));
    vec2 f = c - vec2(i);
    float e00 = ESS[i.x * 16 + i.y], e01 = ESS[i.x * 16 + i.y + 1];
    float e10 = ESS[(i.x + 1) * 16 + i.y], e11 = ESS[(i.x + 1) * 16 + i.y + 1];
    return mix(mix(e00, e01, f.y), mix(e10, e11, f.y), f.x);
}
vec3 energyComp(vec3 F0, float rough, float NoV)
{
    if (uMisc.x < 0.5) return vec3(1.0);
    return 1.0 + F0 * (1.0 / max(essLookup(rough, NoV), 0.05) - 1.0);
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
    vec3 p = wp + n * UM(0.012);
    vec3 rel = p - uSunPos.xyz;
    vec2 suv = vec2(dot(rel, uSunRight.xyz), dot(rel, uSunUp.xyz)) / uSunRight.w + 0.5;
    float depth = dot(uSunPos.xyz - p, uSunDir.xyz);
    if (suv.x < 0.0 || suv.x > 1.0 || suv.y < 0.0 || suv.y > 1.0) return 1.0;
    float texel = 1.0 / float(textureSize(LC_SHADOW, 0).x);
    float wtex = uSunRight.w * texel;                       // world size of one shadow texel
    float bias = UM(0.004 + 0.02 * (1.0 - NoL)) + wtex * 1.5;
    float soft = max(uSunColor.w, 0.0);
    float ang = fract(hash12(gl_FragCoord.xy) + uFrame.x * 0.618034) * 6.2831853;
    float search = max(UM(0.024) * soft, wtex * 2.0) / uSunRight.w;
    float blockers = 0.0, bsum = 0.0;
    for (int i = 0; i < 12; i++) {
        float r = sqrt((float(i) + 0.5) / 12.0);
        float th = float(i) * 2.39996323 + ang;
        float d = texture(LC_SHADOW, suv + vec2(cos(th), sin(th)) * r * search).r;
        if (d > 0.001 && d < depth - bias) { bsum += d; blockers += 1.0; }
    }
    if (blockers < 0.5) return 1.0;
    float pen = clamp((depth - bsum / blockers) * 0.0376 * soft, wtex * 1.2, max(UM(0.0273) * soft, wtex * 1.2)) / uSunRight.w;
    float lit = 0.0;
    for (int i = 0; i < 24; i++) {
        float r = sqrt((float(i) + 0.5) / 24.0);
        float th = float(i) * 2.39996323 + ang;
        float d = texture(LC_SHADOW, suv + vec2(cos(th), sin(th)) * r * pen).r;
        lit += (d > 0.001 && d < depth - bias) ? 0.0 : 1.0;
    }
    return lit / 24.0;
}

// [BTDR:LIGHT.LOCAL] (0.9.0) point, spot and extra distant lights (Light COMPs matched by Lights other than the main
// light), up to 8, looped over directly, no shadows (0.9.1 adds tiled culling and shadows). Same BRDF as the sun
// (GGX + Smith + Schlick + energy compensation, Lambert diffuse); brightness follows BTDR's convention (Dimmer x pi).
// Falloff: the Light COMP's own Attenuation (Start / End / Exp; none when Attenuated is off, like a TouchDesigner
// light) or physical inverse square (the Dimmer x pi irradiance is reached at 1 m).
#ifdef LC_LLSH0
// [BTDR:LIGHT.LLSHADOW] (0.9.1) spot-light shadow: the map stores the distance in front of the light camera (same depth
// material as the sun's), 3 x 3 PCF; slots LLS(k, *) from `uniforms`
float llShadow(int k, vec3 P, vec3 N)
{
    if (LLS(k, 3).w < 0.5) return 1.0;
    vec4 q = vec4(P + N * LLS(k, 3).z, 1.0);
    vec3 c = vec3(dot(LLS(k, 0), q), dot(LLS(k, 1), q), dot(LLS(k, 2), q));
    float z = -c.z;
    if (z <= LLS(k, 3).y) return 1.0;
    vec2 uv = 0.5 + 0.5 * c.xy / (z * LLS(k, 3).x);
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return 1.0;
    float bias = LLS(k, 3).z * 2.0 + z * 0.004;
    float lit = 0.0;
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec2 o = vec2(x, y) / 1024.0;
            float d = k == 0 ? texture(LC_LLSH0, uv + o).r : k == 1 ? texture(LC_LLSH1, uv + o).r :
                      k == 2 ? texture(LC_LLSH2, uv + o).r : texture(LC_LLSH3, uv + o).r;
            lit += (d > 0.001 && d < z - bias) ? 0.0 : 1.0;
        }
    return lit / 9.0;
}
#endif
vec3 localLight(int i, vec3 P, vec3 N, vec3 V, vec3 diff, vec3 F0, float a, float a2, float rough, float NoV)
{
    vec3 L; float dist;
    float att = llAtten(i, P, L, dist);
    float NoL = dot(N, L);
    if (NoL <= 0.0 || att <= 0.0) return vec3(0.0);
#ifdef LC_LLSH0
    int k = int(LL(i, 4).y + 0.5) - 1;     // stored as index + 1 (0 = none)
    if (k >= 0) att *= llShadow(k, P, N);
    if (att <= 0.0) return vec3(0.0);
#endif
    vec3 H = normalize(V + L);
    float NoH = clamp(dot(N, H), 0.0, 1.0);
    float VoH = clamp(dot(V, H), 0.0, 1.0);
    vec3 spec = D_GGX(a2, NoH) * V_SmithJointApprox(a, NoV, NoL) * F_Schlick(F0, VoH) * energyComp(F0, rough, NoV);
    return (diff / PI + spec) * LL(i, 1).rgb * NoL * att;
}
vec3 localLights(vec3 P, vec3 N, vec3 V, vec3 diff, vec3 F0, float a, float a2, float rough, float NoV)
{
    vec3 s = vec3(0.0);
    int n = min(LL_COUNT, LL_MAX);
    for (int i = 0; i < LL_MAX; i++) {
        if (i >= n) break;
        s += localLight(i, P, N, V, diff, F0, a, a2, rough, NoV);
    }
    return s;
}

// [BTDR:LIGHT.SSSIRR] (0.8.0) the subsurface pass needs irradiance without the base colour: lightingTerms leaves the
// sun's diffuse irradiance (shadowed, before the distance fade) and the environment irradiance (before AO) here
vec3 gSunIrr = vec3(0.0);
vec3 gEnvIrr = vec3(0.0);
void lightingTerms(vec2 uv, out vec4 oDirect, out vec4 oAmbDiff, out vec4 oAmbSpec, out vec4 oBRDF)
{
    gSunIrr = vec3(0.0); gEnvIrr = vec3(0.0);
    vec4 g0 = texture(LC_BASE, uv);
    vec4 g1 = texture(LC_NRM, uv);
    vec4 g2 = texture(LC_POS, uv);

    // [BTDR:LIGHT.BACKGROUND]
    vec2 ndc = uv * 2.0 - 1.0;
    vec3 rd = camDir(ndc);                            // [BTDR:CAM.ORTHO] orthographic: one direction, a flat background
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

    vec3 V = -viewDirRel(g2.xyz);
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
        vec3 spec = D_GGX(a2, NoH) * V_SmithJointApprox(a, NoV, NoL) * F_Schlick(F0, VoH) * energyComp(F0, rough, NoV);
        direct = (diffuseColor / PI + spec) * uSunColor.rgb * uSunDir.w * NoL * sh;
        gSunIrr = uSunColor.rgb * uSunDir.w * NoL * sh / PI;
    }
    if (LL_COUNT > 0) direct += localLights(wp, N, V, diffuseColor, F0, a, a2, rough, NoV);

    // [BTDR:LIGHT.IBL]
    vec3 R = reflect(-V, N);
    R = normalize(mix(R, N, a * a));                  // rough reflections bend toward the normal
    vec3 irradiance = envIrradiance(N);
    gEnvIrr = irradiance;
    vec3 prefiltered = envRadiance(R, rough);
    float specOcc = clamp(pow(NoV + ao, exp2(-16.0 * rough - 1.0)) - 1.0 + ao, 0.0, 1.0);
    float horizon = clamp(1.0 + dot(R, N), 0.0, 1.0);
    vec3 brdf = envBRDFApprox(F0, rough, NoV) * energyComp(F0, rough, NoV) * specOcc * horizon * horizon;

    // [BTDR:LIGHT.FADE] optional distance fade into the background (seamless floors)
    float fade = uView.w > uView.z ? smoothstep(uView.z, uView.w, length(g2.xyz)) : 0.0;
    float w = 1.0 - fade;
    oDirect = vec4((direct + emit) * w + bg * fade, 1.0);
    oAmbDiff = vec4(diffuseColor * irradiance * ao * w, 1.0);
    oAmbSpec = vec4(prefiltered * brdf * w, 1.0);
    oBRDF = vec4(brdf, w);
}
