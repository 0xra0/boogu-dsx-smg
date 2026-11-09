#!/usr/bin/env python
"""Turn Trellis2's 1.5-2M face GLBs into game-budget assets, textures intact.

Why not just decimate: Trellis2's UV atlas is made of thousands of tiny charts.
A texture-preserving decimator has to lock every chart boundary, so it stalls at
~400k faces; letting it cross the seams instead reaches the budget but tears the
mesh into ~6700 disconnected shards. Either way the atlas is the blocker, so the
atlas gets rebuilt:

  1. drop connected components below MIN_COMPONENT faces (floating specks)
  2. plain quadric decimation -- no texture term, so topology stays connected
  3. xatlas re-unwrap of the decimated mesh
  4. re-bake baseColor + metallicRoughness from the original high-poly by
     nearest-surface-vertex lookup, normal-checked so thin walls don't sample
     through to the far side
  5. flood-fill the atlas background so bilinear filtering can't suck in voids

Rasterization reuses the node pack's own UV rasterizer (nvdiffrast is a no-op
stub on ROCm -- see the repo's uv_rasterizer docstring).
"""
import os
import shutil
import sys
import tempfile

import numpy as np
import pymeshlab as ml
import torch
import trimesh
import xatlas
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

sys.path.insert(0, "/mnt/sata/ComfyUI/custom_nodes/ComfyUI-Trellis2-GGUF")
from trellis2_gguf.utils.uv_rasterizer import interpolate_uv, rasterize_uv

SRC = "/mnt/ssd/Downloads"
DST = "/mnt/ssd/Downloads/weapon_set"
MIN_COMPONENT = 50   # faces
TEX = 2048           # re-baked atlas size (was 4096 for a 1.5M-face mesh)
KNN = 8              # candidates per texel for the normal-checked lookup
NRM_SS = 2           # normal map supersampling factor (baked at NRM_SS*TEX)

PARTS = {
    "Trellis2Mesh_GGUF_00007_": ("weapon_body", 60_000),
    "Trellis2Mesh_GGUF_00005_": ("weapon_scope", 45_000),
    "Trellis2Mesh_GGUF_00006_": ("weapon_barrel", 45_000),
    "Trellis2Mesh_GGUF_00004_": ("weapon_magazine", 30_000),
}

# one-off re-run of a single regenerated part: <stem> <name> <target faces>
if len(sys.argv) == 4:
    PARTS = {sys.argv[1]: (sys.argv[2], int(sys.argv[3]))}


def sample(img, uv):
    """Bilinear-ish (nearest) sample of a PIL texture at per-vertex UVs."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]
    x = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(np.int32)
    y = np.clip((1.0 - uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(np.int32)
    return a[y, x]


def unit(a):
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    return a / np.where(n < 1e-20, 1.0, n)


def vertex_tangents(V, F, uv, VN):
    """Per-vertex tangent frame, matching the basis a glTF viewer will derive.

    trimesh writes no TANGENT accessor, so by spec the viewer recomputes the
    frame with MikkTSpace from the *exported* UVs -- and trimesh flips v on
    export. Build tangents from (u, 1-v) or every bake lights inside-out.

    Returns (tangent, w) where w is the bitangent sign; xatlas emits charts of
    both windings, so assuming w = +1 inverts green over roughly half the atlas.
    """
    uvx = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]])
    e1, e2 = V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]
    d1, d2 = uvx[F[:, 1]] - uvx[F[:, 0]], uvx[F[:, 2]] - uvx[F[:, 0]]
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)[:, None]
    tf = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r
    bf = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r

    T, B = np.zeros_like(V), np.zeros_like(V)
    for i in range(3):
        np.add.at(T, F[:, i], tf)
        np.add.at(B, F[:, i], bf)
    T = unit(T - VN * (T * VN).sum(1, keepdims=True))   # Gram-Schmidt
    w = np.sign((np.cross(VN, T) * B).sum(1))
    w[w == 0] = 1.0
    return T, w


def pick_nearest(tree, hi_n, P, N, chunk=2_000_000):
    """Nearest high-poly vertex per query point, ignoring the far side of a wall.

    Chunked: the normal check materialises a (points, KNN, 3) array, which at
    the supersampled normal-map resolution would be ~2 GB in one go.
    """
    out = np.empty(len(P), np.int64)
    for s in range(0, len(P), chunk):
        e = min(s + chunk, len(P))
        _, idx = tree.query(P[s:e], k=KNN, workers=-1)
        agree = np.einsum("ijk,ik->ij", hi_n[idx], N[s:e]) > 0.0
        first = np.where(agree.any(1), agree.argmax(1), 0)
        out[s:e] = idx[np.arange(len(idx)), first]
    return out


def decimate(V, F, target):
    """Speck removal + plain quadric decimation, via a temp PLY hop.

    The weld is load-bearing. Trellis2's GLB stores the mesh already split at
    every UV seam (~28% of its vertices are coincident duplicates), so MeshLab
    would otherwise see a surface pre-cracked into thousands of charts and
    decimate each shard independently -- the cracks then open up visibly.
    """
    U, inv = np.unique(np.round(V, 6), axis=0, return_inverse=True)
    V, F = U, inv[F]
    tmp = tempfile.mkdtemp(prefix="retopo_")
    try:
        p = os.path.join(tmp, "in.ply")
        trimesh.Trimesh(V, F, process=False).export(p)
        ms = ml.MeshSet()
        ms.load_new_mesh(p)
        ms.meshing_remove_connected_component_by_face_number(
            mincomponentsize=MIN_COMPONENT, removeunref=True)
        despecked = ms.current_mesh().face_number()
        for _ in range(8):
            cur = ms.current_mesh().face_number()
            if cur <= target:
                break
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target, qualitythr=0.3,
                preserveboundary=False, preservenormal=True,
                preservetopology=False, optimalplacement=True,
                planarquadric=True, autoclean=True)
            if ms.current_mesh().face_number() == cur:
                break
        cm = ms.current_mesh()
        return cm.vertex_matrix().copy(), cm.face_matrix().copy(), despecked
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def bake(hi, hi_attrs, V, F, uv, size):
    """Rasterize the new atlas and pull each texel's value off the high-poly.

    Nearest *vertex* is texel-accurate here -- the source has ~1M vertices, so
    vertex spacing is finer than a texel. The normal check matters more: a bare
    nearest-point query jumps across thin walls (receiver window, vent slots).
    """
    # rasterize_uv puts row 0 at v=0 (glTF's v-down). trimesh keeps UVs v-up
    # and flips them on GLB export, so bake against the flipped v or the atlas
    # comes out vertically mirrored.
    uv_r = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]]).astype(np.float32)
    fid, bary = rasterize_uv(torch.as_tensor(uv_r, dtype=torch.float32),
                             torch.as_tensor(F, dtype=torch.int64), size)
    Ft = torch.as_tensor(F, dtype=torch.int64)
    pos = interpolate_uv(torch.as_tensor(V, dtype=torch.float32), fid, bary, Ft).numpy()

    lo_vn = trimesh.Trimesh(V, F, process=False).vertex_normals
    nrm = interpolate_uv(torch.as_tensor(lo_vn, dtype=torch.float32), fid, bary, Ft).numpy()

    mask = (fid > 0).numpy()
    P, N = pos[mask], nrm[mask]

    pick = pick_nearest(cKDTree(hi.vertices), hi.vertex_normals, P, N)

    # flood the background from the nearest filled texel (seam padding)
    _, (yi, xi) = distance_transform_edt(~mask, return_indices=True)

    out = []
    for attr in hi_attrs:
        img = np.zeros((size, size, 3), np.float32)
        img[mask] = attr[pick]
        out.append(Image.fromarray(img[yi, xi].round().clip(0, 255).astype(np.uint8)))
    return out, mask.mean()


def bake_normal(hi, V, F, uv, size, ss=NRM_SS):
    """Tangent-space normal map, so detail the decimator flattens survives as shading.

    The knurled muzzle ring is geometry in the high-poly and it is the first
    thing to go at a 45k budget -- baking it into normals is the only way to
    keep it without spending faces.

    Rasterized at ss*size and box-filtered down: the knurl pitch is only ~7
    texels at 2048, so point-sampling the high-poly normal field turns the
    teeth into aliased noise rather than a repeating pattern.
    """
    hs = size * ss
    uv_r = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]]).astype(np.float32)
    Ft = torch.as_tensor(F, dtype=torch.int64)
    fid, bary = rasterize_uv(torch.as_tensor(uv_r), Ft, hs)

    lo_vn = trimesh.Trimesh(V, F, process=False).vertex_normals
    T_v, w_v = vertex_tangents(V, F, uv, lo_vn)

    def interp(a):
        return interpolate_uv(torch.as_tensor(np.ascontiguousarray(a), dtype=torch.float32),
                              fid, bary, Ft).numpy()

    mask = (fid > 0).numpy()
    P, N = interp(V)[mask], interp(lo_vn)[mask]
    T, W = interp(T_v)[mask], interp(w_v[:, None])[mask][:, 0]

    hn = hi.vertex_normals[pick_nearest(cKDTree(hi.vertices), hi.vertex_normals, P, N)]

    n = unit(N)
    t = unit(T - n * (T * n).sum(1, keepdims=True))
    b = np.cross(n, t) * np.sign(W)[:, None]
    ts = unit(np.stack([(hn * t).sum(1), (hn * b).sum(1), (hn * n).sum(1)], 1))

    img = np.zeros((hs, hs, 3), np.float32)
    img[~mask] = (0.0, 0.0, 1.0)
    img[mask] = ts
    _, (yi, xi) = distance_transform_edt(~mask, return_indices=True)
    img = img[yi, xi]

    # box-filter to the output size, then renormalise -- averaging unit vectors
    # shortens them, and a short normal reads as a flat spot.
    img = unit(img.reshape(size, ss, size, ss, 3).mean((1, 3)))
    return (Image.fromarray(((img * 0.5 + 0.5) * 255).round().clip(0, 255).astype(np.uint8)),
            (ts[:, 2] < 0).mean())


os.makedirs(DST, exist_ok=True)
print(f"{'part':16s} {'faces in':>10s} {'-specks':>10s} {'faces out':>9s} "
      f"{'verts':>9s} {'atlas fill':>10s} {'n.z<0':>8s} {'MB':>6s}")

for stem, (part, target) in PARTS.items():
    hi = list(trimesh.load(os.path.join(SRC, stem + ".glb"),
                           process=False).geometry.values())[0]
    mat = hi.visual.material
    uv_hi = np.asarray(hi.visual.uv)
    hi_attrs = [sample(mat.baseColorTexture, uv_hi),
                sample(mat.metallicRoughnessTexture, uv_hi)]

    V, F, despecked = decimate(np.asarray(hi.vertices), np.asarray(hi.faces), target)
    vmap, idx, uv = xatlas.parametrize(V, F)
    V2, F2 = V[vmap], idx.astype(np.int64)

    (base, mrough), fill = bake(hi, hi_attrs, V2, F2, uv, TEX)
    normal, behind = bake_normal(hi, V2, F2, uv, TEX)

    out = trimesh.Trimesh(V2, F2, process=False)
    out.visual = trimesh.visual.TextureVisuals(
        uv=uv, material=trimesh.visual.material.PBRMaterial(
            baseColorTexture=base, metallicRoughnessTexture=mrough,
            normalTexture=normal, metallicFactor=1.0, roughnessFactor=1.0))
    dst = os.path.join(DST, part + ".glb")
    out.export(dst)

    print(f"{part:16s} {len(hi.faces):>10,} {despecked:>10,} {len(F2):>9,} "
          f"{len(V2):>9,} {fill*100:>9.1f}% {behind*100:>7.2f}% "
          f"{os.path.getsize(dst)/1e6:>6.1f}", flush=True)
