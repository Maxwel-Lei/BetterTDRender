// [BTDR:FILE.ENV] env_studio.frag — procedural studio environment as an equirect map (cooks once)
// [BTDR:ENV.STUDIO] gradient + four softboxes (key, fill, rim, top)
out vec4 fragColor;
float softbox(vec3 d, vec3 c, float size, float blur)
{
    float a = acos(clamp(dot(d, normalize(c)), -1.0, 1.0));
    return 1.0 - smoothstep(size - 0.02, size + blur, a);
}
void main()
{
    float phi = (vUV.s - 0.5) * 2.0 * PI;
    float theta = (vUV.t - 0.5) * PI;
    vec3 d = vec3(sin(phi) * cos(theta), sin(theta), -cos(phi) * cos(theta));
    float t = d.y * 0.5 + 0.5;
    vec3 col = mix(vec3(0.035, 0.030, 0.028), vec3(0.20, 0.22, 0.26), smoothstep(0.45, 0.60, t));
    col += vec3(1.00, 0.96, 0.90) * 9.0 * softbox(d, vec3(0.55, 0.75, 0.50), 0.26, 0.03);   // key
    col += vec3(0.70, 0.82, 1.00) * 3.0 * softbox(d, vec3(-0.85, 0.35, 0.45), 0.34, 0.03);  // fill
    col += vec3(1.00, 0.80, 0.60) * 6.0 * softbox(d, vec3(-0.45, 0.40, -0.85), 0.20, 0.03); // rim
    col += vec3(1.00, 1.00, 1.00) * 4.0 * softbox(d, vec3(0.10, 1.00, -0.10), 0.23, 0.03);  // top
    fragColor = vec4(col, 1.0);
}
