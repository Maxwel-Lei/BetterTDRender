# [BTDR:M0] technical validation for the BetterTDRender toolkit.
# Run inside TouchDesigner: exec(open(project.folder + '/btdr/m0/m0_test.py', encoding='utf-8').read())
# Builds /project1/btdr_m0 and schedules delayed checks; results go to btdr/m0/result.txt
import traceback, os
import numpy as np

OUTF = project.folder + '/btdr/m0/result.txt'
LOGM = []
def log(*a):
    LOGM.append(' '.join(str(x) for x in a))
def flush():
    open(OUTF, 'w', encoding='utf-8').write('\n'.join(LOGM))

root = op('/project1')
if root.op('btdr_m0'): root.op('btdr_m0').destroy()
T = root.create(baseCOMP, 'btdr_m0')
T.nodeX, T.nodeY = 600, -450

def glsl_text(name, code):
    d = T.create(textDAT, name); d.text = code; return d

# ------------------------------------------------------------------ test 2 (set up first: shared CHOP)
try:
    cb = T.create(textDAT, 'cam_chop_callbacks')
    cb.text = '''
import numpy as np
def onCook(scriptOp):
    scriptOp.clear()
    a = np.zeros((4, 6), dtype=np.float32)      # 4 channels (xyzw) x 6 samples (array elements)
    a[:, 1] = (0.25, 0.5, 0.75, 1.0)
    a[0, 2] = absTime.frame % 1000              # changes every frame
    scriptOp.copyNumpyArray(a)
    return
'''
    sc = T.create(scriptCHOP, 'cam_chop')
    sc.par.callbacks = cb
    sc.cook(force=True)
    log('T2 scriptCHOP chans=%d samples=%d names=%s err=%r' % (sc.numChans, sc.numSamples, [c.name for c in sc.chans()], sc.errors()))
except Exception:
    log('T2 scriptCHOP FAILED', traceback.format_exc())

def set_array(o, name, chop):
    o.seq.array.numBlocks = 1
    o.par.array0name = name
    o.par.array0type = 'vec4'
    o.par.array0chop = chop
    try: o.par.array0arraytype = 'uniformarray'
    except Exception as e: log('arraytype', e)

# GLSL TOP reading the array
try:
    f = glsl_text('t2_top_frag', 'uniform vec4 uCam[6];\nout vec4 fragColor;\nvoid main(){ fragColor = uCam[1]; }\n')
    gt = T.create(glslmultiTOP, 't2_top')
    gt.par.pixeldat = f
    gt.par.outputresolution = 'custom'; gt.par.resolutionw = gt.par.resolutionh = 8
    gt.par.format = 'rgba32float'
    set_array(gt, 'uCam', T.op('cam_chop'))
except Exception:
    log('T2 TOP setup FAILED', traceback.format_exc())

# ------------------------------------------------------------------ test 1: COMP with Out MAT as material; also MAT reading the CHOP array
try:
    mc = T.create(baseCOMP, 'material_comp')
    v = mc.create(textDAT, 'vert'); v.text = 'void main(){ gl_Position = TDWorldToProj(TDDeform(P)); }\n'
    p = mc.create(textDAT, 'frag'); p.text = 'uniform vec4 uCam[6];\nout vec4 fragColor;\nvoid main(){ TDCheckDiscard(); fragColor = TDOutputSwizzle(vec4(uCam[1].rgb, 1.0)); }\n'
    gm = mc.create(glslMAT, 'glsl')
    gm.par.vdat = v; gm.par.pdat = p
    set_array(gm, 'uCam', T.op('cam_chop'))
    om = mc.create(outMAT, 'out1')
    gm.outputConnectors[0].connect(om)
    geo = T.create(geometryCOMP, 'geo')
    for c in list(geo.children): c.destroy()
    s = geo.create(sphereSOP, 'sphere'); s.render = True; s.display = True
    cam = T.create(cameraCOMP, 'cam'); cam.par.tz = 3
    results = {}
    for label, target in (('comp_path', mc), ('inner_mat', gm), ('out_mat', om)):
        try:
            geo.par.material = target
            results[label] = 'set ok -> %r' % geo.par.material.eval()
        except Exception as e:
            results[label] = 'set FAILED %r' % e
    log('T1 material assignment attempts:', results)
    geo.par.material = mc                      # the one we hope works
    r = T.create(renderTOP, 't1_render')
    r.par.camera = cam; r.par.geometry = geo; r.par.lights = ''
    r.par.outputresolution = 'custom'; r.par.resolutionw = r.par.resolutionh = 64
    r.par.format = 'rgba32float'
    log('T1 comp outputConnectors=%d types=%s' % (len(mc.outputConnectors), [str(getattr(c, 'outOP', None)) for c in mc.outputConnectors]))
except Exception:
    log('T1 setup FAILED', traceback.format_exc())

# POP reading the array
try:
    gp = T.create(gridPOP, 't2_grid'); gp.par.surftype = 'points'; gp.par.cols = 4; gp.par.rows = 4
    cd = glsl_text('t2_pop_comp', 'void main(){ const uint id = TDIndex(); if (id >= TDNumElements()) return; Val[id] = uCam[1]; }\n')
    pp = T.create(glslPOP, 't2_pop'); pp.par.computedat = cd
    gp.outputConnectors[0].connect(pp)
    pp.par.attr0name = 'custom'; pp.par.attr0customname = 'Val'; pp.par.attr0type = 'float'; pp.par.attr0numcomps = '4'
    set_array(pp, 'uCam', T.op('cam_chop'))
    pt = T.create(poptoTOP, 't2_pop_top'); pt.par.pop = pp; pt.par.rgbamode = 'custom'; pt.par.extract = 'point'; pt.par.attribscope = 'Val'
    pt.par.format = 'rgba32float'
except Exception:
    log('T2 POP setup FAILED', traceback.format_exc())

# ------------------------------------------------------------------ test 3: disabled feature costs nothing (Switch TOP, pull-based cooking)
try:
    hv = glsl_text('t3_heavy_frag', 'uniform vec4 uCam[6];\nout vec4 fragColor;\nvoid main(){ vec4 c = vec4(0.0); for (int i = 0; i < 400; i++) c += texture(sTD2DInputs[0], vUV.st + vec2(float(i) * 0.0003 + uCam[2].x * 1e-6)); fragColor = c / 400.0; }\n')
    src = T.create(noiseTOP, 't3_src'); src.par.outputresolution = 'custom'; src.par.resolutionw = 1280; src.par.resolutionh = 720
    heavy = T.create(glslmultiTOP, 't3_heavy'); heavy.par.pixeldat = hv
    src.outputConnectors[0].connect(heavy)
    set_array(heavy, 'uCam', T.op('cam_chop'))
    sw = T.create(switchTOP, 't3_switch')
    src.outputConnectors[0].connect(sw); heavy.outputConnectors[0].connect(sw)
    sw.par.index = 1
    o3 = T.create(nullTOP, 't3_out'); sw.outputConnectors[0].connect(o3)
except Exception:
    log('T3 setup FAILED', traceback.format_exc())

# ------------------------------------------------------------------ test 4: scripted COMP with custom parameter pages -> .tox -> reload
try:
    oc = T.create(baseCOMP, 'renderBTDR_proto')
    log('T4 append methods:', sorted(m for m in dir(oc.appendCustomPage('Tmp')) if m.startswith('append')))
    oc.destroyCustomPars()
    pg = oc.appendCustomPage('Render')
    made = {}
    def tryadd(fn, *a, **k):
        try:
            made[a[0]] = [p.name for p in getattr(pg, fn)(*a, **k)]
        except Exception as e:
            made[a[0]] = 'FAILED %s %r' % (fn, e)
    tryadd('appendOBJ', 'Camera', label='Camera')
    tryadd('appendStr', 'Geometry', label='Geometry')
    tryadd('appendOBJ', 'Lights', label='Lights')
    tryadd('appendInt', 'Resolution', label='Resolution', size=2)
    tryadd('appendMenu', 'Quality', label='Quality')
    tryadd('appendToggle', 'Fogactive', label='Fog')
    tryadd('appendFloat', 'Fogdensity', label='Fog Density')
    tryadd('appendPulse', 'Buildproxy', label='Build Proxy')
    tryadd('appendRGB', 'Tint', label='Tint')
    try:
        oc.par.Quality.menuNames = ['high', 'low', 'custom']; oc.par.Quality.menuLabels = ['High', 'Low', 'Custom']
        oc.par.Quality = 'low'
        oc.par.Fogdensity.normMin = 0; oc.par.Fogdensity.normMax = 1; oc.par.Fogdensity.default = 0.22; oc.par.Fogdensity = 0.22
        oc.par.Fogdensity.enableExpr = 'me.par.Fogactive'
    except Exception as e:
        made['menu/ranges'] = 'FAILED %r' % e
    log('T4 custom pars:', made)
    # extension class from a DAT + parameter execute
    ext = oc.create(textDAT, 'RenderExt')
    ext.text = '''
class RenderExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.Builds = 0
    def BuildProxy(self):
        self.Builds += 1
        self.ownerComp.store('builds', self.Builds)
        return self.Builds
'''
    try:
        oc.par.ext0object = "op('./RenderExt').module.RenderExt(me)"
        oc.par.ext0name = 'RenderExt'
        oc.par.ext0promote = True
        oc.par.reinitextensions.pulse()
    except Exception as e:
        log('T4 ext setup FAILED %r' % e)
    pe = oc.create(parameterexecuteDAT, 'parexec')
    pe.text = '''
def onPulse(par):
    if par.name == 'Buildproxy':
        parent().BuildProxy()
    return
def onValueChange(par, prev):
    parent().store('last_change', (par.name, par.eval()))
    return
'''
    try:
        pe.par.op = oc; pe.par.pars = '*'; pe.par.custom = True; pe.par.builtin = False
        pe.par.onpulse = True; pe.par.valuechange = True; pe.par.active = True
    except Exception as e:
        log('T4 parexec setup FAILED %r' % e, sorted(p.name for p in pe.pars()))
    it = oc.create(inTOP, 'in1'); ot = oc.create(outTOP, 'out1'); ot2 = oc.create(outTOP, 'out2')
    it.outputConnectors[0].connect(ot)
    log('T4 comp connectors in=%d out=%d' % (len(oc.inputConnectors), len(oc.outputConnectors)))
except Exception:
    log('T4 setup FAILED', traceback.format_exc())

flush()

def check():
    try:
        # T2 values
        for name in ('t2_top', 't1_render', 't2_pop_top'):
            o = T.op(name)
            try:
                a = o.numpyArray()
                c = a[a.shape[0] // 2, a.shape[1] // 2]
                log('CHECK %s centre=%s err=%r warn=%r' % (name, np.round(c, 3).tolist(), o.errors(), o.warnings()))
            except Exception as e:
                log('CHECK %s FAILED %r err=%r' % (name, e, o.errors()))
        for name in ('material_comp/glsl', 't2_pop', 'geo'):
            o = T.op(name); log('CHECK %s err=%r warn=%r' % (name, o.errors(), o.warnings()))
        # T3: cooks of the heavy node with the switch on / off, driven by forcing the output each frame
        heavy = T.op('t3_heavy'); sw = T.op('t3_switch'); o3 = T.op('t3_out')
        T.store('t3', {'on_start': heavy.totalCooks})
        log('T3 heavy gpu ms while selected = %.3f' % heavy.gpuCookTime)
        sw.par.index = 0
        T.store('t3_off_start', heavy.totalCooks)
        # T4: change pars, pulse, save, reload
        oc = T.op('renderBTDR_proto')
        oc.par.Fogdensity = 0.5
        oc.par.Buildproxy.pulse()
        flush()
        run("args[0]()", check2, delayFrames=60)
    except Exception:
        log('check FAILED', traceback.format_exc()); flush()

def check2():
    try:
        heavy = T.op('t3_heavy')
        log('T3 heavy cooks during 60 frames while NOT selected = %d (0 means free)' % (heavy.totalCooks - T.fetch('t3_off_start')))
        oc = T.op('renderBTDR_proto')
        log('T4 after pulse: builds=%r last_change=%r ext attr=%r' % (oc.fetch('builds', None), oc.fetch('last_change', None), getattr(oc, 'Builds', 'no promoted attr')))
        d = project.folder + '/btdr/m0'
        path = oc.save(d + '/renderBTDR_proto.tox')
        log('T4 saved tox: %s size=%d' % (path, os.path.getsize(d + '/renderBTDR_proto.tox')))
        if T.op('reloaded'): T.op('reloaded').destroy()
        n = T.loadTox(d + '/renderBTDR_proto.tox'); n.name = 'reloaded'
        log('T4 reloaded: custom pages=%s Quality=%r menu=%s Fogdensity=%r enable=%r' % ([p.name for p in n.customPages], n.par.Quality.eval(), list(n.par.Quality.menuNames), n.par.Fogdensity.eval(), n.par.Fogdensity.enable))
        n.par.Buildproxy.pulse()
        run("args[0]()", check3, delayFrames=10)
        flush()
    except Exception:
        log('check2 FAILED', traceback.format_exc()); flush()

def check3():
    try:
        n = T.op('reloaded')
        log('T4 reloaded copy after pulse: builds=%r (extension + parexec survive save/load)' % (n.fetch('builds', None),))
        log('DONE')
    except Exception:
        log('check3 FAILED', traceback.format_exc())
    flush()

# keep everything cooking while we measure
drv = T.create(executeDAT, 'm0_driver')
drv.text = "def onFrameStart(frame):\n    for n in ('t3_out', 't2_top', 't1_render', 't2_pop_top'):\n        o = parent().op(n)\n        if o is not None: o.cook(force=True)\n    return\n"
drv.par.framestart = True; drv.par.active = True
run("args[0]()", check, delayFrames=90)
