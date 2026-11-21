# [BTDR:FILE.TEST.M6] m6_tests.py — M6a transparency checks on the m6_scene test scene ([BTDR:TEST.M6]).
# Run: exec(open(project.folder + '/btdr/tests/m6_tests.py', encoding='utf-8').read())
# Result: btdr/out/m6_tests.txt, first line STATUS PASS / FAIL. Builds /project1/m6_test (tests/m6_scene.py), removes it.
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOGF = BT + '/out/m6_tests.txt'
LOG, FAILS = [], []
def check(name, ok, info=''):
    LOG.append('%s %s %s' % ('PASS' if ok else 'FAIL', name, info))
    if not ok: FAILS.append(name)
def finish():
    open(LOGF, 'w', encoding='utf-8').write('\n'.join(['STATUS ' + ('PASS' if not FAILS else 'FAIL')] + LOG))
    if op('/project1/m6_test'): op('/project1/m6_test').destroy()

M6_SHOT = None
exec(open(BT + '/tests/m6_scene.py', encoding='utf-8').read())
R = op('/project1/m6_test/renderBTDR1')

def px(top):
    a = top.numpyArray(delayed=False)
    return np.asarray(a, dtype=np.float32)

def step1():
    try:
        check('slots resolved', R.par.Transcount.eval() == 5, 'transcount %s' % R.par.Transcount.eval())
        sc = R.op('scene')
        check('refractive mirrors are t*', len(sc.findChildren(name='t*', depth=1)) == 5 and not sc.op('g0') is None)
        check('switches on', R.op('trans_src').par.index.eval() == 1 and R.op('tpos_src').par.index.eval() == 1)
        errs = [o.path for o in R.findChildren() if o.errors()]
        check('no errors', not errs, ' '.join(errs[:5]))
        img = px(R.op('refract'))
        check('refract finite', bool(np.isfinite(img).all()))
        opq = px(R.op('composite'))
        tg = px(R.op('tgbuf1'))
        mask = (tg[..., :3] ** 2).sum(-1) > 0.25
        diff = np.abs(img[..., :3] - opq[..., :3]).mean(-1)
        check('glass pixels exist', mask.mean() > 0.02, 'coverage %.3f' % mask.mean())
        check('glass changes the image', diff[mask].mean() > 0.01, 'mean |d| on glass %.4f' % diff[mask].mean())
        check('opaque pixels untouched', diff[~mask].max() < 1e-4, 'max |d| off glass %.6f' % diff[~mask].max())
        # thickness: the back-face pass sees the solid objects
        tb = px(R.op('tback2'))
        check('back faces rendered', ((tb[..., :3] ** 2).sum(-1) > 1e-8).mean() > 0.01)
        shadow_geo = R.op('shadow').par.geometry.eval()
        check('glass casts no shadow by default', 'scene/t' not in shadow_geo, shadow_geo)
        R.par.Transparency = False
        run('args[0]()', step2, delayFrames=20)
    except Exception:
        check('step1 exception', False, traceback.format_exc()[-400:]); finish()

def step2():
    try:
        check('Transparency off -> no transparent objects', R.par.Transcount.eval() == 0)
        check('switches bypassed', R.op('trans_src').par.index.eval() == 0)
        c0 = R.op('refract').totalCooks
        run('args[0](args[1])', step3, c0, delayFrames=10)
    except Exception:
        check('step2 exception', False, traceback.format_exc()[-400:]); finish()

def step3(c0):
    try:
        check('refract does not cook when bypassed', R.op('refract').totalCooks == c0, '%d -> %d' % (c0, R.op('refract').totalCooks))
        R.par.Transparency = True
        R.par.Refr0preset = 'diamond'
        run('args[0]()', step4, delayFrames=20)
    except Exception:
        check('step3 exception', False, traceback.format_exc()[-400:]); finish()

def step4():
    try:
        check('preset fills the slot', abs(R.par.Refr0ior.eval() - 2.42) < 1e-3)
        check('back on', R.par.Transcount.eval() == 5)
        check('screen space: traced refraction bypassed', R.op('rtr_src').par.index.eval() == 0)
        R.par.Refrmethod = 'raytraced'
        run('args[0]()', step5, delayFrames=40)
    except Exception:
        check('step4 exception', False, traceback.format_exc()[-400:]); finish()

def step5(tries=0):
    # [BTDR:TEST.M6C] ray-traced refraction: glass in the second proxy scene, traced pixels where the glass is, not black
    # (0.8.4) the first read after switching to Ray Traced can still see the warm-up of a freshly rebuilt rt_refr
    # (the Refresh rebuilds the proxy scene; its first frames are garbage, which `refract` already ignores): read again
    # up to 4 times, 30 frames apart, and log how many frames it took ([BTDR:TEST.M6CWARM])
    try:
        a = px(R.op('rt_refr_top'))
        v = a[..., 3] > 0.5
        m = a[v][:, :3].mean() if v.any() else 0.0
        ok = 0.05 < v.mean() < 0.9 and bool(np.isfinite(a).all()) and 0.05 < m < 50.0
        if not ok and tries < 4:
            LOG.append('INFO M6c warm-up read %d: valid %.3f mean %.3f' % (tries, v.mean(), m))
            run('args[0](args[1])', step5, tries + 1, delayFrames=30)
            return
        errs = [o.path for o in R.findChildren() if o.errors()]
        check('M6c: no errors', not errs, ' '.join(errs[:5]))
        check('M6c: switch on', R.op('rtr_src').par.index.eval() == 1 and R.op('uniforms')[3][39] > 1.5)
        n0, n1 = R.op('rtscene/out').numPrims(), R.op('rtscene/out_t').numPrims()
        check('M6c: glass only in the refraction scene', n1 > n0 > 0, 'out %d out_t %d' % (n0, n1))
        a = px(R.op('rt_refr_top'))
        v = a[..., 3] > 0.5
        check('M6c: traced pixels', 0.05 < v.mean() < 0.9, 'valid %.3f' % v.mean())
        m = a[v][:, :3].mean() if v.any() else 0.0
        check('M6c: finite, not black', bool(np.isfinite(a).all()) and m > 0.05, 'mean %.3f' % m)
        img = px(R.op('refract'))
        check('M6c: refract finite', bool(np.isfinite(img).all()))
        R.par.Refrmethod = 'screen'
        run('args[0]()', step6, delayFrames=15)
    except Exception:
        check('step5 exception', False, traceback.format_exc()[-400:]); finish()

def step6():
    try:
        c0 = R.op('rt_refr').totalCooks
        run('args[0](args[1])', step7, c0, delayFrames=10)
    except Exception:
        check('step6 exception', False, traceback.format_exc()[-400:]); finish()

def step7(c0):
    try:
        check('M6c: screen space again -> rt_refr does not cook', R.op('rt_refr').totalCooks == c0 and R.op('rtr_src').par.index.eval() == 0)
    except Exception:
        check('step7 exception', False, traceback.format_exc()[-400:])
    finish()

run('args[0]()', step1, delayFrames=60)
