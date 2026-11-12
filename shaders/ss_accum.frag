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
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec4 s = texture(sTD2DInputs[0], vUV.st + vec2(x, y) * px);
            m1 += s; m2 += s * s;
        }
    vec4 mu = m1 / 9.0;
    vec4 sig = sqrt(max(m2 / 9.0 - mu * mu, 0.0));
    vec4 p = fetchRel(vUV.st);
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
