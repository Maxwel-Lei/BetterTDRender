// [BTDR:FILE.FOG.APPLY] fog_apply.frag — volumetric fog pass 3: look up the integrated volume at each pixel's
// depth. Runs before TAA, which resolves the slice dither.
// inputs: 2D 0 HDR colour (composite), 2D 1 G-Buffer camera-relative position, 3D 0 integrated fog
out vec4 fragColor;
void main()
{
    vec4 c = texture(sTD2DInputs[0], vUV.st);
    ivec2 sz = textureSize(sTD2DInputs[1], 0);
    vec4 g = texelFetch(sTD2DInputs[1], clamp(ivec2(vUV.st * vec2(sz)), ivec2(0), sz - 1), 0);
    float z = dot(g.xyz, g.xyz) > 1e-8 ? dot(g.xyz, uCamFwd.xyz) : uFog2.y;
    float s = clamp(log(max(z, uFog2.x) / uFog2.x) / log(uFog2.y / uFog2.x), 0.0, 1.0);
    float N = float(uTD3DInfos[0].depth.y);
    s += (hash12(gl_FragCoord.xy + uFrame.x * 7.3) - 0.5) / N;                       // hide slice steps
    // [BTDR:FOG.EDGE] stay between the first and last slice centres: the 3D input repeats in depth, so a lookup
    // at s = 1 blends the last slice (full fog) with the first (no fog) — a hard band where pixels reach the
    // fog's Max Distance
    s = clamp(s, 0.5 / N, 1.0 - 0.5 / N);
    vec4 f = texture(sTD3DInputs[0], vec3(vUV.st, s));
    fragColor = vec4(c.rgb * f.a + f.rgb, c.a);
}
