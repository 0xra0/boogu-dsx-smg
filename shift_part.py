"""Rigidly translate a built part glb, in weapon space, without re-fitting it.

WHY (measured 2026-07-30):

`mag_placement.py` converts a design position in the WEAPON frame into the
offset `build_mag.py` wants by subtracting the rig's `mag_slot` position:

    OFFSET = (DES - SLOT) - DC

That assumes the magazine mesh is authored in `mag_std` bone-local space.  It is
not.  The magazine entity's own rig resolves `mag_std` to the identity -

    magazine       T=(-0.00355, +0.01413, -0.09347)  R=(0, .707, .707, 0)
    mag_std        T=(-0.00355, +0.09347, -0.01413)  R=identity   (child)
    world(mag_std) = T_magazine + R*T_mag_std = (0, 0, 0)

- so the magazine mesh is already in weapon space.  Proof, not algebra: render
the donor body glb and the donor magazine glb together with NO offset at all
(`preview_assembly.py`) and the Darra Pulsar comes out perfectly assembled, the
banana mag seated in its magwell.

So subtracting SLOT displaced our magazine by exactly -SLOT.  Measured against
the design position in assembly_v2.json, on all three axes:

    shipped mag centre  (-0.0034, +0.0756, -0.0678)
    design    centre    (+0.0000, -0.0200, -0.0600)
    error               (-0.0034, +0.0956, -0.0078)
    -SLOT               (-0.0034, +0.0956, -0.0078)   residual < 0.05 mm

In game that put the magazine ~9.6 cm forward of the pistol grip, hanging off a
flat underside with a visible gap - "slightly offset from the handle".

This script applies the correction as a pure translation of the finished part,
so nothing else about it changes: no re-fit, no re-decimation, no new topology,
identical triangle and vertex counts.  The part is rigidly skinned to a single
bone that sits at the identity, so moving the vertices moves the rendered
result 1:1 and the reload animation still drives it from wherever we put it.

Usage:  blender -b -P shift_part.py -- IN.glb OUT.glb dx,dy,dz
"""
import bpy, sys
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = A[0], A[1]
DELTA = Vector([float(x) for x in A[2].split(",")])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)


def bbox(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    return (Vector((min(v[i] for v in vs) for i in range(3))),
            Vector((max(v[i] for v in vs) for i in range(3))))


moved = 0
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        continue
    if 'Icosphere' in o.name and len(o.data.vertices) == 42:
        continue
    lo, hi = bbox(o)
    # express the world-space delta in the object's own frame, so the shift is
    # correct whatever transform the glTF importer hung on the node
    local = o.matrix_world.inverted().to_3x3() @ DELTA
    for v in o.data.vertices:
        v.co += local
    o.data.update()
    lo2, hi2 = bbox(o)
    print(f"  {o.name:22} v={len(o.data.vertices):6}  "
          f"({lo.x:+.4f},{lo.y:+.4f},{lo.z:+.4f})..({hi.x:+.4f},{hi.y:+.4f},{hi.z:+.4f})"
          f"  ->  ({lo2.x:+.4f},{lo2.y:+.4f},{lo2.z:+.4f})..({hi2.x:+.4f},{hi2.y:+.4f},{hi2.z:+.4f})")
    moved += 1

assert moved, "no mesh objects found in " + SRC
# export_tangents is not optional: `wkwin import` refuses a glb without TANGENT
# ("One or more geometry entries in GLTF do not contain Tangents data").
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_yup=True, export_apply=False,
                          export_skins=True, export_materials='EXPORT',
                          export_normals=True, export_tangents=True)
print(f"shifted {moved} object(s) by {tuple(round(x, 5) for x in DELTA)} -> {OUT}")
