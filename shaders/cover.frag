// [BTDR:FILE.COVER] cover.frag — the renderBTDR cover / loading screen ([BTDR:BUILD.COVER]).
// Shown on output 1 until a camera is found and the pipeline has warmed up. The TD学长 logo is drawn as a
// signed distance field, so the tox carries no image file and the logo is sharp at any resolution.
// The logo is a slanted shape: in sheared space u = x + K*(y - 640) every edge is axis-aligned, so it is a
// smooth union of three rounded boxes minus a rounded hole (units: the 1280 x 1280 artwork, y down).
// uCover.x = time (s), .y = mode (0 = loading: a light band sweeps through the logo, 1 = waiting for a camera)
uniform vec4 uCover;
out vec4 fragColor;

const vec3 LIME = vec3(0.776, 1.0, 0.051);     // #C6FF0D
const vec3 INK = vec3(0.04);
const float K = 0.28;                           // slant of the artwork (dx / dy)

float sdBox(vec2 p, vec2 lo, vec2 hi, float r)
{
    vec2 c = 0.5 * (lo + hi), h = 0.5 * (hi - lo) - r;
    vec2 q = abs(p - c) - h;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
float smin(float a, float b, float k)
{
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}
float logo(vec2 c)
{
    vec2 p = vec2(c.x + K * (c.y - 640.0), c.y);
    float a = sdBox(p, vec2(235.0, 290.0), vec2(835.0, 490.0), 12.0);     // top bar
    float b = sdBox(p, vec2(500.0, 390.0), vec2(932.0, 890.0), 12.0);     // right column
    float s = sdBox(p, vec2(433.0, 490.0), vec2(830.0, 990.0), 12.0);     // left stem and foot
    float d = smin(smin(a, s, 40.0), b, 40.0);                            // filleted inner corners
    float hole = sdBox(p, vec2(533.0, 490.0), vec2(832.0, 790.0), 45.0);
    return max(d, -hole);
}
float dash(vec2 c, float x0)        // one slanted loading dash
{
    vec2 p = vec2(c.x + K * (c.y - 640.0), c.y);
    return sdBox(p, vec2(x0, 1080.0), vec2(x0 + 70.0, 1100.0), 6.0);
}
void main()
{
    vec2 res = uTDOutputInfo.res.zw;
    float t = uCover.x;
    // fit the artwork's logo (700 units tall) into ~46% of the output height, a little above centre
    float s = res.y * 0.46 / 700.0;
    vec2 px = vUV.st * res;
    vec2 c = vec2(640.0 + (px.x - 0.5 * res.x) / s, 640.0 + ((1.0 - vUV.t) * res.y - res.y * 0.43) / s);
    float aa = 1.0 / s;
    float d = logo(c);
    vec3 col = LIME;
    float ink = 1.0 - smoothstep(-aa, aa, d);
    // loading: a lime band sweeps diagonally through the logo, then a pause
    float u = c.x + K * (c.y - 640.0);
    float ph = fract(t / 1.6);
    float band = (uCover.y < 0.5) ? smoothstep(60.0, 0.0, abs(u - mix(150.0, 1050.0, ph))) * 0.85 : 0.0;
    col = mix(col, mix(INK, LIME, band), ink);
    // three dashes under the logo, lit in turn
    for (int i = 0; i < 3; i++) {
        float x0 = 631.0 + 100.0 * float(i);
        float on = 0.5 + 0.5 * cos(6.2831853 * (t / (uCover.y < 0.5 ? 0.9 : 2.4) - float(i) / 3.0));
        float m = 1.0 - smoothstep(-aa, aa, dash(c, x0));
        col = mix(col, INK, m * mix(0.18, 1.0, on));
    }
    fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
