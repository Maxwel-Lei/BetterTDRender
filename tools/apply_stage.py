# [BTDR:FILE.TOOL.APPLYSTAGE] Copy staged files into place after checking their md5 (device commits sometimes do not land,
# see IMPLEMENTATION_2 §11 #25). Manifest btdr/stage/<STAGE_MANIFEST>: one "dest staged_name md5" per line.
# Run: STAGE_MANIFEST = 'manifest_x.txt'; exec(open(project.folder + '/btdr/tools/apply_stage.py', encoding='utf-8').read())
import hashlib as _h, shutil as _sh
_BT = project.folder + '/btdr'
STAGE_RESULT = []
for _ln in open(_BT + '/stage/' + STAGE_MANIFEST, encoding='utf-8').read().split('\n'):
    if not _ln.strip(): continue
    _dst, _st, _md = _ln.split()
    _got = _h.md5(open(_BT + '/stage/' + _st, 'rb').read()).hexdigest()
    if _got != _md:
        STAGE_RESULT.append('MISMATCH %s %s' % (_st, _got)); continue
    _sh.copyfile(_BT + '/stage/' + _st, _BT + '/' + _dst)
    STAGE_RESULT.append('ok ' + _dst)
