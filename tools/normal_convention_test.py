# [BTDR:FILE.TOOL.NORMALTEST]
# !! WARNING: loads the original 2M-triangle mesh. On 2026-11-11 this crashed TouchDesigner while three
# !! other scenes were loaded. Only run it in an otherwise empty project.
# Decide whether a normal map is OpenGL (+Y) or DirectX (-Y) green.
# Ground truth: G-Buffer normals of the original high-poly mesh. Candidates: the simplified mesh with the
# normal map applied as-is and with green flipped. The candidate whose added detail (vs. the plain
# simplified mesh) correlates best with the high-poly detail wins.
# Run: NT_MODEL = '鎏金铜造像'; exec(open(project.folder + '/btdr/tools/normal_convention_test.py', encoding='utf-8').read())
import os, traceback
import numpy as np
PF = project.folder.replace('\\', '/')
SRC = PF + '/模型（装置+手势）'
SIM = PF + '/模型_简化'
NT_LOG = []
model = globals().get('NT_MODEL', '鎏金铜造像')
outp = PF + '/btdr/out/normal_test_%s.txt' % model
def flush(status):
    open(outp, 'w', encoding='utf-8').write('STATUS %s\n' % status + '\n'.join(NT_LOG))
try:
    root = op('/project1')
    if root.op('nt_test'): root.op('nt_test').destroy()
    T = root.create(baseCOMP, 'nt_test')
    d = SRC + '/' + model
    hi_obj = [f for f in os.listdir(d) if f.lower().endswith('.obj')][0]
    nfile = [f for f in os.listdir(d) if '_normal.' in f][0]
    nm = T.create(moviefileinTOP, 'nmap'); nm.par.file = d + '/' + nfile
    flipf = T.create(textDAT, 'flip_frag')
    flipf.text = 'out vec4 fragColor;\nvoid main(){ vec4 c = texture(sTD2DInputs[0], vUV.st); fragColor = vec4(c.r, 1.0 - c.g, c.b, 1.0); }\n'
    nflip = T.create(glslTOP, 'nmap_flip'); nflip.par.pixeldat = flipf
    nm.outputConnectors[0].connect(nflip)
    nflip.par.outputresolution = 'useinput'
    def geo(name, path, mat):
        g = T.create(geometryCOMP, name)
        for c in list(g.children): c.destroy()
        s = g.create(fileinSOP, 'f'); s.par.file = path; s.render = True; s.display = True
        if mat is not None: g.par.material = mat
        return g
    mA = T.create(pbrMAT, 'mA'); mA.par.normalmap = nm
    mB = T.create(pbrMAT, 'mB'); mB.par.normalmap = nflip
    m0 = T.create(pbrMAT, 'm0')
    lo = SIM + '/' + model + '.obj'
    geo('g_hi', d + '/' + hi_obj, m0)
    geo('g_lo', lo, m0)
    gA = geo('g_A', lo, mA)
    gB = geo('g_B', lo, mB)
    cam = T.create(cameraCOMP, 'cam1'); cam.par.fov = 30
    light = T.create(lightCOMP, 'light1'); light.par.lighttype = 'distant'
    R = T.loadTox(PF + '/btdr/release/BTDR.tox'); R.name = 'R'
    R.par.Resolutionw = 1600; R.par.Resolutionh = 1600; R.par.Shadows = False
    keep = T.create(executeDAT, 'keep')
    keep.text = "def onFrameStart(frame):\n    parent().op('R/gbuffer').cook(force=True)\n    return\n"
    keep.par.framestart = True; keep.par.active = True
    shots = {}
    order = ['g_hi', 'g_lo', 'g_A', 'g_B']
    def place_cam():
        b = T.op('g_lo').computeBounds()
        c = np.array([b.center.x, b.center.y, b.center.z]); sz = max(b.size.x, b.size.y, b.size.z)
        cam.par.tx, cam.par.ty, cam.par.tz = c[0], c[1], c[2] + sz * 2.2
        NT_LOG.append('bounds centre %s size %.3f' % (np.round(c, 3).tolist(), sz))
    def step(i):
        try:
            if i == 0:
                place_cam()
            if i > 0:
                shots[order[i - 1]] = R.op('gbuf1').numpyArray().astype(np.float64)[..., :3].copy()
            if i < len(order):
                R.par.Geometry = order[i]
                run("args[0](args[1])", step, i + 1, delayFrames=25)
            else:
                analyse()
        except Exception:
            NT_LOG.append(traceback.format_exc()); flush('ERROR')
    def analyse():
        H, L0, A, B = shots['g_hi'], shots['g_lo'], shots['g_A'], shots['g_B']
        m = ((H ** 2).sum(-1) > 0.25) & ((L0 ** 2).sum(-1) > 0.25)
        dH = (H - L0)[m]; dA = (A - L0)[m]; dB = (B - L0)[m]
        def corr(x, y): return float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum()))
        cA, cB = corr(dH, dA), corr(dH, dB)
        eA = float(np.degrees(np.arccos(np.clip((H[m] * A[m]).sum(-1), -1, 1))).mean())
        eB = float(np.degrees(np.arccos(np.clip((H[m] * B[m]).sum(-1), -1, 1))).mean())
        e0 = float(np.degrees(np.arccos(np.clip((H[m] * L0[m]).sum(-1), -1, 1))).mean())
        NT_LOG.append('%s (%s, %d px): detail corr OpenGL %.4f / DirectX %.4f ; mean angle to high-poly: no map %.2f, OpenGL %.2f, DirectX %.2f deg'
                      % (model, nfile, int(m.sum()), cA, cB, e0, eA, eB))
        NT_LOG.append('RESULT %s %s' % (model, 'OpenGL' if cA > cB else 'DirectX'))
        flush('DONE')
        T.destroy()
    flush('RUNNING')
    run("args[0](args[1])", step, 0, delayFrames=30)
except Exception:
    NT_LOG.append(traceback.format_exc()); flush('ERROR')
