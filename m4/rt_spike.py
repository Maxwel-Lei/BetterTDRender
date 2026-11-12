# [BTDR:FILE.M4.SPIKE] M4 technical check: build a ray-tracing scene POP live from a set of Geometry COMPs
# (SOP -> POP, world transform, ObjId), trace rays with a GLSL POP, time the acceleration-structure rebuild.
# Run: SPIKE_SRC = '/project1/btdr_models/CarConcept'; exec(open(project.folder + '/btdr/m4/rt_spike.py', encoding='utf-8').read())
import time, traceback
OUT = project.folder + '/btdr/out/rt_spike.txt'
LOG = []
try:
    SRC = op(globals().get('SPIKE_SRC', '/project1/btdr_models/CarConcept'))
    P = op('/project1')
    if P.op('rt_spike'): P.op('rt_spike').destroy()
    S = P.create(baseCOMP, 'rt_spike'); S.nodeX, S.nodeY = 1800, -900
    geos = [c for c in SRC.children if c.OPType == 'geometryCOMP']
    mg = S.create(mergePOP, 'merge'); mg.nodeX = 800
    k = 0
    for gi, g in enumerate(geos):
        for ch in g.children:
            if not getattr(ch, 'render', False): continue
            if ch.family == 'SOP':
                s = S.create(soptoPOP, 'src%d' % k); s.par.sop = ch.path
            elif ch.family == 'POP':
                s = S.create(selectPOP, 'src%d' % k); s.par.pop = ch.path
            else: continue
            s.nodeX, s.nodeY = 0, -k * 100
            x = S.create(transformPOP, 'xf%d' % k); x.nodeX, x.nodeY = 200, -k * 100
            x.par.xformmatrixop = g.path
            s.outputConnectors[0].connect(x)
            a = S.create(attributePOP, 'id%d' % k); a.nodeX, a.nodeY = 400, -k * 100
            a.par.attr0name = 'custom'; a.par.attr0customname = 'ObjId'; a.par.attr0type = 'float'
            a.par.attr0numcomps = '1'; a.par.attr0value0 = gi
            x.outputConnectors[0].connect(a)
            a.outputConnectors[0].connect(mg)
            k += 1
    tri = S.create(triangulatePOP, 'tri'); tri.nodeX = 1000
    mg.outputConnectors[0].connect(tri)
    sc = S.create(nullPOP, 'scene'); sc.nodeX = 1200
    tri.outputConnectors[0].connect(sc)
    LOG.append('sources %d' % k)
    # trace grid: 128 x 128 rays straight down from 3 m over a 6 m square
    gr = S.create(gridPOP, 'rays'); gr.nodeX, gr.nodeY = 1200, -300
    gr.par.surftype = 'points'; gr.par.cols = 128; gr.par.rows = 128; gr.par.sizex = 6; gr.par.sizey = 6
    gr.par.rx = -90; gr.par.ty = 3.0
    gl = S.create(glslPOP, 'trace'); gl.nodeX, gl.nodeY = 1400, -300
    gr.outputConnectors[0].connect(gl); sc.outputConnectors[0].connect(gl)
    gl.par.asname = 'uScene'; gl.par.colpop = sc; gl.par.buildflag = 'fasttrace'; gl.par.opaquecolgeo = True
    gl.par.attrclass = 'point'
    gl.par.attr0name = 'custom'; gl.par.attr0customname = 'Hit'; gl.par.attr0type = 'float'; gl.par.attr0numcomps = '4'
    cd = S.create(textDAT, 'trace_compute'); cd.nodeX, cd.nodeY = 1400, -450
    cd.text = '''void main()
{
    const uint id = TDIndex();
    if (id >= TDNumElements()) return;
    vec3 o = TDIn_P(0, id);
    rayQueryEXT rq;
    rayQueryInitializeEXT(rq, uScene, gl_RayFlagsOpaqueEXT, 0xFF, o, 0.001, vec3(0, -1, 0), 10.0);
    while (rayQueryProceedEXT(rq)) {}
    float t = -1.0, obj = -1.0;
    if (rayQueryGetIntersectionTypeEXT(rq, true) == gl_RayQueryCommittedIntersectionTriangleEXT) {
        t = rayQueryGetIntersectionTEXT(rq, true);
        uint prim = uint(rayQueryGetIntersectionPrimitiveIndexEXT(rq, true));
        uint v0 = TDInputPrimVertsStartIndex(1, prim);
        obj = TDIn_ObjId(1, TDInputPointIndex(1, v0));
    }
    Hit[id] = vec4(t, obj, o.y - t, 1.0);
}
'''
    gl.par.computedat = cd
    S.store('t0', time.time())
    def _measure():
        try:
            out = []
            gl.cook(force=True)
            out.append('errors trace: %r scene: %r' % (gl.errors(), sc.errors()))
            out.append('scene points %s prims %s' % (getattr(sc, 'numPoints', '?'), getattr(sc, 'numPrimitives', '?')))
            # timing: force-cook the trace node N times, read its GPU / CPU cook time
            g_t, c_t = [], []
            for i in range(20):
                gl.cook(force=True)
                g_t.append(gl.gpuCookTime); c_t.append(gl.cookTime)
            g_t.sort(); c_t.sort()
            out.append('trace (AS rebuild + 16k rays) GPU median %.3f ms, CPU median %.3f ms' % (g_t[10], c_t[10]))
            import numpy as np
            h = gl.points('Hit') if hasattr(gl, 'points') else None
            out.append('hit attr read: %s' % (type(h)))
            open(OUT, 'w', encoding='utf-8').write('STATUS DONE\n' + '\n'.join(LOG + out))
        except Exception:
            open(OUT, 'w', encoding='utf-8').write('STATUS ERR\n' + '\n'.join(LOG) + '\n' + traceback.format_exc())
    S.store('m', _measure)
    run("op('/project1/rt_spike').fetch('m')()", delayFrames=10)
    open(OUT, 'w', encoding='utf-8').write('STATUS RUNNING')
except Exception:
    open(OUT, 'w', encoding='utf-8').write('STATUS ERR\n' + '\n'.join(LOG) + '\n' + traceback.format_exc())
