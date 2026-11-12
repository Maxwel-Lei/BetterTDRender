# [BTDR:FILE.SHOWCASE] make_showcase.py — builds the distributable showcase project: a folder you can zip and hand
# over, with BetterTDRender.toe (the showcase), BTDR.tox (the renderer), the CC0 HDRI under Image/ and the docs.
# Run inside the target project (its project.folder is the package folder), with the source tree given:
#   SHOW_SRC = 'F:/Projects/Touchdesigner Projects/ue5/btdr'
#   exec(open(SHOW_SRC + '/examples/make_showcase.py', encoding='utf-8').read())
# Optional: SHOW_SAVE = True also saves the project as <package>/BetterTDRender.toe after the scene has settled.
# Log: <package>/showcase_log.txt (first line STATUS ...)
import os, shutil, traceback
SRC = globals().get('SHOW_SRC', project.folder + '/btdr')
PKG = project.folder
LOGF = PKG + '/showcase_log.txt'
LOG = []

# [BTDR:SHOWCASE.PRESETS] one scene, four looks. Fog is backlit (light from behind the scene towards the camera):
# shafts only show where lit and shadowed fog meet in front of a dark background (USER_GUIDE, Fog page). Values are renderBTDR1 parameters, plus 'light' (rx, ry, dimmer,
# rgb) and 'glow' (emissive of the glowing cube). Applied by the module in the `presets` DAT (no functions in storage:
# IMPLEMENTATION_2 §11 #37).
PRESETS_SRC = r'''
# Presets of the BTDR showcase ([BTDR:SHOWCASE.PRESETS]). apply(name) sets renderBTDR1, light1 and the glow cube.
PRESETS = {
    'studio': dict(light=(-40, 35, 1.0, (1.0, 0.97, 0.92)), glow=(4.0, 1.6, 0.4),
                   pars=dict(Envsource='studio', Envintensity=1.0, Background='color', Bgcolorr=0.05, Bgcolorg=0.05,
                             Bgcolorb=0.06, Bgintensity=1.0, Fog=False, Bloom=0.15, Exposure=0.0, Vignette=0.3)),
    'hdri':   dict(light=(-43, 47.7, 1.59155, (1.0, 0.94, 0.84)), glow=(4.0, 1.6, 0.4),
                   pars=dict(Envsource='hdri', Envintensity=1.0, Envrotate=-96.2, Background='env', Bgblur=0.1,
                             Bgintensity=1.0, Fog=False, Bloom=0.1, Exposure=0.0, Vignette=0.3)),
    'fog':    dict(light=(-32, 165, 2.0, (1.0, 0.86, 0.66)), glow=(4.0, 1.6, 0.4),
                   pars=dict(Envsource='studio', Envintensity=0.35, Background='color', Bgcolorr=0.02, Bgcolorg=0.022,
                             Bgcolorb=0.03, Bgintensity=1.0, Fog=True, Fogdensity=0.1, Foganisotropy=0.8,
                             Fogambient=0.06, Fogheightfalloff=0.3, Fogbaseheight=0.0, Fogdistance=12.0,
                             Bloom=0.12, Exposure=-0.4, Vignette=0.45)),
    'night':  dict(light=(-55, -30, 0.12, (0.55, 0.65, 1.0)), glow=(12.0, 4.0, 1.0),
                   pars=dict(Envsource='studio', Envintensity=0.08, Background='color', Bgcolorr=0.005, Bgcolorg=0.006,
                             Bgcolorb=0.012, Bgintensity=1.0, Fog=False, Bloom=0.45, Exposure=1.0, Vignette=0.5)),
}
ORDER = ['studio', 'hdri', 'fog', 'night']

def apply(name):
    S = parent.Showcase
    p = PRESETS.get(name)
    if p is None:
        return
    R = S.op('renderBTDR1')
    for k, v in p['pars'].items():
        if k == 'Envsource' and v == 'hdri':
            R.par.Envmap = S.op('hdri')
        setattr(R.par, k, v)
    L = S.op('light1')
    L.par.rx, L.par.ry, L.par.dimmer = p['light'][0], p['light'][1], p['light'][2]
    L.par.cr, L.par.cg, L.par.cb = p['light'][3]
    m = S.op('m_glow')
    m.par.emitr, m.par.emitg, m.par.emitb = p['glow']
    S.op('caption').par.text = {'studio': 'Studio  ·  procedural studio light',
                               'hdri': 'HDRI  ·  outdoor panorama, sun aligned',
                               'fog': 'Volumetric fog  ·  backlight through the pergola',
                               'night': 'Night  ·  emissive + bloom'}[name]
'''

PAREXEC_SRC = r'''
def onValueChange(par, prev):
    if par.name == 'Preset':
        op('presets').module.apply(par.eval())
    return
'''

CYCLE_SRC = r'''
# [BTDR:SHOWCASE.CYCLE] Auto Cycle: next preset every Cycle Seconds
def onFrameStart(frame):
    S = parent.Showcase
    if not S.par.Autocycle.eval():
        return
    n = max(1, int(S.par.Cycleseconds.eval() * project.cookRate))
    if frame % n == 0:
        order = op('presets').module.ORDER
        i = (order.index(S.par.Preset.eval()) + 1) % len(order)
        S.par.Preset = order[i]
    return
'''

README_SRC = '''BetterTDRender (BTDR) showcase / 展示工程

What this is
  /project1/showcase renders one procedural scene with renderBTDR1 (BTDR.tox), in four looks:
  Studio, HDRI, Volumetric fog, Night. Pick one on the Showcase parameter page of /project1/showcase,
  or switch on Auto Cycle.

这是什么
  /project1/showcase 用 renderBTDR1（BTDR.tox）渲染一个程序化场景，有四种预设：
  摄影棚、HDRI 户外、体积雾光束、夜景发光。在 /project1/showcase 的 Showcase 参数页里选 Preset，
  或者打开 Auto Cycle 自动轮播。

Use BTDR in your own project / 在自己的工程里用
  Drag BTDR.tox (in this folder) into a network that has a Camera COMP, a Distant Light COMP and
  Geometry COMPs with PBR MATs. Connect its first output to a Null TOP. See USER_GUIDE.md, section 2.
  把本文件夹里的 BTDR.tox 拖进有相机、平行光和挂了 PBR MAT 的 Geometry COMP 的网络，第 1 个输出接 Null TOP。
  详见 USER_GUIDE.md 第 2 节。

Performance tip / 性能提示
  The Status parameter of renderBTDR1 shows tips (e.g. a light drawing a native shadow map BTDR does not use).
  renderBTDR1 的 Status 参数会给出提示（比如灯开着 BTDR 用不到的原生阴影）。
'''

try:
    P = op('/project1')
    # ------------------------------------------------------------------ files of the package
    # [BTDR:SHOWCASE.FILES] BTDR.tox at the top (the thing people come for), the HDRI in TD's own Image/ folder,
    # docs next to the .toe. Paths inside the project are relative to project.folder, so the folder can move.
    os.makedirs(PKG + '/Image', exist_ok=True)
    for a, b in ((SRC + '/release/BTDR.tox', PKG + '/BTDR.tox'),
                 (SRC + '/release/BTDR_Example.tox', PKG + '/BTDR_Example.tox'),
                 (SRC + '/examples/hdri/kloofendal_43d_clear_2k.hdr', PKG + '/Image/kloofendal_43d_clear_2k.hdr'),
                 (SRC + '/docs/USER_GUIDE.md', PKG + '/USER_GUIDE.md'),
                 (SRC + '/docs/RELEASE_README.txt', PKG + '/README.txt')):
        shutil.copyfile(a, b)
        LOG.append('copied %s (%d bytes)' % (b[len(PKG) + 1:], os.path.getsize(b)))

    # ------------------------------------------------------------------ the showcase component
    if P.op('showcase'): P.op('showcase').destroy()
    S = P.create(containerCOMP, 'showcase'); S.nodeX, S.nodeY = 0, 0
    S.par.w, S.par.h = 1280, 720
    S.par.parentshortcut = 'Showcase'
    def place(o, x, y):
        o.nodeX, o.nodeY = x, y
        return o
    pg = S.appendCustomPage('Showcase')
    pm = pg.appendMenu('Preset', label='Preset')[0]
    pm.menuNames = ['studio', 'hdri', 'fog', 'night']
    pm.menuLabels = ['Studio', 'HDRI', 'Volumetric Fog', 'Night']
    pm.default = 'studio'
    pg.appendToggle('Autocycle', label='Auto Cycle')
    cs = pg.appendFloat('Cycleseconds', label='Cycle Seconds')[0]; cs.default = cs.val = 8.0; cs.normMin = 2; cs.normMax = 30
    cw = pg.appendToggle('Cameraswing', label='Camera Swing')[0]; cw.default = cw.val = True

    # camera: slow swing in front of the scene, or still (Camera Swing off)
    # framing: the whole row of spheres, the wall and the arch; the pergola just above the frame (its shadow stripes
    # and, in the fog, its light shafts are what shows)
    tg = place(S.create(nullCOMP, 'target'), 0, 300); tg.par.ty = 0.75
    cam = place(S.create(cameraCOMP, 'cam1'), 0, 450)
    cam.par.tx.expr = 'math.sin(math.sin(absTime.seconds * 0.15) * 0.7) * 6.7 if parent.Showcase.par.Cameraswing else 0.9'
    cam.par.tz.expr = 'math.cos(math.sin(absTime.seconds * 0.15) * 0.7) * 6.7 + 0.4 if parent.Showcase.par.Cameraswing else 6.6'
    cam.par.ty = 2.1; cam.par.fov = 45; cam.par.lookat = tg
    lt = place(S.create(lightCOMP, 'light1'), 0, 150)
    lt.par.lighttype = 'distant'
    try: lt.par.shadowtype = 'off'                       # BTDR draws its own shadows
    except Exception: pass

    def mat(nm, rgb, metal, rough, emit=(0, 0, 0), y=0):
        m = place(S.create(pbrMAT, nm), 600, y)
        m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = rgb
        m.par.metallic = metal; m.par.roughness = rough
        m.par.emitr, m.par.emitg, m.par.emitb = emit
        return m
    def geo(nm, sop, material, t=(0, 0, 0), s=(1, 1, 1), r=(0, 0, 0), y=0, **kw):
        g = place(S.create(geometryCOMP, nm), 300, y)
        for c in list(g.children): c.destroy()
        so = g.create(sop, 'shape'); so.render = so.display = True
        for k, v in kw.items(): setattr(so.par, k, v)
        g.par.tx, g.par.ty, g.par.tz = t; g.par.sx, g.par.sy, g.par.sz = s; g.par.rx, g.par.ry, g.par.rz = r
        g.par.material = material
        return g
    # [BTDR:SHOWCASE.SCENE] the example scene ([BTDR:EXAMPLE.SCENE]) plus a pergola of slats over it: stripes of shadow
    # on the floor in every look, light shafts in the fog
    geo('floor', gridSOP, mat('m_floor', (0.18, 0.18, 0.19), 0.0, 0.22, y=0), y=0, sizex=24, sizey=24, orient='zx', rows=2, cols=2)
    specs = [('chrome', (0.95, 0.95, 0.95), 1.0, 0.05), ('gold', (1.0, 0.78, 0.34), 1.0, 0.3), ('plastic', (0.8, 0.08, 0.06), 0.0, 0.35),
             ('clay', (0.75, 0.72, 0.68), 0.0, 0.85), ('teal', (0.05, 0.45, 0.45), 0.0, 0.12)]
    for i, (nm, rgb, me, ro) in enumerate(specs):
        geo('sphere_' + nm, sphereSOP, mat('m_' + nm, rgb, me, ro, y=-100 - i * 100), t=(-1.6 + i * 0.8, 0.3, 0.6),
            y=-100 - i * 100, radx=0.3, rady=0.3, radz=0.3, freq=10, type='poly')
    geo('wall', boxSOP, mat('m_wall', (0.85, 0.12, 0.08), 0.0, 0.6, y=-650), t=(0, 0.75, -1.2), y=-650, sizex=4.0, sizey=1.5, sizez=0.15)
    am = mat('m_arch', (0.82, 0.82, 0.8), 0.0, 0.5, y=-750)
    geo('arch_top', boxSOP, am, t=(2.4, 0.95, 0.2), y=-750, sizex=1.2, sizey=0.12, sizez=0.9)
    geo('arch_left', boxSOP, am, t=(1.9, 0.45, 0.2), y=-850, sizex=0.15, sizey=0.9, sizez=0.9)
    geo('arch_right', boxSOP, am, t=(2.9, 0.45, 0.2), y=-950, sizex=0.15, sizey=0.9, sizez=0.9)
    geo('glow', boxSOP, mat('m_glow', (1.0, 0.55, 0.2), 0.0, 0.5, emit=(4.0, 1.6, 0.4), y=-1050), t=(-2.5, 0.2, -0.3),
        r=(0, 30, 0), y=-1050, sizex=0.4, sizey=0.4, sizez=0.4)
    pmat = mat('m_pergola', (0.32, 0.24, 0.17), 0.0, 0.7, y=-1150)
    for k in range(7):
        geo('slat%d' % k, boxSOP, pmat, t=(-2.4 + k * 0.8, 2.5, -0.1), y=-1150 - k * 60, sizex=0.22, sizey=0.12, sizez=3.6)
    for k, x in enumerate((-2.9, 2.9)):
        geo('beam%d' % k, boxSOP, pmat, t=(x, 2.38, -0.1), y=-1600 - k * 60, sizex=0.14, sizey=0.14, sizez=3.8)

    # environment: the bundled HDRI, path relative to the project folder (the package can move)
    hd = place(S.create(moviefileinTOP, 'hdri'), 600, 500)
    hd.par.file = 'Image/kloofendal_43d_clear_2k.hdr'

    # the renderer, as a user would drop it in
    R = S.loadTox(PKG + '/BTDR.tox'); R.name = 'renderBTDR1'; R.nodeX, R.nodeY = 900, 300
    o = place(S.create(nullTOP, 'OUT'), 1100, 300)
    R.outputConnectors[0].connect(o)
    # caption over the picture
    cap = place(S.create(textTOP, 'caption'), 1100, 150)
    cap.par.resolutionw, cap.par.resolutionh = 1920, 1080
    try:
        cap.par.outputresolution = 'custom'
        cap.par.alignx = 'left'; cap.par.aligny = 'bottom'
        cap.par.positionx = 60; cap.par.positiony = 50
        cap.par.fontsizex = 34
        cap.par.bgalpha = 0
    except Exception as e:
        LOG.append('caption pars: %r' % e)
    comp_ = place(S.create(overTOP, 'with_caption'), 1300, 300)
    # explicit input slots: connect(op) to a free input replaced input 0 here (caption lost, 'Not enough sources')
    cap.outputConnectors[0].connect(comp_.inputConnectors[0]); o.outputConnectors[0].connect(comp_.inputConnectors[1])
    final = place(S.create(nullTOP, 'FINAL'), 1500, 300)
    comp_.outputConnectors[0].connect(final)
    S.par.opviewer = 'FINAL'
    try: S.viewer = True
    except Exception: pass

    pr = place(S.create(textDAT, 'presets'), 600, 650); pr.text = PRESETS_SRC
    pe = place(S.create(parameterexecuteDAT, 'preset_exec'), 750, 650); pe.text = PAREXEC_SRC
    pe.par.op = '..'; pe.par.pars = 'Preset'; pe.par.custom = True; pe.par.builtin = False; pe.par.valuechange = True; pe.par.active = True
    cy = place(S.create(executeDAT, 'autocycle'), 900, 650); cy.text = CYCLE_SRC
    cy.par.framestart = True; cy.par.active = True
    rd = place(S.create(textDAT, 'README'), 1100, 650); rd.text = README_SRC
    top = P.op('README') or P.create(textDAT, 'README')
    top.text = README_SRC; top.nodeX, top.nodeY = 0, 250

    R.par.Camera = 'cam1'; R.par.Lights = 'light1'
    R.Refresh()
    S.par.Preset = 'studio'
    pr.module.apply('studio')
    LOG.append('renderBTDR1 %s, status: %s' % (R.par.Version.eval(), R.par.Status.eval()))
    open(LOGF, 'w', encoding='utf-8').write('STATUS BUILT\n' + '\n'.join(LOG))
except Exception:
    open(LOGF, 'w', encoding='utf-8').write('STATUS ERR\n' + '\n'.join(LOG) + '\n' + traceback.format_exc())
