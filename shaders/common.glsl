// [BTDR:FILE.COMMON] common.glsl — prepended to every BTDR shader by build.py
// [BTDR:UNI.BLOCK] one shared uniform array, filled once per frame by the Script CHOP `uniforms`
// (ext/uniforms_chop.py). Slot layout must match that file.
uniform vec4 uB[40];
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
#define uEnv       uB[15]   // x intensity, y rotation (radians), z background mode (0 colour, 1 environment), w background blur
#define uBgColor   uB[16]   // rgb background colour (linear), w background intensity
#define uGrade     uB[17]   // x exposure multiplier, y vignette, z grain, w tonemap (0 none, 1 ACES)
#define uView      uB[18]   // x debug view, y sRGB colour inputs, z distance fade start, w distance fade end
#define uClip      uB[19]   // x camera near, y camera far, z aspect (w / h)
#define uTAA       uB[20]   // x current-frame weight, y 1 = TAA on, z variance clip gamma
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
const float PI = 3.14159265359;

float hash12(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
