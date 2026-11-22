# [BTDR:FILE.TEST.M91] m91_tests.py — 0.9.1: spot-light shadows, local lights in the fog and at traced hits (probe GI),
# fog multiple scattering.
# Run: exec(open(project.folder + '/btdr/tests/m91_tests.py', encoding='utf-8').read())
# Result: btdr/out/m91_tests.txt (first line STATUS PASS / FAIL), btdr/out/m91_*.jpg; the test network is removed.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm91_test'
W, H = 640, 360
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m91_tests.txt', 'w', encoding='utf-8').write(
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
    open(BT + '/out/m91_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1400
    m = T.create(pbrMAT, 'm_w'); m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 0.7; m.par.roughness = 0.9
    geo('floor', gridSOP, (0, 0, 0), m, sizex=12, sizey=12, orient='zx')
    geo('wall', boxSOP, (0, 1.5, -3), m, sizex=8, sizey=3, sizez=0.2)
    geo('block', boxSOP, (1.0, 0.5, 0), m, sizex=0.6, sizey=1.0, sizez=0.6)
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 5; cam.par.tz = 6; cam.par.rx = -38; cam.par.fov = 60
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -70; sun.par.dimmer = 0.15
    sun.par.shadowtype = 'off'
    sp = T.create(lightCOMP, 'spot'); sp.par.lighttype = 'cone'; sp.par.tx, sp.par.ty, sp.par.tz = 0, 3, 0
    sp.par.rx = -90; sp.par.coneangle = 80; sp.par.conedelta = 5; sp.par.dimmer = 2.0; sp.par.shadowtype = 'soft2d'
    pt = T.create(lightCOMP, 'pt'); pt.par.lighttype = 'point'; pt.par.tx, pt.par.ty, pt.par.tz = -2, 1.2, -2.4
    pt.par.dimmer = 1.5; pt.par.attenuated = True; pt.par.attenuationstart = 0.3; pt.par.attenuationend = 3.0
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor wall block'; R.par.Lights = 'sun spot pt'
    R.par.Bloom = 0; R.par.Envintensity = 0.15
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    def world():
        p = arr(R.op('gbuf2'))[:, :, :3]
        return p + np.array([cam.worldTransform[0, 3], cam.worldTransform[1, 3], cam.worldTransform[2, 3]])
    def at(img, wp, x, y, z, r=0.25):
        mk = np.sqrt((wp[..., 0] - x) ** 2 + (wp[..., 1] - y) ** 2 + (wp[..., 2] - z) ** 2) < r
        return float(img[mk].mean()) if mk.any() else float('nan')
    def lum(o='composite'):
        return arr(R.op(o))[:, :, :3].mean(-1)

    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        check('spot shadow assigned', R.fetch('llshadow', {}) == {sp.path: 0} and R.op('llsw0').par.index.eval() == 1,
              str(R.fetch('llshadow', {})))
        img = lum(); wp = world(); ST['wp'] = wp
        R.op('out1').save(BT + '/out/m91_shadow.jpg')
        # spot straight down at (0, 3, 0), block x 0.7..1.3, 1 high: its shadow on the floor spans x 1.3..1.95
        inshadow = at(img, wp, 1.62, 0, 0.0, 0.12)
        open_ = at(img, wp, 1.62, 0, 1.0, 0.12)
        check('LIGHT.LLSHADOW the block shadows the spot light', inshadow < 0.6 * open_, 'shadow %.3f, open %.3f' % (inshadow, open_))
        R.par.Localshadows = 0
        R.Refresh()
        step(s3, 30)
    def s3():
        img = lum(); wp = ST['wp']
        inshadow = at(img, wp, 1.62, 0, 0.0, 0.12); open_ = at(img, wp, 1.62, 0, 1.0, 0.12)
        check('Max Shadowed Spot Lights 0: no spot shadow', inshadow > 0.8 * open_ and R.op('llsw0').par.index.eval() == 0,
              'shadow %.3f, open %.3f' % (inshadow, open_))
        R.par.Localshadows = 2
        R.Refresh()
        # fog: local light glow, multiple scattering
        R.par.Fog = True; R.par.Fogdensity = 0.15; R.par.Fogmultiple = 0.0
        step(s4, 60)
    def s4():
        ST['fog_ms0'] = lum('out2')
        R.par.Locallights = False
        step(s5, 60)
    def s5():
        nofl = lum('out2')
        with_ = ST['fog_ms0']
        # the air around the point light: the upper left quarter of the picture, above the floor near the wall
        reg = (slice(int(H * 0.45), int(H * 0.8)), slice(int(W * 0.05), int(W * 0.4)))
        d = float(with_[reg].mean() - nofl[reg].mean())
        check('FOG.LOCAL local lights glow in the fog', d > 0.003, 'fog brighter by %.4f near the point light' % d)
        R.par.Locallights = True; R.par.Fogmultiple = 1.0
        step(s6, 60)
    def s6():
        ms1 = lum('out2')
        d = float(ms1.mean() - ST['fog_ms0'].mean())
        R.op('out1').save(BT + '/out/m91_fog.jpg')
        check('FOG.MULTI multiple scattering brightens the fog', d > 0.002, 'mean +%.4f' % d)
        R.par.Fog = False
        R.par.Debugview = 'rtgi'
        step(s7, 90)
    def s7():
        ST['gi_on'] = lum('out2')
        R.par.Locallights = False
        step(s8, 90)
    def s8():
        off = lum('out2')
        wp = ST['wp']
        # probe GI on the wall near the point light
        on, of = at(ST['gi_on'], wp, -2, 1.0, -2.9, 0.5), at(off, wp, -2, 1.0, -2.9, 0.5)
        if R.par.Raytracing.eval() and R.par.Rtavailable.eval():
            check('RT.LOCAL local lights reach the probe GI', on > of * 1.1 + 0.002, 'probe GI near the point light %.4f vs %.4f' % (on, of))
        else:
            check('RT.LOCAL skipped (no ray tracing)', True)
        R.par.Debugview = 'final'; R.par.Locallights = True
        step(finish, 2)
    step(s1, 90)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
