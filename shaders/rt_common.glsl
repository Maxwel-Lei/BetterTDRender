// [BTDR:FILE.RTCOMMON] rt_common.glsl — hardware ray queries against the proxy scene (M4)
// Included by the GLSL POPs rt_probes / rt_refl. Input 1 of the POP is the proxy scene `rtscene/out` (same
// geometry as the acceleration structure `uScene`, Collisions page); `rtMat` holds two texels per object:
// [2i] albedo rgb | metallic, [2i+1] emissive rgb | 0 ([BTDR:EXT.RTMAT]). Needs env_lookup (ENV_SHARP / ENV_ATLAS).
// (the GLSL POP declares its Arrays-page arrays itself: `rtMat` is a samplerBuffer; `uB` is declared in common.glsl)
// [BTDR:RT.FACESIGN] TD polygon winding -> outward face normal (measured on the floor of the test scene)
#ifndef RT_FACE_SIGN
#define RT_FACE_SIGN 1.0
#endif
struct Hit { bool hit; float t; vec3 n; int obj; bool backface; };

// [BTDR:RT.TRACE] closest hit; the face normal comes from the triangle's corners (proxies need no normals)
Hit traceScene(vec3 o, vec3 d, float tmin, float tmax)
{
    Hit h; h.hit = false; h.t = tmax; h.n = vec3(0.0, 1.0, 0.0); h.obj = -1; h.backface = false;
    rayQueryEXT rq;
    rayQueryInitializeEXT(rq, uScene, gl_RayFlagsOpaqueEXT, 0xFF, o, tmin, d, tmax);
    while (rayQueryProceedEXT(rq)) {}
    if (rayQueryGetIntersectionTypeEXT(rq, true) != gl_RayQueryCommittedIntersectionTriangleEXT) return h;
    h.hit = true;
    h.t = rayQueryGetIntersectionTEXT(rq, true);
    uint prim = uint(rayQueryGetIntersectionPrimitiveIndexEXT(rq, true));
    uint v0 = TDInputPrimVertsStartIndex(1, prim);
    uint i0 = TDInputPointIndex(1, v0), i1 = TDInputPointIndex(1, v0 + 1u), i2 = TDInputPointIndex(1, v0 + 2u);
    vec3 a = TDIn_P(1, i0), b = TDIn_P(1, i1), c = TDIn_P(1, i2);
    h.n = normalize(cross(b - a, c - a) + vec3(0.0, 1e-12, 0.0)) * RT_FACE_SIGN;
    h.obj = int(TDIn_ObjId(1, i0) + 0.5);
    h.backface = dot(h.n, d) > 0.0;
    return h;
}
bool occluded(vec3 o, vec3 d, float tmax)
{
    rayQueryEXT rq;
    rayQueryInitializeEXT(rq, uScene, gl_RayFlagsOpaqueEXT | gl_RayFlagsTerminateOnFirstHitEXT, 0xFF, o, 0.002, d, tmax);
    while (rayQueryProceedEXT(rq)) {}
    return rayQueryGetIntersectionTypeEXT(rq, true) != gl_RayQueryCommittedIntersectionNoneEXT;
}
// [BTDR:RT.SHADE] radiance leaving a hit point, Lumen "surface cache" quality: diffuse only (metals reflect their
// base colour), the sun with a traced shadow ray, ambient from RT_AMBIENT(p, n) (probes or environment), emissive.
vec3 shadeHit(vec3 o, vec3 d, Hit h)
{
    vec3 p = o + d * h.t;
    vec3 n = h.backface ? -h.n : h.n;
    vec4 m0 = texelFetch(rtMat, 2 * max(h.obj, 0));
    vec4 m1 = texelFetch(rtMat, 2 * max(h.obj, 0) + 1);
    vec3 L = normalize(uSunDir.xyz);
    float NoL = max(dot(n, L), 0.0);
    vec3 E = RT_AMBIENT(p, n);
    if (NoL > 0.0 && (uSunPos.w < 0.5 || !occluded(p + n * 0.01, L, 100.0)))
        E += uSunColor.rgb * uSunDir.w * NoL / PI;
    return m0.rgb * E + m1.rgb;
}
