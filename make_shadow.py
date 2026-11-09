"""Build a low-poly shadow proxy from one of our part glbs.

WHY (measured 2026-07-30): our part .app files kept the DONOR's `_shadow.mesh`
components alongside our own geometry, and those proxies never moved.  Measured
in weapon frame:

    donor mag shadow proxy   Y[-0.0223,+0.1040]  Z[-0.1890,+0.0052]
    our magazine (shipped)   Y[-0.0675,+0.0275]  Z[-0.1402,+0.0201]

- a magazine-shaped silhouette 6.1 cm forward and 5 cm below the magazine that
actually exists.  They are `isShadowMesh: 1` so they never draw in the main
pass, but they cast the shadow, so the weapon threw a detached magazine shadow.

The donor proxy is skinned to the same single `mag_std` bone as our magazine, so
a decimated copy of our own magazine drops straight in.

Usage:  blender -b -P make_shadow.py -- IN.glb OUT.glb TARGET_TRIS
"""
import bpy, sys, bmesh
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = A[0], A[1]
TARGET = int(A[2]) if len(A) > 2 else 250

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)


def bbox(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    return (Vector((min(v[i] for v in vs) for i in range(3))),
            Vector((max(v[i] for v in vs) for i in range(3))))


kept = 0
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        continue
    if 'Icosphere' in o.name and len(o.data.vertices) == 42:
        bpy.data.objects.remove(o, do_unlink=True)
        continue

    n0 = len(o.data.polygons)

    # A collapse DECIMATE cannot get near the target here: welded, the part is
    # still ~2500 open edges and the collapser refuses non-manifold boundaries,
    # so it stalls at ~72% (15852 -> 11422 for the magazine).  A convex hull is
    # both the right shape for this job and immune to that - the parts are
    # near-convex boxes and a shadow only needs the silhouette - and it comes
    # out closed and manifold, which decimates properly afterwards.
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    hull = bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=hull.get('geom_interior', []), context='VERTS')
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()

    if len(o.data.polygons) > TARGET:
        md = o.modifiers.new("dec", 'DECIMATE')
        md.ratio = TARGET / len(o.data.polygons)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="dec")
    lo, hi = bbox(o)
    print(f"  {o.name:22} {n0} -> {len(o.data.polygons)} tris, {len(o.data.vertices)} verts  "
          f"X[{lo.x:+.4f},{hi.x:+.4f}] Y[{lo.y:+.4f},{hi.y:+.4f}] Z[{lo.z:+.4f},{hi.z:+.4f}]")
    kept += 1

assert kept == 1, f"expected one mesh in {SRC}, found {kept}"
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_yup=True, export_apply=False,
                          export_skins=True, export_materials='EXPORT',
                          export_normals=True, export_tangents=True)
print("wrote", OUT)
