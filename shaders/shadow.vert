// [BTDR:FILE.SHADOW] shadow.vert — linear distance from the shadow camera plane
out Vertex { float depth; } oVert;
void main()
{
    vec4 wp = TDDeform(TDPos());
    gl_Position = TDWorldToProj(wp);
    vec4 cp = uTDMats[TDCameraIndex()].cam * wp;
    oVert.depth = -cp.z;
}
