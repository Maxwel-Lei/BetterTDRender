// [BTDR:FILE.ENV] env_lookup.glsl — shared environment lookup (included after common.glsl by build.py)
// needs: #define ENV_SHARP <sampler2D>   sharp equirect environment
//        #define ENV_ATLAS <sampler3D>   pre-filtered atlas from env_prefilter.frag
// [BTDR:ENV.LOOKUP]
vec2 envUV(vec3 d)
{
    float c = cos(uEnv.y), s = sin(uEnv.y);
    d = vec3(c * d.x - s * d.z, d.y, s * d.x + c * d.z);
    return vec2(atan(d.x, -d.z) / (2.0 * PI) + 0.5, asin(clamp(d.y, -1.0, 1.0)) / PI + 0.5);
}
// radiance for a reflection lobe of the given roughness
vec3 envRadiance(vec3 d, float rough)
{
    vec2 uv = envUV(d);
    float t = clamp(rough, 0.0, 1.0) * 5.0;           // atlas slices sit at roughness 0.2 .. 1.0
    vec3 c;
    if (t < 1.0) c = mix(textureLod(ENV_SHARP, uv, 0.0).rgb, textureLod(ENV_ATLAS, vec3(uv, 0.5 / 6.0), 0.0).rgb, t);
    else c = textureLod(ENV_ATLAS, vec3(uv, (t - 0.5) / 6.0), 0.0).rgb;
    return c * uEnv.x;
}
// irradiance / PI for a surface normal
vec3 envIrradiance(vec3 n)
{
    return textureLod(ENV_ATLAS, vec3(envUV(n), 5.5 / 6.0), 0.0).rgb * uEnv.x;
}
