# [BTDR:FILE.TEST.M84] m84_tests.py — 0.8.4: energy compensation, traced-reflection upsampling, Refraction Scale,
# absorption colour, hashed alpha test, and "nothing else changed" against the previous release.
# Run: exec(open(project.folder + '/btdr/tests/m84_tests.py', encoding='utf-8').read())
# Needs release/BTDR_ref.tox = the previous release (0.8.3) for the A/B checks; copy it there before building 0.8.4.
# Result: btdr/out/m84_tests.txt (first line STATUS PASS / FAIL), btdr/out/m84_*.jpg; the test network is removed.
#   LIGHT.ENERGY      rough metal brighter with Energy Compensation (>= +8 %), smooth metal and rough plastic nearly
#                     unchanged (< 4 %); off = exactly the previous release (checked with tools/ab_compare.py)
#   COMP.RTUP         traced reflections: less 4x4 block structure than the previous release on the scene-unit scene
#   REFR.SCALE        Refraction Scale 0 / 1 / 2: 0 is (almost) a straight view, 2 bends differently from 1
#   REFR.ABSORBCOLOR  custom absorption colour (red) on white glass: the transmitted light turns red, the surface does not
#   GBUF.HASHALPHA    a 45 %-alpha plane with Alpha Test (threshold 0.5): Threshold mode cuts all of it, Hashed keeps
#                     about 45 % of its pixels
# BTDRs are created one per step (several in one frame can trip the GPU driver timeout, §11 #...).
import traceback, shutil, os
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm84_test'
W, H = 640, 360
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m84_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len([l for l in LOG if not l.startswith('INFO')]), len(FAILS))
        + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t and not KEEP: t.destroy()
def step(fn, frames, *a):
    def wrapped():
        try:
            fn(*a)
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    run("args[0]()", wrapped, delayFrames=frames)
def arr(o):
    o.cook(force=True)
    return np.array(o.numpyArray(delayed=False), dtype=np.float64)
def errs(R):
    return [(c.name, c.errors().strip()[:80]) for c in R.findChildren() if c.valid and c.errors()]
try:
    KEEP
except NameError:
    KEEP = False
ST = {}

def scene(nm, tox=None):
    """an empty base with a keep-cooking DAT; returns (S, add-BTDR function)"""
    S = T.create(baseCOMP, nm)
    return S
def pbr(S, n, c, rough, metal=0.0, alpha=1.0):
    m = S.create(pbrMAT, n); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
    m.par.roughness = rough; m.par.metallic = metal; m.par.alphafront = alpha
    return m
def geo(S, n, sop, mat, t, sc=1.0):
    g = S.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    so = g.create(sop, 's'); so.render = so.display = True
    g.par.tx, g.par.ty, g.par.tz = t; g.par.scale = sc; g.par.material = mat
    return g, so
def btdr(S, tox=BT + '/release/BTDR.tox', name='renderBTDR1'):
    r = S.loadTox(tox); r.name = name
    r.par.Startupinfo = False; r.par.Cover = False
    r.par.Resolutionw = W; r.par.Resolutionh = H
    KEEPLIST.append(r.path)
    return r
KEEPLIST = []

try:
    open(BT + '/out/m84_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1400
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    for p in me.parent().fetch('keep', []):\n        o = op(p + '/out1')\n"
                 "        if o: o.cook(force=True)\n    return\n")
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True
    HAS_REF = os.path.exists(BT + '/release/BTDR_ref.tox')

    # ------------------------------------------------------------ part 1: energy compensation (three spheres)
    E = scene('energy')
    for i, (nm, c, r, m) in enumerate((('roughmetal', (1.0, 0.78, 0.34), 0.8, 1.0), ('smoothmetal', (1.0, 0.78, 0.34), 0.1, 1.0),
                                       ('roughplastic', (0.5, 0.5, 0.5), 0.8, 0.0))):
        g, s = geo(E, nm, sphereSOP, pbr(E, 'm_' + nm, c, r, m), ((i - 1) * 1.25, 0, 0))
        s.par.type = 'poly'; s.par.freq = 16; s.par.radx = s.par.rady = s.par.radz = 0.55
    c = E.create(cameraCOMP, 'cam1'); c.par.tz = 4.2; c.par.fov = 45
    l = E.create(lightCOMP, 'light1'); l.par.lighttype = 'distant'; l.par.shadowtype = 'off'; l.par.rx = -35; l.par.ry = 25
    RE = btdr(E)
    RE.par.Ssr = False; RE.par.Ssgi = False; RE.par.Raytracing = False; RE.par.Bloom = 0
    T.store('keep', list(KEEPLIST))

    def thirds(img, mask):
        out = []
        for k in range(3):
            sl = slice(k * W // 3, (k + 1) * W // 3)
            mk = mask[:, sl]
            out.append(float(img[:, sl][mk].mean()) if mk.any() else 0.0)
        return out
    def e1():
        e = errs(RE)
        check('energy: no errors', not e, str(e[:3]))
        RE.par.Energycomp = True
        step(e2, 30)
    def e2():
        ST['on'] = arr(RE.op('composite'))[:, :, :3].mean(-1)
        ST['mask'] = (arr(RE.op('gbuf1'))[:, :, :3] ** 2).sum(-1) > 0.25
        RE.op('out1').save(BT + '/out/m84_energy_on.jpg')
        RE.par.Energycomp = False
        step(e3, 30)
    def e3():
        off = arr(RE.op('composite'))[:, :, :3].mean(-1)
        RE.op('out1').save(BT + '/out/m84_energy_off.jpg')
        a, b = thirds(ST['on'], ST['mask']), thirds(off, ST['mask'])
        r = [x / max(y, 1e-6) for x, y in zip(a, b)]
        check('LIGHT.ENERGY rough metal brighter', r[0] >= 1.08, 'on / off %.3f' % r[0])
        check('LIGHT.ENERGY smooth metal ~unchanged', abs(r[1] - 1) < 0.04, 'on / off %.3f' % r[1])
        check('LIGHT.ENERGY rough plastic ~unchanged', abs(r[2] - 1) < 0.04, 'on / off %.3f' % r[2])
        step(b1, 2)

    # -------------------------------------------- part 2: traced reflections, block structure vs previous release
    def bscene(nm, tox):
        S = scene(nm)
        _, fl = geo(S, 'floor', gridSOP, pbr(S, 'm_floor', (0.6, 0.6, 0.6), 0.25), (0, 0, 0)); fl.par.sizex = fl.par.sizey = 8; fl.par.orient = 'zx'
        _, sp = geo(S, 'ball', sphereSOP, pbr(S, 'm_ball', (0.8, 0.2, 0.15), 0.35), (-0.6, 0.5, 0))
        sp.par.type = 'poly'; sp.par.freq = 10; sp.par.radx = sp.par.rady = sp.par.radz = 0.5
        geo(S, 'cube', boxSOP, pbr(S, 'm_cube', (0.9, 0.9, 0.9), 0.1, 1.0), (0.7, 0.4, -0.3), 0.8)
        c = S.create(cameraCOMP, 'cam1'); c.par.tx, c.par.ty, c.par.tz = 0.4, 1.4, 3.6; c.par.rx = -18
        c.par.near = 0.05; c.par.far = 100
        l = S.create(lightCOMP, 'light1'); l.par.lighttype = 'distant'; l.par.shadowtype = 'off'; l.par.rx = -40; l.par.ry = 30
        r = btdr(S, tox)
        r.par.Heightfieldao = True
        T.store('keep', list(KEEPLIST))
        return r
    def blockiness(d):
        """ratio of the jump across 4-pixel block borders to the jump inside blocks (1 = no block structure)"""
        g = np.abs(np.diff(d, axis=1)).mean(0)          # per column boundary
        k = np.arange(g.size)
        at = g[(k % 4) == 3].mean(); inside = g[(k % 4) != 3].mean()
        g2 = np.abs(np.diff(d, axis=0)).mean(1)
        k2 = np.arange(g2.size)
        at2 = g2[(k2 % 4) == 3].mean(); in2 = g2[(k2 % 4) != 3].mean()
        return float((at + at2) / max(inside + in2, 1e-9))
    def b1():
        ST['bn'] = bscene('blk_new', BT + '/release/BTDR.tox')
        step(b2, 5)
    def b2():
        if HAS_REF:
            ST['br'] = bscene('blk_ref', BT + '/release/BTDR_ref.tox')
        step(b3, 180)
    def b3():
        rn = ST['bn']
        e = errs(rn)
        check('reflections: no errors', not e, str(e[:3]))
        rn.op('out1').save(BT + '/out/m84_refl_new.jpg')
        hn = arr(rn.op('composite'))[:, :, :3].mean(-1)
        ST['hn'] = hn
        if HAS_REF:
            ST['br'].op('out1').save(BT + '/out/m84_refl_ref.jpg')
            ST['hr'] = arr(ST['br'].op('composite'))[:, :, :3].mean(-1)
        rn.par.Rtreflections = False
        if HAS_REF: ST['br'].par.Rtreflections = False
        step(b4, 40)
    def b4():
        rn = ST['bn']
        dn = ST['hn'] - arr(rn.op('composite'))[:, :, :3].mean(-1)       # what the traced reflections add / remove
        bn = blockiness(dn)
        LOG.append('INFO traced-reflection contribution: blockiness new %.3f, |mean| %.4f' % (bn, float(np.abs(dn).mean())))
        if HAS_REF:
            dr = ST['hr'] - arr(ST['br'].op('composite'))[:, :, :3].mean(-1)
            br = blockiness(dr)
            check('COMP.RTUP less block structure than 0.8.3', bn < br * 0.85 or bn < 1.15, 'new %.3f ref %.3f' % (bn, br))
            # the reflections must still be there (not smoothed away)
            check('COMP.RTUP reflections still present', float(np.abs(dn).mean()) > 0.3 * float(np.abs(dr).mean()),
                  '|contribution| new %.4f ref %.4f' % (float(np.abs(dn).mean()), float(np.abs(dr).mean())))
        else:
            check('COMP.RTUP block structure', bn < 1.15, 'new %.3f (no BTDR_ref.tox for A/B)' % bn)
        step(a1, 2)

    # part 3 (0.8.4): "everything new off = 0.8.3" is checked with tools/ab_compare.py (both builds created in the same
    # frame and pulled together, which gives exactly 0); here the two scenes are created frames apart, so their TAA
    # histories differ and a pixel A/B would measure that instead ([BTDR:TEST.M84AB])
    def a1():
        for nm in ('blk_new', 'blk_ref'):
            o = T.op(nm)
            if o:
                KEEPLIST[:] = [p for p in KEEPLIST if not p.startswith(o.path)]
                o.destroy()
        T.store('keep', list(KEEPLIST))
        step(g1, 5)

    # ------------------------------------------- part 4: glass: Refraction Scale and absorption colour
    def gscene():
        S = scene('glass')
        bg = pbr(S, 'm_bg', (1, 1, 1), 0.6)
        g, s = geo(S, 'stripes', boxSOP, bg, (0, 0, -1.5))
        s.par.sizex, s.par.sizey, s.par.sizez = 6, 4, 0.05
        for i in range(7):     # vertical colour stripes so a sideways shift shows
            col = [(0.9, 0.1, 0.1), (0.1, 0.8, 0.2), (0.1, 0.3, 0.9)][i % 3]
            g, s = geo(S, 'bar%d' % i, boxSOP, pbr(S, 'm_bar%d' % i, col, 0.5), (-1.5 + i * 0.5, 0, -1.45))
            s.par.sizex, s.par.sizey, s.par.sizez = 0.22, 3.5, 0.02
        g, s = geo(S, 'ball', sphereSOP, pbr(S, 'm_glass', (1, 1, 1), 0.02, alpha=0.0), (0, 0, 0))
        s.par.type = 'poly'; s.par.freq = 24; s.par.radx = s.par.rady = s.par.radz = 0.8
        c = S.create(cameraCOMP, 'cam1'); c.par.tz = 3.5; c.par.fov = 45
        l = S.create(lightCOMP, 'light1'); l.par.lighttype = 'distant'; l.par.shadowtype = 'off'; l.par.rx = -35
        R = btdr(S)
        R.par.Geometry = 'stripes bar*'
        R.par.Raytracing = False; R.par.Bloom = 0; R.par.Ssr = False
        R.seq.Refr.numBlocks = 1
        R.par.Refr0geo = 'ball'; R.par.Refr0preset = 'glass'; R.ApplyPreset(0)
        R.Refresh()
        T.store('keep', list(KEEPLIST))
        return R
    def g1():
        ST['g'] = gscene()
        step(g2, 60)
    def g2():
        R = ST['g']
        e = errs(R)
        check('glass: no errors', not e, str(e[:3]))
        ST['mask'] = (arr(R.op('tgbuf1'))[:, :, :3] ** 2).sum(-1) > 0.25
        ST['opq'] = arr(R.op('composite'))[:, :, :3]
        ST['sc'] = {}; ST['si'] = 0
        step(g3, 1)
    def g3():
        R = ST['g']
        vals = (0.0, 1.0, 2.0)
        si = ST['si']
        if si > 0:
            img = arr(R.op('refract'))[:, :, :3]
            ST['sc'][vals[si - 1]] = float(np.abs(img - ST['opq'])[ST['mask']].mean())
            ST.setdefault('img', {})[vals[si - 1]] = img
            R.op('out1').save(BT + '/out/m84_scale_%g.jpg' % vals[si - 1])
        if si >= len(vals):
            d = ST['sc']
            # 0: (almost) the straight view; 2: a different image from 1 (a larger shift can carry part of the
            # image off screen, so the difference to the straight view need not grow monotonically)
            d12 = float(np.abs(ST['img'][2.0] - ST['img'][1.0])[ST['mask']].mean())
            check('REFR.SCALE 0 = straight view', d[0.0] < 0.3 * d[1.0],
                  'mean |refract - straight| at 0 / 1 / 2: %.4f / %.4f / %.4f' % (d[0.0], d[1.0], d[2.0]))
            check('REFR.SCALE 2 bends differently from 1', d12 > 0.05, 'mean |img2 - img1| %.4f' % d12)
            R.par.Refr0scale = 1.0
            R.par.Refr0absorbsrc = 'custom'
            R.par.Refr0absorbcolorr, R.par.Refr0absorbcolorg, R.par.Refr0absorbcolorb = 1.0, 0.15, 0.15
            R.par.Refr0absorb = 0.5
            step(g4, 30); return
        R.par.Refr0scale = vals[si]
        ST['si'] = si + 1
        step(g3, 30)
    def g4():
        R = ST['g']
        img = arr(R.op('refract'))[:, :, :3]
        R.op('out1').save(BT + '/out/m84_absorbcolor.jpg')
        m = ST['mask']
        rr = img[m][:, 0].mean(); gg = img[m][:, 1].mean()
        tb = arr(R.op('tgbuf0'))[:, :, :3][m].mean(0)
        check('REFR.ABSORBCOLOR transmitted light turns red', rr > 1.6 * gg, 'r %.3f g %.3f' % (rr, gg))
        check('REFR.ABSORBCOLOR surface colour stays white', float(tb.min()) > 0.9, 'base %s' % np.round(tb, 3))
        KEEPLIST[:] = [p for p in KEEPLIST if not p.startswith(T.op('glass').path)]
        T.store('keep', list(KEEPLIST))
        T.op('glass').destroy()
        step(h1, 5)

    # ------------------------------------------------------------ part 5: hashed alpha test
    def h1():
        S = scene('hash')
        m = pbr(S, 'm_leaf', (0.2, 0.7, 0.2), 0.5, alpha=0.45)
        m.par.alphatest = True; m.par.alphathreshold = 0.5
        g, s = geo(S, 'leaf', gridSOP, m, (0, 0, 0))
        s.par.sizex = s.par.sizey = 1.5
        c = S.create(cameraCOMP, 'cam1'); c.par.tz = 3.0; c.par.fov = 40
        R = btdr(S)
        R.par.Raytracing = False
        ST['h'] = R
        T.store('keep', list(KEEPLIST))
        step(h2, 40)
    def h2():
        R = ST['h']
        e = errs(R)
        check('hashed alpha: no errors', not e, str(e[:3]))
        cov = ((arr(R.op('gbuf1'))[:, :, :3] ** 2).sum(-1) > 0.25).mean()
        ST['cov_t'] = float(cov)
        R.par.Alphatestmode = 'hashed'
        step(h3, 20)
    def h3():
        R = ST['h']
        g1_ = (arr(R.op('gbuf1'))[:, :, :3] ** 2).sum(-1) > 0.25
        R.op('out1').save(BT + '/out/m84_hashed.jpg')
        # the plane covers a known box on screen: the coverage inside it
        ys, xs = np.nonzero(g1_)
        check('GBUF.HASHALPHA threshold mode cuts the 45 % plane', ST['cov_t'] < 0.001, 'coverage %.4f' % ST['cov_t'])
        if xs.size:
            box = g1_[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            check('GBUF.HASHALPHA hashed keeps ~45 %', 0.3 < box.mean() < 0.6, 'kept %.3f of the plane' % box.mean())
        else:
            check('GBUF.HASHALPHA hashed keeps ~45 %', False, 'nothing drawn')
        step(lambda: finish(), 2)

    step(e1, 60)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
