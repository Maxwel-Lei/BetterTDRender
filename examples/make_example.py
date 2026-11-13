# [BTDR:FILE.EXAMPLE] make_example.py — builds the self-contained example component BTDR_Example.tox (M5).
# Only native operators (primitives, PBR MAT, built-in studio environment): no external files, so the .tox works when
# dropped into any project. Contains its own copy of renderBTDR (from release/BTDR.tox).
# Run: exec(open(project.folder + '/btdr/examples/make_example.py', encoding='utf-8').read())
# Writes btdr/examples/BTDR_Example.tox (+ a copy in btdr/release/), log in btdr/out/example_log.txt
import traceback
BT = project.folder + '/btdr'
LOG = []
try:
    P = op('/project1')
    if P.op('btdr_example'): P.op('btdr_example').destroy()
    E = P.create(containerCOMP, 'btdr_example'); E.nodeX, E.nodeY = 2000, -300
    E.par.w, E.par.h = 960, 540
    def place(o, x, y):
        o.nodeX, o.nodeY = x, y
        return o
    # [BTDR:EXAMPLE.CAMERA] slow swing in front of the scene, always looking at `target`
    tg = place(E.create(nullCOMP, 'target'), 0, 300); tg.par.ty = 0.6
    cam = place(E.create(cameraCOMP, 'cam1'), 0, 450)
    # swings +-55 degrees in front of the scene (the red wall stands behind it)
    cam.par.tx.expr = 'math.sin(math.sin(absTime.seconds * 0.2) * 0.95) * 4.2'
    cam.par.tz.expr = 'math.cos(math.sin(absTime.seconds * 0.2) * 0.95) * 4.2 + 0.4'
    cam.par.ty = 1.5; cam.par.fov = 40; cam.par.lookat = tg
    # [BTDR:EXAMPLE.LIGHT] one distant light (BTDR draws its own shadows: the native shadow stays off)
    lt = place(E.create(lightCOMP, 'light1'), 0, 150)
    lt.par.lighttype = 'distant'; lt.par.rx = -40; lt.par.ry = 35; lt.par.dimmer = 1.0
    try: lt.par.shadowtype = 'off'
    except Exception: pass
    def mat(nm, rgb, metal, rough, emit=(0, 0, 0), y=0):
        m = place(E.create(pbrMAT, nm), 600, y)
        m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = rgb
        m.par.metallic = metal; m.par.roughness = rough
        m.par.emitr, m.par.emitg, m.par.emitb = emit
        return m
    def geo(nm, sop, material, t=(0, 0, 0), s=(1, 1, 1), r=(0, 0, 0), y=0, **kw):
        g = place(E.create(geometryCOMP, nm), 300, y)
        for c in list(g.children): c.destroy()
        so = g.create(sop, 'shape'); so.render = so.display = True
        for k, v in kw.items(): setattr(so.par, k, v)
        g.par.tx, g.par.ty, g.par.tz = t; g.par.sx, g.par.sy, g.par.sz = s; g.par.rx, g.par.ry, g.par.rz = r
        g.par.material = material
        return g
    # [BTDR:EXAMPLE.SCENE] a glossy floor, five spheres from mirror to matte, a red wall (colour bleeding) and an
    # arch (occlusion under it: probe GI / traced reflections), a glowing cube (emissive + bloom)
    geo('floor', gridSOP, mat('m_floor', (0.18, 0.18, 0.19), 0.0, 0.22, y=0), y=0, sizex=24, sizey=24, orient='zx', rows=2, cols=2)
    specs = [('chrome', (0.95, 0.95, 0.95), 1.0, 0.05), ('gold', (1.0, 0.78, 0.34), 1.0, 0.3), ('plastic', (0.8, 0.08, 0.06), 0.0, 0.35),
             ('clay', (0.75, 0.72, 0.68), 0.0, 0.85), ('teal', (0.05, 0.45, 0.45), 0.0, 0.12)]
    for i, (nm, rgb, me, ro) in enumerate(specs):
        geo('sphere_' + nm, sphereSOP, mat('m_' + nm, rgb, me, ro, y=-100 - i * 100), t=(-1.6 + i * 0.8, 0.3, 0.6),
            y=-100 - i * 100, radx=0.3, rady=0.3, radz=0.3, rows=40, cols=40, freq=10, type='poly')
    geo('wall', boxSOP, mat('m_wall', (0.85, 0.12, 0.08), 0.0, 0.6, y=-650), t=(0, 0.75, -1.2), y=-650, sizex=4.0, sizey=1.5, sizez=0.15)
    am = mat('m_arch', (0.82, 0.82, 0.8), 0.0, 0.5, y=-750)
    geo('arch_top', boxSOP, am, t=(2.4, 0.95, 0.2), y=-750, sizex=1.2, sizey=0.12, sizez=0.9)
    geo('arch_left', boxSOP, am, t=(1.9, 0.45, 0.2), y=-850, sizex=0.15, sizey=0.9, sizez=0.9)
    geo('arch_right', boxSOP, am, t=(2.9, 0.45, 0.2), y=-950, sizex=0.15, sizey=0.9, sizez=0.9)
    geo('glow', boxSOP, mat('m_glow', (1.0, 0.55, 0.2), 0.0, 0.5, emit=(4.0, 1.6, 0.4), y=-1050), t=(-2.5, 0.2, -0.3),
        r=(0, 30, 0), y=-1050, sizex=0.4, sizey=0.4, sizez=0.4)
    # [BTDR:EXAMPLE.RENDER] the renderer, as a user would drop it in: defaults, plus a little bloom for the glowing cube
    R = E.loadTox(BT + '/release/BTDR.tox'); R.name = 'renderBTDR1'; R.nodeX, R.nodeY = 900, 300
    R.par.Bloom = 0.15
    o = place(E.create(nullTOP, 'OUT'), 1100, 300)
    R.outputConnectors[0].connect(o)
    E.par.opviewer = 'OUT'
    keep = place(E.create(executeDAT, 'keep_cooking'), 1100, 450)       # cook every frame while building (histories)
    keep.text = "def onFrameStart(frame):\n    op('OUT').cook()\n    return\n"
    keep.par.framestart = True; keep.par.active = True
    try: E.viewer = True
    except Exception: pass
    R.Refresh()
    E.par.top = o if hasattr(E.par, 'top') else None
    note = E.create(textDAT, 'README'); note.nodeX, note.nodeY = 900, 500
    note.text = ('BetterTDRender (BTDR) example. renderBTDR1 renders every Geometry COMP in this network with cam1 and light1.\n'
                 'Everything is native: PBR MAT on each Geometry COMP, one distant Light COMP, a Camera COMP.\n'
                 'Parameters of renderBTDR1: see the user guide (BTDR-UserGuide / 使用手册).\n')
    LOG.append('status: ' + R.par.Status.eval())
    def _save():
        # [BTDR:EXAMPLE.NOSTORE] drop the callback from storage first: a Python function cannot be pickled, so it
        # would break saving the example .tox and the user's .toe ("PicklingError: Can't pickle <function _save>")
        E.unstore('save')
        try:
            errs = [(x.path, x.errors()) for x in E.findChildren() if x.errors()]
            LOG.append('errors: %r' % errs[:5])
            E.op('OUT').save(BT + '/out/example.jpg')
            E.op('keep_cooking').par.active = False                    # in the saved file only the viewer pulls the image
            E.op('renderBTDR1').par.Startupinfo = True                 # the dialog switched it off while building ([BTDR:EXT.INFOONCE])
            E.save(BT + '/examples/BTDR_Example.tox')
            E.save(BT + '/release/BTDR_Example.tox')
            # [BTDR:EXAMPLE.PALETTE] keep the copy in the user's Palette current as well (build.py does it for BTDR.tox)
            import os, shutil
            _pal = os.path.join(os.path.expanduser('~'), 'Documents', 'Derivative', 'Palette', 'BTDR')
            if os.path.isdir(_pal):
                shutil.copyfile(BT + '/release/BTDR_Example.tox', os.path.join(_pal, 'BTDR_Example.tox'))
            # [BTDR:BUILD.BACKUP] versioned copy (release/versions/ and the Palette), never overwritten
            import re as _re
            _v = _re.search(r"^VERSION = '([^']+)'", open(BT + '/build.py', encoding='utf-8').read(), _re.M).group(1)
            os.makedirs(BT + '/release/versions', exist_ok=True)
            shutil.copyfile(BT + '/release/BTDR_Example.tox', BT + '/release/versions/BTDR_Example_%s.tox' % _v)
            if os.path.isdir(_pal):
                shutil.copyfile(BT + '/release/BTDR_Example.tox', os.path.join(_pal, 'BTDR_Example_%s.tox' % _v))
            open(BT + '/out/example_log.txt', 'w', encoding='utf-8').write(('STATUS DONE' if not errs else 'STATUS ERR') + '\n' + '\n'.join(LOG))
        except Exception:
            open(BT + '/out/example_log.txt', 'w', encoding='utf-8').write('STATUS ERR\n' + traceback.format_exc())
    E.store('save', _save)
    for f in globals().get('EXAMPLE_SHOTS', ()):
        run("op('/project1/btdr_example/OUT').save(project.folder + '/btdr/out/example_f%d.jpg')" % f, delayFrames=f)
    run("op('/project1/btdr_example').fetch('save')()", delayFrames=150)
    open(BT + '/out/example_log.txt', 'w', encoding='utf-8').write('STATUS RUNNING')
except Exception:
    open(BT + '/out/example_log.txt', 'w', encoding='utf-8').write('STATUS ERR\n' + '\n'.join(LOG) + '\n' + traceback.format_exc())
