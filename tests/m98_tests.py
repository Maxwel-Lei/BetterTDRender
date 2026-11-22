# [BTDR:FILE.TEST.M98] m98_tests.py — 0.9.8: specular occlusion from the probe GI (COMP.SPECOCC).
# Run: exec(open(project.folder + '/btdr/tests/m98_tests.py', encoding='utf-8').read())   (BTDR_SRC to run elsewhere)
# Result: btdr/out/m98_tests.txt (first line STATUS PASS / FAIL); the test network is removed.
# A closed room with one small window: indoors the probes see almost no sky, so the environment reflection on a rough
# wall must drop with Specular Occlusion on; outdoors (open ground) it must not change.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')
LOG, FAILS = [], []
NAME = 'm98_test'
W, H = 480, 270
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m98_tests.txt', 'w', encoding='utf-8').write(
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
def lum(o):
    o.cook(force=True)
    a = np.array(o.numpyArray(delayed=False), dtype=np.float64)[..., :3]
    return a @ np.array([0.2126, 0.7152, 0.0722])
def centre(L):
    h, w = L.shape
    return float(L[int(h * 0.3):int(h * 0.7), int(w * 0.3):int(w * 0.7)].mean())
ST = {}
try:
    open(BT + '/out/m98_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -2800
    md = T.create(pbrMAT, 'md'); md.par.basecolorr = md.par.basecolorg = md.par.basecolorb = 0.5; md.par.roughness = 0.85
    def geo(n, t, s):
        g = T.create(geometryCOMP, n)
        for c in list(g.children): c.destroy()
        b = g.create(boxSOP, 's'); b.render = b.display = True
        b.par.sizex, b.par.sizey, b.par.sizez = s
        g.par.tx, g.par.ty, g.par.tz = t; g.par.material = md
        return g
    geo('ground', (0, -0.1, 0), (60, 0.2, 60))
    # room 6 x 3 x 6 m, walls 0.2 m; a 0.6 m window in the left wall
    geo('roof', (0, 3.1, 0), (6.4, 0.2, 6.4))
    geo('back', (0, 1.5, -3.1), (6.4, 3.2, 0.2))
    geo('front', (0, 1.5, 3.1), (6.4, 3.2, 0.2))
    geo('right', (3.1, 1.5, 0), (0.2, 3.2, 6.4))
    geo('leftlo', (-3.1, 0.9, 0), (0.2, 2.0, 6.4))
    geo('lefthi', (-3.1, 2.75, 0), (0.2, 0.7, 6.4))
    geo('leftwin', (-3.1, 2.15, 1.8), (0.2, 0.6, 2.8))
    geo('leftwin2', (-3.1, 2.15, -1.8), (0.2, 0.6, 2.8))
    cam = T.create(cameraCOMP, 'cam1'); cam.par.tx, cam.par.ty, cam.par.tz = 0, 1.5, 2.4; cam.par.fov = 60
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -45; sun.par.ry = 30; sun.par.shadowtype = 'off'
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Antialias = 'none'; R.par.Ambientocclusion = False; R.par.Ssgi = False
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('renderBTDR1/out1').cook(force=True)\n    return\n"
    keep.par.framestart = True; keep.par.active = True
    def s1():
        R.par.Camera = 'cam1'; R.par.Geometry = '*'; R.par.Lights = 'sun'
        R.par.Specocclusion = 0.0
        step(s2, 150)
    def s2():
        ST['in0'] = centre(lum(R.op('composite')))
        R.par.Specocclusion = 1.0
        step(s3, 30)
    def s3():
        ub = R.op('uniforms')
        ST['in1'] = centre(lum(R.op('composite')))
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        check('uniform: uAmb.w = Specular Occlusion', abs(ub[3][40] - 1.0) < 1e-6, 'uAmb.w %.2f' % ub[3][40])
        check('COMP.SPECOCC indoors the rough wall loses its open-sky reflection', ST['in1'] < 0.95 * ST['in0'],
              'wall %.4f with, %.4f without' % (ST['in1'], ST['in0']))
        # outdoors: look at the open ground away from the room
        cam.par.tx, cam.par.ty, cam.par.tz = 0, 2.5, 22; cam.par.rx = -25
        R.par.Specocclusion = 0.0
        step(s4, 60)
    def s4():
        ST['out0'] = centre(lum(R.op('composite')))
        R.par.Specocclusion = 1.0
        step(s5, 30)
    def s5():
        o1 = centre(lum(R.op('composite')))
        check('COMP.SPECOCC open ground outdoors is unchanged', abs(o1 - ST['out0']) < 0.02 * max(ST['out0'], 1e-4),
              'ground %.4f with, %.4f without' % (o1, ST['out0']))
        finish()
    step(s1, 5)
except Exception:
    LOG.append('FAIL  setup\n' + traceback.format_exc()); FAILS.append('setup'); finish()
