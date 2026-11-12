# [BTDR:FILE.TOOL.RELEASE] make_release.py — packs release/BTDR_<version>.zip from the built files.
# Run after build.py and examples/make_example.py:
#   exec(open(project.folder + '/btdr/tools/make_release.py', encoding='utf-8').read())
# Result: btdr/out/release_log.txt (first line STATUS DONE / FAIL).
import os, zipfile, hashlib, traceback
BT = project.folder + '/btdr'
_log = []
try:
    _src = BT + '/release/BTDR.tox'
    _ver = None
    # [BTDR:RELEASE.VERSION] the version comes from build.py (the same string the tox carries), not typed in
    import re
    _ver = re.search(r"^VERSION\s*=\s*'([^' ]+)", open(BT + '/build.py', encoding='utf-8').read(), re.M).group(1)
    _zip = BT + '/release/BTDR_%s.zip' % _ver
    _files = [(BT + '/release/BTDR.tox', 'BTDR.tox'),
              (BT + '/release/BTDR_Example.tox', 'BTDR_Example.tox'),
              (BT + '/docs/USER_GUIDE.md', 'USER_GUIDE.md'),
              (BT + '/docs/RELEASE_README.txt', 'README.txt')]
    for _f in sorted(os.listdir(BT + '/examples/hdri')):
        _files.append((BT + '/examples/hdri/' + _f, 'hdri/' + _f))
    with zipfile.ZipFile(_zip, 'w', zipfile.ZIP_DEFLATED) as _z:
        for _a, _n in _files:
            _z.write(_a, 'BTDR_%s/%s' % (_ver, _n))
            _log.append('%-28s %9d  %s' % (_n, os.path.getsize(_a), hashlib.md5(open(_a, 'rb').read()).hexdigest()))
    _log.insert(0, 'STATUS DONE  %s  %d bytes' % (os.path.basename(_zip), os.path.getsize(_zip)))
except Exception:
    _log.insert(0, 'STATUS FAIL'); _log.append(traceback.format_exc())
open(BT + '/out/release_log.txt', 'w', encoding='utf-8').write('\n'.join(_log))
