# [BTDR:FILE.TEST.M6SCENE] m6_scene.py — M6a transparency test scene: glass sphere, frosted panel, tinted cube,
# water block and a single-sided window in front of coloured boxes, rendered by release/BTDR.tox.
# Run: exec(open(project.folder + '/btdr/tests/m6_scene.py', encoding='utf-8').read())
# Optional: M6_SHOT = 'tag' -> after M6_WAIT frames saves btdr/out/m6_<tag>.jpg (and _dbg views if M6_VIEWS is set)
import os
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
P = op('/project1')
if P.op('m6_test'): P.op('m6_test').destroy()
T = P.create(baseCOMP, 'm6_test'); T.nodeX, T.nodeY = 0, -1200

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

floor_m = pbr('m_floor', (0.55, 0.55, 0.58), 0.6)
geo('floor', boxSOP, 0, -0.025, 0, floor_m, sizex=12, sizey=0.05, sizez=12)
cols = [(0.8, 0.1, 0.1), (0.95, 0.6, 0.1), (0.9, 0.9, 0.15), (0.15, 0.7, 0.2), (0.1, 0.4, 0.9), (0.6, 0.2, 0.8)]
for i, c in enumerate(cols):         # coloured boxes behind the glass: the refraction must bend them
    geo('box%d' % i, boxSOP, -2.5 + i, 0.6, -2.0, pbr('m_box%d' % i, c, 0.4), sizex=0.5, sizey=1.2, sizez=0.5)
geo('stripes', boxSOP, 0, 1.6, -2.6, pbr('m_back', (0.85, 0.85, 0.85), 0.7), sizex=7, sizey=3.2, sizez=0.1)

glass = pbr('m_glass', (0.97, 0.98, 1.0), 0.03, alpha=0.0)
frost = pbr('m_frost', (0.95, 0.95, 0.95), 0.05, alpha=0.0)
tint = pbr('m_tint', (0.35, 0.8, 0.45), 0.03, alpha=0.0)
water = pbr('m_water', (0.55, 0.8, 0.95), 0.02, alpha=0.0)
win = pbr('m_window', (0.9, 0.95, 1.0), 0.02, alpha=0.0)
geo('glass_ball', sphereSOP, -1.6, 0.55, 0.0, glass, type='polygon', freq=20, radx=0.55, rady=0.55, radz=0.55)
geo('frost_panel', boxSOP, -0.3, 0.6, 0.2, frost, sizex=0.9, sizey=1.2, sizez=0.06)
geo('tint_cube', boxSOP, 0.9, 0.35, 0.1, tint, sizex=0.6, sizey=0.7, sizez=0.6)
geo('water_block', boxSOP, 2.1, 0.3, 0.0, water, sizex=0.8, sizey=0.6, sizez=0.8)
geo('window', gridSOP, 0.3, 1.5, 0.9, win, rows=2, cols=2, sizex=1.4, sizey=0.6)   # single-sided sheet (faces +Z)

cam = T.create(cameraCOMP, 'cam1'); cam.par.tx, cam.par.ty, cam.par.tz = 0.3, 1.5, 5.2; cam.par.rx = -12; cam.par.fov = 50
lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.rx, lt.par.ry = -50, 35
try: lt.par.shadowtype = 'off'
except Exception: pass

R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
R.par.Geometry = 'floor box* stripes'                        # glass only arrives through the Refractive slots
slots = [('glass_ball', 'glass'), ('frost_panel', 'frosted'), ('tint_cube', 'tinted'), ('water_block', 'water'), ('window', 'window')]
R.seq.Refr.numBlocks = len(slots)
for i, (g, pre) in enumerate(slots):
    getattr(R.par, 'Refr%dgeo' % i).val = g
    getattr(R.par, 'Refr%dpreset' % i).val = pre
    R.ApplyPreset(i)
R.Refresh()
o = T.create(nullTOP, 'OUT'); R.outputConnectors[0].connect(o)
ex = T.create(executeDAT, 'keep_cooking')
ex.text = "def onFrameStart(frame):\n\top('/project1/m6_test/OUT').cook(force=True)\n\treturn\n"
ex.par.framestart = True; ex.par.active = True

_tag = globals().get('M6_SHOT')
if _tag:
    _w = globals().get('M6_WAIT', 60)
    def _shot(tag=_tag):
        op('/project1/m6_test/OUT').save(BT + '/out/m6_%s.jpg' % tag, quality=0.92)
        R_ = op('/project1/m6_test/renderBTDR1')
        lines = ['status %s' % R_.par.Status.eval(), 'transcount %s' % R_.par.Transcount.eval()]
        for o_ in R_.findChildren():
            e = o_.errors(); w = o_.warnings()
            if e: lines.append('ERR %s %s' % (o_.path, e[:300]))
            if w and 'Uniform' not in w: lines.append('WARN %s %s' % (o_.path, w[:200]))
        open(BT + '/out/m6_log.txt', 'w', encoding='utf-8').write('\n'.join(lines))
    run('args[0]()', _shot, delayFrames=_w)
