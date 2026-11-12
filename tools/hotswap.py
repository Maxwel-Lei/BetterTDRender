# [BTDR:FILE.TOOL.HOTSWAP] Rebuild release/BTDR.tox and replace /project1/btdr_demo/renderBTDR1 with it,
# keeping every parameter value / expression and the output wiring.
# Run: exec(open(project.folder + '/btdr/tools/hotswap.py', encoding='utf-8').read())
# Other targets: set HOTSWAP_TARGETS = ['/path/renderBTDR1', ...] before exec; HOTSWAP_NOBUILD = True skips the build.
if not globals().get('HOTSWAP_NOBUILD'):
    exec(open(project.folder + '/btdr/build.py', encoding='utf-8').read())
HOTSWAP = []
for _T in globals().get('HOTSWAP_TARGETS', ['/project1/btdr_demo/renderBTDR1']):
  if op(_T) is None: continue
  _old = op(_T); _D = _old.parent(); _nm = _old.name
  _vals = {}
  for _p in _old.customPars:
      if _p.readOnly or _p.style == 'Pulse': continue
      _vals[_p.name] = (_p.mode, _p.expr if _p.mode == ParMode.EXPRESSION else _p.val)
  _outs = [(_k, _c.owner.path, _c.index) for _k, _oc in enumerate(_old.outputConnectors) for _c in _oc.connections]
  _x, _y = _old.nodeX, _old.nodeY
  _old.destroy()
  _R = _D.loadTox(project.folder + '/btdr/release/BTDR.tox'); _R.name = _nm; _R.nodeX, _R.nodeY = _x, _y
  for _k, (_m, _v) in _vals.items():
      _p = _R.par[_k]
      if _p is None: continue
      if _m == ParMode.EXPRESSION: _p.expr = _v
      else: _p.val = _v
  for _k, _path, _i in _outs:
      _R.outputConnectors[_k].connect(op(_path).inputConnectors[_i])
  _R.Refresh()
  HOTSWAP.append(dict(path=_R.path, build=BLOG[:2] if 'BLOG' in globals() else None, status=_R.par.Status.eval(), version=_R.par.Version.eval(),
                 errors=[(o.path, o.errors()) for o in _R.findChildren() if o.errors()]))
