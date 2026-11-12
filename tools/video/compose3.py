# Compose the 60 s BTDR intro from the TD recordings. One encoded file per scene, then concat + music.
import subprocess, numpy as np, sys, os, math
from PIL import Image
W, H, FPS = 1920, 1080, 60
SRC = '/mnt/user-data/uploads/ue5/btdr/out/video'
OV = '/home/claude/video/ov'
OUT = '/home/claude/video/seg3'
os.makedirs(OUT, exist_ok=True)
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS)]


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Reader:
    def __init__(self, name, start, count):
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', '%s/%s.mp4' % (SRC, name), '-vf',
                                   'select=gte(n\\,%d),setpts=N/FRAME_RATE/TB,scale=%d:%d' % (start, W, H),
                                   '-frames:v', str(count), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
        self.n = count
        self.last = None

    def get(self):
        b = self.p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            if self.last is None:
                raise RuntimeError('no frames')
            return self.last        # hold the last frame if a recording is short
        self.last = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)
        return self.last


_ov = {}


def ov(name):
    if name not in _ov:
        im = np.asarray(Image.open('%s/%s.png' % (OV, name)).convert('RGBA')).astype(np.float32)
        _ov[name] = (im[..., :3], im[..., 3:] / 255.0)
    return _ov[name]


def comp(f, name, a=1.0):
    if a <= 0.001:
        return f
    rgb, al = ov(name)
    al = al * a
    return f * (1 - al) + rgb * al


def fade_ia(t, t0, t1, d=0.3):
    return ease((t - t0) / d) * (1 - ease((t - (t1 - d)) / d))


class Writer:
    def __init__(self, name):
        self.tmp = '%s/%s.tmp.mp4' % (OUT, name)
        self.dst = '%s/%s.mp4' % (OUT, name)
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                                   '-r', str(FPS), '-i', '-'] + ENC + [self.tmp], stdin=subprocess.PIPE)

    def put(self, f):
        self.p.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait() == 0:
            os.replace(self.tmp, self.dst)


def caption(f, t, name, t0, t1):
    return comp(f, 'cap_' + name, fade_ia(t, t0, t1))


# ------------------------------------------------------------------ segments (global time in seconds)

from PIL import ImageDraw, ImageFont
CJK = '/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc'
INT = '/usr/share/fonts/opentype/inter/Inter-%s.otf'
F_LAB = ImageFont.truetype(INT % 'Medium', 26); F_VAL = ImageFont.truetype(INT % 'Regular', 24)
F_ZH = ImageFont.truetype(CJK % 'Regular', 22, index=2)


def caption(f, t, name, t0, t1):
    return comp(f, 'cap_' + name, fade_ia(t, t0, t1, 0.35))


def panel(f, label, zh, frac, valtext, toggle=None, a=1.0):
    """a TouchDesigner-style parameter row, top right: name | value field | slider (or a toggle)"""
    pw, ph, x0, y0 = 640, 112, W - 640 - 64, 60
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=12, fill=(38, 39, 42, 225), outline=(255, 255, 255, 38))
    d.text((24, 34), label, font=F_LAB, fill=(235, 235, 235, 255), anchor='lm')
    d.text((24, 78), zh, font=F_ZH, fill=(200, 200, 200, 220), anchor='lm')
    if toggle is None:
        d.rounded_rectangle([290, 18, 400, 50], radius=4, fill=(24, 24, 26, 255), outline=(90, 90, 95, 255))
        d.text((345, 34), valtext, font=F_VAL, fill=(250, 250, 250, 255), anchor='mm')
        bx0, bx1, by = 420, 612, 34
        d.rounded_rectangle([bx0, by - 4, bx1, by + 4], radius=4, fill=(70, 70, 75, 255))
        d.rounded_rectangle([bx0, by - 4, bx0 + (bx1 - bx0) * frac, by + 4], radius=4, fill=(92, 156, 255, 255))
        kx = bx0 + (bx1 - bx0) * frac
        d.ellipse([kx - 10, by - 10, kx + 10, by + 10], fill=(240, 240, 240, 255))
    else:
        on = toggle
        d.rounded_rectangle([290, 16, 362, 52], radius=18, fill=(92, 156, 255, 255) if on else (70, 70, 75, 255))
        kx = 344 if on else 308
        d.ellipse([kx - 14, 20, kx + 14, 48], fill=(245, 245, 245, 255))
        d.text((380, 34), 'On' if on else 'Off', font=F_VAL, fill=(250, 250, 250, 255), anchor='lm')
    arr = np.asarray(im).astype(np.float32)
    al = arr[..., 3:] / 255.0 * a
    reg = f[y0:y0 + ph, x0:x0 + pw]
    f[y0:y0 + ph, x0:x0 + pw] = reg * (1 - al) + arr[..., :3] * al
    return f


def seg_open():
    # 0-12: native 3 s, wipe in to the middle (3-3.8), hold, wipe to full (8-8.8), title
    w = Writer('s01_open'); nat = Reader('blinds_native', 0, 720); bt = Reader('blinds_btdr', 0, 720)
    xs = np.arange(W)[None, :, None]
    for i in range(720):
        t = i / FPS
        a, b = nat.get(), bt.get()
        if t < 3.0:
            d = 0
        elif t < 8.0:
            d = int(960 * ease((t - 3.0) / 0.8))
        else:
            d = int(960 + 960 * ease((t - 8.0) / 0.8))
        f = np.where(xs < d, b, a) if 0 < d < W else (b if d >= W else a)
        if 0 < d < W:
            f[:, max(0, d - 2):d + 1] = 255
        if t < 8.4:
            f = comp(f, 'lab_btdr', ease((t - 3.3) / 0.3) * (1 - ease((t - 8.0) / 0.3)))
            f = comp(f, 'lab_native_r', ease((t - 3.3) / 0.3) * (1 - ease((t - 8.0) / 0.3)))
        f = caption(f, t, 'k_native', 0.3, 2.9)
        f = comp(f, 'title', fade_ia(t, 8.7, 11.9, 0.5))
        w.put(f)
    w.close()


PCLIPS = [('p_fog', 'Fog Density', '体积雾', lambda u: (u, '%.4f' % (0.01 * u)), None),
          ('p_gi', 'Probe GI Intensity', '光追全局光照', lambda u: (u, '%.2f' % (1.5 * u)), None),
          ('p_refr', 'Transparency', '折射', None, 60),
          ('p_dof', 'F-Stop', '景深', lambda u: (u, '%.1f' % math.exp(math.log(16.0) + (math.log(1.4) - math.log(16.0)) * u)), None)]


def seg_params():
    # 12-20: four parameters TD's Render TOP does not have, 2 s each
    w = Writer('s02_params'); g = 0
    for name, lab, zh, fn, tog in PCLIPS:
        r = Reader(name + '_btdr', 0, 120)
        for i in range(120):
            t = g / FPS
            f = r.get()
            u = ease((i - 20) / 80.0)
            if tog is None:
                frac, vt = fn(u)
                f = panel(f, lab, zh, frac, vt, a=ease(i / 8.0) if g < 8 else 1.0)
            else:
                f = panel(f, lab, zh, 0, '', toggle=i >= tog)
            f = caption(f, t, 'k_param', 0.2, 7.8)
            if i < 6 and g > 0:                       # short dip between clips
                f = f * (0.55 + 0.45 * ease(i / 6.0))
            w.put(f); g += 1
    w.close()


def seg_neon():
    # 20-26: reflections off, cross-fade at 3 s, on
    w = Writer('s03_neon'); a = Reader('neon_off_btdr', 0, 360); b = Reader('neon_on_btdr', 0, 360)
    for i in range(360):
        t = i / FPS
        fa, fb = a.get(), b.get()
        k = ease((t - 3.0) / 0.5)
        f = fa * (1 - k) + fb * k
        f = comp(f, 'lab_refl_off', fade_ia(t, 0.2, 3.3))
        f = comp(f, 'lab_refl_on', fade_ia(t, 3.2, 6.0))
        f = caption(f, t, 'k_refl', 0.3, 5.8)
        w.put(f)
    w.close()


def plain(name, src, start, n, cap):
    w = Writer(name); r = Reader(src, start, n)
    for i in range(n):
        t = i / FPS
        f = r.get()
        if cap:
            f = caption(f, t, cap, 0.3, n / FPS - 0.2)
        w.put(f)
    w.close()


def seg_part():
    # 32-46: Chladni figures (32-40), the sand gathers into the numbers (40-46)
    w = Writer('s05_part'); r = Reader('particles_btdr', 0, 840)
    for i in range(840):
        t = i / FPS
        f = r.get()
        f = caption(f, t, 'k_chladni', 0.3, 7.7)
        f = caption(f, t, 'k_perf', 9.3, 13.8)
        f = comp(f, 'perf_note', fade_ia(t, 9.3, 13.8))
        w.put(f)
    w.close()


def seg_montage():
    # 51-56: quick cuts, then the blinds room pulling back
    w = Writer('s07_montage')
    parts = [('neon_on_btdr', 300, 45), ('monolith_btdr', 360, 45), ('particles_btdr', 300, 45), ('materials_btdr', 30, 45),
             ('blinds_out_btdr', 120, 120)]
    g = 0
    for src, st, n in parts:
        r = Reader(src, st, n)
        for i in range(n):
            t = g / FPS
            f = r.get()
            if t > 4.6:
                f = f * (1 - ease((t - 4.6) / 0.4))
            w.put(f); g += 1
    w.close()


def seg_end():
    w = Writer('s08_end')
    e = np.asarray(Image.open(OV + '/end.png').convert('RGB')).astype(np.float32)
    for i in range(240):
        t = i / FPS
        w.put(e * ease(t / 0.5) * (1 - ease((t - 3.5) / 0.5)))
    w.close()


SEGS = ['s01_open', 's02_params', 's03_neon', 's04_mono', 's05_part', 's06_mat', 's07_montage', 's08_end']
if __name__ == '__main__':
    which = sys.argv[1:] or ['open', 'params', 'neon', 'mono', 'part', 'mat', 'montage', 'end']
    for s in which:
        if s == 'open': seg_open()
        if s == 'params': seg_params()
        if s == 'neon': seg_neon()
        if s == 'mono': plain('s04_mono', 'monolith_btdr', 30, 360, 'k_vol')
        if s == 'part': seg_part()
        if s == 'mat': plain('s06_mat', 'materials_btdr', 30, 300, 'k_refr')
        if s == 'montage': seg_montage()
        if s == 'end': seg_end()
        print('done', s, flush=True)
    open(OUT + '/list.txt', 'w').write(''.join("file '%s/%s.mp4'\n" % (OUT, n) for n in SEGS))
