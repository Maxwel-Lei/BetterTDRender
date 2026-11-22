# [BTDR:FILE.TEST.M93] m93_tests.py — 0.9.3: instanced geometry in the ray-tracing proxy (CHOP and table DAT instances).
# Run: exec(open(project.folder + '/btdr/tests/m93_tests.py', encoding='utf-8').read())
# Result: btdr/out/m93_tests.txt (first line STATUS PASS / FAIL), btdr/out/m93_*.jpg; the test network is removed.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm93_test'
W, H = 640, 360
NI = 6
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m93_tests.txt', 'w', encoding='utf-8').write(
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
def pts(o):
    return np.array([o.point('P', i) for i in range(o.numPoints())]) if o is not None and o.numPoints() else np.zeros((0, 3))
ST = {}
try:
    open(BT + '/out/m93_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1800
    mm = T.create(pbrMAT, 'm_mirror'); mm.par.basecolorr = mm.par.basecolorg = mm.par.basecolorb = 0.9
    mm.par.metallic = 1.0; mm.par.roughness = 0.05
    mr = T.create(pbrMAT, 'm_red'); mr.par.basecolorr = 0.9; mr.par.basecolorg = mr.par.basecolorb = 0.05; mr.par.roughness = 0.6
    mr.par.emitr = 1.0; mr.par.emitg = mr.par.emitb = 0.0
    geo('floor', gridSOP, (0, 0, 0), mm, sizex=12, sizey=12, orient='zx')
    # CHOP instances: NI pillars along x, rotated and stretched
    cb = T.create(textDAT, 'ich_cb')
    cb.text = ("import numpy as np\ndef onCook(scriptOp):\n    scriptOp.clear(); n = %d; scriptOp.numSamples = n\n"
               "    for k, v in (('tx', np.linspace(-2.5, 2.5, n)), ('tz', np.full(n, -1.0)), ('ry', np.arange(n) * 15.0), ('sy', 1.0 + 0.2 * np.arange(n))):\n"
               "        scriptOp.appendChan(k).copyNumpyArray(v.astype(np.float32))\n") % NI
    ich = T.create(scriptCHOP, 'ich'); ich.par.callbacks = cb
    pil = geo('pillars', boxSOP, (0, 0.6, 0), mr, sizex=0.4, sizey=1.2, sizez=0.4)
    pil.par.instancing = True; pil.par.instanceop = ich
    pil.par.instancetx = 'tx'; pil.par.instancetz = 'tz'; pil.par.instancery = 'ry'; pil.par.instancesy = 'sy'
    # table DAT instances: 4 small cubes
    tb = T.create(tableDAT, 'itab'); tb.clear(); tb.appendRow(['tx', 'ty', 'tz'])
    for x in (-1.5, -0.5, 0.5, 1.5): tb.appendRow([x, 0, 1.2])
    dots = geo('dots', boxSOP, (0, 0.15, 0), mr, sizex=0.3, sizey=0.3, sizez=0.3)
    dots.par.instancing = True; dots.par.instanceop = tb
    dots.par.instancetx = 'tx'; dots.par.instancety = 'ty'; dots.par.instancetz = 'tz'
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 1.6; cam.par.tz = 5.5; cam.par.rx = -14; cam.par.fov = 50
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -50; sun.par.ry = 30; sun.par.dimmer = 0.6
    sun.par.shadowtype = 'off'
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor pillars dots'; R.par.Lights = 'sun'
    R.par.Bloom = 0; R.par.Envintensity = 0.3; R.par.Ssr = False
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    def campos():
        return np.array([cam.worldTransform[0, 3], cam.worldTransform[1, 3], cam.worldTransform[2, 3]])
    def copies():
        out = {}
        for c in R.op('rtscene').findChildren(type=copyPOP):
            out[c.name] = c
        return out

    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        cps = copies()
        check('EXT.RTINST two instanced objects copied into the proxy', len(cps) == 2, str(sorted(cps)))
        pp = [pts(c) for c in sorted(cps.values(), key=lambda c: c.numPoints(), reverse=True)]
        if len(pp) == 2:
            a, b = pp
            # pillars: NI copies; points per copy from the single-instance proxy
            span = a[:, 0].max() - a[:, 0].min() if len(a) else 0
            hi = a[:, 1].max() if len(a) else 0
            # object space (before the Geometry COMP transform): first pillar x -2.7 (not rotated), last one rotated 75 deg:
            # half width 0.2 (cos 75 + sin 75) = 0.245 -> x span 5.445; its scale y 2 puts the top at 0.6 x 2 = 1.2
            check('CHOP instances: %d pillars, translate / rotate / scale applied' % NI,
                  len(a) % NI == 0 and abs(span - 5.445) < 0.01 and abs(hi - 1.2) < 0.01,
                  '%d points, x span %.3f, top %.3f' % (len(a), span, hi))
            check('table DAT instances: 4 cubes at z 1.2', len(b) % 4 == 0 and len(b) >= 32 and abs(b[:, 2].mean() - 1.2) < 0.02,
                  '%d points, mean z %.3f' % (len(b), b[:, 2].mean() if len(b) else 0))
        R.par.Debugview = 'rtrefl'
        step(s2, 90)
    def s2():
        ST['on'] = arr(R.op('out2'))[..., :3]
        R.op('out1').save(BT + '/out/m93_rtrefl.jpg')
        R.par.Rtmaxinstances = 0
        step(s3, 90)
    def s3():
        off = arr(R.op('out2'))[..., :3]
        p = arr(R.op('gbuf2'))[:, :, :3] + campos()
        # floor in front of the pillars, where they reflect
        mk = (np.abs(p[..., 1]) < 0.01) & (p[..., 2] > -0.95) & (p[..., 2] < 0.6) & (np.abs(p[..., 0]) < 2.8)
        on = ST['on']
        ron = float((on[mk][:, 0] - on[mk][:, 1]).mean()) if mk.any() else float('nan')
        rof = float((off[mk][:, 0] - off[mk][:, 1]).mean()) if mk.any() else float('nan')
        check('RT reflections see the instanced pillars (red - green on the floor)', ron > rof + 0.02,
              '%.4f vs %.4f with Max Instances 0 (%d px)' % (ron, rof, int(mk.sum())))
        cps = copies()
        check('Max Instances in Proxy 0: left out', len(cps) == 0, str(sorted(cps)))
        R.par.Rtmaxinstances = 3
        step(s4, 30)
    def s4():
        cps = copies()
        n = sorted(c.numPoints() for c in cps.values())
        tp = [o.numSamples for o in R.op('rtscene').findChildren(type=scriptCHOP)]
        check('Max Instances in Proxy 3: three copies each', sorted(tp) == [3, 3], 'instance samples %s, copy points %s' % (tp, n))
        R.par.Rtmaxinstances = 1024
        step(s5, 30)
    def s5():
        # instances change at run time: the proxy follows without Refresh
        tb.appendRow([2.5, 0, 1.2])
        step(s6, 10)
    def s6():
        tp = sorted(o.numSamples for o in R.op('rtscene').findChildren(type=scriptCHOP))
        check('a new table row shows up in the proxy', tp == [5, NI], str(tp))
        R.par.Debugview = 'final'
        step(finish, 2)
    step(s1, 120)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
