// [BTDR:FILE.REFRACT] refract.frag — M6a transparency: front transparent layer + screen-space refraction
// ([BTDR:REFR.*], design in docs/M6_TRANSPARENCY.md §3). Runs after composite, before fog / TAA.
// The opaque image (composite) has no transparent objects in it, so the refraction never samples the glass itself.
// 2D inputs: 0 opaque HDR image (composite, mipmapped: rough glass reads a blurrier level),
//            1 opaque camera-relative position (gbuf2), 2 opaque normal | roughness (gbuf1),
//            3..7 transparent front layer (tgbuffer): 3 base | metal, 4 normal | roughness, 5 camera-relative position,
//            6 emissive | opacity, 7 x IOR, y absorption distance, z thin walled, w thin transmission lift (0.8.1)
//            8 back faces of the transparent objects (tback): camera-relative position, 9 their normals,
//            10 shadow map (shadow_src), 11 sharp environment,
//            12 ray-traced transmission (rtr_src, M6c: radiance | valid, reduced resolution; [BTDR:REFR.RT])
//            13 (0.8.4) transparent layer RT5: absorption colour | refraction scale ([BTDR:GBUF.TRANS2])
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
    float absd = max(UM(t4.y), 1e-6);          // [BTDR:UNI.UNIT] absorption distance is in metres
    bool thin = t4.z > 0.5;
    float rough = clamp(tn.w, 0.02, 1.0);
    vec4 t5 = fetchAt(sTD2DInputs[13], uv);
    vec3 absorbC = clamp(t5.rgb, 0.0, 1.0);          // [BTDR:REFR.ABSORBCOLOR] (0.8.4, G5)
    float rscale = max(t5.a, 0.0);                    // [BTDR:REFR.SCALE] (0.8.4, G3) 1 = physical

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
        // [BTDR:REFR.SCALE] the bend is scaled around the straight ray (0 = no refraction, > 1 = stronger than glass)
        T1 = normalize(I + (T1 - I) * rscale);
        vec3 Pb = P + T1 * thick;
        vec2 ub = curUV(Pb);
        vec3 Nb = normalize(bn.xyz);
        exitP = Pb;
        if (inScreen(ub)) {
            vec4 bq = fetchAt(sTD2DInputs[8], ub);
            if (isGeoRel(bq)) {
                float tq = dot(bq.xyz + uCamPos.xyz - P, T1);
                if (tq > 0.0) {
                    exitP = P + T1 * min(tq, thick * 3.0 + UM(0.01));
                    Nb = normalize(fetchAt(sTD2DInputs[9], ub).xyz);
                }
            }
        }
        if (dot(Nb, T1) > 0.0) Nb = -Nb;
        vec3 T2 = refract(T1, Nb, ior);
        // [BTDR:REFR.RIMBLEND] (0.8.4) near the critical angle (total internal reflection from cos = sqrt(1 - 1/IOR^2),
        // 0.745 for glass) the exit direction fades to the view direction over 0.15 instead of switching: a solid
        // ball showed a sharp circle where the switch happened ("a ball inside the ball"). A real ball lens has a
        // reflective / dark rim there; this keeps it soft without tracing the internal bounce.
        float ex = -dot(T1, Nb);
        float cc = sqrt(max(1.0 - 1.0 / (ior * ior), 0.0));
        float wE = dot(T2, T2) > 1e-6 ? smoothstep(cc, min(cc + 0.15, 1.0), ex) : 0.0;
        T = wE > 0.0 ? normalize(mix(I, normalize(T2), wE)) : I;
        T = normalize(I + (T - I) * rscale);
    }

    // [BTDR:REFR.SAMPLE] march the transmitted ray against the opaque depth (exponential steps, ~2 cm .. 20 m) and read
    // the opaque image where it passes behind a surface; rougher glass and longer paths read a blurrier mip level.
    // Off-screen or behind the camera: the environment in that direction.
    vec2 ruv = vec2(-1.0);
    float dist = UM(0.02);
    bool found = false;
    for (int k = 0; k < 16; k++) {
        vec3 q = exitP + T * dist;
        if (viewDepth(q) < UM(1e-3)) break;
        vec2 u = curUV(q);
        if (!inScreen(u)) break;
        ruv = u;
        vec4 oq = fetchAt(sTD2DInputs[1], u);
        if (!isGeoRel(oq) || viewDepth(q) >= dot(oq.xyz, uCamFwd.xyz)) { found = true; break; }
        dist *= 1.6;
    }
    float maxLod = log2(float(max(textureSize(sTD2DInputs[0], 0).x, 1)));
    // [BTDR:REFR.DIFFUSE] (0.8.1) a rough thin sheet is a diffuser (frosted film, paper, skin): what touches it stays
    // sharp, the blur grows with the distance from the sheet to the surface behind it (width = (distance + 1 cm) x
    // roughness^2 x 2, measured in pixels at that surface). Before 0.8.1 thin sheets blurred by roughness only, the
    // same near and far. Solid glass keeps the roughness + path-length choice.
    float lod;
    if (thin) {
        float dBehind = dist;
        if (inScreen(ruv)) { vec4 oqd = fetchAt(sTD2DInputs[1], ruv); if (isGeoRel(oqd)) dBehind = length(oqd.xyz + uCamPos.xyz - exitP); }
        vec3 fwd = uCamFwd.xyz;
        vec3 side = normalize(abs(fwd.y) < 0.9 ? cross(fwd, vec3(0.0, 1.0, 0.0)) : cross(fwd, vec3(1.0, 0.0, 0.0)));
        float blurW = (dBehind + UM(0.01)) * rough * rough * 2.0;
        vec3 qb = exitP + T * dBehind;
        float px = length((curUV(qb + side * blurW) - curUV(qb)) * vec2(textureSize(sTD2DInputs[0], 0)));
        lod = clamp(log2(max(px, 1.0)), 0.0, maxLod - 2.0);
    } else {
        lod = clamp(rough * rough * 9.0 + rough * log2(1.0 + dist * 4.0), 0.0, maxLod - 2.0);
    }
    vec3 envT = envRadiance(T, rough);
    vec3 trans = envT;
    if (found || inScreen(ruv)) {
        // [BTDR:REFR.SMOOTHBLUR] (0.8.1) frosted transmission: a rotated 12-tap disc one mip level finer instead of one
        // bilinear tap of a box-filtered mip (which shows as blocks). The rotation is interleaved gradient noise
        // (Jimenez 2014) that changes every frame, so TAA averages it out; a per-pixel hash fixed in time (the first
        // version, in a commission) left a faint static diagonal pattern.
        vec3 s = vec3(0.0);
        if (lod < 0.75) s = textureLod(sTD2DInputs[0], clamp(ruv, 0.0, 1.0), lod).rgb;
        else {
            vec2 tx = exp2(lod) / vec2(textureSize(sTD2DInputs[0], 0));
            vec2 fp = gl_FragCoord.xy + 5.588238 * mod(uFrame.x, 64.0);
            float ang = fract(52.9829189 * fract(dot(fp, vec2(0.06711056, 0.00583715)))) * 6.2831853;
            mat2 rot = mat2(cos(ang), sin(ang), -sin(ang), cos(ang));
            const vec2 K[12] = vec2[12](vec2(-0.326,-0.406), vec2(-0.840,-0.074), vec2(-0.696,0.457), vec2(-0.203,0.621),
                                        vec2(0.962,-0.195), vec2(0.473,-0.480), vec2(0.519,0.767), vec2(0.185,-0.893),
                                        vec2(0.507,0.064), vec2(0.896,0.412), vec2(-0.322,-0.933), vec2(-0.792,-0.598));
            // taps that leave the frame would read black (the darker band along the edge): clamp them inside
            vec2 lim = 0.5 * exp2(max(lod - 1.0, 0.0)) / vec2(textureSize(sTD2DInputs[0], 0));
            for (int k = 0; k < 12; k++) s += textureLod(sTD2DInputs[0], clamp(ruv + rot * K[k] * tx, lim, 1.0 - lim), max(lod - 1.0, 0.0)).rgb;
            s /= 12.0;
        }
        vec2 e = min(ruv, 1.0 - ruv);
        // [BTDR:REFR.EDGE] (0.8.1) only the outermost pixels fade to the environment: the old 5 % band showed as a
        // darker frame around frosted / refractive surfaces that fill the picture
        float edge = clamp(min(e.x, e.y) * 400.0, 0.0, 1.0);
        trans = mix(envT, s, edge);
    }

    // [BTDR:REFR.ABSORB] Beer-Lambert: the base colour is the transmittance after `absorption distance` of material
    // [BTDR:REFR.THINTINT] (0.8.1) a thin sheet transmits a lighter colour than its surface colour (light passes once
    // through a thin layer); the slot's Thin Transmission Lift mixes the tint toward white, 0 = the base colour as before
    vec3 tint = thin ? mix(absorbC, vec3(1.0), clamp(t4.w, 0.0, 1.0)) : exp(log(max(absorbC, vec3(1e-3))) * (thick / absd));
    vec3 transT = trans * tint;
    // [BTDR:REFR.RT] M6c (uRT4.w: 1 Hybrid, 2 Ray Traced): the traced transmission already contains the bending and the
    // absorption of every glass segment it crossed. Hybrid keeps the sharper screen-space result where it found the
    // background on screen and uses the traced one where it did not (off screen, behind other glass); Ray Traced uses
    // the traced result everywhere (glass behind glass, objects off screen; softer: reduced resolution, proxy meshes).
    if (uRT4.w > 0.5) {
        vec4 rt = texture(sTD2DInputs[12], uv);
        // the POP-to-TOP of a freshly built / reloaded rt_refr can hold garbage for its first frames (negative, NaN):
        // ignore anything that is not a finite, non-negative radiance
        bool ok = rt.a > 0.5 && !any(isnan(rt)) && !any(isinf(rt)) && all(greaterThanEqual(rt.rgb, vec3(0.0)));
        if (ok) {
            float ssw = 0.0;
            if (uRT4.w < 1.5 && (found || inScreen(ruv))) {
                vec2 e2 = min(ruv, 1.0 - ruv);
                ssw = found ? clamp(min(e2.x, e2.y) * 20.0, 0.0, 1.0) : 0.0;
            }
            transT = mix(rt.rgb, transT, ssw);
        }
    }

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

    vec3 col = (1.0 - Fenv) * ((1.0 - alpha) * transT + alpha * coat) + refl + spec + t3.rgb;
    oColor = vec4(max(col, 0.0), scene.a);
    oPos = vec4(tp.xyz, 1.0);
    oNrm = vec4(N, rough);
}
