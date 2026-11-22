// [BTDR:FILE.SSCOMMON] ss_common.glsl — helpers shared by the screen-space passes (ssgi, ssr, ss_accum)
// G-Buffer position is camera-relative ([BTDR:GBUF.RELPOS]); background pixels store 0.
// POSBUF / NRMBUF are #defined by the including shader.
vec2 projectUV(vec3 wp, vec4 P, vec4 R, vec4 U, vec4 F) { return camProject(wp, P, R, U, F); }   // [BTDR:CAM.ORTHO]
vec2 curUV(vec3 wp)  { return projectUV(wp, uCamPos, uCamRight, uCamUp, uCamFwd); }
vec2 prevUV(vec3 wp) { return projectUV(wp, uPrevPos, uPrevRight, uPrevUp, uPrevFwd); }
float viewDepth(vec3 wp) { return dot(wp - uCamPos.xyz, uCamFwd.xyz); }
// camera-relative position | material AO; xyz = 0 on the background
vec4 fetchRel(vec2 uv)
{
    ivec2 sz = textureSize(POSBUF, 0);
    return texelFetch(POSBUF, clamp(ivec2(uv * vec2(sz)), ivec2(0), sz - 1), 0);
}
vec4 fetchNrm(vec2 uv)
{
    ivec2 sz = textureSize(NRMBUF, 0);
    return texelFetch(NRMBUF, clamp(ivec2(uv * vec2(sz)), ivec2(0), sz - 1), 0);
}
bool isGeoRel(vec4 p) { return dot(p.xyz, p.xyz) > 1e-8; }
bool inScreen(vec2 uv) { return all(greaterThanEqual(uv, vec2(0.0))) && all(lessThanEqual(uv, vec2(1.0))); }
// interleaved gradient noise (Jimenez), animated per frame
float ign(vec2 p, float k) { return fract(52.9829189 * fract(dot(p + k * vec2(5.588238, 5.588238), vec2(0.06711056, 0.00583715)))); }
