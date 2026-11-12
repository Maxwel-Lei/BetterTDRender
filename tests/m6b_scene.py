# [BTDR:FILE.TEST.M6BSCENE] m6b_scene.py — M6b blended transparency test scene: smoke cards (PBR MAT with Blending +
# an alpha map, picked up automatically), glowing particles (instanced spheres, Blended slot, Additive), a hologram
# box (Blended slot, Additive, unlit) and a glass ball (Refractive slot) with smoke behind it.
# Run: exec(open(project.folder + '/btdr/tests/m6b_scene.py', encoding='utf-8').read())
# Optional: M6_SHOT = 'tag' -> after M6_WAIT frames saves btdr/out/m6b_<tag>.jpg and out/m6b_log.txt
import os
BT = project.folder + '/btdr'
P = op('/project1')
if P.op('m6b_test'): P.op('m6b_test').destroy()
T = P.create(baseCOMP, 'm6b_test'); T.nodeX, T.nodeY = 200, -1200

def geo(name, sop, x, y, z, mat, sx=1, sy=1, sz=1, **kw):
    g = T.create(geometryCOMP, name)
    for c in list(g.children): c.destroy()
    s = g.create(sop, 'shape')
    for k, v in kw.items(): setattr(s.par, k, v)
    s.render = True; s.display = True
    g.par.tx, g.par.ty, g.par.tz = x, y, z
    g.par.sx, g.par.sy, g.par.sz = sx, sy, sz
    g.par.material = mat
    return g

def pbr(name, rgb, rough=0.5, metal=0.0, alpha=1.0, emit=None):
    m = T.create(pbrMAT, name)
    m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = rgb
    m.par.roughness = rough; m.par.metallic = metal; m.par.alphafront = alpha
    if emit: m.par.emitr, m.par.emitg, m.par.emitb = emit
    return m

# soft round smoke sprite: radial ramp x noise
ramp = T.create(rampTOP, 'smoke_ramp'); ramp.par.type = 'circular'
ramp.par.extendleft = 'hold'; ramp.par.extendright = 'hold'     # the default repeats: rings in the corners
ramp.par.outputresolution = 'custom'; ramp.par.resolutionw = ramp.par.resolutionh = 256
for d in ramp.docked:                               # keys: white centre -> clear at the edge
    if d.isDAT and d.numRows > 1:
        d.clear(); d.appendRow(['pos', 'r', 'g', 'b', 'a'])
        d.appendRow([0.0, 1, 1, 1, 1]); d.appendRow([0.9, 0, 0, 0, 1]); d.appendRow([1.0, 0, 0, 0, 1])
noise = T.create(noiseTOP, 'smoke_noise'); noise.par.outputresolution = 'custom'
noise.par.resolutionw = noise.par.resolutionh = 256; noise.par.period = 0.6; noise.par.harmon = 4
noise.par.amp = 0.5; noise.par.offset = 0.5
mul = T.create(multiplyTOP, 'smoke_tex')
ramp.outputConnectors[0].connect(mul.inputConnectors[0]); noise.outputConnectors[0].connect(mul.inputConnectors[1])

floor_m = pbr('m_floor', (0.5, 0.5, 0.52), 0.55)
geo('floor', boxSOP, 0, -0.025, 0, floor_m, sizex=14, sizey=0.05, sizez=14)
geo('pillar', boxSOP, -0.6, 1.2, -1.6, pbr('m_pillar', (0.7, 0.68, 0.64), 0.6), sizex=0.5, sizey=2.4, sizez=0.5)
cols = [(0.8, 0.15, 0.1), (0.15, 0.5, 0.9), (0.9, 0.75, 0.2)]
for i, c in enumerate(cols):
    geo('box%d' % i, boxSOP, -2.0 + i * 2.0, 0.4, -3.0, pbr('m_box%d' % i, c, 0.4), sizex=0.8, sizey=0.8, sizez=0.8)

# smoke cards: PBR MAT with Blending on and an alpha map -> blended automatically ([BTDR:EXT.TRANSCLASS])
smoke = pbr('m_smoke', (0.85, 0.85, 0.88), 1.0, alpha=0.55)
smoke.par.alphamap = mul; smoke.par.blending = True
for i, (x, y, z, s) in enumerate([(-1.8, 0.7, -1.0, 1.6), (-0.9, 1.0, -0.6, 1.9), (0.2, 0.8, -1.2, 1.7),
                                  (1.2, 1.1, -0.8, 1.8), (-1.2, 0.5, 0.2, 1.4), (1.6, 0.6, -0.2, 1.5), (0.3, 1.4, -2.2, 2.2)]):
    g = geo('smoke%d' % i, gridSOP, x, y, z, smoke, rows=2, cols=2, sizex=s, sizey=s)
    g.par.rz = i * 47

# glowing particles: instanced small spheres from a point cloud, Additive slot
pm = pbr('m_spark', (0, 0, 0), 1.0, emit=(3.0, 1.4, 0.4))
sp = geo('sparks', sphereSOP, 0, 0, 0, pm, type='poly', freq=2, radx=0.03, rady=0.03, radz=0.03)
pts = T.create(sphereSOP, 'spark_pts'); pts.par.type = 'poly'; pts.par.freq = 6
pts.par.radx, pts.par.rady, pts.par.radz = 1.4, 0.6, 1.0
pts.par.ty = 1.1
sp.par.instancing = True; sp.par.instanceop = pts
for c, i in zip(('tx', 'ty', 'tz'), (0, 1, 2)):
    try: setattr(sp.par, 'instance' + c, 'P(%d)' % i)
    except Exception: pass

# hologram: unlit additive box in a Blended slot
holo = pbr('m_holo', (0, 0, 0), 1.0, alpha=0.35, emit=(0.2, 1.2, 1.6))
geo('holo', boxSOP, 1.9, 0.75, 0.6, holo, sizex=0.6, sizey=1.5, sizez=0.6)
# glass ball in front of a smoke card
glass = pbr('m_glass', (0.97, 0.98, 1.0), 0.03, alpha=0.0)
geo('glass_ball', sphereSOP, -0.4, 0.5, 0.9, glass, type='poly', freq=20, radx=0.45, rady=0.45, radz=0.45)

cam = T.create(cameraCOMP, 'cam1'); cam.par.tx, cam.par.ty, cam.par.tz = 0.2, 1.4, 5.0; cam.par.rx = -10; cam.par.fov = 50
lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx, lt.par.ry = -35, 60
try: lt.par.shadowtype = 'off'
except Exception: pass

R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
R.par.Geometry = 'floor pillar box* smoke* sparks'
R.par.Bloom = 0.15
getattr(R.par, 'Refr0geo').val = 'glass_ball'
R.seq.Blend.numBlocks = 2
R.par.Blend0geo = 'sparks'; R.par.Blend0mode = 'additive'; R.par.Blend0lit = False
R.par.Blend1geo = 'holo'; R.par.Blend1mode = 'additive'; R.par.Blend1lit = False
R.Refresh()
o = T.create(nullTOP, 'OUT'); R.outputConnectors[0].connect(o)
ex = T.create(executeDAT, 'keep_cooking')
ex.text = "def onFrameStart(frame):\n\top('/project1/m6b_test/OUT').cook(force=True)\n\treturn\n"
ex.par.framestart = True; ex.par.active = True

_tag = globals().get('M6_SHOT')
if _tag:
    _w = globals().get('M6_WAIT', 60)
    def _shot(tag=_tag):
        op('/project1/m6b_test/OUT').save(BT + '/out/m6b_%s.jpg' % tag, quality=0.92)
        R_ = op('/project1/m6b_test/renderBTDR1')
        lines = ['status %s' % R_.par.Status.eval(), 'blendcount %s transcount %s' % (R_.par.Blendcount.eval(), R_.par.Transcount.eval())]
        for o_ in R_.findChildren():
            e = o_.errors(); w = o_.warnings()
            if e: lines.append('ERR %s %s' % (o_.path, e[:600]))
            if w and 'Uniform' not in w: lines.append('WARN %s %s' % (o_.path, w[:200]))
        open(BT + '/out/m6b_log.txt', 'w', encoding='utf-8').write('\n'.join(lines))
    run('args[0]()', _shot, delayFrames=_w)
