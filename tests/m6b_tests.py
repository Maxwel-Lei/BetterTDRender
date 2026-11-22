# [BTDR:FILE.TEST.M6B] m6b_tests.py — M6b blended transparency checks on the m6b_scene test scene ([BTDR:TEST.M6B]).
# Run: exec(open(project.folder + '/btdr/tests/m6b_tests.py', encoding='utf-8').read())
# Result: btdr/out/m6b_tests.txt, first line STATUS PASS / FAIL. Builds /project1/m6b_test (tests/m6b_scene.py), removes it.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOGF = BT + '/out/m6b_tests.txt'
LOG, FAILS = [], []
def check(name, ok, info=''):
    LOG.append('%s %s %s' % ('PASS' if ok else 'FAIL', name, info))
    if not ok: FAILS.append(name)
def finish():
    open(LOGF, 'w', encoding='utf-8').write('\n'.join(['STATUS ' + ('PASS' if not FAILS else 'FAIL')] + LOG))
    if op('/project1/m6b_test'): op('/project1/m6b_test').destroy()

M6_SHOT = None
exec(open(BT + '/tests/m6b_scene.py', encoding='utf-8').read())
R = op('/project1/m6b_test/renderBTDR1')

def px(top):
    return np.asarray(top.numpyArray(delayed=False), dtype=np.float32)

def step1():
    try:
        # 7 smoke cards inferred from their PBR MAT (Blending + alpha map) + sparks + hologram from the Blended slots
        check('blended objects classified', R.par.Blendcount.eval() == 9, 'blendcount %s' % R.par.Blendcount.eval())
        check('glass still refractive', R.par.Transcount.eval() == 1)
        sc = R.op('scene')
        check('blended mirrors are b*', len(sc.findChildren(name='b*', depth=1)) == 9)
        check('blend switch on', R.op('blend_src').par.index.eval() == 1)
        errs = [o.path for o in R.findChildren() if o.errors()]
        check('no errors', not errs, ' '.join(errs[:5]))
        ub = px(R.op('ub_tex')); ch = R.op('uniforms')
        check('uniform texture matches the CHOP', R.op('ub_tex').width == 40 and
              max(abs(float(ub[0, i, k]) - ch[k][i]) for i in (0, 3, 10, 15) for k in range(4)) < 1e-4)
        bl = px(R.op('tblend'))
        check('blended layer finite, premultiplied', bool(np.isfinite(bl).all()) and bool((bl[..., 3] <= 1.001).all()))
        cov = (bl[..., 3] > 0.01).mean()
        check('smoke coverage', 0.05 < cov < 0.9, 'coverage %.3f' % cov)
        add = ((bl[..., :3].max(-1) > 0.5) & (bl[..., 3] < 0.01)).mean()
        check('additive pixels (sparks, hologram)', add > 0.001, 'additive %.4f' % add)
        a = px(R.op('trans_src')); b = px(R.op('blend_comp'))
        empty = bl[..., :4].max(-1) < 1e-6
        check('pixels without blended objects untouched', np.abs(a - b)[..., :3][empty].max() < 1e-4)
        # soft particles: no smoke pixel lies behind the opaque surface (they are discarded)
        sh = R.op('shadow').par.geometry.eval()
        check('blended objects cast no shadow', 'scene/b' not in sh, sh)
        R.par.Blendmethod = 'orderind'
        run('args[0]()', step2, delayFrames=15)
    except Exception:
        check('step1 exception', False, traceback.format_exc()[-400:]); finish()

def step2():
    try:
        errs = [o.path for o in R.findChildren() if o.errors()]
        check('order independent: no errors', not errs, ' '.join(errs[:5]))
        check('order independent: render TOP mode', R.op('tblend').par.transparency.eval() == 'orderind')
        bl = px(R.op('tblend'))
        check('order independent: image', bool(np.isfinite(bl).all()) and (bl[..., 3] > 0.01).mean() > 0.05)
        R.par.Blendmethod = 'sorted'
        R.par.Transparency = False
        run('args[0]()', step3, delayFrames=20)
    except Exception:
        check('step2 exception', False, traceback.format_exc()[-400:]); finish()

def step3():
    try:
        check('Transparency off -> no blended objects', R.par.Blendcount.eval() == 0)
        check('blend switch bypassed', R.op('blend_src').par.index.eval() == 0)
        c0 = R.op('tblend').totalCooks
        run('args[0](args[1])', step4, c0, delayFrames=10)
    except Exception:
        check('step3 exception', False, traceback.format_exc()[-400:]); finish()

def step4(c0):
    try:
        check('tblend does not cook when bypassed', R.op('tblend').totalCooks == c0, '%d -> %d' % (c0, R.op('tblend').totalCooks))
    except Exception:
        check('step4 exception', False, traceback.format_exc()[-400:])
    finish()

run('args[0]()', step1, delayFrames=60)
