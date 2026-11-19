# [BTDR:FILE.TEST.M81] m81_tests.py — 0.8.1 fixes merged from the skin-membrane commission.
# Run: exec(open(project.folder + '/btdr/tests/m81_tests.py', encoding='utf-8').read())
# Result: btdr/out/m81_tests.txt (first line STATUS PASS / FAIL), btdr/out/m81_*.jpg; the test network is removed.
#   GBUF.POPUV       a textured POP grid shows its map (before: one corner colour)
#   REFR.DIFFUSE     a rough thin sheet: a checker 1 cm behind stays sharp, one 1 m behind is blurred
#   REFR.SMOOTHBLUR  the disc rotation changes from frame to frame (TAA averages it, no static pattern)
#   REFR.EDGE        no dark band along the frame edge behind a full-screen frosted sheet
#   REFR.THINTINT    Thin Transmission Lift brightens what is seen through a coloured thin sheet
import traceback
import numpy as np
BT = project.folder + '/btdr'
LOG, FAILS, ST = [], [], {}
NAME = 'm81_test'
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m81_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t and not KEEP: t.destroy()
def step(fn, frames):
    def wrapped():
        try:
            fn()
        except Exception:
            LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
    run("args[0]()", wrapped, delayFrames=frames)
def arr(o):
    o.cook(force=True)
    return np.array(o.numpyArray(delayed=False), dtype=np.float64)
def errs(R):
    return [(c.name, c.errors().strip()[:80]) for c in R.findChildren() if c.valid and c.errors()]
try:
    KEEP
except NameError:
    KEEP = False

CHECKER = '''out vec4 fragColor;
void main() { vec2 c = floor(vUV.st * 24.0); float k = mod(c.x + c.y, 2.0); fragColor = TDOutputSwizzle(vec4(vec3(0.1 + 0.8 * k), 1.0)); }
'''
try:
    open(BT + '/out/m81_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1200
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    o = op('/project1/%s/renderBTDR1/out1')\n"
                 "    if o: o.cook(force=True)\n    return\n" % NAME)
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True

    cam = T.create(cameraCOMP, 'cam1'); cam.par.tz = 3.0
    lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx = -30; lt.par.ry = 20; lt.par.shadowtype = 'off'
    px = T.create(textDAT, 'checker_px'); px.text = CHECKER
    chk = T.create(glslTOP, 'checker'); chk.par.pixeldat = px; chk.par.outputresolution = 'custom'
    chk.par.resolutionw = chk.par.resolutionh = 1024
    for d in list(chk.docked): d.destroy()
    ramp = T.create(rampTOP, 'ramp')                    # horizontal black -> white
    def pbr(nm, c=(1, 1, 1), rough=0.6, emitmap=None, basemap=None):
        m = T.create(pbrMAT, nm); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
        m.par.metallic = 0; m.par.roughness = rough
        if basemap: m.par.basecolormap = basemap
        if emitmap:
            m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 0
            m.par.emitr = m.par.emitg = m.par.emitb = 1; m.par.emitmap = emitmap
        return m
    def geo(nm, mat, t=(0, 0, 0), s=(1, 1, 1), pop=False):
        g = T.create(geometryCOMP, nm)
        for c in list(g.children): c.destroy()
        so = g.create(gridPOP if pop else gridSOP, 'shape'); so.render = so.display = True
        so.par.sizex = so.par.sizey = 1.0
        if pop:
            so.par.texture = 'point'
        g.par.tx, g.par.ty, g.par.tz = t; g.par.sx, g.par.sy, g.par.sz = s
        g.par.material = mat
        return g
    # checker panels behind the sheet: left 1 cm behind, right 1 m behind (scaled so the squares look the same size)
    mchk = pbr('m_checker', emitmap=chk.path)
    near = geo('near', mchk, (-0.62, 0, -0.01), (1.2, 1.6, 1))
    far = geo('far', mchk, (0.62 * 4 / 3, 0, -1.0), (1.2 * 4 / 3, 1.6 * 4 / 3, 1))
    msheet = pbr('m_sheet', (1, 1, 1), 0.5); msheet.par.alphafront = 0
    sheet = geo('sheet', msheet, (0, 0, 0), (2.6, 1.8, 1))
    # POP grid with a ramp map, off to the side (only seen in phase 1 by a second camera)
    popg = geo('popgrid', pbr('m_ramp', basemap=ramp.path), (0, 5, 0), (1, 1, 1), pop=True)
    cam2 = T.create(cameraCOMP, 'cam_pop'); cam2.par.tx, cam2.par.ty, cam2.par.tz = 0, 5, 1.2

    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False
    R.par.Camera = 'cam_pop'; R.par.Geometry = 'popgrid'; R.par.Lights = 'light1'
    R.par.Raytracing = False; R.par.Bloom = 0; R.par.Ssr = False; R.par.Ssgi = False

    def s1():
        check('version 0.8.1', R.par.Version.eval() == '0.8.1', R.par.Version.eval())
        g0 = arr(R.op('gbuf0'))
        H, W = g0.shape[:2]
        row = g0[H // 2, W // 4: 3 * W // 4, 0]
        check('GBUF.POPUV: a POP grid shows its ramp map', row.max() - row.min() > 0.3 and not errs(R),          # sRGB ramp 0.25..0.75 = linear 0.05..0.52; 0.8.0: constant
              'base colour across the grid %.2f .. %.2f, errors %s' % (row.min(), row.max(), errs(R)))
        R.par.Camera = 'cam1'; R.par.Geometry = 'near far'
        R.seq.Refr.numBlocks = 1
        R.par.Refr0geo = 'sheet'
        step(s1b, 5)
    def s1b():
        R.par.Refr0preset = 'window'
        step(s1c, 5)
    def s1c():
        R.par.Refr0rough = 0.5; R.par.Refr0thinlift = 0.0
        step(s2, 60)
    def s2():
        check('refractive slot: thin sheet resolved, no errors', R.par.Transcount.eval() == 1 and R.par.Refr0thin.eval() and not errs(R),
              'count %d thin %s errors %s' % (R.par.Transcount.eval(), R.par.Refr0thin.eval(), errs(R)))
        a = arr(R.op('trans_src'))[..., :3].mean(axis=-1)
        H, W = a.shape
        L = a[int(H * 0.3):int(H * 0.7), int(W * 0.12):int(W * 0.38)]
        Rr = a[int(H * 0.3):int(H * 0.7), int(W * 0.62):int(W * 0.88)]
        check('REFR.DIFFUSE: 1 cm behind stays sharp, 1 m behind blurs', L.std() > 2.0 * Rr.std() and L.std() > 0.05,
              'checker contrast (std) near %.3f far %.3f' % (L.std(), Rr.std()))
        check('no NaN', np.isfinite(a).all())
        ST['f0'] = arr(R.op('refract'))[..., :3]
        R.op('out1').save(BT + '/out/m81_frosted.jpg')
        step(s3, 2)
    def s3():
        f1 = arr(R.op('refract'))[..., :3]
        H, W = f1.shape[:2]
        d = np.abs(f1 - ST['f0'])[int(H * 0.3):int(H * 0.7), int(W * 0.62):int(W * 0.88)].mean()
        check('REFR.SMOOTHBLUR: disc rotation changes between frames (averaged by TAA)', d > 1e-4, 'mean |frame diff| %.5f' % d)
        # edge: a flat emissive grey wall behind a sheet that fills the frame
        mchk.par.emitmap = ''
        near.par.ty = 50                                 # out of view
        far.par.tx = 0; far.par.sx = far.par.sy = 12     # fills the frame behind the sheet
        sheet.par.sx, sheet.par.sy = 8, 6
        step(s4, 40)
    def s4():
        a = arr(R.op('trans_src'))[..., :3].mean(axis=-1)
        H, W = a.shape
        band = np.concatenate([a[:, 2:int(W * 0.04)].ravel(), a[:, int(W * 0.96):-2].ravel()])
        mid = a[int(H * 0.4):int(H * 0.6), int(W * 0.4):int(W * 0.6)]
        check('REFR.EDGE: no dark band along the frame edge', band.mean() > 0.9 * mid.mean(),
              'edge band %.3f centre %.3f' % (band.mean(), mid.mean()))
        msheet.par.basecolorr, msheet.par.basecolorg, msheet.par.basecolorb = 1.0, 0.45, 0.5
        ST['m0'] = mid.mean()
        step(s5, 30)
    def s5():
        a = arr(R.op('trans_src'))
        H, W = a.shape[:2]
        ST['g0'] = a[int(H * 0.4):int(H * 0.6), int(W * 0.4):int(W * 0.6), 1].mean()
        R.par.Refr0thinlift = 0.6
        step(s6, 30)
    def s6():
        a = arr(R.op('trans_src'))
        H, W = a.shape[:2]
        g1 = a[int(H * 0.4):int(H * 0.6), int(W * 0.4):int(W * 0.6), 1].mean()
        check('REFR.THINTINT: lift 0.6 lets more green through a pink sheet', g1 > ST['g0'] * 1.3,
              'green through the sheet %.3f -> %.3f' % (ST['g0'], g1))
        R.op('out1').save(BT + '/out/m81_lift.jpg')
        finish()

    step(s1, 90)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
