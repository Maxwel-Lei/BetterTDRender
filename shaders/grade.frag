// [BTDR:FILE.GRADE] grade.frag — exposure, tone mapping, vignette, sRGB, grain
// inputs: 0 HDR colour, 1 bloom (1/2 res, whole mip chain already combined), 2 auto exposure (1x1, g = multiplier)
out vec4 fragColor;

vec3 RRTAndODTFit(vec3 v)
{
    vec3 a = v * (v + 0.0245786) - 0.000090537;
    vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081;
    return a / b;
}
// [BTDR:GRADE.ACES] Stephen Hill's ACES fit
vec3 ACESFitted(vec3 c)
{
    const mat3 inM = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
    const mat3 outM = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
    return clamp(outM * RRTAndODTFit(inM * c), 0.0, 1.0);
}
void main()
{
    vec4 hdr = texture(sTD2DInputs[0], vUV.st);
    // [BTDR:GRADE.BLOOM] bloom is added in HDR, before exposure (like UE)
    vec3 bloom = texture(sTD2DInputs[1], vUV.st).rgb;
    // [BTDR:GRADE.EXPOSURE] manual exposure (EV) x auto exposure
    float ae = uAE.x > 0.5 ? texelFetch(sTD2DInputs[2], ivec2(0), 0).g : 1.0;
    vec3 c = (hdr.rgb + bloom * uBloom.x) * uGrade.x * ae;
    vec3 col = uGrade.w > 0.5 ? ACESFitted(c) : clamp(c, 0.0, 1.0);
    vec2 q = vUV.st - 0.5;
    col *= mix(1.0, smoothstep(0.95, 0.25, length(q * vec2(1.0, 0.8))), uGrade.y);
    col = pow(col, vec3(1.0 / 2.2));
    col += (hash12(gl_FragCoord.xy + fract(uFrame.x * 0.618034) * 97.0) - 0.5) * uGrade.z;
    // [BTDR:GRADE.ALPHA] Background = Transparent (uEnv.z < 0): alpha = geometry coverage, from the temporally stable
    // depth in the HDR alpha. An anti-aliased edge holds a mix of object depth and far plane; the nearest depth in
    // the 3x3 neighbourhood stands in for the object's.
    float alpha = 1.0;
    if (uEnv.z < -0.5) {
        vec2 px = 1.0 / vec2(textureSize(sTD2DInputs[0], 0));
        float dn = hdr.a;
        for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++)
            dn = min(dn, texture(sTD2DInputs[0], vUV.st + vec2(i, j) * px).a);
        alpha = dn < uClip.y * 0.999 ? clamp((uClip.y - hdr.a) / max(uClip.y - dn, 1e-4), 0.0, 1.0) : 0.0;
        col *= alpha;                                   // premultiplied, like the native Render TOP
    }
    fragColor = TDOutputSwizzle(vec4(col, alpha));
}
