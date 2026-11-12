# [BTDR:FILE.TOOL.PREVIEW] Load one converted test model (测试模型/<name>, from tools/gltf2obj.py) into
# /project1/btdr_models/<name>: one Geometry COMP + PBR MAT per OBJ, camera framed on the bounding box, the demo HDRI,
# a floor and a renderBTDR. Saves btdr/out/preview_<name>.jpg after ~40 frames.
# Run: MODEL = 'DamagedHelmet'; exec(open(project.folder + '/btdr/tools/model_preview.py', encoding='utf-8').read())
import os, json, math
_PF = project.folder.replace('\\', '/')
_DIR = _PF + '/测试模型/' + MODEL
_rep = json.load(open(_DIR + '/convert_report.json', encoding='utf-8'))
_root = op('/project1').op('btdr_models') or op('/project1').create(baseCOMP, 'btdr_models')
_root.nodeX, _root.nodeY = 900, -600
if _root.op(MODEL): _root.op(MODEL).destroy()
S = _root.create(baseCOMP, MODEL)
S.nodeX = 200 * (len(_root.children) - 1)
lo = [min(r['bbox'][0][k] for r in _rep) for k in range(3)]
hi = [max(r['bbox'][1][k] for r in _rep) for k in range(3)]
ctr = [(lo[k] + hi[k]) / 2 for k in range(3)]
size = max(hi[k] - lo[k] for k in range(3))
for i, r in enumerate(_rep):
    n = r['name']
    m = S.create(pbrMAT, 'm_%d' % i); m.nodeX, m.nodeY = -300, -i * 150
    def tex(kind):
        t = S.create(moviefileinTOP, '%s_%d' % (kind, i)); t.par.file = _DIR + '/%s_%s.png' % (n, kind)
        t.nodeX, t.nodeY = -600 - 150 * ['basecolor', 'roughness', 'metallic', 'ao', 'normal', 'emissive'].index(kind), -i * 150
        return t
    f = r['factors']
    if 'basecolor' in r['maps']: m.par.basecolormap = tex('basecolor')
    if f.get('base'): m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = f['base'][:3]
    if 'roughness' in r['maps']: m.par.roughnessmap = tex('roughness')
    m.par.roughness = f['rough'] if f.get('rough') is not None else 1
    if 'metallic' in r['maps']: m.par.metallicmap = tex('metallic')
    m.par.metallic = f['metal'] if f.get('metal') is not None else 1
    if 'ao' in r['maps']: m.par.ambientocclusionmap = tex('ao')
    if 'normal' in r['maps']: m.par.normalmap = tex('normal'); m.par.bumpscale = 1
    if 'emissive' in r['maps']:
        m.par.emitmap = tex('emissive'); m.par.emitr, m.par.emitg, m.par.emitb = (f.get('emissive') or [1, 1, 1])[:3]
    elif any((f.get('emissive') or [0, 0, 0])[:3]):      # constant emission without a map (car lights, LEDs)
        m.par.emitr, m.par.emitg, m.par.emitb = f['emissive'][:3]
    g = S.create(geometryCOMP, 'geo_%d' % i); g.nodeX, g.nodeY = 0, -i * 150
    for c in list(g.children): c.destroy()
    s = g.create(fileinSOP, 'obj'); s.par.file = _DIR + '/' + n + '.obj'; s.render = s.display = True
    g.par.material = m
fl = S.create(geometryCOMP, 'floor'); fl.nodeX, fl.nodeY = 0, 150
for c in list(fl.children): c.destroy()
gs = fl.create(gridSOP, 'grid'); gs.par.orient = 'zx'; gs.par.sizex = gs.par.sizey = size * 20
gs.par.ty = lo[1]; gs.render = gs.display = True
mf = S.create(pbrMAT, 'm_floor'); mf.par.basecolorr = mf.par.basecolorg = mf.par.basecolorb = 0.2; mf.par.metallic = 0; mf.par.roughness = 0.4
fl.par.material = mf
tgt = S.create(nullCOMP, 'target'); tgt.par.tx, tgt.par.ty, tgt.par.tz = ctr
cam = S.create(cameraCOMP, 'cam1'); cam.par.lookat = tgt; cam.par.fov = 35
d = size * 2.8
cam.par.tx, cam.par.ty, cam.par.tz = ctr[0] + d * 0.45, ctr[1] + d * 0.25, ctr[2] + d * 0.85
cam.par.near, cam.par.far = size * 0.01, size * 60
L = S.create(lightCOMP, 'light1'); L.par.lighttype = 'distant'; L.par.rx, L.par.ry = -45.2569, 47.7263
L.par.cr, L.par.cg, L.par.cb = 1.0, 0.94, 0.84; L.par.dimmer = 1.59155
hf = S.create(moviefileinTOP, 'hdri_file'); hf.par.file = _PF + '/btdr/examples/hdri/kloofendal_43d_clear_2k.hdr'
R = S.loadTox(_PF + '/btdr/release/BTDR.tox'); R.name = 'renderBTDR1'; R.nodeX, R.nodeY = 400, 0
R.par.Camera = 'cam1'; R.par.Geometry = 'geo_* floor'; R.par.Lights = 'light1'
R.par.Envsource = 'hdri'; R.par.Envmap = hf; R.par.Envrotate = -96.2; R.par.Background = 'env'; R.par.Bgblur = 0.1
R.par.Exposure = 0.5; R.par.Fadestart, R.par.Fadeend = size * 3, size * 6
out = S.create(nullTOP, 'OUT'); out.nodeX, out.nodeY = 600, 0; R.outputConnectors[0].connect(out)
S.store('model', MODEL)
op('/').time.play = True
def _save(Sc=S):
    Sc.op('renderBTDR1').Refresh()
    run("args[0]()", lambda: Sc.op('OUT').save(_PF + '/btdr/out/preview_%s.jpg' % Sc.name), delayFrames=20)
run("args[0]()", _save, delayFrames=20)
