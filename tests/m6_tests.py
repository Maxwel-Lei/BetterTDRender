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
    except Exception:
        check('step4 exception', False, traceback.format_exc()[-400:])
    finish()

run('args[0]()', step1, delayFrames=60)
