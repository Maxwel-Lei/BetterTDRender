# [BTDR:FILE.TOOL.SHOTS] Fixed camera shots of the demo scene for before/after comparisons.
# Run: SHOT_TAG = 'x'; exec(open(project.folder + '/btdr/tools/shots.py', encoding='utf-8').read())
# Writes btdr/out/shot_<TAG>_<name>.jpg, then btdr/out/shots_done.txt; restores the camera afterwards.
# Frame driven (one shot every few frames, timeline playing): moving the camera and force-cooking in the same
# frame can render with a stale camera. A camera orbit path (Path SOP on cam1) is detached during the shots.
D = op('/project1/btdr_demo'); O = D.op('OUT'); _c = D.op('cam1'); _t = D.op('target')
SHOTS = [     # test-model layout ([BTDR:DEMO.TESTMODELS]): AntiqueCamera at x -0.55, FlightHelmet at x 0.6
    ('wide',   (1.1, 1.15, 3.4, 45), (0.0, 0.62, 0.0)),
    ('camera', (-0.05, 1.55, 0.85, 35), (-0.55, 1.38, 0.0)),
    ('helmet', (1.05, 0.85, 1.05, 35), (0.6, 0.68, 0.15)),
    ('low',    (0.2, 0.3, 2.6, 50), (0.0, 0.5, 0.0)),
]
_WAIT = globals().get('SHOT_WAIT', 4)          # frames per shot (TAA needs ~20 to converge)
_ST = dict(i=-1, f=0, tag=SHOT_TAG, play=op('/').time.play, path=_c.par.pathop.eval(),
           sv=[(_c.par.tx.eval(), _c.par.ty.eval(), _c.par.tz.eval(), _c.par.fov.eval()), (_t.par.tx.eval(), _t.par.ty.eval(), _t.par.tz.eval())])
def _set(cp, tp):
    _c.par.tx, _c.par.ty, _c.par.tz, _c.par.fov = cp
    _t.par.tx, _t.par.ty, _t.par.tz = tp
_c.par.pathop = ''                 # the demo camera may follow an orbit path (Path SOP); detach it for the shots
def _shot_cb():
    s = _ST
    s['f'] += 1
    if s['i'] >= 0 and s['f'] == _WAIT:
        O.save(project.folder + '/btdr/out/shot_%s_%s.jpg' % (s['tag'], SHOTS[s['i']][0]))
    if s['i'] < 0 or s['f'] >= _WAIT:
        s['i'] += 1; s['f'] = 0
        if s['i'] < len(SHOTS):
            _set(SHOTS[s['i']][1], SHOTS[s['i']][2])
        else:
            _set(*s['sv']); _c.par.pathop = s['path'] or ''; op('/').time.play = s['play']
            open(project.folder + '/btdr/out/shots_done.txt', 'w').write(s['tag'])
            op('/project1/shots_exec').destroy()
if op('/project1').op('shots_exec'): op('/project1/shots_exec').destroy()
_ex = op('/project1').create(executeDAT, 'shots_exec')
_ex.text = "def onFrameEnd(frame):\n    me.fetch('cb')()\n    return\n"
_ex.store('cb', _shot_cb)
_ex.par.frameend = True; _ex.par.active = True
open(project.folder + '/btdr/out/shots_done.txt', 'w').write('running')
op('/').time.play = True
