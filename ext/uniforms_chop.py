# [BTDR:FILE.UNIFORMS] Script CHOP callbacks for `uniforms`.
# [BTDR:UNI.BLOCK] Fills the shared uniform array uB[40] once per frame: 4 channels (xyzw) x 40 samples.
# Slot layout must match shaders/common.glsl.
import math
import numpy as np

NSLOT = 40
_STATE = {}      # per-CHOP runtime state (previous camera, frame counter); not saved with the file

def _halton(i, b):
    f, r = 1.0, 0.0
    while i > 0:
        f /= b
        r += f * (i % b)
        i //= b
    return r

def _tan_half_fov(cam, aspect):
    # [BTDR:UNI.FOV] horizontal half-angle tangent for the three Camera COMP view angle methods
    cp = _pars(cam)
    m = cp['viewanglemethod'].eval()
    if m == 'vertfov':
        return math.tan(math.radians(cp['fov'].eval() / 2.0)) * aspect
    if m == 'focallength':
        return cp['aperture'].eval() / max(2.0 * cp['focal'].eval(), 1e-6)
    return math.tan(math.radians(cp['fov'].eval() / 2.0))

def _norm(x, y, z):
    n = math.sqrt(x * x + y * y + z * z)
    return n if n > 1e-9 else 1e-9

def _camera(cam, aspect):
    # [BTDR:UNI.CAMBASIS] plain Python on Matrix.vals (column-major), ~10x cheaper than numpy for 4x4
    v = cam.worldTransform.vals
    nx, ny, nz = _norm(*v[0:3]), _norm(*v[4:7]), _norm(*v[8:11])
    return ((v[12], v[13], v[14], 1.0),                                  # pos
            (v[0] / nx, v[1] / nx, v[2] / nx, 0.0),                      # right
            (v[4] / ny, v[5] / ny, v[6] / ny, 0.0),                      # up
            (-v[8] / nz, -v[9] / nz, -v[10] / nz, _tan_half_fov(cam, aspect)))   # forward, tan(fov/2)

_ZERO = (0.0, 0.0, 0.0, 0.0)

# [BTDR:UNI.PARCACHE] Looking a parameter up by attribute (C.par.Bloom) costs ~0.65 us in TD, the eval itself ~0.12 us;
# ~120 reads per frame. Cache the Par objects per component / operator (keyed by its id: a rebuilt or reloaded
# component gets a new id) and only eval them every frame. Expressions and exports keep working: eval() still runs.
_PARS = {}
def _pars(o):
    k = o.id
    d = _PARS.get(k)
    if d is None or not d['_valid'].valid:
        d = {p.name: p for p in o.pars()}
        d['_valid'] = o
        _PARS[k] = d
    return d

def onCook(scriptOp):
    C = scriptOp.parent()
    Q = _pars(C)
    a = [_ZERO] * NSLOT
    W, H = max(int(Q['Resolutionw'].eval()), 1), max(int(Q['Resolutionh'].eval()), 1)
    aspect = W / float(H)
    frame = absTime.frame          # cooking every frame comes from the Frame parameter ([BTDR:BUILD.UNICOOK])

    # [BTDR:UNI.CAMERA] current + previous camera
    cp = C.fetch('cam_path', '')
    cam = op(cp) if cp else None
    st = _STATE.get(scriptOp.path)
    if cam is not None:
        cur = _camera(cam, aspect)
        reset = st is None or st.get('cam') != cam.path
        # [BTDR:UNI.RECOOK] a second cook in the same frame (something read this CHOP or a TOP downstream from
        # a frame-start callback) must not advance the history: keep the previous frame's camera, frame
        # index and jitter, or prev == cur and TAA / motion blur see no motion.
        again = not reset and st.get('frame') == frame
        prev = cur if reset else (st['prev'] if again else st['cur'])
        n = 0 if reset else (st['n'] if again else st['n'] + 1)
        a[0:4] = cur
        a[4:8] = prev
        cpar = _pars(cam)
        a[19] = (cpar['near'].eval(), cpar['far'].eval(), aspect, 0.0)
        # [BTDR:UNI.JITTER] Halton(2,3), 8 samples, within +-half a pixel, in NDC. Applied as a projection
        # offset of `cam_jit` (Window X/Y: NDC shift = -2 x window offset, measured), used by the next G-Buffer
        # render (the G-Buffer cooks before this CHOP in a frame). TAA does not need the value itself: it
        # reprojects with the un-jittered cameras ([BTDR:TAA.REPROJECT]).
        taa = Q['Antialias'].eval() == 'taa'
        k = n % 8 + 1
        jit = ((_halton(k, 2) - 0.5) * 2.0 / W, (_halton(k, 3) - 0.5) * 2.0 / H) if taa else (0.0, 0.0)
        pj = (0.0, 0.0) if reset else (st.get('pjit', (0.0, 0.0)) if again else st.get('jit', (0.0, 0.0)))
        a[8] = (jit[0], jit[1], pj[0], pj[1])
        cj = C.op('cam_jit')
        if cj is not None:
            jp = _pars(cj)
            wx, wy = cpar['winx'].eval() - jit[0] * 0.5, cpar['winy'].eval() - jit[1] * 0.5
            if jp['winx'].eval() != wx or jp['winy'].eval() != wy:
                jp['winx'].val, jp['winy'].val = wx, wy
        a[20] = (Q['Taaweight'].eval(), 1.0 if taa else 0.0, 1.25, 0.0)
        # [BTDR:UNI.FRAMEWRAP] (0.7.3) the shaders hash `frame x constant` for their per-frame noise (fog jitter,
        # dither, SSR / SSGI / shadow rotations). In 32-bit float those products lose their fraction after half an
        # hour or more without a camera cut (n ~ 1e5-1e6) and the noise turns into fixed patterns; wrap the index.
        a[9] = (float(n % 4096), 1.0 / max(project.cookRate, 1.0), 1.0 if n < 4 else 0.0, absTime.seconds)
        _STATE[scriptOp.path] = {'cam': cam.path, 'cur': cur, 'prev': prev, 'n': n, 'jit': jit, 'pjit': pj,
                                 'frame': frame}
    else:
        a[19] = (0.1, 100.0, aspect, 0.0)

    # [BTDR:UNI.SUN] main light + shadow camera basis (read back from the internal shadow camera)
    lp = C.fetch('light_path', '')
    light = op(lp) if lp else None
    sun = C.op('suncam')
    shd = C.op('shadow')
    cache = C.op('shadow_cache')
    # [BTDR:UNI.SHADOWCACHE] Within a frame `lighting` cooks its inputs (shadow_cache -> shadow) before this CHOP
    # (measured), so the shadow map of this frame was rendered with the suncam state as it is *now*, before we
    # move it below. Keep the basis of the camera that rendered the current map (`mapv`), so the lookup always
    # matches the map, also on frames where the map is not re-rendered.
    ss = _STATE.setdefault(scriptOp.path + '#shadow', {})
    tc = shd.totalCooks
    if tc != ss.get('tc') or 'mapv' not in ss:
        ss['mapv'] = sun.worldTransform.vals
        ss['mapow'] = sun.par.orthowidth.eval(); ss['mapfar'] = sun.par.far.eval()
    ss['tc'] = tc
    # keep the shadow camera centred for the next render (constant pars, written only on change)
    loc = C.SunLocal()
    sp = _pars(sun)
    if (sp['tx'].eval(), sp['ty'].eval(), sp['tz'].eval()) != loc:
        sp['tx'].val, sp['ty'].val, sp['tz'].val = loc
    if cache is not None:
        shp = _pars(shd)
        wx, wc = C.fetch('shadow_watch', ([], []))
        sig = [loc, Q['Shadows'].eval(), Q['Shadowres'].eval(), Q['Shadowrange'].eval(), Q['Heightfieldao'].eval()]
        for path in wx:
            o = op(path)
            sig.append(o.worldTransform.vals if o is not None else None)
        for path in wc:
            o = op(path)
            sig.append(o.totalCooks if o is not None else None)
        old = ss.get('sig')
        changed = sig != old
        if changed:                      # debugging aid: which entry changed (0 loc, 1-3 pars, then watch_x, watch_c)
            ss['why'] = (absTime.frame, next((i for i in range(len(sig)) if old is None or i >= len(old) or sig[i] != old[i]), -1))
        ss['sig'] = sig
        full = int(Q['Shadowres'].eval())
        direct = False                   # lighting reads `shadow` directly instead of the cache
        if Q['Shadowupdate'].eval() == 'always':
            active, target, direct = False, full, True
            ss['settle'] = 0
        else:
            moving = changed or ss.get('changed_prev', True)
            ss['changed_prev'] = changed
            if moving:
                # [BTDR:UNI.SHADOWMOTION] while the light / objects move: optional half resolution and every-N-frames
                n = ss.get('mn', 0); ss['mn'] = n + 1
                target = full // 2 if Q['Shadowmovinghalf'].eval() else full
                every = max(1, int(Q['Shadowmovinginterval'].eval()))
                if every == 1:
                    active, direct = False, True     # every frame anyway: skip the cache copy
                else:
                    active = n % every == 0
                ss['settle'] = 2
            else:
                # settled: render once more at full resolution, then stop
                ss['mn'] = 0
                target = full
                k = ss.get('settle', 2)
                active = k > 0 or int(shp['resolutionw'].eval()) != target
                ss['settle'] = max(0, k - 1)
        if int(shp['resolutionw'].eval()) != target:
            shp['resolutionw'].val = shp['resolutionh'].val = target
        cpa = _pars(cache)['active']
        if cpa.eval() != active:
            cpa.val = active
        # [BTDR:UNI.HFCACHE] the height-field AO map (same casters, same change signature) is re-rendered whenever
        # the shadow map is (cache active, or `shadow` read directly while moving), otherwise it keeps its last image
        hc = C.op('hf_cache')
        if hc is not None and _pars(hc)['active'].eval() != (active or direct):
            _pars(hc)['active'].val = active or direct
        # [BTDR:UNI.RTXFORM] keep the proxy transforms current (tables rtscene/xf<i>, written only when they change)
        if changed:
            R = C.op('rtscene')
            for i, path in enumerate(C.fetch('rt_geos', [])):
                o = op(path); t = R.op('xf%d' % i) if R is not None else None
                if o is None or t is None:
                    continue
                M = o.worldTransform
                rows = [['%.9g' % M[r, c] for c in range(4)] for r in range(4)]
                if [[c.val for c in t.row(r)] for r in range(4)] != rows:
                    t.clear()
                    for r in rows:
                        t.appendRow(r)
        sw = C.op('shadow_src')
        if sw is not None and int(_pars(sw)['index'].eval()) != (0 if direct else 1):
            _pars(sw)['index'].val = 0 if direct else 1
    v = ss['mapv']
    nz = _norm(*v[8:11])
    if light is not None:
        lc = _pars(light)
        color = (lc['cr'].eval(), lc['cg'].eval(), lc['cb'].eval())
        inten = lc['dimmer'].eval() * math.pi            # native PBR MAT: dimmer 1 == irradiance PI
    else:
        color, inten = (1.0, 0.94, 0.84), 5.0          # built-in key light when Lights matches nothing
    a[10] = (v[8] / nz, v[9] / nz, v[10] / nz, inten * Q['Lightmult'].eval())
    a[11] = (color[0], color[1], color[2], Q['Shadowsoftness'].eval())
    a[12] = (v[12], v[13], v[14], 1.0 if Q['Shadows'].eval() else 0.0)
    a[13] = (v[0], v[1], v[2], ss['mapow'])
    a[14] = (v[4], v[5], v[6], ss['mapfar'])

    # [BTDR:UNI.PARAMS] parameter pages -> shader constants
    a[15] = (Q['Envintensity'].eval(), math.radians(Q['Envrotate'].eval()),
             1.0 if Q['Background'].eval() == 'env' else 0.0, Q['Bgblur'].eval())
    a[16] = (Q['Bgcolorr'].eval(), Q['Bgcolorg'].eval(), Q['Bgcolorb'].eval(), Q['Bgintensity'].eval())
    a[17] = (2.0 ** Q['Exposure'].eval(), Q['Vignette'].eval(), Q['Grain'].eval(),
             1.0 if Q['Tonemap'].eval() == 'aces' else 0.0)
    a[18] = (float(Q['Debugview'].menuIndex), 1.0 if Q['Srgbcolors'].eval() else 0.0, Q['Fadestart'].eval(), Q['Fadeend'].eval())
    # [BTDR:UNI.POST] M2 lens / camera effects
    high = Q['Quality'].eval() != 'low'
    a[21] = (Q['Bloom'].eval(), Q['Bloomthreshold'].eval(), Q['Bloomknee'].eval(), Q['Bloomradius'].eval())
    ae_on = bool(Q['Autoexposure'].eval())
    ps = _STATE.setdefault(scriptOp.path + '#post', {})
    ae_reset = ae_on and not ps.get('ae_on', False)          # snap to the target when switched on
    ps['ae_on'] = ae_on
    a[22] = (1.0 if ae_on else 0.0, Q['Aeminev'].eval(), Q['Aemaxev'].eval(), Q['Aekey'].eval())
    a[23] = (Q['Aespeedup'].eval(), Q['Aespeeddown'].eval(), 1.0 / max(project.cookRate, 1.0), 1.0 if ae_reset else 0.0)
    flen = Q['Focallength'].eval()
    if flen <= 0.0 and cam is not None:                       # from the camera's horizontal view angle
        flen = Q['Sensorwidth'].eval() / (2.0 * max(_tan_half_fov(cam, aspect), 1e-4))
    a[24] = (max(flen, 1.0), Q['Fstop'].eval(), Q['Focusdistance'].eval(), Q['Dofmaxblur'].eval())
    a[25] = (Q['Sensorwidth'].eval(), 1.0 if Q['Dof'].eval() else 0.0, 1.25 if high else 2.0, Q['Fogshadowblur'].eval())
    a[26] = (Q['Shutter'].eval(), Q['Mbmaxblur'].eval(), 12.0 if high else 6.0, 1.0 if Q['Motionblur'].eval() else 0.0)
    # [BTDR:UNI.SS] M3 screen-space AO / GI / reflections (0 strength = off; the passes are bypassed by Switch TOPs)
    a[27] = (Q['Aointensity'].eval() if Q['Ambientocclusion'].eval() else 0.0,
             Q['Ssgiintensity'].eval() if Q['Ssgi'].eval() else 0.0,
             Q['Ssrintensity'].eval() if Q['Ssr'].eval() else 0.0, 0.0)
    a[28] = (Q['Giradius'].eval(), 8.0 if high else 6.0, 2.0 if high else 1.0, Q['Fogjitter'].eval())
    a[29] = (Q['Ssrmaxdistance'].eval(), 32.0 if high else 20.0, Q['Ssrmaxroughness'].eval(), Q['Ssrthickness'].eval())
    fz = a[9][2] if cam is not None else 1.0
    a[30] = (0.1, 1.0, fz, Q['Fogcurweight'].eval())
    # [BTDR:UNI.FOG] volumetric fog
    a[31] = (Q['Fogdensity'].eval(), Q['Fogheightfalloff'].eval(), Q['Fogbaseheight'].eval(), Q['Foganisotropy'].eval())
    a[32] = (0.1, max(Q['Fogdistance'].eval(), 0.2), Q['Fogambient'].eval(), Q['Fognoise'].eval())
    a[33] = (Q['Fogcolorr'].eval(), Q['Fogcolorg'].eval(), Q['Fogcolorb'].eval(), 1.0 if Q['Fog'].eval() else 0.0)
    # [BTDR:UNI.HFAO] height-field AO: top-down map centre x / z, width, camera height (= topcam); on, intensity,
    # radius, sample count (directions)
    rng = Q['Shadowrange'].eval()
    a[34] = (Q['Shadowcenterx'].eval(), Q['Shadowcenterz'].eval(), rng, Q['Shadowcentery'].eval() + rng)
    a[35] = (1.0 if Q['Heightfieldao'].eval() else 0.0, Q['Hfaointensity'].eval(), Q['Hfaoradius'].eval(), 8.0 if high else 4.0)
    # [BTDR:UNI.RT] M4 hardware ray tracing
    rs = _STATE.setdefault(scriptOp.path + '#rt', {})
    rton = bool(Q['Raytracing'].eval()) and bool(Q['Rtavailable'].eval())
    gi_on = rton and bool(Q['Rtgi'].eval())
    rf_on = rton and bool(Q['Rtreflections'].eval())
    g = C.op('rt_probe_grid')
    gp = _pars(g)
    gd = (max(int(gp['cols'].eval()), 2), max(int(gp['rows'].eval()), 2), max(int(gp['slices'].eval()), 2))
    gc = (gp['tx'].eval(), gp['ty'].eval(), gp['tz'].eval()); gs = (gp['sizex'].eval(), gp['sizey'].eval(), gp['sizez'].eval())
    a[36] = (1.0 if gi_on else 0.0, 1.0 if rf_on else 0.0, Q['Rtreflmaxrough'].eval(), Q['Rtgiintensity'].eval())
    a[37] = (gc[0] - gs[0] / 2, gc[1] - gs[1] / 2, gc[2] - gs[2] / 2, 64.0 if high else 32.0)
    a[38] = (gs[0] / (gd[0] - 1), gs[1] / (gd[1] - 1), gs[2] / (gd[2] - 1), 16.0)
    div = 4 if high else 6                                  # must match rt_refl_grid ([BTDR:BUILD.RTREFL])
    # w: M6c refraction method (0 screen space, 1 hybrid, 2 ray traced), 0 when ray tracing is off ([BTDR:REFR.RT])
    rm = {'hybrid': 1.0, 'raytraced': 2.0}.get(str(Q['Refrmethod'].eval()), 0.0) if (rton and 'Refrmethod' in Q) else 0.0
    a[39] = (float(max(W // div, 1)), float(max(H // div, 1)), Q['Rtreflintensity'].eval(), rm)
    # [BTDR:UNI.RTSTATIC] the probe pass reads its own copy of the slots it needs (sun, shadows on, environment, RT),
    # written only when they change: rt_probes then cooks only on real changes, not every frame
    if gi_on:
        # [BTDR:UNI.RTSTATICKEY] the key is the 7 slots as computed (same inputs give bit-identical floats); 0.4.0
        # rounded all 160 values every frame (~0.07 ms)
        key = (a[10], a[11], a[12][3], a[15], a[36][0], a[37], a[38])
        if rs.get('static') != key:
            rs['static'] = key
            keep = {10, 11, 12, 15, 36, 37, 38}
            st = [a[i] if i in keep else _ZERO for i in range(NSLOT)]
            st[12] = (0.0, 0.0, 0.0, a[12][3])
            st[36] = (a[36][0], 0.0, 0.0, 0.0)             # reflection settings do not affect the probes
            t = C.op('rt_static')
            t.clear(); t.appendRow(['x', 'y', 'z', 'w'])
            for row in st:
                t.appendRow(['%.7g' % v for v in row])
    # [BTDR:UNI.RTCHECK] hardware ray queries need an RTX-class GPU (Vulkan ray query). Shortly after each Refresh,
    # look at the tracing POPs' errors: if they failed to compile, switch ray tracing off and say so.
    chk = C.fetch('rt_check', 0)
    if rton and chk < 30:
        C.store('rt_check', chk + 1)
        if chk == 29:
            bad = []
            for nm in ('rt_refl', 'rt_probes'):
                o = C.op(nm)
                if o is not None:
                    o.cook(force=True)          # a compile error from while the node was being built can be stale
                e = o.errors() if o is not None else ''
                if e:
                    bad.append('%s: %s' % (nm, e.splitlines()[0][:160]))
            o = C.op('rt_refr')                 # M6c: only cooks for Hybrid / Ray Traced; clear its stale errors too
            if o is not None and 'Refrmethod' in Q and Q['Refrmethod'].eval() != 'screen':
                o.cook(force=True)
            out = C.op('rtscene/out')
            ntri = out.numPrims() if out is not None else 0
            C.par.Rtproxyinfo = '%d triangles' % ntri
            if bad:
                C.par.Rtavailable = False
                st_ = C.fetch('status', None) or {}
                st_.setdefault('warnings', []).append('Hardware ray tracing unavailable, switched off (%s)' % bad[0])
                C.store('status', st_)
    scriptOp.clear()
    scriptOp.copyNumpyArray(np.array(list(zip(*a)), dtype=np.float32))   # 4 x 40, C-contiguous (see §11 #11)
    # [BTDR:UNI.WARN] surface the warnings collected by the last Refresh (see [BTDR:EXT.STATUS])
    w = (C.fetch('status', None) or {}).get('warnings')
    if w:
        scriptOp.addWarning(' | '.join(w))
    return
