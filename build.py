# [BTDR:FILE.BUILD] BetterTDRender build script.
# Run inside TouchDesigner:  exec(open(project.folder + '/btdr/build.py', encoding='utf-8').read())
# Builds the renderBTDR component from shaders/ and ext/, saves release/BTDR.tox (and a copy in the TD Palette,
# [BTDR:BUILD.PALETTE]), removes the build copy.
# Result and errors: btdr/out/build_log.txt
import os, re, traceback

BT = project.folder.replace('\\', '/') + '/btdr'
VERSION = '0.7.4'
BLOG = []

def _read(rel):
    return open(BT + '/' + rel, encoding='utf-8').read()

MAT_SHADERS = ('gbuffer.vert', 'gbuffer.frag', 'shadow.vert', 'shadow.frag')

# shaders that render into a 3D texture read the uniforms from a texture buffer ([BTDR:BUILD.TBUF])
TBUF_SHADERS = ['fog_scatter.comp', 'fog_accum.comp', 'fog_integrate.comp']
# the forward material of blended transparency reads the uniforms from a 40 x 1 texture ([BTDR:BUILD.FWDUB])
FWD_SHADERS = ['forward.frag']
# [BTDR:BUILD.M6B] M6b blended transparency is kept in the source but not built into the release (the user found it
# not good enough yet, 2026-11-12): no Blended page section, no tblend / blend_comp, auto-detection treats sprite
# materials as refractive again (0.6.0 behaviour). Set True to build it ([BTDR:FWD.*], IMPLEMENTATION_1b §9f).
M6B = False
FWD_SLOTS = 20                  # slots 0..19 are all the forward material needs (camera, sun, environment, clip)

def _shader(name):
    # [BTDR:BUILD.SHADER] common.glsl is prepended (material shaders are self-contained);
    # "//#include x" pulls in shaders/x.glsl
    src = _read('shaders/' + name)
    src = re.sub(r'^//#include (\w+)\s*$', lambda m: _read('shaders/%s.glsl' % m.group(1)), src, flags=re.M)
    if name in MAT_SHADERS:
        return src
    common = _read('shaders/common.glsl')
    if name in TBUF_SHADERS:
        # [BTDR:BUILD.TBUF] a uniform array is only correct for the first slice of a 3D GLSL TOP (measured in
        # TD 2025.33230: later slices read shifted values), a texture buffer is correct for all slices. The
        # buffer is copied into a global array of the same name, so the uB[] macros work unchanged; the shader
        # calls loadUB() first thing in main().
        n = re.search(r'uniform vec4 uB\[(\d+)\];', common).group(1)
        common = common.replace('uniform vec4 uB[%s];' % n,
                                'uniform samplerBuffer uBbuf;\nvec4 uB[%s];\n'
                                'void loadUB() { for (int i = 0; i < %s; i++) uB[i] = texelFetch(uBbuf, i); }' % (n, n))
    if name in FWD_SHADERS:
        # [BTDR:BUILD.FWDUB] a GLSL MAT with a uniform array bound to the per-frame CHOP would re-cook every frame;
        # a sampler whose TOP changes does not ([BTDR:FWD.UB]). main() calls loadUB() first.
        n = re.search(r'uniform vec4 uB\[(\d+)\];', common).group(1)
        common = common.replace('uniform vec4 uB[%s];' % n,
                                'uniform sampler2D sUB;\nvec4 uB[%s];\n'
                                'void loadUB() { for (int i = 0; i < %d; i++) uB[i] = texelFetch(sUB, ivec2(i, 0), 0); }'
                                % (n, FWD_SLOTS))
    return common + '\n' + src

def _menu(par, cands):
    names = list(par.menuNames)
    for c in cands:
        if c in names:
            par.val = c
            return c
    BLOG.append('MENU MISS %s.%s wanted %s have %s' % (par.owner.name, par.name, cands, names))

def build_btdr(dest, name='renderBTDR'):
    if dest.op(name):
        dest.op(name).destroy()
    C = dest.create(baseCOMP, name)
    C.par.parentshortcut = 'BTDR'
    C.store('version', VERSION)

    def place(o, x, y):
        o.nodeX, o.nodeY = x, y
        return o
    def dat(nm, text, x, y):
        d = place(C.create(textDAT, nm), x, y)
        d.text = text
        return d
    def undock(o):
        for d in list(o.docked):             # template shader DATs TD adds to new GLSL operators
            d.destroy()
    def uarray(o, tbuf=False):
        # [BTDR:BUILD.UARRAY] every shader reads the same CHOP as `uniform vec4 uB[40]`
        # (3D outputs: as a texture buffer `uBbuf`, see [BTDR:BUILD.TBUF])
        o.seq.array.numBlocks = 1
        o.par.array0name = 'uBbuf' if tbuf else 'uB'
        o.par.array0type = 'vec4'
        o.par.array0chop = C.op('uniforms')
        try: o.par.array0arraytype = 'texturebuffer' if tbuf else 'uniformarray'
        except Exception as e: BLOG.append('arraytype %s %r' % (o.name, e))
    def res(o, w, h, fmt=None):
        o.par.outputresolution = 'custom'
        for p, v in ((o.par.resolutionw, w), (o.par.resolutionh, h)):
            if isinstance(v, str): p.expr = v
            else: p.val = v
        if fmt: _menu(o.par.format, fmt)
    RW, RH = 'parent.BTDR.par.Resolutionw', 'parent.BTDR.par.Resolutionh'
    def glsl(nm, frag, inputs, w, h, fmt, x, y, shared=True):
        g = place(C.create(glslmultiTOP, nm), x, y)
        g.par.pixeldat = frag
        undock(g)
        res(g, w, h, fmt)
        for s in inputs:
            s.outputConnectors[0].connect(g)
        if shared:                       # static passes opt out so they do not cook every frame
            uarray(g)
        return g

    # ---------------------------------------------------------------- custom parameters
    # [BTDR:BUILD.PARS]
    def setup(p, default=None, lo=None, hi=None, clampmin=False, clampmax=False):
        if default is not None:
            p.default = default; p.val = default
        if lo is not None: p.normMin = lo; p.min = lo; p.clampMin = clampmin
        if hi is not None: p.normMax = hi; p.max = hi; p.clampMax = clampmax
        return p
    def menu(p, names, labels, default):
        p.menuNames = names; p.menuLabels = labels; p.default = default; p.val = default
        return p
    pg = C.appendCustomPage('Render')
    setup(pg.appendOBJ('Camera', label='Camera')[0], 'cam1')
    setup(pg.appendStr('Geometry', label='Geometry')[0], '*')
    setup(pg.appendStr('Lights', label='Lights')[0], '*')
    pg.appendPulse('Refresh', label='Refresh Scene')
    p = pg.appendStr('Status', label='Status')[0]; p.readOnly = True
    wh = pg.appendWH('Resolution', label='Resolution')
    setup(wh[0], 1920, 16, 3840, True); setup(wh[1], 1080, 16, 2160, True)
    menu(pg.appendMenu('Quality', label='Quality')[0], ['high', 'low', 'custom'], ['High', 'Low', 'Custom'], 'high')
    menu(pg.appendMenu('Debugview', label='Debug View')[0],
         ['final', 'basecolor', 'normal', 'roughness', 'metallic', 'ao', 'emissive', 'depth', 'direct', 'envdiffuse', 'envspecular',
          'ssao', 'ssgi', 'ssr', 'rtgi', 'rtrefl'],
         ['Final Image', 'Base Color', 'Normal', 'Roughness', 'Metallic', 'Material AO', 'Emissive', 'Depth',
          'Direct Light', 'Environment Diffuse', 'Environment Specular',
          'Screen-Space AO', 'Bounce Light (SSGI)', 'Reflections (SSR)', 'Probe GI (RT)', 'Traced Reflections (RT)'], 'final')
    setup(pg.appendToggle('Srgbcolors', label='sRGB Colors and Color Maps')[0], True)
    # [BTDR:BUILD.TAAPARS] temporal anti-aliasing parameters
    menu(pg.appendMenu('Antialias', label='Anti-Aliasing')[0], ['taa', 'none'], ['TAA (Temporal)', 'None'], 'taa')
    p = setup(pg.appendFloat('Taaweight', label='TAA Current Frame Weight')[0], 0.1, 0.03, 0.5, True, True)
    p.enableExpr = "me.par.Antialias == 'taa'"
    # [BTDR:BUILD.NCONV] normal map convention of all materials (Blender / Tripo default OpenGL = Y+, Unreal / Substance default DirectX = Y-)
    menu(pg.appendMenu('Normalconvention', label='Normal Map Convention')[0], ['opengl', 'directx'],
         ['OpenGL (Y+)', 'DirectX (Y-)'], 'opengl')

    pg = C.appendCustomPage('Light')
    p = pg.appendStr('Mainlight', label='Main Light')[0]; p.readOnly = True
    setup(pg.appendFloat('Lightmult', label='Intensity Multiplier')[0], 1.0, 0, 4, True)
    setup(pg.appendToggle('Shadows', label='Shadows')[0], True)
    setup(pg.appendFloat('Shadowsoftness', label='Shadow Softness')[0], 1.0, 0, 4, True)
    setup(pg.appendToggle('Shadowfit', label='Auto Fit Shadow Range')[0], True)
    for p in pg.appendXYZ('Shadowcenter', label='Shadow Center'):
        p.enableExpr = 'not me.par.Shadowfit'
    p = setup(pg.appendFloat('Shadowrange', label='Shadow Range')[0], 8.0, 0.5, 50, True)
    p.enableExpr = 'not me.par.Shadowfit'
    p = menu(pg.appendMenu('Shadowres', label='Shadow Resolution')[0], ['1024', '2048', '4096', '8192'], ['1024', '2048', '4096', '8192'], '4096')
    p.enableExpr = "me.par.Quality == 'custom'"
    # [BTDR:BUILD.SHADOWUPDATE] On Change: the shadow map is only re-rendered when the light, a geometry COMP's
    # transform or its rendered SOP / POP changes (see [BTDR:UNI.SHADOWCACHE]); Every Frame: always.
    menu(pg.appendMenu('Shadowupdate', label='Shadow Update')[0], ['auto', 'always'], ['On Change', 'Every Frame'], 'auto')
    p = setup(pg.appendToggle('Shadowmovinghalf', label='Half Resolution While Moving')[0], True)
    p.enableExpr = "me.par.Shadowupdate == 'auto'"
    p = pg.appendInt('Shadowmovinginterval', label='Update Every N Frames While Moving')[0]
    setup(p, 1, 1, 4, True, True); p.enableExpr = "me.par.Shadowupdate == 'auto'"

    pg = C.appendCustomPage('Environment')
    menu(pg.appendMenu('Envsource', label='Source')[0], ['studio', 'hdri'], ['Studio (built-in)', 'HDRI Map'], 'studio')
    p = pg.appendTOP('Envmap', label='HDRI Map')[0]; p.enableExpr = "me.par.Envsource == 'hdri'"
    setup(pg.appendFloat('Envintensity', label='Intensity')[0], 1.0, 0, 4, True)
    setup(pg.appendFloat('Envrotate', label='Rotate')[0], 0.0, -180, 180)
    menu(pg.appendMenu('Background', label='Background')[0], ['color', 'env'], ['Color', 'Environment'], 'color')
    for p, v in zip(pg.appendRGB('Bgcolor', label='Background Color'), (0.16, 0.16, 0.17)):
        setup(p, v); p.enableExpr = "me.par.Background == 'color'"
    p = setup(pg.appendFloat('Bgblur', label='Background Blur')[0], 0.3, 0, 1, True, True); p.enableExpr = "me.par.Background == 'env'"
    setup(pg.appendFloat('Bgintensity', label='Background Intensity')[0], 1.0, 0, 4, True)
    setup(pg.appendFloat('Fadestart', label='Distance Fade Start')[0], 0.0, 0, 50, True)
    setup(pg.appendFloat('Fadeend', label='Distance Fade End')[0], 0.0, 0, 50, True)

    # [BTDR:BUILD.RTPARS] M4 hardware ray tracing (simplified Lumen): probe GI + traced reflections on a proxy scene
    pg = C.appendCustomPage('Ray Tracing')
    setup(pg.appendToggle('Raytracing', label='Hardware Ray Tracing')[0], True)
    p = pg.appendToggle('Rtavailable', label='Ray Tracing Available')[0]; p.default = True; p.val = True; p.readOnly = True
    p = setup(pg.appendToggle('Rtgi', label='Probe GI')[0], True); p.enableExpr = 'me.par.Raytracing'
    p = setup(pg.appendFloat('Rtgiintensity', label='GI Intensity')[0], 1.0, 0, 4, True); p.enableExpr = 'me.par.Raytracing and me.par.Rtgi'
    p = setup(pg.appendToggle('Rtreflections', label='Ray-Traced Reflections')[0], True); p.enableExpr = 'me.par.Raytracing'
    p = setup(pg.appendFloat('Rtreflintensity', label='Reflection Intensity')[0], 1.0, 0, 1, True, True); p.enableExpr = 'me.par.Raytracing and me.par.Rtreflections'
    p = setup(pg.appendFloat('Rtreflmaxrough', label='Reflection Max Roughness')[0], 0.7, 0.05, 1, True, True); p.enableExpr = 'me.par.Raytracing and me.par.Rtreflections'
    p = setup(pg.appendFloat('Rtproxydetail', label='Proxy Detail (%)')[0], 15.0, 1, 100, True, True); p.enableExpr = 'me.par.Raytracing'
    p = pg.appendStr('Rtproxyinfo', label='Proxy')[0]; p.readOnly = True

    # [BTDR:BUILD.POSTPARS] lens / camera effects (M2)
    pg = C.appendCustomPage('Post')
    setup(pg.appendFloat('Bloom', label='Bloom Intensity')[0], 0.05, 0, 1, True)
    setup(pg.appendFloat('Bloomthreshold', label='Bloom Threshold')[0], 1.0, 0, 10, True)
    setup(pg.appendFloat('Bloomknee', label='Bloom Knee')[0], 0.5, 0, 2, True)
    setup(pg.appendFloat('Bloomradius', label='Bloom Radius')[0], 0.65, 0, 0.95, True, True)
    setup(pg.appendToggle('Autoexposure', label='Auto Exposure')[0], False)
    for nm, lab, d, lo, hi in (('Aeminev', 'Auto Exposure Min Luminance (EV)', -6.0, -12, 4),
                               ('Aemaxev', 'Auto Exposure Max Luminance (EV)', 4.0, -4, 16),
                               ('Aekey', 'Auto Exposure Target Grey', 0.18, 0.02, 1.0),
                               ('Aespeedup', 'Adapt Speed To Brighter', 3.0, 0.1, 20),
                               ('Aespeeddown', 'Adapt Speed To Darker', 1.0, 0.1, 20)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi); p.enableExpr = 'me.par.Autoexposure'
    setup(pg.appendToggle('Dof', label='Depth of Field')[0], False)
    for nm, lab, d, lo, hi in (('Focusdistance', 'Focus Distance', 3.0, 0.05, 100),
                               ('Fstop', 'F-Stop', 2.8, 0.7, 32),
                               ('Focallength', 'Focal Length (mm, 0 = from camera)', 0.0, 0, 600),
                               ('Sensorwidth', 'Sensor Width (mm)', 36.0, 1, 100),
                               ('Dofmaxblur', 'Max Blur Radius (px)', 14.0, 1, 40)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi, True); p.enableExpr = 'me.par.Dof'
    setup(pg.appendToggle('Motionblur', label='Motion Blur')[0], False)
    for nm, lab, d, lo, hi in (('Shutter', 'Shutter (fraction of a frame)', 0.5, 0, 1),
                               ('Mbmaxblur', 'Max Blur Length (px)', 32.0, 1, 128)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi, True); p.enableExpr = 'me.par.Motionblur'

    # [BTDR:BUILD.SSPARS] M3 screen-space indirect lighting
    pg = C.appendCustomPage('Indirect')
    setup(pg.appendToggle('Ambientocclusion', label='Screen-Space AO')[0], True)
    p = setup(pg.appendFloat('Aointensity', label='AO Intensity')[0], 1.0, 0, 2, True); p.enableExpr = 'me.par.Ambientocclusion'
    setup(pg.appendToggle('Ssgi', label='Bounce Light (SSGI)')[0], True)
    p = setup(pg.appendFloat('Ssgiintensity', label='Bounce Intensity')[0], 1.0, 0, 4, True); p.enableExpr = 'me.par.Ssgi'
    p = setup(pg.appendFloat('Giradius', label='AO / Bounce Radius')[0], 0.6, 0.05, 5, True)
    p.enableExpr = 'me.par.Ambientocclusion or me.par.Ssgi'
    setup(pg.appendToggle('Ssr', label='Screen-Space Reflections')[0], True)
    for nm, lab, d, lo, hi in (('Ssrintensity', 'Reflection Intensity', 1.0, 0, 1),
                               ('Ssrmaxdistance', 'Max Ray Distance', 8.0, 0.5, 50),
                               ('Ssrmaxroughness', 'Max Roughness', 0.6, 0.05, 1),
                               ('Ssrthickness', 'Object Thickness', 0.15, 0.01, 2)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi, True); p.enableExpr = 'me.par.Ssr'
    # [BTDR:BUILD.HFPARS] height-field AO: large-scale sky occlusion from a top-down depth map (under cars, tables)
    setup(pg.appendToggle('Heightfieldao', label='Height-Field AO')[0], False)
    p = setup(pg.appendFloat('Hfaointensity', label='Height-Field AO Intensity')[0], 1.0, 0, 1, True); p.enableExpr = 'me.par.Heightfieldao'
    p = setup(pg.appendFloat('Hfaoradius', label='Height-Field AO Radius')[0], 2.0, 0.2, 10, True); p.enableExpr = 'me.par.Heightfieldao'

    # [BTDR:BUILD.FOGPARS] volumetric fog (M3)
    pg = C.appendCustomPage('Fog')
    setup(pg.appendToggle('Fog', label='Volumetric Fog')[0], False)
    for nm, lab, d, lo, hi in (('Fogdensity', 'Density', 0.03, 0, 1),
                               ('Fogheightfalloff', 'Height Falloff', 0.4, 0, 5),
                               ('Fogbaseheight', 'Base Height', 0.0, -10, 10),
                               ('Foganisotropy', 'Anisotropy (Forward Scattering)', 0.6, -0.9, 0.95),
                               ('Fogambient', 'Ambient Light', 1.0, 0, 4),
                               ('Fognoise', 'Noise', 0.3, 0, 1),
                               ('Fogdistance', 'Max Distance', 40.0, 1, 500)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi, nm not in ('Fogbaseheight',)); p.enableExpr = 'me.par.Fog'
    for p, v in zip(pg.appendRGB('Fogcolor', label='Fog Color (Albedo)'), (1.0, 1.0, 1.0)):
        setup(p, v); p.enableExpr = 'me.par.Fog'
    # [BTDR:BUILD.FOGQUALITY] (0.7.2) noise / stability controls: grid resolution, temporal weight, jitter, shadow blur.
    # 0.7.3: Fog Shadow Blur = penumbra relative to the surface shadows (1 = same contact-hardening PCSS, 0 = hard)
    p = pg.appendMenu('Fogres', label='Fog Resolution')[0]
    p.menuNames = ['auto', 'low', 'medium', 'high', 'ultra']
    p.menuLabels = ['Auto (from Quality)', 'Low 128x72x48', 'Medium 160x90x64', 'High 240x135x96', 'Ultra 320x180x128']
    p.default = 'auto'; p.val = 'auto'; p.enableExpr = 'me.par.Fog'
    for nm, lab, d, lo, hi in (('Fogcurweight', 'Fog Current Frame Weight', 0.1, 0.02, 1),
                               ('Fogjitter', 'Fog Jitter', 1.0, 0, 1),
                               ('Fogshadowblur', 'Fog Shadow Blur', 1.0, 0, 4)):
        p = setup(pg.appendFloat(nm, label=lab)[0], d, lo, hi, True); p.enableExpr = 'me.par.Fog'

    # [BTDR:BUILD.TRANSPARS] M6a transparency: Refractive slots (drag Geometry COMPs in), global defaults
    pg = C.appendCustomPage('Transparency')
    setup(pg.appendToggle('Transparency', label='Transparency')[0], True)
    p = setup(pg.appendInt('Transcount', label='Transparent Objects')[0], 0); p.readOnly = True
    setup(pg.appendFloat('Defaultior', label='Default IOR')[0], 1.5, 1.0, 3.0, True)
    setup(pg.appendFloat('Absorbdist', label='Absorption Distance')[0], 1.0, 0.01, 10, True)
    # M6b blended transparency globals ([BTDR:FWD.*]); custom parameters appended after a sequence join its block,
    # so every plain parameter of the page comes before the two sequences
    # [BTDR:BUILD.REFRMETHOD] M6c: how refractive objects find what is behind them ([BTDR:REFR.RT])
    p = menu(pg.appendMenu('Refrmethod', label='Refraction Method')[0], ['screen', 'hybrid', 'raytraced'],
             ['Screen Space', 'Hybrid (Screen Space + Ray Traced)', 'Ray Traced'], 'screen')
    if M6B:
        p = setup(pg.appendInt('Blendcount', label='Blended Objects')[0], 0); p.readOnly = True
        menu(pg.appendMenu('Blendmethod', label='Blend Method')[0], ['sorted', 'orderind'],
             ['Sorted', 'Order Independent (Depth Peeling)'], 'sorted')
        p = setup(pg.appendInt('Peellayers', label='Peel Layers')[0], 4, 2, 8, True); p.enableExpr = "me.par.Blendmethod == 'orderind'"
        setup(pg.appendFloat('Softdist', label='Soft Particles Distance')[0], 0.1, 0.0, 2.0, True)
        setup(pg.appendFloat('Glassdim', label='Behind Glass Dimming')[0], 0.75, 0.0, 1.0, True, True)
    sq = pg.appendSequence('Refr', label='Refractive')
    setup(pg.appendStr('Geo', label='Geometry')[0], '')
    menu(pg.appendMenu('Preset', label='Preset')[0],
         ['glass', 'frosted', 'tinted', 'water', 'ice', 'crystal', 'diamond', 'acrylic', 'window', 'custom'],
         ['Glass', 'Frosted Glass', 'Tinted Glass', 'Water', 'Ice', 'Crystal', 'Diamond', 'Acrylic', 'Window (thin)', 'Custom'], 'glass')
    setup(pg.appendFloat('Ior', label='IOR')[0], 1.5, 1.0, 3.0, True)
    setup(pg.appendFloat('Rough', label='Roughness Override')[0], -1.0, -1.0, 1.0, True)
    setup(pg.appendToggle('Thin', label='Thin Walled')[0], False)
    setup(pg.appendFloat('Absorb', label='Absorption Distance')[0], 1.0, 0.01, 10, True)
    menu(pg.appendMenu('Shadow', label='Cast Shadow')[0], ['none', 'opaque'], ['None', 'Opaque'], 'none')
    setup(pg.appendToggle('Inrt', label='In Ray Tracing')[0], False)
    try:
        C.seq.Refr.blockSize = 8       # a sequence keeps at least one block: an empty slot is ignored
    except Exception as e:
        BLOG.append('refr seq %r' % e)
    # M6b blended transparency: Blended slots + how they are layered ([BTDR:FWD.*], built only with M6B)
    if M6B:
        pg.appendSequence('Blend', label='Blended')
        setup(pg.appendStr('Geo', label='Geometry')[0], '')
        menu(pg.appendMenu('Mode', label='Mode')[0], ['alpha', 'additive'], ['Alpha', 'Additive'], 'alpha')
        setup(pg.appendToggle('Lit', label='Lit')[0], True)
        setup(pg.appendFloat('Soft', label='Soft Distance Override')[0], -1.0, -1.0, 2.0, True)
        try:
            C.seq.Blend.blockSize = 4
        except Exception as e:
            BLOG.append('blend seq %r' % e)

    pg = C.appendCustomPage('Grade')
    setup(pg.appendFloat('Exposure', label='Exposure (EV)')[0], 0.0, -5, 5)
    menu(pg.appendMenu('Tonemap', label='Tone Mapping')[0], ['aces', 'none'], ['ACES', 'None'], 'aces')
    setup(pg.appendFloat('Vignette', label='Vignette')[0], 0.3, 0, 1, True, True)
    setup(pg.appendFloat('Grain', label='Grain')[0], 0.01, 0, 0.1, True)

    # [BTDR:BUILD.INFO] author, contact, licence (0.7.4: replaces the About page; the dialog is [BTDR:EXT.INFO])
    pg = C.appendCustomPage('Info')
    p = setup(pg.appendStr('Version', label='Version')[0], VERSION); p.readOnly = True
    pg.appendPulse('Showinfo', label='About / Contact...')
    for nm, lab, v in (('Author', 'Author', 'TD学长 (Xikai Lei)'), ('Wechat', 'WeChat 微信', 'TD_Xuezhang'),
                       ('Xianyu', 'Xianyu 闲鱼', '搜索 “TD学长”'), ('Email1', 'Email', 'max_lei_in_london@163.com'),
                       ('Email2', 'Email 2', 'ginicholaslbert@gmail.com'),
                       ('License', 'License', 'Free for noncommercial use; commercial use needs a license (contact the author)'),
                       ('Source', 'Source', 'https://github.com/Maxwel-Lei/BetterTDRender')):
        p = setup(pg.appendStr(nm, label=lab)[0], v); p.readOnly = True

    # ---------------------------------------------------------------- code + shaders
    X0 = -1400
    names = ['gbuffer.vert', 'gbuffer.frag', 'shadow.vert', 'shadow.frag', 'env_studio.frag', 'env_prefilter.frag',
             'lighting.frag', 'composite.frag', 'taa.frag', 'grade.frag', 'debug.frag', 'depth.frag',
             'dof.frag', 'mblur.frag', 'bloom_pre.frag', 'bloom_down.frag', 'bloom_up.frag', 'lum.frag', 'exposure.frag',
             'ssgi.frag', 'ssr.frag', 'ss_accum.frag', 'rt_probes.comp', 'rt_refl.comp', 'fog_scatter.comp', 'fog_accum.comp', 'fog_integrate.comp', 'fog_apply.frag', 'refract.frag', 'rt_refr.comp'] + (['forward.frag', 'blend_comp.frag'] if M6B else [])
    D = {}
    for i, n in enumerate(names):
        D[n] = dat(n.replace('.', '_'), _shader(n), X0, 400 - i * 100)
    D['white_frag'] = dat('white_frag', 'out vec4 fragColor;\nvoid main() { fragColor = vec4(1.0); }\n', X0 - 250, -100)   # unused pixel stage of compute TOPs
    D['rt_accum.frag'] = dat('rt_accum_frag', '#define RT_ACC\n' + _shader('ss_accum.frag'), X0, 300 - len(names) * 100)
    D['bloom_karis.frag'] = dat('bloom_karis_frag', '#define BLOOM_KARIS\n' + _shader('bloom_down.frag'), X0, 400 - len(names) * 100)
    dat('BTDRExt', _read('ext/BTDRExt.py'), X0 - 250, 400)
    dat('status', 'OK', X0 - 250, 0)
    cb = dat('uniforms_callbacks', _read('ext/uniforms_chop.py'), X0 - 250, 300)
    pe = place(C.create(parameterexecuteDAT, 'parexec'), X0 - 250, 200)
    pe.text = _read('ext/parexec.py')
    pe.par.op = '..'; pe.par.pars = '*'; pe.par.custom = True; pe.par.builtin = False
    pe.par.onpulse = True; pe.par.valuechange = True; pe.par.active = True
    ex = place(C.create(executeDAT, 'execute'), X0 - 250, 100)
    ex.text = _read('ext/execute.py')
    ex.par.create = True; ex.par.start = True; ex.par.active = True
    C.par.ext0object = "op('./BTDRExt').module.BTDRExt(me)"
    C.par.ext0name = 'BTDRExt'
    C.par.ext0promote = True

    # [BTDR:BUILD.UNIFORMS]
    uni = place(C.create(scriptCHOP, 'uniforms'), -1000, 600)
    uni.par.callbacks = cb
    # [BTDR:BUILD.UNICOOK] a parameter that references absTime makes the CHOP time-dependent, so it cooks every
    # frame. Reading absTime inside the Python callback does not: with a still camera the CHOP cooked once and
    # the frame index stayed at 0 — TAA jitter froze and every temporal history (TAA, AO / SSGI / SSR, fog)
    # was reset each frame (found in 0.3.1).
    uni.appendCustomPage('BTDR').appendFloat('Frame', label='Frame')
    uni.par.Frame.expr = 'absTime.frame'
    # [BTDR:BUILD.JITCAM] internal camera for the G-Buffer: user camera + TAA jitter ([BTDR:EXT.JITCAM])
    place(C.create(cameraCOMP, 'cam_jit'), -800, 550)
    white = place(C.create(constantTOP, 'white'), -1000, 500)
    white.par.colorr = white.par.colorg = white.par.colorb = 1
    res(white, 4, 4)
    scene = place(C.create(baseCOMP, 'scene'), -800, 400)

    # [BTDR:BUILD.GBUF] G-Buffer: 4 colour buffers, 16-bit float (position is stored camera-relative), no MSAA
    gb = place(C.create(renderTOP, 'gbuffer'), -600, 400)
    gb.par.camera = ''; gb.par.geometry = 'scene/g*'; gb.par.lights = ''
    gb.par.numcolorbufs = 4
    res(gb, RW, RH, ['rgba16float'])
    _menu(gb.par.antialias, ['aa1', '1x', '1'])
    gb.par.bgcolorr = gb.par.bgcolorg = gb.par.bgcolorb = gb.par.bgcolora = 0
    rs = []
    for i in range(4):
        r = place(C.create(renderselectTOP, 'gbuf%d' % i), -400, 500 - i * 100)
        r.par.top = gb; r.par.bufferindex = i
        rs.append(r)

    # [BTDR:BUILD.SHADOW] shadow map: orthographic camera parented to the main light, depth-only override material
    sun = place(C.create(cameraCOMP, 'suncam'), -800, 0)
    _menu(sun.par.projection, ['ortho', 'orthographic'])
    sun.par.near = 0.1
    msh = place(C.create(glslMAT, 'mat_shadow'), -800, -100)
    msh.par.vdat = D['shadow.vert']; msh.par.pdat = D['shadow.frag']
    undock(msh)
    shd = place(C.create(renderTOP, 'shadow'), -600, 0)
    shd.par.camera = 'suncam'; shd.par.geometry = 'scene/g*'; shd.par.lights = ''
    shd.par.overridemat = msh
    # resolution is managed by `uniforms` ([BTDR:UNI.SHADOWMOTION]: Shadow Resolution, halved while moving)
    res(shd, 4096, 4096, ['r32float', 'mono32float', 'rgba32float'])
    _menu(shd.par.antialias, ['aa1', '1x', '1'])
    shd.par.bgcolorr = shd.par.bgcolorg = shd.par.bgcolorb = shd.par.bgcolora = 0
    # Cache TOP holding the last shadow map: while inactive it does not pull `shadow`, so the shadow Render TOP
    # stops re-rendering (a Render TOP re-renders every frame whenever it is pulled, see IMPLEMENTATION §11 #8).
    shc = place(C.create(cacheTOP, 'shadow_cache'), -400, 0)
    shc.par.cachesize = 1; shc.par.active = True
    shd.outputConnectors[0].connect(shc)
    # while the shadow map is re-rendered every frame, `lighting` reads `shadow` directly (index 0): a Cache TOP
    # copy costs ~0.3 ms GPU per frame. Index 1 = the cached map. Set by [BTDR:UNI.SHADOWCACHE].
    shs = place(C.create(switchTOP, 'shadow_src'), -200, 0)
    shd.outputConnectors[0].connect(shs); shc.outputConnectors[0].connect(shs)
    shs.par.index = 1

    # [BTDR:BUILD.HFAO] height-field AO: orthographic camera looking straight down over the shadow range, the same
    # casters and depth material as the shadow map (the ground plane is not a caster, so it is not in the map).
    # Stored value = depth below the camera, so height = camera height - value; 0 = nothing there. Cached like the
    # shadow map: `hf_cache` is only active while the scene changes ([BTDR:UNI.SHADOWCACHE]); `hf_src` feeds a
    # constant (no occluder) when the option is off, so the pass does not cook.
    top = place(C.create(cameraCOMP, 'topcam'), -800, -150)
    _menu(top.par.projection, ['ortho', 'orthographic'])
    top.par.rx = -90
    top.par.tx.expr = 'parent.BTDR.par.Shadowcenterx'
    top.par.ty.expr = 'parent.BTDR.par.Shadowcentery + parent.BTDR.par.Shadowrange'
    top.par.tz.expr = 'parent.BTDR.par.Shadowcenterz'
    top.par.orthowidth.expr = 'parent.BTDR.par.Shadowrange'
    top.par.near = 0.01
    top.par.far.expr = 'parent.BTDR.par.Shadowrange * 3'
    hfr = place(C.create(renderTOP, 'hf_render'), -600, -150)
    hfr.par.camera = 'topcam'; hfr.par.lights = ''; hfr.par.overridemat = msh
    hfr.par.geometry.expr = "op('shadow').par.geometry.eval()"
    HFR = "512 if parent.BTDR.par.Quality != 'low' else 256"
    res(hfr, HFR, HFR, ['r32float', 'mono32float', 'rgba32float'])
    _menu(hfr.par.antialias, ['aa1', '1x', '1'])
    hfr.par.bgcolorr = hfr.par.bgcolorg = hfr.par.bgcolorb = hfr.par.bgcolora = 0
    hfc = place(C.create(cacheTOP, 'hf_cache'), -400, -150)
    hfc.par.cachesize = 1; hfc.par.active = True
    hfr.outputConnectors[0].connect(hfc)
    hfo = place(C.create(constantTOP, 'hf_off'), -400, -220)
    hfo.par.colorr = hfo.par.colorg = hfo.par.colorb = 0; hfo.par.alpha = 1
    res(hfo, 4, 4, ['r32float', 'mono32float', 'rgba32float'])
    hfs = place(C.create(switchTOP, 'hf_src'), -200, -150)
    hfo.outputConnectors[0].connect(hfs); hfc.outputConnectors[0].connect(hfs)
    hfs.par.index.expr = '1 if parent.BTDR.par.Heightfieldao else 0'

    # [BTDR:BUILD.ENV] environment: studio or user HDRI -> sharp equirect + pre-filtered 3D atlas
    est = glsl('env_studio', D['env_studio.frag'], [], 1024, 512, ['rgba16float'], -600, -300, shared=False)
    eus = place(C.create(selectTOP, 'env_user'), -600, -400)
    eus.par.top.expr = "parent.BTDR.par.Envmap.eval() or op('env_studio')"
    esw = place(C.create(switchTOP, 'env_src'), -400, -300)
    est.outputConnectors[0].connect(esw); eus.outputConnectors[0].connect(esw)
    esw.par.index.expr = "1 if (parent.BTDR.par.Envsource == 'hdri' and parent.BTDR.par.Envmap.eval()) else 0"
    eat = glsl('env_atlas', D['env_prefilter.frag'], [esw], 256, 128, ['rgba16float'], -200, -300, shared=False)
    eat.par.type = 'texture3d'; eat.par.depth = 'custom'; eat.par.customdepth = 6
    _menu(eat.par.inputfiltertype, ['mipmap'])
    _menu(eat.par.inputextenduv, ['repeat'])

    # [BTDR:BUILD.LIGHT]
    lit = glsl('lighting', D['lighting.frag'], rs[:3] + [shs, rs[3], esw, eat], RW, RH, ['rgba16float'], -200, 400)
    lit.par.numcolorbufs = 4
    _menu(lit.par.inputextenduv, ['repeat'])
    litb = [lit]
    for i in (1, 2, 3):
        s = place(C.create(renderselectTOP, 'lit%d' % i), 0, 400 - i * 100)
        s.par.top = lit; s.par.bufferindex = i
        litb.append(s)
    # [BTDR:BUILD.TAA] TAA history (Feedback TOP, Target TOP = taa). Its input only sets resolution / format, and
    # must not depend on the image: the screen-space passes below read last frame's image from it, so wiring
    # composite into it would be a cook loop (composite -> ssgi -> taa_hist -> composite). gbuf0 has the same size
    # and format.
    fbk = place(C.create(feedbackTOP, 'taa_hist'), 300, 550)
    rs[0].outputConnectors[0].connect(fbk)

    # [BTDR:BUILD.SS] M3 screen-space passes: noisy pass -> temporal accumulation (own Feedback history);
    # full resolution on High, half on Low. A Switch TOP feeds a neutral constant when the effect is off,
    # so the passes do not cook.
    SW = "max(int(parent.BTDR.par.Resolutionw) // (2 if parent.BTDR.par.Quality == 'low' else 1), 1)"
    SH = "max(int(parent.BTDR.par.Resolutionh) // (2 if parent.BTDR.par.Quality == 'low' else 1), 1)"
    def ss_chain(nm, frag, off_rgba, on_expr, y):
        g = glsl(nm, D[frag], [rs[1], rs[2], fbk], SW, SH, ['rgba16float'], -200, y)
        h = place(C.create(feedbackTOP, nm + '_hist'), 0, y - 60)
        g.outputConnectors[0].connect(h)
        acc = glsl(nm + '_acc', D['ss_accum.frag'], [g, h, rs[2]], SW, SH, ['rgba16float'], 0, y)
        h.par.top = acc
        off = place(C.create(constantTOP, nm + '_off'), 0, y + 60)
        off.par.colorr, off.par.colorg, off.par.colorb, off.par.alpha = off_rgba
        res(off, 4, 4, ['rgba16float'])
        s = place(C.create(switchTOP, nm + '_src'), 200, y)
        off.outputConnectors[0].connect(s); acc.outputConnectors[0].connect(s)
        s.par.index.expr = on_expr
        return s
    ssg = ss_chain('ssgi', 'ssgi.frag', (0, 0, 0, 1),
                   '1 if (parent.BTDR.par.Ambientocclusion or parent.BTDR.par.Ssgi) else 0', 800)
    ssr = ss_chain('ssr', 'ssr.frag', (0, 0, 0, 0), '1 if parent.BTDR.par.Ssr else 0', 1000)
    # [BTDR:BUILD.RT] M4 hardware ray tracing. The proxy scene lives in `rtscene` (chains built by Refresh,
    # [BTDR:EXT.RTPROXY]): rtscene/merge -> tri (Convert POP: quads to triangles) -> out. GLSL POPs trace it with ray queries (Collisions page).
    RX, RY = -1400, -1300
    rsc = place(C.create(baseCOMP, 'rtscene'), RX, RY)
    rmg = place(rsc.create(mergePOP, 'merge'), 800, 0)
    rtq = place(rsc.create(convertPOP, 'tri'), 1000, 0)       # acceleration structures take triangles only (POP
    rtq.par.convert = 'quadstotriangles'                       # sources are not reduced; PolyReduce pre-triangulates)
    rmg.outputConnectors[0].connect(rtq)
    rout = place(rsc.create(nullPOP, 'out'), 1200, 0)
    rtq.outputConnectors[0].connect(rout)
    # [BTDR:BUILD.RTREFR] M6c: the same scene plus the glass (only for the ray-traced refraction pass, [BTDR:EXT.RTREFR])
    rmt = place(rsc.create(mergePOP, 'merge_t'), 800, 200)
    rout.outputConnectors[0].connect(rmt)
    rtqt = place(rsc.create(convertPOP, 'tri_t'), 1000, 200); rtqt.par.convert = 'quadstotriangles'
    rmt.outputConnectors[0].connect(rtqt)
    routt = place(rsc.create(nullPOP, 'out_t'), 1200, 200)
    rtqt.outputConnectors[0].connect(routt)
    asel = place(rsc.create(selectTOP, 'avg_sel'), 800, -300)              # map averages for rt_mat ([BTDR:EXT.RTMAT])
    ares = place(rsc.create(resolutionTOP, 'avg_res'), 1000, -300)
    asel.outputConnectors[0].connect(ares)
    ares.par.outputresolution = 'custom'; ares.par.resolutionw = 16; ares.par.resolutionh = 16
    _menu(ares.par.inputfiltertype, ['mipmap']); _menu(ares.par.format, ['rgba32float'])
    scn = place(C.create(selectPOP, 'rt_scene'), RX + 200, RY)
    scn.par.pop = 'rtscene/out'
    scnt = place(C.create(selectPOP, 'rt_scene_t'), RX + 200, RY + 100)
    scnt.par.pop = 'rtscene/out_t'
    # per-object materials ([BTDR:EXT.RTMAT]) and the probe uniforms ([BTDR:UNI.RTSTATIC]) as CHOPs from tables
    def tchop(nm, x, y):
        t = place(C.create(tableDAT, nm), x, y)
        t.clear(); t.appendRow(['x', 'y', 'z', 'w']); t.appendRow([0, 0, 0, 0]); t.appendRow([0, 0, 0, 0])
        c = place(C.create(dattoCHOP, nm + '_chop'), x + 200, y)
        c.par.dat = t; c.par.output = 'chanpercol'; c.par.firstrow = 'names'; c.par.firstcolumn = 'values'
        return c
    rmat = tchop('rt_mat', RX, RY - 150)
    rsta = tchop('rt_static', RX, RY - 250)
    zf = dat('zero_frag', 'out vec4 fragColor;\nvoid main() { fragColor = vec4(0.0); }\n', X0 - 250, -200)
    def rtpop(nm, comp, src, attrs, chop, samplers, x, y, build, scene=None):
        scene = scene or scn
        g = place(C.create(glslPOP, nm), x, y)
        undock(g)
        g.par.computedat = D[comp]
        src.outputConnectors[0].connect(g); scene.outputConnectors[0].connect(g)
        # [BTDR:BUILD.RTAS] a GLSL POP rebuilds its acceleration structure on every cook. Fast Trace costs ~0.65 ms per
        # build for a 32k-triangle proxy (5080 Laptop, measured), Fast Build ~0.03 ms including 130k rays: the pass that
        # cooks every frame (reflections) uses Fast Build; the probes (cook on change, many rays) use Fast Trace.
        g.par.asname = 'uScene'; g.par.colpop = scene; g.par.buildflag = build; g.par.opaquecolgeo = True
        g.par.attrclass = 'point'
        g.seq.attr.numBlocks = len(attrs)
        for i, a in enumerate(attrs):
            getattr(g.par, 'attr%dname' % i).val = 'custom'; getattr(g.par, 'attr%dcustomname' % i).val = a
            getattr(g.par, 'attr%dtype' % i).val = 'float'; getattr(g.par, 'attr%dnumcomps' % i).val = '4'
        g.seq.array.numBlocks = 2
        g.par.array0name = 'uB'; g.par.array0type = 'vec4'; g.par.array0chop = chop; g.par.array0arraytype = 'uniformarray'
        g.par.array1name = 'rtMat'; g.par.array1type = 'vec4'; g.par.array1chop = rmat; g.par.array1arraytype = 'texturebuffer'
        g.seq.sampler.numBlocks = len(samplers)
        for i, (sn, top) in enumerate(samplers):
            getattr(g.par, 'sampler%dname' % i).val = sn
            getattr(g.par, 'sampler%dtop' % i).val = top
            getattr(g.par, 'sampler%dfilter' % i).val = 'linear'
            for e in ('u', 'v'): getattr(g.par, 'sampler%dextend%s' % (i, e)).val = 'repeat' if sn.startswith('sEnv') else 'hold'
        return g
    def p2t(nm, pop, attr, x, y, dim3):
        t = place(C.create(poptoTOP, nm), x, y)
        t.par.pop = pop; t.par.rgbamode = 'custom'; t.par.extract = 'point'; t.par.attribscope = attr; t.par.layout = 'popdim'
        if dim3:
            t.par.dim = '3d'; t.par.toptype = 'texture3d'
        _menu(t.par.format, ['rgba16float'])
        return t
    # [BTDR:BUILD.RTPROBES] probe grid (16x8x16 High / 12x6x12 Low until the first Refresh, then about 2048 / 860 probes
    # spread evenly over the scene bounds, EXT.RTGRIDDIMS); cooks only
    # when the proxy scene or rt_static change (static scene: zero per frame)
    pgd = place(C.create(gridPOP, 'rt_probe_grid'), RX + 200, RY - 400)
    pgd.par.surftype = 'points'; pgd.par.normal = 'none'; pgd.par.texture = 'none'
    pgd.par.cols.expr = "16 if parent.BTDR.par.Quality != 'low' else 12"
    pgd.par.rows.expr = "8 if parent.BTDR.par.Quality != 'low' else 6"
    pgd.par.slices.expr = "16 if parent.BTDR.par.Quality != 'low' else 12"
    rpr = rtpop('rt_probes', 'rt_probes.comp', pgd, ['SH0', 'SH1', 'SH2', 'SH3'], rsta,
                [('sEnv', 'env_src'), ('sEnvAtlas', 'env_atlas')], RX + 400, RY - 400, 'fasttrace')
    zp = glsl('rt_probe_off', zf, [], 2, 2, ['rgba16float'], RX + 600, RY - 900, shared=False)
    zp.par.type = 'texture3d'; zp.par.depth = 'custom'; zp.par.customdepth = 2
    psrc = []
    for i in range(4):
        t = p2t('probe_sh%d' % i, rpr, 'SH%d' % i, RX + 600, RY - 400 - i * 110, True)
        sw_ = place(C.create(switchTOP, 'probe_src%d' % i), RX + 800, RY - 400 - i * 110)
        zp.outputConnectors[0].connect(sw_); t.outputConnectors[0].connect(sw_)
        sw_.par.index.expr = '1 if (parent.BTDR.par.Raytracing and parent.BTDR.par.Rtavailable and parent.BTDR.par.Rtgi) else 0'
        psrc.append(sw_)
    # [BTDR:BUILD.RTREFL] traced reflections: one ray per pixel at 1/4 (High) or 1/6 (Low) resolution, every frame
    TW = 'max(int(parent.BTDR.par.Resolutionw) // (4 if parent.BTDR.par.Quality != "low" else 6), 1)'
    TH = 'max(int(parent.BTDR.par.Resolutionh) // (4 if parent.BTDR.par.Quality != "low" else 6), 1)'
    rgd = place(C.create(gridPOP, 'rt_refl_grid'), RX + 200, RY - 900)
    rgd.par.surftype = 'points'; rgd.par.normal = 'none'; rgd.par.texture = 'none'
    rgd.par.cols.expr = TW; rgd.par.rows.expr = TH
    rrf = rtpop('rt_refl', 'rt_refl.comp', rgd, ['Refl'], C.op('uniforms'),
                [('sNrm', 'gbuf1'), ('sPos', 'gbuf2'), ('sEnv', 'env_src'), ('sEnvAtlas', 'env_atlas')]
                + [('sProbe%d' % i, 'probe_src%d' % i) for i in range(4)], RX + 400, RY - 900, 'fastbuild')
    rtt = p2t('rt_refl_top', rrf, 'Refl', RX + 600, RY - 900, False)
    rth = place(C.create(feedbackTOP, 'rt_hist'), RX + 800, RY - 1000)
    rtt.outputConnectors[0].connect(rth)
    rta = glsl('rt_acc', D['rt_accum.frag'], [rtt, rth, rs[2], rs[1]], TW, TH, ['rgba16float'], RX + 800, RY - 900)
    rth.par.top = rta
    roff = place(C.create(constantTOP, 'rt_off'), RX + 800, RY - 800)
    roff.par.colorr = roff.par.colorg = roff.par.colorb = 1; roff.par.alpha = 0
    res(roff, 4, 4, ['rgba16float'])
    rts = place(C.create(switchTOP, 'rt_src'), RX + 1000, RY - 900)
    roff.outputConnectors[0].connect(rts); rta.outputConnectors[0].connect(rts)
    rts.par.index.expr = '1 if (parent.BTDR.par.Raytracing and parent.BTDR.par.Rtavailable and parent.BTDR.par.Rtreflections) else 0'
    # [BTDR:BUILD.COMPINLINE] composite computes the lighting terms itself ([BTDR:COMP.INLINE]); `lighting` and lit1..3
    # are only pulled by the Debug View. 2D inputs in order, then 3D (environment atlas, probes).
    comp = glsl('composite', D['composite.frag'], rs[:3] + [shs, rs[3], esw, ssg, ssr, hfs, rts, eat] + psrc,
                RW, RH, ['rgba16float'], 200, 400)
    _menu(comp.par.inputextenduv, ['repeat'])

    # [BTDR:BUILD.TRANS] M6a front transparent layer ([BTDR:REFR.*]): the refractive mirrors scene/t* are drawn by
    # `tgbuffer` (5 colour buffers, same material shader) and by `tback` (front faces culled: the nearest back face,
    # for the thickness). `refract` composites them over the opaque image. With no transparent object the Switch TOPs
    # stay on the opaque inputs and none of these cook.
    TON = '1 if (parent.BTDR.par.Transparency and parent.BTDR.par.Transcount > 0) else 0'
    tg = place(C.create(renderTOP, 'tgbuffer'), -600, -400)
    tg.par.camera = 'cam_jit'; tg.par.geometry = 'scene/t*'; tg.par.lights = ''
    tg.par.numcolorbufs = 5
    res(tg, RW, RH, ['rgba16float'])
    _menu(tg.par.antialias, ['aa1', '1x', '1'])
    tg.par.bgcolorr = tg.par.bgcolorg = tg.par.bgcolorb = tg.par.bgcolora = 0
    tgs = []
    for i in range(5):
        r = place(C.create(renderselectTOP, 'tgbuf%d' % i), -400, -300 - i * 80)
        r.par.top = tg; r.par.bufferindex = i
        tgs.append(r)
    tb = place(C.create(renderTOP, 'tback'), -600, -800)
    tb.par.camera = 'cam_jit'; tb.par.geometry = 'scene/t*'; tb.par.lights = ''
    tb.par.numcolorbufs = 3
    res(tb, RW, RH, ['rgba16float'])
    _menu(tb.par.antialias, ['aa1', '1x', '1'])
    _menu(tb.par.cullface, ['frontfaces'])
    tb.par.bgcolorr = tb.par.bgcolorg = tb.par.bgcolorb = tb.par.bgcolora = 0
    tbs = []
    for i in (1, 2):
        r = place(C.create(renderselectTOP, 'tback%d' % i), -400, -760 - i * 80)
        r.par.top = tb; r.par.bufferindex = i
        tbs.append(r)
    # [BTDR:BUILD.RTREFR] M6c ray-traced refraction: rt_refr traces the glass scene from the front layer at the
    # reflection grid's resolution, accumulated like the traced reflections; `rtr_src` keeps it bypassed unless the
    # Refraction Method is Hybrid / Ray Traced, ray tracing is available and there is glass.
    RTRON = ("1 if (parent.BTDR.par.Transparency and parent.BTDR.par.Transcount > 0 and parent.BTDR.par.Raytracing "
             "and parent.BTDR.par.Rtavailable and parent.BTDR.par.Refrmethod != 'screen') else 0")
    rrr = rtpop('rt_refr', 'rt_refr.comp', rgd, ['Refr'], C.op('uniforms'),
                [('sTNrm', 'tgbuf1'), ('sTPos', 'tgbuf2'), ('sTIor', 'tgbuf4'), ('sTBase', 'tgbuf0'), ('sPos', 'gbuf2'), ('sEnv', 'env_src'),
                 ('sEnvAtlas', 'env_atlas')] + [('sProbe%d' % i, 'probe_src%d' % i) for i in range(4)],
                RX + 400, RY - 1200, 'fastbuild', scene=scnt)
    for i in range(rrr.seq.sampler.numBlocks):        # positions must not be blended between texels
        if getattr(rrr.par, 'sampler%dname' % i).eval() in ('sTNrm', 'sTPos', 'sTIor', 'sTBase', 'sPos'):
            getattr(rrr.par, 'sampler%dfilter' % i).val = 'nearest'
    rrt = p2t('rt_refr_top', rrr, 'Refr', RX + 600, RY - 1200, False)
    rrh = place(C.create(feedbackTOP, 'rt_refr_hist'), RX + 800, RY - 1300)
    rrt.outputConnectors[0].connect(rrh)
    rra = glsl('rt_refr_acc', D['rt_accum.frag'], [rrt, rrh, tgs[2], tgs[1]], TW, TH, ['rgba16float'], RX + 800, RY - 1200)
    rrh.par.top = rra
    rroff = place(C.create(constantTOP, 'rt_refr_off'), RX + 800, RY - 1100)
    rroff.par.colorr = rroff.par.colorg = rroff.par.colorb = 0; rroff.par.alpha = 0
    res(rroff, 4, 4, ['rgba16float'])
    rrs = place(C.create(switchTOP, 'rtr_src'), RX + 1000, RY - 1200)
    rroff.outputConnectors[0].connect(rrs); rra.outputConnectors[0].connect(rrs)
    rrs.par.index.expr = RTRON
    refr = glsl('refract', D['refract.frag'], [comp, rs[2], rs[1]] + tgs + [tbs[1], tbs[0], shs, esw, rrs, eat],
                RW, RH, ['rgba16float'], 400, -300)
    refr.par.numcolorbufs = 3
    try: _menu(refr.par.inputfiltertype, ['mipmap'])
    except Exception as e: BLOG.append('refract filter %r' % e)
    rsel = []
    for i in (1, 2):
        r = place(C.create(renderselectTOP, 'refract%d' % i), 600, -300 - i * 80)
        r.par.top = refr; r.par.bufferindex = i
        rsel.append(r)
    def tsw(nm, a, b, y):
        s_ = place(C.create(switchTOP, nm), 800, y)
        a.outputConnectors[0].connect(s_); b.outputConnectors[0].connect(s_)
        s_.par.index.expr = TON
        return s_
    tsrc = tsw('trans_src', comp, refr, -300)
    tpos = tsw('tpos_src', rs[2], rsel[0], -400)
    tnrm = tsw('tnrm_src', rs[1], rsel[1], -480)

    # [BTDR:BUILD.BLEND] M6b blended transparency ([BTDR:FWD.*]): the blended mirrors scene/b* are drawn forward-lit
    # by `tblend` (premultiplied, Render TOP Transparency = Sorted or Order Independent), then `blend_comp` lays them
    # over the image. `ub_tex` is the uniform block as a texture for the forward material ([BTDR:FWD.UB]).
    if M6B:
        BON = '1 if (parent.BTDR.par.Transparency and parent.BTDR.par.Blendcount > 0) else 0'
        ubt = place(C.create(choptoTOP, 'ub_tex'), -1000, 700)
        ubt.par.chop = uni
        try: _menu(ubt.par.dataformat, ['rgba'])
        except Exception as e: BLOG.append('ub_tex dataformat %r' % e)
        _menu(ubt.par.format, ['rgba32float'])
        tbl = place(C.create(renderTOP, 'tblend'), -600, -1000)
        tbl.par.camera = 'cam_jit'; tbl.par.geometry = 'scene/b*'; tbl.par.lights = ''
        res(tbl, RW, RH, ['rgba16float'])
        _menu(tbl.par.antialias, ['aa1', '1x', '1'])
        tbl.par.bgcolorr = tbl.par.bgcolorg = tbl.par.bgcolorb = tbl.par.bgcolora = 0
        tbl.par.transparency.expr = "'orderind' if parent.BTDR.par.Blendmethod == 'orderind' else 'sortedblending'"
        tbl.par.transpeellayers.expr = 'parent.BTDR.par.Peellayers'
        bcm = glsl('blend_comp', D['blend_comp.frag'], [tsrc, tbl], RW, RH, ['rgba16float'], 900, -150, shared=False)
        bsrc = place(C.create(switchTOP, 'blend_src'), 1000, -200)
        tsrc.outputConnectors[0].connect(bsrc); bcm.outputConnectors[0].connect(bsrc)
        bsrc.par.index.expr = BON
    else:
        bsrc = tsrc

    # [BTDR:BUILD.FOG] volumetric fog: froxel scattering (3D) -> front-to-back integration (3D) -> apply per pixel,
    # before TAA (it resolves the slice dither). Bypassed by a Switch TOP when off.
    # [BTDR:BUILD.FOGRES] grid size: Fog Resolution, or from Quality when Auto
    def _fr(i, auto_hi, auto_lo):
        return ("{'low': %d, 'medium': %d, 'high': %d, 'ultra': %d}.get(parent.BTDR.par.Fogres.eval(), "
                "%d if parent.BTDR.par.Quality != 'low' else %d)" % (
                    (128, 72, 48)[i], (160, 90, 64)[i], (240, 135, 96)[i], (320, 180, 128)[i], auto_hi, auto_lo))
    FX = _fr(0, 160, 128)
    FY = _fr(1, 90, 72)
    FZ = _fr(2, 64, 48)
    # Both volume passes are compute shaders: one dispatch instead of one draw per slice (a 3D pixel-shader GLSL
    # TOP costs about 1 ms CPU for 64 slices), and the integration walks each column once.
    def vol(nm, comp, inputs, x, y, per_slice):
        g = glsl(nm, D['white_frag'], inputs, FX, FY, ['rgba16float'], x, y, shared=False)
        g.par.mode = 'compute'; g.par.computedat = D[comp]
        uarray(g, tbuf=True)
        g.par.type = 'texture3d'; g.par.depth = 'custom'; g.par.customdepth.expr = FZ
        g.par.autodispatchsize = False
        g.par.dispatchsizex.expr = '(int(%s) + 7) // 8' % FX
        g.par.dispatchsizey.expr = '(int(%s) + 7) // 8' % FY
        g.par.dispatchsizez.expr = FZ if per_slice else '1'
        return g
    fsc = vol('fog_scatter', 'fog_scatter.comp', [shs, esw, eat], 0, 1200, True)
    # [BTDR:BUILD.FOGACC] temporal reprojection in the volume ([BTDR:FOG.ACCUM]); the history's input is the
    # scattering pass (same size / format, does not depend on the history, so no cook loop)
    fhi = place(C.create(feedbackTOP, 'fog_hist'), 0, 1300)
    fsc.outputConnectors[0].connect(fhi)
    fac = vol('fog_accum', 'fog_accum.comp', [fsc, fhi], 100, 1300, True)
    fhi.par.top = fac
    fin = vol('fog_integrate', 'fog_integrate.comp', [fac], 200, 1200, False)
    fap = glsl('fog_apply', D['fog_apply.frag'], [bsrc, tpos, fin], RW, RH, ['rgba16float'], 200, 1050)
    _menu(fap.par.inputextenduv, ['hold'])
    fsw = place(C.create(switchTOP, 'fog_src'), 250, 300)
    bsrc.outputConnectors[0].connect(fsw); fap.outputConnectors[0].connect(fsw)
    fsw.par.index.expr = '1 if parent.BTDR.par.Fog else 0'
    taa = glsl('taa', D['taa.frag'], [fsw, fbk, tpos, tnrm], RW, RH, ['rgba16float'], 300, 400)
    fbk.par.top = taa
    # [BTDR:BUILD.POST] depth of field -> motion blur (each bypassed by a Switch TOP when off), bloom, auto exposure
    def sw(nm, a, b, expr, x, y):
        s = place(C.create(switchTOP, nm), x, y)
        a.outputConnectors[0].connect(s); b.outputConnectors[0].connect(s)
        s.par.index.expr = expr
        return s
    dof = glsl('dof', D['dof.frag'], [taa], RW, RH, ['rgba16float'], 300, 700)
    sdof = sw('post_dof', taa, dof, '1 if parent.BTDR.par.Dof else 0', 500, 700)
    mbl = glsl('mblur', D['mblur.frag'], [sdof], RW, RH, ['rgba16float'], 700, 700)
    smb = sw('post_mb', sdof, mbl, '1 if parent.BTDR.par.Motionblur else 0', 900, 700)
    HW, HH = 'max(int(parent.BTDR.par.Resolutionw) // 2, 1)', 'max(int(parent.BTDR.par.Resolutionh) // 2, 1)'
    bpre = glsl('bloom_pre', D['bloom_pre.frag'], [smb], HW, HH, ['rgba16float'], 1100, 850)   # + ae_exposure below
    # [BTDR:BUILD.BLOOM] mip chain ([BTDR:BLOOM.CHAIN]): 13-tap downsample 1/2 -> 1/4 ... 1/128, then tent upsample
    # back to 1/2, blending each level (radius = uBloom.w). Bypassed by a Switch TOP when the intensity is 0.
    BLV = int(globals().get("BLOOM_LEVELS", 6))
    downs = [bpre]
    for k in range(1, BLV + 1):
        d = 2 ** (k + 1)
        downs.append(glsl('bloom_d%d' % k, D['bloom_karis.frag' if k == 1 else 'bloom_down.frag'], [downs[-1]],
                          'max(int(parent.BTDR.par.Resolutionw) // %d, 1)' % d, 'max(int(parent.BTDR.par.Resolutionh) // %d, 1)' % d,
                          ['rgba16float'], 1100 + 150 * k, 850))
    up = downs[-1]
    for k in range(BLV - 1, -1, -1):
        d = 2 ** (k + 1)
        if k == 3 and BLV > 4:
            # [BTDR:BUILD.BLOOMLOW] Low quality stops the chain at 1/32: bloom_u3 takes bloom_d4 instead of bloom_u4, so the
            # four coarsest TOPs (d5, d6, u5, u4) are not pulled (~0.1 ms CPU); the halo is a little tighter
            lv = place(C.create(switchTOP, 'bloom_lvl'), 1100 + 150 * k, 1050)
            up.outputConnectors[0].connect(lv); downs[4].outputConnectors[0].connect(lv)
            lv.par.index.expr = "1 if parent.BTDR.par.Quality == 'low' else 0"
            up = lv
        up = glsl('bloom_u%d' % k, D['bloom_up.frag'], [up, downs[k]],
                  'max(int(parent.BTDR.par.Resolutionw) // %d, 1)' % d, 'max(int(parent.BTDR.par.Resolutionh) // %d, 1)' % d,
                  ['rgba16float'], 1100 + 150 * k, 950)
    boff = place(C.create(constantTOP, 'bloom_off'), 1100, 1000)
    boff.par.colorr = boff.par.colorg = boff.par.colorb = 0; boff.par.alpha = 1
    res(boff, 4, 4, ['rgba16float'])
    bsrc = place(C.create(switchTOP, 'bloom_src'), 1300, 1000)
    boff.outputConnectors[0].connect(bsrc); up.outputConnectors[0].connect(bsrc)
    bsrc.par.index.expr = '1 if parent.BTDR.par.Bloom > 0 else 0'
    # [BTDR:BUILD.AE] auto exposure: metering at 256x144 -> Analyze TOP average -> 1x1 adaptation with feedback
    lum = glsl('ae_lum', D['lum.frag'], [smb], 256, 144, ['rgba32float'], 1100, 1100)
    _menu(lum.par.inputfiltertype, ['mipmap'])
    ana = place(C.create(analyzeTOP, 'ae_avg'), 1300, 1100)
    lum.outputConnectors[0].connect(ana)
    ana.par.op = 'average'
    try: ana.par.analyzechannel = 'independent'
    except Exception as e: BLOG.append('analyzechannel %r' % e)
    _menu(ana.par.format, ['rgba32float'])
    aeh = place(C.create(feedbackTOP, 'ae_hist'), 1500, 1200)
    ana.outputConnectors[0].connect(aeh)
    expo = glsl('ae_exposure', D['exposure.frag'], [ana, aeh], 1, 1, ['rgba32float'], 1500, 1100)
    aeh.par.top = expo
    # [BTDR:BUILD.AEOFF] with Auto Exposure off grade / bloom_pre read a 1x1 constant (log2 0, multiplier 1) through
    # a Switch, so the metering chain (ae_lum, ae_avg, ae_exposure) is not pulled: ~0.1 ms CPU. Before 0.5.1 the
    # shaders ignored the input when off, but TD still cooked the chain every frame.
    aoff = place(C.create(constantTOP, 'ae_off'), 1500, 1000)
    aoff.par.colorr = 0; aoff.par.colorg = 1; aoff.par.colorb = 0; aoff.par.alpha = 1
    res(aoff, 1, 1, ['rgba32float'])
    asrc = place(C.create(switchTOP, 'ae_src'), 1700, 1100)
    aoff.outputConnectors[0].connect(asrc); expo.outputConnectors[0].connect(asrc)
    asrc.par.index.expr = '1 if parent.BTDR.par.Autoexposure else 0'
    asrc.outputConnectors[0].connect(bpre)
    # [BTDR:BUILD.GRADE]
    grd = glsl('grade', D['grade.frag'], [smb, bsrc, asrc], RW, RH, ['rgba8fixed'], 400, 400)
    dbg = glsl('debug', D['debug.frag'], rs[:3] + [rs[3], litb[0], litb[1], litb[2], ssg, ssr, litb[3], rts] + psrc, RW, RH, ['rgba8fixed'], 400, 250)
    view = place(C.create(switchTOP, 'view'), 600, 400)
    grd.outputConnectors[0].connect(view); dbg.outputConnectors[0].connect(view)
    view.par.index.expr = "0 if parent.BTDR.par.Debugview == 'final' else 1"
    dep = glsl('depth', D['depth.frag'], [rs[1], rs[2]], RW, RH, ['r32float', 'mono32float'], 400, 100)

    # [BTDR:BUILD.COVER] cover / loading screen on output 1 ([BTDR:EXT.COVER], shaders/cover.frag): the TD学长
    # logo (signed distance field, no image file) with a light sweep while loading, then the render once a camera
    # is found and the pipeline has warmed up. `out_src` only pulls the selected branch, so the cover costs
    # nothing once the render is up and the render chain is only pulled behind the loading screen by `cover_warm`.
    cst = place(C.create(constantCHOP, 'cover_state'), 400, 800)
    cst.par.name0 = 'show'; cst.par.value0 = 1; cst.par.name1 = 'mode'; cst.par.value1 = 0
    cfr = dat('cover_frag', _shader('cover.frag'), X0, 300 - (len(names) + 2) * 100)
    cov = place(C.create(glslTOP, 'cover'), 400, 700)
    cov.par.pixeldat = cfr
    undock(cov)
    res(cov, RW, RH, ['rgba8fixed'])
    cov.par.vec0name = 'uCover'; cov.par.vec0valuex.expr = 'absTime.seconds'
    cov.par.vec0valuey.expr = "op('cover_state')['mode']"
    def ctext(nm, txt, size, y, bold, alpha, x):
        t = place(C.create(textTOP, nm), x, 850)
        if isinstance(txt, str) and txt.startswith('='): t.par.text.expr = txt[1:]
        else: t.par.text = txt
        try: t.par.font = 'Microsoft YaHei'
        except Exception as e: BLOG.append('cover font %r' % e)
        t.par.bold = bold
        t.par.fontsizexunit = 'fract'; t.par.fontsizex = size; t.par.keepfontratio = True
        t.par.positionunit = 'fraction'; t.par.positionx = 0; t.par.positiony = y
        t.par.fontcolorr = t.par.fontcolorg = t.par.fontcolorb = 0.04; t.par.fontalpha = alpha
        t.par.bgalpha = 0
        res(t, RW, RH)
        return t
    layers = [ctext('cover_title', 'BetterTDRender', 0.05, -0.30, True, 1.0, 600),
              ctext('cover_status', "=('Loading…' if op('cover_state')['mode'] < 0.5 else "
                                    "'Waiting for a camera  ·  set Camera on the Render page')", 0.022, -0.372, False, 0.7, 750),
              ctext('cover_credit', 'TD学长  ·  微信 TD_Xuezhang  ·  闲鱼搜“TD学长”', 0.02, -0.44, False, 0.85, 900)]
    prev = cov
    for i, t in enumerate(layers):
        ov = place(C.create(overTOP, 'cover_ov%d' % i), 600 + 150 * i, 700)
        t.outputConnectors[0].connect(ov.inputConnectors[0]); prev.outputConnectors[0].connect(ov.inputConnectors[1])
        prev = ov
    osrc = place(C.create(switchTOP, 'out_src'), 700, 550)
    view.outputConnectors[0].connect(osrc); prev.outputConnectors[0].connect(osrc)
    osrc.par.index.expr = "int(op('cover_state')['show'])"
    warm = place(C.create(executeDAT, 'cover_warm'), X0 - 250, -100)
    warm.text = ('# [BTDR:EXT.COVER] behind the loading screen: pull the render so it warms up\n'
                 'def onFrameStart(frame):\n    op(\'view\').cook(force=True)\n    return\n')
    warm.par.framestart = True; warm.par.active = False

    # [BTDR:BUILD.OUT] outputs: 1 final image (sRGB; the cover until the render is up), 2 HDR linear, 3 depth
    for i, src in enumerate((osrc, smb, dep)):
        o = place(C.create(outTOP, 'out%d' % (i + 1)), 800, 400 - i * 150)
        src.outputConnectors[0].connect(o)
    try: C.par.opviewer = './out1'
    except Exception as e: BLOG.append('opviewer %r' % e)
    C.viewer = True
    return C

try:
    _tmp = op('/project1').op('btdr_build') or op('/project1').create(baseCOMP, 'btdr_build')
    _tmp.nodeX, _tmp.nodeY = 900, -250
    _C = build_btdr(_tmp)
    os.makedirs(BT + '/release', exist_ok=True)
    os.makedirs(BT + '/out', exist_ok=True)
    _C.save(BT + '/release/BTDR.tox')
    BLOG.append('saved release/BTDR.tox (%d bytes), %d ops, version %s' % (os.path.getsize(BT + '/release/BTDR.tox'), len(_C.findChildren()), VERSION))
    # [BTDR:BUILD.PALETTE] also copy into the user's TouchDesigner Palette (Documents/Derivative/Palette/BTDR/),
    # so it shows up in the Palette panel under My Components. Skipped when that folder does not exist.
    _pal = os.path.join(os.path.expanduser('~'), 'Documents', 'Derivative', 'Palette')
    if os.path.isdir(_pal):
        import shutil
        os.makedirs(os.path.join(_pal, 'BTDR'), exist_ok=True)
        shutil.copyfile(BT + '/release/BTDR.tox', os.path.join(_pal, 'BTDR', 'BTDR.tox'))
        BLOG.append('copied to %s' % os.path.join(_pal, 'BTDR', 'BTDR.tox').replace('\\', '/'))
    _tmp.destroy()
    BLOG.insert(0, 'STATUS DONE')
except Exception:
    BLOG.insert(0, 'STATUS ERROR')
    BLOG.append(traceback.format_exc())
open(BT + '/out/build_log.txt', 'w', encoding='utf-8').write('\n'.join(BLOG))
