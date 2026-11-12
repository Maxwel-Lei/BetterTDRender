// [BTDR:FILE.BLENDCOMP] blend_comp.frag — M6b: lay the blended layer (tblend, premultiplied) over the image
// ([BTDR:FWD.COMP]). Runs after refract, before fog / TAA.
// inputs: 0 HDR image (trans_src), 1 blended layer (rgb premultiplied, a coverage)
out vec4 fragColor;
void main()
{
    vec4 c = texture(sTD2DInputs[0], vUV.st);
    vec4 b = texture(sTD2DInputs[1], vUV.st);
    b = max(b, vec4(0.0));
    if (any(isnan(b)) || any(isinf(b))) b = vec4(0.0);
    fragColor = vec4(c.rgb * (1.0 - clamp(b.a, 0.0, 1.0)) + b.rgb, c.a);
}
