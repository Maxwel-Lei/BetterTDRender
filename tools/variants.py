# [BTDR:FILE.TOOL.VARIANTS] Render the demo scene with several parameter sets, one after another, frame driven.
# Run:  VARIANTS = [('tag', {'Bloom': 0.3}), ...]; VAR_CAM = 'helmet'; VAR_ORBIT = False; VAR_WAIT = 40
#       exec(open(project.folder + '/btdr/tools/variants.py', encoding='utf-8').read())
# Writes btdr/out/var_<tag>.jpg and btdr/out/variants_done.txt; restores every parameter and the camera.
D = op('/project1/btdr_demo'); R = D.op('renderBTDR1'); O = D.op('OUT'); _c = D.op('cam1'); _t = D.op('target')
_CAMS = {
    'wide':   ((1.1, 1.15, 3.4, 45), (0.0, 0.62, 0.0)),
    'helmet': ((1.05, 0.85, 1.05, 35), (0.6, 0.68, 0.15)),
    'camera': ((-0.05, 1.55, 0.85, 35), (-0.55, 1.38, 0.0)),
    'floor':  ((1.0, 0.32, 1.35, 40), (0.15, 0.12, 0.0)),        # low view: object feet on the floor (AO, reflections)
    'sun':    ((-2.2, 0.45, -2.0, 55), (0.4, 1.3, 0.4)),          # looking toward the demo light through the objects (fog light shafts)
}
_vw = globals().get('VAR_WAIT', 40)
_orbit = globals().get('VAR_ORBIT', False)
_sv = dict(cam=(_c.par.tx.eval(), _c.par.ty.eval(), _c.par.tz.eval(), _c.par.fov.eval()),
           tgt=(_t.par.tx.eval(), _t.par.ty.eval(), _t.par.tz.eval()), path=_c.par.pathop.eval(),
           pars={k: getattr(R.par, k).eval() for _, d in VARIANTS for k in d}, play=op('/').time.play)
if not _orbit:
    _cp, _tp = _CAMS[globals().get('VAR_CAM', 'helmet')]
    _c.par.pathop = ''
    _c.par.tx, _c.par.ty, _c.par.tz, _c.par.fov = _cp
    _t.par.tx, _t.par.ty, _t.par.tz = _tp
_VS = dict(i=-1, f=0)
def _var_cb():
    s = _VS; s['f'] += 1
    if s['i'] >= 0 and s['f'] == _vw:
        O.save(project.folder + '/btdr/out/var_%s.jpg' % VARIANTS[s['i']][0])
    if s['i'] < 0 or s['f'] >= _vw:
        s['i'] += 1; s['f'] = 0
        if s['i'] < len(VARIANTS):
            for k, v in _sv['pars'].items(): getattr(R.par, k).val = v
            for k, v in VARIANTS[s['i']][1].items(): getattr(R.par, k).val = v
        else:
            for k, v in _sv['pars'].items(): getattr(R.par, k).val = v
            _c.par.tx, _c.par.ty, _c.par.tz, _c.par.fov = _sv['cam']
            _t.par.tx, _t.par.ty, _t.par.tz = _sv['tgt']
            _c.par.pathop = _sv['path'] or ''
            op('/').time.play = _sv['play']
            open(project.folder + '/btdr/out/variants_done.txt', 'w').write('done')
            op('/project1/var_exec').destroy()
if op('/project1').op('var_exec'): op('/project1/var_exec').destroy()
_ex = op('/project1').create(executeDAT, 'var_exec')
_ex.text = "def onFrameEnd(frame):\n    me.fetch('cb')()\n    return\n"
_ex.store('cb', _var_cb); _ex.par.frameend = True; _ex.par.active = True
open(project.folder + '/btdr/out/variants_done.txt', 'w').write('running')
op('/').time.play = True
