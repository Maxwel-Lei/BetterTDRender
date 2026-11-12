// [BTDR:FILE.GBUF] gbuffer.frag — G-Buffer pixel shader
//   RT0: base colour rgb (linear) | metallic
//   RT1: world normal xyz         | roughness
//   RT2: position relative to the camera xyz | ambient occlusion  ([BTDR:GBUF.RELPOS] keeps 16-bit float precise near the camera)
//   RT3: emissive rgb (linear)    | unused
// [BTDR:GBUF.MATERIAL] every uniform below is bound by expression to the source material (ext/BTDRExt.py, _bind_material)
uniform sampler2D sBaseColor;
uniform sampler2D sMetallic;
uniform sampler2D sRoughness;
uniform sampler2D sAO;
uniform sampler2D sNormal;
uniform sampler2D sEmit;
uniform vec4 uBase;    // rgb base colour
uniform vec4 uPBR;     // x metallic, y roughness, z AO strength, w normal map strength (0 = no normal map, < 0 = DirectX map)
uniform vec4 uEmit;    // rgb emissive colour, w 1 = an emissive map is assigned
uniform vec4 uChan;    // xyz channel source of the metallic, roughness, AO maps (PBR MAT menu index), w 1 = colours are sRGB

in Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
} iVert;

layout(location = 0) out vec4 oAlbedo;
layout(location = 1) out vec4 oNormal;
layout(location = 2) out vec4 oPosition;
layout(location = 3) out vec4 oEmissive;

// PBR MAT "Channel Source" menu: luminance, red, green, blue, alpha, rgbaverage, average
float pick(vec4 t, float mode)
{
    int m = int(mode + 0.5);
    if (m == 0) return dot(t.rgb, vec3(0.2126, 0.7152, 0.0722));
    if (m == 1) return t.r;
    if (m == 2) return t.g;
    if (m == 3) return t.b;
    if (m == 4) return t.a;
    return (t.r + t.g + t.b) / 3.0;
}
vec3 toLinear(vec3 c)
{
    return uChan.w > 0.5 ? pow(max(c, 0.0), vec3(2.2)) : c;
}

void main()
{
    TDCheckDiscard();
    vec2 uvc = iVert.texCoord;
    vec3 base = toLinear(uBase.rgb) * toLinear(texture(sBaseColor, uvc).rgb);
    float metal = uPBR.x * pick(texture(sMetallic, uvc), uChan.x);
    float rough = uPBR.y * pick(texture(sRoughness, uvc), uChan.y);
    float ao = mix(1.0, pick(texture(sAO, uvc), uChan.z), clamp(uPBR.z, 0.0, 1.0));
    vec3 emit = toLinear(uEmit.rgb);
    if (uEmit.w > 0.5) emit *= toLinear(texture(sEmit, uvc).rgb);

    // [BTDR:GBUF.NORMAL] geometry without a normal attribute gets a flat normal from screen-space derivatives
    vec3 n = iVert.worldNorm;
    if (dot(n, n) < 1e-10) {
        n = normalize(cross(dFdx(iVert.worldPos), dFdy(iVert.worldPos)));
        if (dot(n, iVert.camPos - iVert.worldPos) < 0.0) n = -n;
    } else {
        n = normalize(n);
        if (!gl_FrontFacing) n = -n;
    }
    // [BTDR:GBUF.NORMALMAP] tangent frame from screen-space derivatives: no tangent attribute needed
    if (uPBR.w != 0.0) {
        vec3 dp1 = dFdx(iVert.worldPos), dp2 = dFdy(iVert.worldPos);
        vec2 du1 = dFdx(uvc), du2 = dFdy(uvc);
        vec3 dp2p = cross(dp2, n), dp1p = cross(n, dp1);
        vec3 T = dp2p * du1.x + dp1p * du2.x;
        vec3 B = dp2p * du1.y + dp1p * du2.y;
        float inv = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-20));
        vec3 tn = texture(sNormal, uvc).xyz * 2.0 - 1.0;
        if (uPBR.w < 0.0) tn.y = -tn.y;         // [BTDR:GBUF.NCONV] DirectX (Y-) normal map
        tn.xy *= abs(uPBR.w);
        n = normalize(mat3(T * inv, B * inv, n) * tn);
    }
    oAlbedo = vec4(base, clamp(metal, 0.0, 1.0));
    oNormal = vec4(n, clamp(rough, 0.04, 1.0));
    oPosition = vec4(iVert.worldPos - iVert.camPos, ao);
    oEmissive = vec4(emit, 1.0);
}
