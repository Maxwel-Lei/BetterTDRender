# Score for the before / after comparison (51.5 s), same palette as the v0.7.3 intro (music3.py): a D drone with soft
# saturation, saturated pads, bells, sub thumps, filtered-noise sweeps, a long dark reverb.
# Picture: 0 title | shots start at 2.5 + 7.5 k (k = 0..5), 8 s each (0.5 s crossfades):
#   +0..2 native | +2..3 wipe to the middle | +3..5 split | +5..6 wipe on | +6..8 BTDR | 47.5 end card | 51.5
# "Before / after" is audible: the bed is low-passed (dull) while the native picture shows and opens with the wipe.
import numpy as np, wave
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000; T = 51.5; N = int(SR * T)
t = np.arange(N) / SR
rng = np.random.default_rng(23)
bed = np.zeros((N, 2))      # filtered by the before/after brightness
fx = np.zeros((N, 2))       # hits and sweeps, never filtered
SHOTS = [2.5 + 7.5 * k for k in range(6)]
END = 47.5


def note(m): return 440.0 * 2 ** ((m - 69) / 12.0)
def sat(x, k): return np.tanh(k * x) / np.tanh(k)
def lowpass(x, fc): return sosfilt(butter(2, fc, 'lowpass', fs=SR, output='sos'), x)
def ramp(a, b): return np.clip((t - a) / (b - a), 0, 1)
def easeu(a, b):
    u = ramp(a, b); return u * u * (3 - 2 * u)
def env(x0, x1, a, r):
    e = np.clip((t - x0) / max(a, 1e-3), 0, 1) * np.clip((x1 - t) / max(r, 1e-3), 0, 1)
    return e * e * (3 - 2 * e)
def smooth(points):
    tp, vp = zip(*points); return np.interp(t, tp, vp)
def add(buf, x, gain=1.0, pan=0.0):
    buf[:, 0] += x * gain * (1 - pan); buf[:, 1] += x * gain * (1 + pan)


def bell(buf, at, m, g=1.0, pan=0.0, dec=2.2):
    s = int(at * SR); n = min(N - s, int(4.0 * SR))
    if n <= 0: return
    tt = np.arange(n) / SR; f = note(m)
    x = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.01 * f * tt) * np.exp(-tt * 5)
         + 0.12 * np.sin(2 * np.pi * 3.98 * f * tt) * np.exp(-tt * 9)) * np.exp(-tt / dec)
    x = sat(x * np.clip(tt / 0.004, 0, 1) * 0.8, 1.3)
    buf[s:s + n, 0] += x * g * 0.11 * (1 - pan); buf[s:s + n, 1] += x * g * 0.11 * (1 + pan)


duck = np.ones(N)
def thump(at, g=1.0, f0=46):
    s = int(at * SR); n = min(N - s, int(0.6 * SR)); tt = np.arange(n) / SR
    f = f0 + 30 * np.exp(-tt * 25)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7) * np.clip(tt / 0.006, 0, 1)
    fx[s:s + n, 0] += x * g * 0.5; fx[s:s + n, 1] += x * g * 0.5
    duck[s:s + n] = np.minimum(duck[s:s + n], 1 - 0.35 * g * np.exp(-tt * 6))


def noise_sweep(t0, t1, f0, f1, g, pan=0.0):
    s, e = int(t0 * SR), int(t1 * SR); n = e - s
    x = rng.standard_normal(n); y = np.zeros(n); blk = 1024
    for k in range(0, n, blk):
        u = k / n; fc = f0 * (f1 / f0) ** u
        y[k:k + blk] = sosfilt(butter(2, [fc * 0.7, min(fc * 1.4, SR / 2 - 100)], 'bandpass', fs=SR, output='sos'), x[k:k + blk])
    u = np.linspace(0, 1, n); a = u ** 2 * np.clip(u / 0.02, 0, 1) * np.clip((1 - u) / 0.04, 0, 1)
    fx[s:e, 0] += y * a * g * (1 - pan); fx[s:e, 1] += y * a * g * (1 + pan)


def grains(buf, t0, t1, n, g, lo=79, hi=96, dec=0.12):
    for u in rng.uniform(0, 1, n) ** 2.5:
        at = t0 + (t1 - t0) * u; s = int(at * SR); m = min(N - s, int(0.4 * SR))
        tt = np.arange(m) / SR; f = note(rng.uniform(lo, hi))
        x = np.sin(2 * np.pi * f * tt) * np.exp(-tt / dec) * np.clip(tt / 0.002, 0, 1); p = rng.uniform(-0.8, 0.8)
        buf[s:s + m, 0] += x * g * (1 - p); buf[s:s + m, 1] += x * g * (1 + p)


def tone(buf, f, a, gain, pan=0.0):
    add(buf, np.sin(2 * np.pi * np.cumsum(f) / SR) * a, gain, pan)


# ---------------------------------------------------------------- before/after brightness (follows the wipe)
bright = np.zeros(N)
for s0 in SHOTS:
    b = np.where(t < s0 + 2, 0.0, np.where(t < s0 + 3, 0.5 * easeu(s0 + 2, s0 + 3),
        np.where(t < s0 + 5, 0.5, np.where(t < s0 + 6, 0.5 + 0.5 * easeu(s0 + 5, s0 + 6), 1.0))))
    bright = np.where((t >= s0) & (t < s0 + 7.75), b, bright)
bright = np.where(t < SHOTS[0], 0.3, bright)
bright = np.where(t >= END, 1.0, bright)
bright = lowpass(bright, 3.0)

# ---------------------------------------------------------------- drone (D), drive breathes with the picture
drive = smooth([(0, 1.1), (2.5, 1.4)] + [(s0 + 6, 2.2 + 0.15 * k) for k, s0 in enumerate(SHOTS)] + [(END, 2.6), (51.5, 1.2)])
lfo = 0.5 + 0.5 * np.sin(2 * np.pi * t / 7.5)
d1 = np.sin(2 * np.pi * note(38) * t) + np.sin(2 * np.pi * note(38) * 1.004 * t + 1.3)
d2 = 0.6 * np.sin(2 * np.pi * note(45) * t + 0.4) + 0.35 * np.sin(2 * np.pi * note(50) * 0.998 * t)
dr = lowpass(sat((d1 + d2) * 0.32, drive * (0.8 + 0.4 * lfo)), 1400)
add(bed, dr * smooth([(0, 0), (0.8, 0.5), (2.5, 0.65), (46, 0.9), (50, 0.6), (51.5, 0)]), 0.42)
hd = np.sin(2 * np.pi * note(74) * t) + 0.7 * np.sin(2 * np.pi * note(81) * 1.002 * t + 2.0)
hd = sat(hd * 0.5, 1.5) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 5.3))
add(bed, hd * env(2.5, 51.0, 3.0, 2.5), 0.04, 0.2); add(bed, hd * env(2.5, 51.0, 3.0, 2.5), 0.04, -0.2)

# ---------------------------------------------------------------- pads: Dm9 under each native part, the shot's chord on BTDR
chords = {'Dm9': [50, 57, 60, 64, 69], 'Bb': [46, 53, 57, 62, 69], 'F/A': [45, 53, 57, 60, 64],
          'Csus': [48, 55, 62, 64, 67], 'Gm9': [43, 50, 58, 62, 69], 'Bbmaj7': [46, 53, 57, 62, 65]}
def pad(a, b, c, g, att=1.0, pan=0.0):
    e = env(a - 0.1, b + 0.6, att, 0.9); sig = np.zeros(N)
    for j, m in enumerate(chords[c]):
        vib = 1 + 0.0015 * np.sin(2 * np.pi * (4.5 + j * 0.3) * t)
        sig += np.sin(2 * np.pi * note(m) * t * vib + j) / 5
    add(bed, sat(sig * 1.4, 1.8) * e, g, pan)
shot_ch = ['Bb', 'F/A', 'Csus', 'Gm9', 'Bbmaj7', 'Dm9']
for k, s0 in enumerate(SHOTS):
    pad(s0, s0 + 5.0, 'Dm9', 0.10, 1.0, 0.25 * (-1) ** k)
    pad(s0 + 5.0, s0 + 7.6, shot_ch[k], 0.17, 0.6, -0.25 * (-1) ** k)
pad(END, 51.0, 'Dm9', 0.22, 0.3)

# ---------------------------------------------------------------- title: a soft hit with the logo
thump(0.35, 0.45); bell(fx, 0.35, 62, 0.7, 0, 3.5); bell(fx, 0.35, 69, 0.5, 0.2, 3.5)
grains(fx, 0.4, 2.0, 35, 0.03, 84, 98, 0.25)
noise_sweep(1.9, 2.52, 300, 3000, 0.09)

# ---------------------------------------------------------------- every shot: cut, wipe whooshes, BTDR hit
seq = [62, 69, 72, 74, 72, 69, 65, 69]
for k, s0 in enumerate(SHOTS):
    thump(s0, 0.55)
    bell(fx, s0, 62 + (0, 5, 7, 3, 10, 0)[k], 0.45, 0.3 * (-1) ** k, 2.5)
    noise_sweep(s0 + 1.55, s0 + 2.6, 300, 2500, 0.08, -0.3)        # into the split
    noise_sweep(s0 + 4.6, s0 + 6.02, 300, 6000, 0.12, 0.3)          # into BTDR
    thump(s0 + 6.0, 1.0)
    top = (74, 77, 79, 74, 81, 74)[k]
    bell(fx, s0 + 6.0, top, 0.9, -0.25, 3.5); bell(fx, s0 + 6.0, top - 5, 0.6, 0.25, 3.5); bell(fx, s0 + 6.0, top - 12, 0.5, 0, 3.5)
    thump(s0 + 7.0, 0.35)

# per-shot colour (into the bed, so it is dull while the native side shows)
s0 = SHOTS[0]   # global illumination: light fills the room
gi = sum(np.sin(2 * np.pi * note(m) * t + m) for m in (69, 74, 76, 81)) / 4
add(bed, sat(gi, 1.5) * easeu(s0 + 2, s0 + 6) * env(s0, s0 + 7.8, 0.1, 0.4), 0.08)
s0 = SHOTS[1]   # light shafts: air
air = lowpass(rng.standard_normal(N), 2500) - lowpass(rng.standard_normal(N), 700)
add(bed, air * easeu(s0 + 1, s0 + 6) * env(s0, s0 + 7.8, 0.3, 0.5), 0.05)
grains(bed, s0 + 6.0, s0 + 7.6, 60, 0.02, 86, 100, 0.3)
s0 = SHOTS[2]   # auto exposure: a tone rises as the camera tilts up to the sky
u = easeu(s0, s0 + 8)
tone(bed, note(62) * 2 ** (u * 1.0), env(s0, s0 + 7.9, 0.5, 0.3), 0.05)
tone(bed, note(69) * 2 ** (u * 1.0), env(s0, s0 + 7.9, 0.5, 0.3) * u, 0.035)
s0 = SHOTS[3]   # tracking focus: a high sine glides down and softens (the background falls out of focus)
u = easeu(s0 + 5.0, s0 + 7.0)
tone(bed, note(86) * 2 ** (-u), env(s0 + 4.8, s0 + 7.9, 0.2, 0.3) * (1 - 0.5 * u), 0.035)
for at in np.arange(s0, s0 + 8, 0.5):
    bell(bed, at, seq[int((at - s0) * 2) % 8] + 12, 0.18, 0.6 * np.sin(at * 3.1), 0.35)
s0 = SHOTS[4]   # reflections: an arpeggio that is muffled until the reflections appear
for j, at in enumerate(np.arange(s0, s0 + 8, 0.25)):
    bell(bed, at, seq[j % 8] + (12 if (j // 8) % 2 else 0), 0.35 + 0.2 * (j % 4 == 0), 0.6 * np.sin(j * 1.7), 0.8)
s0 = SHOTS[5]   # refraction: reverse swell into a glass ting on the reveal
add(bed, np.sin(2 * np.pi * note(86) * t) * ramp(s0 + 5.0, s0 + 6.0) ** 3 * (t < s0 + 6.0), 0.05)
bell(fx, s0 + 6.0, 93, 0.6, 0.2, 1.2); bell(fx, s0 + 6.0, 86, 0.7, -0.2, 1.8)

# ---------------------------------------------------------------- end card
noise_sweep(END - 0.9, END + 0.02, 300, 5000, 0.12)
thump(END, 1.2, 40)
for m, g, p in ((50, 1.0, 0), (62, 0.9, -0.2), (69, 0.8, 0.2), (74, 0.6, -0.3), (81, 0.4, 0.3)):
    bell(fx, END, m, g, p, 5.0)

# ---------------------------------------------------------------- before / after filter on the bed
dull = np.stack([lowpass(bed[:, c], 550) for c in range(2)], 1) * 1.5
mid = np.stack([lowpass(bed[:, c], 2200) for c in range(2)], 1) * 1.15
b = bright[:, None]
bedf = np.where(b < 0.5, dull * (1 - 2 * b) + mid * (2 * b), mid * (2 - 2 * b) + bed * (2 * b - 1))
out = (bedf + fx) * duck[:, None]

# ---------------------------------------------------------------- space and master
ir_n = int(3.2 * SR); irt = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-irt / 1.0)[:, None]
ir = np.stack([lowpass(ir[:, 0], 6000), lowpass(ir[:, 1], 6000)], 1); ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(out[:, c], ir[:, c])[:N] for c in range(2)], 1)
mix = sat((out * 0.75 + wet * 0.55) * 1.1, 1.2)
fo = np.ones(N); fo[:int(0.3 * SR)] = np.linspace(0, 1, int(0.3 * SR))
s = int(49.6 * SR); fo[s:] = np.linspace(1, 0, N - s) ** 2
mix *= fo[:, None]
mix /= np.abs(mix).max() / 0.89
w = wave.open('music4.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix * 32767).astype('<i2').tobytes()); w.close()
print('ok rms', float(np.sqrt((mix ** 2).mean())))
