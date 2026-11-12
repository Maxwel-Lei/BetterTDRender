# [BTDR:FILE.TEST.M7] m7_tests.py — "behaves like the native Render TOP" (0.7.4 / 0.7.5): cover and loading
# screen, start with the timeline paused, scene watch, Render flag, nested Geometry COMPs, Constant MAT unlit,
# transparent background, Ambient / Environment Light COMPs, deleting the camera, the Info page.
# Run: exec(open(project.folder + '/btdr/tests/m7_tests.py', encoding='utf-8').read())
# Result: btdr/out/m7_tests.txt (first line STATUS PASS / FAIL); the test network is removed afterwards.
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOG, FAILS = [], []
NAME = 'm7_test'
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m7_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t: t.destroy()
    op('/local/time').play = True
def errs(R):
    return [(c.name, c.errors().strip()[:60]) for c in R.findChildren() if c.valid and c.errors()]
def step(fn, frames):
    # the function object is passed as an argument, never stored (IMPLEMENTATION_2 §11 #37)
    def wrapped():
        try:
            fn()
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    run("args[0]()", wrapped, delayFrames=frames)

try:
    open(BT + '/out/m7_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -800
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    o = op('/project1/%s/renderBTDR1/out1')\n"
                 "    if o: o.cook(force=True)\n    return\n" % NAME)
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True

    # ---- 1. dropped into an empty network: cover, waiting for a camera, no errors
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    cs = R.op('cover_state')

    def s1():
        a = R.op('out1').numpyArray()
        check('empty network: cover up, waiting for a camera, no operator errors',
              cs['show'].eval() == 1 and cs['mode'].eval() == 1 and not errs(R) and not R.par.Rtavailable.eval(),
              'show %s mode %s rt %s errors %s' % (cs['show'].eval(), cs['mode'].eval(), R.par.Rtavailable.eval(), errs(R)))
        check('cover picture: lime with a dark logo', a[..., 1].mean() > 0.6 and a[..., 2].mean() < 0.3 and (a[..., 1] < 0.2).mean() > 0.03,
              'mean g %.2f b %.2f dark %.3f' % (a[..., 1].mean(), a[..., 2].mean(), (a[..., 1] < 0.2).mean()))
        ip = [p.name for p in R.customPages[-1].pars]
        check('Info page', R.customPages[-1].name == 'Info' and all(n in ip for n in ('Version', 'Showinfo', 'Startupinfo', 'Cover', 'Wechat', 'Xianyu', 'Email1', 'License')), str(ip))
        check('node colour', max(abs(x - y) for x, y in zip(R.color, (0.5, 0.5, 0.05))) < 0.01, str(R.color))
        # the scene arrives after the renderer
        cam = T.create(cameraCOMP, 'cam1'); cam.par.tz = 8
        lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx = -45; lt.par.shadowtype = 'off'
        g = T.create(geometryCOMP, 'geo_red'); g.par.tx = 3
        cm = T.create(constantMAT, 'red'); cm.par.colorr = 1; cm.par.colorg = 0; cm.par.colorb = 0; g.par.material = cm
        h = T.create(geometryCOMP, 'geo_hidden'); h.par.tx = -3; h.render = False
        pg = T.create(geometryCOMP, 'parent_geo'); pg.par.ty = 2
        ch = pg.create(geometryCOMP, 'child_geo'); ch.par.ty = -4
        for c in list(pg.children):
            if c.OPType != 'geometryCOMP': c.destroy()
        gl = T.create(geometryCOMP, 'geo_line')
        for c in list(gl.children): c.destroy()
        ln = gl.create(lineSOP, 'line'); ln.par.pax = -2; ln.par.pbx = 2; ln.render = ln.display = True
        step(s2, 45)

    def s2():
        check('scene watch: camera and geometry found without Refresh; loading screen up',
              R.par.Status.eval().startswith('OK') and cs['show'].eval() == 1 and cs['mode'].eval() == 0, '%r show %s mode %s' % (R.par.Status.eval(), cs['show'].eval(), cs['mode'].eval()))
        step(s3, 110)

    def s3():
        n = len([c for c in R.op('scene').children if c.OPType == 'geometryCOMP'])
        check('cover gone after warm-up; Render flag off not drawn; nested Geometry COMP drawn; a line does not break ray tracing',
              cs['show'].eval() == 0 and n == 4 and not errs(R) and R.par.Rtavailable.eval(), 'show %s mirrored %d errors %s' % (cs['show'].eval(), n, errs(R)))
        R.par.Tonemap = 'none'; R.par.Bloom = 0; R.par.Background = 'transparent'
        nr = T.create(renderTOP, 'native'); nr.par.camera = 'cam1'; nr.par.geometry = '*'; nr.par.lights = '*'
        nr.par.outputresolution = 'custom'; nr.par.resolutionw = 1920; nr.par.resolutionh = 1080
        step(s4, 60)

    def s4():
        a = R.op('out1').numpyArray(); b = T.op('native').numpyArray()
        m = (a[..., 0] > 0.6) & (a[..., 1] < 0.3) & (a[..., 3] > 0.99)
        col = a[m][:, :3].mean(0) if m.sum() else np.zeros(3)
        check('Constant MAT is unlit: pure colour', m.sum() > 1000 and abs(col[0] - 1) < 0.02 and col[1] < 0.02 and col[2] < 0.02 and a[m][:, :3].std(0).max() < 0.02,
              '%d px, mean %s' % (m.sum(), np.round(col, 3)))
        check('Background = Transparent: alpha is the coverage, like the native Render TOP',
              a[..., 3].min() == 0 and a[..., 3].max() == 1 and abs(a[..., 3].mean() - b[..., 3].mean()) < 0.01 and a[5, 5, :3].max() == 0,
              'alpha mean %.4f native %.4f' % (a[..., 3].mean(), b[..., 3].mean()))
        R.par.Background = 'color'
        T.op('geo_hidden').render = True
        mt = T.create(pbrMAT, 'newmat'); T.op('geo_red').par.material = mt
        al = T.create(ambientlightCOMP, 'amb'); al.par.dimmer = 0.5
        step(s5, 50)

    def s5():
        n = len([c for c in R.op('scene').children if c.OPType == 'geometryCOMP'])
        u = R.op('uniforms')
        st = R.fetch('status', {}) or {}
        check('scene watch: Render flag switched on, material swapped, Ambient Light COMP picked up',
              n == 5 and not any('Constant' in w for w in st.get('warnings', [])) and abs(float(u[0][40]) - 0.5) < 1e-3 and R.op('out1').numpyArray()[..., 3].min() == 1.0,
              'mirrored %d ambient %.2f warnings %s' % (n, float(u[0][40]), st.get('warnings')))
        ev = T.create(environmentlightCOMP, 'env1')
        rp = T.create(rampTOP, 'sky'); ev.par.envlightmap = rp
        T.op('cam1').destroy()
        step(s6, 50)

    def s6():
        check('camera deleted: back to the cover, no errors', cs['show'].eval() == 1 and cs['mode'].eval() == 1 and not errs(R), 'show %s mode %s errors %s' % (cs['show'].eval(), cs['mode'].eval(), errs(R)))
        check('Environment Light COMP used by Source = Auto', R.par.Envlight.eval().endswith('/env1') and R.op('env_src').par.index.eval() == 1, '%r' % R.par.Envlight.eval())
        R.par.Cover = False
        step(s7, 5)

    def s7():
        check('Cover While Loading off: output 1 is the render branch', R.op('out_src').par.index.eval() == 0, str(R.op('out_src').par.index.eval()))
        R.par.Cover = True
        # ---- start with the timeline paused: must refresh at once and skip the loading screen
        R.destroy()
        c = T.create(cameraCOMP, 'cam1'); c.par.tz = 8
        op('/local/time').play = False
        R2 = T.loadTox(BT + '/release/BTDR.tox'); R2.name = 'renderBTDR1'
        c2 = R2.op('cover_state')
        check('dropped in with the timeline paused: refreshed at once, no loading screen',
              R2.par.Status.eval() != '' and c2['show'].eval() == 0, '%r show %s' % (R2.par.Status.eval(), c2['show'].eval()))
        op('/local/time').play = True
        finish()

    step(s1, 20)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
