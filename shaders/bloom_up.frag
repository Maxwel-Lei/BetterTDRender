// [BTDR:FILE.BLOOMUP] bloom_up.frag — 3x3 tent upsample of the coarser level, blended with this level
// inputs: 0 coarser level (already accumulated), 1 this level's downsample. uBloom.w = radius (scatter):
// out = mix(this, tent(coarser), radius) — a weighted average, so the brightness does not depend on the radius.
out vec4 fragColor;
void main()
{
    vec2 t = uTD2DInfos[0].res.xy;
    vec3 s = texture(sTD2DInputs[0], vUV.st).rgb * 4.0;
    s += (texture(sTD2DInputs[0], vUV.st + vec2(t.x, 0)).rgb + texture(sTD2DInputs[0], vUV.st - vec2(t.x, 0)).rgb
        + texture(sTD2DInputs[0], vUV.st + vec2(0, t.y)).rgb + texture(sTD2DInputs[0], vUV.st - vec2(0, t.y)).rgb) * 2.0;
    s += texture(sTD2DInputs[0], vUV.st + t).rgb + texture(sTD2DInputs[0], vUV.st - t).rgb
       + texture(sTD2DInputs[0], vUV.st + vec2(t.x, -t.y)).rgb + texture(sTD2DInputs[0], vUV.st - vec2(t.x, -t.y)).rgb;
    vec3 cur = texture(sTD2DInputs[1], vUV.st).rgb;
    fragColor = vec4(mix(cur, s / 16.0, clamp(uBloom.w, 0.0, 0.95)), 1.0);
}
