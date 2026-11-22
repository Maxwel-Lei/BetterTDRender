# [BTDR:FILE.TEST.M5] m5_acceptance.py — the M5 acceptance check, done by script: start from an empty network,
# follow the user guide's quick start (§2) step by step with native operators only, and check the result.
# Run: exec(open(project.folder + '/btdr/tests/m5_acceptance.py', encoding='utf-8').read())
# Result: btdr/out/m5_acceptance.txt (first line STATUS PASS / FAIL); the test network is removed afterwards.
import traceback, time
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m5_acceptance.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    if op('/project1/m5_accept'): op('/project1/m5_accept').destroy()
try:
    P = op('/project1')
    if P.op('m5_accept'): P.op('m5_accept').destroy()
    N = P.create(baseCOMP, 'm5_accept'); N.nodeX, N.nodeY = 2200, -600     # stands in for an empty project
    t0 = time.perf_counter()
    # quick start step 1: a camera, a distant light, a Geometry COMP (it comes with a torus) with a PBR MAT
    cam = N.create(cameraCOMP, 'cam1'); cam.par.tz = 5
    lt = N.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx = -45; lt.par.ry = 30
    g = N.create(geometryCOMP, 'geo1')
    m = N.create(pbrMAT, 'pbr1'); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = 0.8, 0.3, 0.1
    g.par.material = m
    # step 2: drop BTDR.tox in (as the Palette does); no parameter is filled in
    R = N.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    o = N.create(nullTOP, 'OUT'); R.outputConnectors[0].connect(o)
    keep = N.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    o = op('/project1/m5_accept/OUT')\n    if o: o.cook(force=True)\n    return\n"
    keep.par.framestart = True; keep.par.active = True
    N.store('t0', t0)
    def _check():
        try:
            st = R.fetch('status', {}) or {}
            check('drop in: refresh found camera, light, geometry with no parameter filled in',
                  st.get('camera', '').endswith('/cam1') and st.get('light', '').endswith('/light1') and st.get('mirrored') == 1,
                  'status %r' % R.par.Status.eval())
            check('no warnings, no errors', not st.get('warnings') and not [x for x in R.findChildren() if x.errors()],
                  repr(st.get('warnings')))
            a = o.numpyArray()[..., :3].astype(np.float64)
            check('picture: finite, not empty, object lit', np.isfinite(a).all() and a.std() > 0.02 and a.max() > 0.3,
                  'mean %.3f std %.3f max %.3f' % (a.mean(), a.std(), a.max()))
            check('ray tracing available and on', R.par.Rtavailable.eval() and R.par.Raytracing.eval())
            # BUILD.AEDEFAULT (0.9.7): auto exposure on out of the box, like UE5
            check('auto exposure on by default', bool(R.par.Autoexposure.eval()) and R.op('ae_src').par.index.eval() == 1,
                  'Autoexposure %s, ae_src %s' % (R.par.Autoexposure.eval(), R.op('ae_src').par.index.eval()))
            import re as _re
            _v = _re.search(r"^VERSION = '([^']+)'", open(BT + '/build.py', encoding='utf-8').read(), _re.M).group(1)
            check('version (same as build.py)', R.par.Version.eval() == _v, '%s / %s' % (R.par.Version.eval(), _v))
            o.save(BT + '/out/m5_acceptance.jpg')
            # [BTDR:TEST.COLDSTART] the example dropped into a network nobody views: its first picture, cooked once after
            # 60 idle frames, must match a warmed-up picture (0.4.0: uninitialised Feedback TOPs showed as coloured sparkles)
            X = N.loadTox(BT + '/release/BTDR_Example.tox'); X.name = 'example'
            for c in X.findChildren(type=executeDAT, maxDepth=1):      # the example's own keep_cooking, not the renderer's DATs
                c.par.active = False
            # 0.7.4: the cover would hide the first picture, and its warm-up pulls the renderer; this test is about
            # the raw first picture of a renderer nobody pulled
            for r in X.findChildren(name='renderBTDR*', maxDepth=1):
                r.par.Cover = False
                r.op('cover_warm').par.active = False
                r.ext.BTDRExt.warmed = True
            # the example camera swings with absTime: freeze it, or the cold / warm pictures differ by camera motion
            # (0.5.1: the measured difference wandered between 0.01 and 0.07 for that reason alone)
            for cam in X.findChildren(type=cameraCOMP):
                for p in cam.pars('t[xyz]', 'r[xyz]'):
                    if p.mode != ParMode.CONSTANT:
                        v = p.eval(); p.mode = ParMode.CONSTANT; p.val = v
            N.store('X', X.path)
            run("args[0]()", _cold, delayFrames=60)
            return
        except Exception:
            check('acceptance', False, traceback.format_exc())
        finish()
    def _cold():
        try:
            X = op(N.fetch('X')); xo = X.op('OUT'); xo.cook(force=True)
            a = xo.numpyArray()[..., :3].astype(np.float64)
            N.store('cold', a)
            keep.text = "def onFrameStart(frame):\n    o = op('%s')\n    if o: o.cook(force=True)\n    return\n" % xo.path
            run("args[0]()", _warm, delayFrames=60)
        except Exception:
            check('cold start', False, traceback.format_exc()); finish()
    def _warm():
        try:
            X = op(N.fetch('X')); xo = X.op('OUT')
            b = xo.numpyArray()[..., :3].astype(np.float64); a = N.fetch('cold')
            hot = (a.max(-1) > 0.98).mean()
            check('cold start: first picture of an unviewed example is clean', np.isfinite(a).all() and np.abs(a - b).mean() < 0.08 and hot < 0.05,
                  'mean diff to warmed-up %.3f, saturated pixels %.1f%%' % (np.abs(a - b).mean(), hot * 100))
            LOG.append('time from empty network to last check: %.1f s (210 frames of waiting included)' % (time.perf_counter() - N.fetch('t0')))
        except Exception:
            check('cold start', False, traceback.format_exc())
        finish()
    N.store('check', _check)
    run("op('/project1/m5_accept').fetch('check')()", delayFrames=90)
    open(BT + '/out/m5_acceptance.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
except Exception:
    check('acceptance setup', False, traceback.format_exc()); finish()
