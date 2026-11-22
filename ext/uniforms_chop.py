# [BTDR:FILE.UNIFORMS] Script CHOP callbacks for `uniforms`.
# [BTDR:UNI.BLOCK] Fills the shared uniform array uB[68] once per frame: 4 channels (xyzw) x 68 samples (40 until 0.7.4,
# 44 until 0.7.6).
# Slot layout must match shaders/common.glsl.
import math
import numpy as np

NSLOT = 124                 # 0.9.0: + 8 local lights x 5 slots from 68; 0.9.1: + 4 spot shadows x 4 from 108
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

def _is_ortho(cam):
    return _pars(cam)['projection'].eval() == 'ortho'

def _camera(cam, aspect):
    # [BTDR:UNI.CAMBASIS] plain Python on Matrix.vals (column-major), ~10x cheaper than numpy for 4x4
    # [BTDR:CAM.ORTHO] (0.9.4) an orthographic camera puts half its Ortho Width in forward.w instead of tan(fov / 2)
    v = cam.worldTransform.vals
    w = _pars(cam)['orthowidth'].eval() * 0.5 if _is_ortho(cam) else _tan_half_fov(cam, aspect)
    nx, ny, nz = _norm(*v[0:3]), _norm(*v[4:7]), _norm(*v[8:11])
    return ((v[12], v[13], v[14], 1.0),                                  # pos
            (v[0] / nx, v[1] / nx, v[2] / nx, 0.0),                      # right
            (v[4] / ny, v[5] / ny, v[6] / ny, 0.0),                      # up
            (-v[8] / nz, -v[9] / nz, -v[10] / nz, w))     # forward, tan(fov/2) or half the ortho width

_ZERO = (0.0, 0.0, 0.0, 0.0)
UNIT_M = {'meters': 1.0, 'centimeters': 0.01, 'millimeters': 0.001, 'inches': 0.0254, 'feet': 0.3048, 'custom': None}

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

def _local_lights(C, Q, a):
    """[BTDR:UNI.LOCALLIGHTS] (0.9.0) the local lights (stored by Refresh in 'local_lights') into slots 68.. every
    frame, so moving a light or changing its colour needs no Refresh. Returns how many were written."""
    if 'Locallights' in Q and not Q['Locallights'].eval():
        return 0
    paths = C.fetch('local_lights', [])
    mult = Q['Lightmult'].eval() * (Q['Localintensity'].eval() if 'Localintensity' in Q else 1.0)
    physical = 'Localfalloff' in Q and Q['Localfalloff'].eval() == 'physical'
    K = a[42][0]
    n = 0
    for path in paths[:8]:
        l = op(path)
        if l is None or not l.valid:
            continue
        p = _pars(l)
        t = p['lighttype'].eval()
        typ = {'point': 1.0, 'cone': 2.0, 'distant': 3.0}.get(t, 1.0)
        M = l.worldTransform
        z = _norm(M[0, 2], M[1, 2], M[2, 2])
        zx, zy, zz = M[0, 2] / z, M[1, 2] / z, M[2, 2] / z
        inten = p['dimmer'].eval() * math.pi * mult
        col = (p['cr'].eval() * inten, p['cg'].eval() * inten, p['cb'].eval() * inten)
        if typ == 3.0:
            d = (zx, zy, zz)                         # direction TO a distant light (its +Z), like the sun
        else:
            d = (-zx, -zy, -zz)                      # a light points down its -Z
        half = math.radians(max(p['coneangle'].eval(), 0.1)) * 0.5
        delta = math.radians(max(p['conedelta'].eval(), 0.0))
        cos_in, cos_out = math.cos(half), math.cos(min(half + delta, math.pi * 0.5))
        if physical:
            fall = 2.0
        else:
            fall = 1.0 if p['attenuated'].eval() else 0.0
        base = 68 + 5 * n
        a[base] = (M[0, 3], M[1, 3], M[2, 3], typ)
        a[base + 1] = (col[0], col[1], col[2], p['attenuationend'].eval())
        a[base + 2] = (d[0], d[1], d[2], cos_out)
        a[base + 3] = (p['attenuationstart'].eval(), p['attenuationexp'].eval(), cos_in, fall)
        k = C.fetch('llshadow', {}).get(path)
        a[base + 4] = (p['coneroll'].eval(), float(k + 1) if k is not None else 0.0, 0.0, 0.0)
        if k is not None:
            # [BTDR:UNI.LLSHADOW] (0.9.1) the shadow camera's world-to-camera rows and its lens
            cam = C.op('llcam%d' % k)
            if cam is not None:
                Mi = cam.worldTransform
                Mi.invert()
                for r in range(3):
                    a[108 + 4 * k + r] = (Mi[r, 0], Mi[r, 1], Mi[r, 2], Mi[r, 3])
                cp = _pars(cam)
                a[108 + 4 * k + 3] = (math.tan(math.radians(cp['fov'].eval()) * 0.5), cp['near'].eval(), 0.02 * K, 1.0)
        n += 1
    return n

def _velocity(C, Q, key, frame):
    """[BTDR:UNI.VELOCITY] (0.9.2) object motion vectors. Every frame: compare each opaque object's world matrix with
    the last frame's; the moving ones (plus objects with a velocity attribute, [BTDR:VEL.ATTRIB]) go into the
    `velocity` geometry list, their material gets last frame's matrix. `velocity` reads this CHOP in a parameter
    expression, so it renders after this cook (this frame's list and matrices). Returns 1 while anything moves."""
    st = _STATE.setdefault(key + '#vel', {})
    again = st.get('frame') == frame
    objs = C.fetch('vel_objs', [])
    on = Q['Objectmotion'].eval() if 'Objectmotion' in Q else False
    if again:
        return st.get('on', 0.0)
    prevs = st.get('w', {})
    cur = {}
    moving = []
    for vpath, spath, mpath, attr in objs:
        s = op(spath)
        if s is None:
            continue
        M = s.worldTransform
        vals = M.vals
        cur[spath] = (vals, M)
        old = prevs.get(spath)
        if not on or old is None:
            continue
        if attr or old[0] != vals:
            moving.append(vpath)
            m = op(mpath)
            if m is not None:
                P = old[1]
                mp = _pars(m)
                for c in range(4):
                    for r, ch in enumerate('xyzw'):
                        q = mp['vec%dvalue%s' % (c, ch)]
                        if q.eval() != P[r, c]:
                            q.val = P[r, c]
    st['w'] = cur
    st['frame'] = frame
    vel, sw = C.op('velocity'), C.op('vel_src')
    geo = ' '.join(p.split('/')[-2] + '/' + p.split('/')[-1] for p in moving)
    if vel is not None and _pars(vel)['geometry'].eval() != geo:
        _pars(vel)['geometry'].val = geo
    if sw is not None:
        idx = 1 if moving else 0
        if int(_pars(sw)['index'].eval()) != idx:
            _pars(sw)['index'].val = idx
    if 'Movingcount' in Q:
        txt = '%d of %d' % (len(moving), len(objs)) if on else 'off'
        if Q['Movingcount'].eval() != txt:
            Q['Movingcount'].val = txt
    st['on'] = 1.0 if moving else 0.0
    return st['on']


def _focus_distance(C, Q, cam):
    """[BTDR:UNI.FOCUSTRACK] (0.9.5) Focus Distance, or with Focus Method = Tracking the Focus Object's distance along
    the camera's view axis (+ Focus Offset), every frame, so a moving object stays sharp. Scene units. Falls back to
    Focus Distance when there is no object; the tracked value is shown in Tracked Distance."""
    d = Q['Focusdistance'].eval()
    if 'Focusmethod' not in Q or Q['Focusmethod'].eval() != 'tracking' or cam is None:
        return d
    o = Q['Focusobject'].eval()
    if o is None or not hasattr(o, 'worldTransform'):
        return d
    c, w = cam.worldTransform.vals, o.worldTransform.vals            # column-major: translation 12..14, z axis 8..10
    nz = _norm(*c[8:11])
    t = ((w[12] - c[12]) * -c[8] + (w[13] - c[13]) * -c[9] + (w[14] - c[14]) * -c[10]) / nz + Q['Focusoffset'].eval()
    t = max(t, 0.05)
    p = Q.get('Focustracked')
    if p is not None and abs(p.eval() - t) > 1e-4:
        p.val = round(t, 4)
    return t


def onCook(scriptOp):
    C = scriptOp.parent()
    Q = _pars(C)
    a = [_ZERO] * NSLOT
    W, H = max(int(Q['Resolutionw'].eval()), 1), max(int(Q['Resolutionh'].eval()), 1)
    aspect = W / float(H)
    frame = absTime.frame          # cooking every frame comes from the Frame parameter ([BTDR:BUILD.UNICOOK])
    # [BTDR:UNI.UNIT] (0.8.3) scene unit: K = scene units per metre. Distance parameters designed in metres are
    # multiplied by K here; shaders use uUnit / UM() for their own metre constants. Meters (K = 1) = 0.8.2.
    um = UNIT_M.get(Q['Sceneunit'].eval()) if 'Sceneunit' in Q else 1.0
    if um is None:
        um = max(Q['Unitsize'].eval(), 1e-6)
    K = 1.0 / um
    a[42] = (K, um, 0.0, 0.0)
    # [BTDR:UNI.MISC] (0.8.4) x energy compensation ([BTDR:LIGHT.ENERGY]); (0.9.0) y local light count
    nll = _local_lights(C, Q, a)
    a[43] = (1.0 if ('Energycomp' not in Q or Q['Energycomp'].eval()) else 0.0, float(nll),
             Q['Fogmultiple'].eval() if 'Fogmultiple' in Q else 0.0,           # z (0.9.1) fog multiple scattering
             _velocity(C, Q, scriptOp.path, frame))                            # w (0.9.2) object motion vectors present

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
        a[19] = (cpar['near'].eval(), cpar['far'].eval(), aspect, 1.0 if _is_ortho(cam) else 0.0)   # w [BTDR:CAM.ORTHO]
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
        a[20] = (Q['Taaweight'].eval(), 1.0 if taa else 0.0, 1.25,
                 1.0 if ('Taastatic' not in Q or Q['Taastatic'].eval()) else 0.0)   # w [BTDR:TAA.STATIC] (0.9.6)
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
    if light is None and C.fetch('sun_off', False):
        inten = 0.0                                    # (0.9.0) only point / spot lights matched: no sun
    a[10] = (v[8] / nz, v[9] / nz, v[10] / nz, inten * Q['Lightmult'].eval())
    a[11] = (color[0], color[1], color[2], Q['Shadowsoftness'].eval())
    a[12] = (v[12], v[13], v[14], 1.0 if Q['Shadows'].eval() else 0.0)
    a[13] = (v[0], v[1], v[2], ss['mapow'])
    a[14] = (v[4], v[5], v[6], ss['mapfar'])

    # [BTDR:UNI.PARAMS] parameter pages -> shader constants
    # [BTDR:UNI.ENVAUTO] Source = Auto with an Environment Light COMP: its Dimmer and Rotate Y apply on top
    ei, er = Q['Envintensity'].eval(), Q['Envrotate'].eval()
    if Q['Envsource'].eval() == 'auto':
        el = op(Q['Envlight'].eval() or '/__none')
        if el is not None and el.par.envlightmap.eval() is not None:
            ei *= el.par.dimmer.eval()
            er += el.par.envlightmaprotatey.eval()
    a[15] = (ei, math.radians(er),
             {'env': 1.0, 'transparent': -1.0}.get(Q['Background'].eval(), 0.0), Q['Bgblur'].eval())
    a[16] = (Q['Bgcolorr'].eval(), Q['Bgcolorg'].eval(), Q['Bgcolorb'].eval(), Q['Bgintensity'].eval())
    if Q['Background'].eval() == 'transparent':
        a[16] = (0.0, 0.0, 0.0, 0.0)                     # [BTDR:GRADE.ALPHA] black behind the alpha
    # [BTDR:UNI.AMBIENT] Ambient Light COMPs (native PBR: ambient colour x dimmer added to the diffuse term)
    ar = ag = ab = 0.0
    for pth in C.fetch('ambient_paths', []):
        al = op(pth)
        if al is not None:
            q = _pars(al)
            d = q['dimmer'].eval()
            ar += q['cr'].eval() * d; ag += q['cg'].eval() * d; ab += q['cb'].eval() * d
    a[40] = (ar, ag, ab, 0.0)
    # [BTDR:UNI.SSS] 0.8.0 subsurface: globals + one profile per Subsurface slot (first 8), read every frame so slot
    # edits apply at once (only the slots that exist are read)
    if 'Subsurface' in Q:
        sq = Q['Sssquality'].eval()
        hi_s = sq == 'high' or (sq == 'auto' and Q['Quality'].eval() != 'low')
        sc = Q['Sssscale'].eval()
        a[41] = (1.0 if Q['Subsurface'].eval() else 0.0, sc, 7.0 if hi_s else 4.0, 1.0 if Q['Ssstransmission'].eval() else 0.0)
        try:
            nb = min(C.seq.Sss.numBlocks, 8)
        except Exception:
            nb = 0
        for k in range(nb):
            P = 'Sss%d' % k
            if (P + 'geo') not in Q:
                _PARS.pop(C.id, None); Q = _pars(C)       # blocks added since the cache was built
                if (P + 'geo') not in Q:
                    break
            thin = bool(Q[P + 'thin'].eval())
            r = Q[P + 'radius'].eval() * sc * K
            ts = Q[P + 'transstrength'].eval()
            a[44 + 3 * k] = (r * Q[P + 'scatterr'].eval(), r * Q[P + 'scatterg'].eval(), r * Q[P + 'scatterb'].eval(),
                             0.0 if thin else Q[P + 'strength'].eval())
            a[45 + 3 * k] = (ts * Q[P + 'transr'].eval(), ts * Q[P + 'transg'].eval(), ts * Q[P + 'transb'].eval(), 1.0 if thin else 0.0)
            a[46 + 3 * k] = (Q[P + 'detail'].eval(), Q[P + 'thickness'].eval() * K, 0.0, 0.0)
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
    a[24] = (max(flen, 1.0), Q['Fstop'].eval(), _focus_distance(C, Q, cam) * um, Q['Dofmaxblur'].eval())   # metres (dof.frag)
    # [BTDR:CAM.ORTHO] no depth of field with an orthographic camera
    a[25] = (Q['Sensorwidth'].eval(), 1.0 if Q['Dof'].eval() and a[19][3] < 0.5 else 0.0, 1.25 if high else 2.0, Q['Fogshadowblur'].eval())
    a[26] = (Q['Shutter'].eval(), Q['Mbmaxblur'].eval(), 12.0 if high else 6.0, 1.0 if Q['Motionblur'].eval() else 0.0)
    # [BTDR:UNI.SS] M3 screen-space AO / GI / reflections (0 strength = off; the passes are bypassed by Switch TOPs)
    a[27] = (Q['Aointensity'].eval() if Q['Ambientocclusion'].eval() else 0.0,
             Q['Ssgiintensity'].eval() if Q['Ssgi'].eval() else 0.0,
             Q['Ssrintensity'].eval() if Q['Ssr'].eval() else 0.0, 0.0)
    a[28] = (Q['Giradius'].eval() * K, 8.0 if high else 6.0, 2.0 if high else 1.0, Q['Fogjitter'].eval())
    a[29] = (Q['Ssrmaxdistance'].eval() * K, 32.0 if high else 20.0, Q['Ssrmaxroughness'].eval(), Q['Ssrthickness'].eval() * K)
    fz = a[9][2] if cam is not None else 1.0
    a[30] = (0.1, 1.0, fz, Q['Fogcurweight'].eval())
    # [BTDR:UNI.FOG] volumetric fog
    a[31] = (Q['Fogdensity'].eval() / K, Q['Fogheightfalloff'].eval() / K, Q['Fogbaseheight'].eval() * K, Q['Foganisotropy'].eval())
    a[32] = (0.1 * K, max(Q['Fogdistance'].eval(), 0.2) * K, Q['Fogambient'].eval(), Q['Fognoise'].eval())
    a[33] = (Q['Fogcolorr'].eval(), Q['Fogcolorg'].eval(), Q['Fogcolorb'].eval(), 1.0 if Q['Fog'].eval() else 0.0)
    # [BTDR:UNI.HFAO] height-field AO: top-down map centre x / z, width, camera height (= topcam); on, intensity,
    # radius, sample count (directions)
    rng = Q['Shadowrange'].eval()
    a[34] = (Q['Shadowcenterx'].eval(), Q['Shadowcenterz'].eval(), rng, Q['Shadowcentery'].eval() + rng)
    a[35] = (1.0 if Q['Heightfieldao'].eval() else 0.0, Q['Hfaointensity'].eval(), Q['Hfaoradius'].eval() * K, 8.0 if high else 4.0)
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
        key = (a[10], a[11], a[12][3], a[15], a[36][0], a[37], a[38], tuple(a[68:108]))   # 0.9.1: + local lights
        if rs.get('static') != key:
            rs['static'] = key
            keep = {10, 11, 12, 15, 36, 37, 38, 42, 43} | set(range(68, 108))   # 0.9.1: unit, light count, local lights
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
