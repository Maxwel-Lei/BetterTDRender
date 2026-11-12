// [BTDR:FILE.GBUF] gbuffer.vert — G-Buffer vertex shader (mirror materials)
out Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
} oVert;
// [BTDR:GBUF.SHARED] material shaders are built without common.glsl and read no per-frame uniform, so the
// mirror materials never re-cook. The TAA jitter is in the projection of the internal camera `cam_jit`
// ([BTDR:EXT.JITCAM]), not in this shader.

void main()
{
    // TDPos / TDNormal / TDTexCoord work for both SOP and POP geometry
    vec4 wp = TDDeform(TDPos());
    gl_Position = TDWorldToProj(wp);
    oVert.worldPos = wp.xyz;
    oVert.worldNorm = TDDeformNorm(TDNormal());
    oVert.texCoord = TDTexCoord(0).st;
    oVert.camPos = uTDMats[TDCameraIndex()].camInverse[3].xyz;
}
