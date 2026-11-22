// [BTDR:FILE.MB] mblur.frag — camera + (0.9.2) object motion blur (ported from ue5r).
// input 0: HDR colour with the TAA-stable view depth in alpha; input 1: object velocity ([BTDR:BUILD.VELOCITY]).
// Moving objects blur along their own screen motion inside their silhouette (no tile-max reconstruction yet: the
// background next to a fast object is not smeared over, [BTDR:VEL.LIMITS]). output: same layout.
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
    // [BTDR:MB.OBJECT] (0.9.2) a moving object's own displacement (velocity pass holds this surface: same distance)
    vec3 disp = vec3(0.0);
    ivec2 vs = textureSize(sTD2DInputs[1], 0);
    if (uMisc.w > 0.5 && vs.x > 1) {
        vec4 v = texelFetch(sTD2DInputs[1], clamp(ivec2(vUV.st * vec2(vs)), ivec2(0), vs - 1), 0);
        float d = length(wp - uCamPos.xyz);
        if (v.a > 0.0 && abs(v.a - d) < 0.03 * d + UM(0.02)) disp = v.rgb;
    }
    vec2 vel = (project(wp, uCamPos, uCamRight, uCamUp, uCamFwd) - project(wp - disp, uPrevPos, uPrevRight, uPrevUp, uPrevFwd)) * uMB.x;
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
