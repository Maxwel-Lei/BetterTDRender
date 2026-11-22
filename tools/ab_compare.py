# [BTDR:FILE.TOOL.AB] ab_compare.py — image A/B of two BTDR builds on the same scene, for "no visible change" checks.
# Loads release/BTDR_Example.tox twice into /project1/ab_compare and swaps each copy's embedded renderer: A gets AB_NEW
# (default release/BTDR.tox, the current build), B gets AB_REF (default release/BTDR_ref.tox: copy the old build there
# first), both with the example's parameter values. Two identical builds give a difference of exactly 0 (measured).
# Both are pulled every frame (same frame counters, so the same noise); after AB_FRAMES frames the HDR (out 2) and
# final (out 1) images are compared. Optional before exec: AB_PARS = {'Quality': 'low', ...} applied to both.
# Run: exec(open(project.folder + '/btdr/tools/ab_compare.py', encoding='utf-8').read())
# Result: btdr/out/ab_compare.txt (STATUS DONE + numbers), out/ab_A.jpg, out/ab_B.jpg
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
REF = globals().get('AB_REF', BT + '/release/BTDR_ref.tox')
NEW = globals().get('AB_NEW', BT + '/release/BTDR.tox')
NF = int(globals().get('AB_FRAMES', 90))
PARS = dict(globals().get('AB_PARS', {}))
LOGF = BT + '/out/ab_compare.txt'
try:
    P = op('/project1')
    if P.op('ab_compare'): P.op('ab_compare').destroy()
    N = P.create(baseCOMP, 'ab_compare'); N.nodeX, N.nodeY = 2400, -800
    A = N.loadTox(BT + '/release/BTDR_Example.tox'); A.name = 'A'
    B = N.loadTox(BT + '/release/BTDR_Example.tox'); B.name = 'B'
    for X in (A, B):
        for c in X.findChildren(type=executeDAT):
            c.par.active = False
    def swap(X, tox):
        old = X.op('renderBTDR1')
        vals = {p.name: p.eval() for p in old.customPars if not p.readOnly and p.style not in ('Pulse', 'Momentary')}
        conns = [(c.owner, c.index) for c in old.outputConnectors[0].connections]
        old.destroy()
        r = X.loadTox(tox); r.name = 'renderBTDR1'
        for k, v in vals.items():
            try: setattr(r.par, k, v)
            except Exception: pass
        for o, i in conns:
            r.outputConnectors[0].connect(o.inputConnectors[i])
        return r
    na = swap(A, NEW)
    nb = swap(B, REF)
    for X in (A, B):
        R = X.op('renderBTDR1')
        for k, v in PARS.items():
            if hasattr(R.par, k):          # a parameter the older build does not have yet is skipped (0.8.4)
                setattr(R.par, k, v)
    keep = N.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n"
                 "    for x in ('A', 'B'):\n"
                 "        r = op('/project1/ab_compare/' + x + '/renderBTDR1')\n"
                 "        r.op('out1').cook(force=True); r.op('out2').cook(force=True)\n"
                 "    return\n")
    keep.par.framestart = True; keep.par.active = True
    open(LOGF, 'w').write('STATUS RUNNING')
    def _done():
        try:
            L = ['STATUS DONE', 'A = %s, B = %s (%s), %d frames, extra pars %r' % (
                na.par.Version.eval(), REF.split('/')[-1], nb.par.Version.eval(), NF, PARS)]
            for k in ('out2', 'out1'):
                a = A.op('renderBTDR1/' + k).numpyArray()[..., :3].astype(np.float64)
                b = B.op('renderBTDR1/' + k).numpyArray()[..., :3].astype(np.float64)
                d = np.abs(a - b)
                rel = d / np.maximum(np.abs(b), 0.05)
                L.append('%s: mean |A-B| %.5f, p99.9 %.5f, max %.5f; relative p99.9 %.4f; pixels with |A-B| > 1/255: %.3f%%' % (
                    k, d.mean(), np.percentile(d, 99.9), d.max(), np.percentile(rel, 99.9), (d.max(-1) > 1 / 255.0).mean() * 100))
            A.op('renderBTDR1/out1').save(BT + '/out/ab_A.jpg'); B.op('renderBTDR1/out1').save(BT + '/out/ab_B.jpg')
            a = A.op('renderBTDR1/out1').numpyArray()[..., :3]; b = B.op('renderBTDR1/out1').numpyArray()[..., :3]
            L.append('final image also saved: out/ab_A.jpg, out/ab_B.jpg')
            dd = np.clip(np.abs(a - b) * 16.0, 0, 1)
            N.store('diff', dd)
            st = [(x, [(c.name, (c.errors() or c.warnings())[:90]) for c in X.op('renderBTDR1').findChildren()
                       if (c.errors() or c.warnings()) and c.name != 'tri']) for x, X in (('A', A), ('B', B))]
            L.append('errors / warnings: %r' % st)
            open(LOGF, 'w').write('\n'.join(L))
        except Exception:
            open(LOGF, 'w').write('STATUS ERROR\n' + traceback.format_exc())
        if not globals().get('AB_KEEP'):
            run("op('/project1/ab_compare').destroy() if op('/project1/ab_compare') else None", delayFrames=2)
    N.store('done', _done)
    run("op('/project1/ab_compare').fetch('done')()", delayFrames=NF)
except Exception:
    open(LOGF, 'w').write('STATUS ERROR\n' + traceback.format_exc())
