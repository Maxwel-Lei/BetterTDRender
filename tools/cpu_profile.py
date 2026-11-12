# [BTDR:FILE.TOOL.CPUPROF] Per-operator CPU / GPU breakdown of one renderBTDR instance.
# Run: exec(open(project.folder + '/btdr/tools/cpu_profile.py', encoding='utf-8').read())
# Optional before exec: PROF_TARGET = '/path/renderBTDR1'
# Result: btdr/out/cpu_profile.txt (median over NF frames after a warm-up; only ops that cooked that frame)
import statistics, traceback
PF = project.folder.replace('\\', '/')
NF, WARM = 150, 30
R = op(globals().get('PROF_TARGET', '/project1/btdr_demo/renderBTDR1'))   # PROF_TARGET: another instance
ST = dict(f=0, cpu={}, gpu={}, tot=[], was_playing=op('/').time.play)

def _cb():
    ST['f'] += 1
    R.op('out1').cook(force=True)
    if ST['f'] <= WARM: return
    t = 0.0
    for o in R.findChildren():
        if o.valid and o.cookedThisFrame:
            ST['cpu'].setdefault(o.path[len(R.path) + 1:], []).append(o.cookTime)
            if o.family == 'TOP': ST['gpu'].setdefault(o.path[len(R.path) + 1:], []).append(o.gpuCookTime)
            t += o.cookTime
    ST['tot'].append(t)
    if ST['f'] >= WARM + NF: _finish()

def _finish():
    # [BTDR:PROF.STEADY] only operators that cooked in (almost) every measured frame: one-off cooks after a Refresh
    # (shader compiles, PolyReduce) would otherwise top the list
    steady = {k for k, v in ST['cpu'].items() if len(v) >= 0.9 * NF}
    cpu = sorted(((statistics.median(v), k) for k, v in ST['cpu'].items() if k in steady), reverse=True)
    gpu = sorted(((statistics.median(v), k) for k, v in ST['gpu'].items() if k in steady), reverse=True)
    rare = sorted(((max(v), k, len(v)) for k, v in ST['cpu'].items() if k not in steady), reverse=True)
    L = ['STATUS DONE', 'target %s' % R.path,
         'CPU total median %.3f ms over %d frames (all cooks)' % (statistics.median(ST['tot']), len(ST['tot'])),
         'steady ops: %d, CPU sum of medians %.3f ms, GPU sum of medians %.3f ms (without gbuf0 %.3f)' % (
             len(steady), sum(m for m, _ in cpu), sum(m for m, _ in gpu), sum(m for m, k in gpu if k != 'gbuf0')),
         '', 'steady ops: CPU median ms | GPU median ms | name']
    gd = {k: m for m, k in gpu}
    for m, k in cpu:
        L.append('  %7.3f  %7.3f  %s' % (m, gd.get(k, 0.0), k))
    L += ['', 'occasional cooks (max CPU ms, times):']
    for m, k, n in rare[:25]:
        L.append('  %7.3f  %-40s %d' % (m, k, n))
    open(PF + '/btdr/out/cpu_profile.txt', 'w', encoding='utf-8').write('\n'.join(L))
    op('/').time.play = ST['was_playing']
    if op('/project1').op('prof_exec'): op('/project1/prof_exec').destroy()

try:
    if op('/project1').op('prof_exec'): op('/project1/prof_exec').destroy()
    ex = op('/project1').create(executeDAT, 'prof_exec')
    ex.text = "def onFrameEnd(frame):\n    me.fetch('cb')()\n    return\n"
    ex.store('cb', _cb)
    ex.par.frameend = True; ex.par.active = True
    open(PF + '/btdr/out/cpu_profile.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    op('/').time.play = True
except Exception:
    open(PF + '/btdr/out/cpu_profile.txt', 'w', encoding='utf-8').write('STATUS ERROR\n' + traceback.format_exc())
