// [BTDR:FILE.VEL] velocity.vert — (0.9.2) object motion vectors ([BTDR:VEL.OBJECT]). Drawn by the `velocity` Render
// TOP, only for objects that moved this frame ([BTDR:UNI.VELOCITY]): one material per object, its previous world
// matrix comes in as four uniform columns, set each frame by `uniforms`. Like the G-Buffer materials, built without
// common.glsl. Output: world-space displacement since the last frame + distance to the camera (validity check).
uniform vec4 uPW0;
uniform vec4 uPW1;
uniform vec4 uPW2;
uniform vec4 uPW3;
uniform vec4 uVelOpt;   // x seconds per frame (particle velocity attributes are per second)
out Vertex {
    vec3 disp;
    vec3 rel;
} oVert;
void main()
{
    vec4 wp = TDDeform(TDPos());
    gl_Position = TDWorldToProj(wp);
    mat4 W = uTDMats[TDCameraIndex()].world;
    // previous position of this vertex: same object-space point under last frame's world matrix (instances keep
    // their own transform; instance motion itself is not seen, [BTDR:VEL.LIMITS])
    vec4 pp = mat4(uPW0, uPW1, uPW2, uPW3) * (inverse(W) * wp);
    // [BTDR:VEL.ATTRIB] (G1) a velocity point attribute moves the vertex by itself: PartVel (Particle POP), v (SOPs)
    vec3 av = TDAttrib_PartVel() + TDAttrib_v();
    pp.xyz -= mat3(W) * av * uVelOpt.x;
    oVert.disp = wp.xyz - pp.xyz;
    oVert.rel = wp.xyz - uTDMats[TDCameraIndex()].camInverse[3].xyz;
}
