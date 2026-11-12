// [BTDR:FILE.PROBELOOKUP] probe_lookup.glsl — irradiance from the probe grid (M4), shared by composite, debug, rt_refl
// needs: #define PROBE_SH0..PROBE_SH3 <sampler3D>  (SH0 = mean radiance | validity, SH1..3 = first moments r / g / b)
// uRT2.xyz grid minimum, uRT3.xyz probe spacing ([BTDR:UNI.RT]). Returns irradiance / PI, like envIrradiance().
// [BTDR:GI.PROBE_SAMPLE] trilinear over the 8 surrounding probes, weighted by validity (probes inside objects are
// invalid) and by side: (0.7.3) a probe behind the surface plane gets (almost) no weight. Until 0.7.3 it kept
// 0.2 of its weight, so probes behind a face (a plinth's front face, with the probes between plinth and a wall of
// neon strips) bled their light through: coloured streaks on surfaces that cannot see that light. The lookup
// point is pushed off the surface by a third of the probe spacing (normal bias, as in DDGI).
vec3 probeIrradiance(vec3 P, vec3 N)
{
    ivec3 dims = textureSize(PROBE_SH0, 0);
    vec3 sp = max(uRT3.xyz, vec3(1e-4));
    vec3 Pb = P + N * (0.3 * min(sp.x, min(sp.y, sp.z)));
    vec3 g = (Pb - uRT2.xyz) / sp;
    g = clamp(g, vec3(0.0), vec3(dims - 1) - 0.001);
    ivec3 b = ivec3(floor(g));
    vec3 f = g - vec3(b);
    vec3 sum = vec3(0.0);
    float ws = 0.0;
    for (int i = 0; i < 8; i++) {
        ivec3 o = ivec3(i & 1, (i >> 1) & 1, (i >> 2) & 1);
        ivec3 c = min(b + o, dims - 1);
        vec3 tw = mix(1.0 - f, f, vec3(o));
        vec4 s0 = texelFetch(PROBE_SH0, c, 0);
        vec3 pp = uRT2.xyz + vec3(c) * uRT3.xyz;
        vec3 dp = pp - P + vec3(0.0, 1e-5, 0.0);
        float wn = dot(normalize(dp), N);
        float side = smoothstep(-0.05, 0.15, wn);                 // behind the surface plane -> ~0
        float w = tw.x * tw.y * tw.z * s0.a * (side * (wn * 0.5 + 0.5) + 1e-3);
        vec3 E = s0.rgb + (2.0 / 3.0) * vec3(dot(texelFetch(PROBE_SH1, c, 0).xyz, N),
                                             dot(texelFetch(PROBE_SH2, c, 0).xyz, N),
                                             dot(texelFetch(PROBE_SH3, c, 0).xyz, N));
        sum += max(E, 0.0) * w;
        ws += w;
    }
    return ws > 1e-4 ? sum / ws : vec3(0.0);
}
