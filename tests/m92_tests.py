# [BTDR:FILE.TEST.M92] m92_tests.py — 0.9.2: object motion vectors (velocity pass, TAA reprojection, motion blur).
# Run: exec(open(project.folder + '/btdr/tests/m92_tests.py', encoding='utf-8').read())
# Result: btdr/out/m92_tests.txt (first line STATUS PASS / FAIL), btdr/out/m92_*.jpg; the test network is removed.
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOG, FAILS = [], []
NAME = 'm92_test'
W, H = 640, 360
SPEED = 0.04                     # scene units per frame
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m92_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t: t.destroy()
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
def geo(n, sop, t, mat, **kw):
    g = T.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    s = g.create(sop, 's'); s.render = s.display = True
    for k, v in kw.items(): setattr(s.par, k, v)
    g.par.tx, g.par.ty, g.par.tz = t; g.par.material = mat
    return g
ST = {}
try:
    open(BT + '/out/m92_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1600
    md = T.create(pbrMAT, 'm_dark'); md.par.basecolorr = md.par.basecolorg = md.par.basecolorb = 0.05; md.par.roughness = 1
    # a noise texture on the mover's top, to see whether TAA keeps it sharp while it moves
    mb = T.create(pbrMAT, 'm_box'); mb.par.basecolorr = mb.par.basecolorg = mb.par.basecolorb = 1; mb.par.roughness = 1
    tx = T.create(noiseTOP, 'tex'); tx.par.resolutionw = tx.par.resolutionh = 64; tx.par.period = 0.15; tx.par.mono = True
    tx.par.amp = 1.0; tx.par.offset = 0.5
    mb.par.basecolormap = tx.path
    geo('floor', gridSOP, (0, 0, 0), md, sizex=12, sizey=12, orient='zx')
    mover = geo('mover', boxSOP, (0, 0.25, 0), mb, sizex=1.0, sizey=0.5, sizez=1.0)
    mover.par.tx.expr = "((absTime.frame * %g) %% 3.0) - 1.5" % SPEED
    still = geo('still', boxSOP, (0, 0.25, 2.0), mb, sizex=0.6, sizey=0.5, sizez=0.6)
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 6; cam.par.tz = 2.5; cam.par.rx = -65; cam.par.fov = 45
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -80; sun.par.dimmer = 1.0
    sun.par.shadowtype = 'off'
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor mover still'; R.par.Lights = 'sun'
    R.par.Bloom = 0; R.par.Envintensity = 0.3; R.par.Ambientocclusion = False; R.par.Ssgi = False; R.par.Ssr = False
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    def campos():
        return np.array([cam.worldTransform[0, 3], cam.worldTransform[1, 3], cam.worldTransform[2, 3]])
    def mover_mask():
        p = arr(R.op('gbuf2'))[:, :, :3] + campos()
        x = mover.par.tx.eval()
        return (np.abs(p[..., 0] - x) < 0.4) & (np.abs(p[..., 2]) < 0.4) & (p[..., 1] > 0.45)
    def lum(o):
        return arr(R.op(o))[:, :, :3].mean(-1)

    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        vel = R.op('velocity')
        geo_ = vel.par.geometry.val
        check('UNI.VELOCITY only the mover is drawn', geo_ == 'scene/v1' and R.op('vel_src').par.index.eval() == 1,
              '%r, Moving Objects %s' % (geo_, R.par.Movingcount.eval()))
        v = arr(vel)
        mk = v[..., 3] > 0
        dx = float(np.median(v[mk][:, 0])) if mk.any() else float('nan')
        dyz = float(np.abs(v[mk][:, 1:3]).max()) if mk.any() else float('nan')
        # whole frames since the last render: TD can drop frames while the test loads (0.52 = 13 frames was seen once)
        nf = max(1, int(round(dx / SPEED))) if dx == dx else 1
        check('VEL.OBJECT displacement = %.2f per frame along x' % SPEED, abs(dx - nf * SPEED) < 0.004 and dyz < 0.004 and nf <= 20,
              'median dx %.4f, max |dy|,|dz| %.4f, %d px' % (dx, dyz, int(mk.sum())))
        # sharpness of the noise texture on the moving box: gradient energy inside the box, TAA with / without motion vectors
        img = lum('out2'); m = mover_mask()
        g = np.abs(np.diff(img, axis=1))[m[:, 1:] & m[:, :-1]].mean()
        ST['g_on'] = float(g)
        R.op('out1').save(BT + '/out/m92_on.jpg')
        R.par.Objectmotion = False
        step(s2, 40)
    def s2():
        img = lum('out2'); m = mover_mask()
        g = float(np.abs(np.diff(img, axis=1))[m[:, 1:] & m[:, :-1]].mean())
        R.op('out1').save(BT + '/out/m92_off.jpg')
        check('UNI.VELOCITY off: nothing drawn', R.op('vel_src').par.index.eval() == 0 and R.par.Movingcount.eval() == 'off',
              R.par.Movingcount.eval())
        check('TAA.VELDILATE a moving textured box stays sharper with motion vectors', ST['g_on'] > 1.15 * g,
              'gradient %.4f vs %.4f without' % (ST['g_on'], g))
        R.par.Objectmotion = True
        R.par.Motionblur = True; R.par.Shutter = 1.0; R.par.Mbmaxblur = 64
        step(s3, 40)
    def s3():
        img = lum('out2')
        ST['mb_on'] = img
        R.op('out1').save(BT + '/out/m92_mblur.jpg')
        R.par.Objectmotion = False
        step(s4, 40)
    def s4():
        off = lum('out2')
        # blur along x: compare horizontal vs vertical gradients over the whole picture (only the mover moves)
        def ratio(img):
            gx = np.abs(np.diff(img, axis=1)).sum(); gy = np.abs(np.diff(img, axis=0)).sum()
            return float(gx / max(gy, 1e-6))
        ron, roff = ratio(ST['mb_on']), ratio(off)
        check('MB.OBJECT the moving box blurs along its motion', ron < 0.85 * roff, 'x / y gradient ratio %.3f vs %.3f without' % (ron, roff))
        R.par.Motionblur = False; R.par.Objectmotion = True
        mover.par.tx.expr = ''; mover.par.tx = 0.0
        step(s5, 10)
    def s5():
        ST['vc'] = R.op('velocity').cookFrame
        step(s6, 20)
    def s6():
        check('static scene: velocity pass off', R.op('vel_src').par.index.eval() == 0 and R.op('velocity').cookFrame == ST['vc'],
              'Moving Objects %s, cookFrame %s -> %s' % (R.par.Movingcount.eval(), ST['vc'], R.op('velocity').cookFrame))
        # POP geometry moving with its Geometry COMP (the velocity material declares PartVel / v: must compile on POPs)
        pg = T.create(geometryCOMP, 'popmover')
        for c in list(pg.children): c.destroy()
        bp = pg.create(boxPOP, 's'); bp.render = bp.display = True
        pg.par.ty = 0.25; pg.par.tz = -1.5; pg.par.material = mb
        pg.par.tx.expr = "((absTime.frame * %g) %% 3.0) - 1.5" % SPEED
        R.par.Geometry = 'floor mover still popmover'
        step(s7, 60)
    def s7():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        v = arr(R.op('velocity')); mk = v[..., 3] > 0
        dx = float(np.median(v[mk][:, 0])) if mk.any() else float('nan')
        nf = max(1, int(round(dx / SPEED))) if dx == dx else 1
        check('VEL.OBJECT a POP box moves too', not e and R.par.Movingcount.eval().startswith('1 of 4') and abs(dx - nf * SPEED) < 0.004,
              'errors %s, Moving Objects %s, median dx %.4f' % (e[:2], R.par.Movingcount.eval(), dx))
        step(finish, 2)
    step(s1, 120)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
