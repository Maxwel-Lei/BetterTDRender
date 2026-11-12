// [BTDR:FILE.MB] mblur.frag — camera motion blur (ported from ue5r). Velocity comes from the camera only:
// objects that move by themselves are not blurred (no per-object motion vectors yet).
// input 0: HDR colour with the TAA-stable view depth in alpha. output: same layout.
// uMB: x shutter (fraction of a frame), y max blur px, z samples
out vec4 fragColor;
vec2 project(vec3 wp, vec4 P, vec4 R, vec4 U, vec4 F)
{
    vec3 v = wp - P.xyz;
    float z = max(dot(v, F.xyz), 1e-4);
    return vec2(dot(v, R.xyz) / (z * F.w), dot(v, U.xyz) / (z * F.w / uClip.z)) * 0.5 + 0.5;
}
void main()
{
    vec4 c0 = texture(sTD2DInputs[0], vUV.st);
    // world position from the stable depth: depth is along the view axis, the ray's forward component is 1
    vec2 ndc = vUV.st * 2.0 - 1.0;
    vec3 ray = uCamFwd.xyz + ndc.x * uCamFwd.w * uCamRight.xyz + ndc.y * uCamFwd.w / uClip.z * uCamUp.xyz;
    vec3 wp = uCamPos.xyz + ray * c0.a;
    // [BTDR:MB.VELOCITY] jitter-free camera velocity in uv per frame, scaled by the shutter
    vec2 vel = (project(wp, uCamPos, uCamRight, uCamUp, uCamFwd) - project(wp, uPrevPos, uPrevRight, uPrevUp, uPrevFwd)) * uMB.x;
    float lenPx = length(vel * uTD2DInfos[0].res.zw);
    if (lenPx < 0.5 || uFrame.z > 0.5) { fragColor = c0; return; }
    vel *= min(1.0, uMB.y / lenPx);
    int n = int(uMB.z);
    float j = fract(hash12(gl_FragCoord.xy) + uFrame.x * 0.618034);
    vec3 acc = vec3(0.0);
    for (int i = 0; i < n; i++) {
        float t = (float(i) + j) / float(n) - 0.5;
        acc += texture(sTD2DInputs[0], vUV.st + vel * t).rgb;
    }
    fragColor = vec4(acc / float(n), c0.a);
}
