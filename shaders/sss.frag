// [BTDR:FILE.SSS] sss.frag — screen-space subsurface scattering (0.8.0), separable: built twice, horizontal (sss_h)
// and, with SSS_V defined, vertical + composite (sss_v). Jimenez's separable SSS with a Burley-like profile
// (two exponentials per colour channel: a short and a 3x longer tail), radius in world units.
// sss_h inputs: 0 irradiance x diffuse^(1 - detail) | profile + 1 (composite buffer 1), 1 camera-relative position (gbuf2)
// sss_v inputs: 0 sss_h, 1 position, 2 lit image (composite buffer 0), 3 composite buffer 1, 4 base colour | metallic
// [BTDR:SSS.WEIGHTS] taps at r = R (i / N)^2 (dense near the centre), weight = profile(r) x the interval each tap
// stands for, normalised per channel. Taps on another profile, or farther than R in depth, read the centre value
// instead (Jimenez's "follow surface"): the energy stays where it was, edges do not darken or bleed.
#ifdef SSS_V
layout(location = 0) out vec4 fragColor;
layout(location = 1) out vec4 oBlur;     // Debug View: Subsurface Irradiance (buffer only allocated for that view)
#else
out vec4 fragColor;
#endif

vec3 profile(float r, vec3 d)
{
    return exp(-r / d) + 0.25 * exp(-r / (3.0 * d));
}

void main()
{
    ivec2 pc = ivec2(gl_FragCoord.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    vec4 c = texelFetch(sTD2DInputs[0], pc, 0);
#ifdef SSS_V
    vec4 col = texelFetch(sTD2DInputs[2], pc, 0);
    fragColor = col;
    oBlur = vec4(0.0);
#else
    fragColor = c;
#endif
    if (c.a < 0.5) return;                                  // not a subsurface pixel
    int k = clamp(int(c.a - 1.0 + 0.5), 0, 7);
    vec4 A = SSS_A(k);
    vec3 d = max(A.rgb, vec3(1e-6));
    float dmax = max(d.r, max(d.g, d.b));
    float R = 4.0 * dmax;                                   // world range of the kernel
    vec3 rel = texelFetch(sTD2DInputs[1], pc, 0).xyz;
    float z = max(dot(rel, uCamFwd.xyz), 1e-3);
    float pxPerM = pxPerUnit(z, float(sz.x));             // [BTDR:CAM.ORTHO]
    float Rpx = min(R * pxPerM, 64.0);
    R = Rpx / pxPerM;                                       // clamped: keep the profile, cut its range
#ifdef SSS_V
    ivec2 dir = ivec2(0, 1);
#else
    ivec2 dir = ivec2(1, 0);
#endif
    vec3 sum = vec3(0.0), wsum = vec3(0.0);
    if (Rpx >= 1.0) {
        int N = int(uSSSG.z + 0.5);
        float invN2 = 1.0 / float(N * N);
        vec3 w0 = profile(R * 0.0625 * invN2, d) * (R * 0.25 * invN2);
        sum = c.rgb * w0; wsum = w0;
        for (int i = 1; i <= 8; i++) {
            if (i > N) break;
            float fi = float(i);
            float r = R * fi * fi * invN2;
            vec3 w = profile(r, d) * (R * 2.0 * fi * invN2);
            int o = int(r * pxPerM + 0.5);
            for (int s = -1; s <= 1; s += 2) {
                ivec2 q = clamp(pc + dir * (o * s), ivec2(0), sz - 1);
                vec4 t = texelFetch(sTD2DInputs[0], q, 0);
                vec3 v = c.rgb;
                if (abs(t.a - c.a) < 0.5) {
                    float zs = dot(texelFetch(sTD2DInputs[1], q, 0).xyz, uCamFwd.xyz);
                    v = mix(t.rgb, c.rgb, clamp(abs(zs - z) / R, 0.0, 1.0));
                }
                sum += v * w; wsum += w;
            }
        }
    } else {
        sum = c.rgb; wsum = vec3(1.0);
    }
    vec3 blur = sum / max(wsum, vec3(1e-12));
#ifdef SSS_V
    // [BTDR:SSS.COMPOSE] replace the diffuse part: lit image + strength x diffuse^detail x (blurred - original)
    vec3 x0 = texelFetch(sTD2DInputs[3], pc, 0).rgb;
    vec4 g0 = texelFetch(sTD2DInputs[4], pc, 0);
    vec3 dc = max(g0.rgb * (1.0 - g0.a), vec3(1e-4));
    fragColor = vec4(col.rgb + A.w * pow(dc, vec3(SSS_C(k).x)) * (blur - x0), col.a);
    oBlur = vec4(blur, c.a);
#else
    fragColor = vec4(blur, c.a);
#endif
}
