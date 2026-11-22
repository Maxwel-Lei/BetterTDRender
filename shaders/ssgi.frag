// [BTDR:FILE.SSGI] ssgi.frag — screen-space AO + indirect diffuse in one horizon sweep (ported from ue5r)
// GTAO-style slices: along each slice side the horizon only rises; whenever a sample raises it, the newly
// covered (cosine-weighted) part of the hemisphere is blocked by that sample, so it is both occlusion and a
// bounce of that surface's radiance, taken from last frame's image.
// inputs: 0 G-Buffer normal | rough, 1 camera-relative position | ao, 2 previous frame HDR (taa_hist)
// output: rgb indirect diffuse radiance (before albedo), a visible fraction (AO)
// uGI: x radius (scene units), y steps, z directions
#define NRMBUF sTD2DInputs[0]
#define POSBUF sTD2DInputs[1]
//#include ss_common
out vec4 fragColor;
void main()
{
    vec4 p0 = fetchRel(vUV.st);
    if (!isGeoRel(p0)) { fragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }
    vec3 P = p0.xyz + uCamPos.xyz;
    vec3 N = normalize(fetchNrm(vUV.st).xyz);
    vec2 res = vec2(textureSize(POSBUF, 0));
    float depth = max(dot(p0.xyz, uCamFwd.xyz), 1e-3);
    float radPx = min(uGI.x * pxPerUnit(depth, res.x), 0.25 * res.x);   // world radius -> pixels ([BTDR:CAM.ORTHO])
    int steps = int(uGI.y);
    int dirs = int(uGI.z);
    float n1 = ign(gl_FragCoord.xy, uFrame.x);
    float n2 = ign(gl_FragCoord.yx + 17.0, uFrame.x);
    vec3 gi = vec3(0.0);
    float occl = 0.0;
    for (int d = 0; d < dirs; d++) {
        float ang = (float(d) + n1) / float(dirs) * PI;
        vec2 sd = vec2(cos(ang), sin(ang));             // a direction in pixels (divided by res below)
        for (int side = 0; side < 2; side++) {
            vec2 dir = side == 0 ? sd : -sd;
            // [BTDR:SSGI.HORIZON]
            float hs = 0.0;                              // sin^2 of the horizon elevation (blocked measure)
            for (int i = 0; i < steps; i++) {
                float t = (float(i) + n2) / float(steps);
                t = t * t;
                vec2 uv = vUV.st + dir * (1.0 + t * radPx) / res;
                if (!inScreen(uv)) break;
                vec4 sp = fetchRel(uv);
                if (!isGeoRel(sp)) continue;
                vec3 D = sp.xyz - p0.xyz;
                float dist = length(D);
                // [BTDR:SSGI.BIAS] the 16-bit camera-relative position is quantised (about 0.05 % of the
                // distance): ignore samples closer than that and lift the tangent plane a little, otherwise flat
                // surfaces seen at a grazing angle occlude themselves in contour lines
                if (dist < 2e-3 * depth) continue;
                float s = dot(N, D / dist) - 0.08;       // sine of the elevation above the (biased) tangent plane
                if (s <= 0.0) continue;
                s /= 0.92;
                float s2 = s * s * (1.0 - smoothstep(0.5 * uGI.x, uGI.x, dist));
                if (s2 > hs) {
                    // [BTDR:SS.HISTRESET] no last frame yet (history reset): the Feedback TOP may hold uninitialised memory
                    vec3 L = uFrame.z > 0.5 ? vec3(0.0) : min(texture(sTD2DInputs[2], prevUV(sp.xyz + uCamPos.xyz)).rgb, vec3(64.0));
                    if (any(isnan(L)) || any(isinf(L))) L = vec3(0.0);
                    gi += min(L, vec3(16.0)) * (s2 - hs);
                    hs = s2;
                }
            }
            occl += hs;
        }
    }
    float norm = 1.0 / float(2 * dirs);
    fragColor = vec4(gi * norm, clamp(1.0 - occl * norm, 0.0, 1.0));
}
