// [BTDR:FILE.DEPTH] depth.frag — third output: view-space depth in scene units (background = camera far)
// inputs: 0 normal|rough, 1 camera-relative pos|ao
out vec4 fragColor;
void main()
{
    vec4 g1 = texture(sTD2DInputs[0], vUV.st);
    vec3 rp = texture(sTD2DInputs[1], vUV.st).xyz;      // camera-relative position
    float d = dot(g1.xyz, g1.xyz) > 0.25 ? dot(rp, uCamFwd.xyz) : uClip.y;
    fragColor = vec4(d, d, d, 1.0);
}
