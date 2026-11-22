// [BTDR:FILE.COMMON] common.glsl — prepended to every BTDR shader by build.py
// [BTDR:UNI.BLOCK] one shared uniform array, filled once per frame by the Script CHOP `uniforms`
// (ext/uniforms_chop.py). Slot layout must match that file.
uniform vec4 uB[124];
#define uCamPos    uB[0]    // xyz camera position
#define uCamRight  uB[1]    // xyz camera right
#define uCamUp     uB[2]    // xyz camera up
#define uCamFwd    uB[3]    // xyz camera forward, w tan(horizontal fov / 2)
#define uPrevPos   uB[4]    // previous frame camera (same layout)
#define uPrevRight uB[5]
#define uPrevUp    uB[6]
#define uPrevFwd   uB[7]
#define uJitter    uB[8]    // xy sub-pixel jitter in NDC (current), zw previous
#define uFrame     uB[9]    // x frame index, y delta seconds, z history reset, w seconds
#define uSunDir    uB[10]   // xyz direction TO the light, w intensity
#define uSunColor  uB[11]   // rgb colour, w shadow softness
#define uSunPos    uB[12]   // xyz shadow camera position, w shadows on
#define uSunRight  uB[13]   // xyz shadow camera right, w ortho width
#define uSunUp     uB[14]   // xyz shadow camera up, w shadow far
#define uEnv       uB[15]   // x intensity, y rotation (radians), z background mode (0 colour, 1 environment, -1 transparent), w background blur
#define uBgColor   uB[16]   // rgb background colour (linear), w background intensity
#define uGrade     uB[17]   // x exposure multiplier, y vignette, z grain, w tonemap (0 none, 1 ACES)
#define uView      uB[18]   // x debug view, y sRGB colour inputs, z distance fade start, w distance fade end
#define uClip      uB[19]   // x camera near, y camera far, z aspect (w / h), w (0.9.4) 1 = orthographic camera
#define uTAA       uB[20]   // x current-frame weight, y 1 = TAA on, z variance clip gamma, w (0.9.6) static stabilization
#define uBloom     uB[21]   // x intensity, y threshold, z knee, w radius (mip-chain blend)
#define uAE        uB[22]   // x auto exposure on, y min EV, z max EV, w key (target mid grey)
#define uAE2       uB[23]   // x speed up, y speed down, z delta seconds, w reset
#define uDOF       uB[24]   // x focal length mm, y f-stop, z focus distance, w max blur radius px
#define uDOF2      uB[25]   // x sensor width mm, y on, z radius step (quality), w fog shadow blur (texels)
#define uMB        uB[26]   // x shutter (fraction of a frame), y max blur px, z samples, w on
#define uSS        uB[27]   // x screen-space AO strength, y SSGI strength, z SSR strength (0 = off)
#define uGI        uB[28]   // x AO / GI radius (scene units), y steps, z directions, w fog jitter (0-1)
#define uSSR       uB[29]   // x max distance, y steps, z max roughness, w thickness
#define uAcc       uB[30]   // x current-frame weight, y clamp sigma, z reset, w fog current-frame weight
#define uFog       uB[31]   // x density, y height falloff, z base height, w anisotropy g
#define uFog2      uB[32]   // x near, y far (fog distance), z ambient intensity, w noise amount
#define uFog3      uB[33]   // rgb albedo (fog colour), w on
#define uHF        uB[34]   // height-field AO map: x centre x, y centre z, z width, w top camera height
#define uHF2       uB[35]   // x on, y intensity, z radius, w directions
#define uRT        uB[36]   // M4: x probe GI on, y traced reflections on, z reflection max roughness, w GI intensity
#define uRT2       uB[37]   // xyz probe grid minimum, w rays per probe
#define uRT3       uB[38]   // xyz probe spacing, w radiance clamp
#define uRT4       uB[39]   // x / y traced-reflection grid width / height, z reflection intensity
#define uAmb       uB[40]   // 0.7.5: rgb Ambient Light COMPs (colour x dimmer, summed); 0.9.8: w specular occlusion strength ([BTDR:COMP.SPECOCC])
#define uSSSG      uB[41]   // 0.8.0 subsurface: x on, y Scatter Scale, z taps per side, w transmission on
#define uUnit      uB[42]   // 0.8.3 [BTDR:UNI.UNIT] x scene units per metre, y metres per scene unit
#define uMisc      uB[43]   // 0.8.4: x energy compensation on ([BTDR:LIGHT.ENERGY]); 0.9.0: y local light count; 0.9.1: z fog multiple scattering; 0.9.2: w object motion vectors present ([BTDR:UNI.VELOCITY])
#define UM(m_)     ((m_) * uUnit.x)  // a length designed in metres, in scene units (parameter not named x: .x would expand)
// [BTDR:UNI.SSS] subsurface profile k (0..7) = Subsurface slot k: three slots each, 44 + 3k ..
#define SSS_A(k)   uB[44 + 3 * (k)]   // rgb scatter distance per channel (m, x Scatter Scale), w scatter strength (0 = thin)
#define SSS_B(k)   uB[45 + 3 * (k)]   // rgb transmission colour x strength, w 1 = thin (sheet)
#define SSS_C(k)   uB[46 + 3 * (k)]   // x texture detail (post-scatter share), y sheet thickness (m)
const float PI = 3.14159265359;

float hash12(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
// [BTDR:UNI.LOCALLIGHTS] (0.9.0) local lights: 8 x 5 slots from 68 ([BTDR:LIGHT.LOCAL])
//   0 xyz position, w type (1 point, 2 spot, 3 distant)
//   1 rgb colour x intensity (Dimmer x pi x Intensity Multiplier x Local Intensity), w attenuation end
//   2 xyz direction the light points (spot axis; distant: direction TO the light), w cos of the outer cone half-angle
//   3 x attenuation start, y attenuation exponent, z cos of the inner cone half-angle, w falloff (0 none, 1 the
//     Light COMP's attenuation, 2 physical inverse square)
//   4 x cone roll-off exponent, y spot shadow map index + 1 (0 = none; 0.9.1)
#define LL_MAX 8
#define LL_COUNT int(uMisc.y + 0.5)
#define LL(i, k) uB[68 + 5 * (i) + (k)]
// [BTDR:UNI.LLSHADOW] (0.9.1) spot-light shadow maps 0..3, 4 slots each from 108: rows 0..2 of the light camera's
// world-to-camera matrix (xyz | w), 3 x tan(half fov), y near, z bias (scene units), w 1 = on
#define LLS(k, r) uB[108 + 4 * (k) + (r)]
// [BTDR:CAM.ORTHO] (0.9.4) orthographic camera: uClip.w = 1 and uCamFwd.w / uPrevFwd.w hold half the view width (scene
// units) instead of tan(fov / 2). Every pass that builds a camera ray, projects a point or turns a world size into
// pixels goes through these, so perspective results are unchanged (same arithmetic).
#define ORTHO (uClip.w > 0.5)
vec3 camOffset(vec2 ndc) { return ndc.x * uCamFwd.w * uCamRight.xyz + ndc.y * uCamFwd.w / uClip.z * uCamUp.xyz; }
// world point at view depth d (along the view axis) under screen position ndc
vec3 camPoint(vec2 ndc, float d)
{
    vec3 o = camOffset(ndc);
    return ORTHO ? uCamPos.xyz + o + uCamFwd.xyz * d : uCamPos.xyz + (uCamFwd.xyz + o) * d;
}
// unit direction of the camera ray through ndc
vec3 camDir(vec2 ndc) { return ORTHO ? uCamFwd.xyz : normalize(uCamFwd.xyz + camOffset(ndc)); }
// camera -> surface direction for a camera-relative position
vec3 viewDirRel(vec3 rel) { return ORTHO ? uCamFwd.xyz : rel / max(length(rel), 1e-6); }
// screen uv of a world point under a camera basis (P position, R right, U up, F forward | w)
vec2 camProject(vec3 wp, vec4 P, vec4 R, vec4 U, vec4 F)
{
    vec3 v = wp - P.xyz;
    float z = ORTHO ? 1.0 : max(dot(v, F.xyz), 1e-4);
    return vec2(dot(v, R.xyz) / (z * F.w), dot(v, U.xyz) / (z * F.w / uClip.z)) * 0.5 + 0.5;
}
// pixels per scene unit at view depth z, horizontally, in an image xres pixels wide
float pxPerUnit(float z, float xres) { return xres * 0.5 / ((ORTHO ? 1.0 : z) * uCamFwd.w); }

// [BTDR:LIGHT.LOCALATT] (0.9.1) one local light's direction and attenuation at P (shared by the surface lighting, the
// fog and the ray-traced hit shading); returns the attenuation (0 = no light), L = direction to the light, dist =
// distance to it (1e9 for a distant light)
float llAtten(int i, vec3 P, out vec3 L, out float dist)
{
    vec4 l0 = LL(i, 0), l1 = LL(i, 1), l2 = LL(i, 2), l3 = LL(i, 3), l4 = LL(i, 4);
    int t = int(l0.w + 0.5);
    float att = 1.0;
    if (t == 3) { L = normalize(l2.xyz); dist = 1e9; return 1.0; }
    vec3 d = l0.xyz - P;
    dist = length(d);
    L = d / max(dist, 1e-6);
    int f = int(l3.w + 0.5);
    if (f == 1) att = pow(clamp((l1.w - dist) / max(l1.w - l3.x, 1e-4), 0.0, 1.0), max(l3.y, 1e-3));
    else if (f == 2) { float m = UM(1.0); att = m * m / max(dist * dist, UM(0.01) * UM(0.01)); }
    if (t == 2) {
        float c = dot(-L, normalize(l2.xyz));
        att *= pow(smoothstep(l2.w, max(l3.z, l2.w + 1e-4), c), max(l4.x, 1e-3));
    }
    return att;
}
