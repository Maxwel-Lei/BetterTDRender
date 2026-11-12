# [BTDR:FILE.SCENES] make_scenes.py — the five showcase scenes used by the intro video (SCENES.*).
# Only native operators: SOPs, POPs, instancing, PBR MAT, one distant Light COMP, a Camera COMP, one renderBTDR.
# Run inside the project that has btdr/ next to it:
#   SCENES = ['blinds', 'neon', 'monolith', 'particles', 'materials']   # any subset
#   exec(open(project.folder + '/btdr/examples/make_scenes.py', encoding='utf-8').read())
# Builds /project1/sc_<name> (replacing an existing one). Log: btdr/out/scenes_log.txt
# Cameras are static here; tools/video_rig.py animates them while recording.
import traceback, math
BT = project.folder + '/btdr'
LOG = []


class S:
    def __init__(self, name, x):
        P = op('/project1')
        if P.op('sc_' + name):
            P.op('sc_' + name).destroy()
        self.C = P.create(containerCOMP, 'sc_' + name)
        self.C.nodeX, self.C.nodeY = x, -2200
        self.C.par.w, self.C.par.h = 960, 540
        self.my = 0
        self.gy = 0

    def place(self, o, x, y):
        o.nodeX, o.nodeY = x, y
        return o

    def mat(self, nm, rgb, metal=0.0, rough=0.5, emit=(0, 0, 0)):
        m = self.place(self.C.create(pbrMAT, nm), 600, self.my); self.my -= 100
        m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = rgb
        m.par.metallic = metal; m.par.roughness = rough
        m.par.emitr, m.par.emitg, m.par.emitb = emit
        return m

    def geo(self, nm, material, sop=None, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1), build=None, **kw):
        g = self.place(self.C.create(geometryCOMP, nm), 300, self.gy); self.gy -= 100
        for c in list(g.children):
            c.destroy()
        if build is not None:
            last = build(g)
        else:
            last = g.create(sop, 'shape')
            for k, v in kw.items():
                setattr(last.par, k, v)
        last.render = last.display = True
        g.par.tx, g.par.ty, g.par.tz = t; g.par.rx, g.par.ry, g.par.rz = r; g.par.sx, g.par.sy, g.par.sz = s
        g.par.material = material
        return g

    def box(self, nm, material, center, size, r=(0, 0, 0)):
        return self.geo(nm, material, boxSOP, t=center, r=r, sizex=size[0], sizey=size[1], sizez=size[2])

    def camlight(self, cam_t, cam_look, light_r, dimmer=1.0, fov=40.0, shadow=False):
        tg = self.place(self.C.create(nullCOMP, 'target'), 0, 300)
        tg.par.tx, tg.par.ty, tg.par.tz = cam_look
        cam = self.place(self.C.create(cameraCOMP, 'cam1'), 0, 450)
        cam.par.tx, cam.par.ty, cam.par.tz = cam_t; cam.par.fov = fov; cam.par.lookat = tg
        cam.par.near = 0.05; cam.par.far = 400
        lt = self.place(self.C.create(lightCOMP, 'light1'), 0, 150)
        lt.par.lighttype = 'distant'; lt.par.rx, lt.par.ry, lt.par.rz = light_r; lt.par.dimmer = dimmer
        try:
            lt.par.shadowtype = 'soft2d' if shadow else 'off'
        except Exception:
            pass
        return cam, lt

    def render(self, **pars):
        R = self.C.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'; R.nodeX, R.nodeY = 900, 300
        for k, v in pars.items():
            setattr(R.par, k, v)
        o = self.place(self.C.create(nullTOP, 'OUT'), 1100, 300)
        R.outputConnectors[0].connect(o)
        self.C.par.opviewer = 'OUT'
        keep = self.place(self.C.create(executeDAT, 'keep_cooking'), 1100, 450)
        keep.text = "def onFrameStart(frame):\n    op('OUT').cook()\n    return\n"
        keep.par.framestart = True; keep.par.active = False
        R.Refresh()
        self.R = R
        return R


# ------------------------------------------------------------------ 1. blinds
def build_blinds():
    s = S('blinds', 0)
    # [BTDR:SCENES.BLINDS] a closed room 8 x 6 x 3.2 m; the only opening is a window in the back wall (z = -3) with a row
    # of tilted slats; a low sun shines in through it: volumetric light shafts, striped shadows, red-wall colour bleeding
    W, D, H, T = 8.0, 6.0, 3.2, 0.15
    wx0, wx1, wy0, wy1 = -1.7, 1.7, 0.85, 2.55
    m_wall = s.mat('m_wall', (0.82, 0.8, 0.76), rough=0.75)
    m_red = s.mat('m_red', (0.75, 0.09, 0.06), rough=0.7)
    m_floor = s.mat('m_floor', (0.55, 0.34, 0.18), rough=0.38)
    m_slat = s.mat('m_slat', (0.9, 0.88, 0.84), rough=0.5)
    m_white = s.mat('m_white', (0.92, 0.92, 0.9), rough=0.25)
    m_dark = s.mat('m_dark', (0.08, 0.08, 0.09), metal=0.0, rough=0.4)
    m_brass = s.mat('m_brass', (0.95, 0.72, 0.4), metal=1.0, rough=0.25)
    s.geo('floor', m_floor, gridSOP, sizex=W + 1, sizey=D + 1, orient='zx', rows=2, cols=2)
    s.box('ceiling', m_wall, (0, H + T / 2, 0), (W + 1, T, D + 1))
    s.box('wall_left', m_red, (-W / 2 - T / 2, H / 2, 0), (T, H, D))
    s.box('wall_right', m_wall, (W / 2 + T / 2, H / 2, 0), (T, H, D))
    s.box('wall_front', m_wall, (0, H / 2, D / 2 + T / 2), (W, H, T))
    z = -D / 2 - T / 2
    s.box('wall_back_l', m_wall, ((-W / 2 + wx0) / 2, H / 2, z), (wx0 + W / 2, H, T))
    s.box('wall_back_r', m_wall, ((W / 2 + wx1) / 2, H / 2, z), (W / 2 - wx1, H, T))
    s.box('wall_back_b', m_wall, (0, wy0 / 2, z), (wx1 - wx0, wy0, T))
    s.box('wall_back_t', m_wall, (0, (H + wy1) / 2, z), (wx1 - wx0, H - wy1, T))

    def slats(g):
        b = g.create(boxSOP, 'slat'); b.par.sizex = wx1 - wx0 - 0.04; b.par.sizey = 0.006; b.par.sizez = 0.12
        x = g.create(transformSOP, 'tilt'); x.inputConnectors[0].connect(b); x.par.rx = -30
        c = g.create(copySOP, 'copies'); c.inputConnectors[0].connect(x)
        n = 12
        c.par.ncy = n; c.par.ty = (wy1 - wy0 - 0.1) / (n - 1)
        return c
    s.geo('blinds', m_slat, build=slats, t=(0, wy0 + 0.05, -D / 2 + 0.06))
    # furniture the shafts fall on
    s.box('plinth', m_white, (-0.6, 0.45, -0.4), (0.6, 0.9, 0.6))
    s.geo('sphere', m_brass, sphereSOP, t=(-0.6, 1.2, -0.4), radx=0.3, rady=0.3, radz=0.3, freq=12, type='poly')
    s.box('bench', m_dark, (1.4, 0.22, 0.6), (2.0, 0.44, 0.5))
    s.box('cabinet', m_white, (-3.55, 0.6, 1.6), (0.7, 1.2, 1.6))
    s.camlight((2.9, 1.45, 2.4), (-0.7, 1.15, -2.0), (-24, 200, 0), dimmer=9.0, fov=50, shadow=True)
    R = s.render(Envsource='studio', Envintensity=0.8, Rtgiintensity=1.8, Background='color', Bgcolorr=0.75, Bgcolorg=0.85, Bgcolorb=1.0,
                 Bgintensity=3.0, Fog=True, Fogdensity=0.06, Fogheightfalloff=0.0, Foganisotropy=0.85, Fogambient=0.1,
                 Fognoise=0.0, Fogdistance=12.0, Fogres='high', Fogcurweight=0.04, Fogjitter=0.5, Fogshadowblur=1.0, Bloom=0.12, Exposure=0.35, Shadowfit=False, Shadowcenterx=0.0,
                 Shadowcentery=1.5, Shadowcenterz=-0.5, Shadowrange=10.0)
    # native Render TOP of the same scene, for the opening comparison
    amb = s.place(s.C.create(ambientlightCOMP, 'ambient1'), 0, 0)
    amb.par.dimmer = 0.35
    nr = s.place(s.C.create(renderTOP, 'native_render'), 900, 100)
    nr.par.camera = 'cam1'; nr.par.geometry = '*'; nr.par.lights = 'light1 ambient1'
    nr.par.resolutionw, nr.par.resolutionh = 1920, 1080
    nr.par.bgcolorr, nr.par.bgcolorg, nr.par.bgcolorb, nr.par.bgcolora = 0.75, 0.85, 1.0, 1.0
    try:
        nr.par.antialias = '4x'
    except Exception:
        pass
    s.place(s.C.create(nullTOP, 'native_out'), 1100, 100).inputConnectors[0].connect(nr)
    return R


# ------------------------------------------------------------------ 2. neon
def build_neon():
    s = S('neon', 400)
    # [BTDR:SCENES.NEON] a wet night street: glossy ground with a noise normal map and puddle roughness,
    # dark buildings both sides, rows of emissive neon tubes (Copy SOP), dim blue moonlight, thin fog, strong bloom
    nz = s.place(s.C.create(noiseTOP, 'puddle_noise'), 900, -400)
    nz.par.resolutionw = nz.par.resolutionh = 1024; nz.par.period = 0.35; nz.par.harmon = 4; nz.par.mono = True
    lv = s.place(s.C.create(levelTOP, 'puddle_rough'), 1050, -400); lv.inputConnectors[0].connect(nz)
    lv.par.brightness1 = 0.55; lv.par.contrast = 2.0
    nm = s.place(s.C.create(normalmapTOP, 'ground_normal'), 1050, -500); nm.inputConnectors[0].connect(nz)
    nm.par.zscale = 0.03
    m_ground = s.mat('m_ground', (0.05, 0.05, 0.055), rough=1.0)
    m_ground.par.roughnessmap = lv; m_ground.par.normalmap = nm; m_ground.par.bumpscale = 0.03
    m_ground.par.roughness = 0.07
    m_bld = s.mat('m_bld', (0.09, 0.09, 0.1), rough=0.6)
    s.geo('ground', m_ground, gridSOP, sizex=40, sizey=80, orient='zx', rows=2, cols=2)
    for i, (x, z, w, h, d) in enumerate([(-5.5, -6, 3, 9, 8), (-5.0, -18, 2.5, 14, 10), (-6.0, -32, 4, 11, 12),
                                         (5.5, -4, 3, 12, 7), (5.2, -16, 2.6, 8, 10), (6.0, -30, 4, 16, 12)]):
        s.box('bld%d' % i, m_bld, (x, h / 2, z), (w, h, d))
    cols = [('pink', (6.0, 0.6, 2.6)), ('cyan', (0.4, 3.6, 6.0)), ('amber', (6.0, 2.6, 0.4)), ('violet', (2.8, 0.6, 6.0))]
    spec = [  # colour, side x, z start, count, step, vertical?, y, length
        (0, -3.95, -2.0, 6, -2.2, True, 2.6, 1.6), (1, 3.95, -1.0, 5, -2.6, True, 3.0, 2.0),
        (2, -3.95, -14.0, 4, -2.4, False, 3.4, 1.6), (3, 3.95, -13.0, 5, -2.2, True, 2.4, 1.4),
        (1, -4.7, -26.0, 3, -2.5, False, 5.0, 2.4), (0, 4.6, -25.0, 4, -2.4, True, 4.0, 2.0)]
    mats = {i: s.mat('m_neon_' + n, (0.1, 0.1, 0.1), rough=0.3, emit=e) for i, (n, e) in enumerate(cols)}
    for j, (ci, x, z0, n, step, vert, y, ln) in enumerate(spec):
        def tubes(g, n=n, step=step, vert=vert, ln=ln):
            b = g.create(boxSOP, 'tube')
            b.par.sizex, b.par.sizey, b.par.sizez = (0.07, ln, 0.07) if vert else (0.07, 0.07, ln)
            c = g.create(copySOP, 'copies'); c.inputConnectors[0].connect(b); c.par.ncy = n; c.par.tz = step
            return c
        s.geo('neon%d' % j, mats[ci], build=tubes, t=(x, y, z0))
    # facade strips: horizontal neon bands along both building rows
    for j, (ci, x, y, z0, n) in enumerate([(1, -3.95, 4.6, -3.0, 4), (0, 3.95, 5.4, -2.0, 4), (2, -3.95, 7.0, -20.0, 3),
                                           (3, 3.95, 6.2, -18.0, 3), (1, 3.95, 1.4, -8.0, 3), (0, -3.95, 1.2, -9.0, 3)]):
        def strips(g, n=n):
            b = g.create(boxSOP, 'strip'); b.par.sizex, b.par.sizey, b.par.sizez = 0.06, 0.06, 2.6
            c = g.create(copySOP, 'copies'); c.inputConnectors[0].connect(b); c.par.ncy = n; c.par.tz = -3.4
            return c
        s.geo('strip%d' % j, mats[ci], build=strips, t=(x, y, z0))
    # a sign: a ring of light at the end of the street
    s.geo('sign', mats[1], torusSOP, t=(0, 6.5, -38), radx=2.0, rady=0.08, rows=12, cols=64, type='poly')
    s.camlight((0.3, 0.35, 6.0), (0.0, 1.6, -20.0), (-35, 150, 0), dimmer=0.35, fov=45)
    R = s.render(Envsource='studio', Envintensity=0.05, Background='color', Bgcolorr=0.01, Bgcolorg=0.012,
                 Bgcolorb=0.02, Fog=True, Fogdensity=0.025, Fogheightfalloff=0.08, Foganisotropy=0.5, Fogambient=0.4,
                 Fogdistance=60.0, Bloom=0.35, Bloomradius=0.75, Exposure=0.9, Ssrmaxdistance=30.0,
                 Ssrmaxroughness=0.5, Shadowfit=False, Shadowcenterz=-15.0, Shadowrange=50.0)
    return R


# ------------------------------------------------------------------ 3. monolith
def build_monolith():
    s = S('monolith', 800)
    # [BTDR:SCENES.MONOLITH] one-point perspective into the sunset sun (generated HDRI examples/hdri/sunset_btdr.hdr,
    # sun 3.4 deg above the horizon straight down -Z). Composition: horizon on the lower third, an avenue of
    # identical slabs repeating towards the vanishing point (rhythm, size falling off with distance, fading into the
    # haze), one slab in the right row leaning out (the break in the rhythm), a screen of tall slabs on the horizon
    # with the sun just behind the middle one (rays), a small block on the axis in the foreground (scale). Back light:
    # the light travels from the sun towards the camera, so every shadow is a line running to the vanishing point.
    hd = s.place(s.C.create(moviefileinTOP, 'hdri_file'), 900, -400)
    hd.par.file = BT + '/examples/hdri/sunset_btdr.hdr'
    m_ground = s.mat('m_ground', (0.5, 0.36, 0.26), rough=0.85)
    m_stone = s.mat('m_stone', (0.025, 0.025, 0.028), rough=0.35)
    m_pale = s.mat('m_pale', (0.62, 0.6, 0.56), rough=0.6)
    s.geo('ground', m_ground, gridSOP, sizex=1200, sizey=1200, orient='zx', rows=2, cols=2)
    for side, x in (('l', -4.5), ('r', 4.5)):
        for k in range(9):
            z = 22.0 - 14.0 * k
            lean = (0, 0, -12) if (side == 'r' and k == 2) else (0, 0, 0)      # the one that breaks the row
            y = 2.9 if lean[2] else 3.0
            s.box('slab_%s%d' % (side, k), m_stone, (x + (0.6 if lean[2] else 0.0), y, z), (1.4, 6.0, 0.4), r=lean)
    # the screen: a row of tall slabs across the horizon, the middle one exactly in front of the sun. Their shadows
    # are vertical sheets running straight at the camera: in the fog they read as rays fanning out from the sun
    # (crepuscular rays), on the ground as stripes converging on the vanishing point
    for i in range(9):
        s.box('screen%d' % i, m_stone, (-40.0 + 10.0 * i, 17.0, -160.0), (5.0, 34.0, 1.0))
    s.box('block', m_pale, (0.0, 0.3, 20.0), (0.6, 0.6, 0.6), r=(0, 30, 0))
    # camera 1.2 m high on the axis, pitched up 3.9 deg so the horizon sits on the lower third
    cam, _ = s.camlight((0.0, 1.2, 40.0), (0.0, 8.0, -60.0), (-3.4, 180, 0), dimmer=3.0, fov=40)
    cam.par.far = 1500
    # shafts need the camera in shadow looking at lit fog: low ambient, strong forward scattering, warm albedo;
    # the shadow map has to reach the screen 200 m away (Shadow Range 130, centred between camera and screen)
    R = s.render(Envsource='hdri', Envmap='hdri_file', Envintensity=1.0, Background='env', Bgblur=0.03,
                 Fog=True, Fogdensity=0.01, Fogheightfalloff=0.03, Foganisotropy=0.7, Fogambient=0.02,
                 Fogcolorr=1.0, Fogcolorg=0.82, Fogcolorb=0.62, Fogres='high',
                 Fogdistance=320.0, Dof=True, Focusdistance=26.0, Fstop=4.0, Bloom=0.1, Exposure=-2.2,
                 Shadowfit=False, Shadowcenterx=0.0, Shadowcentery=8.0, Shadowcenterz=-60.0, Shadowrange=130.0)
    return R


# ------------------------------------------------------------------ 4. particles
PART_N = (1000, 400)  # grid cols x rows = particle count


def build_particles():
    s = S('particles', 1200)
    # [BTDR:SCENES.PARTICLES] audio-driven POP particles. A Grid POP of points is the particle pool; a GLSL POP
    # (`swirl`) places every particle from its id, the time and four audio features (stateless, so a recording
    # is frame-exact), writes P, Color, PointScale; a Geometry COMP instances a small icosahedron on it.
    # Audio: Audio File In -> Audio Spectrum -> bands (bass / mid / high) -> `feat_live`; `feat_baked` holds the
    # same features computed offline from the same file (the video recorder drives it frame by frame).
    au = s.place(s.C.create(audiofileinCHOP, 'audio'), 900, -400)
    au.par.file = BT + '/examples/audio/btdr_theme.wav'
    sp = s.place(s.C.create(audiospectrumCHOP, 'spectrum'), 1050, -400); sp.inputConnectors[0].connect(au)
    sp.par.fftsize = '2048'
    bands = []
    for k, (nm, a, b) in enumerate((('bass', 0.0, 0.12), ('mid', 0.12, 0.5), ('high', 0.5, 1.0))):
        tr = s.place(s.C.create(trimCHOP, 'trim_' + nm), 1200, -350 - 80 * k); tr.inputConnectors[0].connect(sp)
        tr.par.startunit = 'fraction'; tr.par.endunit = 'fraction'; tr.par.start = a; tr.par.end = b
        an = s.place(s.C.create(analyzeCHOP, 'an_' + nm), 1350, -350 - 80 * k); an.inputConnectors[0].connect(tr)
        an.par.function = 'average'
        rn = s.place(s.C.create(renameCHOP, 'rn_' + nm), 1500, -350 - 80 * k); rn.inputConnectors[0].connect(an)
        rn.par.renamefrom = '*'; rn.par.renameto = nm
        bands.append(rn)
    mg = s.place(s.C.create(mergeCHOP, 'bands'), 1650, -400)
    for b in bands:
        mg.inputConnectors[len(mg.inputs)].connect(b)
    lag = s.place(s.C.create(lagCHOP, 'feat_live'), 1800, -400); lag.inputConnectors[0].connect(mg)
    lag.par.lag1 = 0.02; lag.par.lag2 = 0.25
    bk = s.place(s.C.create(constantCHOP, 'feat_baked'), 1800, -500)
    for i, n in enumerate(('bass', 'mid', 'high', 'kick')):
        getattr(bk.par, 'name%d' % i).val = n
    sw = s.place(s.C.create(switchCHOP, 'feat'), 1950, -450)
    sw.inputConnectors[0].connect(lag); sw.inputConnectors[1].connect(bk); sw.par.index = 0
    clk = s.place(s.C.create(constantCHOP, 'clock'), 1950, -550); clk.par.name0 = 't'; clk.par.value0.expr = 'absTime.seconds'
    # particles
    gp = s.place(s.C.create(gridPOP, 'pool'), 900, -700)
    gp.par.surftype = 'points'; gp.par.cols, gp.par.rows = PART_N; gp.par.normal = 'none'; gp.par.texture = 'none'
    dat = s.place(s.C.create(textDAT, 'swirl_comp'), 1050, -800)
    dat.text = open(BT + '/examples/swirl.comp', encoding='utf-8').read()
    g = s.place(s.C.create(glslPOP, 'swirl'), 1050, -700); g.inputConnectors[0].connect(gp)
    for c in list(g.docked):
        if c.valid and c is not dat:
            c.destroy()
    g.par.computedat = dat; g.par.attrclass = 'point'; g.par.outputattrs = 'P Color PointScale'
    g.seq.attr.numBlocks = 2
    g.par.attr0name = 'color'; g.par.attr0type = 'color'; g.par.attr0numcomps = '4'
    g.par.attr1name = 'pointscale'; g.par.attr1type = 'float'; g.par.attr1numcomps = '1'
    # [SCENES.TEXT] the text the particles gather into (uForm.x drives it; 0 = free swirl)
    tx = s.place(s.C.create(textTOP, 'form_text'), 900, -900)
    tx.par.resolutionw, tx.par.resolutionh = 1600, 520
    tx.par.text = 'GPU 3-4 ms\nCPU 2-3 ms'
    tx.par.fontsizex = 150; tx.par.alignx = 'center'; tx.par.aligny = 'center'
    tx.par.fontcolorr = tx.par.fontcolorg = tx.par.fontcolorb = 1.0; tx.par.bgalpha = 0.0
    try:
        tx.par.font = 'Arial Black'
    except Exception:
        pass
    g.seq.sampler.numBlocks = 1
    g.par.sampler0name = 'sText'; g.par.sampler0top = tx; g.par.sampler0filter = 'nearest'
    g.seq.vec.numBlocks = 3
    g.par.vec0name = 'uAudio'; g.par.vec0type = 'vec4'
    g.par.vec0valuex.expr = "op('feat')['bass']"; g.par.vec0valuey.expr = "op('feat')['mid']"
    g.par.vec0valuez.expr = "op('feat')['high']"; g.par.vec0valuew.expr = "op('feat')['kick'] if op('feat')['kick'] is not None else 0"
    g.par.vec1name = 'uTime'; g.par.vec1type = 'vec4'; g.par.vec1valuex.expr = "op('clock')['t']"
    g.par.vec2name = 'uForm'; g.par.vec2type = 'vec4'; g.par.vec2valuex = 0.0
    g.par.vec2valuey = 5.4; g.par.vec2valuez = 1.7; g.par.vec2valuew = 0.6
    m_p = s.mat('m_particle', (0.02, 0.02, 0.02), rough=0.4, emit=(1, 1, 1))

    def inst(gc):
        sh = gc.create(sphereSOP, 'grain'); sh.par.type = 'poly'; sh.par.freq = 1
        sh.par.radx = sh.par.rady = sh.par.radz = 1.0
        return sh
    pg = s.geo('particles', m_p, build=inst)
    pg.par.instancing = True; pg.par.instanceop = g
    pg.par.instancetx = 'P(0)'; pg.par.instancety = 'P(1)'; pg.par.instancetz = 'P(2)'
    pg.par.instancesx = 'PointScale'; pg.par.instancesy = 'PointScale'; pg.par.instancesz = 'PointScale'
    pg.par.instancecolorop = g; pg.par.instancecolormode = 'multiply'
    pg.par.instancer = 'Color(0)'; pg.par.instanceg = 'Color(1)'; pg.par.instanceb = 'Color(2)'; pg.par.instancea = 'Color(3)'
    # glossy metal floor: the sand lies on it (the floor is the Chladni plate), its sheen carries the shot
    m_floor = s.mat('m_floor', (0.5, 0.5, 0.5), metal=1.0, rough=0.2)
    s.geo('floor', m_floor, gridSOP, sizex=60, sizey=60, orient='zx', rows=2, cols=2)
    m_ring = s.mat('m_ring', (0.6, 0.6, 0.62), metal=1.0, rough=0.2)
    s.geo('ring', m_ring, torusSOP, t=(0, 0.02, 0), radx=4.6, rady=0.05, rows=8, cols=96, type='poly')
    s.camlight((0.0, 2.6, 9.5), (0.0, 1.4, 0.0), (-60, 30, 0), dimmer=0.25, fov=42)
    R = s.render(Envsource='studio', Envintensity=0.6, Background='color', Bgcolorr=0.005, Bgcolorg=0.005,
                 Bgcolorb=0.008, Bloom=0.4, Bloomradius=0.7, Bloomthreshold=0.8, Exposure=0.0,
                 Ssrmaxdistance=4.0, Ssrthickness=0.2, Fog=True, Fogdensity=0.015, Fogambient=0.3, Fogdistance=40.0, Fogheightfalloff=0.0)
    return R


# ------------------------------------------------------------------ 5. materials
def build_materials():
    s = S('materials', 1600)
    # [BTDR:SCENES.MATERIALS] a row of plinths under studio light: chrome, gold, ceramic, rubber, emissive,
    # glass (Refractive slot) and a diamond (Diamond preset, ray-traced refraction)
    m_pl = s.mat('m_plinth', (0.55, 0.55, 0.56), rough=0.6)
    m_floor = s.mat('m_floor', (0.2, 0.2, 0.21), rough=0.35)
    s.geo('floor', m_floor, gridSOP, sizex=40, sizey=40, orient='zx', rows=2, cols=2)
    items = [
        ('chrome', s.mat('m_chrome', (0.96, 0.96, 0.97), metal=1.0, rough=0.04), sphereSOP, dict(radx=0.32, rady=0.32, radz=0.32, freq=14, type='poly')),
        ('gold', s.mat('m_gold', (1.0, 0.76, 0.33), metal=1.0, rough=0.3), torusSOP, dict(radx=0.28, rady=0.1, rows=24, cols=64, type='poly')),
        ('ceramic', s.mat('m_ceramic', (0.9, 0.88, 0.84), rough=0.12), sphereSOP, dict(radx=0.32, rady=0.32, radz=0.32, freq=14, type='poly')),
        ('rubber', s.mat('m_rubber', (0.05, 0.05, 0.055), rough=0.92), torusSOP, dict(radx=0.26, rady=0.12, rows=24, cols=64, type='poly')),
        ('emissive', s.mat('m_emit', (0.1, 0.1, 0.1), rough=0.4, emit=(0.4, 2.6, 4.0)), boxSOP, dict(sizex=0.42, sizey=0.42, sizez=0.42)),
        ('glass', s.mat('m_glass', (0.96, 0.98, 1.0), rough=0.02), sphereSOP, dict(radx=0.32, rady=0.32, radz=0.32, freq=14, type='poly')),
        ('diamond', s.mat('m_diamond', (0.98, 0.98, 1.0), rough=0.0), sphereSOP, dict(radx=0.34, rady=0.34, radz=0.34, freq=1, type='poly')),
    ]
    for i, (nm, m, sop, kw) in enumerate(items):
        x = (i - 3) * 1.25
        s.box('plinth_' + nm, m_pl, (x, 0.45, 0), (0.8, 0.9, 0.8))
        rot = (20, 30, 0) if nm in ('gold', 'rubber', 'emissive', 'diamond') else (0, 0, 0)
        s.geo('obj_' + nm, m, sop, t=(x, 1.25, 0), r=rot, **kw)
    # backdrop with coloured light strips: the glass and the diamond bend them
    m_back = s.mat('m_back', (0.05, 0.05, 0.055), rough=0.6)
    s.box('backdrop', m_back, (0, 1.6, -2.2), (12.0, 3.2, 0.1))
    for j, (x, e) in enumerate([(-4.4, (3.0, 0.4, 1.2)), (-2.9, (0.4, 2.0, 3.5)), (-1.4, (3.5, 1.8, 0.3)), (0.1, (2.4, 0.4, 3.5)),
                                (1.9, (0.4, 3.2, 2.0)), (3.1, (3.5, 0.6, 0.6)), (4.4, (0.5, 1.6, 3.5))]):
        s.box('strip%d' % j, s.mat('m_strip%d' % j, (0.1, 0.1, 0.1), emit=e), (x, 1.6, -2.12), (0.12, 2.6, 0.04))
    s.camlight((-4.2, 1.7, 3.2), (-2.0, 1.15, 0.0), (-42, 35, 0), dimmer=1.4, fov=38)
    R = s.render(Envsource='studio', Envintensity=1.0, Background='color', Bgcolorr=0.12, Bgcolorg=0.12, Bgcolorb=0.13,
                 Bloom=0.1, Exposure=0.2, Geometry='floor backdrop strip* plinth_* obj_chrome obj_gold obj_ceramic obj_rubber obj_emissive',
                 Refrmethod='hybrid')
    for nm in ('m_glass', 'm_diamond'):
        s.C.op(nm).par.alphafront = 0.0      # fully transparent: Alpha Front > 0 is a diffuse coating
    R.seq.Refr.numBlocks = 2
    R.par.Refr0geo = 'obj_glass'; R.par.Refr0preset = 'glass'
    R.par.Refr1geo = 'obj_diamond'; R.par.Refr1preset = 'diamond'
    R.Refresh()
    return R


BUILD = dict(blinds=build_blinds, neon=build_neon, monolith=build_monolith, particles=build_particles, materials=build_materials)
for _nm in globals().get('SCENES', list(BUILD)):
    try:
        _R = BUILD[_nm]()
        LOG.append('%s: %s' % (_nm, _R.par.Status.eval()))
    except Exception:
        LOG.append('%s: ERROR\n%s' % (_nm, traceback.format_exc()))
open(BT + '/out/scenes_log.txt', 'w', encoding='utf-8').write('\n'.join(LOG))
