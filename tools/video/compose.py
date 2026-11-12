# Compose the 60 s BTDR intro from the TD recordings. One encoded file per scene, then concat + music.
import subprocess, numpy as np, sys, os, math
from PIL import Image
W, H, FPS = 1920, 1080, 60
SRC = '/mnt/user-data/uploads/ue5/btdr/out/video'
OV = '/home/claude/video/ov'
OUT = '/home/claude/video/seg'
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
        if t < 3.0:
            f = comp(f, 'lab_native', fade_ia(t, 0.15, 3.05))
            f = caption(f, t, 's1', 0.3, 2.9)
        elif t < 8.4:
            f = comp(f, 'lab_btdr', ease((t - 3.3) / 0.3) * (1 - ease((t - 8.0) / 0.3)))
            f = comp(f, 'lab_native_r', 1 - ease((t - 8.0) / 0.3))
            f = caption(f, t, 's2', 3.4, 7.9)
        f = comp(f, 'title', fade_ia(t, 8.7, 11.9, 0.5))
        w.put(f)
    w.close()


def seg_node():
    # 12-16: the network editor screenshot, slow push in
    w = Writer('s02_node')
    im = Image.open('/home/claude/video/assets/onenode.png').convert('RGB')
    iw, ih = im.size
    cx, cy = NODE_FOCUS
    for i in range(240):
        t = i / FPS
        z = 1.0 + 0.08 * ease(t / 4.0)
        cw, ch = iw / z, ih / z
        x0 = min(max(cx * iw - cw / 2, 0), iw - cw) * ease(t / 4.0) + (iw - cw) / 2 * (1 - ease(t / 4.0))
        y0 = min(max(cy * ih - ch / 2, 0), ih - ch) * ease(t / 4.0) + (ih - ch) / 2 * (1 - ease(t / 4.0))
        fr = im.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
        f = np.asarray(fr).astype(np.float32)
        f = comp(f, 'lab_onenode', fade_ia(t, 0.2, 4.0))
        f = caption(f, t, 's4', 0.3, 3.9)
        if t < 0.25:
            f = f * ease(t / 0.25)
        w.put(f)
    w.close()


def seg_neon():
    # 16-22: reflections off for 3 s, cross-fade 0.5 s, on
    w = Writer('s03_neon'); a = Reader('neon_off_btdr', 0, 360); b = Reader('neon_on_btdr', 0, 360)
    for i in range(360):
        t = i / FPS
        fa, fb = a.get(), b.get()
        k = ease((t - 3.0) / 0.5)
        f = fa * (1 - k) + fb * k
        f = comp(f, 'lab_refl_off', fade_ia(t, 0.2, 3.3))
        f = comp(f, 'lab_refl_on', fade_ia(t, 3.2, 6.0))
        f = caption(f, t, 's5', 0.3, 5.8)
        w.put(f)
    w.close()


def plain(name, src, start, n, cap, lab, debug=None, lab_end=None):
    w = Writer(name); r = Reader(src, start, n)
    for i in range(n):
        t = i / FPS
        f = r.get()
        if lab:
            f = comp(f, lab, fade_ia(t, 0.2, lab_end or n / FPS - 0.1))
        if debug:
            for k0, k1, nm in debug:
                if k0 <= i < k1:
                    f = comp(f, nm, 1.0)
        if cap:
            f = caption(f, t, cap, 0.3, n / FPS - 0.2)
        w.put(f)
    w.close()


def seg_perf():
    # 43-48: the particles gather into the numbers
    w = Writer('s07_perf'); r = Reader('particles_btdr', 960, 300)
    for i in range(300):
        t = i / FPS
        f = r.get()
        f = comp(f, 'perf_note', fade_ia(t, 1.2, 4.6))
        f = caption(f, t, 's9', 0.6, 4.8)
        w.put(f)
    w.close()


def seg_montage():
    # 48-56: 1 s each from four scenes, then the blinds room pulling back
    w = Writer('s08_montage')
    parts = [('neon_on_btdr', 300, 60), ('monolith_btdr', 360, 60), ('particles_btdr', 1260, 60), ('materials_btdr', 0, 60),
             ('blinds_out_btdr', 0, 240)]
    g = 0
    for src, st, n in parts:
        r = Reader(src, st, n)
        for i in range(n):
            t = g / FPS
            f = r.get()
            f = caption(f, t, 's12', 4.2, 7.8)
            if t > 7.6:
                f = f * (1 - ease((t - 7.6) / 0.4))
            w.put(f); g += 1
    w.close()


def seg_end():
    w = Writer('s09_end')
    e = np.asarray(Image.open(OV + '/end.png').convert('RGB')).astype(np.float32)
    for i in range(240):
        t = i / FPS
        w.put(e * ease(t / 0.5) * (1 - ease((t - 3.5) / 0.5)))
    w.close()


NODE_FOCUS = (0.5, 0.5)
if __name__ == '__main__':
    which = sys.argv[1:] or ['open', 'node', 'neon', 'mono', 'part', 'mat', 'perf', 'montage', 'end']
    if os.path.exists('/home/claude/video/assets/node_focus.txt'):
        NODE_FOCUS = tuple(float(v) for v in open('/home/claude/video/assets/node_focus.txt').read().split())
    for s in which:
        if s == 'open': seg_open()
        if s == 'node': seg_node()
        if s == 'neon': seg_neon()
        if s == 'mono': plain('s04_mono', 'monolith_btdr', 30, 360, 's6', 'lab_mono')
        if s == 'part': plain('s05_part', 'particles_btdr', 60, 540, 's7', 'lab_part')
        if s == 'mat': plain('s06_mat', 'materials_btdr', 60, 360, 's8', 'lab_mat',
                             debug=[(270, 300, 'lab_dbg_basecolor'), (300, 330, 'lab_dbg_normal'), (330, 360, 'lab_dbg_roughness')], lab_end=4.45)
        if s == 'perf': seg_perf()
        if s == 'montage': seg_montage()
        if s == 'end': seg_end()
        print('done', s, flush=True)
