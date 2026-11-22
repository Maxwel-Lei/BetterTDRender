# [BTDR:FILE.TOOL.REGRESSION] run_regression.py — run the test scripts one after another (each waits for the previous
# one's result file to leave STATUS RUNNING), so several BTDRs are never initialised in the same frame.
# Optional before exec: REG_TESTS = ['m1_tests', ...] (default: the full regression set below).
# Run: exec(open(project.folder + '/btdr/tools/run_regression.py', encoding='utf-8').read())
# Result: btdr/out/regression.txt — one line per test: its first result line (STATUS PASS / FAIL (...)).
import os, time
BT = project.folder + '/btdr'
_REG = list(globals().get('REG_TESTS', ['m1_tests', 'm81_tests', 'm8_tests', 'm7_tests', 'm6_tests', 'm5_acceptance', 'm83_tests', 'm84_tests', 'm85_tests', 'm90_tests', 'm91_tests', 'm92_tests', 'm93_tests']))
_OUT = BT + '/out/regression.txt'
open(_OUT, 'w', encoding='utf-8').write('RUNNING\n')

def _status(name):
    f = BT + '/out/%s.txt' % name
    if not os.path.exists(f):
        return None
    t = open(f, encoding='utf-8').read().splitlines()
    return t[0] if t else None

def _start(i, results):
    if i >= len(_REG):
        open(_OUT, 'w', encoding='utf-8').write('DONE\n' + '\n'.join(results) + '\n')
        return
    name = _REG[i]
    f = BT + '/out/%s.txt' % name
    open(f, 'w', encoding='utf-8').write('STATUS RUNNING')
    t0 = time.time()
    try:
        # the tests run in this namespace (they need TD's globals); each one resets its own LOG / FAILS at the start
        exec(open(BT + '/tests/%s.py' % name, encoding='utf-8').read(), globals())
    except Exception as e:
        open(f, 'w', encoding='utf-8').write('STATUS FAIL (exception at start: %r)' % e)
    run('args[0](args[1], args[2], args[3])', _poll, i, results, t0, delayFrames=60)

def _poll(i, results, t0):
    s = _status(_REG[i]) or ''
    if s.startswith('STATUS RUNNING') and time.time() - t0 < 900:
        run('args[0](args[1], args[2], args[3])', _poll, i, results, t0, delayFrames=60)
        return
    results.append('%-14s %s  (%.0f s)' % (_REG[i], s if s else 'no result', time.time() - t0))
    open(_OUT, 'w', encoding='utf-8').write('RUNNING\n' + '\n'.join(results) + '\n')
    run('args[0](args[1], args[2])', _start, i + 1, results, delayFrames=30)

_start(0, [])
