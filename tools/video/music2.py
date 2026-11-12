# BTDR intro v3 score: drone-based, soft-saturated sines, almost no drums. 120 bpm, bar = 2 s.
# Timeline (s): 0 open (native) | 3 BTDR reveal | 8.7 title | 12 parameters | 20 neon | 26 monolith |
# 32 particles (Chladni figure changes on every even second) | 40 gather into text | 46 materials |
# 51 montage | 56 end card | 60
import numpy as np, wave
from scipy.signal import lfilter, butter, sosfilt, fftconvolve

SR = 48000; T = 60.0; N = int(SR * T)
t = np.arange(N) / SR
rng = np.random.default_rng(11)
out = np.zeros((N, 2))


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def sat(x, k):
    # soft clipping: a sine through tanh gains mostly odd harmonics, gently
    return np.tanh(k * x) / np.tanh(k)


def env(x0, x1, a, r, n0=None):
    """0 before x0, attack a, hold, release r ending at x1 (all seconds) -> array over the whole timeline."""
    e = np.clip((t - x0) / max(a, 1e-3), 0, 1) * np.clip((x1 - t) / max(r, 1e-3), 0, 1)
    return e * e * (3 - 2 * e)


def smooth(points):
    """piecewise smooth automation from [(time, value), ...]"""
    tp, vp = zip(*points)
    v = np.interp(t, tp, vp)
    return lfilter([0.0005], [1, -0.9995], v) if False else v


def add(x, gain=1.0, pan=0.0):
    out[:, 0] += x * gain * (1 - pan)
    out[:, 1] += x * gain * (1 + pan)


def lowpass(x, fc):
    return sosfilt(butter(2, fc, 'lowpass', fs=SR, output='sos'), x)


# ---------------------------------------------------------------- drone
# D: two detuned low sines (slow beating) + a fifth, through a soft saturator whose drive breathes
drive = smooth([(0, 1.2), (3, 1.6), (12, 2.0), (26, 2.6), (32, 2.2), (40, 3.0), (46, 2.0), (56, 1.4), (60, 1.2)])
lfo = 0.5 + 0.5 * np.sin(2 * np.pi * t / 8.0)
d1 = np.sin(2 * np.pi * note(38) * t) + np.sin(2 * np.pi * note(38) * 1.004 * t + 1.3)
d2 = 0.6 * np.sin(2 * np.pi * note(45) * t + 0.4) + 0.35 * np.sin(2 * np.pi * note(50) * 0.998 * t)
dr = sat((d1 + d2) * 0.32, drive * (0.8 + 0.4 * lfo))
dr = lowpass(dr, 1400)
lvl = smooth([(0, 0.0), (0.6, 0.55), (3, 0.7), (12, 0.8), (40, 0.9), (56, 0.6), (60, 0.0)])
add(dr * lvl, 0.42)

# a high drone that opens with the reveal: an octave pair with very slow tremolo
hd = np.sin(2 * np.pi * note(74) * t) + 0.7 * np.sin(2 * np.pi * note(81) * 1.002 * t + 2.0)
hd = sat(hd * 0.5, 1.5) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 5.3))
add(hd * env(3.0, 59.0, 4.0, 3.0), 0.045, 0.2)
add(hd * env(3.0, 59.0, 4.0, 3.0), 0.045, -0.2)

# ---------------------------------------------------------------- chords (sine pads, slow swell)
# Dm9 | Bbmaj7 | Fmaj7/A | Csus2 ... 4 bars (8 s) each from the reveal on
chords = [[50, 57, 60, 64, 69], [46, 53, 57, 62, 69], [45, 53, 57, 60, 64], [48, 55, 62, 64, 67]]
for i, st in enumerate(np.arange(4.0, 56.0, 8.0)):
    ch = chords[i % 4]
    e = env(st - 0.5, st + 8.6, 2.5, 2.5)
    sig = np.zeros(N)
    for j, m in enumerate(ch):
        f = note(m)
        vib = 1 + 0.0015 * np.sin(2 * np.pi * (4.5 + j * 0.3) * t)
        sig += np.sin(2 * np.pi * f * t * vib + j) / len(ch)
    sig = sat(sig * 1.4, 1.8) * e
    add(sig, 0.16, 0.25 * (-1) ** i)

# ---------------------------------------------------------------- plucks: sparse sine bells (pentatonic in D minor)
pent = [62, 65, 67, 69, 72, 74, 77, 79, 81]


def bell(at, m, g=1.0, pan=0.0, dec=2.2):
    s = int(at * SR)
    n = min(N - s, int(4.0 * SR))
    if n <= 0:
        return
    tt = np.arange(n) / SR
    f = note(m)
    x = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.01 * f * tt) * np.exp(-tt * 5) + 0.12 * np.sin(2 * np.pi * 3.98 * f * tt) * np.exp(-tt * 9)) * np.exp(-tt / dec)
    x *= np.clip(tt / 0.004, 0, 1)
    x = sat(x * 0.8, 1.3)
    out[s:s + n, 0] += x * g * 0.11 * (1 - pan)
    out[s:s + n, 1] += x * g * 0.11 * (1 + pan)


# reveal and title accents
bell(3.0, 69, 1.0, -0.3, 3.0); bell(3.0, 74, 0.7, 0.3, 3.0)
bell(8.7, 62, 1.0, 0.0, 4.0); bell(8.7, 69, 0.8, -0.2, 4.0); bell(8.7, 77, 0.6, 0.2, 4.0)
# parameters: one note per parameter change (12, 14, 16, 18)
for k, m in enumerate([69, 72, 74, 77]):
    bell(12.0 + 2 * k, m, 0.8, (-0.4, 0.4, -0.2, 0.2)[k])
# neon + monolith: slow arpeggio on quarter notes
seq = [62, 69, 72, 74, 72, 69, 65, 69]
for k, at in enumerate(np.arange(20.0, 32.0, 0.5)):
    bell(at, seq[k % 8] + (12 if k % 16 >= 12 else 0), 0.45 + 0.2 * ((k % 4) == 0), 0.5 * np.sin(k * 1.7), 1.4)
# particles: a chord-bell on every figure change (even seconds 32..40) + soft eighths
for k, at in enumerate(np.arange(32.0, 40.5, 2.0)):
    for m in (pent[(k * 2) % 9], pent[(k * 2 + 3) % 9], pent[(k * 2 + 5) % 9]):
        bell(at, m, 0.9, rng.uniform(-0.5, 0.5), 2.8)
for k, at in enumerate(np.arange(32.0, 40.0, 0.25)):
    if k % 8 in (2, 5, 7):
        bell(at, pent[(k * 5) % 9] + 12, 0.25, rng.uniform(-0.7, 0.7), 0.6)
# gather into text: rising bells, then the held chord
for k, at in enumerate(np.arange(40.0, 41.4, 0.175)):
    bell(at, pent[min(k, 8)] + 12, 0.5, (-0.6 + 0.15 * k), 1.5)
bell(41.4, 62, 1.0, 0, 5.0); bell(41.4, 69, 0.8, -0.2, 5.0); bell(41.4, 74, 0.7, 0.2, 5.0)
# materials + montage: quarter-note bells
for k, at in enumerate(np.arange(46.0, 56.0, 0.5)):
    bell(at, seq[(k + 3) % 8], 0.4, 0.5 * np.sin(k * 2.1), 1.2)
# end card
bell(56.0, 50, 1.0, 0, 6.0); bell(56.0, 62, 0.9, -0.2, 6.0); bell(56.0, 69, 0.7, 0.2, 6.0)

# ---------------------------------------------------------------- pulse: a soft sub thump on every bar, no clicks
duck = np.ones(N)


def thump(at, g=1.0):
    s = int(at * SR)
    n = min(N - s, int(0.6 * SR))
    tt = np.arange(n) / SR
    f = 46 + 30 * np.exp(-tt * 25)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7) * np.clip(tt / 0.006, 0, 1)
    out[s:s + n, 0] += x * g * 0.5
    out[s:s + n, 1] += x * g * 0.5
    duck[s:s + n] = np.minimum(duck[s:s + n], 1 - 0.35 * g * np.exp(-tt * 6))


for at in np.arange(12.0, 56.0, 2.0):
    if 40.0 <= at < 42.0:
        continue
    g = 0.55 if at < 20 else (0.8 if at < 32 else 1.0)
    thump(at, g)
    if 20 <= at < 40 or 46 <= at < 56:
        thump(at + 1.0, g * 0.45)          # a lighter one on beat 3
thump(41.4, 1.0)
out *= duck[:, None]

# noise breath swells into the section changes (filtered, quiet)
br = lowpass(rng.standard_normal(N), 1800) * 0.5
for at in (3.0, 12.0, 20.0, 26.0, 32.0, 46.0, 51.0, 56.0):
    add(br * env(at - 1.6, at + 0.15, 1.4, 0.15), 0.05)

# ---------------------------------------------------------------- space: a long, dark reverb
ir_n = int(3.2 * SR)
irt = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-irt / 1.0)[:, None]
ir = np.stack([lowpass(ir[:, 0], 6000), lowpass(ir[:, 1], 6000)], 1)
ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(out[:, c], ir[:, c])[:N] for c in range(2)], 1)
mix = out * 0.75 + wet * 0.55

# master: gentle glue saturation, fades, normalise
mix = sat(mix * 1.1, 1.2)
fo = np.ones(N)
fo[:int(0.4 * SR)] = np.linspace(0, 1, int(0.4 * SR))
s = int(58.0 * SR)
fo[s:] = np.linspace(1, 0, N - s) ** 2
mix *= fo[:, None]
mix /= np.abs(mix).max() / 0.89
w = wave.open('music.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((mix * 32767).astype('<i2').tobytes()); w.close()
print('ok', np.sqrt((mix ** 2).mean()))
