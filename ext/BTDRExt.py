# [BTDR:FILE.EXT] BTDRExt — extension class of the renderBTDR component.
# Resolves the Camera / Geometry / Lights parameters and builds the internal "scene mirror".
import math
import numpy as np

QUALITY = {
    # [BTDR:EXT.QUALITY] values written into the performance-related parameters when Quality is not Custom
    'high': dict(Shadowres='4096'),
    'low':  dict(Shadowres='2048'),
}
SRGB = '1 if parent.BTDR.par.Srgbcolors else 0'
# [BTDR:EXT.NCONV] negative normal strength = DirectX (Y-) normal map, see gbuffer.frag
NCONV = "(-1 if parent.BTDR.par.Normalconvention == 'directx' else 1)"
CHANNELS = ('metallicmapchannelsource', 'roughnessmapchannelsource', 'ambientocclusionmapchannelsource')
# [BTDR:EXT.REFRPRESET] Refractive slot presets: IOR, roughness override (-1 = the material's), thin walled,
# absorption distance (m). Material colours still come from the PBR MAT.
REFR_PRESETS = {
    'glass':   (1.5, -1, False, 1.0),
    'frosted': (1.5, 0.35, False, 1.0),
    'tinted':  (1.52, -1, False, 0.4),
    'water':   (1.333, -1, False, 2.0),
    'ice':     (1.31, 0.12, False, 1.0),
    'crystal': (1.54, -1, False, 1.0),
    'diamond': (2.42, -1, False, 1.0),
    'acrylic': (1.49, -1, False, 0.3),
    'window':  (1.5, -1, True, 1.0),
}

# [BTDR:EXT.SSSPRESET] 0.8.0 Subsurface slot presets: scatter colour, radius (m), transmission colour, thin (sheet),
# sheet thickness (m). Strength / texture detail / transmission strength are left as they are.
SSS_PRESETS = {
    'skin':   ((0.90, 0.35, 0.20), 0.012, (1.00, 0.40, 0.25), False, 0.0005),
    'jade':   ((0.45, 0.95, 0.60), 0.020, (0.70, 1.00, 0.80), False, 0.0005),
    'wax':    ((1.00, 0.75, 0.45), 0.015, (1.00, 0.80, 0.60), False, 0.0005),
    'marble': ((0.95, 0.93, 0.88), 0.008, (0.80, 0.80, 0.78), False, 0.0005),
    'milk':   ((1.00, 0.97, 0.90), 0.025, (1.00, 1.00, 0.95), False, 0.0005),
    'soap':   ((0.95, 0.90, 0.95), 0.010, (0.95, 0.90, 0.95), False, 0.0005),
    'leaf':   ((0.50, 0.90, 0.30), 0.003, (1.00, 1.00, 0.50), True, 0.0005),
    'paper':  ((1.00, 0.97, 0.92), 0.002, (1.00, 0.95, 0.85), True, 0.0003),
}
MAX_SSS = 8


# [BTDR:EXT.INFO] author / contact, shown on the Info page and in the start-up dialog
INFO_TEXT = ('BetterTDRender (renderBTDR) 来自 TD学长\n'
             'BetterTDRender is made by TD学长 (Xikai Lei)\n\n'
             '微信 WeChat: TD_Xuezhang\n'
             '闲鱼 Xianyu: 搜索 “TD学长”\n'
             '邮箱 Email: max_lei_in_london@163.com\n'
             '            ginicholaslbert@gmail.com\n\n'
             '免费用于非商业用途；商业使用需要授权，请联系作者。\n'
             'Free for noncommercial use. Commercial use requires a license from the author.\n'
             'https://github.com/Maxwel-Lei/BetterTDRender')
COVER_WARM_FRAMES = 60          # [BTDR:EXT.COVER] frames the loading screen stays up while the pipeline warms up
COVER_POLL_FRAMES = 30          # how often to look for the camera while waiting for one


class BTDRExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.warmed = False         # not stored: every project start / new instance shows the loading screen once

    # ------------------------------------------------------------------ cover, loading screen, info
    def _cover(self, show, mode):
        # [BTDR:EXT.COVER] output 1 shows the cover (`cover_state`: show 1) until a camera is found and the
        # pipeline has rendered COVER_WARM_FRAMES frames; mode 0 = loading animation, 1 = waiting for a camera.
        # While the loading screen is up `cover_warm` pulls `view` every frame, so shaders compile and the
        # temporal histories fill behind it; with the cover off it is inactive and costs nothing.
        C = self.ownerComp
        cs = C.op('cover_state')
        if cs is None:
            return
        if cs.par.value0.eval() != show:
            cs.par.value0 = show
        if cs.par.value1.eval() != mode:
            cs.par.value1 = mode
        w = C.op('cover_warm')
        if w is not None and w.par.active.eval() != (show == 1 and mode == 0):
            w.par.active = (show == 1 and mode == 0)

    def _cover_after_refresh(self, cam):
        C = self.ownerComp
        if cam is None:
            self._cover(1, 1)               # `scene_watch` refreshes as soon as the camera appears ([BTDR:EXT.WATCH])
        elif not self.warmed and not C.time.play:
            # [BTDR:EXT.PAUSED] timeline paused: frames may not advance at all (then no delayed call ever fires and
            # the loading screen would stay up, found in 0.7.4), so show the render straight away
            self.warmed = True
            self._cover(0, 0)
        elif not self.warmed:
            self._cover(1, 0)
            run("args[0].CoverDone() if (args[0].valid and hasattr(args[0], 'CoverDone')) else None",
                C, delayFrames=COVER_WARM_FRAMES)
        else:
            self._cover(0, 0)

    def CoverDone(self):
        C = self.ownerComp
        self.warmed = True
        cam = C.par.Camera.eval()
        self._cover(0, 0) if (cam is not None and cam.OPType == 'cameraCOMP') else self._cover(1, 1)

    def _scene_sig(self):
        # [BTDR:EXT.WATCH] what Camera / Geometry / Lights resolve to right now
        C = self.ownerComp
        cam = C.par.Camera.eval()
        def one(g):
            m = g.par.material.eval()
            return (g.path, m.path if m is not None else '',
                    tuple(c.name for c in g.children if c.family in ('SOP', 'POP') and c.render))
        return (cam.path if (cam is not None and cam.OPType == 'cameraCOMP') else '',
                tuple(one(g) for g in self._geos()),
                tuple((l.path, l.par.lighttype.eval() if l.OPType == 'lightCOMP' else '')        # (0.9.0) main / local
                      for l in self._find(C.par.Lights.eval(), ('lightCOMP', 'ambientlightCOMP'))),
                tuple((e.path, bool(e.par.envlightmap.eval())) for e in self._find(C.par.Lights.eval(), ('environmentlightCOMP',))))

    def WatchScene(self):
        # [BTDR:EXT.WATCH] called by `scene_watch` every COVER_POLL_FRAMES frames: a camera, Geometry COMP or light
        # added, deleted or renamed, a Render flag toggled, another material assigned or another SOP / POP given the
        # Render flag (0.7.5) refreshes the scene by itself (before 0.7.4 that needed Refresh
        # Scene: a renderer dropped in before the geometry existed stayed empty, and the empty ray-tracing scene
        # showed compile errors). Costs a few ops() lookups twice a second.
        if self.SyncShell() or self._scene_sig() != getattr(self, 'sig', None):
            self.Refresh()

    def ShowInfo(self, once=False):
        # [BTDR:EXT.INFO] the start-up dialog: once per TouchDesigner session for all instances (once=True),
        # or every time from the Info page's button
        import sys
        if once:
            # [BTDR:EXT.INFOONCE] 0.7.5: the Info page's Show At Startup switches itself off after the first time, so
            # a saved project does not open the dialog again; and never more than once per TouchDesigner session
            C = self.ownerComp
            p = getattr(C.par, 'Startupinfo', None)
            if p is not None and not p.eval():
                return
            if p is not None:
                p.val = False
            if getattr(sys, '_btdr_info_shown', False):
                return
            sys._btdr_info_shown = True
        try:
            op.TDResources.PopDialog.Open(text=INFO_TEXT, title='BetterTDRender · TD学长', buttons=['OK'],
                                          escButton=1, enterButton=1, escOnClickAway=True)
        except Exception:
            try:
                ui.messageBox('BetterTDRender · TD学长', INFO_TEXT, buttons=['OK'])
            except Exception:
                pass

    # ------------------------------------------------------------------ shell (0.7.6)
    def _shell(self):
        # [BTDR:EXT.SHELL] the renderer can sit inside a thin public Base COMP (tools/make_shell.py, tag BTDRshell)
        # so that the core can be made private (TD Privacy): a private COMP cannot show an inner TOP as its node
        # viewer, the shell can. The shell carries a copy of every custom parameter; the core's parameters are bound
        # to them (OP-type ones by expression, so relative paths resolve next to the shell).
        p = self.ownerComp.parent()
        return p if (p is not None and 'BTDRshell' in p.tags) else None

    def SyncShell(self):
        # keep the sequences (Refractive / Blended slots) the same length as the shell's and bind new blocks
        C = self.ownerComp
        shell = self._shell()
        if shell is None:
            return False
        changed = False
        for s in C.seq:
            if s.name in ('ext', 'iop'):
                continue
            t = getattr(shell.seq, s.name, None)
            if t is not None and s.numBlocks != t.numBlocks:
                s.numBlocks = t.numBlocks
                changed = True
        for p in C.customPars:
            q = getattr(shell.par, p.name, None)
            if q is None or p.isPulse:
                continue
            if p.style in ('OP', 'OBJ', 'Object', 'TOP', 'COMP', 'SOP', 'CHOP', 'DAT', 'MAT', 'PanelCOMP'):
                if p.mode != ParMode.EXPRESSION:
                    p.expr = 'parent().par.%s.eval()' % p.name; p.mode = ParMode.EXPRESSION; changed = True
            elif p.mode != ParMode.BIND:
                p.bindExpr = 'parent().par.%s' % p.name; p.mode = ParMode.BIND; changed = True
        return changed

    # ------------------------------------------------------------------ helpers
    def _find(self, pattern, optypes):
        # [BTDR:EXT.RESOLVE] patterns are resolved like the native Render TOP: relative to the network
        # that contains renderBTDR, space separated, wildcards allowed, absolute paths allowed.
        shell = self._shell()
        base = (shell or self.ownerComp).parent()        # [BTDR:EXT.SHELL] inside a shell: the shell's network
        found = []
        for tok in str(pattern).split():
            try:
                hits = base.ops(tok)
            except Exception:
                hits = []
            for o in hits:
                if o.OPType in optypes and o not in found and o is not self.ownerComp and o is not shell:
                    found.append(o)
        return found

    def _geos(self):
        # [BTDR:EXT.GEOS] the Geometry COMPs to draw, like the native Render TOP: everything Geometry matches whose
        # Render flag is on (0.7.5: only the Render parameter was followed), plus the Geometry COMPs nested inside
        # them (0.7.5: children were not drawn); a nested COMP is drawn only if every COMP above it has its flag on.
        out = []
        def add(g):
            if not g.render or g in out:
                return
            out.append(g)
            for c in g.children:
                if c.OPType == 'geometryCOMP':
                    add(c)
        for g in self._find(self.ownerComp.par.Geometry.eval(), ('geometryCOMP',)):
            add(g)
        return out

    def _vecs(self, o, items):
        o.seq.vec.numBlocks = len(items)
        for i, (name, vals) in enumerate(items):
            getattr(o.par, 'vec%dname' % i).val = name
            for c, v in zip('xyzw', vals):
                p = getattr(o.par, 'vec%dvalue%s' % (i, c))
                if isinstance(v, str):
                    p.expr = v
                else:
                    p.expr = ''
                    p.val = v

    def _samplers(self, o, items, state=None):
        state = state or {}
        o.seq.sampler.numBlocks = len(items)
        for i, (name, expr) in enumerate(items):
            getattr(o.par, 'sampler%dname' % i).val = name
            getattr(o.par, 'sampler%dtop' % i).expr = expr
            # [BTDR:EXT.ANISO] at least 4x anisotropic filtering: keeps textures sharp at grazing angles, near-free on GPU
            a = getattr(o.par, 'sampler%danisotropy' % i, None)
            # [BTDR:EXT.SAMPLERSTATE] (0.8.3) Extend U / V and Filter follow the source material's map, by expression
            # (static: the mirror material only re-cooks when the user changes them); anisotropy = the material's, min 4x
            src = state.get(name)
            for k in ('extendu', 'extendv', 'filter'):
                q = getattr(o.par, 'sampler%d%s' % (i, k), None)
                if q is None:
                    continue
                q.expr = '%s.par.%s%s' % (src[0], src[1], k) if src else ''
            if a is not None:
                if src:
                    A = '%s.par.%sanisotropy' % src
                    a.expr = "%s.eval() if %s.menuIndex >= 2 else '4x'" % (A, A)
                else:
                    a.expr = ''; a.val = '4x'

    # ------------------------------------------------------------------ materials
    def _bind_material(self, m, src, warn, tr=None, sss=None, sprite=None):
        # [BTDR:EXT.MATERIAL] bind the internal G-Buffer material to the user's material by expression,
        # so edits to the source material show up immediately without a refresh.
        white = "parent.BTDR.op('white')"
        S = "op('%s')" % src.path if src is not None else None
        tex = lambda par: "%s.par.%s.eval() or %s" % (S, par, white)
        maps = dict(sBaseColor=white, sMetallic=white, sRoughness=white, sAO=white, sNormal=white, sEmit=white, sAlpha=white)
        base, pbr, emit, chan = (0.5, 0.5, 0.5, 1), (0, 0.5, 0, 0), (0, 0, 0, 0), (1, 1, 1, SRGB)
        # [BTDR:EXT.TRANSMAT] uTrans: opacity, IOR, absorption distance, thin walled; uTrans2: alpha map on, alpha-test
        # threshold (-1 = off), roughness override (-1 = the material's). IOR / absorption / thin / roughness come from the
        # object's Refractive slot (tr) or the global defaults; opacity and alpha test from the PBR MAT.
        tr = tr or {}
        trans = (1, tr.get('ior', 'parent.BTDR.par.Defaultior'), tr.get('absorb', 'parent.BTDR.par.Absorbdist'),
                 tr.get('thin', 0))
        trans2 = (0, -1, tr.get('rough', -1), 0)
        # [BTDR:EXT.TRANS3] (0.8.4) absorption colour (r < 0: the base colour) | refraction scale (G3, G5);
        # uOpt x: hashed alpha test (G4)
        trans3 = tr.get('trans3', (-1, 1, 1, 1))
        opt = ("1 if parent.BTDR.par.Alphatestmode == 'hashed' else 0", 0, 0, 0)
        state, uv0, uv1 = {}, (0, 0, 0, 0), (0, 0, 0, 0)
        t = src.OPType if src is not None else None
        if t == 'pbrMAT':
            base = tuple('%s.par.basecolor%s' % (S, c) for c in 'rgb') + (1,)
            pbr = ('%s.par.metallic' % S, '%s.par.roughness' % S, '%s.par.ambientocclusion' % S,
                   '(%s.par.bumpscale.eval() if %s.par.normalmap.eval() else 0) * %s' % (S, S, NCONV))
            emit = tuple('%s.par.emit%s' % (S, c) for c in 'rgb') + ('1 if %s.par.emitmap.eval() else 0' % S,)
            chan = tuple('%s.par.%s.menuIndex' % (S, c) for c in CHANNELS) + (SRGB,)
            maps = dict(sBaseColor=tex('basecolormap'), sMetallic=tex('metallicmap'), sRoughness=tex('roughnessmap'),
                        sAO=tex('ambientocclusionmap'), sNormal=tex('normalmap'), sEmit=tex('emitmap'), sAlpha=tex('alphamap'))
            trans = ('%s.par.alphafront' % S,) + trans[1:]
            trans2 = ('1 if %s.par.alphamap.eval() else 0' % S,
                      '(%s.par.alphathreshold.eval() if %s.par.alphatest.eval() else -1)' % (S, S)) + trans2[2:]
            state, uv0, uv1 = self._uv_codes(src, S, warn)
        elif t == 'phongMAT':
            if hasattr(src.par, 'colormapextendu'):
                state = dict(sBaseColor=(S, 'colormap'))
            base = tuple('%s.par.diff%s' % (S, c) for c in 'rgb') + (1,)
            emit = tuple('%s.par.emit%s' % (S, c) for c in 'rgb') + (0,)
            maps['sBaseColor'] = tex('colormap')
            warn.append('%s is a Phong MAT: only its diffuse colour and colour map are used (roughness 0.5).' % src.path)
        elif t == 'constantMAT':
            if hasattr(src.par, 'colormapextendu'):
                state = dict(sBaseColor=(S, 'colormap'))
            base = tuple('%s.par.color%s' % (S, c) for c in 'rgb') + (1,)
            maps['sBaseColor'] = tex('colormap')
            trans2 = trans2[:3] + (1,)          # [BTDR:EXT.UNLIT] unlit like in TD: colour only, no lighting or reflections
        elif src is not None:
            warn.append('%s (%s) is not supported: rendered with the default grey material. Use a PBR MAT.' % (src.path, src.OPType))
        # [BTDR:EXT.SSSMAT] subsurface profile = Subsurface slot index (static); unlit materials never scatter
        k = -1 if (sss is None or t == 'constantMAT') else sss
        scr = ('1.0 / max(1, parent.BTDR.par.Resolutionw.eval())', '1.0 / max(1, parent.BTDR.par.Resolutionh.eval())', 0, 0)
        self._vecs(m, [('uBase', base), ('uPBR', pbr), ('uEmit', emit), ('uChan', chan), ('uTrans', trans), ('uTrans2', trans2),
                       ('uTrans3', trans3), ('uOpt', opt), ('uSSS', (k, 0, 0, 0)), ('uUV0', uv0), ('uUV1', uv1), ('uScr', scr)]
                   + ([('uSprite', ('parent.BTDR.par.Pointsize', 'parent.BTDR.par.Resolutionh', 0, 0))] if sprite else []))
        self._samplers(m, list(maps.items()), state)

    def UnitsPerMeter(self):
        """[BTDR:UNI.UNIT] (0.8.3) scene units per metre from the Scene Unit menu (same table as uniforms_chop.py)."""
        P = self.ownerComp.par
        m = {'meters': 1.0, 'centimeters': 0.01, 'millimeters': 0.001, 'inches': 0.0254, 'feet': 0.3048}
        try:
            u = m.get(P.Sceneunit.eval())
            if u is None:
                u = max(float(P.Unitsize.eval()), 1e-6)
        except Exception:
            u = 1.0
        return 1.0 / u

    # [BTDR:EXT.UVSET] (0.8.3) PBR MAT map -> (sampler, parameter prefix, sampling-mode parameter)
    UVMAPS = (('sBaseColor', 'basecolormap', 'texturesamplingmode'), ('sMetallic', 'metallicmap', 'metallicmapsamplingmode'),
              ('sRoughness', 'roughnessmap', 'roughnessmapsamplingmode'), ('sAO', 'ambientocclusionmap', 'ambientocclusionmapsamplingmode'),
              ('sNormal', 'normalmap', 'normalmapsamplingmode'), ('sEmit', 'emitmap', 'emitmapsamplingmode'),
              ('sAlpha', 'alphamap', 'alphamapsamplingmode'))

    def _uv_codes(self, src, S, warn):
        """[BTDR:EXT.UVSET] per-map texture coordinates of a PBR MAT: code = UV set (0 = uv0, 1 = the one extra set the
        material uses, uUV1.w) + 2 for Screen Space. Expressions, so changing the menus needs no refresh. The shader can
        carry one extra UV set per material; Triplanar is not supported (in TD 2025.33230 the PBR MAT's own Triplanar
        does nothing on SOPs and samples one texel on POPs, so there is nothing to match)."""
        state, codes, extra = {}, [], []
        for samp, pre, mode in self.UVMAPS:
            state[samp] = (S, pre)
            cp = getattr(src.par, pre + 'coord', None)
            mp = getattr(src.par, mode, None)
            c_set = "(0 if %s.par.%scoord.menuIndex == 0 else 1)" % (S, pre) if cp is not None else '0'
            c_mode = "(2 if %s.par.%s.eval() == 'screenspace' else 0)" % (S, mode) if mp is not None else '0'
            codes.append('%s + %s' % (c_set, c_mode))
            if cp is not None:
                extra.append('(%s.par.%scoord.menuIndex if %s.par.%s.eval() else 0)' % (S, pre, S, pre))
            if getattr(src.par, pre).eval() and mp is not None and mp.eval() == 'triplanar':
                warn.append('%s: Triplanar sampling (%s) is not supported, the map uses its UV coordinates.' % (src.path, pre))
        used = sorted(set(getattr(src.par, pre + 'coord').menuIndex for _, pre, _ in self.UVMAPS
                          if getattr(src.par, pre).eval() and hasattr(src.par, pre + 'coord')) - {0})
        if len(used) > 1:
            warn.append('%s: maps use UV sets %s; only one extra set besides uv0 is supported (uv%d is used for all of them).'
                        % (src.path, ', '.join('uv%d' % u for u in used), used[-1]))
        uv0 = tuple(codes[:4])
        uv1 = tuple(codes[4:7]) + (('max(%s)' % ', '.join(extra)) if extra else 0,)
        return state, uv0, uv1

    def _new_material(self, scene, name, src, warn, tr=None, sss=None, sprite=None):
        C = self.ownerComp
        m = scene.create(glslMAT, name)
        # [BTDR:EXT.SPRITE] (0.9.4) points: the sprite variants ('scale' = the geometry has PointScale)
        m.par.vdat = C.op({'points': 'gbuffer_sprite_vert', 'scale': 'gbuffer_spritescale_vert'}.get(sprite, 'gbuffer_vert'))
        m.par.pdat = C.op('gbuffer_sprite_frag' if sprite else 'gbuffer_frag')
        # [BTDR:GBUF.POPUV] (0.8.1) POP geometry keeps its texture coordinates in the point attribute `Tex`: declared
        # here so gbuffer.vert can read it with TDTexAttrib_Tex() (which is uv[0] on SOPs). TDTexCoord(0) is 0 on POPs,
        # so every map sampled one corner (found on a POP membrane in a commission, 2026-11-16).
        m.seq.attr.numBlocks = 2 if sprite == 'scale' else 1
        m.par.attr0name = 'Tex'
        m.par.attr0type = 'float3'
        if sprite == 'scale':
            m.par.attr1name = 'PointScale'; m.par.attr1type = 'float'
        for d in list(m.docked):             # TD adds template shader DATs to every new GLSL MAT
            d.destroy()
        # no per-frame uniform in the material (TAA jitter lives in the projection of `cam_jit`, [BTDR:EXT.JITCAM]),
        # so the mirror materials never re-cook
        self._bind_material(m, src, warn, tr, sss, sprite)
        return m

    @staticmethod
    def _sprite_kind(src):
        """[BTDR:EXT.SPRITE] None for surfaces; 'points' when every rendered child is point-only (a POP with only point
        primitives or no primitives, a SOP without primitives or with only particle primitives); 'scale' when such a
        POP also has a PointScale attribute."""
        kids = [c for c in src.children if getattr(c, 'render', False) and c.family in ('SOP', 'POP')]
        if not kids:
            return None
        scale = False
        for c in kids:
            try:
                if c.family == 'POP':
                    n = c.numPrims()
                    if n and c.numPrims(primType='pointPrims') != n:
                        return None
                    if c.numPoints() == 0:
                        return None
                    scale = scale or any(a.name == 'PointScale' for a in c.pointAttributes)
                else:
                    if c.numPoints == 0 or any(type(p).__name__ != 'Particle' for p in c.prims):
                        return None
            except Exception:
                return None
        return 'scale' if scale else 'points'

    def _new_forward_material(self, scene, name, src, warn, slot):
        """[BTDR:EXT.FWDMAT] M6b: forward-lit material of a blended mirror (forward.frag, premultiplied output).
        Per-frame data comes in through textures (uniform block `ub_tex`, positions, shadow, environment), so the
        material does not re-cook every frame ([BTDR:FWD.UB])."""
        C = self.ownerComp
        m = scene.create(glslMAT, name)
        m.par.vdat = C.op('gbuffer_vert')
        m.par.pdat = C.op('forward_frag')
        for d in list(m.docked):
            d.destroy()
        white = "parent.BTDR.op('white')"
        S = "op('%s')" % src.path if src is not None else None
        tex = lambda par: "%s.par.%s.eval() or %s" % (S, par, white)
        base, emit, chan = (0.5, 0.5, 0.5, 1), (0, 0, 0, 0), (1, 1, 1, SRGB)
        trans, trans2 = (1, 0, 0, 0), (0, 0, 0, 0)
        maps = dict(sBaseColor=white, sAlpha=white, sEmit=white)
        if src is not None and src.OPType == 'pbrMAT':
            base = tuple('%s.par.basecolor%s' % (S, c) for c in 'rgb') + (1,)
            emit = tuple('%s.par.emit%s' % (S, c) for c in 'rgb') + ('1 if %s.par.emitmap.eval() else 0' % S,)
            maps = dict(sBaseColor=tex('basecolormap'), sAlpha=tex('alphamap'), sEmit=tex('emitmap'))
            trans = ('%s.par.alphafront' % S, 0, 0, 0)
            trans2 = ('1 if %s.par.alphamap.eval() else 0' % S, 0, 0, 0)
        elif src is not None and src.OPType == 'constantMAT':
            emit = tuple('%s.par.color%s' % (S, c) for c in 'rgb') + (0,)
            base = (0, 0, 0, 1)
            maps['sBaseColor'] = tex('colormap')
            trans = ('%s.par.alpha' % S, 0, 0, 0) if hasattr(src.par, 'alpha') else trans
        elif src is not None:
            warn.append('%s (%s): blended objects read PBR MAT or Constant MAT; using grey.' % (src.path, src.OPType))
        if slot is None:
            blend = (1, 'parent.BTDR.par.Softdist', 0, 'parent.BTDR.par.Glassdim')
        else:
            P = 'parent.BTDR.par.Blend%d' % slot
            blend = ('1 if %slit else 0' % P,
                     '(%ssoft.eval() if %ssoft.eval() >= 0 else parent.BTDR.par.Softdist.eval())' % (P, P),
                     "1 if %smode == 'additive' else 0" % P, 'parent.BTDR.par.Glassdim')
        self._vecs(m, [('uBase', base), ('uEmit', emit), ('uChan', chan), ('uTrans', trans), ('uTrans2', trans2),
                       ('uBlend', blend)])
        P = "parent.BTDR.op('%s')"
        self._samplers(m, list(maps.items()) + [('sUB', P % 'ub_tex'), ('sOpaquePos', P % 'gbuf2'),
                       ('sFrontPos', P % 'tpos_src'), ('sShadow', P % 'shadow_src'), ('sEnvSharp', P % 'env_src'),
                       ('sEnvAtlas', P % 'env_atlas')])
        # ub_tex / positions must be read exactly (no filtering between texels); maps keep the default filtering
        for i in range(m.seq.sampler.numBlocks):
            nm = getattr(m.par, 'sampler%dname' % i).eval()
            if nm in ('sUB', 'sOpaquePos', 'sFrontPos'):
                f = getattr(m.par, 'sampler%dfilter' % i, None)
                if f is not None:
                    try: f.val = 'nearest'
                    except Exception: pass
        # [BTDR:EXT.FWDSTATE] premultiplied blending, no depth writes (Sorted); the Render TOP's Order Independent mode
        # depth-peels on its own
        m.par.blending = True
        m.par.srcblend = 'one'; m.par.destblend = 'omsa'
        m.par.postmultalpha = False
        m.par.depthwriting.expr = "parent.BTDR.par.Blendmethod == 'orderind'"
        try: m.par.cullface = 'neither'          # two-sided cards
        except Exception: pass
        return m

    # ------------------------------------------------------------------ transparency (M6a / M6b)
    def _slots(self, seq='Refr'):
        """[BTDR:EXT.SLOTS] the Refractive (Refr) or Blended (Blend) slots of the Transparency page:
        [(index, geometry pattern), ...]"""
        C = self.ownerComp
        try:
            n = getattr(C.seq, seq).numBlocks
        except Exception:
            return []
        return [(i, str(getattr(C.par, '%s%dgeo' % (seq, i)).eval() or '').strip()) for i in range(n)]

    def _slot_exprs(self, slot):
        if slot is None:
            return None
        P = 'parent.BTDR.par.Refr%d' % slot
        cust = "%sabsorbsrc == 'custom'" % P
        trans3 = tuple('(%sabsorbcolor%s if %s else -1)' % (P, c, cust) for c in 'rgb') + (P + 'scale',)
        return dict(ior=P + 'ior', absorb=P + 'absorb', thin='(1 + %sthinlift) if %sthin else 0' % (P, P), rough=P + 'rough',
                    trans3=trans3)

    def _classify(self, geos, warn):
        """[BTDR:EXT.TRANSCLASS] per Geometry COMP: kind (opaque / refr), slot, cast shadow, in ray tracing.
        Layer 1: the first Refractive slot whose pattern matches. Layer 2: inferred from the PBR MAT (alpha < 1 or an
        alpha map -> refractive). Slot objects outside the Geometry pattern are added to the scene."""
        C = self.ownerComp
        on = bool(C.par.Transparency.eval())
        blend_on = hasattr(C.par, 'Blendcount')          # M6b is only in builds with M6B = True ([BTDR:BUILD.M6B])
        slot_of = {}
        extra = []
        label = dict(Refr='Refractive', Blend='Blended')
        for seq in ('Refr', 'Blend'):
            for i, pat in self._slots(seq):
                if not pat:
                    continue
                hits = self._find(pat, ('geometryCOMP',))
                if not hits:
                    warn.append('%s slot %d: nothing matches "%s".' % (label[seq], i + 1, pat))
                for g in hits:
                    if g.path in slot_of:
                        s0, i0 = slot_of[g.path]
                        warn.append('%s is in %s slot %d and %s slot %d: the first is used.' % (g.path, label[s0], i0 + 1, label[seq], i + 1))
                        continue
                    slot_of[g.path] = (seq, i)
                    if g not in geos and g not in extra:
                        extra.append(g)
        # [BTDR:EXT.SSSCLASS] 0.8.0 Subsurface slots: profile = slot index (the first 8); refractive / blended wins
        sss_of = {}
        for i, pat in self._slots('Sss'):
            if not pat:
                continue
            if i >= MAX_SSS:
                warn.append('Subsurface slot %d: only the first %d subsurface slots are used.' % (i + 1, MAX_SSS))
                continue
            hits = self._find(pat, ('geometryCOMP',))
            if not hits:
                warn.append('Subsurface slot %d: nothing matches "%s".' % (i + 1, pat))
            for g in hits:
                if g.path in sss_of:
                    warn.append('%s is in Subsurface slots %d and %d: the first is used.' % (g.path, sss_of[g.path] + 1, i + 1))
                    continue
                sss_of[g.path] = i
                if g not in geos and g not in extra:
                    extra.append(g)
        geos = list(geos) + extra
        info = []
        for g in geos:
            d = dict(kind='opaque', slot=None, cast=True, inrt=True)
            if on and g.path in slot_of:
                seq, i = slot_of[g.path]
                if seq == 'Refr':
                    d.update(kind='refr', slot=i, cast=getattr(C.par, 'Refr%dshadow' % i).eval() == 'opaque',
                             inrt=bool(getattr(C.par, 'Refr%dinrt' % i).eval()))
                else:
                    d.update(kind='blend', slot=i, cast=False, inrt=False)
            elif on:
                m = g.par.material.eval()
                if m is not None and m.OPType == 'pbrMAT':
                    try:
                        if m.par.alphatest.eval():
                            pass                 # alpha test = opaque cut-out ([BTDR:GBUF.ALPHA])
                        elif blend_on and m.par.blending.eval() and m.par.alphamap.eval() is not None:
                            d.update(kind='blend', cast=False, inrt=False)    # sprite / smoke card ([BTDR:FWD.*])
                        elif m.par.alphafront.eval() < 0.999 or m.par.alphamap.eval() is not None:
                            d.update(kind='refr', cast=False, inrt=False)
                            if m.par.blending.eval() and m.par.alphamap.eval() is not None:
                                warn.append('%s looks like a blended (sprite / smoke) material: blended transparency is not '
                                            'in this build, drawn as refractive.' % g.path)
                    except Exception:
                        pass
            if g.path in sss_of:
                if d['kind'] == 'opaque':
                    d['sss'] = sss_of[g.path]
                else:
                    warn.append('%s is transparent and in Subsurface slot %d: drawn as transparent, no subsurface.'
                                % (g.path, sss_of[g.path] + 1))
            info.append(d)
        return geos, info

    def ApplyPreset(self, i):
        """Fill a Refractive slot from its Preset menu ([BTDR:EXT.REFRPRESET])."""
        C = self.ownerComp
        v = REFR_PRESETS.get(getattr(C.par, 'Refr%dpreset' % i).eval())
        if v is None:
            return
        ior, rough, thin, absorb = v
        getattr(C.par, 'Refr%dior' % i).val = ior
        getattr(C.par, 'Refr%drough' % i).val = rough
        getattr(C.par, 'Refr%dthin' % i).val = thin
        getattr(C.par, 'Refr%dabsorb' % i).val = absorb

    def ApplySssPreset(self, i):
        """Fill a Subsurface slot from its Preset menu ([BTDR:EXT.SSSPRESET])."""
        C = self.ownerComp
        v = SSS_PRESETS.get(getattr(C.par, 'Sss%dpreset' % i).eval())
        if v is None:
            return
        sc, rad, tc, thin, th = v
        for c, a, b in zip('rgb', sc, tc):
            getattr(C.par, 'Sss%dscatter%s' % (i, c)).val = a
            getattr(C.par, 'Sss%dtrans%s' % (i, c)).val = b
        getattr(C.par, 'Sss%dradius' % i).val = rad
        getattr(C.par, 'Sss%dthin' % i).val = thin
        getattr(C.par, 'Sss%dthickness' % i).val = th

    # ------------------------------------------------------------------ scene mirror
    def _mirror(self, geos, warn, info=None):
        # [BTDR:EXT.MIRROR] one hidden Geometry COMP per source Geometry COMP:
        #   Select SOP / Select POP for every child with its Render flag on,
        #   Parent Object = the source (inherits its world transform),
        #   material = internal G-Buffer GLSL MAT bound to the source material.
        scene = self.ownerComp.op('scene')
        for c in list(scene.children):
            if c.valid:                      # docked DATs disappear together with their owner
                c.destroy()
        mats = {}
        count = 0
        vel = []
        C = self.ownerComp
        info = info or [dict(kind='opaque', slot=None)] * len(geos)
        for i, src in enumerate(geos):
            # [BTDR:EXT.TRANSSPLIT] refractive objects become scene/t<i>: not drawn by `gbuffer` (scene/g*), drawn by
            # `tgbuffer` / `tback` (scene/t*)
            # blended objects become scene/b<i>, drawn by `tblend` with the forward material
            g = scene.create(geometryCOMP, dict(refr='t%d', blend='b%d').get(info[i]['kind'], 'g%d') % i)
            for c in list(g.children):
                c.destroy()
            g.nodeX, g.nodeY = 200, -i * 120
            n = 0
            for k, child in enumerate(src.children):
                if not getattr(child, 'render', False):
                    continue
                if child.family == 'SOP':
                    s = g.create(selectSOP, 's%d' % k)
                    s.par.sops = child.path
                elif child.family == 'POP':
                    s = g.create(selectPOP, 's%d' % k)
                    s.par.pop = child.path
                else:
                    continue
                s.render = True
                s.display = True
                n += 1
            if n == 0 and not any(c.OPType == 'geometryCOMP' for c in src.children):     # a pure parent is fine
                warn.append('%s has no SOP or POP with its Render flag on.' % src.path)
            g.par.parentxformsrc = 'specify'
            g.par.parentobject = src.path
            g.par.render.expr = "op('%s').par.render" % src.path
            msrc = src.par.material.eval()
            slot = info[i].get('slot')
            sss = info[i].get('sss')
            spr = info[i].get('sprite')
            key = (msrc.path if msrc is not None else '', info[i]['kind'], slot, sss, spr)
            if key not in mats:
                if info[i]['kind'] == 'blend':
                    mats[key] = self._new_forward_material(scene, 'm%d' % len(mats), msrc, warn, slot)
                else:
                    mats[key] = self._new_material(scene, 'm%d' % len(mats), msrc, warn, self._slot_exprs(slot), sss, spr)
                mats[key].nodeX, mats[key].nodeY = 0, -(len(mats) - 1) * 120
            g.par.material = mats[key]
            # [BTDR:EXT.INSTANCING] every parameter of the Instance pages follows the source by expression;
            # the G-Buffer and shadow shaders apply instancing through TDDeform().
            for p in src.pars():
                if p.page is not None and p.page.name.startswith('Instance'):
                    q = getattr(g.par, p.name, None)
                    if q is not None:
                        ref = "op('%s').par.%s" % (src.path, p.name)
                        q.expr = (ref + ".eval() or ''") if p.isOP else ref     # empty OP references stay empty
            if info[i]['kind'] == 'opaque':
                self._vel_mirror(scene, i, src, g, vel)
            count += 1
        C.store('vel_objs', vel)
        return count

    def _vel_mirror(self, scene, i, src, g, vel):
        """[BTDR:EXT.VELMIRROR] (0.9.2) scene/v<i>: the same SOPs / POPs as scene/g<i>, with its own velocity material
        (its previous world matrix is a uniform, set every frame by `uniforms` only while the object moves). Not
        rendered by `gbuffer` / `shadow` (scene/g*); `velocity` draws it only while it is in the moving list."""
        C = self.ownerComp
        v = scene.create(geometryCOMP, 'v%d' % i)
        for c in list(v.children):
            c.destroy()
        v.nodeX, v.nodeY = 400, -i * 120
        attr = None
        for c in g.children:
            t = v.create(type(c), c.name)
            if c.family == 'SOP':
                t.par.sops = c.par.sops.eval()
                o = t.par.sops.eval()
                o = op(o) if isinstance(o, str) else o
                if o is not None and any(a.name == 'v' for a in getattr(o, 'pointAttribs', [])):
                    attr = attr or 'v'
            else:
                t.par.pop = c.par.pop.eval()
                o = t.par.pop.eval()
                o = op(o) if isinstance(o, str) else o
                if o is not None and any(a.name == 'PartVel' for a in getattr(o, 'pointAttributes', [])):
                    attr = attr or 'PartVel'
            t.render = True; t.display = True
        v.par.parentxformsrc = 'specify'
        v.par.parentobject = src.path
        v.par.render.expr = "op('%s').par.render" % src.path
        for p in g.pars():
            if p.page is not None and p.page.name.startswith('Instance') and p.expr:
                q = getattr(v.par, p.name, None)
                if q is not None:
                    q.expr = p.expr
        m = scene.create(glslMAT, 'vm%d' % i)
        m.nodeX, m.nodeY = 600, -i * 120
        m.par.vdat = C.op({'PartVel': 'velocity_pv_vert', 'v': 'velocity_v_vert'}.get(attr, 'velocity_vert'))
        m.par.pdat = C.op('velocity_frag')
        if attr:                     # [BTDR:VEL.ATTRIB] declared only where the geometry has it
            m.seq.attr.numBlocks = 1
            m.par.attr0name = attr; m.par.attr0type = 'float3'
        for d in list(m.docked):
            d.destroy()
        M = src.worldTransform
        self._vecs(m, [('uPW%d' % c, [M[r, c] for r in range(4)]) for c in range(4)] + [('uVelOpt', [1.0 / max(project.cookRate, 1.0), 0, 0, 0])])
        v.par.material = m
        vel.append((v.path, src.path, m.path, bool(attr)))

    # ------------------------------------------------------------------ ray tracing (M4)
    def _rt_build(self, geos, warn, info=None):
        # [BTDR:EXT.RTPROXY] the proxy scene for hardware ray tracing, rebuilt with the mirror. Per source Geometry COMP:
        #   SOP: Select -> Convert (to polygons; grids are meshes) -> PolyReduce (Proxy Detail %) -> SOP to POP
        #   POP: Select (no reduction)
        #   -> Transform POP (matrix from the table rtscene/xf<i>, kept current by `uniforms`, [BTDR:UNI.RTXFORM])
        #   -> Attribute POP ObjId = i -> rtscene/merge -> tri (quads to triangles, for POP sources) -> out
        # Every chain caches: PolyReduce only re-cooks when its source changes, a moved object only re-cooks its
        # Transform POP. The acceleration structure is rebuilt whenever a tracing GLSL POP cooks, so its cost
        # follows the proxy triangle count, not the render meshes.
        # [BTDR:EXT.RTREFR] M6c: refractive objects go into a second scene rtscene/merge_t -> tri_t -> out_t (= the
        # opaque proxy + the glass), traced only by the ray-traced refraction pass; the reflection and probe passes keep
        # tracing rtscene/out, where glass lets light through. ObjId = index in the full object list, so rt_mat has a row
        # pair for every object (glass: base colour | absorption distance, 0 | IOR, negative = thin walled).
        C = self.ownerComp
        R = C.op('rtscene')
        info = info or [dict(kind='opaque', inrt=True)] * len(geos)
        rtrefr = str(C.par.Refrmethod.eval()) != 'screen' if hasattr(C.par, 'Refrmethod') else False
        keep = ('merge', 'tri', 'out', 'merge_t', 'tri_t', 'out_t', 'avg_sel', 'avg_res')
        for c in list(R.children):
            if c.valid and c.name not in keep:
                c.destroy()
        mg = R.op('merge')
        mgt = R.op('merge_t')
        if mgt is not None:
            for c in list(mgt.inputConnectors):
                c.disconnect()
            R.op('out').outputConnectors[0].connect(mgt)
        k = 0
        rows = []
        inst = []
        for i, src in enumerate(geos):
            t = R.create(tableDAT, 'xf%d' % i); t.nodeX, t.nodeY = 400, -i * 120 - 400
            M = src.worldTransform
            t.clear()
            for r in range(4):
                t.appendRow([M[r, c] for c in range(4)])
            kind = info[i]['kind']
            to_main = (kind == 'opaque' and not info[i].get('sprite')) or (kind == 'refr' and info[i].get('inrt'))   # [BTDR:EXT.SPRITE] no points
            to_glass = kind == 'refr' and not to_main and rtrefr and mgt is not None
            skip = not (to_main or to_glass)
            # [BTDR:EXT.RTINST] (0.9.3) instanced objects: the proxy of the geometry is copied onto a template POP made from
            # the instance transforms (Script CHOP rtscene/inst<i> -> CHOP to POP -> Copy POP), then the object transform
            tmpl = None
            try:
                instanced = bool(src.par.instancing.eval())
            except Exception:
                instanced = False
            if not skip and instanced:
                kind_ = self._rt_inst_kind(src)
                cap = int(C.par.Rtmaxinstances.eval()) if hasattr(C.par, 'Rtmaxinstances') else 0
                if kind_ != 'ok' or cap <= 0:
                    inst.append('%s (%s)' % (src.path, 'Max Instances in Proxy 0' if cap <= 0 else 'instance OP is a ' + kind_))
                    skip = True
                else:
                    tmpl = self._rt_inst_template(R, i, src, cap)
            for ch in ([] if skip else src.children):
                if not getattr(ch, 'render', False) or ch.family not in ('SOP', 'POP'):
                    continue
                # [BTDR:EXT.RTLINES] open curves (Line SOP ...) cannot go into the acceleration structure: it accepts
                # triangles only and one line made rt_refl / rt_probes fail for the whole scene (0.7.4)
                try:
                    if ch.family == 'SOP' and ch.numPrims > 0 and not getattr(ch.prims[0], 'closed', True):
                        continue
                except Exception:
                    pass
                y = -k * 120 - 400
                if ch.family == 'SOP':
                    a = R.create(selectSOP, 's%d' % k); a.par.sops = ch.path
                    cv = R.create(convertSOP, 'cv%d' % k); cv.par.totype = 'poly'
                    a.outputConnectors[0].connect(cv)
                    # [BTDR:EXT.RTMINPOLY] keep Proxy Detail % of the polygons, but never fewer than 800 triangles (or all of them):
                    # 0.4.0 reduced a 6-face box to one triangle and a sphere to one or two, so low-poly objects were
                    # missing from the ray-traced scene (found with M6c's traced glass)
                    pr = R.create(polyreduceSOP, 'pr%d' % k); pr.par.method = 'number'
                    # (Keep # counts triangles after Pre-Triangulate: a quad is two)
                    # instanced: the floor is 800 triangles for all copies together (at least 12 per copy)
                    floor = ("min(op('cv%d').numPrims * 2, max(12, 800 // max(op('%s').numSamples, 1)))" % (k, tmpl[0].name)) if tmpl else \
                            ("min(op('cv%d').numPrims * 2, 800)" % k)
                    pr.par.numpolys.expr = ("max(int(op('cv%d').numPrims * 2 * parent.BTDR.par.Rtproxydetail / 100), %s)" % (k, floor))
                    cv.outputConnectors[0].connect(pr)
                    sp = R.create(soptoPOP, 'sp%d' % k); sp.par.sop = pr
                    for n, o in enumerate((a, cv, pr, sp)): o.nodeX, o.nodeY = -800 + n * 150, y
                else:
                    sp = R.create(selectPOP, 'sp%d' % k); sp.par.pop = ch.path
                    sp.nodeX, sp.nodeY = -350, y
                x = R.create(transformPOP, 'x%d' % k); x.par.xformmatrixop = t; x.nodeX, x.nodeY = 0, y
                if tmpl:
                    cp = R.create(copyPOP, 'cp%d' % k); cp.nodeX, cp.nodeY = -150, y - 60
                    sp.outputConnectors[0].connect(cp.inputConnectors[0])
                    tmpl[1].outputConnectors[0].connect(cp.inputConnectors[1])
                    cp.par.dotemplatetranslate = True; cp.par.translateattr = 'P'
                    cp.par.dotemplaterotate = True; cp.par.rotateattr = 'InstR'
                    cp.par.dotemplatescale = True; cp.par.scaleattrib = 'InstS'
                    cp.outputConnectors[0].connect(x)
                else:
                    sp.outputConnectors[0].connect(x)
                at = R.create(attributePOP, 'id%d' % k); at.nodeX, at.nodeY = 200, y
                at.par.attr0name = 'custom'; at.par.attr0customname = 'ObjId'; at.par.attr0type = 'float'
                at.par.attr0numcomps = '1'; at.par.attr0value0 = i
                x.outputConnectors[0].connect(at)
                at.outputConnectors[0].connect(mg if to_main else mgt)
                k += 1
            rr = self._rt_material(src)
            if kind == 'refr':
                sl = info[i].get('slot')
                P = C.par
                ior = float(getattr(P, 'Refr%dior' % sl).eval()) if sl is not None else float(P.Defaultior.eval())
                ab = float(getattr(P, 'Refr%dabsorb' % sl).eval()) if sl is not None else float(P.Absorbdist.eval())
                thin = bool(getattr(P, 'Refr%dthin' % sl).eval()) if sl is not None else False
                # [BTDR:EXT.RTREFRMAT] (0.8.4) absorption colour (custom or the averaged base colour), refraction scale
                ac = (rr[0][0], rr[0][1], rr[0][2])
                scl = 1.0
                if sl is not None:
                    if getattr(P, 'Refr%dabsorbsrc' % sl).eval() == 'custom':
                        ac = tuple(float(getattr(P, 'Refr%dabsorbcolor%s' % (sl, c)).eval()) for c in 'rgb')
                    scl = float(getattr(P, 'Refr%dscale' % sl).eval())
                rr = [(ac[0], ac[1], ac[2], max(ab, 1e-3)), (scl, 0.0, 0.0, -ior if thin else ior)]
            rows += rr
        if inst:
            warn.append('Instanced geometry left out of the ray-tracing scene: %s' % ', '.join(inst))
        C.store('rt_geos', [g.path for g in geos])
        # [BTDR:EXT.RTMAT] two texels per object: albedo rgb | metallic, emissive rgb | 0 (linear)
        mt = C.op('rt_mat')
        mt.clear(); mt.appendRow(['x', 'y', 'z', 'w'])
        for r in rows or [(0, 0, 0, 0), (0, 0, 0, 0)]:
            mt.appendRow(['%.6g' % v for v in r])
        # [BTDR:EXT.RTGRID] probe grid over the bounds of the solid objects (+ margin), from just above the ground
        fit = self._bounds([g for g, d in zip(geos, info) if d['kind'] == 'opaque' or (d['kind'] == 'refr' and d.get('inrt'))] or geos)
        g = C.op('rt_probe_grid')
        if fit is not None:
            lo, hi = fit
            span = hi - lo
            K = self.UnitsPerMeter()                     # [BTDR:UNI.UNIT] margins below are in metres
            m = np.maximum(span * 0.15, 0.2 * K)
            lo2 = lo - m; hi2 = hi + m
            lo2[1] = lo[1] + 0.03 * K; hi2[1] = hi[1] + max(span[1] * 0.25, 0.2 * K)
            c = (lo2 + hi2) / 2.0; sz = hi2 - lo2
            g.par.tx, g.par.ty, g.par.tz = [float(v) for v in c]
            g.par.sizex, g.par.sizey, g.par.sizez = [float(max(v, 0.1 * K)) for v in sz]
            # [BTDR:EXT.RTGRIDDIMS] (0.7.3) probe counts follow the shape of the bounds, so the spacing is about the
            # same on all three axes (budget 16x8x16 = 2048 probes on High, x0.75 per axis on Low). A fixed 16x8x16
            # over a wide, shallow scene gave 0.1 m spacing in depth and 0.7 m across: the per-probe noise of
            # neighbouring depth layers showed as coloured stripes on flat surfaces.
            szc = np.maximum(sz, 0.1 * K)
            step = float((np.prod(szc) / 2048.0) ** (1.0 / 3.0))
            for par, v in zip((g.par.cols, g.par.rows, g.par.slices), szc):
                n = int(min(40, max(3, round(float(v) / step) + 1)))
                par.expr = "max(3, int(round(%d * (1.0 if parent.BTDR.par.Quality != 'low' else 0.75))))" % n
        return k

    def _rt_inst_kind(self, src):
        ns = {}
        exec(self.ownerComp.op('rt_inst_callbacks').text, ns)
        return ns['source_kind'](src)

    def _rt_inst_template(self, R, i, src, cap):
        """[BTDR:EXT.RTINST] Script CHOP inst<i> (instance transforms, rt_inst_chop.py) -> CHOP to POP tp<i>: one point per
        instance, P = translate, InstR = rotate (degrees), InstS = scale. Copy POP's default order (SRT, XYZ) matches
        the Geometry COMP's instancing."""
        C = self.ownerComp
        sc = R.create(scriptCHOP, 'inst%d' % i); sc.nodeX, sc.nodeY = -1100, -i * 120 - 400
        sc.par.callbacks = C.op('rt_inst_callbacks')
        sc.store('src', src.path); sc.store('cap', cap)
        tp = R.create(choptoPOP, 'tp%d' % i); tp.nodeX, tp.nodeY = -950, -i * 120 - 400
        tp.par.chop = sc
        tp.par.surftype = 'none'; tp.par.specifypos = False
        tp.par.chanscope = 'tx ty tz'; tp.par.attrscope = 'P'
        tp.seq.attr.numBlocks = 2
        tp.par.attr0chanscope = 'rx ry rz'; tp.par.attr0customname = 'InstR'; tp.par.attr0numcomps = '3'
        tp.par.attr1chanscope = 'sx sy sz'; tp.par.attr1customname = 'InstS'; tp.par.attr1numcomps = '3'
        sc.cook(force=True)
        return (sc, tp)

    @staticmethod
    def _solid_boxes(boxes):
        """[BTDR:EXT.SOLIDBOXES] (0.8.5) the bounds the shadow camera and the probe grid fit to: every object but a
        ground plane (flat in Y and not above the lowest point of the others, the rule of [BTDR:EXT.CASTERS]).
        Before 0.8.5 every flat object was dropped, walls and ceilings too (0.1 thick, 6 wide): in a room the shadow
        map covered only the furniture (sun came in through a ceiling outside it) and the probe grid stopped short of
        the walls (vertical stripes of extrapolated light on them). Found with the path-traced reference
        (tools/pt_reference.py)."""
        def ground(i):
            lo_, hi_ = boxes[i]
            others = [boxes[j] for j in range(len(boxes)) if j != i]
            if not others:
                return False
            w = max(hi_[0] - lo_[0], hi_[2] - lo_[2])
            low = min(o[0][1] for o in others)
            size = max(float(np.max([o[1] for o in others], axis=0).max() - np.min([o[0] for o in others], axis=0).min()), 1e-6)
            return (hi_[1] - lo_[1]) < 0.02 * w and hi_[1] <= low + 0.01 * size
        return [b for i, b in enumerate(boxes) if not ground(i)] or boxes

    def _bounds(self, geos):
        boxes = []
        for g in geos:
            try:
                b = g.computeBounds()
                lo = np.array([b.min.x, b.min.y, b.min.z]); hi = np.array([b.max.x, b.max.y, b.max.z])
                if np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)):
                    boxes.append((lo, hi))
            except Exception:
                pass
        if not boxes:
            return None
        solid = self._solid_boxes(boxes)   # [BTDR:EXT.SOLIDBOXES]
        return np.min([b[0] for b in solid], axis=0), np.max([b[1] for b in solid], axis=0)

    def _map_mean(self, top, srgb):
        # mean colour of a texture (16x16 mipmapped copy), linearised when the colour maps are sRGB
        if top is None:
            return np.ones(3)
        R = self.ownerComp.op('rtscene')
        R.op('avg_sel').par.top = top.path
        r = R.op('avg_res')
        r.cook(force=True)
        a = r.numpyArray()
        if a is None:
            return np.ones(3)
        c = np.clip(a[..., :3].astype(np.float64), 0.0, None)
        if srgb:
            c = c ** 2.2
        return c.reshape(-1, 3).mean(axis=0)

    def _rt_material(self, src):
        m = src.par.material.eval()
        srgb = bool(self.ownerComp.par.Srgbcolors.eval())
        lin = (lambda v: max(v, 0.0) ** 2.2) if srgb else (lambda v: max(v, 0.0))
        base, metal, emit = np.array([0.5, 0.5, 0.5]), 0.0, np.zeros(3)
        if srgb:
            base = base ** 2.2
        try:
            t = m.OPType if m is not None else None
            if t == 'pbrMAT':
                base = np.array([lin(m.par.basecolorr.eval()), lin(m.par.basecolorg.eval()), lin(m.par.basecolorb.eval())])
                if m.par.basecolormap.eval() is not None:
                    base = base * self._map_mean(m.par.basecolormap.eval(), srgb)
                metal = float(m.par.metallic.eval())
                emit = np.array([lin(m.par.emitr.eval()), lin(m.par.emitg.eval()), lin(m.par.emitb.eval())])
                if m.par.emitmap.eval() is not None:
                    emit = emit * self._map_mean(m.par.emitmap.eval(), srgb)
            elif t == 'phongMAT':
                base = np.array([lin(m.par.diffr.eval()), lin(m.par.diffg.eval()), lin(m.par.diffb.eval())])
                if m.par.colormap.eval() is not None:
                    base = base * self._map_mean(m.par.colormap.eval(), srgb)
            elif t == 'constantMAT':
                base = np.array([lin(m.par.colorr.eval()), lin(m.par.colorg.eval()), lin(m.par.colorb.eval())])
                if m.par.colormap.eval() is not None:
                    base = base * self._map_mean(m.par.colormap.eval(), srgb)
        except Exception:
            pass
        base = np.clip(base, 0.0, 1.0)
        return [(base[0], base[1], base[2], metal), (emit[0], emit[1], emit[2], 0.0)]

    # ------------------------------------------------------------------ shadow camera
    def _fit_shadow(self, geos):
        # [BTDR:EXT.SHADOWFIT] centre and range of the shadow camera from the geometry bounds.
        # A ground plane is ignored so a large floor does not waste resolution (walls and ceilings are kept, 0.8.5).
        boxes = []
        for g in geos:
            try:
                b = g.computeBounds()
                lo = np.array([b.min.x, b.min.y, b.min.z]); hi = np.array([b.max.x, b.max.y, b.max.z])
                if np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)):
                    boxes.append((lo, hi))
            except Exception:
                pass
        if not boxes:
            return None
        solid = self._solid_boxes(boxes)
        lo = np.min([b[0] for b in solid], axis=0); hi = np.max([b[1] for b in solid], axis=0)
        centre = (lo + hi) / 2.0
        return centre, float(np.linalg.norm(hi - lo)) * 1.6

    def _setup_jitcam(self, cam):
        # [BTDR:EXT.JITCAM] the G-Buffer is rendered through `cam_jit`: it inherits the user camera's world
        # transform (Parent Object) and copies its lens by expression; `uniforms` writes Window X / Y every frame
        # = the user's value + the TAA sub-pixel jitter. A projection offset is TD's own mechanism, so no shader
        # or material has to read the jitter (materials would otherwise re-cook every frame).
        cj = self.ownerComp.op('cam_jit')
        cj.par.parentxformsrc = 'specify'
        cj.par.parentobject = cam.path if cam is not None else ''
        for p in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
            getattr(cj.par, p).val = 0
        # [BTDR:CAM.ORTHO] (0.9.4) + Ortho Width / Ortho Origin (0.9.3 and earlier left cam_jit at the default width)
        for p in ('projection', 'viewanglemethod', 'fov', 'focal', 'aperture', 'near', 'far', 'winsize', 'winroll', 'winrollpivot',
                  'orthowidth', 'orthoorigin', 'winsizex', 'winsizey', 'winrollx', 'winrolly'):
            par = getattr(cj.par, p, None)
            if par is None:
                continue
            if cam is not None:
                # [BTDR:EXT.CAMGONE] survives the camera being deleted: until `scene_watch` notices (up to half a
                # second) the expression falls back to the default instead of raising (0.7.4 left red errors)
                par.expr = "op('%s').par.%s.eval() if op('%s') else %r" % (cam.path, p, cam.path, par.default)
            else:
                par.expr = ''
                par.val = par.default

    def _shadow_casters(self, geos, info=None):
        # [BTDR:EXT.CASTERS] a ground plane only receives shadows: leave it out of the shadow pass (one draw less).
        # Ground = flat in Y (height < 2% of its width) and not above the lowest point of every other object.
        boxes = []
        for g in geos:
            try:
                b = g.computeBounds()
                boxes.append((b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z))
            except Exception:
                boxes.append(None)
        casters = []
        for i, b in enumerate(boxes):
            others = [o for j, o in enumerate(boxes) if j != i and o is not None]
            ground = False
            if b is not None and others and all(math.isfinite(x) for x in b):
                w = max(b[3] - b[0], b[5] - b[2])
                low = min(o[1] for o in others)
                size = max(max(o[3] for o in others) - min(o[0] for o in others), max(o[4] for o in others) - low, 1e-6)
                ground = (b[4] - b[1]) < 0.02 * w and b[4] <= low + 0.01 * size
            if info is not None and info[i]['kind'] == 'blend':
                continue                     # blended objects never cast ([BTDR:FWD.*])
            if info is not None and info[i].get('sprite'):
                continue                     # [BTDR:EXT.SPRITE] the shadow material draws points one pixel wide
            refr = info is not None and info[i]['kind'] == 'refr'
            if refr and not info[i]['cast']:
                continue                     # [BTDR:EXT.TRANSSHADOW] glass casts no shadow unless its slot says Opaque
            if not ground:
                casters.append(('scene/t%d' if refr else 'scene/g%d') % i)
        sh = self.ownerComp.op('shadow')
        nopaque = sum(1 for d in (info or [dict(kind='opaque')] * len(geos)) if d['kind'] == 'opaque' and not d.get('sprite'))
        allg = len(casters) == nopaque == len(geos)
        sh.par.geometry = 'scene/g*' if allg else (' '.join(casters) or 'none')
        self.ownerComp.store('shadow_casters', casters)

    def SunLocal(self):
        # [BTDR:EXT.SUNCAM] position of the shadow camera in the main light's local space, so that its
        # frustum stays centred on Shadow Center while the light rotates. Used by expressions on `suncam`.
        # Plain Python (no numpy) and memoised on its inputs: the three tx/ty/tz expressions share one result.
        C = self.ownerComp
        P = C.par
        centre = (P.Shadowcenterx.eval(), P.Shadowcentery.eval(), P.Shadowcenterz.eval())
        rng = P.Shadowrange.eval()
        lp = C.fetch('light_path', '')
        light = op(lp) if lp else None
        v = tuple(light.worldTransform.vals) if light is not None else None
        key = (centre, rng, v)
        memo = self.__dict__.get('_sun_memo')
        if memo is not None and memo[0] == key:
            return memo[1]
        dist = max(10.0, rng * 1.5)
        if v is None:
            L = (0.55, 0.75, 0.50); n = math.sqrt(sum(c * c for c in L))
            res = tuple(centre[i] + L[i] / n * dist for i in range(3))
        else:
            # vals is column-major: column k = v[4k:4k+3], translation = v[12:15]
            d = (centre[0] - v[12], centre[1] - v[13], centre[2] - v[14])
            loc = []
            for k in range(3):
                col = v[4 * k:4 * k + 3]
                n = max(math.sqrt(col[0] * col[0] + col[1] * col[1] + col[2] * col[2]), 1e-9)
                loc.append((col[0] * d[0] + col[1] * d[1] + col[2] * d[2]) / n)
            res = (loc[0], loc[1], loc[2] + dist)
        self._sun_memo = (key, res)
        return res

    def _setup_suncam(self, light):
        C = self.ownerComp
        sun = C.op('suncam')
        # translate is a constant, re-written by the `uniforms` CHOP only when SunLocal() changes
        # ([BTDR:UNI.SHADOWCACHE]); a Python expression here re-evaluated every frame (~0.1 ms)
        for i, c in enumerate('xyz'):
            p = getattr(sun.par, 't' + c); p.expr = ''; p.mode = ParMode.CONSTANT
        sun.par.tx, sun.par.ty, sun.par.tz = self.SunLocal()
        sun.par.orthowidth.expr = 'parent.BTDR.par.Shadowrange'
        sun.par.far.expr = 'max(10.0, parent.BTDR.par.Shadowrange * 1.5) * 2 + parent.BTDR.par.Shadowrange'
        if light is not None:
            sun.par.parentxformsrc = 'specify'
            sun.par.parentobject = light.path
            sun.par.rx = sun.par.ry = sun.par.rz = 0
        else:
            sun.par.parentxformsrc = 'specify'
            sun.par.parentobject = ''
            L = np.array([0.55, 0.75, 0.50]); L /= np.linalg.norm(L)
            sun.par.ry = math.degrees(math.atan2(L[0], L[2]))
            sun.par.rx = -math.degrees(math.asin(L[1]))
            sun.par.rz = 0

    # ------------------------------------------------------------------ public
    def Refresh(self):
        """[BTDR:EXT.REFRESH] Re-resolve Camera / Geometry / Lights and rebuild the scene mirror."""
        C = self.ownerComp
        warn = []
        self.SyncShell()
        self.sig = self._scene_sig()        # first, so a Refresh that fails is not retried twice a second
        cam = C.par.Camera.eval()
        if cam is None or cam.OPType != 'cameraCOMP':
            warn.append('Camera: no Camera COMP found for "%s".' % C.par.Camera.val)
            cam = None
        elif cam.par.projection.eval() not in ('perspective', 'ortho'):
            # [BTDR:CAM.ORTHO] (0.9.4) perspective and orthographic; the blend and custom matrices are not followed
            warn.append('%s: Projection %s is not supported (Perspective or Orthographic).' % (cam.path, cam.par.projection.eval()))
        elif cam.par.projection.eval() == 'ortho' and C.par.Dof.eval():
            warn.append('Depth of field is off with an orthographic camera.')
        geos = self._geos()
        if not geos:
            warn.append('Geometry: nothing matches "%s" (or every match has its Render flag off).' % C.par.Geometry.eval())
        lights = self._find(C.par.Lights.eval(), ('lightCOMP',))
        # [BTDR:EXT.AMBIENT] Ambient Light COMPs matched by Lights add their colour x dimmer to the diffuse ambient
        C.store('ambient_paths', [a.path for a in self._find(C.par.Lights.eval(), ('ambientlightCOMP',))])
        # [BTDR:EXT.LIGHTS] (0.9.0) the first distant light is the main light (sun: shadows, fog shafts, subsurface
        # transmission, probe GI); every other Light COMP (point, cone, further distant lights) is a local light, up
        # to 8, lit without shadows ([BTDR:LIGHT.LOCAL]). With only point / cone lights there is no sun. Before 0.9.0
        # a point or cone light was treated as a distant one (direction only).
        distant = [l for l in lights if l.par.lighttype.eval() == 'distant']
        light = distant[0] if distant else None
        local = [l for l in lights if l is not light]
        C.store('sun_off', light is None and bool(lights))
        if not lights:
            warn.append('Lights: no Light COMP matches "%s"; using the built-in key light.' % C.par.Lights.eval())
        if len(local) > 8:
            warn.append('%d local lights matched: only the first 8 are used (%s ...).' % (len(local), ', '.join(l.name for l in local[8:11])))
        C.store('local_lights', [l.path for l in local[:8]])
        # [BTDR:EXT.LLSHADOW] (0.9.1) spot lights whose Shadow Type is not Off get a shadow map, up to Max Shadowed
        # Spot Lights (default 2, at most 4); point lights have none yet (a cube map is six renders).
        nmax = int(C.par.Localshadows.eval()) if hasattr(C.par, 'Localshadows') else 0
        shadowed = [l for l in local[:8] if l.par.lighttype.eval() == 'cone' and l.par.shadowtype.eval() != 'off'][:min(nmax, 4)]
        skipped = [l for l in local[:8] if l.par.lighttype.eval() == 'cone' and l.par.shadowtype.eval() != 'off'][len(shadowed):]
        if skipped:
            warn.append('Spot shadows: only %d allowed (Max Shadowed Spot Lights): %s without.' % (len(shadowed), ', '.join(l.name for l in skipped)))
        if any(l.par.lighttype.eval() == 'point' and l.par.shadowtype.eval() != 'off' for l in local[:8]):
            warn.append('Point lights do not cast shadows yet (spot lights do).')
        K = self.UnitsPerMeter()
        C.store('llshadow', {l.path: k for k, l in enumerate(shadowed)})
        for k in range(4):
            cam_, sw_ = C.op('llcam%d' % k), C.op('llsw%d' % k)
            if cam_ is None or sw_ is None:
                continue
            if k < len(shadowed):
                l = shadowed[k]
                cam_.par.parentxformsrc = 'specify'
                cam_.par.parentobject = l.path
                cam_.par.fov = min(max(l.par.coneangle.eval() + 2 * l.par.conedelta.eval() + 4.0, 5.0), 170.0)
                cam_.par.near = 0.05 * K
                cam_.par.far = (l.par.attenuationend.eval() if l.par.attenuated.eval() else 50.0 * K) * 1.05
                sw_.par.index = 1
            else:
                cam_.par.parentobject = ''
                sw_.par.index = 0
        if hasattr(C.par, 'Lightcount'):
            kinds = [l.par.lighttype.eval() for l in local[:8]]
            C.par.Lightcount = '%s, %d point, %d cone, %d distant' % (
                '1 main' if light is not None else ('built-in main' if not lights else 'no main'),
                kinds.count('point'), kinds.count('cone'), kinds.count('distant'))

        C.store('cam_path', cam.path if cam is not None else '')
        C.store('light_path', light.path if light is not None else '')
        C.par.Mainlight = light.path if light is not None else ('(none: only local lights)' if lights else '(built-in key light)')
        # [BTDR:EXT.ENVLIGHT] the first Environment Light COMP matched by Lights that has a map (used by Source = Auto)
        envl = [e for e in self._find(C.par.Lights.eval(), ('environmentlightCOMP',)) if e.par.envlightmap.eval() is not None]
        C.par.Envlight = envl[0].path if envl else ''
        self._setup_jitcam(cam)
        C.op('gbuffer').par.camera = 'cam_jit'
        geos, info = self._classify(geos, warn)
        # [BTDR:EXT.SPRITE] (0.9.4) point-only geometry is drawn as spheres (sprite material); no shadow, not ray traced
        for g, d in zip(geos, info):
            d['sprite'] = self._sprite_kind(g)
        n = self._mirror(geos, warn, info)
        ntr = sum(1 for d in info if d['kind'] == 'refr')
        C.par.Transcount = ntr
        if hasattr(C.par, 'Ssscount'):
            C.par.Ssscount = sum(1 for d in info if d.get('sss') is not None)
        if hasattr(C.par, 'Blendcount'):
            C.par.Blendcount = sum(1 for d in info if d['kind'] == 'blend')
        nrt = self._rt_build(geos, warn, info)
        # re-tested by `uniforms` ([BTDR:UNI.RTCHECK]). [BTDR:EXT.RTEMPTY] an empty proxy scene (no geometry yet) keeps
        # ray tracing off: its POPs have nothing to trace and fail to compile (0.7.4, found in a new project)
        C.par.Rtavailable = nrt > 0
        if C.par.Shadowfit.eval():
            fit = self._fit_shadow(geos)
            if fit is not None:
                C.par.Shadowcenterx, C.par.Shadowcentery, C.par.Shadowcenterz = [float(v) for v in fit[0]]
                C.par.Shadowrange = max(fit[1], 0.5)
        self._setup_suncam(light)
        self._shadow_casters(geos, info)
        # [BTDR:EXT.SHADOWWATCH] what the shadow cache watches for changes: the light, every source Geometry COMP,
        # its rendered SOP / POP children and instance source
        watch_x, watch_c = [light.path] if light is not None else [], []
        for g in geos:
            watch_x.append(g.path)
            for ch in g.children:
                if getattr(ch, 'render', False) and ch.family in ('SOP', 'POP'):
                    watch_c.append(ch.path)
            try:
                if g.par.instancing.eval() and g.par.instanceop.eval() is not None:
                    watch_c.append(g.par.instanceop.eval().path)
            except Exception:
                pass
        C.store('shadow_watch', (watch_x, watch_c))
        self.ApplyQuality()
        # [BTDR:EXT.STATUS] warnings cannot be raised from here (TD only allows addWarning during a cook):
        # they are stored, shown in the read-only Status parameter and the `status` DAT, and raised by the
        # `uniforms` Script CHOP on its next cook so the warning marker appears on the component.
        C.store('rt_check', 0)              # [BTDR:UNI.RTCHECK] re-check ray-tracing support after a rebuild
        C.store('status', {'camera': cam.path if cam is not None else None, 'geometry': [g.path for g in geos],
                           'light': light.path if light is not None else None, 'mirrored': n, 'warnings': warn})
        # [BTDR:EXT.TIPS] hints that are not problems (no warning marker): things in the user's scene that cost time
        # for nothing. A Light COMP with a native shadow re-renders its own shadow map every frame (IMPLEMENTATION_2
        # §11 #18: ~0.4 ms CPU, ~1.4 ms GPU in the demo scene) although BTDR draws its own shadows.
        tips, short = [], ''
        try:
            if light is not None and light.par.shadowtype.eval() != 'off':
                tips.append('%s draws a native shadow map every frame that BTDR does not use: set its Shadow Type to '
                            'Off to save ~1 ms (BTDR shadows are not affected)' % light.name)
                short = ' - tip: set %s Shadow Type to Off (saves ~1 ms)' % light.name
        except Exception:
            pass
        st = C.fetch('status'); st['tips'] = tips; C.store('status', st)
        C.par.Status = (('OK: %d geometry' % n) + short) if not warn else \
                       ('%d warning%s: %s' % (len(warn), '' if len(warn) == 1 else 's', warn[0]))
        C.op('status').text = '\n'.join(warn + ['tip: ' + t for t in tips]) if (warn or tips) else 'OK'
        self._cover_after_refresh(cam)
        return warn

    def ApplyQuality(self):
        C = self.ownerComp
        q = QUALITY.get(C.par.Quality.eval())
        if q:
            for k, v in q.items():
                getattr(C.par, k).val = v
