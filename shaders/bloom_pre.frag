// [BTDR:FILE.BLOOM] bloom_pre.frag — soft-knee bright pass + 2x downsample (ported from ue5r)
// inputs: 0 HDR colour, 1 auto exposure (1x1). uBloom: x intensity, y threshold, z knee.
// The threshold applies to the EXPOSED colour (like UE): 1.0 = what ends up as white on screen.
out vec4 fragColor;
void main()
{
    vec2 px = 1.0 / uTD2DInfos[0].res.zw;
    vec3 c = vec3(0.0);
    for (int y = 0; y < 2; y++)
        for (int x = 0; x < 2; x++)
            c += texture(sTD2DInputs[0], vUV.st + (vec2(x, y) * 2.0 - 1.0) * px).rgb;
    c = min(c * 0.25, vec3(64.0));                  // clamp fireflies (sun glints)
    float expo = uGrade.x * (uAE.x > 0.5 ? texelFetch(sTD2DInputs[1], ivec2(0), 0).g : 1.0);
    float br = max(c.r, max(c.g, c.b)) * expo;
    float k = max(uBloom.z, 1e-4);
    float soft = clamp(br - uBloom.y + k, 0.0, 2.0 * k);
    soft = soft * soft / (4.0 * k);
    float w = max(soft, br - uBloom.y) / max(br, 1e-4);
    fragColor = vec4(c * w, 1.0);
}
