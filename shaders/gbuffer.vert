// [BTDR:FILE.GBUF] gbuffer.vert — G-Buffer vertex shader (mirror materials)
out Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
    vec4 color;     // [BTDR:GBUF.INSTCOLOR] instance colour (1 without instancing / Instance Color)
    vec2 texCoord1; // [BTDR:GBUF.UVSET] (0.8.3) the second UV set a map asks for (SOP Texture Coord uv1..uv7)
#ifdef SPRITE
    float spriteR;  // [BTDR:GBUF.SPRITE] (0.9.4) sphere radius of this point (scene units)
    vec3 camX;      // camera right / up / back: TDCameraIndex() only exists in the vertex stage
    vec3 camY;
    vec3 camZ;
#endif
} oVert;
#ifdef SPRITE
uniform vec4 uSprite;   // x point diameter (scene units, Point Sprite Size), y render height (pixels)
#endif
uniform vec4 uUV1;  // w: index of the extra UV set (0 = none); static per material, see gbuffer.frag
// [BTDR:GBUF.SHARED] material shaders are built without common.glsl and read no per-frame uniform, so the
// mirror materials never re-cook. The TAA jitter is in the projection of the internal camera `cam_jit`
// ([BTDR:EXT.JITCAM]), not in this shader.

void main()
{
    // TDPos / TDNormal work for both SOP and POP geometry; texture coordinates: [BTDR:GBUF.POPUV]
    vec4 wp = TDDeform(TDPos());
    gl_Position = TDWorldToProj(wp);
    oVert.worldPos = wp.xyz;
    oVert.worldNorm = TDDeformNorm(TDNormal());
    oVert.texCoord = TDTexAttrib_Tex(0).st;   // [BTDR:GBUF.POPUV] uv[0] on SOPs, `Tex` on POPs
    oVert.camPos = uTDMats[TDCameraIndex()].camInverse[3].xyz;
    oVert.color = TDInstanceColor(vec4(1.0));
    oVert.texCoord1 = TDTexAttrib_Tex(int(uUV1.w + 0.5)).st;   // [BTDR:GBUF.UVSET] uv[n] on SOPs (S3, 0.8.3)
#ifdef SPRITE
    // [BTDR:GBUF.SPRITE] (0.9.4) points drawn as small spheres: size in pixels from the projection (works for
    // perspective and orthographic cameras: proj[1][1] x half the height / clip w = pixels per scene unit)
    float diam = uSprite.x;
#ifdef SPRITE_SCALE
    diam *= TDAttrib_PointScale();     // only declared when the geometry has it ([BTDR:EXT.SPRITE])
#endif
    gl_PointSize = max(diam * uTDMats[TDCameraIndex()].proj[1][1] * 0.5 * uSprite.y / max(gl_Position.w, 1e-6), 1.0);
    oVert.spriteR = 0.5 * diam;
    mat4 CI = uTDMats[TDCameraIndex()].camInverse;
    oVert.camX = normalize(CI[0].xyz); oVert.camY = normalize(CI[1].xyz); oVert.camZ = normalize(CI[2].xyz);
#endif
}
