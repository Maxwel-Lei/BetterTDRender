# [BTDR:FILE.TEST.M90] m90_tests.py — 0.9.0 local lights (point, cone, extra distant), no shadows ([BTDR:LIGHT.LOCAL]).
# Run: exec(open(project.folder + '/btdr/tests/m90_tests.py', encoding='utf-8').read())
# Result: btdr/out/m90_tests.txt (first line STATUS PASS / FAIL), btdr/out/m90_*.jpg; the test network is removed.
# Floor points are picked from the G-Buffer position (world position within a radius), so the checks do not depend on
# the camera projection. Compared on `composite` (before TAA), so a parameter switch shows after a few frames.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm90_test'
W, H = 640, 360
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m90_tests.txt', 'w', encoding='utf-8').write(
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
ST = {}
try:
    open(BT + '/out/m90_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1400
    m = T.create(pbrMAT, 'm_floor'); m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 0.6; m.par.roughness = 0.9
    g = T.create(geometryCOMP, 'floor')
    for c in list(g.children): c.destroy()
    s = g.create(gridSOP, 's'); s.render = s.display = True; s.par.sizex = s.par.sizey = 12; s.par.orient = 'zx'
    g.par.material = m
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 6; cam.par.tz = 6; cam.par.rx = -45; cam.par.fov = 60
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -60; sun.par.dimmer = 0.3
    sun.par.shadowtype = 'off'
    pt = T.create(lightCOMP, 'pt'); pt.par.lighttype = 'point'; pt.par.tx, pt.par.ty, pt.par.tz = -2, 1, 0
    pt.par.attenuated = True; pt.par.attenuationstart = 0.5; pt.par.attenuationend = 3.0; pt.par.dimmer = 1.0
    sp = T.create(lightCOMP, 'spot'); sp.par.lighttype = 'cone'; sp.par.tx, sp.par.ty, sp.par.tz = 2.5, 3, 0
    sp.par.rx = -90; sp.par.coneangle = 30; sp.par.conedelta = 5; sp.par.dimmer = 2.0
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor'; R.par.Lights = 'sun'
    R.par.Raytracing = False; R.par.Ssgi = False; R.par.Ssr = False; R.par.Bloom = 0; R.par.Envintensity = 0.2
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R

    def world():
        p = arr(R.op('gbuf2'))[:, :, :3]
        c = np.array([cam.worldTransform[0, 3], cam.worldTransform[1, 3], cam.worldTransform[2, 3]])
        return p + c
    def at(img, wp, x, z, r=0.3):
        d = np.sqrt((wp[..., 0] - x) ** 2 + (wp[..., 2] - z) ** 2)
        mk = d < r
        return float(img[mk].mean()) if mk.any() else float('nan')
    def lum():
        return arr(R.op('composite'))[:, :, :3].mean(-1)

    def s1():
        ST['wp'] = world()
        ST['sun_only'] = lum()
        check('sun only: count readout', R.par.Lightcount.eval().startswith('1 main, 0 point'), R.par.Lightcount.eval())
        R.par.Lights = 'sun pt spot'
        step(s2, 30)
    def s2():
        img = lum(); wp = ST['wp']; base = ST['sun_only']
        R.op('out1').save(BT + '/out/m90_lights.jpg')
        e = [(c.name, c.errors()[:60]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        check('count readout', R.par.Lightcount.eval() == '1 main, 1 point, 1 cone, 0 distant', R.par.Lightcount.eval())
        check('LIGHT.LOCAL finite', bool(np.isfinite(img).all()))
        under = at(img, wp, -2, 0) - at(base, wp, -2, 0)
        dl = np.sqrt((wp[..., 0] + 2) ** 2 + (wp[..., 1] - 1) ** 2 + wp[..., 2] ** 2)
        ring = (dl > 3.3) & (dl < 4.0) & (np.abs(wp[..., 0] - 2.5) > 2.0)   # 3.3-4 m from the light (End = 3), away from the cone
        far = float((img - base)[ring].mean()) if ring.any() else float('nan')
        check('point light brightens the floor under it', under > 0.08, 'added %.3f' % under)
        check('point light: nothing beyond Attenuation End', abs(far) < 0.01, 'added %.4f at 3.3-4 m' % far)
        inside = at(img, wp, 2.5, 0) - at(base, wp, 2.5, 0)
        outside = at(img, wp, 2.5, 2.2) - at(base, wp, 2.5, 2.2)
        check('cone light: inside the cone, not outside', inside > 0.2 and outside < 0.05 * inside,
              'inside %.3f, outside %.4f' % (inside, outside))
        ST['img2'] = img
        pt.par.tx = 0                                  # move: picked up every frame, no Refresh
        step(s3, 20)
    def s3():
        img = lum(); wp = ST['wp']; base = ST['sun_only']
        a0 = at(img, wp, 0, 0) - at(base, wp, 0, 0)
        a1 = at(img, wp, -2, 0) - at(base, wp, -2, 0)
        check('moving the point light follows without a Refresh', a0 > 0.08 and a1 < 0.5 * a0, 'new spot %.3f, old spot %.3f' % (a0, a1))
        R.par.Locallights = False
        step(s4, 20)
    def s4():
        d = float(np.abs(lum() - ST['sun_only']).mean())      # mean: screen-space AO is noisy frame to frame
        check('Local Lights off = sun only', d < 2e-3, 'mean |diff| %.6f' % d)
        R.par.Locallights = True
        R.par.Localfalloff = 'physical'
        pt.par.tx = -2
        step(s5, 20)
    def s5():
        img = lum(); wp = ST['wp']; base = ST['sun_only']
        n1 = at(img, wp, -2, 0) - at(base, wp, -2, 0)        # 1 m below the light
        n2 = at(img, wp, -2, 1.7) - at(base, wp, -2, 1.7)    # about 2 m away, at a grazing angle
        check('physical falloff: falls with distance, nothing cut off', n1 > 3 * n2 > 0, 'at 1 m %.3f, at ~2 m %.3f' % (n1, n2))
        R.par.Localfalloff = 'light'
        R.par.Lights = 'pt spot'                              # only local lights: no sun
        step(s6, 30)
    def s6():
        img = lum(); wp = ST['wp']
        check('only local lights: no main light', 'no main' in R.par.Lightcount.eval() and R.op('uniforms')[3][10] == 0.0,
              '%s / sun intensity %.3f' % (R.par.Lightcount.eval(), R.op('uniforms')[3][10]))
        far, far0 = at(img, wp, -4, -4), at(ST['sun_only'], wp, -4, -4)
        check('only local lights: the sun is gone from the far floor', far < 0.7 * far0, 'far floor %.4f (with sun %.4f)' % (far, far0))
        step(finish, 2)
    step(s1, 60)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
