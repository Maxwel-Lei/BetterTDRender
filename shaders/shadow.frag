// [BTDR:FILE.SHADOW] shadow.frag
in Vertex { float depth; } iVert;
layout(location = 0) out vec4 oDepth;
void main()
{
    TDCheckDiscard();
    oDepth = vec4(iVert.depth, iVert.depth, iVert.depth, 1.0);
}
