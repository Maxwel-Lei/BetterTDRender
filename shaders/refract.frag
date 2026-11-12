// [BTDR:FILE.REFRACT] refract.frag — M6a transparency: front transparent layer + screen-space refraction
// ([BTDR:REFR.*], design in docs/M6_TRANSPARENCY.md §3). Runs after composite, before fog / TAA.
// The opaque image (composite) has no transparent objects in it, so the refraction never samples the glass itself.
// 2D inputs: 0 opaque HDR image (composite, mipmapped: rough glass reads a blurrier level),
//            1 opaque camera-relative position (gbuf2), 2 opaque normal | roughness (gbuf1),
//            3..7 transparent front layer (tgbuffer): 3 base | metal, 4 normal | roughness, 5 camera-relative position,
//            6 emissive | opacity, 7 x IOR, y absorption distance, z thin walled, w unused
//            8 back faces of the transparent objects (tback): camera-relative position, 9 their normals,
//            10 shadow map (shadow_src), 11 sharp environment
// 3D inputs: 0 pre-filtered environment atlas
// outputs: 0 image, 1 combined camera-relative position (front layer where it is in front), 2 combined normal | roughness
//   (fog_apply, TAA, depth of field and motion blur read 1 / 2, so glass edges get the glass depth)
#define LC_BASE sTD2DInputs[3]
#define LC_NRM sTD2DInputs[4]
#define LC_POS sTD2DInputs[5]
#define LC_EMIT sTD2DInputs[6]
#define LC_SHADOW sTD2DInputs[10]
#define ENV_SHARP sTD2DInputs[11]
#define ENV_ATLAS sTD3DInputs[0]
#define POSBUF sTD2DInputs[1]
#define NRMBUF sTD2DInputs[2]
//#include env_lookup
//#include lighting_core
//#include ss_common
layout(location = 0) out vec4 oColor;
layout(location = 1) out vec4 oPos;
layout(location = 2) out vec4 oNrm;

vec4 fetchAt(sampler2D s, vec2 uv)
{
    ivec2 sz = textureSize(s, 0);
    return texelFetch(s, clamp(ivec2(uv * vec2(sz)), ivec2(0), sz - 1), 0);
}

void main()
{
    vec2 uv = vUV.st;
    vec4 scene = textureLod(sTD2DInputs[0], uv, 0.0);
    vec4 op = fetchAt(sTD2DInputs[1], uv);
    vec4 on = fetchAt(sTD2DInputs[2], uv);
    vec4 tn = fetchAt(sTD2DInputs[4], uv);
    vec4 tp = fetchAt(sTD2DInputs[5], uv);
    oColor = scene; oPos = op; oNrm = on;

    // [BTDR:REFR.LAYER] a transparent pixel exists and is in front of the opaque surface
    bool hasT = dot(tn.xyz, tn.xyz) > 0.25;
    float zo = isGeoRel(op) ? dot(op.xyz, uCamFwd.xyz) : 1e9;
    float zt = hasT ? dot(tp.xyz, uCamFwd.xyz) : 1e9;
    if (!hasT || zt > zo - 1e-4) return;

    vec4 t0 = fetchAt(sTD2DInputs[3], uv);
    vec4 t3 = fetchAt(sTD2DInputs[6], uv);
    vec4 t4 = fetchAt(sTD2DInputs[7], uv);
    vec3 base = clamp(t0.rgb, 0.0, 1.0);
    float alpha = clamp(t3.a, 0.0, 1.0);
    float ior = max(t4.x, 1.0001);
    float absd = max(t4.y, 1e-3);
    bool thin = t4.z > 0.5;
    float rough = clamp(tn.w, 0.02, 1.0);

    vec3 P = tp.xyz + uCamPos.xyz;
    vec3 V = normalize(-tp.xyz);
    vec3 N = normalize(tn.xyz);
    if (dot(N, V) < 0.0) N = -N;                      // looking at the inside of an open mesh
    float NoV = clamp(dot(N, V), 1e-4, 1.0);
    float f0 = (ior - 1.0) / (ior + 1.0);
    vec3 F0 = vec3(f0 * f0);
    vec3 Fenv = envBRDFApprox(F0, rough, NoV);        // reflected share (split-sum, same as the opaque path)

    // [BTDR:REFR.THICKNESS] nearest back face behind the front layer, cut by the opaque surface (glass in a table)
    vec4 bp = fetchAt(sTD2DInputs[8], uv);
    vec4 bn = fetchAt(sTD2DInputs[9], uv);
    float zb = isGeoRel(bp) ? dot(bp.xyz, uCamFwd.xyz) : 0.0;
    bool hasBack = isGeoRel(bp) && zb > zt + 1e-4;
    float cosv = max(dot(-V, uCamFwd.xyz), 0.05);
    float thick = hasBack ? (min(zb, zo) - zt) / cosv : 0.0;
    if (!hasBack) thin = true;                        // single-sided surface: a thin sheet

    // [BTDR:REFR.DIR] thin: the ray leaves parallel to itself (a window barely shifts the image);
    // solid: refract in at the front face, find the back face along the refracted ray (one refinement through the back
    // face buffer), refract out there (HDRP sphere / box model with a measured thickness). Grazing exits and total
    // internal reflection leave along the view direction instead (a slab's exit ray), which avoids black rims.
    vec3 I = -V;
    vec3 T = I, exitP = P;
    if (!thin) {
        vec3 T1 = refract(I, N, 1.0 / ior);
        if (dot(T1, T1) < 1e-6) T1 = I;
        vec3 Pb = P + T1 * thick;
        vec2 ub = curUV(Pb);
        vec3 Nb = normalize(bn.xyz);
        exitP = Pb;
        if (inScreen(ub)) {
            vec4 bq = fetchAt(sTD2DInputs[8], ub);
            if (isGeoRel(bq)) {
                float tq = dot(bq.xyz + uCamPos.xyz - P, T1);
                if (tq > 0.0) {
                    exitP = P + T1 * min(tq, thick * 3.0 + 0.01);
                    Nb = normalize(fetchAt(sTD2DInputs[9], ub).xyz);
                }
            }
        }
        if (dot(Nb, T1) > 0.0) Nb = -Nb;
        vec3 T2 = refract(T1, Nb, ior);
        T = (dot(T2, T2) > 1e-6 && -dot(T1, Nb) > 0.3) ? normalize(T2) : I;
    }

    // [BTDR:REFR.SAMPLE] march the transmitted ray against the opaque depth (exponential steps, ~2 cm .. 20 m) and read
    // the opaque image where it passes behind a surface; rougher glass and longer paths read a blurrier mip level.
    // Off-screen or behind the camera: the environment in that direction.
    vec2 ruv = vec2(-1.0);
    float dist = 0.02;
    bool found = false;
    for (int k = 0; k < 16; k++) {
        vec3 q = exitP + T * dist;
        if (viewDepth(q) < 1e-3) break;
        vec2 u = curUV(q);
        if (!inScreen(u)) break;
        ruv = u;
        vec4 oq = fetchAt(sTD2DInputs[1], u);
        if (!isGeoRel(oq) || viewDepth(q) >= dot(oq.xyz, uCamFwd.xyz)) { found = true; break; }
        dist *= 1.6;
    }
    float maxLod = log2(float(max(textureSize(sTD2DInputs[0], 0).x, 1)));
    float lod = clamp(rough * rough * 9.0 + (thin ? 0.0 : rough * log2(1.0 + dist * 4.0)), 0.0, maxLod - 2.0);
    vec3 envT = envRadiance(T, rough);
    vec3 trans = envT;
    if (found || inScreen(ruv)) {
        vec3 s = textureLod(sTD2DInputs[0], ruv, lod).rgb;
        vec2 e = min(ruv, 1.0 - ruv);
        float edge = clamp(min(e.x, e.y) * 20.0, 0.0, 1.0);    // fade to the environment near the frame edge
        trans = mix(envT, s, edge);
    }

    // [BTDR:REFR.ABSORB] Beer-Lambert: the base colour is the transmittance after `absorption distance` of material
    vec3 tint = thin ? base : exp(log(max(base, vec3(1e-3))) * (thick / absd));

    // [BTDR:REFR.SURFACE] surface terms: environment reflection, sun highlight (shadowed), opacity as a diffuse coat
    vec3 L = normalize(uSunDir.xyz);
    float NoL = clamp(dot(N, L), 0.0, 1.0);
    float sh = (NoL > 0.0 && uSunDir.w > 0.0) ? sunShadow(P, N, NoL) : 0.0;
    vec3 H = normalize(V + L);
    float a = rough * rough, a2 = a * a;
    vec3 sun = uSunColor.rgb * uSunDir.w * NoL * sh;
    vec3 spec = D_GGX(a2, clamp(dot(N, H), 0.0, 1.0)) * V_SmithJointApprox(a, NoV, NoL) * F_Schlick(F0, clamp(dot(V, H), 0.0, 1.0)) * sun;
    vec3 R = normalize(mix(reflect(-V, N), N, a * a));
    vec3 refl = envRadiance(R, rough) * Fenv;
    vec3 coat = base * (envIrradiance(N) + sun / PI);

    vec3 col = (1.0 - Fenv) * ((1.0 - alpha) * trans * tint + alpha * coat) + refl + spec + t3.rgb;
    oColor = vec4(max(col, 0.0), scene.a);
    oPos = vec4(tp.xyz, 1.0);
    oNrm = vec4(N, rough);
}
