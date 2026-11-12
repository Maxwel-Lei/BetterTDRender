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
        return (cam.path if (cam is not None and cam.OPType == 'cameraCOMP') else '',
                tuple(g.path for g in self._find(C.par.Geometry.eval(), ('geometryCOMP',))),
                tuple(l.path for l in self._find(C.par.Lights.eval(), ('lightCOMP',))))

    def WatchScene(self):
        # [BTDR:EXT.WATCH] called by `scene_watch` every COVER_POLL_FRAMES frames: a camera, Geometry COMP or light
        # added, deleted or renamed in the network refreshes the scene by itself (before 0.7.4 that needed Refresh
        # Scene: a renderer dropped in before the geometry existed stayed empty, and the empty ray-tracing scene
        # showed compile errors). Costs a few ops() lookups twice a second.
        if self._scene_sig() != getattr(self, 'sig', None):
            self.Refresh()

    def ShowInfo(self, once=False):
        # [BTDR:EXT.INFO] the start-up dialog: once per TouchDesigner session for all instances (once=True),
        # or every time from the Info page's button
        import sys
        if once:
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

    # ------------------------------------------------------------------ helpers
    def _find(self, pattern, optypes):
        # [BTDR:EXT.RESOLVE] patterns are resolved like the native Render TOP: relative to the network
        # that contains renderBTDR, space separated, wildcards allowed, absolute paths allowed.
        base = self.ownerComp.parent()
        found = []
        for tok in str(pattern).split():
            try:
                hits = base.ops(tok)
            except Exception:
                hits = []
            for o in hits:
                if o.OPType in optypes and o not in found and o is not self.ownerComp:
                    found.append(o)
        return found

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

    def _samplers(self, o, items):
        o.seq.sampler.numBlocks = len(items)
        for i, (name, expr) in enumerate(items):
            getattr(o.par, 'sampler%dname' % i).val = name
            getattr(o.par, 'sampler%dtop' % i).expr = expr
            # [BTDR:EXT.ANISO] 4x anisotropic filtering: keeps textures sharp at grazing angles, near-free on GPU
            a = getattr(o.par, 'sampler%danisotropy' % i, None)
            if a is not None: a.val = '4x'

    # ------------------------------------------------------------------ materials
    def _bind_material(self, m, src, warn, tr=None):
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
        elif t == 'phongMAT':
            base = tuple('%s.par.diff%s' % (S, c) for c in 'rgb') + (1,)
            emit = tuple('%s.par.emit%s' % (S, c) for c in 'rgb') + (0,)
            maps['sBaseColor'] = tex('colormap')
            warn.append('%s is a Phong MAT: only its diffuse colour and colour map are used (roughness 0.5).' % src.path)
        elif t == 'constantMAT':
            base = tuple('%s.par.color%s' % (S, c) for c in 'rgb') + (1,)
            maps['sBaseColor'] = tex('colormap')
            warn.append('%s is a Constant MAT: only its colour is used (roughness 0.5).' % src.path)
        elif src is not None:
            warn.append('%s (%s) is not supported: rendered with the default grey material. Use a PBR MAT.' % (src.path, src.OPType))
        self._vecs(m, [('uBase', base), ('uPBR', pbr), ('uEmit', emit), ('uChan', chan), ('uTrans', trans), ('uTrans2', trans2)])
        self._samplers(m, list(maps.items()))

    def _new_material(self, scene, name, src, warn, tr=None):
        C = self.ownerComp
        m = scene.create(glslMAT, name)
        m.par.vdat = C.op('gbuffer_vert')
        m.par.pdat = C.op('gbuffer_frag')
        for d in list(m.docked):             # TD adds template shader DATs to every new GLSL MAT
            d.destroy()
        # no per-frame uniform in the material (TAA jitter lives in the projection of `cam_jit`, [BTDR:EXT.JITCAM]),
        # so the mirror materials never re-cook
        self._bind_material(m, src, warn, tr)
        return m

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
        return dict(ior=P + 'ior', absorb=P + 'absorb', thin='1 if %sthin else 0' % P, rough=P + 'rough')

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
            if n == 0:
                warn.append('%s has no SOP or POP with its Render flag on.' % src.path)
            g.par.parentxformsrc = 'specify'
            g.par.parentobject = src.path
            g.par.render.expr = "op('%s').par.render" % src.path
            msrc = src.par.material.eval()
            slot = info[i].get('slot')
            key = (msrc.path if msrc is not None else '', info[i]['kind'], slot)
            if key not in mats:
                if info[i]['kind'] == 'blend':
                    mats[key] = self._new_forward_material(scene, 'm%d' % len(mats), msrc, warn, slot)
                else:
                    mats[key] = self._new_material(scene, 'm%d' % len(mats), msrc, warn, self._slot_exprs(slot))
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
            count += 1
        return count

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
            to_main = kind == 'opaque' or (kind == 'refr' and info[i].get('inrt'))
            to_glass = kind == 'refr' and not to_main and rtrefr and mgt is not None
            skip = not (to_main or to_glass)
            try:
                if not skip and src.par.instancing.eval():
                    inst.append(src.path); skip = True
            except Exception:
                pass
            for ch in ([] if skip else src.children):
                if not getattr(ch, 'render', False) or ch.family not in ('SOP', 'POP'):
                    continue
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
                    pr.par.numpolys.expr = ("max(int(op('cv%d').numPrims * 2 * parent.BTDR.par.Rtproxydetail / 100), "
                                            "min(op('cv%d').numPrims * 2, 800))" % (k, k))
                    cv.outputConnectors[0].connect(pr)
                    sp = R.create(soptoPOP, 'sp%d' % k); sp.par.sop = pr
                    for n, o in enumerate((a, cv, pr, sp)): o.nodeX, o.nodeY = -800 + n * 150, y
                else:
                    sp = R.create(selectPOP, 'sp%d' % k); sp.par.pop = ch.path
                    sp.nodeX, sp.nodeY = -350, y
                x = R.create(transformPOP, 'x%d' % k); x.par.xformmatrixop = t; x.nodeX, x.nodeY = 0, y
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
                rr = [(rr[0][0], rr[0][1], rr[0][2], max(ab, 1e-3)), (0.0, 0.0, 0.0, -ior if thin else ior)]
            rows += rr
        if inst:
            warn.append('Instanced geometry is not in the ray-tracing scene yet: %s' % ', '.join(inst))
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
            m = np.maximum(span * 0.15, 0.2)
            lo2 = lo - m; hi2 = hi + m
            lo2[1] = lo[1] + 0.03; hi2[1] = hi[1] + max(span[1] * 0.25, 0.2)
            c = (lo2 + hi2) / 2.0; sz = hi2 - lo2
            g.par.tx, g.par.ty, g.par.tz = [float(v) for v in c]
            g.par.sizex, g.par.sizey, g.par.sizez = [float(max(v, 0.1)) for v in sz]
            # [BTDR:EXT.RTGRIDDIMS] (0.7.3) probe counts follow the shape of the bounds, so the spacing is about the
            # same on all three axes (budget 16x8x16 = 2048 probes on High, x0.75 per axis on Low). A fixed 16x8x16
            # over a wide, shallow scene gave 0.1 m spacing in depth and 0.7 m across: the per-probe noise of
            # neighbouring depth layers showed as coloured stripes on flat surfaces.
            szc = np.maximum(sz, 0.1)
            step = float((np.prod(szc) / 2048.0) ** (1.0 / 3.0))
            for par, v in zip((g.par.cols, g.par.rows, g.par.slices), szc):
                n = int(min(40, max(3, round(float(v) / step) + 1)))
                par.expr = "max(3, int(round(%d * (1.0 if parent.BTDR.par.Quality != 'low' else 0.75))))" % n
        return k

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
        solid = [b for b in boxes if (b[1] - b[0]).min() > 0.02 * (b[1] - b[0]).max()] or boxes
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
        # Flat objects (floors, backdrops) are ignored so a large ground plane does not waste resolution.
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
        solid = [b for b in boxes if (b[1] - b[0]).min() > 0.02 * (b[1] - b[0]).max()] or boxes
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
        for p in ('projection', 'viewanglemethod', 'fov', 'focal', 'aperture', 'near', 'far', 'winsize', 'winroll', 'winrollpivot'):
            par = getattr(cj.par, p, None)
            if par is None:
                continue
            if cam is not None:
                par.expr = "op('%s').par.%s" % (cam.path, p)
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
            refr = info is not None and info[i]['kind'] == 'refr'
            if refr and not info[i]['cast']:
                continue                     # [BTDR:EXT.TRANSSHADOW] glass casts no shadow unless its slot says Opaque
            if not ground:
                casters.append(('scene/t%d' if refr else 'scene/g%d') % i)
        sh = self.ownerComp.op('shadow')
        nopaque = sum(1 for d in (info or [dict(kind='opaque')] * len(geos)) if d['kind'] == 'opaque')
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
        self.sig = self._scene_sig()        # first, so a Refresh that fails is not retried twice a second
        cam = C.par.Camera.eval()
        if cam is None or cam.OPType != 'cameraCOMP':
            warn.append('Camera: no Camera COMP found for "%s".' % C.par.Camera.val)
            cam = None
        elif cam.par.projection.eval() != 'perspective':
            warn.append('%s: only perspective cameras are supported.' % cam.path)
        geos = self._find(C.par.Geometry.eval(), ('geometryCOMP',))
        if not geos:
            warn.append('Geometry: nothing matches "%s".' % C.par.Geometry.eval())
        lights = self._find(C.par.Lights.eval(), ('lightCOMP',))
        distant = [l for l in lights if l.par.lighttype.eval() == 'distant']
        light = (distant or lights or [None])[0]
        if light is None:
            warn.append('Lights: no Light COMP matches "%s"; using the built-in key light.' % C.par.Lights.eval())
        else:
            if not distant:
                warn.append('%s is not a distant light: it is treated as one (direction only).' % light.path)
            if len(lights) > 1:
                warn.append('Only one light is supported for now: using %s.' % light.path)

        C.store('cam_path', cam.path if cam is not None else '')
        C.store('light_path', light.path if light is not None else '')
        C.par.Mainlight = light.path if light is not None else '(built-in key light)'
        self._setup_jitcam(cam)
        C.op('gbuffer').par.camera = 'cam_jit'
        geos, info = self._classify(geos, warn)
        n = self._mirror(geos, warn, info)
        ntr = sum(1 for d in info if d['kind'] == 'refr')
        C.par.Transcount = ntr
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
