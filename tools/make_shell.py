# [BTDR:FILE.TOOL.SHELL] make_shell.py — wraps release/BTDR.tox in a public shell: release/BTDR_Shell.tox.
# Run after build.py:  exec(open(project.folder + '/btdr/tools/make_shell.py', encoding='utf-8').read())
# Why: with TD Privacy on, a component cannot show one of its inner TOPs as its node viewer (the node tile is
# empty). The shell `renderBTDR` is a plain Base COMP that stays public: it carries the parameter pages, the
# three outputs and the node viewer; everything else is in `core` (the normal renderBTDR), which the author
# can then make private (enter the shell, RMB on core > Privacy). [BTDR:EXT.SHELL]
import os, shutil, traceback
BT = project.folder + '/btdr'
SLOG = []
try:
    P = op('/project1')
    if P.op('btdr_shell_build'): P.op('btdr_shell_build').destroy()
    tmp = P.create(baseCOMP, 'btdr_shell_build')
    S = tmp.create(baseCOMP, 'renderBTDR')
    S.tags.add('BTDRshell')
    S.color = (0.5, 0.5, 0.05)
    core = S.loadTox(BT + '/release/BTDR.tox'); core.name = 'core'; core.nodeX, core.nodeY = 0, 0
    S.copyParameters(core, custom=True, builtin=False)
    S.store('version', core.fetch('version', ''))
    for i in range(3):
        o = S.create(outTOP, 'out%d' % (i + 1)); o.nodeX, o.nodeY = 300, 150 - i * 150
        core.outputConnectors[i].connect(o)
    # pulses do not travel through a binding: forward them
    pe = S.create(parameterexecuteDAT, 'shell_pulse'); pe.nodeX, pe.nodeY = 0, -200
    pe.text = ("# [BTDR:EXT.SHELL] forward the shell's pulse parameters to the core\n"
               "def onPulse(par):\n    p = getattr(op('core').par, par.name, None)\n    if p is not None:\n        p.pulse()\n    return\n")
    pe.par.op = '..'; pe.par.pars = '*'; pe.par.custom = True; pe.par.builtin = False
    pe.par.onpulse = True; pe.par.valuechange = False; pe.par.active = True
    S.par.opviewer = './out1'; S.viewer = True
    core.SyncShell()
    core.Refresh()
    S.save(BT + '/release/BTDR_Shell.tox')
    SLOG.append('saved release/BTDR_Shell.tox (%d bytes), %d shell parameters' % (os.path.getsize(BT + '/release/BTDR_Shell.tox'), len(S.customPars)))
    pal = os.path.join(os.path.expanduser('~'), 'Documents', 'Derivative', 'Palette', 'BTDR')
    if os.path.isdir(pal):
        shutil.copyfile(BT + '/release/BTDR_Shell.tox', os.path.join(pal, 'BTDR_Shell.tox'))
        SLOG.append('copied to the Palette')
    tmp.destroy()
    SLOG.insert(0, 'STATUS DONE')
except Exception:
    SLOG.insert(0, 'STATUS ERROR'); SLOG.append(traceback.format_exc())
open(BT + '/out/shell_log.txt', 'w', encoding='utf-8').write('\n'.join(SLOG))
