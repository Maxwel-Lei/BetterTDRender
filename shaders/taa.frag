// [BTDR:FILE.TAA] taa.frag — temporal anti-aliasing (ported from ue5r/shaders/taa.frag)
// inputs: 0 current HDR (rendered with sub-pixel jitter), 1 history (Feedback TOP of this node),
//         2 G-Buffer camera-relative position | ao, 3 G-Buffer normal | roughness (geometry mask)
// output: rgb resolved HDR colour, a temporally stable view depth (scene units, background = camera far)
// uTAA: x current-frame weight, y 1 = TAA on, z variance clip gamma
out vec4 fragColor;

bool isGeo(vec2 uv)
{
    vec4 n = texture(sTD2DInputs[3], uv);
    return dot(n.xyz, n.xyz) > 0.25;
}
// world position of the pixel (geometry) or a far point along the view ray (background)
vec3 pixelWorldPos(vec2 uv, out bool geo)
{
    ivec2 sz = textureSize(sTD2DInputs[2], 0);
    ivec2 p = clamp(ivec2(uv * vec2(sz)), ivec2(0), sz - 1);
    geo = dot(texelFetch(sTD2DInputs[3], p, 0).xyz, texelFetch(sTD2DInputs[3], p, 0).xyz) > 0.25;
    if (geo) return texelFetch(sTD2DInputs[2], p, 0).xyz + uCamPos.xyz;
    vec2 ndc = uv * 2.0 - 1.0;
    vec3 rd = normalize(uCamFwd.xyz + ndc.x * uCamFwd.w * uCamRight.xyz + ndc.y * uCamFwd.w / uClip.z * uCamUp.xyz);
    return uCamPos.xyz + rd * 1000.0;
}
vec2 project(vec3 wp, vec4 P, vec4 R, vec4 U, vec4 F)
{
    vec3 v = wp - P.xyz;
    float z = max(dot(v, F.xyz), 1e-4);
    return vec2(dot(v, R.xyz) / (z * F.w), dot(v, U.xyz) / (z * F.w / uClip.z)) * 0.5 + 0.5;
}
float viewDepth(vec3 wp) { return dot(wp - uCamPos.xyz, uCamFwd.xyz); }

vec3 RGB2YCoCg(vec3 c) { return vec3(dot(c, vec3(0.25, 0.5, 0.25)), dot(c, vec3(0.5, 0.0, -0.5)), dot(c, vec3(-0.25, 0.5, -0.25))); }
vec3 YCoCg2RGB(vec3 c) { return vec3(c.x + c.y - c.z, c.x + c.z, c.x - c.y - c.z); }
float lumaOf(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
// Karis: weight HDR samples so bright speculars do not dominate the resolve
vec3 toneW(vec3 c) { return c / (1.0 + lumaOf(c)); }
vec3 untoneW(vec3 c) { return c / max(1.0 - lumaOf(c), 1e-4); }

// [BTDR:TAA.HISTORY] 5-tap Catmull-Rom history fetch (keeps the image sharp under reprojection)
vec3 sampleHistoryCR(vec2 uv)
{
    vec2 texSize = uTD2DInfos[1].res.zw;
    vec2 sp = uv * texSize;
    vec2 tp1 = floor(sp - 0.5) + 0.5;
    vec2 f = sp - tp1;
    vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
    vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
    vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
    vec2 w3 = f * f * (-0.5 + 0.5 * f);
    vec2 w12 = w1 + w2;
    vec2 tc0 = (tp1 - 1.0) / texSize;
    vec2 tc3 = (tp1 + 2.0) / texSize;
    vec2 tc12 = (tp1 + w2 / w12) / texSize;
    float a = w12.x * w0.y, b = w0.x * w12.y, c = w12.x * w12.y, d = w3.x * w12.y, e = w12.x * w3.y;
    vec3 r = texture(sTD2DInputs[1], vec2(tc12.x, tc0.y)).rgb * a
           + texture(sTD2DInputs[1], vec2(tc0.x, tc12.y)).rgb * b
           + texture(sTD2DInputs[1], tc12).rgb * c
           + texture(sTD2DInputs[1], vec2(tc3.x, tc12.y)).rgb * d
           + texture(sTD2DInputs[1], vec2(tc12.x, tc3.y)).rgb * e;
    return max(r / (a + b + c + d + e), 0.0);
}
vec3 clipAABB(vec3 aabbMin, vec3 aabbMax, vec3 q)
{
    vec3 center = 0.5 * (aabbMax + aabbMin);
    vec3 extent = 0.5 * (aabbMax - aabbMin) + 1e-5;
    vec3 v = q - center;
    vec3 a = abs(v / extent);
    float m = max(a.x, max(a.y, a.z));
    return m > 1.0 ? center + v / m : q;
}

void main()
{
    vec2 px = 1.0 / uTD2DInfos[0].res.zw;
    vec4 curA = texture(sTD2DInputs[0], vUV.st);
    vec3 cur = curA.rgb;
    if (any(isnan(cur)) || any(isinf(cur))) cur = vec3(0.0);       // [BTDR:TAA.NAN] never let a bad pixel in
    bool geo;
    vec3 wp = pixelWorldPos(vUV.st, geo);
    float dC = geo ? viewDepth(wp) : uClip.y;
    // off, first frames after a camera switch, or history of another size: pass the current frame through
    bool reset = uTAA.y < 0.5 || uFrame.z > 0.5 || any(notEqual(uTD2DInfos[1].res.zw, uTD2DInfos[0].res.zw));
    if (reset) { fragColor = vec4(cur, dC); return; }

    // [BTDR:TAA.CLIP] neighbourhood statistics, variance clipping in YCoCg (Salvi 2016)
    vec3 m1 = vec3(0.0), m2 = vec3(0.0);
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++) {
            vec3 s = RGB2YCoCg(toneW(texture(sTD2DInputs[0], vUV.st + vec2(x, y) * px).rgb));
            m1 += s; m2 += s * s;
        }
    vec3 mu = m1 / 9.0;
    vec3 sigma = sqrt(max(m2 / 9.0 - mu * mu, 0.0));
    vec3 bmin = mu - uTAA.z * sigma, bmax = mu + uTAA.z * sigma;

    // [BTDR:TAA.REPROJECT] screen motion = difference of the two UN-jittered projections of this surface
    // point. Using the point's previous projection directly would leak the G-Buffer jitter into the history
    // lookup and make the whole image wobble (ue5r bug).
    vec2 puv = vUV.st - (project(wp, uCamPos, uCamRight, uCamUp, uCamFwd) - project(wp, uPrevPos, uPrevRight, uPrevUp, uPrevFwd));
    bool offscreen = any(lessThan(puv, vec2(0.0))) || any(greaterThan(puv, vec2(1.0)));

    vec3 hc = sampleHistoryCR(puv);
    if (any(isnan(hc)) || any(isinf(hc))) hc = cur;                 // a poisoned history heals itself
    vec3 hist = clipAABB(bmin, bmax, RGB2YCoCg(toneW(hc)));
    float w = offscreen ? 0.4 : uTAA.x;
    vec3 res = mix(hist, RGB2YCoCg(toneW(cur)), w);

    // [BTDR:TAA.DEPTH] alpha: temporally stable view depth for depth of field / motion blur (the jittered
    // G-Buffer would make silhouettes flicker by a pixel)
    float dMin = dC, dMax = dC;
    for (int k = 0; k < 4; k++) {
        vec2 o = vec2(k == 0 ? -1.0 : (k == 1 ? 1.0 : 0.0), k == 2 ? -1.0 : (k == 3 ? 1.0 : 0.0)) * px;
        bool g; vec3 q = pixelWorldPos(vUV.st + o, g);
        float dq = g ? viewDepth(q) : uClip.y;
        dMin = min(dMin, dq); dMax = max(dMax, dq);
    }
    float dH = clamp(texture(sTD2DInputs[1], puv).a, dMin, dMax);
    fragColor = vec4(max(untoneW(YCoCg2RGB(res)), 0.0), offscreen ? dC : mix(dH, dC, w));
}
