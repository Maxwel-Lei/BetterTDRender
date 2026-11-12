# BTDR intro video recorder (VIDEO.*).
# Runs inside TD. Each shot drives cameras / parameters as a pure function of the
# shot-local frame index and records one or more TOPs with Movie File Out TOPs,
# with the project in non-realtime mode so no frame is dropped.
#
#   exec(open(project.folder + '/btdr/tools/video_rig.py', encoding='utf-8').read())
#   VR.record('hero')            # or VR.preview('hero', [0, 300, 700])
#
# All touched parameters are saved before a shot and restored afterwards
# (also on error). Nothing is stored in OP storage except plain data.
import math, json, os

RIG = '/project1/video_rig'
OUTDIR = project.folder + '/btdr/out/video'
DEMO = '/project1/btdr_demo'
CAR = '/project1/btdr_models/CarConcept'
M6 = '/project1/m6_test'
WARM = 90


def _ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


class Ctx:
    """Parameter setter that remembers original values for restore."""
    def __init__(self, saved):
        self.saved = saved  # list of [path, name, mode, val, expr]
        self.keys = set((s[0], s[1]) for s in saved)

    def set(self, path, name, value):
        o = op(path)
        p = o.par[name]
        if (path, name) not in self.keys:
            self.keys.add((path, name))
            v = p.eval()
            if hasattr(v, 'path'):
                v = v.path
            self.saved.append([path, name, str(p.mode), v if isinstance(v, (int, float, str, bool)) or v is None else str(v), p.expr])
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        elif p.eval() == value or (value in ('', None) and p.eval() in ('', None)):
            return          # re-setting an unchanged value still counts as a change (shadow map / fog history reset)
        p.val = value

    def look(self, cam, pos, tgt):
        dx, dy, dz = tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        dx, dy, dz = dx / L, dy / L, dz / L
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, dy))))
        yaw = math.degrees(math.atan2(-dx, -dz))
        self.set(cam, 'pathop', '')
        self.set(cam, 'lookat', '')
        self.set(cam, 'xord', 'srt')
        self.set(cam, 'rord', 'xyz')
        for n in ('px', 'py', 'pz'):        # the viewer's navigation leaves a pivot behind: it rotates the camera around it
            self.set(cam, n, 0.0)
        for n, v in (('tx', pos[0]), ('ty', pos[1]), ('tz', pos[2]), ('rx', pitch), ('ry', yaw), ('rz', 0.0)):
            self.set(cam, n, v)
        return (dx, dy, dz)


def _orbit(tgt, r, h, a_deg):
    a = math.radians(a_deg)
    return (tgt[0] + r * math.cos(a), h, tgt[2] + r * math.sin(a))


def _restore(saved):
    for path, name, mode, val, expr in reversed(saved):
        o = op(path)
        if o is None:
            continue
        p = o.par[name]
        try:
            if mode == 'ParMode.EXPRESSION':
                p.expr = expr
                p.mode = ParMode.EXPRESSION
            else:
                p.mode = ParMode.CONSTANT
                p.val = '' if val is None else val
        except Exception as e:
            debug('restore', path, name, e)


# ---------------------------------------------------------------- shots
DT = (0.0, 0.62, 0.0)
HT = (0.15, 0.78, 0.1)
B = DEMO + '/renderBTDR1'


def demo_base(c, fog=False):
    c.set(B, 'Fog', fog)
    c.set(B, 'Dof', False)
    c.set(B, 'Motionblur', False)
    c.set(B, 'Debugview', 'final')


def hero_setup(c):
    demo_base(c)


def hero_update(c, i, n):
    t = i / max(n - 1, 1)
    a = _lerp(-22.0, 38.0, t)
    c.look(DEMO + '/cam1', _orbit(DT, 3.7, 1.0, a), HT)


def outro_setup(c):
    demo_base(c)


def outro_update(c, i, n):
    t = _ease(i / max(n - 1, 1))
    a = _lerp(38.0, 72.0, i / max(n - 1, 1))
    r = _lerp(2.3, 7.5, t)
    h = _lerp(0.8, 2.1, t)
    c.look(DEMO + '/cam1', _orbit(DT, r, h, a), (0.15, _lerp(0.6, 0.55, t), 0.1))


DBG = ['basecolor', 'normal', 'roughness', 'direct', 'final']


def debug_setup(c):
    demo_base(c)


def debug_update(c, i, n):
    c.look(DEMO + '/cam1', _orbit(DT, 2.9, 0.95, 10.0 + 4.0 * i / n), (0.2, 0.62, 0.15))
    c.set(B, 'Debugview', DBG[min(i // 60, 4)] if i >= 0 else 'final')


def floor_setup(on):
    def f(c):
        demo_base(c)
        for n in ('Ambientocclusion', 'Ssgi', 'Ssr'):
            c.set(B, n, on)
    return f


def floor_update(c, i, n):
    t = i / max(n - 1, 1)
    c.look(DEMO + '/cam1', _orbit((0.2, 0, 0.15), _lerp(2.1, 1.8, t), 0.16, _lerp(-6, 12, t)), (0.2, 0.32, 0.15))


def fog_setup(c):
    demo_base(c, fog=True)
    c.set(B, 'Fogdensity', 0.14)
    c.set(B, 'Foganisotropy', 0.8)
    c.set(B, 'Fogambient', 0.08)
    c.set(B, 'Fogheightfalloff', 0.0)
    c.set(B, 'Fogdistance', 20.0)
    c.set(DEMO + '/light1', 'rx', -24.0)


def fog_update(c, i, n):
    t = i / max(n - 1, 1)
    c.look(DEMO + '/cam1', _orbit(DT, 3.3, 0.55, -140.0 + 6 * t), (0.15, 0.85, 0.1))
    c.set(DEMO + '/light1', 'ry', _lerp(32.0, 62.0, t))


ANT = (-0.22, 0.32, 0.2)
HEL = (0.62, 0.35, 0.14)


def dof_setup(c):
    demo_base(c)
    c.set(B, 'Dof', True)
    c.set(B, 'Fstop', 1.4)
    c.set(B, 'Motionblur', True)
    c.set(B, 'Shutter', 1.0)


def dof_update(c, i, n):
    pos = (-1.35, 0.5, 0.62)
    tgt = (0.3, 0.33, 0.12)
    sec = i / 60.0
    if sec > 2.6:  # whip pan
        u = _ease((sec - 2.6) / 1.1)
        yaw = math.radians(_lerp(0.0, 38.0, u))
        dx, dz = tgt[0] - pos[0], tgt[2] - pos[2]
        tgt = (pos[0] + dx * math.cos(yaw) - dz * math.sin(yaw), tgt[1], pos[2] + dx * math.sin(yaw) + dz * math.cos(yaw))
    d = c.look(DEMO + '/cam1', pos, tgt)

    def dist(p):
        return (p[0] - pos[0]) * d[0] + (p[1] - pos[1]) * d[1] + (p[2] - pos[2]) * d[2]
    f = _lerp(dist(HEL), dist(ANT), _ease((sec - 0.6) / 1.4))
    c.set(B, 'Focusdistance', max(f, 0.2))


CB = CAR + '/renderBTDR1'


def car_setup(on):
    def f(c):
        c.set(CB, 'Raytracing', on)
        c.set(CB, 'Debugview', 'final')
        if op(CAR + '/keep_cooking'):
            c.set(CAR + '/keep_cooking', 'active', False)
    return f


def car_update(c, i, n):
    t = op(CAR + '/target')
    tg = (t.par.tx.eval(), t.par.ty.eval(), t.par.tz.eval())
    u = i / max(n - 1, 1)
    c.look(CAR + '/cam1', _orbit(tg, _lerp(5.2, 4.8, u), 0.38, _lerp(-128, -118, u)), (tg[0], 0.42, tg[2]))
    if VR.flash and i >= n - 55:
        c.set(CB, 'Debugview', 'rtrefl')


MB = M6 + '/renderBTDR1'
MT = (0.0, 0.55, -0.85)


def refr_setup(method):
    def f(c):
        c.set(MB, 'Refrmethod', method)
        c.set(MB, 'Debugview', 'final')
        if op(M6 + '/keep_cooking'):
            c.set(M6 + '/keep_cooking', 'active', False)
    return f


def refr_update(c, i, n):
    u = i / max(n - 1, 1)
    c.look(M6 + '/cam1', _orbit(MT, _lerp(5.6, 5.0, u), 1.35, _lerp(78, 98, u)), MT)


def probe_update(c, i, n):
    c.look(DEMO + '/cam1', _orbit(DT, 4.6, 1.1, -180.0 + i * 0.5), (0.15, 0.8, 0.1))


# ------------------------------------------------ showcase scenes (examples/make_scenes.py)
def _P(nm):
    return '/project1/sc_' + nm


def blinds_setup(c):
    c.set(_P('blinds') + '/renderBTDR1', 'Debugview', 'final')


def blinds_update(c, i, n):
    u = i / max(n - 1, 1)
    # nearly static: the volumetric fog accumulates over many frames and stays clean (big moves make it noisy here)
    pos = (_lerp(2.95, 2.75, u), _lerp(1.75, 1.7, u), _lerp(2.7, 2.45, u))
    c.look(_P('blinds') + '/cam1', pos, (-0.6, 0.95, -1.6))


def blinds_out_update(c, i, n):
    u = _ease(i / max(n - 1, 1))
    pos = (_lerp(2.2, 3.3, u), _lerp(1.6, 1.85, u), _lerp(1.8, 2.85, u))
    c.look(_P('blinds') + '/cam1', pos, (-0.6, 0.9, -1.6))


def neon_setup(on):
    def f(c):
        R = _P('neon') + '/renderBTDR1'
        c.set(R, 'Ssr', on)
        c.set(R, 'Rtreflections', on)
    return f


def neon_update(c, i, n):
    u = i / max(n - 1, 1)
    z = _lerp(6.0, 1.0, u)
    c.look(_P('neon') + '/cam1', (_lerp(0.4, -0.2, u), 0.32, z), (0.0, 1.5, z - 22.0))


def mono_setup(c):
    pass


def mono_update(c, i, n):
    # truck from left to right across the light sheets while pushing in ([BTDR:SCENES.MONOLITH]): the camera
    # passes from shadow into the lit gaps of the screen and back, so the rays sweep around the sun.
    # The view direction stays fixed (target moves with the camera): the sun holds its place in the frame.
    u = i / max(n - 1, 1)
    e = 0.5 - 0.5 * math.cos(math.pi * u)
    x = _lerp(-7.0, 7.0, e)
    y = 1.2 + 0.3 * math.sin(math.pi * u)
    z = _lerp(41.0, 35.0, e)
    c.look(_P('monolith') + '/cam1', (x, y, z), (x, y + 6.8, z - 100.0))
    c.set(_P('monolith') + '/renderBTDR1', 'Focusdistance', z - 14.0)


PART_T0 = 32.0       # global video time (s) of the first recorded particle frame (v3 timeline)
FEAT = []


def _feat(k):
    global FEAT
    if not FEAT:
        FEAT = [tuple(float(v) for v in ln.split(',')) for ln in
                open(project.folder + '/btdr/examples/audio/audio_feat.csv').read().split()]
    return FEAT[max(0, min(k, len(FEAT) - 1))]


def part_setup(c):
    S = _P('particles')
    c.set(S + '/feat', 'index', 1)


def part_update(c, i, n):
    S = _P('particles')
    tg = PART_T0 + i / 60.0
    b, m, h, k = _feat(int(round(tg * 60)))
    for j, v in enumerate((b, m, h, k)):
        c.set(S + '/feat_baked', 'value%d' % j, v)
    c.set(S + '/clock', 'value0', tg)
    # gather into the text 40.0-44.6 s
    f = _ease((tg - 40.0) / 1.3) * (1.0 - _ease((tg - 44.4) / 1.2))
    c.set(S + '/swirl', 'vec2valuex', f)
    # Chladni part: a high slow orbit so the figures read; then down to the front for the text
    a = _lerp(-35.0, -5.0, (tg - PART_T0) / 8.0) if tg < 40.0 else _lerp(-5.0, 0.0, _ease((tg - 40.0) / 1.2)) + max(0.0, tg - 44.6) * 5.0
    u = _ease((tg - 40.0) / 1.2) * (1.0 - _ease((tg - 44.6) / 1.4))
    r = _lerp(10.0, 10.5, u)
    y = _lerp(6.0, 1.9, u)
    pos = (r * math.sin(math.radians(a)), y, r * math.cos(math.radians(a)))
    c.look(S + '/cam1', pos, (0.0, _lerp(0.6, 1.7, u), 0.0))


MDBG = ['basecolor', 'normal', 'roughness']


def mat_setup(c):
    c.set(_P('materials') + '/renderBTDR1', 'Debugview', 'final')


def mat_update(c, i, n):
    S = _P('materials')
    u = i / max(n - 1, 1)
    x = _lerp(4.4, -2.4, _ease(u) * 0.3 + u * 0.7)
    c.look(S + '/cam1', (x, 1.65, 3.3), (x - 1.9, 1.15, 0.0))
    k = i - (n - 90)
    c.set(S + '/renderBTDR1', 'Debugview', MDBG[k // 30] if k >= 0 else 'final')


# ---------------------------------------------------------------- parameter page (v3): what TD's Render TOP lacks
PSWEEP = 120                       # frames per clip (2 s); the value moves over frames 20..100


def _pv(i):
    return _ease((i - 20) / 80.0)


def pfog_update(c, i, n):
    S = _P('monolith')
    c.look(S + '/cam1', (-3.5, 1.2, 38.0), (-3.5, 8.0, -62.0))
    c.set(S + '/renderBTDR1', 'Focusdistance', 24.0)
    c.set(S + '/renderBTDR1', 'Fogdensity', round(_lerp(0.0, 0.01, _pv(i)), 5))


def pgi_update(c, i, n):
    S = _P('blinds')
    c.look(S + '/cam1', (2.85, 1.72, 2.58), (-0.6, 0.95, -1.6))
    c.set(S + '/renderBTDR1', 'Rtgiintensity', round(_lerp(0.0, 1.5, _pv(i)), 4))


def prefr_update(c, i, n):
    S = _P('materials')
    c.look(S + '/cam1', (3.1, 1.55, 2.7), (3.1, 1.15, 0.0))
    c.set(S + '/renderBTDR1', 'Debugview', 'final')
    c.set(S + '/renderBTDR1', 'Transparency', i >= 60)


def pdof_update(c, i, n):
    S = _P('materials')
    pos, tgt = (-4.6, 1.45, 2.2), (-2.2, 1.2, 0.0)
    c.look(S + '/cam1', pos, tgt)
    c.set(S + '/renderBTDR1', 'Debugview', 'final')
    c.set(S + '/renderBTDR1', 'Dof', True)
    c.set(S + '/renderBTDR1', 'Focusdistance', round(math.dist(pos, (-2.5, 1.25, 0.0)), 3))
    c.set(S + '/renderBTDR1', 'Fstop', round(math.exp(_lerp(math.log(16.0), math.log(1.4), _pv(i))), 3))


SHOTS = {
    'blinds': dict(src={'native': _P('blinds') + '/native_out', 'btdr': _P('blinds') + '/renderBTDR1/out1'}, n=720,
                   setup=blinds_setup, update=blinds_update),
    'blinds_out': dict(src={'btdr': _P('blinds') + '/renderBTDR1/out1'}, n=300, setup=blinds_setup, update=blinds_out_update),
    'neon_off': dict(src={'btdr': _P('neon') + '/renderBTDR1/out1'}, n=360, setup=neon_setup(False), update=neon_update),
    'neon_on': dict(src={'btdr': _P('neon') + '/renderBTDR1/out1'}, n=360, setup=neon_setup(True), update=neon_update),
    'monolith': dict(src={'btdr': _P('monolith') + '/renderBTDR1/out1'}, n=420, setup=mono_setup, update=mono_update),
    'particles': dict(src={'btdr': _P('particles') + '/renderBTDR1/out1'}, n=840, setup=part_setup, update=part_update),
    'materials': dict(src={'btdr': _P('materials') + '/renderBTDR1/out1'}, n=420, setup=mat_setup, update=mat_update),
    'p_fog': dict(src={'btdr': _P('monolith') + '/renderBTDR1/out1'}, n=PSWEEP, setup=mono_setup, update=pfog_update),
    'p_gi': dict(src={'btdr': _P('blinds') + '/renderBTDR1/out1'}, n=PSWEEP, setup=blinds_setup, update=pgi_update),
    'p_refr': dict(src={'btdr': _P('materials') + '/renderBTDR1/out1'}, n=PSWEEP, setup=mat_setup, update=prefr_update),
    'p_dof': dict(src={'btdr': _P('materials') + '/renderBTDR1/out1'}, n=PSWEEP, setup=mat_setup, update=pdof_update),
}


class _VR:
    flash = False

    def _rig(self):
        r = op(RIG)
        if r is None:
            r = op('/project1').create(baseCOMP, 'video_rig')
            r.nodeX, r.nodeY = 0, -1600
        return r

    def queue(self, items):
        # items: list of (name, mode, frames)
        r = self._rig()
        r.store('queue', [list(x) for x in items[1:]])
        n, m, f = items[0]
        return self._start(n, m, f)

    def _start(self, name, mode, frames=()):
        if op(RIG) and op(RIG).fetch('state', None, storeDefault=False):
            raise RuntimeError('video_rig busy')
        os.makedirs(OUTDIR, exist_ok=True)
        r = self._rig()
        for ch in list(r.children):
            if ch.valid and ch.name.startswith(('sel_', 'mfo_', 'tick', 'rig_mod')) and ch.name not in ('tick', 'rig_mod'):
                ch.destroy()
        spec = SHOTS[name]
        mfos = {}
        for tag, src in spec['src'].items():
            sel = r.create(selectTOP, 'sel_' + tag)
            sel.par.top = src
            m = r.create(moviefileoutTOP, 'mfo_' + tag)
            m.inputConnectors[0].connect(sel)
            m.par.type = 'movie'
            m.par.videocodec = 'h264'
            m.par.moviecontainer = 'mp4'
            m.par.fps = 60
            m.par.file = '%s/%s_%s.mp4' % (OUTDIR, name, tag)
            m.par.record = False
            for pn, pv in (('qualityscale', 1.0),):
                try:
                    m.par[pn] = pv
                except Exception:
                    pass
            mfos[tag] = m.path
        ex = r.op('tick') or r.create(executeDAT, 'tick')
        ex.text = ("def onFrameStart(frame):\n    mod('/project1/video_rig/rig_mod').VR.step()\n    return\n"
                   "def onFrameEnd(frame):\n    mod('/project1/video_rig/rig_mod').VR.end()\n    return\n")
        rm = r.op('rig_mod') or r.create(textDAT, 'rig_mod')
        rm.text = open(project.folder + '/btdr/tools/video_rig.py', encoding='utf-8').read()
        ex.par.framestart = True
        ex.par.frameend = True
        r.store('state', dict(name=name, mode=mode, i=-WARM, frames=list(frames), mfos=mfos, saved=[], rt=project.realTime, done=False))
        project.realTime = False
        ex.par.active = True
        return 'started ' + name

    def record(self, name):
        return self._start(name, 'record')

    def preview(self, name, frames):
        return self._start(name, 'preview', frames)

    def step(self):
        r = op(RIG)
        st = r.fetch('state', None, storeDefault=False)
        if not st or st['done']:
            return
        spec = SHOTS[st['name']]
        VR.flash = spec.get('flash', False)
        c = Ctx(st['saved'])
        try:
            i, n = st['i'], spec['n']
            if i == -WARM:
                spec['setup'](c)
            if i < n:
                spec['update'](c, max(i, 0), n)
            if st['mode'] == 'record':
                on = 0 <= i < n
                for pth in st['mfos'].values():
                    if op(pth).par.record.eval() != on:
                        op(pth).par.record = on
            st['saved'] = c.saved
            r.store('state', st)
        except Exception as e:
            st['saved'] = c.saved
            r.store('state', st)
            self._finish('error: %r' % (e,))

    def end(self):
        r = op(RIG)
        st = r.fetch('state', None, storeDefault=False)
        if not st or st['done']:
            return
        spec = SHOTS[st['name']]
        i = st['i']
        if st['mode'] == 'preview' and i in st['frames']:
            for tag, src in spec['src'].items():
                op(src).save('%s/pv_%s_%s_%04d.jpg' % (OUTDIR, st['name'], tag, i))
        st['i'] = i + 1
        r.store('state', st)
        last = max(st['frames']) if st['mode'] == 'preview' else spec['n'] + 2
        if st['i'] > last:
            self._finish('ok')

    def _finish(self, msg):
        r = op(RIG)
        st = r.fetch('state')
        for pth in st['mfos'].values():
            if op(pth):
                op(pth).par.record = False
        _restore(st['saved'])
        project.realTime = st['rt']
        st['done'] = True
        r.store('state', st)
        r.op('tick').par.active = False
        with open(OUTDIR + '/status.txt', 'a', encoding='utf-8') as f:
            f.write('%s %s %s frames=%d\n' % (st['name'], st['mode'], msg, st['i']))
        r.unstore('state')
        q = r.fetch('queue', [], storeDefault=False)
        if q:
            r.store('queue', q[1:])
            run("mod('/project1/video_rig/rig_mod').VR._start(%r, %r, %r)" % tuple(q[0]), delayFrames=3)
        else:
            r.unstore('queue')
            with open(OUTDIR + '/status.txt', 'a', encoding='utf-8') as f:
                f.write('QUEUE DONE\n')


VR = _VR()
