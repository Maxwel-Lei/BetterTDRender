// [BTDR:FILE.SSR] ssr.frag — screen-space reflections (ported from ue5r): one GGX importance-sampled ray per
// pixel, world-space march with a thickness test against the G-Buffer, binary refinement, hit radiance from
// last frame's image (reprojected).
// inputs: 0 G-Buffer normal | rough, 1 camera-relative position | ao, 2 previous frame HDR (taa_hist)
// output: rgb reflected radiance, a confidence (0 = no hit, use the environment)
// uSSR: x max distance, y steps, z max roughness, w thickness
#define NRMBUF sTD2DInputs[0]
#define POSBUF sTD2DInputs[1]
//#include ss_common
out vec4 fragColor;
vec3 importanceGGX(vec2 xi, vec3 N, float a)
{
    float phi = 2.0 * PI * xi.x;
    float cosT = sqrt((1.0 - xi.y) / (1.0 + (a * a - 1.0) * xi.y));
    float sinT = sqrt(1.0 - cosT * cosT);
    vec3 h = vec3(cos(phi) * sinT, sin(phi) * sinT, cosT);
    vec3 up = abs(N.z) < 0.999 ? vec3(0, 0, 1) : vec3(1, 0, 0);
    vec3 tx = normalize(cross(up, N));
    vec3 ty = cross(N, tx);
    return normalize(tx * h.x + ty * h.y + N * h.z);
}
void main()
{
    vec4 p0 = fetchRel(vUV.st);
    vec4 n0 = fetchNrm(vUV.st);
    // geometric normal (no normal map), taken before any early return: derivatives need uniform control flow
    vec3 Ng = normalize(cross(dFdx(p0.xyz), dFdy(p0.xyz)) + vec3(0.0, 1e-12, 0.0));
    float rough = n0.a;
    if (!isGeoRel(p0) || rough > uSSR.z) { fragColor = vec4(0.0); return; }
    vec3 P = p0.xyz + uCamPos.xyz;
    vec3 N = normalize(n0.xyz);
    vec3 V = viewDirRel(p0.xyz);
    float a = max(rough * rough, 0.002);
    vec2 xi = vec2(ign(gl_FragCoord.xy, uFrame.x), ign(gl_FragCoord.yx + 31.0, uFrame.x * 1.3));
    xi.y *= 0.85;                                        // trim the long GGX tail (less noise)
    vec3 R = reflect(V, importanceGGX(xi, N, a));
    if (dot(R, N) <= 0.0) R = reflect(V, N);

    int steps = int(uSSR.y);
    float jit = ign(gl_FragCoord.xy + 7.0, uFrame.x);
    vec3 start = P + N * (UM(0.004) + 0.002 * length(p0.xyz));
    float tFront = 0.0, tHit = 0.0;                     // last sample where the ray was in front of the depth buffer
    bool hit = false, behind = false;
    // [BTDR:SSR.MARCH] quadratic step distribution: fine near the surface, coarse far away
    // [BTDR:SSR.REFINE] every sample that is behind the depth buffer is refined first (binary search back to the
    // last sample in front) and the thickness test is made at the refined point. 0.3.4 and earlier tested the
    // thickness at the coarse sample: whether a ray counted as a hit depended on where the step happened to land,
    // which gave stair steps along reflected edges (thick setting) or horizontal bands of missed hits (thin).
    // The depth gap at the refined point changes smoothly with the ray, so edges come out smooth.
    for (int i = 1; i <= steps; i++) {
        float f = (float(i) - 1.0 + jit) / float(steps);
        float t = uSSR.x * f * f + UM(0.01);
        vec3 Q = start + R * t;
        vec2 uv = curUV(Q);
        if (!inScreen(uv)) break;
        vec4 sp = fetchRel(uv);
        if (!isGeoRel(sp) || viewDepth(Q) <= dot(sp.xyz, uCamFwd.xyz)) { tFront = t; behind = false; continue; }
        if (behind) continue;                           // only refine where the ray goes from in front to behind
        behind = true;
        float lo = tFront, hi = t;
        for (int k = 0; k < 7; k++) {
            float mid = 0.5 * (lo + hi);
            vec3 M = start + R * mid;
            vec4 mp = fetchRel(curUV(M));
            if (isGeoRel(mp) && viewDepth(M) > dot(mp.xyz, uCamFwd.xyz)) hi = mid; else lo = mid;
        }
        vec3 H = start + R * hi;
        vec4 hp = fetchRel(curUV(H));
        float gap = viewDepth(H) - dot(hp.xyz, uCamFwd.xyz);
        if (isGeoRel(hp) && gap < uSSR.w + hi * 0.05) { tHit = hi; hit = true; break; }
        // behind something, but too far behind to be its surface: the ray passes behind it; keep marching
    }
    if (!hit) { fragColor = vec4(0.0); return; }
    vec2 huv = curUV(start + R * tHit);
    vec4 hn = fetchNrm(huv);
    if (dot(hn.xyz, R) > 0.2) { fragColor = vec4(0.0); return; }                // hit a back face
    // [BTDR:SSR.SELFHIT] a short hit on a surface facing the same way as the start is the surface itself
    // (normal-mapped or engraved detail re-entering the coarse G-Buffer surface), not a reflected object.
    // Only rejected when the normals agree: a short hit on a wall standing on the floor is the contact
    // reflection and must be kept (0.3.0 rejected every short hit, which left a gap between object and
    // reflection).
    if (dot(Ng, N) < 0.0) Ng = -Ng;
    if (tHit < 0.01 + 0.01 * length(p0.xyz) && dot(normalize(hn.xyz), Ng) > 0.9) { fragColor = vec4(0.0); return; }
    // [BTDR:SSR.CONFIDENCE] fade at the screen border, near the roughness limit and at the end of the ray
    vec2 e = smoothstep(vec2(0.0), vec2(0.08), huv) * (1.0 - smoothstep(vec2(0.92), vec2(1.0), huv));
    float conf = e.x * e.y;
    conf *= 1.0 - smoothstep(uSSR.z * 0.7, uSSR.z, rough);
    conf *= 1.0 - smoothstep(0.6, 1.0, tHit / uSSR.x);
    conf *= 1.0 - smoothstep(0.3, 0.7, dot(R, -V));           // rays back toward the camera leave the screen
    if (uFrame.z > 0.5) { fragColor = vec4(0.0); return; }   // [BTDR:SS.HISTRESET] no valid last frame yet
    vec3 L = texture(sTD2DInputs[2], prevUV(fetchRel(huv).xyz + uCamPos.xyz)).rgb;
    if (any(isnan(L)) || any(isinf(L))) L = vec3(0.0);
    fragColor = vec4(min(L, vec3(32.0)), conf);
}
