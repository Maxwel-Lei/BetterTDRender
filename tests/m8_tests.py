# [BTDR:FILE.TEST.M8] m8_tests.py — 0.8.0 subsurface scattering (docs/SUBSURFACE.md §7).
# Run: exec(open(project.folder + '/btdr/tests/m8_tests.py', encoding='utf-8').read())
# Result: btdr/out/m8_tests.txt (first line STATUS PASS / FAIL), btdr/out/m8_*.jpg; the test network is removed.
# Comparisons are made inside one frame (composite = before, sss_v = after): the shadows' per-frame noise would
# otherwise show up as differences.
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOG, FAILS = [], []
NAME = 'm8_test'
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m8_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t and not KEEP: t.destroy()
def errs(R):
    return [(c.name, c.errors().strip()[:80]) for c in R.findChildren() if c.valid and c.errors()]
def step(fn, frames):
    def wrapped():
        try:
            fn()
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    run("args[0]()", wrapped, delayFrames=frames)
def arr(o):
    o.cook(force=True)
    return np.array(o.numpyArray(delayed=False), dtype=np.float64)
def save(o, nm):
    o.save(BT + '/out/' + nm)
try:
    KEEP
except NameError:
    KEEP = False

try:
    open(BT + '/out/m8_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1000
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    o = op('/project1/%s/renderBTDR1/out1')\n"
                 "    if o: o.cook(force=True)\n    return\n" % NAME)
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True

    cam = T.create(cameraCOMP, 'cam1'); cam.par.tz = 4.2; cam.par.ty = 0.9; cam.par.rx = -8
    lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx = -35; lt.par.ry = 50; lt.par.shadowtype = 'off'
    def pbr(nm, c, rough=0.45):
        m = T.create(pbrMAT, nm); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
        m.par.metallic = 0; m.par.roughness = rough
        return m
    def geo(nm, sop, mat, t=(0, 0, 0), s=(1, 1, 1)):
        g = T.create(geometryCOMP, nm)
        for c in list(g.children): c.destroy()
        so = g.create(sop, 'shape'); so.render = so.display = True
        g.par.tx, g.par.ty, g.par.tz = t; g.par.sx, g.par.sy, g.par.sz = s
        g.par.material = mat
        return g, so
    floor, fs = geo('floor', boxSOP, pbr('m_floor', (0.5, 0.5, 0.5)), (0, -0.05, 0), (8, 0.1, 8))
    jade, js = geo('jade', sphereSOP, pbr('m_jade', (0.55, 0.85, 0.6), 0.3), (-1.15, 0.5, 0))
    skin, ss = geo('skin', sphereSOP, pbr('m_skin', (0.8, 0.55, 0.45), 0.5), (0, 0.5, 0))
    grey, gs = geo('grey', sphereSOP, pbr('m_grey', (0.6, 0.6, 0.6)), (1.15, 0.5, 0))
    for so in (js, ss, gs):
        so.par.type = 'geodesic'; so.par.freq = 24; so.par.radx = so.par.rady = so.par.radz = 0.5

    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False
    R.par.Camera = cam.path; R.par.Geometry = 'floor jade skin grey'; R.par.Lights = 'light1'
    R.par.Ssr = False; R.par.Ssgi = False; R.par.Raytracing = False; R.par.Antialias = 'none'
    R.par.Bloom = 0

    # ---- 1. no Subsurface slot: everything bypassed
    def s1():
        import re as _re
        _v = _re.search(r"^VERSION = '([^']+)'", open(BT + '/build.py', encoding='utf-8').read(), _re.M).group(1)
        check('version (same as build.py)', R.par.Version.eval() == _v, '%s / %s' % (R.par.Version.eval(), _v))
        check('uniform block 4 x 124 (0.9.1)', R.op('uniforms').numSamples == 124, str(R.op('uniforms').numSamples))
        check('no subsurface object: bypassed (1 colour buffer, sss_src on composite, no errors)',
              R.par.Ssscount.eval() == 0 and int(R.op('composite').par.numcolorbufs.eval()) == 1
              and R.op('sss_src').par.index.eval() == 0 and not errs(R),
              'count %d bufs %s idx %s errors %s' % (R.par.Ssscount.eval(), R.op('composite').par.numcolorbufs.eval(),
                                                     R.op('sss_src').par.index.eval(), errs(R)))
        save(R.op('out1'), 'm8_off.jpg')
        # two slots: jade, skin
        R.seq.Sss.numBlocks = 2
        R.par.Sss0geo = 'jade'; R.par.Sss0preset = 'jade'
        R.par.Sss1geo = 'skin'; R.par.Sss1preset = 'skin'
        R.par.Ssstransmission = False
        step(s2, 30)
    ST = {}

    # ---- 2. scattering: same-frame before / after
    def s2():
        p = R.par
        check('slots: 2 subsurface objects, presets applied',
              p.Ssscount.eval() == 2 and abs(p.Sss0radius.eval() - 0.020) < 1e-6 and abs(p.Sss1scatterr.eval() - 0.9) < 1e-6,
              'count %d r0 %.3f s1r %.2f' % (p.Ssscount.eval(), p.Sss0radius.eval(), p.Sss1scatterr.eval()))
        check('on: 2 colour buffers, sss_src on sss_v, no errors',
              int(R.op('composite').par.numcolorbufs.eval()) == 2 and R.op('sss_src').par.index.eval() == 1 and not errs(R), str(errs(R)))
        R.op('uniforms').cook(force=True)
        comp = R.op('composite'); comp.cook(force=True)
        before = arr(comp)[..., :3]; irr = arr(R.op('sss_irr'))
        R.op('sss_h').cook(force=True); after = arr(R.op('sss_v'))[..., :3]
        g3 = arr(R.op('gbuf3'))[..., 3]
        mask = irr[..., 3] > 0.5
        jm, sm = np.abs(irr[..., 3] - 1) < 0.1, np.abs(irr[..., 3] - 2) < 0.1
        check('profile ids in the G-Buffer and composite buffer 1', (np.abs(g3 - 2) < 0.01).sum() > 1000 and (np.abs(g3 - 3) < 0.01).sum() > 1000
              and jm.sum() > 1000 and sm.sum() > 1000, 'jade %d skin %d' % (jm.sum(), sm.sum()))
        check('no NaN / Inf', np.isfinite(after).all() and np.isfinite(irr).all())
        d = np.abs(after - before).max(axis=-1)
        check('pixels outside subsurface objects unchanged (no bleed)', d[~mask].max() == 0.0, 'max %.3g' % d[~mask].max())
        check('subsurface objects changed', d[mask].mean() > 1e-3, 'mean %.4f' % d[mask].mean())
        e0, e1 = before[mask].sum(), after[mask].sum()
        check('energy kept within 3%% on subsurface objects', abs(e1 / e0 - 1) < 0.03, 'ratio %.4f' % (e1 / e0))
        gx0 = np.abs(np.diff(before[..., 1], axis=1))[sm[:, 1:] & sm[:, :-1]]
        gx1 = np.abs(np.diff(after[..., 1], axis=1))[sm[:, 1:] & sm[:, :-1]]
        check('skin: shading softer (95th percentile gradient lower)', np.percentile(gx1, 95) < np.percentile(gx0, 95) * 0.9,
              '%.4f -> %.4f' % (np.percentile(gx0, 95), np.percentile(gx1, 95)))
        rel = lambda c: np.abs(after[..., c] - before[..., c])[sm].mean() / max(before[..., c][sm].mean(), 1e-6)
        check('skin: red scatters farther than blue', rel(0) > rel(2), 'rel change r %.4f b %.4f' % (rel(0), rel(2)))
        save(R.op('out1'), 'm8_on.jpg')
        ST['perf'] = []
        step(s3, 20)

    # ---- 3. performance (GPU) over a few frames
    def s3():
        for _ in range(1):
            ST['perf'].append([R.op(n).gpuCookTime for n in ('sss_h', 'sss_v', 'composite')])
        if len(ST['perf']) < 20:
            run("args[0]()", s3_more, delayFrames=1); return
        s3_done()
    def s3_more():
        try:
            s3()
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    def s3_done():
        m = np.median(np.array(ST['perf']), axis=0)
        cover = (arr(R.op('sss_irr'))[..., 3] > 0.5).mean()
        check('GPU: sss_h + sss_v < 0.5 ms (1080p, %.0f%% of the image)' % (cover * 100), m[0] + m[1] < 0.5,
              'sss_h %.3f sss_v %.3f composite %.3f ms' % tuple(m))
        # ---- 4. transmission: backlit slabs of two thicknesses, a leaf sheet
        for g in (jade, skin, grey): g.par.ty = -5
        t1, b1 = geo('slab_thin', boxSOP, T.op('m_skin'), (-0.6, 0.6, 0), (0.6, 0.8, 0.01))
        t2, b2 = geo('slab_thick', boxSOP, T.op('m_skin'), (0.3, 0.6, 0), (0.6, 0.8, 0.08))
        lf, ls = geo('leaf', gridSOP, pbr('m_leaf', (0.25, 0.5, 0.1)), (1.2, 0.6, 0))
        ls.par.orient = 'xy'; ls.par.sizex = 0.6; ls.par.sizey = 0.8
        R.par.Geometry = 'floor slab_* leaf'
        R.seq.Sss.numBlocks = 2
        R.par.Sss0geo = 'slab_*'; R.par.Sss0preset = 'skin'
        R.par.Sss1geo = 'leaf'; R.par.Sss1preset = 'leaf'
        R.par.Ssstransmission = True
        lt.par.rx = -20; lt.par.ry = 180            # from behind the slabs, towards the camera
        R.par.Debugview = 'ssstransmission'
        ST['slabs'] = (t1, t2, lf)
        step(s4, 40)
    def s4():
        R.op('uniforms').cook(force=True); R.op('composite').cook(force=True)
        a = arr(R.op('sss_irr'))
        tr = a[..., :3].mean(axis=-1)
        ids = a[..., 3]
        H, W = tr.shape
        leaf = tr[(np.abs(ids - 2) < 0.1)]
        # thin and thick slab are both profile 1: split by screen x (thin on the left half)
        xs = np.arange(W)[None, :].repeat(H, 0)
        m1 = (np.abs(ids - 1) < 0.1) & (xs < W * 0.5)
        m2 = (np.abs(ids - 1) < 0.1) & (xs >= W * 0.5)
        v1, v2 = (tr[m1].mean() if m1.any() else 0), (tr[m2].mean() if m2.any() else 0)
        check('transmission: backlit thin slab brighter than thick slab, both > 0', v1 > v2 * 1.5 and v1 > 1e-3,
              'thin %.4f thick %.4f (px %d / %d)' % (v1, v2, m1.sum(), m2.sum()))
        check('transmission: backlit leaf sheet > 0', leaf.size > 500 and leaf.mean() > 1e-3, 'leaf %.4f px %d' % (leaf.mean() if leaf.size else 0, leaf.size))
        save(R.op('out1'), 'm8_trans_debug.jpg')
        R.par.Debugview = 'final'
        lt.par.rx = -35; lt.par.ry = 0               # from the front: no transmission on the lit faces
        R.par.Debugview = 'ssstransmission'
        step(s5, 30)
    def s5():
        R.op('uniforms').cook(force=True); R.op('composite').cook(force=True)
        a = arr(R.op('sss_irr'))
        m = np.abs(a[..., 3] - 1) < 0.1
        v = a[..., :3].mean(axis=-1)[m].mean() if m.any() else 0
        check('transmission: front-lit slabs ~0', v < 1e-3, 'mean %.5f' % v)
        for nm in ('sssprofile', 'sssirradiance'):
            R.par.Debugview = nm
            R.op('debug').cook(force=True)
        check('debug views cook without errors', not errs(R), str(errs(R)))
        R.par.Debugview = 'final'
        R.par.Subsurface = False
        step(s6, 10)
    def s6():
        check('Subsurface off: bypassed', R.op('sss_src').par.index.eval() == 0 and int(R.op('composite').par.numcolorbufs.eval()) == 1, '')
        finish()

    step(s1, 90)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
