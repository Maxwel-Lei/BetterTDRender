# [BTDR:FILE.TEST.M96] m96_tests.py — 0.9.6: anti-flicker (TAA static pixel stabilization, geometric specular AA).
# Run: exec(open(project.folder + '/btdr/tests/m96_tests.py', encoding='utf-8').read())   (BTDR_SRC to run elsewhere)
# Result: btdr/out/m96_tests.txt (first line STATUS PASS / FAIL); the test network is removed.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm96_test'
W, H = 640, 360
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m96_tests.txt', 'w', encoding='utf-8').write(
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
    open(BT + '/out/m96_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -2600
    m = T.create(pbrMAT, 'm'); m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 0.7; m.par.roughness = 0.35; m.par.metallic = 1.0
    md = T.create(pbrMAT, 'md'); md.par.basecolorr = md.par.basecolorg = md.par.basecolorb = 0.5; md.par.roughness = 0.9
    def geo(n, sop, t, mat, **kw):
        g = T.create(geometryCOMP, n)
        for c in list(g.children): c.destroy()
        s = g.create(sop, 's'); s.render = s.display = True
        for k, v in kw.items(): setattr(s.par, k, v)
        g.par.tx, g.par.ty, g.par.tz = t; g.par.material = mat
        return g
    geo('floor', gridSOP, (0, 0, 0), md, sizex=12, sizey=12, orient='zx')
    geo('wall', boxSOP, (0, 1.5, -2.5), md, sizex=8, sizey=3, sizez=0.2)
    # thin metal rods (a few mm wide at this distance: sub-pixel) and small glossy spheres: the shimmer cases
    rods = geo('rods', boxSOP, (0, 1.2, -1.0), m, sizex=0.012, sizey=2.0, sizez=0.012)
    rods.par.instancing = True
    tb = T.create(tableDAT, 'rpos'); tb.clear(); tb.appendRow(['tx', 'rz'])
    for i in range(40): tb.appendRow([-3.0 + i * 0.15, (i % 7 - 3) * 4.0])
    rods.par.instanceop = tb; rods.par.instancetx = 'tx'; rods.par.instancerz = 'rz'
    balls = geo('balls', sphereSOP, (0, 0.06, 0.5), m, radx=0.05, rady=0.05, radz=0.05, type='poly')
    balls.par.instancing = True
    tb2 = T.create(tableDAT, 'bpos'); tb2.clear(); tb2.appendRow(['tx', 'tz'])
    for i in range(30): tb2.appendRow([-2.5 + (i % 10) * 0.55, 0.5 + (i // 10) * 0.4])
    balls.par.instanceop = tb2; balls.par.instancetx = 'tx'; balls.par.instancetz = 'tz'
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 1.4; cam.par.tz = 6.5; cam.par.rx = -6; cam.par.fov = 45
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -45; sun.par.ry = 30; sun.par.dimmer = 1.5
    sun.par.shadowtype = 'off'
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor wall rods balls'; R.par.Lights = 'sun'; R.par.Bloom = 0
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    def lum():
        return arr(R.op('out2'))[..., :3].mean(-1)
    def flicker(tag, then):
        acc = []
        def g(i):
            acc.append(lum().astype(np.float32))
            if i < 31: step(lambda: g(i + 1), 1)
            else:
                A = np.stack(acc); mm = A.mean(0); s = A.std(0); rel = s / (mm + 2e-3)
                ST[tag] = float((rel > 0.05).mean()); then()
        g(0)
    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        u = R.op('uniforms')
        check('uniform: TAA static stabilization on by default', abs(u[3][20] - 1.0) < 1e-6, 'uTAA.w %.1f' % u[3][20])
        R.par.Taastatic = False
        step(lambda: flicker('off', s2), 90)
    def s2():
        R.par.Taastatic = True
        step(lambda: flicker('on', s3), 90)
    def s3():
        check('TAA.STATIC a still image shimmers less', ST['on'] < 0.6 * ST['off'] + 1e-4,
              'flickering pixels %.2f %% with, %.2f %% without' % (ST['on'] * 100, ST['off'] * 100))
        # responsiveness: the sun jumps 25 degrees, compare frame +12 with the converged image
        ST['mode'] = True
        sun.par.ry = 55
        step(s4, 12)
    def s4():
        ST['f12'] = lum()
        step(s5, 150)
    def s5():
        conv = lum()
        ST['err_on'] = float(np.abs(ST['f12'] - conv).mean() / (conv.mean() + 1e-6))
        R.par.Taastatic = False
        sun.par.ry = 30
        step(s6, 150)
    def s6():
        sun.par.ry = 55
        step(s7, 12)
    def s7():
        ST['f12off'] = lum()
        step(s8, 150)
    def s8():
        conv = lum()
        eoff = float(np.abs(ST['f12off'] - conv).mean() / (conv.mean() + 1e-6))
        check('TAA.STATIC a lighting change still settles quickly (12 frames after the sun moved)',
              ST['err_on'] < max(2.0 * eoff, 0.03), 'error %.4f with, %.4f without' % (ST['err_on'], eoff))
        R.par.Taastatic = True
        # specular AA: roughness in the G-Buffer grows on the small spheres, flat walls are unchanged
        R.par.Specularaa = False
        step(s9, 30)
    def s9():
        ST['g1off'] = arr(R.op('gbuf1'))
        R.par.Specularaa = True
        step(s10, 30)
    def s10():
        g1 = arr(R.op('gbuf1')); g0 = ST['g1off']
        p = arr(R.op('gbuf2'))[..., :3]
        cpos = np.array([cam.worldTransform[0, 3], cam.worldTransform[1, 3], cam.worldTransform[2, 3]])
        wp = p + cpos
        ballm = (np.abs(p).sum(-1) > 0) & (wp[..., 1] > 0.015) & (wp[..., 1] < 0.12) & (wp[..., 2] > 0.3)
        wallm = (np.abs(p).sum(-1) > 0) & (np.abs(wp[..., 2] + 2.4) < 0.02) & (wp[..., 1] > 2.0)
        rb = float((g1[ballm][:, 3] - g0[ballm][:, 3]).mean()) if ballm.any() else float('nan')
        # the wall's face (95th percentile): its edges, where the normal turns from the front to the top face, do change
        rw = float(np.percentile(np.abs(g1[wallm][:, 3] - g0[wallm][:, 3]), 95)) if wallm.any() else float('nan')
        check('GBUF.SPECAA roughness grows on small curved surfaces, flat walls unchanged', rb > 0.01 and rw < 1e-3,
              'spheres +%.3f, wall change (95th percentile) %.5f (%d / %d px)' % (rb, rw, int(ballm.sum()), int(wallm.sum())))
        step(finish, 2)
    step(s1, 120)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
