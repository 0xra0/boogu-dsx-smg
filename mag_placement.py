"""Work out the build_mag.py SCALE/OFFSET that reproduce the placement in
assembly_v2.json - i.e. the magazine exactly where the assembled custom model
puts it, rather than where the donor's magazine happened to sit.

assemble.py places a part in the WEAPON frame with matrix_world = T @ R @ S
(translate / axis-remap / uniform scale).  build_mag.py instead works in the
part BONE's local frame and lands the fitted centre at `DC + OFFSET`, scaled by
`max(DS)/max(MS) * SCALE`.  The two frames differ by the rig's slot position:

    weapon frame = bone-local + SLOT

so, with `d` = the design scale and `DES` = the design bbox centre,

    SCALE  = d * max(MS) / max(DS)
    OFFSET = (DES - SLOT) - DC

Everything on the right is measured here, nothing is assumed.

*** BUT SLOT IS NOT THE SAME FOR EVERY PART - see SLOTS below. ***

Usage: bl -b -P mag_placement.py -- assembly_v2.json PARTNAME DONOR_GLB [SLOT_XYZ]
"""
import bpy, sys, json
from mathutils import Vector, Matrix

A = sys.argv[sys.argv.index("--") + 1:]
CFG, PART, DONOR = A[0], A[1], A[2]
# Rig slot in the Blender/mesh frame (Y forward, Z up), read from the donor .rig.
# NOTE the .rig itself stores Y=up/Z=forward - these are already converted.
#
# THE MAGAZINE USES mag_slot LIKE EVERY OTHER PART.  A previous version set this
# to (0,0,0) on the theory that the magazine mesh is authored in weapon space,
# and that was WRONG - it is what put the magazine 9.56 cm too far back in game
# through four separate builds while every render here looked correct.
#
# What the rig actually says.  In the magazine PART's own rig:
#
#     magazine   T=(-0.00355, +0.01413, -0.09347)  R=(0, .707, .707, 0)
#     mag_std    T=(-0.00355, +0.09347, -0.01413)  R=identity   (child)
#     world      = T_magazine + R*T_mag_std = (0, 0, 0)
#
# That zero is real but it means the bone sits at the PART's origin - it says
# nothing about where the part sits on the weapon.  The part entity is then
# attached at the weapon's Magazine slot, i.e. `mag_slot` on the weapon rig,
# weapon-space (0.0034, -0.0956, 0.0078).  So world = mag_slot * part_vertex,
# exactly like the scope and muzzle.
#
# Check it against the donor rather than trusting either story: the donor's
# magazine mesh has bbox centre (-0.0036, +0.0405, -0.0935), and
#     (-0.0036, +0.0405, -0.0935) + mag_slot = (-0.0002, -0.0551, -0.0857)
# which is the pistol grip - where a Darra Pulsar actually feeds.  Without the
# slot it would sit at Y=+0.0405, straddling the trigger at Y=+0.0553.
#
# The old "proof" - render the donor body glb and donor magazine glb together
# with no offset and it looks assembled - is a FALSE POSITIVE.  It looks
# plausible because a magazine 9.56 cm forward still lands under the receiver.
# Do not re-derive this from a Blender preview; the rig is the authority.
SLOTS = {"mag": Vector((0.0, 0.0756, 0.0068)),          # mag_slot in OUR rig
         "scope": Vector((0.0, 0.1120, 0.0896)),        # scope_slot
         "muzzle": Vector((0.0, 0.2971, 0.0307))}       # muzzle_slot
SLOT = Vector([float(x) for x in A[3].split(",")]) if len(A) > 3 else SLOTS[PART]

AX = {"+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0)), "+Y": Vector((0, 1, 0)),
      "-Y": Vector((0, -1, 0)), "+Z": Vector((0, 0, 1)), "-Z": Vector((0, 0, -1))}


def import_glb(p):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=p)
    return [o for o in bpy.data.objects if o not in before]


def strip(objs):
    ms, ar = [], []
    for o in objs:
        if o.type == 'MESH' and 'Icosphere' in o.name and len(o.data.vertices) == 42:
            bpy.data.objects.remove(o, do_unlink=True); continue
        if o.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(o, do_unlink=True); continue
        if o.type == 'MESH': ms.append(o)
        elif o.type == 'ARMATURE': ar.append(o)
    return list(dict.fromkeys(ms)), list(dict.fromkeys(ar))


def join(ms, name):
    for o in bpy.data.objects: o.select_set(False)
    for m in ms:
        m.parent = None; m.modifiers.clear(); m.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    for vg in list(o.vertex_groups): o.vertex_groups.remove(vg)
    return o


def bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return mn, mx, (mn + mx) / 2, (mx - mn)


spec = next(p for p in json.load(open(CFG))["parts"] if p["name"] == PART)
axes, d, t = spec["axes"], spec["scale"], Vector(spec.get("translate", [0, 0, 0]))

bpy.ops.wm.read_factory_settings(use_empty=True)

# --- donor part: bone-local bbox of its mesh = what build_mag.py fits into ----
dm, da = strip(import_glb(DONOR))
da[0].matrix_world = Matrix.Identity(4)
bpy.context.view_layer.update()
BONE = da[0].data.bones[0].name
# build_mag.py fits to dtarg[0] - the FIRST donor mesh, i.e. LOD1 - not to the
# union, so measure the same thing or the derived scale is off by the LOD2 slack.
_, _, DC, DS = bbox(dm[0])
print(f"DONOR {BONE} [{dm[0].name}] of {[o.name for o in dm]}: "
      f"centre=({DC.x:+.4f},{DC.y:+.4f},{DC.z:+.4f}) "
      f"size=({DS.x:.4f},{DS.y:.4f},{DS.z:.4f}) max={max(DS):.4f}")
for o in dm: bpy.data.objects.remove(o, do_unlink=True)

# --- our source, oriented (no scale/offset yet) -------------------------------
ms, ar = strip(import_glb(spec["glb"]))
for a in ar: bpy.data.objects.remove(a, do_unlink=True)
mine = join(ms, "src")
ix, iy, iz = (AX[s] for s in axes)
R = Matrix(((ix.x, iy.x, iz.x, 0), (ix.y, iy.y, iz.y, 0), (ix.z, iy.z, iz.z, 0), (0, 0, 0, 1)))
mine.matrix_world = R
bpy.context.view_layer.update()
_, _, MC, MS = bbox(mine)
print(f"SOURCE oriented {axes}: centre=({MC.x:+.4f},{MC.y:+.4f},{MC.z:+.4f}) "
      f"size=({MS.x:.4f},{MS.y:.4f},{MS.z:.4f}) max={max(MS):.4f}")

# --- the design placement, exactly as assemble.py computes it -----------------
mine.matrix_world = Matrix.Translation(t) @ R @ Matrix.Diagonal((d, d, d, 1.0))
bpy.context.view_layer.update()
dmn, dmx, DES, DSZ = bbox(mine)
print(f"DESIGN scale={d} translate=({t.x:+.4f},{t.y:+.4f},{t.z:+.4f})")
print(f"  weapon-frame bbox X[{dmn.x:+.4f},{dmx.x:+.4f}] Y[{dmn.y:+.4f},{dmx.y:+.4f}] "
      f"Z[{dmn.z:+.4f},{dmx.z:+.4f}]")
print(f"  centre=({DES.x:+.4f},{DES.y:+.4f},{DES.z:+.4f}) size=({DSZ.x:.4f},{DSZ.y:.4f},{DSZ.z:.4f})")

target = DES - SLOT
scale = d * max(MS) / max(DS)
offset = target - DC
print(f"SLOT {PART} = ({SLOT.x:+.4f},{SLOT.y:+.4f},{SLOT.z:+.4f})")
print(f"  target bone-local centre = ({target.x:+.4f},{target.y:+.4f},{target.z:+.4f})")
print()
print(f"BUILD_MAG_ARGS  \"{','.join(axes)}\" <TARGET> {scale:.5f} "
      f"\"{offset.x:.5f},{offset.y:.5f},{offset.z:.5f}\"")
