# [BTDR:FILE.TEST.M83] m83_tests.py — 0.8.3 texture coordinates and scene unit.
# Run: exec(open(project.folder + '/btdr/tests/m83_tests.py', encoding='utf-8').read())
# Result: btdr/out/m83_tests.txt (first line STATUS PASS / FAIL), btdr/out/m83_*.jpg; the test network is removed.
#   EXT.SAMPLERSTATE  the mirror material's Extend / Filter follow the PBR MAT
#   GBUF.UVSET        BTDR's G-Buffer base colour equals the native Render TOP pixel for pixel (a texture whose colour
#                     is its own UV): uv0, uv1 (a second set from a Texture SOP), Extend Hold / Mirror, Screen Space
#   UNI.UNIT          the same scene in centimetres (every length x 100, Scene Unit = Centimeters) renders like the metre original
#                     (AO, bounce light, reflections, fog, height-field AO, depth of field, ray tracing all on)
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm83_test'
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m83_tests.txt', 'w', encoding='utf-8').write(
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

UVPX = '''out vec4 fragColor;
void main() { fragColor = TDOutputSwizzle(vec4(vUV.st, 0.0, 1.0)); }
'''
W, H = 640, 360
try:
    open(BT + '/out/m83_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -1400
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    for n in ('uv/renderBTDR1', 'sc_m/renderBTDR1', 'sc_cm/renderBTDR1'):\n"
                 "        o = op('/project1/%s/' + n + '/out1')\n        if o: o.cook(force=True)\n    return\n" % NAME)
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True

    # ------------------------------------------------------------------ part 1: texture coordinates vs native
    U = T.create(baseCOMP, 'uv')
    px = U.create(textDAT, 'uv_px'); px.text = UVPX
    uvt = U.create(glslTOP, 'uvtex'); uvt.par.pixeldat = px; uvt.par.outputresolution = 'custom'
    uvt.par.resolutionw = uvt.par.resolutionh = 256; uvt.par.format = 'rgba32float'
    for d in list(uvt.docked): d.destroy()
    g = U.create(geometryCOMP, 'box')
    for c in list(g.children): c.destroy()
    bx = g.create(boxSOP, 'b'); bx.par.texture = 'faceoutside'
    tx = g.create(textureSOP, 't'); tx.inputConnectors[0].connect(bx)
    tx.par.texlayer = 1; tx.par.type = 'face'; tx.par.su = 2.5; tx.par.sv = 2.5     # uv[1] = uv[0] x 2.5 (repeats)
    tx.render = tx.display = True
    g.par.rx = 25; g.par.ry = 35
    mb = U.create(pbrMAT, 'm_btdr'); mb.par.basecolorr = mb.par.basecolorg = mb.par.basecolorb = 1; mb.par.basecolormap = uvt.path
    mb.par.metallic = 0
    mn = U.create(pbrMAT, 'm_native'); mn.par.basecolorr = mn.par.basecolorg = mn.par.basecolorb = 0
    mn.par.emitr = mn.par.emitg = mn.par.emitb = 1; mn.par.emitmap = uvt.path
    g.par.material = mb.path
    cam = U.create(cameraCOMP, 'cam1'); cam.par.tz = 2.6
    lt = U.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.shadowtype = 'off'
    # native: a copy of the box with the emissive material, no lights -> output = the map
    gn = U.create(geometryCOMP, 'box_native')
    for c in list(gn.children): c.destroy()
    bn = gn.create(boxSOP, 'b'); bn.par.texture = 'faceoutside'
    tn = gn.create(textureSOP, 't'); tn.inputConnectors[0].connect(bn)
    tn.par.texlayer = 1; tn.par.type = 'face'; tn.par.su = 2.5; tn.par.sv = 2.5
    tn.render = tn.display = True
    gn.par.rx = 25; gn.par.ry = 35; gn.par.material = mn.path         # BTDR's Geometry = 'box' leaves it out
    NR = U.create(renderTOP, 'native'); NR.par.camera = cam.path; NR.par.geometry = gn.path; NR.par.lights = ''
    NR.par.outputresolution = 'custom'; NR.par.resolutionw = W; NR.par.resolutionh = H; NR.par.format = 'rgba32float'
    NR.par.bgcolora = 0
    R = U.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False
    R.par.Camera = 'cam1'; R.par.Geometry = 'box'; R.par.Lights = 'light1'
    R.par.Resolutionw = W; R.par.Resolutionh = H
    R.par.Antialias = 'none'; R.par.Srgbcolors = False
    R.par.Ssr = False; R.par.Ssgi = False; R.par.Raytracing = False; R.par.Bloom = 0

    def setboth(**kv):
        # the native copy shows the map as emission, so its parameters are the Emit Map's
        for k, v in kv.items():
            setattr(mb.par, k, v)
            setattr(mn.par, 'emitmapsamplingmode' if k == 'texturesamplingmode' else k.replace('basecolormap', 'emitmap'), v)

    def compare(tag):
        gb = arr(R.op('gbuf0'))[:, :, :2]
        nat = arr(NR)
        mask = nat[:, :, 3] > 0.999
        # skip pixels next to a UV seam (repeat wrap / face edge): their 2x2 footprint straddles two texels
        gx = np.abs(np.diff(nat[:, :, 0], axis=1, append=0)) + np.abs(np.diff(nat[:, :, 1], axis=0, append=0))
        mask &= gx < 0.05
        d = np.abs(gb - nat[:, :, :2])[mask]
        med, p90 = float(np.median(d)), float(np.percentile(d, 90))
        check('GBUF.UVSET %s: G-Buffer = native' % tag, med < 0.01 and p90 < 0.03 and mask.sum() > 2000,
              'median %.4f p90 %.4f over %d px' % (med, p90, int(mask.sum())))

    CASES = [('uv0', dict(basecolormapcoord='uv0', texturesamplingmode='regular')),
             ('uv1 repeat', dict(basecolormapcoord='uv1')),
             ('uv1 extend hold', dict(basecolormapextendu='hold', basecolormapextendv='hold')),
             ('uv1 extend mirror', dict(basecolormapextendu='mirror', basecolormapextendv='mirror')),
             ('screen space', dict(basecolormapcoord='uv0', basecolormapextendu='repeat', basecolormapextendv='repeat',
                                   texturesamplingmode='screenspace'))]

    def s1():
        check('version (same as build.py)', True, R.par.Version.eval())
        e = errs(R)
        check('uv scene: no errors', not e, str(e[:3]))
        m = R.op('scene').findChildren(type=glslMAT)
        check('mirror material has uUV0 / uUV1 / uScr', bool(m) and all(
            any(getattr(m[0].par, 'vec%dname' % i).eval() == n for i in range(m[0].seq.vec.numBlocks)) for n in ('uUV0', 'uUV1', 'uScr')),
            str([getattr(m[0].par, 'vec%dname' % i).eval() for i in range(m[0].seq.vec.numBlocks)]) if m else 'no mirror')
        run_case(0)

    def run_case(i):
        if i >= len(CASES):
            step(s2, 2); return
        tag, kv = CASES[i]
        setboth(**kv)
        def after():
            if tag == 'uv1 extend mirror':
                m = R.op('scene').findChildren(type=glslMAT)[0]
                ex = [getattr(m.par, 'sampler%dextendu' % j).eval() for j in range(m.seq.sampler.numBlocks)
                      if getattr(m.par, 'sampler%dname' % j).eval() == 'sBaseColor']
                check('EXT.SAMPLERSTATE: mirror sampler Extend follows the PBR MAT', ex == ['mirror'], str(ex))
            compare(tag)
            if i == 1:
                R.op('gbuf0').save(BT + '/out/m83_uv1_btdr.jpg'); NR.save(BT + '/out/m83_uv1_native.jpg')
            run_case(i + 1)
        step(after, 8)

    # ------------------------------------------------------------------ part 2: scene unit
    def build_scene(nm, s, unit):
        S = T.create(baseCOMP, nm)
        def pbr(n, c, rough, metal=0.0):
            m = S.create(pbrMAT, n); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
            m.par.roughness = rough; m.par.metallic = metal
            return m
        def geo(n, sop, mat, t, sc=1.0):
            gg = S.create(geometryCOMP, n)
            for c in list(gg.children): c.destroy()
            so = gg.create(sop, 's'); so.render = so.display = True
            gg.par.tx, gg.par.ty, gg.par.tz = [v * s for v in t]; gg.par.scale = sc * s
            gg.par.material = mat
            return gg, so
        _, fl = geo('floor', gridSOP, pbr('m_floor', (0.6, 0.6, 0.6), 0.25), (0, 0, 0))
        fl.par.sizex = fl.par.sizey = 8; fl.par.orient = 'zx'
        _, sp = geo('ball', sphereSOP, pbr('m_ball', (0.8, 0.2, 0.15), 0.35), (-0.6, 0.5, 0))
        sp.par.type = 'poly'; sp.par.freq = 10; sp.par.radx = sp.par.rady = sp.par.radz = 0.5
        geo('cube', boxSOP, pbr('m_cube', (0.9, 0.9, 0.9), 0.1, 1.0), (0.7, 0.4, -0.3), 0.8)
        c = S.create(cameraCOMP, 'cam1'); c.par.tx, c.par.ty, c.par.tz = 0.4 * s, 1.4 * s, 3.6 * s; c.par.rx = -18
        c.par.near = 0.05 * s; c.par.far = 100 * s
        l = S.create(lightCOMP, 'light1'); l.par.lighttype = 'distant'; l.par.shadowtype = 'off'; l.par.rx = -40; l.par.ry = 30
        r = S.loadTox(BT + '/release/BTDR.tox'); r.name = 'renderBTDR1'
        r.par.Startupinfo = False; r.par.Cover = False
        r.par.Resolutionw = W; r.par.Resolutionh = H
        r.par.Sceneunit = unit
        r.par.Heightfieldao = True; r.par.Fog = True; r.par.Fogdensity = 0.08; r.par.Fogbaseheight = 0.0
        r.par.Fogdistance = 12; r.par.Dof = True; r.par.Focusdistance = 3.8 * s; r.par.Fstop = 2.0
        return r

    def s2():
        ST['m'] = build_scene('sc_m', 1.0, 'meters')
        ST['cm'] = build_scene('sc_cm', 100.0, 'centimeters')        # 1 unit = 1 cm: every length x 100
        step(s3, 150)

    def s3():
        rm, rc = ST['m'], ST['cm']
        e = errs(rm) + errs(rc)
        check('scene unit: no errors', not e, str(e[:3]))
        a, b = arr(rm.op('out1'))[:, :, :3], arr(rc.op('out1'))[:, :, :3]
        d = np.abs(a - b)
        check('UNI.UNIT: x100 + Centimeters = Meters (final image)', float(d.mean()) < 0.01,
              'mean |diff| %.4f, p99 %.4f, image mean %.3f' % (float(d.mean()), float(np.percentile(d, 99)), float(a.mean())))
        rm.op('out1').save(BT + '/out/m83_unit_m.jpg'); rc.op('out1').save(BT + '/out/m83_unit_cm.jpg')
        # the same comparison per effect, so a failure points at the pass that still assumes metres
        views = ['depth', 'ssao', 'ssgi', 'ssr', 'rtgi', 'rtrefl', 'direct']
        ST['views'] = views; ST['vi'] = 0
        step(s4, 1)

    def s4():
        rm, rc = ST['m'], ST['cm']
        vi = ST['vi']
        if vi > 0:
            v = ST['views'][vi - 1]
            a, b = arr(rm.op('out1'))[:, :, :3], arr(rc.op('out1'))[:, :, :3]
            dd = float(np.abs(a - b).mean())
            check('UNI.UNIT debug view %s' % v, dd < 0.015 if v != 'depth' else True, 'mean |diff| %.4f' % dd)
        if vi >= len(ST['views']):
            rm.par.Debugview = rc.par.Debugview = 'final'
            step(lambda: finish(), 2); return
        rm.par.Debugview = rc.par.Debugview = ST['views'][vi]
        ST['vi'] = vi + 1
        step(s4, 40)

    ST = {}
    step(s1, 60)
except Exception:
    LOG.append('FAIL  setup exception\n' + traceback.format_exc()); FAILS.append('setup'); finish()
