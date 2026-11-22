# [BTDR:FILE.TEST.M8SHOW] m8_showcase.py — subsurface comparison renders (jade Buddha, white-jade beast).
# Run: MODELS = '<folder with the .obj files>'; exec(open(project.folder + '/btdr/tests/m8_showcase.py', encoding='utf-8').read())
# Result: btdr/out/sss_<shot>_<on|off>.jpg, btdr/out/m8_showcase.txt. The scene /project1/sss_show stays for inspection.
import traceback
BT = globals().get('BTDR_SRC', project.folder + '/btdr')   # BTDR_SRC: run from another project (0.9.6)
LOG = []
def log(s):
    LOG.append(s); open(BT + '/out/m8_showcase.txt', 'w', encoding='utf-8').write('\n'.join(LOG))
def step(fn, frames):
    def wrapped():
        try:
            fn()
        except Exception:
            log('ERROR\n' + traceback.format_exc())
    run("args[0]()", wrapped, delayFrames=frames)

try:
    log('STATUS RUNNING')
    P = op('/project1')
    if P.op('sss_show'): P.op('sss_show').destroy()
    T = P.create(baseCOMP, 'sss_show'); T.nodeX, T.nodeY = 2600, -1200
    op('/local/time').play = True
    def pbr(nm, c, rough):
        m = T.create(pbrMAT, nm); m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = c
        m.par.metallic = 0; m.par.roughness = rough
        return m
    def model(nm, f, mat):
        g = T.create(geometryCOMP, nm)
        for c in list(g.children): c.destroy()
        fi = g.create(fileinSOP, 'file'); fi.par.file = MODELS + '/' + f
        fi.render = fi.display = True
        g.par.material = mat
        return g, fi
    buddha, bf = model('buddha', '鎏金铜造像.obj', pbr('m_jade', (0.32, 0.62, 0.40), 0.22))
    beast, sf = model('beast', '鎏金铜兽形饰.obj', pbr('m_whitejade', (0.86, 0.84, 0.76), 0.3))
    floor = T.create(geometryCOMP, 'floor')
    for c in list(floor.children): c.destroy()
    fb = floor.create(boxSOP, 'box'); fb.render = fb.display = True
    floor.par.sx, floor.par.sy, floor.par.sz = 3, 0.02, 3; floor.par.ty = -0.01
    floor.par.material = pbr('m_floor', (0.08, 0.08, 0.09), 0.35)
    cam = T.create(cameraCOMP, 'cam1')
    lt = T.create(lightCOMP, 'light1'); lt.par.lighttype = 'distant'; lt.par.shadowtype = 'off'
    lt.par.dimmer = 2.5

    def fit():
        # scale each model to a real carving size and stand it on the floor
        for g, s, h, x in ((buddha, bf, 0.30, -0.05), (beast, sf, 0.12, 0.26)):
            s.cook(force=True)
            b = s.computeBounds()
            k = h / max(b.size.y, 1e-6)
            g.par.sx = g.par.sy = g.par.sz = k
            g.par.tx = x - b.center.x * k; g.par.tz = -b.center.z * k; g.par.ty = -b.min.y * k
        log('bounds buddha %s beast %s' % (bf.computeBounds().size, sf.computeBounds().size))
        R = T.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'
        R.par.Startupinfo = False; R.par.Cover = False
        R.par.Camera = cam.path; R.par.Geometry = 'buddha beast floor'; R.par.Lights = 'light1'
        R.par.Raytracing = False
        R.seq.Sss.numBlocks = 2
        R.par.Sss0geo = 'buddha'; R.par.Sss0preset = 'jade'
        R.par.Sss1geo = 'beast'; R.par.Sss1preset = 'jade'
        R.par.Sss1scatterr, R.par.Sss1scatterg, R.par.Sss1scatterb = 0.95, 0.92, 0.8
        R.par.Sss1transr, R.par.Sss1transg, R.par.Sss1transb = 1.0, 0.95, 0.8
        out = T.create(nullTOP, 'view'); R.outputConnectors[0].connect(out)
        SH['R'] = R
        shot(0)
    SH = {'shots': [
        # name, camera (t, r), light (rx, ry): front key / back light
        ('front', (0.05, 0.2, 0.75), (-6, 4, 0), (-40, 35)),
        ('back', (0.05, 0.2, 0.75), (-6, 4, 0), (-15, 160)),
    ]}
    def shot(i):
        if i >= len(SH['shots']):
            log('STATUS DONE'); return
        nm, t, r, l = SH['shots'][i]
        cam.par.tx, cam.par.ty, cam.par.tz = t; cam.par.rx, cam.par.ry, cam.par.rz = r
        lt.par.rx, lt.par.ry = l
        SH['i'] = i
        SH['R'].par.Subsurface = True
        step(grab_on, 90)
    def grab_on():
        nm = SH['shots'][SH['i']][0]
        SH['R'].op('out1').save(BT + '/out/sss_%s_on.jpg' % nm)
        log('%s on: %s' % (nm, SH['R'].par.Status.eval()))
        SH['R'].par.Subsurface = False
        step(grab_off, 60)
    def grab_off():
        nm = SH['shots'][SH['i']][0]
        SH['R'].op('out1').save(BT + '/out/sss_%s_off.jpg' % nm)
        shot(SH['i'] + 1)
    step(fit, 20)
except Exception:
    log('ERROR\n' + traceback.format_exc())
