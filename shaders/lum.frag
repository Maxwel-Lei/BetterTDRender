// [BTDR:FILE.AE.METER] lum.frag — centre-weighted log-luminance metering (r = log2 L x weight, g = weight)
out vec4 fragColor;
void main()
{
    vec3 c = texture(sTD2DInputs[0], vUV.st).rgb;
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    vec2 q = (vUV.st - 0.5) * vec2(1.0, 0.75);
    float w = exp(-dot(q, q) * 6.0);
    fragColor = vec4(log2(max(l, 1e-4)) * w, w, 0.0, 1.0);
}
