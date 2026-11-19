// [BTDR:FILE.FORWARD] forward.frag — M6b blended transparency (smoke, sprites, holograms, particles): forward-lit
// material of the blended mirrors scene/b* drawn by `tblend` ([BTDR:FWD.*], design in docs/M6_TRANSPARENCY.md §4).
// Output: premultiplied colour | coverage. Alpha mode: (rgb * a, a); additive mode: (rgb * a, 0). The material
// blends with ONE / ONE_MINUS_SRC_ALPHA, so both modes use the same state and can share a Render TOP.
// [BTDR:FWD.UB] the shared uniform block arrives as a 40 x 1 float texture (`ub_tex`, CHOP to TOP of `uniforms`)
// instead of a uniform array: a material whose sampler TOP changes does not re-cook, a uniform array bound to the
// CHOP would make it cook every frame. build.py turns `uniform vec4 uB[40]` into sUB + loadUB() ([BTDR:BUILD.FWDUB]).
#define LC_SHADOW sShadow
#define ENV_SHARP sEnvSharp
#define ENV_ATLAS sEnvAtlas
#define POSBUF sOpaquePos
#define NRMBUF sOpaquePos    // ss_common needs both names; fetchNrm is unused here
uniform sampler2D sBaseColor;
uniform sampler2D sAlpha;
uniform sampler2D sEmit;
uniform sampler2D sOpaquePos;    // opaque camera-relative position (gbuf2)
uniform sampler2D sFrontPos;     // combined position (tpos_src): the glass front layer where it is in front
uniform sampler2D sShadow;
uniform sampler2D sEnvSharp;
uniform sampler3D sEnvAtlas;
//#include env_lookup
//#include ss_common
uniform vec4 uBase;    // rgb base colour
uniform vec4 uEmit;    // rgb emissive, w 1 = emissive map
uniform vec4 uChan;    // w 1 = colours are sRGB
uniform vec4 uTrans;   // x opacity (alpha front)
uniform vec4 uTrans2;  // x 1 = alpha map
uniform vec4 uBlend;   // x lit (0 = emissive only), y soft-particle distance, z 1 = additive, w glass dimming

in Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
    vec4 color;
    vec2 texCoord1;   // [BTDR:GBUF.UVSET] declared to match gbuffer.vert (forward materials read uv0 only)
} iVert;

layout(location = 0) out vec4 oColor;

vec3 toLinear(vec3 c) { return uChan.w > 0.5 ? pow(max(c, 0.0), vec3(2.2)) : c; }

// [BTDR:FWD.SHADOW] 8-tap PCF of the BTDR sun shadow map (same mapping as LIGHT.SHADOW, no blocker search:
// smoke and sprites do not need contact hardening)
float fwdShadow(vec3 wp)
{
    if (uSunPos.w < 0.5) return 1.0;
    vec3 rel = wp - uSunPos.xyz;
    vec2 suv = vec2(dot(rel, uSunRight.xyz), dot(rel, uSunUp.xyz)) / uSunRight.w + 0.5;
    if (suv.x < 0.0 || suv.x > 1.0 || suv.y < 0.0 || suv.y > 1.0) return 1.0;
    float depth = dot(uSunPos.xyz - wp, uSunDir.xyz);
    float texel = 1.0 / float(textureSize(sShadow, 0).x);
    float r = max(0.012 * max(uSunColor.w, 0.2) / uSunRight.w, texel * 1.5);
    float ang = hash12(gl_FragCoord.xy) * 6.2831853;
    float bias = 0.01 + uSunRight.w * texel * 2.0;
    float lit = 0.0;
    for (int i = 0; i < 8; i++) {
        float rr = sqrt((float(i) + 0.5) / 8.0);
        float th = float(i) * 2.39996323 + ang;
        float d = texture(sShadow, suv + vec2(cos(th), sin(th)) * rr * r).r;
        lit += (d > 0.001 && d < depth - bias) ? 0.0 : 1.0;
    }
    return lit / 8.0;
}

void main()
{
    TDCheckDiscard();
    TDCheckOrderIndTrans();
    loadUB();
    vec2 uvc = iVert.texCoord;
    float a = clamp(uTrans.x, 0.0, 1.0);
    if (uTrans2.x > 0.5) { vec4 am = texture(sAlpha, uvc); a *= am.a < 0.999 ? am.a : am.r; }
    vec4 bt = texture(sBaseColor, uvc);
    a *= bt.a;                                   // sprites often carry their shape in the colour map's alpha

    // [BTDR:FWD.SOFT] depth test against the opaque scene by hand (the blended pass has its own depth buffer), fade
    // out near opaque surfaces (soft particles) and near the camera
    vec2 suv = gl_FragCoord.xy / vec2(textureSize(sOpaquePos, 0));
    vec3 rp = iVert.worldPos - iVert.camPos;
    float z = dot(rp, uCamFwd.xyz);
    vec4 op = fetchRel(suv);
    float zo = isGeoRel(op) ? dot(op.xyz, uCamFwd.xyz) : 1e9;
    if (z > zo) discard;
    float soft = max(uBlend.y, 1e-4);
    a *= clamp((zo - z) / soft, 0.0, 1.0) * clamp((z - uClip.x) / soft, 0.0, 1.0);
    // behind the glass front layer: dimmed, not refracted (only the front layer refracts)
    ivec2 fs = textureSize(sFrontPos, 0);
    vec4 fp = texelFetch(sFrontPos, clamp(ivec2(suv * vec2(fs)), ivec2(0), fs - 1), 0);
    float zf = isGeoRel(fp) ? dot(fp.xyz, uCamFwd.xyz) : 1e9;
    float dim = z > zf + 1e-3 ? uBlend.w : 1.0;
    if (a < 1.0 / 512.0) discard;

    vec3 base = toLinear(uBase.rgb) * toLinear(bt.rgb);
    vec3 emit = toLinear(uEmit.rgb);
    if (uEmit.w > 0.5) emit *= toLinear(texture(sEmit, uvc).rgb);

    // [BTDR:FWD.LIGHT] non-directional lighting (UE5 "volumetric non-directional"): cards and smoke have no
    // meaningful normal, so the ambient is the average of both sides and the sun is wrapped
    vec3 col = emit;
    if (uBlend.x > 0.5) {
        vec3 n = iVert.worldNorm;
        n = dot(n, n) > 1e-10 ? normalize(n) : -uCamFwd.xyz;
        vec3 amb = 0.5 * (envIrradiance(n) + envIrradiance(-n));
        float wrap = 0.5 + 0.5 * abs(dot(n, uSunDir.xyz));
        vec3 sun = uSunColor.rgb * uSunDir.w * fwdShadow(iVert.worldPos) * wrap / PI;
        col += base * (amb + sun);
    }
    col *= dim;
    oColor = TDOutputSwizzle(vec4(col * a, uBlend.z > 0.5 ? 0.0 : a * dim));
}
