# [BTDR:FILE.TEST.M95] m95_tests.py — 0.9.5: depth of field Focus Method = Tracking (Focus Object).
# Run: exec(open(project.folder + '/btdr/tests/m95_tests.py', encoding='utf-8').read())
# Result: btdr/out/m95_tests.txt (first line STATUS PASS / FAIL), btdr/out/m95_*.jpg; the test network is removed.
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOG, FAILS = [], []
NAME = 'm95_test'
W, H = 640, 360
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m95_tests.txt', 'w', encoding='utf-8').write(
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
    open(BT + '/out/m95_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -2200
    tx = T.create(noiseTOP, 'tex'); tx.par.resolutionw = tx.par.resolutionh = 256; tx.par.period = 0.08; tx.par.mono = True
    m = T.create(pbrMAT, 'm'); m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 1; m.par.roughness = 0.8
    m.par.basecolormap = tx.path
    md = T.create(pbrMAT, 'md'); md.par.basecolorr = md.par.basecolorg = md.par.basecolorb = 0.3
    geo('floor', gridSOP, (0, 0, 0), md, sizex=30, sizey=30, orient='zx')
    # two textured boards facing the camera: near one left at 3 m, far one right at 10 m
    near = geo('near', boxSOP, (-0.6, 0.6, 3.0), m, sizex=1.2, sizey=1.2, sizez=0.05)
    far = geo('far', boxSOP, (2.6, 1.5, -4.0), m, sizex=3.6, sizey=3.0, sizez=0.05)
    tgt = T.create(nullCOMP, 'focus_target'); tgt.par.tx, tgt.par.ty, tgt.par.tz = -0.6, 0.6, 3.0
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 1.0; cam.par.tz = 6.0; cam.par.fov = 45
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -40; sun.par.ry = 20
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor near far'; R.par.Lights = 'sun'
    R.par.Bloom = 0; R.par.Dof = True; R.par.Fstop = 1.4; R.par.Dofmaxblur = 20; R.par.Focusdistance = 7.0
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    def sharp(img, x0, x1, y0, y1):
        g = img[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)].mean(-1)
        return float(np.abs(np.diff(g, axis=1)).mean() + np.abs(np.diff(g, axis=0)).mean())
    def regions():
        img = arr(R.op('out2'))[..., :3]
        return sharp(img, 0.20, 0.34, 0.40, 0.62), sharp(img, 0.66, 0.84, 0.45, 0.70)   # near board, far board
    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        R.par.Focusmethod = 'tracking'; R.par.Focusobject = 'focus_target'
        step(s2, 60)
    def s2():
        u = R.op('uniforms')
        check('UNI.FOCUSTRACK tracked distance = 3 (along the view axis)', abs(u[2][24] - 3.0) < 0.01 and abs(R.par.Focustracked.eval() - 3.0) < 0.01,
              'uDOF.z %.3f, Tracked Distance %.3f' % (u[2][24], R.par.Focustracked.eval()))
        n, f = regions(); ST['a'] = (n, f)
        R.op('out1').save(BT + '/out/m95_near.jpg')
        tgt.par.tx, tgt.par.ty, tgt.par.tz = 2.6, 1.5, -4.0          # move the target: no Refresh
        step(s3, 60)
    def s3():
        u = R.op('uniforms')
        n, f = regions()
        R.op('out1').save(BT + '/out/m95_far.jpg')
        # each board against itself (their textures differ in scale): sharper when the focus is on it
        n0, f0 = ST['a']
        check('the target moved to the far board: focus follows (no Refresh)', abs(u[2][24] - 10.0) < 0.01, 'uDOF.z %.3f' % u[2][24])
        check('each board is sharper when it is the focus object', n0 > 1.2 * n and f > 1.2 * f0,
              'near %.4f focused / %.4f not, far %.4f focused / %.4f not' % (n0, n, f, f0))
        R.par.Focusoffset = -7.0
        step(s4, 30)
    def s4():
        u = R.op('uniforms')
        check('Focus Offset shifts the tracked distance', abs(u[2][24] - 3.0) < 0.01, 'uDOF.z %.3f' % u[2][24])
        R.par.Focusmethod = 'manual'
        step(s5, 30)
    def s5():
        u = R.op('uniforms')
        check('Manual: back to Focus Distance', abs(u[2][24] - 7.0) < 0.01, 'uDOF.z %.3f' % u[2][24])
        R.par.Focusmethod = 'tracking'; R.par.Focusobject = ''
        step(s6, 30)
    def s6():
        u = R.op('uniforms')
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('Tracking without an object: Focus Distance, no errors', abs(u[2][24] - 7.0) < 0.01 and not e, 'uDOF.z %.3f %s' % (u[2][24], e[:2]))
        step(finish, 2)
    step(s1, 120)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
