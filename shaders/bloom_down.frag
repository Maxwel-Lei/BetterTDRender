// [BTDR:FILE.BLOOMDOWN] bloom_down.frag — 13-tap 2x downsample (Jimenez, "Next Generation Post Processing in
// Call of Duty: Advanced Warfare", 2014). Taps are in INPUT texel units, so every level of the chain blurs the
// same amount in x and y ([BTDR:BLOOM.CHAIN]; 0.3.4 and earlier blurred the wide level only vertically).
// BLOOM_KARIS (first level only): Karis average of the 5 boxes, so single bright pixels do not flicker.
out vec4 fragColor;
vec3 T(vec2 o) { return texture(sTD2DInputs[0], vUV.st + o * uTD2DInfos[0].res.xy).rgb; }
float kw(vec3 c) { return 1.0 / (1.0 + max(c.r, max(c.g, c.b))); }
void main()
{
    vec3 a = T(vec2(-2, 2)), b = T(vec2(0, 2)), c = T(vec2(2, 2));
    vec3 d = T(vec2(-2, 0)), e = T(vec2(0, 0)), f = T(vec2(2, 0));
    vec3 g = T(vec2(-2, -2)), h = T(vec2(0, -2)), i = T(vec2(2, -2));
    vec3 j = T(vec2(-1, 1)), k = T(vec2(1, 1)), l = T(vec2(-1, -1)), m = T(vec2(1, -1));
#ifdef BLOOM_KARIS
    vec3 b0 = (j + k + l + m) * 0.25, b1 = (a + b + d + e) * 0.25, b2 = (b + c + e + f) * 0.25;
    vec3 b3 = (d + e + g + h) * 0.25, b4 = (e + f + h + i) * 0.25;
    float w0 = kw(b0) * 0.5, w1 = kw(b1) * 0.125, w2 = kw(b2) * 0.125, w3 = kw(b3) * 0.125, w4 = kw(b4) * 0.125;
    vec3 o = (b0 * w0 + b1 * w1 + b2 * w2 + b3 * w3 + b4 * w4) / (w0 + w1 + w2 + w3 + w4);
#else
    vec3 o = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
#endif
    fragColor = vec4(max(o, vec3(0.0)), 1.0);
}
