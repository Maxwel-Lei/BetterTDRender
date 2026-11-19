// [BTDR:FILE.DOF] dof.frag — depth of field (ported from ue5r): physically based circle of confusion +
// single-pass scatter-as-gather bokeh on a golden-angle spiral (after Dennis Gustafsson).
// input 0: HDR colour with the TAA-stable view depth in alpha. output: same layout.
// uDOF: x focal length mm, y f-stop, z focus distance, w max blur radius px; uDOF2: x sensor width mm, z radius step
out vec4 fragColor;
const float GOLDEN_ANGLE = 2.39996323;
float depthAt(vec2 uv) { return texture(sTD2DInputs[0], uv).a; }
// [BTDR:DOF.COC] thin-lens circle of confusion, as a radius in output pixels
float blurSize(float d)
{
    d *= uUnit.y;                       // [BTDR:UNI.UNIT] thin-lens maths in metres (focus distance is converted in uniforms)
    float f = uDOF.x * 0.001;
    float A = f / uDOF.y;
    float S1 = max(uDOF.z, f * 1.01);
    float coc = abs(A * f * (d - S1) / (max(d, 1e-3) * (S1 - f)));      // metres on the sensor
    float px = coc / (uDOF2.x * 0.001) * uTD2DInfos[0].res.z * 0.5;
    return clamp(px, 0.0, uDOF.w);
}
void main()
{
    vec4 c0 = texture(sTD2DInputs[0], vUV.st);
    float cd = c0.a;
    vec2 px = 1.0 / uTD2DInfos[0].res.zw;
    float cs = blurSize(cd);
    vec3 col = c0.rgb;
    float tot = 1.0;
    float radius = uDOF2.z;
    for (float ang = 0.0; radius < uDOF.w; ang += GOLDEN_ANGLE) {
        vec2 tc = vUV.st + vec2(cos(ang), sin(ang)) * px * radius;
        vec4 s = texture(sTD2DInputs[0], tc);
        float ss = blurSize(s.a);
        if (s.a > cd) ss = clamp(ss, 0.0, cs * 2.0);          // background does not bleed over a sharp foreground
        float m = smoothstep(radius - 0.5, radius + 0.5, ss);
        col += mix(col / tot, s.rgb, m);
        tot += 1.0;
        radius += uDOF2.z / radius;
    }
    fragColor = vec4(col / tot, cd);
}
