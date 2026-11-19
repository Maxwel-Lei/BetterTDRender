// [BTDR:FILE.GBUF] gbuffer.frag — G-Buffer pixel shader
//   RT0: base colour rgb (linear) | metallic
//   RT1: world normal xyz         | roughness
//   RT2: position relative to the camera xyz | ambient occlusion  ([BTDR:GBUF.RELPOS] keeps 16-bit float precise near the camera)
//   RT3: emissive rgb (linear)    | opacity (alpha front x alpha map; M6a transparency); [BTDR:GBUF.SSSID] (0.8.0) opaque
//        layer: 2 + subsurface profile k for objects in a Subsurface slot (the opaque layer never reads its opacity)
//   RT4: x IOR, y absorption distance, z thin walled (only the transparent front layer `tgbuffer` has a 5th buffer;
//        the opaque G-Buffer has 4 and drops it)
// [BTDR:GBUF.MATERIAL] every uniform below is bound by expression to the source material (ext/BTDRExt.py, _bind_material)
uniform sampler2D sBaseColor;
uniform sampler2D sMetallic;
uniform sampler2D sRoughness;
uniform sampler2D sAO;
uniform sampler2D sNormal;
uniform sampler2D sEmit;
uniform sampler2D sAlpha;
uniform vec4 uBase;    // rgb base colour
uniform vec4 uPBR;     // x metallic, y roughness, z AO strength, w normal map strength (0 = no normal map, < 0 = DirectX map)
uniform vec4 uEmit;    // rgb emissive colour, w 1 = an emissive map is assigned
uniform vec4 uChan;    // xyz channel source of the metallic, roughness, AO maps (PBR MAT menu index), w 1 = colours are sRGB
uniform vec4 uTrans;   // [BTDR:GBUF.TRANS] x opacity, y IOR, z absorption distance, w thin walled: 0 = solid, 1 + lift = thin
uniform vec4 uTrans2;  // x 1 = alpha map, y alpha-test threshold (< 0 = off), z roughness override (< 0 = material), w 1 = unlit
uniform vec4 uSSS;     // x subsurface profile (Subsurface slot index), < 0 = none ([BTDR:GBUF.SSSID])
// [BTDR:GBUF.UVSET] (0.8.3) per-map texture coordinates, following the PBR MAT's SOP Texture Coord and Texture
// Sampling Mode: code = UV set (0 = uv0, 1 = the extra set uUV1.w) + 2 for Screen Space.
uniform vec4 uUV0;     // base colour, metallic, roughness, AO
uniform vec4 uUV1;     // normal, emit, alpha; w index of the extra UV set (read in gbuffer.vert)
uniform vec4 uScr;     // xy 1 / render resolution (Screen Space sampling)

in Vertex {
    vec3 worldPos;
    vec3 worldNorm;
    vec2 texCoord;
    vec3 camPos;
    vec4 color;
    vec2 texCoord1;
} iVert;

layout(location = 0) out vec4 oAlbedo;
layout(location = 1) out vec4 oNormal;
layout(location = 2) out vec4 oPosition;
layout(location = 3) out vec4 oEmissive;
layout(location = 4) out vec4 oTrans;

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
vec2 uvOf(float code)
{
    int c = int(code + 0.5);
    if (c >= 2) return gl_FragCoord.xy * uScr.xy;     // Screen Space, like the PBR MAT: pixel / resolution
    return c == 1 ? iVert.texCoord1 : iVert.texCoord;
}
vec3 toLinear(vec3 c)
{
    return uChan.w > 0.5 ? pow(max(c, 0.0), vec3(2.2)) : c;
}

void main()
{
    TDCheckDiscard();
    vec3 base = toLinear(uBase.rgb) * toLinear(texture(sBaseColor, uvOf(uUV0.x)).rgb);
    float metal = uPBR.x * pick(texture(sMetallic, uvOf(uUV0.y)), uChan.x);
    float rough = uPBR.y * pick(texture(sRoughness, uvOf(uUV0.z)), uChan.y);
    float ao = mix(1.0, pick(texture(sAO, uvOf(uUV0.w)), uChan.z), clamp(uPBR.z, 0.0, 1.0));
    // [BTDR:GBUF.ALPHA] opacity; alpha test = cut-out (leaves, fences). An RGB alpha map reads its red channel.
    float alpha = uTrans.x;
    if (uTrans2.x > 0.5) { vec4 am = texture(sAlpha, uvOf(uUV1.z)); alpha *= am.a < 0.999 ? am.a : am.r; }
    if (uTrans2.y >= 0.0 && alpha <= uTrans2.y) discard;
    if (uTrans2.z >= 0.0) rough = uTrans2.z;
    vec3 emit = toLinear(uEmit.rgb);
    if (uEmit.w > 0.5) emit *= toLinear(texture(sEmit, uvOf(uUV1.y)).rgb);

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
        vec2 uvn = uvOf(uUV1.x);
        vec2 du1 = dFdx(uvn), du2 = dFdy(uvn);
        vec3 dp2p = cross(dp2, n), dp1p = cross(n, dp1);
        vec3 T = dp2p * du1.x + dp1p * du2.x;
        vec3 B = dp2p * du1.y + dp1p * du2.y;
        float inv = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-20));
        vec3 tn = texture(sNormal, uvn).xyz * 2.0 - 1.0;
        if (uPBR.w < 0.0) tn.y = -tn.y;         // [BTDR:GBUF.NCONV] DirectX (Y-) normal map
        tn.xy *= abs(uPBR.w);
        n = normalize(mat3(T * inv, B * inv, n) * tn);
    }
    // [BTDR:GBUF.INSTCOLOR] the instance colour tints base colour and emission (particles, per-instance glow)
    base *= max(iVert.color.rgb, 0.0);
    emit *= max(iVert.color.rgb, 0.0);
    // [BTDR:GBUF.UNLIT] Constant MAT: the colour goes out as emission. Base 0 + metallic 1 gives no diffuse and F0 = 0,
    // roughness 1 and AO 0 switch off reflections and ambient: no lighting term is left, without a flag channel.
    if (uTrans2.w > 0.5) { emit = base; base = vec3(0.0); metal = 1.0; rough = 1.0; ao = 0.0; }
    oAlbedo = vec4(base, clamp(metal, 0.0, 1.0));
    oNormal = vec4(n, clamp(rough, 0.04, 1.0));
    oPosition = vec4(iVert.worldPos - iVert.camPos, ao);
    oEmissive = vec4(emit, uSSS.x >= 0.0 ? 2.0 + uSSS.x : clamp(alpha, 0.0, 1.0));
    oTrans = vec4(uTrans.y, uTrans.z, uTrans.w > 0.5 ? 1.0 : 0.0, max(uTrans.w - 1.0, 0.0));   // w: thin transmission lift
}
