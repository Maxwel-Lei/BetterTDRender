# [BTDR:FILE.TOOL.BENCH] Per-renderer GPU / CPU cost, measured one renderer at a time.
# Run: exec(open(project.folder + '/btdr/tools/perf_bench.py', encoding='utf-8').read())
# Result: btdr/out/perf_bench.txt
# Method: for each case, only that renderer's output is pulled every frame; per frame we sum gpuCookTime
# and cookTime over the operators inside it that cooked this frame; report the median of N frames
# (after a warm-up). Mirror geometry SOP cooks are excluded (they only cook on change).
import traceback, statistics
import numpy as np
PF = project.folder.replace('\\', '/')
BL = []
NF, WARM = 180, 40
D = op('/project1/btdr_demo'); R = D.op('renderBTDR1')   # the native comparison lives in the demo scene: native_render / native_out ([BTDR:DEMO.NATIVE])

def sample(ops):
    g = c = 0.0
    for o in ops:
        if o.valid and o.cookedThisFrame:
            if o.family in ('TOP', 'POP'): g += o.gpuCookTime
            c += o.cookTime
    return g, c

CASES = []
def add(name, pull, scope, setup=None, teardown=None):
    CASES.append(dict(name=name, pull=pull, scope=scope, setup=setup, teardown=teardown))

saved = {}
def set_btdr(**kw):
    def f():
        for k, v in kw.items():
            saved.setdefault(k, getattr(R.par, k).eval()); getattr(R.par, k).val = v
    return f
def restore_btdr():
    for k, v in saved.items(): getattr(R.par, k).val = v
    saved.clear()

# The Light COMP's own (native) shadow map is only needed by the native renderer. In this scene it re-renders
# every frame (~0.25 ms CPU, ~1.4 ms GPU) and its cost lands on whichever op first touches the light (the
# G-Buffer / uniforms of BTDR), so it is switched off for the BTDR cases and restored at the end.
LIGHT = D.op('light1'); LIGHT_SHADOW = LIGHT.par.shadowtype.eval()
def light_shadow(v):
    def f(): LIGHT.par.shadowtype = v
    return f
add('TD native Render TOP (same scene: PBR MAT, 1 distant light soft shadow + HDRI env light), 1920x1080', D.op('native_out'), [D.op('native_render'), D.op('native_out'), D.op('light1'), D.op('envlight')], None, light_shadow('off'))
# the demo scene's own settings (fog, motion blur...) are overridden so every case starts from the shipped defaults
DEF = dict(Antialias='taa', Bloom=0.05, Autoexposure=False, Dof=False, Motionblur=False, Fog=False, Heightfieldao=False,
           Ambientocclusion=True, Ssgi=True, Ssr=True, Raytracing=True, Quality='high')
SSOFF = dict(DEF, Ambientocclusion=False, Ssgi=False, Ssr=False, Raytracing=False)
OFF = dict(SSOFF, Antialias='none', Bloom=0.0)
ALL = dict(DEF, Autoexposure=True, Dof=True, Motionblur=True)
add('BTDR High, 1920x1080, everything off (M1 equivalent)', R.op('out1'), R, set_btdr(**OFF), restore_btdr)
add('BTDR High, 1920x1080, M2 defaults, screen-space and RT off (= 0.2.0 defaults)', R.op('out1'), R, set_btdr(**SSOFF), restore_btdr)
add('BTDR High, 1920x1080, M3 defaults, RT off (= 0.3.x defaults)', R.op('out1'), R, set_btdr(**dict(DEF, Raytracing=False)), restore_btdr)
add('BTDR High, 1920x1080, defaults (TAA + bloom + AO + SSGI + SSR + RT probes + RT reflections)', R.op('out1'), R, set_btdr(**DEF), restore_btdr)
add('BTDR Low, 1920x1080, defaults', R.op('out1'), R, set_btdr(**dict(DEF, Quality='low')), restore_btdr)
add('BTDR Low, 1920x1080, defaults, RT off', R.op('out1'), R, set_btdr(**dict(DEF, Quality='low', Raytracing=False)), restore_btdr)
add('BTDR High, 1920x1080, defaults + volumetric fog', R.op('out1'), R, set_btdr(**dict(DEF, Fog=True)), restore_btdr)
add('BTDR High, 1920x1080, all on (+ AE, DOF, motion blur)', R.op('out1'), R, set_btdr(**ALL), restore_btdr)
add('BTDR High, 2560x1440, defaults', R.op('out1'), R, set_btdr(**dict(DEF, Resolutionw=2560, Resolutionh=1440)), restore_btdr)
add('BTDR High, 3840x2160, defaults', R.op('out1'), R, set_btdr(**dict(DEF, Resolutionw=3840, Resolutionh=2160)), restore_btdr)

state = dict(i=-1, f=0, g=[], gx=[], c=[], per={})
ex = None
def frame_cb():
    s = state
    if s['i'] < 0 or s['i'] >= len(CASES): return
    case = CASES[s['i']]
    case['pull'].cook(force=True)
    s['f'] += 1
    if s['f'] > WARM:
        ops = case['scope'] if isinstance(case['scope'], list) else case['scope'].findChildren()
        g, c = sample(ops); s['g'].append(g); s['c'].append(c)
        # [BTDR:BENCH.SYNC] the first Render Select after the G-Buffer render is where the GPU queue is waited on:
        # its gpuCookTime also contains unrelated GPU work queued before it (other renders, the UI, other apps)
        # and swings 0.03 -> 7 ms between sessions on an otherwise identical frame. Reported separately.
        sy = R.op('gbuf0')
        s['gx'].append(g - (sy.gpuCookTime if case['scope'] is R and sy.cookedThisFrame else 0.0))
        for o in ops:
            if o.family == 'TOP' and o.cookedThisFrame:
                s['per'].setdefault(o.name, []).append(o.gpuCookTime)
    if s['f'] >= WARM + NF:
        top = sorted(((statistics.median(v), k) for k, v in s['per'].items()), reverse=True)[:8]
        BL.append('%s\n   GPU median %.2f ms (p90 %.2f), without the gbuf0 sync %.2f | CPU median %.2f ms\n   top GPU: %s'
                  % (case['name'], statistics.median(s['g']), float(np.percentile(s['g'], 90)), statistics.median(s['gx']), statistics.median(s['c']),
                     ', '.join('%s %.2f' % (k, v) for v, k in top)))
        if case['teardown']: case['teardown']()
        next_case()

def next_case():
    s = state
    s['i'] += 1; s['f'] = 0; s['g'] = []; s['gx'] = []; s['c'] = []; s['per'] = {}
    if s['i'] < len(CASES):
        if CASES[s['i']]['setup']: CASES[s['i']]['setup']()
    else:
        finish()

def finish():
    LIGHT.par.shadowtype = LIGHT_SHADOW
    try:
        tris = 0
        for g in D.findChildren(type=geometryCOMP, depth=1):
            for s in g.children:
                if s.family == 'SOP' and s.render: tris += s.numPrims
        BL.insert(0, 'scene: %d triangles (4 models + floor), 4K textures, %s' % (tris, R.par.Version.eval()))
    except Exception:
        BL.append(traceback.format_exc())
    open(PF + '/btdr/out/perf_bench.txt', 'w', encoding='utf-8').write('STATUS DONE\n' + '\n'.join(BL))
    if op('/project1').op('bench_exec'): op('/project1/bench_exec').destroy()
    op('/').time.play = _was_playing

_was_playing = op('/').time.play
try:
    if op('/project1').op('bench_exec'): op('/project1/bench_exec').destroy()
    ex = op('/project1').create(executeDAT, 'bench_exec')
    ex.text = "def onFrameEnd(frame):\n    me.fetch('cb')()\n    return\n"
    ex.par.frameend = True; ex.par.active = True
    ex.store('cb', frame_cb)
    open(PF + '/btdr/out/perf_bench.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    op('/').time.play = True              # frame callbacks only run while the timeline plays
    next_case()
except Exception:
    open(PF + '/btdr/out/perf_bench.txt', 'w', encoding='utf-8').write('STATUS ERROR\n' + traceback.format_exc())
