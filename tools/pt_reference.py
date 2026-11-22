# [BTDR:FILE.TOOL.PTREF] pt_reference.py — (0.8.5, J2) path-traced reference images for calibrating BTDR.
# One native scene (Geometry COMPs + PBR MATs + a distant Light COMP + a constant-colour environment) is rendered by
# release/BTDR.tox and by Josef Pelz's Pathtracer (PT_FAM.tox, MIT; not shipped with BTDR, used only on this machine
# as a reference, [BTDR:PTREF.LICENSE]). The Pathtracer reads the same Geometry COMPs, PBR MATs and Light COMP itself
# (its td_geo / TDLight import, with TouchDesigner's own light-strength convention), so both see the same scene.
# Both linear HDR outputs are compared per region (named rectangles) and as a log2-ratio heat map.
# Optional before exec:
#   PTREF_SCENE   'room' (default: open room, coloured walls, boxes, rough metal / plastic spheres) or 'spheres'
#   PTREF_SPP     samples per pixel to accumulate (default 1024)
#   PTREF_PARS    {par: value} applied to the BTDR (calibration runs)
#   PTREF_TAG     file tag (default the scene name)
#   PTREF_TOX     path of PT_FAM.tox (default: 03_BTDR/Josef Pelz's tox/Pathtracer/PT_FAM.tox next to the project)
#   PTREF_KEEP    True keeps /project1/pt_ref afterwards
# Run: exec(open(project.folder + '/btdr/tools/pt_reference.py', encoding='utf-8').read())
# Result: btdr/out/pt_ref_<tag>.txt (STATUS DONE + per-region numbers), out/pt_ref_<tag>.jpg (BTDR | Pathtracer |
# heat map: red = BTDR brighter, blue = darker, one stop per full colour).
import os, traceback, time
import numpy as np
BT = project.folder + '/btdr'
_SCENE = globals().get('PTREF_SCENE', 'room')
_SPP = int(globals().get('PTREF_SPP', 1024))
# [BTDR:PTREF.MATCH] BTDR's own light convention differs from TouchDesigner's (and the Pathtracer's): sun = Dimmer x pi,
# colour parameters decoded as sRGB (kept on purpose, 2026-11-22: BTDR does not follow the native look). For a fair
# comparison of the algorithms the reference run uses linear colours and Intensity Multiplier 1/pi.
import math as _math
_PARS = dict({'Srgbcolors': False, 'Lightmult': 1.0 / _math.pi}, **dict(globals().get('PTREF_PARS', {})))
_TAG = globals().get('PTREF_TAG', _SCENE)
_TOX = globals().get('PTREF_TOX', os.path.normpath(project.folder + "/../Josef Pelz's tox/Pathtracer/PT_FAM.tox").replace('\\', '/'))
_KEEP = bool(globals().get('PTREF_KEEP', False))
_LOGF = BT + '/out/pt_ref_%s.txt' % _TAG
_W, _H = 640, 360
_ST = {'t0': time.time()}

def _log(text):
    open(_LOGF, 'w', encoding='utf-8').write(text)

def _pbr(S, n, c, rough, metal=0.0):
    m = S.create(pbrMAT, n)
    m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
    m.par.roughness = rough; m.par.metallic = metal
    return m

def _setp(o, **kw):
    for k, v in kw.items():
        if hasattr(o.par, k):
            setattr(o.par, k, v)

# [BTDR:PTREF.POP] the Pathtracer imports a Geometry COMP's render-flagged POP, not SOPs (py/gltf.prims): the scene
# is built from POPs (Box POP size 1, Sphere POP radius 0.5) and sized by the COMP's scale; BTDR renders POPs too.
def _box(S, n, mat, t, size):
    g = S.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    s = g.create(boxPOP, 'p'); s.render = s.display = True
    _setp(s, sizex=1.0, sizey=1.0, sizez=1.0)
    g.par.tx, g.par.ty, g.par.tz = t; g.par.sx, g.par.sy, g.par.sz = size; g.par.material = mat
    return g

def _ball(S, n, mat, t, r):
    g = S.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    s = g.create(spherePOP, 'p'); s.render = s.display = True
    _setp(s, radx=0.5, rady=0.5, radz=0.5, rows=48, cols=96, freq=24)
    g.par.tx, g.par.ty, g.par.tz = t; g.par.scale = 2 * r; g.par.material = mat
    return g

# named regions (x0, y0, x1, y1 in 0..1 of the image, y up as in TOP arrays) — chosen for the fixed camera
REGIONS = {
    'room': {
        'floor in sun':          (0.40, 0.04, 0.60, 0.14),
        'floor under box (AO)':  (0.215, 0.13, 0.29, 0.19),
        'back wall':             (0.42, 0.62, 0.58, 0.80),
        'red wall':              (0.03, 0.40, 0.12, 0.70),
        'green wall':            (0.88, 0.40, 0.97, 0.70),
        'box top':               (0.19, 0.42, 0.32, 0.48),
        'box shadow side':       (0.30, 0.22, 0.36, 0.38),
        'rough metal ball':      (0.55, 0.22, 0.64, 0.38),
        'plastic ball':          (0.70, 0.20, 0.78, 0.33),
        'ceiling':               (0.40, 0.93, 0.60, 0.99),
    },
}

def _build():
    P = op('/project1')
    if P.op('pt_ref'): P.op('pt_ref').destroy()
    S = P.create(baseCOMP, 'pt_ref'); S.nodeX, S.nodeY = 2400, -2000
    _ST['S'] = S
    env = S.create(constantTOP, 'env')            # uniform sky: no rotation convention to match
    env.par.colorr, env.par.colorg, env.par.colorb = 0.45, 0.5, 0.6
    env.par.outputresolution = 'custom'; env.par.resolutionw = 64; env.par.resolutionh = 32
    env.par.format = 'rgba32float'
    white = _pbr(S, 'm_white', (0.75, 0.75, 0.75), 0.8)
    red = _pbr(S, 'm_red', (0.7, 0.08, 0.06), 0.8)
    green = _pbr(S, 'm_green', (0.1, 0.55, 0.12), 0.8)
    # open room: floor, back wall, side walls, ceiling with a gap at the front (sun comes in from above-front)
    _box(S, 'floor', white, (0, -0.05, 0), (6, 0.1, 6))
    _box(S, 'backwall', white, (0, 1.5, -2.0), (6, 3, 0.1))
    _box(S, 'leftwall', red, (-2.0, 1.5, 0), (0.1, 3, 6))
    _box(S, 'rightwall', green, (2.0, 1.5, 0), (0.1, 3, 6))
    _box(S, 'ceiling', white, (0, 3.05, -0.6), (6, 0.1, 3.0))
    _box(S, 'box', white, (-0.8, 0.5, -0.6), (0.9, 1.0, 0.9))
    _ball(S, 'metal', _pbr(S, 'm_metal', (0.95, 0.75, 0.4), 0.45, 1.0), (0.35, 0.45, -0.3), 0.45)
    _ball(S, 'plastic', _pbr(S, 'm_plastic', (0.2, 0.35, 0.8), 0.25), (1.15, 0.3, 0.3), 0.3)
    cam = S.create(cameraCOMP, 'cam1'); cam.par.tx, cam.par.ty, cam.par.tz = 0, 1.4, 5.2; cam.par.rx = -6; cam.par.fov = 50
    lt = S.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx = -55; lt.par.ry = 20
    lt.par.dimmer = 3.0
    try: lt.par.shadowtype = 'soft2d'
    except Exception: pass
    keep = S.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    for n in ('renderBTDR1/out2', 'pathtracer/out1'):\n        o = op('/project1/pt_ref/' + n)\n"
                 "        if o: o.cook(force=True)\n    return\n")
    keep.par.framestart = True; keep.par.active = True
    op('/local/time').play = True
    run('args[0]()', _btdr, delayFrames=5)

def _btdr():
    S = _ST['S']
    r = S.loadTox(BT + '/release/BTDR.tox'); r.name = 'renderBTDR1'
    r.par.Startupinfo = False; r.par.Cover = False
    r.par.Resolutionw, r.par.Resolutionh = _W, _H
    r.par.Envsource = 'hdri'; r.par.Envmap = S.op('env').path
    r.par.Background = 'env'; r.par.Bgblur = 0.0
    r.par.Bloom = 0
    if hasattr(r.par, 'Vignette'): r.par.Vignette = 0
    for k, v in _PARS.items():
        if hasattr(r.par, k): setattr(r.par, k, v)
    _ST['R'] = r
    run('args[0]()', _pt, delayFrames=30)

def _pt():
    S = _ST['S']
    if not os.path.exists(_TOX):
        _log('STATUS ERROR\nPathtracer not found: %s (set PTREF_TOX)' % _TOX); return
    fam = S.loadTox(_TOX); fam.name = 'pt_fam'
    fam.allowCooking = False
    src = fam.op('PT_OPs/Pathtracer')
    pt = S.copy(src, name='pathtracer')
    pt.nodeX, pt.nodeY = 400, 0
    pt.par.Camera = S.op('cam1').path
    pt.par.Geometry = 'floor backwall leftwall rightwall ceiling box metal plastic'
    pt.par.Lights = 'light1'
    pt.par.Envmap = S.op('env').path
    pt.par.Envstrength = 1.0
    pt.par.Method = 'Accumulate'
    pt.par.Panelresolution = False          # its default takes the size from a panel (/project1)
    pt.par.Resolutionw, pt.par.Resolutionh = _W, _H
    pt.par.Bounces = 8
    pt.par.Samples = 8
    pt.par.Srgb = False
    pt.par.Exposure = 0.0
    try: pt.par.Fireflyclamp = 0.0
    except Exception: pass
    _ST['pt'] = pt
    run('args[0]()', _wait, delayFrames=60)

def _samples(pt):
    # accumulated frames x samples per frame (the Samples parameter's own expression reads the same CHOP)
    try:
        return int(pt.op('state/out')['n']) * int(pt.par.Samples.eval())
    except Exception:
        return -1

def _wait():
    try:
        pt = _ST['pt']
        n = _samples(pt)
        el = time.time() - _ST['t0']
        _log('STATUS RUNNING\nsamples %d / %d after %.0f s' % (n, _SPP, el))
        if (n < _SPP) and el < 900:
            run('args[0]()', _wait, delayFrames=60)
            return
        _compare(n)
    except Exception:
        _log('STATUS ERROR\n' + traceback.format_exc())

def _arr(o):
    o.cook(force=True)
    return np.array(o.numpyArray(delayed=False), dtype=np.float64)[:, :, :3]

def _compare(n):
  try:
    _compare_(n)
  except Exception:
    _log('STATUS ERROR\n' + traceback.format_exc())

def _compare_(n):
    S, R, pt = _ST['S'], _ST['R'], _ST['pt']
    a = _arr(R.op('out2')); b = _arr(pt.op('out1'))
    if a.shape != b.shape:
        _log('STATUS ERROR\nsize mismatch %s %s' % (a.shape, b.shape)); return
    la = a @ np.array([0.2126, 0.7152, 0.0722]); lb = b @ np.array([0.2126, 0.7152, 0.0722])
    lines = ['STATUS DONE', 'scene %s, %dx%d, Pathtracer %d spp, BTDR pars %s' % (_SCENE, _W, _H, n, _PARS),
             'whole image: mean luminance BTDR %.4f, Pathtracer %.4f, ratio %.3f' % (la.mean(), lb.mean(), la.mean() / max(lb.mean(), 1e-9)),
             '%-22s %9s %9s %7s   %s' % ('region', 'BTDR', 'PT', 'ratio', 'rgb ratio')]
    H, W = la.shape
    for nm, (x0, y0, x1, y1) in REGIONS.get(_SCENE, {}).items():
        sl = (slice(int(y0 * H), int(y1 * H)), slice(int(x0 * W), int(x1 * W)))
        ma, mb = la[sl].mean(), lb[sl].mean()
        ca, cb = a[sl].reshape(-1, 3).mean(0), b[sl].reshape(-1, 3).mean(0)
        lines.append('%-22s %9.4f %9.4f %7.3f   %s' % (nm, ma, mb, ma / max(mb, 1e-9), np.round(ca / np.maximum(cb, 1e-9), 3)))
    _log('\n'.join(lines) + '\n')
    # side-by-side picture: BTDR | Pathtracer (same simple tone map) | log2 ratio heat map
    try:
        def tm(x):
            x = x / (1.0 + x)
            return np.clip(x, 0, 1) ** (1 / 2.2)
        r = np.log2(np.maximum(la, 1e-4) / np.maximum(lb, 1e-4))
        heat = np.zeros_like(a)
        heat[..., 0] = np.clip(r, 0, 1); heat[..., 2] = np.clip(-r, 0, 1); heat[..., 1] = 0.15
        img = np.concatenate([tm(a), tm(b), heat], axis=1)
        sc = S.create(scriptTOP, 'pic')
        T = S.create(textDAT, 'pic_cb')
        T.text = ("import numpy as np\ndef onCook(scriptOp):\n    scriptOp.copyNumpyArray(scriptOp.fetch('img'))\n    return\n")
        sc.par.callbacks = T
        im4 = np.concatenate([img, np.ones(img.shape[:2] + (1,))], axis=2).astype(np.float32)
        sc.store('img', np.ascontiguousarray(im4))
        sc.cook(force=True)
        sc.save(BT + '/out/pt_ref_%s.jpg' % _TAG, quality=0.92)
    except Exception:
        open(_LOGF, 'a', encoding='utf-8').write('picture failed\n' + traceback.format_exc())
    if not _KEEP:
        run("op('/project1/pt_ref').destroy() if op('/project1/pt_ref') else None", delayFrames=5)

try:
    _log('STATUS RUNNING')
    _build()
except Exception:
    _log('STATUS ERROR\n' + traceback.format_exc())
