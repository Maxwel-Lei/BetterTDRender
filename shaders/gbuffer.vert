// [BTDR:FILE.GBUF] gbuffer.vert — G-Buffer vertex shader (mirror materials)
out Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
    vec4 color;     // [BTDR:GBUF.INSTCOLOR] instance colour (1 without instancing / Instance Color)
} oVert;
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
}
