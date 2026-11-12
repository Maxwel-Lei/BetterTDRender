// [BTDR:FILE.LIGHT] lighting.frag — the split lighting terms as four buffers ([BTDR:LIGHT.SPLIT]). Since 0.5.1 only the
// Debug View reads them (Direct Light, Environment Diffuse / Specular, Bounce Light, Reflections); the final image
// computes the same terms inline in composite.frag ([BTDR:COMP.INLINE]), so this pass does not cook normally.
// 2D inputs: 0 base|metal, 1 normal|rough, 2 camera-relative pos|ao, 3 shadow depth, 4 emissive, 5 sharp environment
// 3D inputs: 0 pre-filtered environment atlas
#define LC_BASE sTD2DInputs[0]
#define LC_NRM sTD2DInputs[1]
#define LC_POS sTD2DInputs[2]
#define LC_SHADOW sTD2DInputs[3]
#define LC_EMIT sTD2DInputs[4]
#define ENV_SHARP sTD2DInputs[5]
#define ENV_ATLAS sTD3DInputs[0]
//#include env_lookup
//#include lighting_core
layout(location = 0) out vec4 oDirect;
layout(location = 1) out vec4 oAmbDiff;
layout(location = 2) out vec4 oAmbSpec;
layout(location = 3) out vec4 oBRDF;
void main()
{
    lightingTerms(vUV.st, oDirect, oAmbDiff, oAmbSpec, oBRDF);
}
