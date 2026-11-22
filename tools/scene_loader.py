# [BTDR:FILE.TOOL.SCENELOADER] scene_loader.py — load a model folder converted by tools/gltf2obj.py into a Base COMP:
# one Geometry COMP (File In SOP) + one PBR MAT (File In TOPs) per material, using convert_report.json.
# A file <part>_alpha.png next to the maps turns on the PBR MAT's Alpha Test with it as the Alpha Map (glTF MASK
# materials: gltf2obj keeps RGB only). Used by tools/scene_shots.py; the models are not part of the repository.
# Usage (inside TD): exec(open(BT + '/tools/scene_loader.py', encoding='utf-8').read()); geos = load_scene(parent, folder, ...)
import os, json


def load_scene(parent, folder, prefix, scale=1.0, offset=(0.0, 0.0, 0.0), ry=0.0, skip=(), maxtex=None):
    """Returns {part name: Geometry COMP}. folder holds <prefix>_<part>.obj, its maps and convert_report.json."""
    rep = json.load(open(folder + '/convert_report.json', encoding='utf-8'))
    out = {}
    for k, r in enumerate(rep):
        name = r['name']
        if any(s in name for s in skip):
            continue
        tag = '%s_%d' % (prefix, k)
        m = parent.create(pbrMAT, 'mat_' + tag)
        m.nodeX, m.nodeY = -400, -k * 150
        f = r['factors']

        def tmap(kind):
            p = folder + '/%s_%s.png' % (name, kind)
            if not os.path.exists(p):
                return None
            t = parent.create(moviefileinTOP, 'tex_%s_%s' % (tag, kind))
            t.par.file = p
            t.nodeX, t.nodeY = -700 - 150 * ['basecolor', 'roughness', 'metallic', 'ao', 'normal', 'emissive', 'alpha'].index(kind), -k * 150
            if maxtex:
                t.par.outputresolution = 'custom'
                t.par.resolutionw = t.par.resolutionh = maxtex
            return t
        bc = tmap('basecolor')
        if bc is not None: m.par.basecolormap = bc
        if f.get('base'): m.par.basecolorr, m.par.basecolorg, m.par.basecolorb = f['base'][:3]
        rm = tmap('roughness')
        if rm is not None: m.par.roughnessmap = rm
        m.par.roughness = f['rough'] if f.get('rough') is not None else 1.0
        mm = tmap('metallic')
        if mm is not None: m.par.metallicmap = mm
        m.par.metallic = f['metal'] if f.get('metal') is not None else (1.0 if mm is not None else 0.0)
        ao = tmap('ao')
        if ao is not None: m.par.ambientocclusionmap = ao
        nm = tmap('normal')
        if nm is not None:
            m.par.normalmap = nm; m.par.bumpscale = 1.0
        em = tmap('emissive')
        if em is not None:
            m.par.emitmap = em
            m.par.emitr, m.par.emitg, m.par.emitb = (f.get('emissive') or [1, 1, 1])[:3]
        am = tmap('alpha')
        if am is not None:                     # glTF alphaMode MASK: cut-out (leaves, chains), cutoff 0.5
            m.par.alphamap = am; m.par.alphatest = True; m.par.alphathreshold = 0.5
        g = parent.create(geometryCOMP, 'geo_' + tag)
        for c in list(g.children):
            c.destroy()
        s = g.create(fileinSOP, 'obj'); s.par.file = folder + '/%s.obj' % name
        s.render = True; s.display = True
        g.par.material = m
        g.par.scale = scale
        g.par.tx, g.par.ty, g.par.tz = offset
        g.par.ry = ry
        g.nodeX, g.nodeY = 0, -k * 150
        out[name] = g
    return out
