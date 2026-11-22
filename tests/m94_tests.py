# [BTDR:FILE.TEST.M94] m94_tests.py — 0.9.4: orthographic camera, point sprites.
# Run: exec(open(project.folder + '/btdr/tests/m94_tests.py', encoding='utf-8').read())
# Result: btdr/out/m94_tests.txt (first line STATUS PASS / FAIL), btdr/out/m94_*.jpg; the test network is removed.
import traceback
import numpy as np
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG, FAILS = [], []
NAME = 'm94_test'
W, H = 640, 360
OW = 8.0                          # ortho width
def check(name, ok, detail=''):
    LOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)
def finish():
    open(BT + '/out/m94_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(LOG), len(FAILS)) + '\n'.join(LOG))
    t = op('/project1/' + NAME)
    if t: t.destroy()
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
def geo(n, sop, t, mat, **kw):
    g = T.create(geometryCOMP, n)
    for c in list(g.children): c.destroy()
    s = g.create(sop, 's'); s.render = s.display = True
    for k, v in kw.items(): setattr(s.par, k, v)
    g.par.tx, g.par.ty, g.par.tz = t; g.par.material = mat
    return g
ST = {}
try:
    open(BT + '/out/m94_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    P = op('/project1')
    if P.op(NAME): P.op(NAME).destroy()
    T = P.create(baseCOMP, NAME); T.nodeX, T.nodeY = 2400, -2000
    m = T.create(pbrMAT, 'm_w'); m.par.basecolorr = m.par.basecolorg = m.par.basecolorb = 0.7; m.par.roughness = 0.4
    geo('floor', gridSOP, (0, 0, 0), m, sizex=12, sizey=12, orient='zx')
    geo('box', boxSOP, (-1.5, 0.5, 0), m, sizex=1, sizey=1, sizez=1)
    geo('ball', sphereSOP, (1.5, 0.6, 0), m, radx=0.6, rady=0.6, radz=0.6, type='polygon', rows=24, cols=24)
    # point sprites: a 10 x 10 grid of POP points in the air
    pg = T.create(geometryCOMP, 'pts')
    for c in list(pg.children): c.destroy()
    gp = pg.create(gridPOP, 's'); gp.render = gp.display = True
    gp.par.surftype = 'points'; gp.par.rows = 10; gp.par.cols = 10
    pg.par.ty = 1.6; pg.par.tz = 1.5; pg.par.sx = pg.par.sy = 3.0; pg.par.material = m
    cam = T.create(cameraCOMP, 'cam1'); cam.par.ty = 5; cam.par.tz = 6; cam.par.rx = -35
    cam.par.projection = 'ortho'; cam.par.orthowidth = OW
    sun = T.create(lightCOMP, 'sun'); sun.par.lighttype = 'distant'; sun.par.rx = -50; sun.par.ry = 30; sun.par.dimmer = 1.0
    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Startupinfo = False; R.par.Cover = False; R.par.Resolutionw, R.par.Resolutionh = W, H
    R.par.Camera = 'cam1'; R.par.Geometry = 'floor box ball pts'; R.par.Lights = 'sun'
    R.par.Bloom = 0; R.par.Pointsize = 0.2
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    op('/project1/%s/renderBTDR1/out1').cook(force=True)\n    return\n" % NAME
    keep.par.framestart = True; keep.par.active = True
    ST['R'] = R
    M = cam.worldTransform
    cpos = np.array([M[0, 3], M[1, 3], M[2, 3]])
    right = np.array([M[0, 0], M[1, 0], M[2, 0]]); up = np.array([M[0, 1], M[1, 1], M[2, 1]]); back = np.array([M[0, 2], M[1, 2], M[2, 2]])
    right /= np.linalg.norm(right); up /= np.linalg.norm(up); back /= np.linalg.norm(back)

    def s1():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        check('no errors', not e, str(e[:3]))
        u = R.op('uniforms')
        check('UNI ortho flag and half width', abs(u[3][19] - 1.0) < 1e-6 and abs(u[3][3] - OW / 2) < 1e-6,
              'uClip.w %.2f, uCamFwd.w %.3f' % (u[3][19], u[3][3]))
        # geometry: the camera-relative G-Buffer position projects back onto its own pixel (orthographic mapping)
        p = arr(R.op('gbuf2'))[:, :, :3]
        geo_ = np.abs(p).sum(-1) > 1e-6
        ys, xs = np.nonzero(geo_)
        sel = np.linspace(0, len(xs) - 1, 400).astype(int)
        rel = p[ys[sel], xs[sel]]
        u_ = rel @ right / (OW / 2) * 0.5 + 0.5
        v_ = rel @ up / (OW / 2 / (W / float(H))) * 0.5 + 0.5
        err = np.sqrt((u_ * W - (xs[sel] + 0.5)) ** 2 + (v_ * H - (ys[sel] + 0.5)) ** 2)
        check('CAM.ORTHO depth -> world -> pixel round trip < 1 px (jitter)', float(np.percentile(err, 95)) < 1.0,
              'p95 %.3f px, max %.3f px' % (float(np.percentile(err, 95)), float(err.max())))
        img = arr(R.op('out2'))[..., :3]
        check('final image: finite, lit', np.isfinite(img).all() and img[geo_].mean() > 0.05, 'mean %.3f' % float(img[geo_].mean()))
        bg = img[~geo_]
        check('background is one direction (flat)', bg.size == 0 or float(bg.std(0).max()) < 1e-3, 'std %.5f' % (float(bg.std(0).max()) if bg.size else 0))
        # sprites
        mats = [g.par.material.eval() for g in R.op('scene').findChildren(type=geometryCOMP, name='g*')]
        spr = [mm for mm in mats if mm is not None and mm.par.pdat.eval() == R.op('gbuffer_sprite_frag')]
        check('EXT.SPRITE the point grid gets the sprite material', len(spr) == 1, '%d sprite materials' % len(spr))
        cas = R.fetch('shadow_casters', [])
        check('sprites cast no shadow, are not ray traced', all(not c.endswith('g3') for c in cas) and
              not any(sp.par.pop.eval() == gp for sp in R.op('rtscene').findChildren(type=selectPOP)), str(cas))
        # sprite pixels: G-Buffer normals spread over the hemisphere facing the camera
        nrm = arr(R.op('gbuf1'))[:, :, :3]
        wp = p + cpos
        mk = (wp[..., 1] > 0.9) & (np.abs(wp[..., 2] - 1.5) < 1.7) & geo_
        nb = nrm[mk] @ back
        npx = int(mk.sum())
        # expected: 100 discs of diameter 0.2 x pixels per unit (W / OW)
        exp_px = 100 * np.pi * (0.1 * W / OW) ** 2
        check('GBUF.SPRITE 100 round sprites of the right size', 0.6 * exp_px < npx < 1.4 * exp_px, '%d px, expected about %.0f' % (npx, exp_px))
        check('GBUF.SPRITE sphere normals (centre faces the camera, edges turn away)',
              npx > 0 and nb.max() > 0.97 and nb.min() < 0.5, 'n.back %.2f .. %.2f' % (nb.min() if npx else 0, nb.max() if npx else 0))
        lum = img[..., :3].mean(-1)[mk]
        check('sprites are shaded like spheres', npx > 0 and float(lum.std()) > 0.03, 'lum std %.3f' % (float(lum.std()) if npx else 0))
        R.op('out1').save(BT + '/out/m94_ortho.jpg')
        R.par.Fog = True; R.par.Fogdensity = 0.1; R.par.Dof = True; R.par.Motionblur = True
        step(s2, 60)
    def s2():
        img = arr(R.op('out2'))[..., :3]
        check('fog, depth of field (off), motion blur with an orthographic camera: finite', np.isfinite(img).all() and img.mean() > 0.02,
              'mean %.3f' % float(img.mean()))
        R.par.Fog = False; R.par.Dof = False; R.par.Motionblur = False
        cam.par.projection = 'perspective'
        step(s3, 60)
    def s3():
        e = [(c.name, c.errors()[:80]) for c in R.findChildren() if c.valid and c.errors()]
        u = R.op('uniforms')
        img = arr(R.op('out2'))[..., :3]
        check('back to perspective: flag off, finite image', u[3][19] < 0.5 and np.isfinite(img).all() and not e, 'uClip.w %.1f' % u[3][19])
        R.op('out1').save(BT + '/out/m94_persp.jpg')
        step(finish, 2)
    step(s1, 120)
except Exception:
    LOG.append('FAIL  exception\n' + traceback.format_exc()); FAILS.append('exception'); finish()
