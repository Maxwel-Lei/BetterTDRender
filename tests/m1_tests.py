# [BTDR:FILE.TEST] M1 + M2 + M3 regression tests.
# Run inside TouchDesigner:  exec(open(project.folder + '/btdr/tests/m1_tests.py', encoding='utf-8').read())
# Builds /project1/btdr_test (7 spheres, one per material case), runs the checks over ~10 seconds,
# writes btdr/out/m1_tests.txt (first line STATUS PASS / FAIL) and btdr/out/test_*.jpg, then removes the scene.
import os, math, traceback
import numpy as np

BT = project.folder.replace('\\', '/') + '/btdr'
TLOG, FAILS = [], []

def check(name, ok, detail=''):
    TLOG.append('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok: FAILS.append(name)

def finish(T=None):
    open(BT + '/out/m1_tests.txt', 'w', encoding='utf-8').write(
        'STATUS %s (%d checks, %d failed)\n' % ('FAIL' if FAILS else 'PASS', len(TLOG), len(FAILS)) + '\n'.join(TLOG))
    for n in ('btdr_test', 'btdr_test_reload'):
        if op('/project1').op(n): op('/project1').op(n).destroy()

try:
    root = op('/project1')
    for n in ('btdr_test', 'btdr_test_reload'):
        if root.op(n): root.op(n).destroy()
    T = root.create(baseCOMP, 'btdr_test')
    XS = [-3, -2, -1, 0, 1, 2, 3]
    CASES = ['pbr normal map', 'pbr emissive map', 'pbr packed map + channel source', 'phong', 'constant', 'no material', 'custom glsl']

    # ---- textures
    noise = T.create(noiseTOP, 'noise'); noise.par.period = 0.15
    nrm = T.create(normalmapTOP, 'nrm'); noise.outputConnectors[0].connect(nrm)
    ramp = T.create(rampTOP, 'ramp')
    packed = T.create(constantTOP, 'packed'); packed.par.colorr, packed.par.colorg, packed.par.colorb = 1.0, 0.2, 1.0

    # ---- materials
    m0 = T.create(pbrMAT, 'm_normal'); m0.par.basecolorr = m0.par.basecolorg = m0.par.basecolorb = 0.6
    m0.par.metallic = 0; m0.par.roughness = 0.4; m0.par.normalmap = nrm
    m1 = T.create(pbrMAT, 'm_emit'); m1.par.basecolorr = m1.par.basecolorg = m1.par.basecolorb = 0.05
    m1.par.metallic = 0; m1.par.roughness = 0.5; m1.par.emitr = m1.par.emitg = m1.par.emitb = 1; m1.par.emitmap = ramp
    m2 = T.create(pbrMAT, 'm_packed'); m2.par.basecolorr, m2.par.basecolorg, m2.par.basecolorb = 0.9, 0.7, 0.3
    m2.par.metallic = 1; m2.par.roughness = 1; m2.par.metallicmap = packed; m2.par.roughnessmap = packed
    m2.par.metallicmapchannelsource = 'blue'; m2.par.roughnessmapchannelsource = 'green'
    m3 = T.create(phongMAT, 'm_phong'); m3.par.diffr, m3.par.diffg, m3.par.diffb = 1, 0, 0
    m4 = T.create(constantMAT, 'm_const'); m4.par.colorr, m4.par.colorg, m4.par.colorb = 0, 0, 1
    m6 = T.create(glslMAT, 'm_custom')
    MATS = [m0, m1, m2, m3, m4, None, m6]

    for i, x in enumerate(XS):
        g = T.create(geometryCOMP, 'geo%d' % i)
        for c in list(g.children): c.destroy()
        s = g.create(sphereSOP, 'sphere'); s.par.radx = s.par.rady = s.par.radz = 0.4
        s.par.rows = 40; s.par.cols = 60
        s.render = True; s.display = True
        g.par.tx = x; g.par.ty = 0.4
        if MATS[i] is not None: g.par.material = MATS[i]
    fl = T.create(geometryCOMP, 'floor')
    for c in list(fl.children): c.destroy()
    gs = fl.create(gridSOP, 'grid'); gs.par.orient = 'zx'; gs.par.sizex = gs.par.sizey = 20; gs.render = True; gs.display = True

    tgt = T.create(nullCOMP, 'target'); tgt.par.ty = 0.4
    cam = T.create(cameraCOMP, 'cam1'); cam.par.tx, cam.par.ty, cam.par.tz = 0, 2.2, 7.5; cam.par.lookat = tgt; cam.par.fov = 50
    cam2 = T.create(cameraCOMP, 'cam2'); cam2.par.tx, cam2.par.ty, cam2.par.tz = 5, 1.5, 4; cam2.par.lookat = tgt
    light = T.create(lightCOMP, 'light1'); light.par.lighttype = 'distant'; light.par.rx = -45; light.par.ry = 35

    # synthetic HDR panorama: sky gradient + a sun disc at radiance 60 (no HDR sample ships with TD)
    hf = T.create(textDAT, 'hdri_frag')
    hf.text = ('out vec4 fragColor;\nvoid main(){\n float phi=(vUV.s-0.5)*6.2831853, th=(vUV.t-0.5)*3.14159265;\n'
               ' vec3 d=vec3(sin(phi)*cos(th), sin(th), -cos(phi)*cos(th));\n'
               ' vec3 c=mix(vec3(0.25,0.22,0.2), mix(vec3(0.9,0.95,1.0), vec3(0.15,0.35,0.9), smoothstep(0.0,0.8,d.y)), smoothstep(-0.02,0.02,d.y));\n'
               ' c+=vec3(60.0,52.0,40.0)*smoothstep(0.995,0.998,dot(d,normalize(vec3(-0.6,0.5,0.6))));\n fragColor=vec4(c,1.0);}\n')
    hdri = T.create(glslTOP, 'hdri'); hdri.par.pixeldat = hf
    hdri.par.outputresolution = 'custom'; hdri.par.resolutionw = 2048; hdri.par.resolutionh = 1024
    hdri.par.format = 'rgba32float'

    R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
    R.par.Antialias = 'none'   # the geometry checks compare against the un-jittered camera; TAA is tested in [BTDR:TEST.M2]
    R.par.Geometry = 'geo* floor'; R.par.Exposure = 0
    keep = T.create(executeDAT, 'keep')
    keep.text = ("def onFrameStart(frame):\n    for n in ('renderBTDR1', 'renderBTDR2'):\n        o = parent().op(n)\n"
                 "        if o:\n            for k in ('out1', 'out2', 'out3'): o.op(k).cook(force=True)\n    return\n")
    keep.par.framestart = True; keep.par.active = True

    def arr(o): return o.numpyArray().astype(np.float64)
    def region(i, wp):
        return (np.abs(wp[..., 0] - XS[i]) < 0.25) & (wp[..., 1] > 0.25) & (wp[..., 1] < 0.7) & (np.abs(wp[..., 2]) < 0.45)
    def comp_errors(Rc):
        errs = [(o.path, o.errors()) for o in Rc.findChildren() if o.errors()]
        inf = T.create(infoDAT, 'tmpinfo'); bad = []
        for o in Rc.findChildren():
            if o.OPType in ('glslmultiTOP', 'glslMAT', 'glslPOP'):
                inf.par.op = o.path; inf.cook(force=True)
                if 'rror' in inf.text: bad.append((o.path, inf.text[:300]))
        inf.destroy()
        return errs, bad
    def worldpos(Rc):   # the G-Buffer stores camera-relative position ([BTDR:GBUF.RELPOS])
        u = Rc.op('uniforms')
        return arr(Rc.op('gbuf2'))[..., :3] + np.array([float(u[c][0]) for c in range(3)])
    def fov_error(Rc, camop):
        # reconstruct world position from the depth output + camera basis and compare with the G-Buffer
        u = Rc.op('uniforms'); col = lambda k: np.array([float(u[c][k]) for c in range(4)])
        P, Rt, Up, Fw, clip = col(0), col(1), col(2), col(3), col(19)
        d = arr(Rc.op('out3'))[..., 0]; wp = worldpos(Rc); n1 = arr(Rc.op('gbuf1'))[..., :3]
        H, W = d.shape
        ys, xs = np.mgrid[0:H:8, 0:W:8]
        ndx = (xs + 0.5) / W * 2 - 1; ndy = (ys + 0.5) / H * 2 - 1
        rd = Fw[:3] + ndx[..., None] * Fw[3] * Rt[:3] + ndy[..., None] * Fw[3] / clip[2] * Up[:3]
        rec = P[:3] + rd * d[::8, ::8][..., None]
        hit = (n1[::8, ::8] ** 2).sum(-1) > 0.25
        return float(np.abs(rec - wp[::8, ::8])[hit].max()), int(hit.sum())

    def s1():   # ---------------- materials
        try:
            st = R.fetch('status', {})
            check('auto refresh on load', st.get('mirrored') == 8, 'mirrored=%r' % st.get('mirrored'))
            errs, bad = comp_errors(R)
            check('no operator errors', not errs, repr(errs)[:300])
            check('all shaders compile', not bad, repr(bad)[:400])
            g0, g1, g2, g3 = [arr(R.op('gbuf%d' % k)) for k in range(4)]
            wp = worldpos(R)
            def dev(i):   # mean angle between G-Buffer normal and the analytic sphere normal
                m = region(i, wp); n = g1[m][:, :3]; a = wp[m] - np.array([XS[i], 0.4, 0.0]); a /= np.linalg.norm(a, axis=1)[:, None]
                return float(np.degrees(np.arccos(np.clip((n * a).sum(1), -1, 1))).mean()), int(m.sum())
            d0, n0 = dev(0); d5, n5 = dev(5)
            check('normal map perturbs normals', d0 > 3.0 and d5 < 1.5, 'mapped %.2f deg vs plain %.2f deg (%d px)' % (d0, d5, n0))
            e1 = g3[region(1, wp)][:, :3]; e5 = g3[region(5, wp)][:, :3]
            check('emissive map', e1.mean() > 0.05 and e1.std() > 0.02 and e5.max() < 1e-4, 'mean %.3f std %.3f, plain max %.5f' % (e1.mean(), e1.std(), e5.max()))
            r2 = g1[region(2, wp)][:, 3].mean(); me2 = g0[region(2, wp)][:, 3].mean()
            check('channel source (rough=G, metal=B)', abs(r2 - 0.2) < 0.02 and abs(me2 - 1.0) < 0.02, 'rough %.3f metal %.3f' % (r2, me2))
            b3 = g0[region(3, wp)][:, :3].mean(0); r3 = g1[region(3, wp)][:, 3].mean()
            check('Phong MAT fallback', b3[0] > 0.9 and b3[1] < 0.02 and abs(r3 - 0.5) < 0.02, 'base %s rough %.2f' % (np.round(b3, 3).tolist(), r3))
            b4 = g0[region(4, wp)][:, :3].mean(0)
            e4 = g3[region(4, wp)][:, :3].mean(0)       # [BTDR:GBUF.UNLIT] 0.7.5: unlit, the colour is in the emission buffer
            check('Constant MAT unlit', e4[2] > 0.9 and e4[0] < 0.02 and b4.max() < 0.02, 'emission %s base %s' % (np.round(e4, 3).tolist(), np.round(b4, 3).tolist()))
            b5 = g0[region(5, wp)][:, :3].mean(0)
            check('no material -> default grey', abs(b5[0] - 0.5 ** 2.2) < 0.01, 'base %s' % np.round(b5, 3).tolist())
            w = ' | '.join(st.get('warnings', []))
            check('warnings for phong / constant / custom', all(k in w for k in ('Phong', 'not supported')), w[:300])
            u = R.op('uniforms')
            check('uniform block 4 x 124 (0.9.1)', u.numChans == 4 and u.numSamples == 124, '%d chans %d samples' % (u.numChans, u.numSamples))
            # the velocity materials (scene/vm*, 0.9.2) carry last frame's matrix and have no maps: not G-Buffer materials
            mats = [m for m in R.findChildren(type=glslMAT, path='*/scene/*') if not m.name.startswith('vm')]
            check('materials: no per-frame uniform, 4x anisotropic; G-Buffer through cam_jit',
                  mats and all(all(getattr(m.par, 'array%dchop' % i).eval() is None for i in range(m.seq.array.numBlocks)) and m.par.sampler0anisotropy.eval() == '4x' for m in mats)
                  and R.op('gbuffer').par.camera.eval() == R.op('cam_jit'), '%d materials' % len(mats))
            T.store('nrm_gl', g1[region(0, wp)][:, :3].copy())
            T.store('shc0', R.op('shadow').totalCooks)
            R.par.Normalconvention = 'directx'
            R.op('out1').save(BT + '/out/test_materials.jpg')
            R.par.Debugview = 'normal'
            run("args[0]()", s1b, delayFrames=10)
        except Exception:
            check('materials', False, traceback.format_exc()); finish()
    def s1b():
        try:
            R.op('out1').save(BT + '/out/test_normals.jpg'); R.par.Debugview = 'final'
            g1 = arr(R.op('gbuf1')); wp = worldpos(R)
            a, b = T.fetch('nrm_gl'), g1[region(0, wp)][:, :3]
            k = min(len(a), len(b))
            ang = float(np.degrees(np.arccos(np.clip((a[:k] * b[:k]).sum(1), -1, 1))).mean()) if k else 0.0
            check('normal map convention DirectX changes normals', len(a) == len(b) and ang > 1.0, 'mean change %.2f deg' % ang)
            R.par.Normalconvention = 'opengl'
            c1 = R.op('shadow').totalCooks
            check('shadow cache: static scene does not re-render the shadow map', c1 - T.fetch('shc0') <= 1 and not R.op('shadow_cache').par.active.eval(),
                  '%d shadow renders over 10 frames' % (c1 - T.fetch('shc0')))
            T.store('shc1', c1); T.store('shimg', arr(R.op('lighting'))[::8, ::8, :3].copy())
            light.par.ry = light.par.ry.eval() + 40
            cam.par.viewanglemethod = 'vertfov'; cam.par.fov = 35
            e, n = fov_error(R, cam); check('view angle: horizontal FOV', e < 0.01, 'max world error %.5f over %d px' % (e, n))
            run("args[0]()", s2, delayFrames=10)
        except Exception:
            check('fov horizontal', False, traceback.format_exc()); finish()
    def s2():
        try:
            e, n = fov_error(R, cam); check('view angle: vertical FOV', e < 0.01, 'max world error %.5f over %d px' % (e, n))
            dimg = float(np.abs(arr(R.op('lighting'))[::8, ::8, :3] - T.fetch('shimg')).mean())
            check('shadow cache: moving the light re-renders the shadow map', R.op('shadow').totalCooks > T.fetch('shc1') and dimg > 1e-3,
                  '%d renders, direct light change %.4f' % (R.op('shadow').totalCooks - T.fetch('shc1'), dimg))
            light.par.ry = light.par.ry.eval() - 40
            cam.par.viewanglemethod = 'focallength'; cam.par.focal = 35; cam.par.aperture = 36
            run("args[0]()", s3, delayFrames=10)
        except Exception:
            check('fov vertical', False, traceback.format_exc()); finish()
    def s3():
        try:
            e, n = fov_error(R, cam); check('view angle: focal length', e < 0.01, 'max world error %.5f over %d px' % (e, n))
            cam.par.viewanglemethod = 'horzfov'; cam.par.fov = 50
            R.par.Resolutionw = 1280; R.par.Resolutionh = 720
            run("args[0]()", s4, delayFrames=10)
        except Exception:
            check('fov focal', False, traceback.format_exc()); finish()
    def s4():   # ---------------- resolution, quality, light type
        try:
            sizes = [(R.op(k).width, R.op(k).height) for k in ('out1', 'out2', 'out3')]
            e, n = fov_error(R, cam)
            check('resolution change', sizes == [(1280, 720)] * 3 and e < 0.01, '%r err %.5f' % (sizes, e))
            R.par.Resolutionw = 1920; R.par.Resolutionh = 1080
            R.par.Quality = 'low'
            light.par.lighttype = 'point'; light.par.tx, light.par.ty, light.par.tz = 3, 4, 3
            R.par.Refresh.pulse()
            run("args[0]()", s5, delayFrames=12)
        except Exception:
            check('resolution', False, traceback.format_exc()); finish()
    def s5(tries=0):
        try:
            ss = R.op('uniforms_callbacks').module._STATE.get(R.op('uniforms').path + '#shadow', {})
            # a heavy frame (Refresh, shader compiles) can skip many timeline frames in one cook: wait until the
            # shadow map has settled (full resolution re-render after the change) before checking
            if (ss.get('changed_prev') or ss.get('settle', 0) > 0 or R.op('shadow').width != int(R.par.Shadowres.eval())) and tries < 20:
                run("args[0](args[1])", s5, tries + 1, delayFrames=3)
                return
            check('Quality Low', R.par.Shadowres.eval() == '2048' and R.op('shadow').width == 2048,
                  'shadow %d (res par %s, cache %s, src %s, settle %s, moving-prev %s, mn %s, why %s, now %d, watch %s)' % (
                      R.op('shadow').width, R.op('shadow').par.resolutionw.eval(), R.op('shadow_cache').par.active.eval(),
                      R.op('shadow_src').par.index.eval(), ss.get('settle'), ss.get('changed_prev'), ss.get('mn'), ss.get('why'), absTime.frame,
                      R.fetch('shadow_watch', None)))
            st = R.fetch('status', {}); w = ' | '.join(st.get('warnings', []))
            d = arr(R.op('lighting'))[..., :3]; wp = worldpos(R)
            # (0.9.0) a non-distant light is a local light now ([BTDR:EXT.LIGHTS]): lit, and the readout counts it
            check('non-distant light is a local light', 'point' in R.par.Lightcount.eval() and d[region(5, wp)].mean() > 0.01, '%s, direct mean %.3f' % (R.par.Lightcount.eval(), d[region(5, wp)].mean()))
            light.par.lighttype = 'distant'; R.par.Quality = 'high'
            R.par.Lights = 'nothing_here'
            run("args[0]()", s6, delayFrames=12)
        except Exception:
            check('light type', False, traceback.format_exc()); finish()
    def s6():   # ---------------- no light, HDRI
        try:
            st = R.fetch('status', {}); w = ' | '.join(st.get('warnings', []))
            d = arr(R.op('lighting'))[..., :3]; wp = worldpos(R)
            check('no light -> built-in key light', 'built-in key light' in w and d[region(5, wp)].mean() > 0.01 and not R.op('uniforms').errors(), w[:120])
            R.par.Lights = 'light1'
            T.store('studio', arr(R.op('out2'))[::4, ::4, :3])
            R.par.Envsource = 'hdri'; R.par.Envmap = hdri; R.par.Background = 'env'; R.par.Bgblur = 0
            run("args[0]()", s7, delayFrames=15)
        except Exception:
            check('no light', False, traceback.format_exc()); finish()
    def s7():
        try:
            a = arr(R.op('out2'))[::4, ::4, :3]; at = arr(R.op('env_atlas'))
            check('HDRI environment', np.abs(a - T.fetch('studio')).mean() > 0.02 and np.isfinite(at).all() and R.op('env_src').par.index.eval() == 1,
                  'image diff %.3f, atlas shape %s max %.1f, irradiance mean %.3f' % (np.abs(a - T.fetch('studio')).mean(), at.shape, at.max(), at[-1].mean() if at.ndim == 4 else -1))
            R.op('out1').save(BT + '/out/test_hdri.jpg')
            R.par.Envrotate = 120
            run("args[0]()", s8, delayFrames=10)
        except Exception:
            check('hdri', False, traceback.format_exc()); finish()
    def s8():   # ---------------- second instance
        try:
            R.op('out1').save(BT + '/out/test_hdri_rotated.jpg')
            R.par.Envrotate = 0; R.par.Envsource = 'studio'; R.par.Background = 'color'
            R2 = T.copy(R, name='renderBTDR2'); R2.par.Camera = 'cam2'; R2.par.Geometry = 'geo[0-3]'
            run("args[0](args[1])", s9, R2, delayFrames=15)
        except Exception:
            check('hdri rotate', False, traceback.format_exc()); finish()
    def s9(R2):
        try:
            s1_, s2_ = R.fetch('status', {}), R2.fetch('status', {})
            errs, bad = comp_errors(R2)
            a1 = arr(R.op('out1'))[::4, ::4, :3]; a2 = arr(R2.op('out1'))[::4, ::4, :3]
            check('two instances side by side', s1_.get('mirrored') == 8 and s2_.get('mirrored') == 4 and s2_.get('camera', '').endswith('cam2')
                  and not errs and not bad and np.abs(a1 - a2).mean() > 0.01,
                  'mirrored %r / %r, image diff %.3f, status %r, errors %r %r' % (s1_.get('mirrored'), s2_.get('mirrored'), np.abs(a1 - a2).mean(), R2.par.Status.eval(), errs[:2], bad[:1]))
            R2.op('out1').save(BT + '/out/test_second_instance.jpg')
            R2.destroy()
            R.par.Antialias = 'none'
            run("args[0]()", m2a, delayFrames=10)
        except Exception:
            check('two instances', False, traceback.format_exc()); finish()
    # ---------------- [BTDR:TEST.M2] TAA, bloom, auto exposure, depth of field, motion blur
    POST = ('Antialias', 'Bloom', 'Autoexposure', 'Dof', 'Focusdistance', 'Fstop', 'Motionblur', 'Shutter')
    def m2a():
        try:
            cam, cj = op(R.fetch('cam_path')), R.op('cam_jit')
            T.store('post0', {k: getattr(R.par, k).eval() for k in POST if k != 'Antialias'})
            check('TAA off: no jitter', cj.par.winx.eval() == cam.par.winx.eval() and cj.par.winy.eval() == cam.par.winy.eval()
                  and R.op('uniforms').chan('chan1')[8] == 0.0,
                  'winx %.6f vs %.6f' % (cj.par.winx.eval(), cam.par.winx.eval()))
            T.store('noaa', arr(R.op('out2'))[..., :3].copy())
            R.par.Antialias = 'taa'
            run("args[0](args[1])", m2b, cam, delayFrames=20)
        except Exception:
            check('TAA', False, traceback.format_exc()); finish()
    def m2b(cam):
        try:
            u = R.op('uniforms'); cj = R.op('cam_jit')
            jit = (u.chan('chan1')[8], u.chan('chan2')[8]); W = R.par.Resolutionw.eval(); H = R.par.Resolutionh.eval()
            jpx = max(abs(jit[0]) * W, abs(jit[1]) * H)      # NDC -> pixels: x by width, y by height
            a = arr(R.op('out2'))[..., :3]; d = np.abs(a - T.fetch('noaa')).max(-1)
            check('TAA on: sub-pixel jitter, history blended, finite',
                  0 < jpx <= 1.0 + 1e-4 and (cj.par.winx.eval(), cj.par.winy.eval()) != (cam.par.winx.eval(), cam.par.winy.eval()) and u.chan('chan2')[20] == 1.0
                  and np.isfinite(a).all() and 0 < (d > 0.01).mean() < 0.2,
                  'jitter %.3f px, changed pixels %.3f' % (jpx / 2, (d > 0.01).mean()))
            T.store('base', arr(R.op('out1'))[::2, ::2, :3].copy())
            R.par.Bloom = 0.5; R.par.Autoexposure = True; R.par.Dof = True; R.par.Focusdistance = 0.5; R.par.Fstop = 1.4
            R.par.Motionblur = True; R.par.Shutter = 1.0
            run("args[0]()", m2c, delayFrames=30)
        except Exception:
            check('TAA', False, traceback.format_exc()); finish()
    def m2c():
        try:
            errs, bad = comp_errors(R)
            e = arr(R.op('ae_exposure'))[0, 0]; a = arr(R.op('out1'))[::2, ::2, :3]
            dof = arr(R.op('dof'))[..., :3]; src = arr(R.op('taa'))[..., :3]
            check('post: bloom, auto exposure, DOF, motion blur on',
                  not errs and not bad and np.isfinite(a).all() and np.isfinite(e).all() and 2 ** -6 * 0.99 <= e[1] <= 2 ** 4 * 1.01
                  and R.op('post_dof').par.index.eval() == 1 and R.op('post_mb').par.index.eval() == 1
                  and np.abs(dof - src).mean() > 0.003 and np.abs(a - T.fetch('base')).mean() > 0.002,
                  'exposure x%.3f (metered %.3f), DOF change %.4f, image change %.4f' % (e[1], e[2], np.abs(dof - src).mean(), np.abs(a - T.fetch('base')).mean()))
            R.op('out1').save(BT + '/out/test_post.jpg')
            # [BTDR:TEST.BLOOM] mip chain: 1/2 -> 1/128 and back, all levels finite, Switch on the chain
            W = R.par.Resolutionw.eval(); lv = [R.op('bloom_d%d' % k) for k in range(1, 7)]; bu = arr(R.op('bloom_u0'))[..., :3]
            check('bloom mip chain', all(lv) and lv[0].width == W // 4 and lv[-1].width == max(W // 128, 1)
                  and R.op('bloom_src').par.index.eval() == 1 and np.isfinite(bu).all() and bu.min() >= 0 and bu.max() > 0,
                  'levels %s, max %.3f' % ([o.width for o in lv if o], bu.max()))
            for k, v in T.fetch('post0').items(): setattr(R.par, k, v)
            run("args[0]()", m3a, delayFrames=15)
        except Exception:
            check('post', False, traceback.format_exc()); finish()
    # ---------------- [BTDR:TEST.M3] screen-space AO / bounce / reflections, volumetric fog, debug views
    def m3a():
        try:
            T.store('nofog', arr(R.op('out2'))[::2, ::2, :3].copy())
            T.store('n_m3b', R.op('uniforms').chan('chan1')[9])
            R.par.Fog = True; R.par.Fogdensity = 0.1; R.par.Heightfieldao = True
            run("args[0]()", m3b, delayFrames=25)
        except Exception:
            check('M3 setup', False, traceback.format_exc()); finish()
    def m3b():
        try:
            g = arr(R.op('ssgi_acc')); r = arr(R.op('ssr_acc'))
            hit = (arr(R.op('gbuf1'))[..., :3] ** 2).sum(-1) > 0.25
            ao = g[..., 3][hit[::max(1, hit.shape[0] // g.shape[0]), ::max(1, hit.shape[1] // g.shape[1])][:g.shape[0], :g.shape[1]]]
            check('screen-space AO, bounce light, reflections',
                  np.isfinite(g).all() and np.isfinite(r).all() and ao.min() < 0.8 and ao.mean() > 0.5 and r[..., 3].max() > 0.05
                  and R.op('ssgi_src').par.index.eval() == 1 and R.op('ssr_src').par.index.eval() == 1,
                  'AO min %.2f mean %.2f, bounce max %.3f, SSR confidence max %.2f (%.1f%% of pixels > 0.1)'
                  % (ao.min(), ao.mean(), g[..., :3].max(), r[..., 3].max(), (r[..., 3] > 0.1).mean() * 100))
            # [BTDR:TEST.STILLCAM] the test camera does not move: the uniforms must still advance every frame,
            # or every temporal history is reset each frame (0.3.1 bug, [BTDR:BUILD.UNICOOK])
            u = R.op('uniforms'); n0 = T.fetch('n_m3b', 0.0)
            check('still camera: frame index advances, histories kept',
                  u.chan('chan1')[9] >= n0 + 10 and u.chan('chan3')[9] == 0.0 and R.op('fog_accum') is not None,
                  'frame index %d -> %d, reset %.0f' % (n0, u.chan('chan1')[9], u.chan('chan3')[9]))
            # [BTDR:TEST.HFAO] height-field AO: top-down map holds the spheres (not the floor), result is finite
            hm = arr(R.op('hf_render'))[..., 0]; occ = (hm > 1e-4).mean(); cp = arr(R.op('composite'))[..., :3]
            check('height-field AO', R.op('hf_src').par.index.eval() == 1 and 0.001 < occ < 0.5 and np.isfinite(cp).all(),
                  'map %dx%d, occupied %.2f%%' % (hm.shape[1], hm.shape[0], occ * 100))
            f = arr(R.op('fog_apply'))[::2, ::2, :3]; fi = arr(R.op('fog_integrate'))
            check('volumetric fog', R.op('fog_src').par.index.eval() == 1 and np.isfinite(f).all() and np.isfinite(fi).all()
                  and 0.0 < fi[-1, ..., 3].mean() < 0.999 and np.abs(f - T.fetch('nofog')).mean() > 0.01,
                  'froxels %s, far transmittance %.3f, image change %.3f' % (fi.shape[:3], fi[-1, ..., 3].mean(), np.abs(f - T.fetch('nofog')).mean()))
            R.op('out1').save(BT + '/out/test_fog.jpg')
            R.par.Debugview = 'ssao'
            run("args[0]()", m3c, delayFrames=8)
        except Exception:
            check('M3', False, traceback.format_exc()); finish()
    def m3c():
        try:
            a = arr(R.op('out1'))[..., :3]
            R.par.Debugview = 'ssr'
            run("args[0](args[1])", m3d, a, delayFrames=8)
        except Exception:
            check('debug views', False, traceback.format_exc()); finish()
    def m3d(a_ao):
        try:
            a = arr(R.op('out1'))[..., :3]
            check('debug views: screen-space AO, reflections', R.op('view').par.index.eval() == 1 and np.isfinite(a_ao).all()
                  and a_ao.min() < a_ao.max() and np.isfinite(a).all() and a.max() > 0.0,
                  'AO view range %.2f-%.2f, SSR view max %.2f' % (a_ao.min(), a_ao.max(), a.max()))
            R.par.Debugview = 'final'; R.par.Fog = False; R.par.Fogdensity = 0.03
            R.par.Ambientocclusion = False; R.par.Ssgi = False; R.par.Ssr = False; R.par.Heightfieldao = False
            run("args[0]()", m3e, delayFrames=10)
        except Exception:
            check('debug views', False, traceback.format_exc()); finish()
    def m3e():
        try:
            check('screen-space and fog off: switches bypassed', R.op('ssgi_src').par.index.eval() == 0
                  and R.op('ssr_src').par.index.eval() == 0 and R.op('fog_src').par.index.eval() == 0
                  and R.op('hf_src').par.index.eval() == 0)
            R.par.Ambientocclusion = True; R.par.Ssgi = True; R.par.Ssr = True
            run("args[0]()", m4a, delayFrames=15)
        except Exception:
            check('M3 off', False, traceback.format_exc()); finish()
    # ---------------- [BTDR:TEST.M4] hardware ray tracing: proxy scene, probe GI, traced reflections, switches
    def m4a():
        try:
            out = R.op('rtscene/out'); ntri = out.numPrims()
            p0 = arr(R.op('probe_sh0')); rt = arr(R.op('rt_refl_top')); cp = arr(R.op('composite'))[..., :3]
            hitf = (np.abs(rt[..., :3] - 1.0).max(-1) > 1e-3).mean()
            u = R.op('uniforms'); rtu = [float(u[c][36]) for c in range(4)]
            check('ray tracing: proxy scene, probes, traced reflections',
                  R.par.Rtavailable.eval() and not R.op('rt_refl').errors() and not R.op('rt_probes').errors()
                  and ntri > 100 and 3 <= min(p0.shape[:3]) and max(p0.shape[:3]) <= 40 and 1000 <= int(np.prod(p0.shape[:3])) <= 4096 and np.isfinite(p0).all() and 0.3 < (p0[..., 3] > 0.5).mean() <= 1.0
                  and p0[..., :3].max() > 0.0 and np.isfinite(rt).all() and 0.0 < hitf < 1.0 and np.isfinite(cp).all()
                  and rtu[0] == 1.0 and rtu[1] == 1.0 and R.op('rt_src').par.index.eval() == 1 and R.op('probe_src0').par.index.eval() == 1,
                  'proxy %d triangles, probes %s valid %.0f%%, reflection hits %.1f%%, uRT %s'
                  % (ntri, p0.shape[:3], (p0[..., 3] > 0.5).mean() * 100, hitf * 100, rtu))
            # [BTDR:TEST.RTSTATIC] the probe pass must not cook every frame
            T.store('pc', R.op('rt_probes').totalCooks)
            R.par.Debugview = 'rtgi'
            run("args[0]()", m4b, delayFrames=10)
        except Exception:
            check('M4', False, traceback.format_exc()); finish()
    def m4b():
        try:
            a = arr(R.op('out1'))[..., :3]
            R.par.Debugview = 'rtrefl'
            run("args[0](args[1])", m4c, a, delayFrames=8)
        except Exception:
            check('M4 debug', False, traceback.format_exc()); finish()
    def m4c(a_gi):
        try:
            a = arr(R.op('out1'))[..., :3]
            pc = R.op('rt_probes').totalCooks - T.fetch('pc')
            check('ray tracing: debug views, probes static', np.isfinite(a_gi).all() and a_gi.max() > 0.02 and np.isfinite(a).all()
                  and a.max() > 0.02 and pc <= 1, 'probe GI view max %.2f, reflection view max %.2f, probe cooks in 18 frames: %d'
                  % (a_gi.max(), a.max(), pc))
            R.par.Debugview = 'final'; R.par.Raytracing = False
            run("args[0]()", m4d, delayFrames=10)
        except Exception:
            check('M4 debug', False, traceback.format_exc()); finish()
    def m4d():
        try:
            u = R.op('uniforms')
            check('ray tracing off: switches bypassed', R.op('rt_src').par.index.eval() == 0 and R.op('probe_src0').par.index.eval() == 0
                  and float(u[0][36]) == 0.0 and float(u[1][36]) == 0.0)
            R.par.Raytracing = True
            run("args[0]()", s9e, delayFrames=20)
        except Exception:
            check('M4 off', False, traceback.format_exc()); finish()
    def s9e():
        try:
            check('post off: switches bypassed', R.op('post_dof').par.index.eval() == 0 and R.op('post_mb').par.index.eval() == 0)
            T.store('ref', arr(R.op('out2'))[::4, ::4, :3])
            T.save(BT + '/out/test_scene.tox')
            T2 = op('/project1').loadTox(BT + '/out/test_scene.tox'); T2.name = 'btdr_test_reload'
            run("args[0](args[1])", s10, T2, delayFrames=25)
        except Exception:
            check('save', False, traceback.format_exc()); finish()
    def s10(T2):   # ---------------- save + reload
        try:
            Rr = T2.op('renderBTDR1')
            for k in ('out1', 'out2'): Rr.op(k).cook(force=True)
            st = Rr.fetch('status', {})
            geos = st.get('geometry', [])
            errs, bad = comp_errors(Rr)
            a = arr(Rr.op('out2'))[::4, ::4, :3]
            src = Rr.op('scene/g0').par.parentobject.eval()
            check('save + reload', st.get('mirrored') == 8 and all('btdr_test_reload' in g for g in geos) and not errs and not bad
                  and src is not None and 'btdr_test_reload' in src.path and np.abs(a - T.fetch('ref')).mean() < 0.01,
                  'mirrored %r, mirror follows %s, image diff vs original %.4f' % (st.get('mirrored'), src.path if src else None, np.abs(a - T.fetch('ref')).mean()))
            try: os.remove(BT + '/out/test_scene.tox')
            except Exception: pass
            finish()
        except Exception:
            check('save + reload', False, traceback.format_exc()); finish()
    open(BT + '/out/m1_tests.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
    run("args[0]()", s1, delayFrames=40)
except Exception:
    check('setup', False, traceback.format_exc()); finish()
