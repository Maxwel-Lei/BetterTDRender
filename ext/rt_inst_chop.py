# [BTDR:FILE.RTINST] rt_inst_chop.py — (0.9.3) Script CHOP callbacks: the instance transforms of one instanced Geometry
# COMP as channels tx ty tz rx ry rz sx sy sz, one sample per instance, for the ray-tracing proxy ([BTDR:EXT.RTINST]).
# The source path and the instance cap are stored on the Script CHOP (store 'src', 'cap'). Reads the same OPs and
# channel / column names as the Geometry COMP's Instance pages: a CHOP (channels) or a table DAT (columns, first row =
# names). Other instance OP types (TOP, SOP, POP) are not read: the object stays out of the proxy, with a warning.
# Reading the source here makes this CHOP cook again whenever the instances change.
import numpy as np

NAMES = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz')
DEFAULTS = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
GROUP_OP = {'t': 'instancetop', 'r': 'instancerop', 's': 'instancesop'}


def _values(o, name):
    if o is None or not name:
        return None
    if o.family == 'CHOP':
        c = o.chan(name)
        return None if c is None else np.asarray(c.vals, dtype=np.float32)
    if o.family == 'DAT' and o.isTable:
        col = o.col(name)
        if col is None:
            return None
        out = []
        for cell in col[1:]:
            try:
                out.append(float(cell.val))
            except ValueError:
                out.append(0.0)
        return np.asarray(out, dtype=np.float32)
    return None


def source_kind(src):
    """'ok' when every instance OP used by src is a CHOP or table DAT, else the unsupported OP type."""
    P = src.par
    for g in ('t', 'r', 's'):
        o = getattr(P, GROUP_OP[g]).eval() or P.instanceop.eval()
        if o is not None and not (o.family == 'CHOP' or (o.family == 'DAT' and o.isTable)):
            return o.OPType
    return 'ok'


def onCook(scriptOp):
    scriptOp.clear()
    src = op(scriptOp.fetch('src', ''))
    if src is None:
        return
    cap = int(scriptOp.fetch('cap', 1024))
    P = src.par
    cols, n = [], None
    for nm in NAMES:
        o = getattr(P, GROUP_OP[nm[0]]).eval() or P.instanceop.eval()
        v = _values(o, getattr(P, 'instance' + nm).eval())
        cols.append(v)
        if v is not None:
            n = len(v) if n is None else min(n, len(v))
    if not n:
        return
    n = min(n, cap)
    scriptOp.numSamples = n
    for nm, d, v in zip(NAMES, DEFAULTS, cols):
        c = scriptOp.appendChan(nm)
        c.copyNumpyArray(v[:n] if v is not None else np.full(n, d, dtype=np.float32))
