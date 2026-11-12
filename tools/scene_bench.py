# [BTDR:FILE.TOOL.SCENEBENCH] GPU / CPU cost of the renderBTDR in each showcase scene (make_scenes.py).
# Run: exec(open(project.folder + '/btdr/tools/scene_bench.py', encoding='utf-8').read())
# Pulls one scene's OUT every frame, sums gpuCookTime / cookTime of the ops inside its renderBTDR that cooked this
# frame (+ the scene's own GLSL POP for the particles), median of NF frames after WARM. Result: out/scene_bench.txt
import statistics
NF, WARM = 150, 60
SC = globals().get('BENCH_SCENES', ['blinds', 'neon', 'monolith', 'particles', 'materials'])
RES = []


def _sample(ops):
    g = c = 0.0
    for o in ops:
        if o.valid and o.cookedThisFrame:
            if o.family in ('TOP', 'POP') and o.name != 'gbuf0':   # gbuf0 carries the GPU queue wait (IMPLEMENTATION_2 §11 #17)
                g += o.gpuCookTime
            c += o.cookTime
    return g, c


def _run(k):
    S = op('/project1/sc_' + SC[k])
    R = S.op('renderBTDR1')
    ops = R.findChildren() + ([S.op('swirl')] if S.op('swirl') else [])
    gs, cs = [], []
    state = {'i': 0}

    def tick():
        S.op('OUT').cook()
        if state['i'] >= WARM:
            g, c = _sample(ops)
            gs.append(g); cs.append(c)
        state['i'] += 1
        if state['i'] < WARM + NF:
            run(tick, delayFrames=1)
        else:
            RES.append('%-10s GPU %.2f ms  CPU %.2f ms' % (SC[k], statistics.median(gs), statistics.median(cs)))
            if k + 1 < len(SC):
                run(lambda: _run(k + 1), delayFrames=5)
            else:
                open(project.folder + '/btdr/out/scene_bench.txt', 'w').write('STATUS DONE\n' + '\n'.join(RES))
    run(tick, delayFrames=1)


open(project.folder + '/btdr/out/scene_bench.txt', 'w').write('STATUS RUNNING')
_run(0)
