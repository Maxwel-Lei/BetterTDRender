// [BTDR:FILE.AE] exposure.frag — eye adaptation, 1x1: r = log2 exposure, g = exposure, b = metered luminance
// inputs: 0 average of the metering pass (Analyze TOP, 1x1), 1 previous result (Feedback TOP)
// uAE: x on, y min EV, z max EV, w key (target mid grey); uAE2: x speed up, y speed down, z delta seconds, w reset
out vec4 fragColor;
void main()
{
    vec4 a = texelFetch(sTD2DInputs[0], ivec2(0), 0);
    float logL = clamp(a.r / max(a.g, 1e-6), uAE.y, uAE.z);       // metered log2 luminance, clamped to the EV range
    // [BTDR:AE.ADAPT] exponential adaptation, faster when the image gets brighter
    float target = log2(uAE.w) - logL;
    float prev = texelFetch(sTD2DInputs[1], ivec2(0), 0).r;
    float speed = target < prev ? uAE2.x : uAE2.y;
    float cur = uAE2.w > 0.5 ? target : prev + (target - prev) * (1.0 - exp(-uAE2.z * speed));
    if (uAE.x < 0.5) cur = 0.0;
    fragColor = vec4(cur, exp2(cur), exp2(logL), 1.0);
}
