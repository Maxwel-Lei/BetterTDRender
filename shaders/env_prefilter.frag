// [BTDR:FILE.ENV] env_prefilter.frag — pre-filters the environment into a 3D texture (equirect x roughness)
// input 0: equirect environment (mip-mapped). Output slices:
//   0..4 : GGX pre-filtered radiance for roughness 0.2, 0.4, 0.6, 0.8, 1.0
//   5    : cosine-convolved irradiance / PI (multiply by diffuse colour directly)
// [BTDR:ENV.PREFILTER] cooks only when the environment source changes
out vec4 fragColor;
const int NS = 96;

vec3 dirFromUV(vec2 uv)
{
    float phi = (uv.x - 0.5) * 2.0 * PI;
    float theta = (uv.y - 0.5) * PI;
    return vec3(sin(phi) * cos(theta), sin(theta), -cos(phi) * cos(theta));
}
vec2 uvFromDir(vec3 d)
{
    return vec2(atan(d.x, -d.z) / (2.0 * PI) + 0.5, asin(clamp(d.y, -1.0, 1.0)) / PI + 0.5);
}
float radicalInverse(uint b)
{
    b = (b << 16u) | (b >> 16u);
    b = ((b & 0x55555555u) << 1u) | ((b & 0xAAAAAAAAu) >> 1u);
    b = ((b & 0x33333333u) << 2u) | ((b & 0xCCCCCCCCu) >> 2u);
    b = ((b & 0x0F0F0F0Fu) << 4u) | ((b & 0xF0F0F0F0u) >> 4u);
    b = ((b & 0x00FF00FFu) << 8u) | ((b & 0xFF00FF00u) >> 8u);
    return float(b) * 2.3283064365386963e-10;
}
void main()
{
    ivec3 sz = ivec3(uTDOutputInfo.res.zw, int(uTDOutputInfo.depth.y));
    int slice = clamp(int(vUV.z * float(sz.z)), 0, sz.z - 1);
    vec3 N = dirFromUV(vUV.st);
    vec3 up = abs(N.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 T = normalize(cross(up, N));
    vec3 B = cross(N, T);
    vec2 srcRes = uTD2DInfos[0].res.zw;
    float texelSolid = 4.0 * PI / (srcRes.x * srcRes.y * 0.6366);     // average solid angle of a source texel
    vec3 sum = vec3(0.0);
    float wsum = 0.0;
    if (slice == sz.z - 1) {
        for (int i = 0; i < NS; i++) {
            vec2 xi = vec2((float(i) + 0.5) / float(NS), radicalInverse(uint(i)));
            float r = sqrt(xi.x), ph = 2.0 * PI * xi.y;
            vec3 l = vec3(r * cos(ph), r * sin(ph), sqrt(1.0 - xi.x));       // cosine-weighted
            vec3 L = T * l.x + B * l.y + N * l.z;
            float pdf = max(l.z, 1e-4) / PI;
            float lod = 0.5 * log2(1.0 / (float(NS) * pdf) / texelSolid) + 1.5;
            sum += textureLod(sTD2DInputs[0], uvFromDir(L), max(lod, 0.0)).rgb;
            wsum += 1.0;
        }
    } else {
        float rough = float(slice + 1) / float(sz.z - 1);
        float a = rough * rough, a2 = a * a;
        for (int i = 0; i < NS; i++) {
            vec2 xi = vec2((float(i) + 0.5) / float(NS), radicalInverse(uint(i)));
            float ct = sqrt((1.0 - xi.x) / (1.0 + (a2 - 1.0) * xi.x));
            float st = sqrt(max(1.0 - ct * ct, 0.0)), ph = 2.0 * PI * xi.y;
            vec3 H = T * (st * cos(ph)) + B * (st * sin(ph)) + N * ct;
            vec3 L = 2.0 * dot(N, H) * H - N;
            float NoL = dot(N, L);
            if (NoL <= 0.0) continue;
            float d = (ct * a2 - ct) * ct + 1.0;
            float pdf = a2 / (PI * d * d) * 0.25;                            // D * NoH / (4 VoH), with V = N
            float lod = 0.5 * log2(1.0 / (float(NS) * pdf) / texelSolid) + 1.0;
            sum += textureLod(sTD2DInputs[0], uvFromDir(L), max(lod, 0.0)).rgb * NoL;
            wsum += NoL;
        }
    }
    fragColor = vec4(sum / max(wsum, 1e-4), 1.0);
}
