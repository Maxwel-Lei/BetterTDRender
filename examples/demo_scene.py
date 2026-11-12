# [BTDR:FILE.DEMO] Example scene for BetterTDRender.
# Run inside TouchDesigner:  exec(open(project.folder + '/btdr/examples/demo_scene.py', encoding='utf-8').read())
# Builds /project1/btdr_demo: native Camera, Light, Geometry COMPs with PBR MATs, and one renderBTDR.
# Models: the open test models in 测试模型/ (AntiqueCamera + FlightHelmet, see [BTDR:DEMO.TESTMODELS]);
# without them, the relic models in 模型_简化 next to the .toe (or the first folder there that directly contains .obj files).
# Textures beside each model, by name: <name>_basecolor_4k.jpg, <name>_ao.png, and when present
# <name>_roughness.*, <name>_metallic.*, <name>_normal.* (OpenGL / Y+ convention).
# All textures live in one shared library COMP, /project1/tex_lib (bc_i, ao_i, rough_i, metal_i, nrm_i),
# so other scenes in the project can reuse them without loading a second copy.
import os, math, traceback

PF = project.folder.replace('\\', '/')
BT = PF + '/btdr'
DLOG = []
try:
    root = op('/project1')
    if root.op('btdr_demo'): root.op('btdr_demo').destroy()
    S = root.create(baseCOMP, 'btdr_demo')
    S.nodeX, S.nodeY = 300, -250
    def place(o, x, y):
        o.nodeX, o.nodeY = x, y
        return o

    cands = [n for n in sorted(os.listdir(PF)) if os.path.isdir(PF + '/' + n) and n not in ('btdr', 'ue5r')
             and any(f.lower().endswith('.obj') for f in os.listdir(PF + '/' + n))]
    mdir = '模型_简化' if '模型_简化' in cands else cands[0]
    objs = sorted(f for f in os.listdir(PF + '/' + mdir) if f.lower().endswith('.obj'))
    n = len(objs)

    # [BTDR:DEMO.TEXLIB] shared texture library
    lib = root.op('tex_lib') or root.create(baseCOMP, 'tex_lib')
    lib.nodeX, lib.nodeY = 300, -450
    files = os.listdir(PF + '/' + mdir)
    def find(stem, kind):
        # [BTDR:DEMO.GILT] a corrected map named <stem>_<kind>_gilt.* wins over the original (see IMPLEMENTATION §11c)
        for f in sorted(files):
            if f.startswith(stem + '_' + kind + '_gilt') and f.lower().endswith(('.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff')):
                return PF + '/' + mdir + '/' + f
        for f in sorted(files):
            if f.startswith(stem + '_' + kind) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff')):
                return PF + '/' + mdir + '/' + f
        return None
    def tex(name, path, x, y):
        t = lib.op(name) or lib.create(moviefileinTOP, name)
        if t.par.file.eval() != path: t.par.file = path
        t.nodeX, t.nodeY = x, y
        return t
    # fallback when a model has no roughness map: roughness from base colour brightness
    rf = place(S.create(textDAT, 'rough_frag'), -600, 500)
    rf.text = ('out vec4 fragColor;\nvoid main()\n{\n    vec3 t = pow(max(texture(sTD2DInputs[0], vUV.st).rgb, 0.0), vec3(2.2));\n'
               '    float luma = dot(t, vec3(0.2126, 0.7152, 0.0722));\n    float r = mix(0.75, 0.22, smoothstep(0.02, 0.45, luma));\n'
               '    fragColor = vec4(r, r, r, 1.0);\n}\n')
    # [BTDR:DEMO.TESTMODELS] default scene: open test models from 测试模型/ (Khronos glTF Sample Assets, CC0,
    # converted by tools/gltf2obj.py). One Geometry COMP + PBR MAT per material part; each model is scaled to a
    # target height and placed side by side. Falls back to the old relic models in 模型_简化 when missing.
    TESTSET = [('AntiqueCamera', 1.5, -0.55, 0.0, 25.0), ('FlightHelmet', 0.95, 0.6, 0.15, -20.0)]   # name, height, x, z, ry
    TM = PF + '/测试模型'
    use_test = all(os.path.exists(TM + '/' + t[0] + '/convert_report.json') for t in TESTSET)
    if use_test:
        import json
        n = 0
        for mname, height, mx, mz, mry in TESTSET:
            rep = json.load(open(TM + '/' + mname + '/convert_report.json', encoding='utf-8'))
            lo = [min(r['bbox'][0][k] for r in rep) for k in range(3)]
            hi = [max(r['bbox'][1][k] for r in rep) for k in range(3)]
            sc = height / max(hi[1] - lo[1], 1e-6)
            cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
            for k, r in enumerate(rep):
                i = n; n += 1
                y = 300 - i * 200
                m = place(S.create(pbrMAT, 'pbr_%d' % i), -200, y)
                f = r['factors']
                def tmap(kind, x):
                    return tex('tm_%d_%s' % (i, kind), TM + '/%s/%s_%s.png' % (mname, r['name'], kind), x, -i * 150)
                if 'basecolor' in r['maps']: m.par.basecolormap = tmap('basecolor', 0)
                if f.get('base'): m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = f['base'][:3]
                if 'roughness' in r['maps']: m.par.roughnessmap = tmap('roughness', 150)
                m.par.roughness = f['rough'] if f.get('rough') is not None else 1
                if 'metallic' in r['maps']: m.par.metallicmap = tmap('metallic', 300)
                m.par.metallic = f['metal'] if f.get('metal') is not None else 1
                if 'ao' in r['maps']: m.par.ambientocclusionmap = tmap('ao', 450)
                if 'normal' in r['maps']: m.par.normalmap = tmap('normal', 600); m.par.bumpscale = 1
                if 'emissive' in r['maps']:
                    m.par.emitmap = tmap('emissive', 750); m.par.emitr, m.par.emitg, m.par.emitb = (f.get('emissive') or [1, 1, 1])[:3]
                g = place(S.create(geometryCOMP, 'geo_%d' % i), 0, y)
                for c in list(g.children): c.destroy()
                so = g.create(fileinSOP, 'obj'); so.par.file = TM + '/%s/%s.obj' % (mname, r['name'])
                # tangents (MikkTSpace) for TD's native PBR MAT normal mapping; BTDR does not need them
                ta = g.create(attributecreateSOP, 'tangents'); ta.par.comptang = True; ta.par.mikktspace = True
                so.outputConnectors[0].connect(ta); ta.nodeY = so.nodeY - 120
                ta.render = True; ta.display = True
                g.par.material = m
                # pivot at the model's footprint centre, so scale / rotate keep it standing on the floor at (mx, mz)
                g.par.px, g.par.py, g.par.pz = cx, lo[1], cz
                g.par.tx, g.par.ty, g.par.tz = mx - cx, -lo[1], mz - cz
                g.par.scale = sc; g.par.ry = mry
                DLOG.append('%s / %s: %s' % (mname, r['name'], ', '.join(r['maps'])))
    else:
        for i, f in enumerate(objs):
            stem = f[:-4]
            y = 300 - i * 250
            m = place(S.create(pbrMAT, 'pbr_%d' % i), -200, y)
            bc = tex('bc_%d' % i, find(stem, 'basecolor'), 0, -i * 150)
            m.par.basecolormap = bc
            p = find(stem, 'ao')
            if p: m.par.ambientocclusionmap = tex('ao_%d' % i, p, 150, -i * 150)
            p = find(stem, 'roughness')
            if p:
                m.par.roughnessmap = tex('rough_%d' % i, p, 300, -i * 150); m.par.roughness = 1
            else:
                ro = place(S.create(glslTOP, 'rough_%d' % i), -400, y)
                ro.par.pixeldat = rf
                ro.par.outputresolution = 'custom'; ro.par.resolutionw = ro.par.resolutionh = 2048
                bc.outputConnectors[0].connect(ro)
                m.par.roughnessmap = ro; m.par.roughness = 1
            p = find(stem, 'metallic')
            if p:
                m.par.metallicmap = tex('metal_%d' % i, p, 450, -i * 150); m.par.metallic = 1
            else:
                m.par.metallic = 1          # the test relics are mostly metal
            p = find(stem, 'normal')
            if p:
                m.par.normalmap = tex('nrm_%d' % i, p, 600, -i * 150); m.par.bumpscale = 0.2  # Tripo 法线贴图会重复叠加起伏，见 IMPLEMENTATION §11c
            DLOG.append('%s: %s' % (stem, ', '.join(k for k in ('ao', 'roughness', 'metallic', 'normal') if find(stem, k)) or 'base colour only'))
            g = place(S.create(geometryCOMP, 'geo_%d' % i), 0, y)
            for c in list(g.children): c.destroy()
            s = g.create(fileinSOP, 'obj'); s.par.file = PF + '/' + mdir + '/' + f
            s.render = True; s.display = True
            g.par.material = m
            g.par.tx = (i - (n - 1) / 2.0) * 0.95
            g.par.ry = -90
    mf = place(S.create(pbrMAT, 'pbr_floor'), -200, 300 - n * 250)
    mf.par.basecolorr, mf.par.basecolorg, mf.par.basecolorb = 0.2, 0.2, 0.205
    mf.par.metallic = 0; mf.par.roughness = 0.38
    fl = place(S.create(geometryCOMP, 'floor'), 0, 300 - n * 250)
    for c in list(fl.children): c.destroy()
    gs = fl.create(gridSOP, 'grid'); gs.par.orient = 'zx'; gs.par.sizex = gs.par.sizey = 30
    gs.render = True; gs.display = True
    fl.par.material = mf

    # camera looking at a target null; move or animate cam1 freely
    tgt = place(S.create(nullCOMP, 'target'), 250, 400)
    tgt.par.ty = 0.62 if use_test else 0.42
    cam = place(S.create(cameraCOMP, 'cam1'), 250, 300)
    cam.par.lookat = tgt
    cam.par.tx, cam.par.ty, cam.par.tz = (1.1, 1.15, 3.4) if use_test else (1.5, 1.15, 4.3)
    cam.par.fov = 45; cam.par.near, cam.par.far = 0.05, 100
    light = place(S.create(lightCOMP, 'light1'), 250, 150)
    light.par.lighttype = 'distant'
    light.par.rx, light.par.ry = -45.2569, 47.7263
    light.par.tx, light.par.ty, light.par.tz = 5.2, 7.5, 4.7
    light.par.cr, light.par.cg, light.par.cb = 1.0, 0.94, 0.84
    light.par.dimmer = 1.59155

    R = S.loadTox(BT + '/release/BTDR.tox')
    R.name = 'renderBTDR1'
    place(R, 500, 300)
    R.par.Camera = 'cam1'; R.par.Geometry = 'geo_* floor'; R.par.Lights = 'light1'
    R.par.Fadestart, R.par.Fadeend = 6.0, 12.0
    R.par.Exposure = 0.5
    # [BTDR:DEMO.HDRI] use the bundled HDRI (Poly Haven, CC0) when present. Envrotate turns the HDRI so its sun
    # (u = 0.600, 43 deg up) lines up with light1 (rx -45.3, ry 47.7): reflections, sky and shadows agree.
    hd = BT + '/examples/hdri/kloofendal_43d_clear_2k.hdr'
    if os.path.exists(hd):
        hf = place(S.create(moviefileinTOP, 'hdri_file'), 500, 150)
        hf.par.file = hd
        R.par.Envsource = 'hdri'; R.par.Envmap = hf
        R.par.Envrotate = -96.2
        R.par.Background = 'env'; R.par.Bgblur = 0.1
    out = place(S.create(nullTOP, 'OUT'), 700, 300)
    # [BTDR:DEMO.NATIVE] TD's own Render TOP on the very same Geometry COMPs, materials and textures (no extra
    # texture memory): the comparison case for tools/perf_bench.py. Only cooks while something pulls native_out.
    light.par.shadowtype = 'soft2d'; light.par.maxshadowsoftness = 0.1
    light.par.shadowresolution1 = light.par.shadowresolution2 = 4096
    envl = place(S.create(environmentlightCOMP, 'envlight'), 250, 0)
    if os.path.exists(hd):
        envl.par.envlightmap = hf; envl.par.envlightmaptype2d = 'equirect'
    nat = place(S.create(renderTOP, 'native_render'), 500, 0)
    nat.par.camera = 'cam1'; nat.par.geometry = 'geo_* floor'; nat.par.lights = 'light1 envlight'
    nat.par.outputresolution = 'custom'; nat.par.resolutionw, nat.par.resolutionh = 1920, 1080
    nout = place(S.create(nullTOP, 'native_out'), 700, 0)
    nat.outputConnectors[0].connect(nout)
    R.outputConnectors[0].connect(out)
    out.viewer = True
    DLOG.append('demo built: %d material parts from %s' % (n, '测试模型 (' + ', '.join(t[0] for t in TESTSET) + ')' if use_test else mdir))

    def post():
        try:
            w = R.Refresh()
            DLOG.append('refresh warnings: %r' % (w,))
            DLOG.append('status: %r' % (R.fetch('status', None),))
            run("args[0]()", post2, delayFrames=60)
        except Exception:
            DLOG.append(traceback.format_exc()); flush('ERROR')
    def post2():
        try:
            infos = []
            for o in R.findChildren():
                e, w = o.errors(), o.warnings()
                if e: DLOG.append('ERR  %s: %s' % (o.path, e))
                if w: DLOG.append('WARN %s: %s' % (o.path, w))
                if o.OPType in ('glslmultiTOP', 'glslMAT'):
                    inf = S.create(infoDAT, 'tmpinfo_%d' % len(infos)); inf.par.op = o.path; infos.append((o, inf))
            for o, inf in infos:
                t = inf.text
                if 'rror' in t: DLOG.append('--- compile %s ---\n%s' % (o.path, t[:2500]))
                inf.destroy()
            os.makedirs(BT + '/out', exist_ok=True)
            out.save(BT + '/out/demo.jpg')
            for nm in ('gbuf0', 'gbuf1', 'shadow', 'env_src', 'lighting'):
                try: R.op(nm).save(BT + '/out/dbg_%s.jpg' % nm)
                except Exception as ex: DLOG.append('save %s %r' % (nm, ex))
            tops = [o for o in R.findChildren(depth=1) if o.family == 'TOP']
            DLOG.append('gpu ms: total %.2f | %s' % (sum(o.gpuCookTime for o in tops),
                        ', '.join('%s %.2f' % (o.name, o.gpuCookTime) for o in sorted(tops, key=lambda o: -o.gpuCookTime)[:8])))
            DLOG.append('cpu ms: uniforms %.3f, component total %.3f' % (R.op('uniforms').cookTime, sum(o.cookTime for o in R.findChildren())))
            flush('DONE')
        except Exception:
            DLOG.append(traceback.format_exc()); flush('ERROR')
    def flush(status):
        open(BT + '/out/demo_log.txt', 'w', encoding='utf-8').write('STATUS %s\n' % status + '\n'.join(DLOG))
    flush('BUILDING')
    run("args[0]()", post, delayFrames=30)
except Exception:
    DLOG.append(traceback.format_exc())
    open(BT + '/out/demo_log.txt', 'w', encoding='utf-8').write('STATUS ERROR\n' + '\n'.join(DLOG))
