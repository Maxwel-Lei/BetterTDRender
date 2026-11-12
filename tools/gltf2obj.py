# [BTDR:FILE.TOOL.GLTF2OBJ] glTF/GLB -> one OBJ per material (world space, all node instances merged) + separated PBR maps.
# Run: python gltf2obj.py <src.gltf|.glb> <out dir> <prefix>. Maps BTDR cannot place (2nd UV set, texture transform)
# are left out; transmission becomes opaque tinted glass; emissive_strength is applied (see convert_report.json).
import sys, os, json, io, numpy as np
from pygltflib import GLTF2
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
src, out, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
g = GLTF2().load(src)
base_dir = os.path.dirname(src)
blob = g.binary_blob() if src.endswith('.glb') else None
bufs = {}
def buf(i):
    if i not in bufs:
        b = g.buffers[i]
        bufs[i] = blob if (b.uri is None and blob is not None) else open(os.path.join(base_dir, b.uri), 'rb').read()
    return bufs[i]
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
def acc(i):
    a = g.accessors[i]; bv = g.bufferViews[a.bufferView]
    dt = np.dtype(CT[a.componentType]); n = NC[a.type]
    off = (bv.byteOffset or 0) + (a.byteOffset or 0)
    stride = bv.byteStride or dt.itemsize * n
    raw = buf(bv.buffer)
    if stride == dt.itemsize * n:
        arr = np.frombuffer(raw, dt, a.count * n, off).reshape(a.count, n)
    else:
        arr = np.stack([np.frombuffer(raw, dt, n, off + k * stride) for k in range(a.count)])
    arr = arr.astype(np.float64)
    if a.normalized and dt != np.float32:
        arr = arr / np.iinfo(dt).max
    return arr
def img(i):
    im = g.images[i]
    if im.uri:
        return Image.open(os.path.join(base_dir, im.uri))
    bv = g.bufferViews[im.bufferView]
    return Image.open(io.BytesIO(buf(bv.buffer)[(bv.byteOffset or 0):(bv.byteOffset or 0) + bv.byteLength]))
def tex_img(t):
    return img(g.textures[t.index].source) if t is not None else None
def local(n):
    if n.matrix: return np.array(n.matrix, dtype=np.float64).reshape(4, 4).T
    T = np.eye(4); R = np.eye(4); S = np.eye(4)
    if n.translation: T[:3, 3] = n.translation
    if n.rotation:
        x, y, z, w = n.rotation
        R[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    if n.scale: S[0, 0], S[1, 1], S[2, 2] = n.scale
    return T @ R @ S
geo = {}   # material index -> lists
def walk(ni, M):
    n = g.nodes[ni]; W = M @ local(n)
    if n.mesh is not None:
        for p in g.meshes[n.mesh].primitives:
            P = acc(p.attributes.POSITION); N = acc(p.attributes.NORMAL) if p.attributes.NORMAL is not None else None
            UV = acc(p.attributes.TEXCOORD_0) if p.attributes.TEXCOORD_0 is not None else np.zeros((len(P), 2))
            I = acc(p.indices).astype(np.int64).reshape(-1, 3) if p.indices is not None else np.arange(len(P)).reshape(-1, 3)
            Pw = (W[:3, :3] @ P.T).T + W[:3, 3]
            Nm = np.linalg.inv(W[:3, :3]).T
            Nw = (Nm @ N.T).T if N is not None else None
            if Nw is not None: Nw /= np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-12)
            if np.linalg.det(W[:3, :3]) < 0: I = I[:, ::-1]
            geo.setdefault(p.material, []).append((Pw, Nw, UV, I))
    for c in (n.children or []): walk(c, W)
scene = g.scenes[g.scene or 0]
for r in scene.nodes: walk(r, np.eye(4))
report = []
for mi, parts in geo.items():
    m = g.materials[mi] if mi is not None else None
    name = prefix + '_' + (m.name if m and m.name else 'mat%s' % mi).replace(' ', '_')
    with open(os.path.join(out, name + '.obj'), 'w') as f:
        f.write('# converted from %s (glTF, Y-up, metres)\n' % os.path.basename(src))
        o = 0; tris = 0
        for Pw, Nw, UV, I in parts:
            f.write(''.join('v %.6f %.6f %.6f\n' % tuple(v) for v in Pw))
            f.write(''.join('vt %.6f %.6f\n' % (u, 1.0 - v) for u, v in UV))      # glTF v is top-down
            if Nw is not None: f.write(''.join('vn %.6f %.6f %.6f\n' % tuple(v) for v in Nw))
            for a, b, c in I + o + 1:
                f.write(('f %d/%d/%d %d/%d/%d %d/%d/%d\n' % (a, a, a, b, b, b, c, c, c)) if Nw is not None else ('f %d/%d %d/%d %d/%d\n' % (a, a, b, b, c, c)))
            o += len(Pw); tris += len(I)
    maps = []; dropped = []
    pb = m.pbrMetallicRoughness if m else None
    # BTDR reads neither a second UV set nor KHR_texture_transform (tiling / offset): such a map would land on the
    # wrong texels (smudged AO, one stretched tile of a fabric normal map), so it is left out and listed in `dropped`
    def usable(t, kind):
        if t is None: return False
        if (getattr(t, 'texCoord', 0) or 0) != 0 or 'KHR_texture_transform' in (getattr(t, 'extensions', None) or {}):
            dropped.append(kind); return False
        return True
    if pb and usable(pb.baseColorTexture, 'basecolor'):
        tex_img(pb.baseColorTexture).convert('RGB').save(os.path.join(out, name + '_basecolor.png')); maps.append('basecolor')
    if pb and usable(pb.metallicRoughnessTexture, 'metallicroughness'):
        mr = np.asarray(tex_img(pb.metallicRoughnessTexture).convert('RGB'))
        Image.fromarray(mr[..., 1]).save(os.path.join(out, name + '_roughness.png'))
        Image.fromarray(mr[..., 2]).save(os.path.join(out, name + '_metallic.png')); maps += ['roughness', 'metallic']
    if m and usable(m.occlusionTexture, 'ao'):
        Image.fromarray(np.asarray(tex_img(m.occlusionTexture).convert('RGB'))[..., 0]).save(os.path.join(out, name + '_ao.png')); maps.append('ao')
    if m and usable(m.normalTexture, 'normal'):
        tex_img(m.normalTexture).convert('RGB').save(os.path.join(out, name + '_normal.png')); maps.append('normal')
    if m and usable(m.emissiveTexture, 'emissive'):
        tex_img(m.emissiveTexture).convert('RGB').save(os.path.join(out, name + '_emissive.png')); maps.append('emissive')
    allp = np.concatenate([p[0] for p in parts])
    ext = (m.extensions or {}) if m else {}
    base = list(pb.baseColorFactor) if pb and pb.baseColorFactor else None
    rough = pb.roughnessFactor if pb else None
    emis = list(m.emissiveFactor) if m and m.emissiveFactor else None
    note = None
    # KHR_materials_emissive_strength: HDR emission = emissiveFactor x strength (car lights, screens)
    if emis and 'KHR_materials_emissive_strength' in ext:
        k = ext['KHR_materials_emissive_strength'].get('emissiveStrength', 1.0)
        emis = [c * k for c in emis]
    # KHR_materials_transmission: BTDR has no transparency yet -> dark, smooth, opaque glass (looks like tinted
    # windows, still reflects through SSR / the environment)
    if 'KHR_materials_transmission' in ext:
        base, rough, note = [0.02, 0.022, 0.025, 1.0], 0.03, 'transmission -> opaque tinted glass'
    report.append(dict(name=name, tris=int(tris), maps=maps,
                       factors=dict(base=base, metal=pb.metallicFactor if pb else None, rough=rough, emissive=emis),
                       ext=list(ext.keys()), alpha=m.alphaMode if m else None, note=note, dropped=dropped,
                       bbox=[allp.min(0).round(3).tolist(), allp.max(0).round(3).tolist()]))
json.dump(report, open(os.path.join(out, 'convert_report.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps(report, ensure_ascii=False)[:1500])
