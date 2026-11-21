// [BTDR:FILE.SSACCUM] ss_accum.frag — temporal accumulation for the noisy screen-space passes (SSGI / AO, SSR)
// inputs: 0 current (noisy), 1 history (Feedback TOP of this node), 2 camera-relative position (G-Buffer)
// uAcc: x current-frame weight, y neighbourhood clamp sigma, z reset
// RT_ACC (rt_accum_frag, M4): traced reflection ratio; input 3 = normal | roughness ([BTDR:ACCUM.RT])
#define POSBUF sTD2DInputs[2]
#define NRMBUF sTD2DInputs[2]
//#include ss_common
out vec4 fragColor;
void main()
{
    vec2 px = 1.0 / uTD2DInfos[0].res.zw;
    vec4 cur = texture(sTD2DInputs[0], vUV.st);
    if (uAcc.z > 0.5 || any(notEqual(uTD2DInfos[1].res.zw, uTD2DInfos[0].res.zw))) { fragColor = cur; return; }
    vec4 m1 = vec4(0.0), m2 = vec4(0.0);
    vec4 p = fetchRel(vUV.st);
#ifdef RT_ACC
    // [BTDR:ACCUM.RTEDGE] (0.8.4) the neighbourhood only counts texels on the same surface (normal, plane distance):
    // a plain 3x3 here is a 12x12-pixel block at full resolution and mixed the box top into its face
    vec3 nC = texture(sTD2DInputs[3], vUV.st).xyz;
    bool okC = dot(nC, nC) > 0.25;
    nC = okC ? normalize(nC) : vec3(0.0, 1.0, 0.0);
    float tolC = UM(0.02) + 0.02 * length(p.xyz);
    float wsum = 0.0;
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec2 q = vUV.st + vec2(x, y) * px;
            vec4 s = texture(sTD2DInputs[0], q);
            float wq = 1.0;
            if (okC && (x != 0 || y != 0)) {
                vec3 nq = texture(sTD2DInputs[3], q).xyz;
                vec3 pq = fetchRel(q).xyz;
                wq = dot(nq, nq) > 0.25 ? pow(max(dot(nC, normalize(nq)), 0.0), 16.0) * exp(-abs(dot(pq - p.xyz, nC)) / tolC) : 0.0;
            }
            m1 += s * wq; m2 += s * s * wq; wsum += wq;
        }
    vec4 mu = m1 / wsum;
    vec4 sig = sqrt(max(m2 / wsum - mu * mu, 0.0));
#else
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec4 s = texture(sTD2DInputs[0], vUV.st + vec2(x, y) * px);
            m1 += s; m2 += s * s;
        }
    vec4 mu = m1 / 9.0;
    vec4 sig = sqrt(max(m2 / 9.0 - mu * mu, 0.0));
#endif
    vec3 wp = p.xyz + uCamPos.xyz;
    vec2 vel = isGeoRel(p) ? (curUV(wp) - prevUV(wp)) : vec2(0.0);   // jitter-free screen motion
    vec2 puv = vUV.st - vel;
    // [BTDR:ACCUM.MOTION] reflections and bounce light move differently from the surface they sit on, so history
    // reprojected by surface motion smears when the camera moves: trust it less (and clamp harder) when moving
    float m = clamp(length(vel * uTD2DInfos[0].res.zw) / 2.0, 0.0, 1.0);
#ifdef RT_ACC
    // [BTDR:ACCUM.RT] one ray per pixel at 1/4 resolution is noisy on rough surfaces: pre-filter the current frame
    // spatially there (3x3 mean, a full-resolution 12x12 block), accumulate slower, clamp looser
    float rough = texture(sTD2DInputs[3], vUV.st).a;
    cur = mix(cur, mu, smoothstep(0.05, 0.35, rough));
    float sigma = mix(1.5, 0.75, m);
    float wcur = mix(0.06, 0.5, m);
#else
    float sigma = mix(uAcc.y, 0.75, m);
    float wcur = mix(uAcc.x, 0.5, m);
#endif
    vec4 h = texture(sTD2DInputs[1], puv);
    if (any(isnan(h)) || any(isinf(h))) h = cur;
    h = clamp(h, mu - sigma * sig, mu + sigma * sig);
    fragColor = mix(h, cur, inScreen(puv) ? wcur : 1.0);
}
