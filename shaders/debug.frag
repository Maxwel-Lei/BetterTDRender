// [BTDR:FILE.DEBUG] debug.frag — Debug View of the Render page
// 2D inputs: 0 base|metal, 1 normal|rough, 2 world pos|ao, 3 emissive, 4 direct light, 5 env diffuse, 6 env specular,
//            7 SSGI | AO (accumulated), 8 SSR | confidence (accumulated), 9 env BRDF | weight,
//            10 traced reflection ratio | valid; 3D inputs 0..3 probe grid (M4)
// Views 11-13 are computed here, not in composite: composite feeds TAA, whose history is the "last frame" the
// screen-space passes read their bounce / reflection radiance from, so a debug image there would feed back.
// [BTDR:DEBUG.VIEWS] index = position in the Debug View menu (0 = final image, handled by a Switch TOP)
out vec4 fragColor;
#define PROBE_SH0 sTD3DInputs[0]
#define PROBE_SH1 sTD3DInputs[1]
#define PROBE_SH2 sTD3DInputs[2]
#define PROBE_SH3 sTD3DInputs[3]
//#include probe_lookup
void main()
{
    vec4 g0 = texture(sTD2DInputs[0], vUV.st);
    vec4 g1 = texture(sTD2DInputs[1], vUV.st);
    vec4 g2 = texture(sTD2DInputs[2], vUV.st);
    int v = int(uView.x + 0.5);
    bool hit = dot(g1.xyz, g1.xyz) > 0.25;
    vec3 c = vec3(0.0);
    if (v == 1) c = pow(g0.rgb, vec3(1.0 / 2.2));
    else if (v == 2) c = hit ? normalize(g1.xyz) * 0.5 + 0.5 : vec3(0.0);
    else if (v == 3) c = vec3(hit ? g1.a : 0.0);
    else if (v == 4) c = vec3(g0.a);
    else if (v == 5) c = vec3(hit ? g2.a : 0.0);
    else if (v == 6) c = pow(texture(sTD2DInputs[3], vUV.st).rgb, vec3(1.0 / 2.2));
    else if (v == 7) c = hit ? vec3(dot(g2.xyz, uCamFwd.xyz) / uClip.y) : vec3(1.0);
    else if (v == 8) c = pow(clamp(texture(sTD2DInputs[4], vUV.st).rgb * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2));
    else if (v == 9) c = pow(clamp(texture(sTD2DInputs[5], vUV.st).rgb * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2));
    else if (v == 10) c = pow(clamp(texture(sTD2DInputs[6], vUV.st).rgb * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2));
    else if (v >= 11) {
        // [BTDR:DEBUG.SS] same terms as composite.frag ([BTDR:COMP.AO], [BTDR:COMP.SPEC])
        vec4 gi = texture(sTD2DInputs[7], vUV.st);
        vec4 ssr = texture(sTD2DInputs[8], vUV.st);
        vec4 brdf = texture(sTD2DInputs[9], vUV.st);
        float w = brdf.a;
        if (v == 11) c = vec3(hit ? mix(1.0, gi.a, uSS.x) : 1.0);
        else if (v == 12) c = pow(clamp(g0.rgb * (1.0 - g0.a) * gi.rgb * w * uSS.y * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2));
        else if (v == 13) c = pow(clamp(ssr.rgb * brdf.rgb * w * clamp(ssr.a * uSS.z, 0.0, 1.0) * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2));
        // [BTDR:DEBUG.RT] M4: probe irradiance on a mid-grey surface; traced reflection ratio (grey = 1, the environment)
        else if (v == 14) c = hit ? pow(clamp(0.18 * probeIrradiance(g2.xyz + uCamPos.xyz, normalize(g1.xyz)) * uGrade.x, 0.0, 1.0), vec3(1.0 / 2.2)) : vec3(0.0);
        else if (v == 15) { vec4 rt = texture(sTD2DInputs[10], vUV.st); c = hit ? pow(clamp(mix(vec3(1.0), rt.rgb, rt.a) * 0.5, 0.0, 1.0), vec3(1.0 / 2.2)) : vec3(0.0); }
    }
    fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
