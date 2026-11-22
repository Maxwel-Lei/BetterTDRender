// [BTDR:FILE.VEL] velocity.frag — rgb world displacement since the last frame, a distance to the camera (0 = none)
in Vertex {
    vec3 disp;
    vec3 rel;
} iVert;
layout(location = 0) out vec4 oVel;
void main()
{
    TDCheckDiscard();
    oVel = vec4(iVert.disp, max(length(iVert.rel), 1e-4));
}
