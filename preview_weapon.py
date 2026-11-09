"""Render the assembled weapon exactly as the game builds it: our body mesh in
the weapon frame, plus each attached part placed at its rig slot.

Slot positions come from the donor rig (w_smg__darra_pulsar__base1.rig), which
stores them Y-up/Z-forward; here they are converted to the Blender frame the
meshes were built in (Y forward, Z up).  Part meshes are bone-local, so the slot
translation (plus any tuning offset) is all that positions them.

Usage: blender -b -P preview_weapon.py -- OUTDIR [part=dx,dy,dz ...]
       e.g. ... -- work/mag mag=0,0.06,0.02
"""
import bpy, sys, os, math, json
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUTDIR = ARGS[0]
OFFSETS = {}
for a in ARGS[1:]:
    k, v = a.split("=")
    OFFSETS[k] = Vector([float(x) for x in v.split(",")])

BUILD = "/mnt/sata/weapon_mod/build_v2"
# rig slots, converted rig(X, Y=up, Z=fwd) -> blender(X, Y=fwd, Z=up)
SLOTS = {
    "mag":    Vector((0.0034, -0.0956, 0.0078)),
    "scope":  Vector((0.0,     0.1120, 0.0896)),
    "muzzle": Vector((0.0,     0.2971, 0.0307)),
}
PARTS = [("body", f"{BUILD}/weaponset_smg.glb", Vector((0, 0, 0))),
         ("mag",  f"{BUILD}/weaponset_mag.glb", SLOTS["mag"])]
for name, path, slot in [("scope", f"{BUILD}/weaponset_scope.glb", SLOTS["scope"]),
                         ("muzzle", f"{BUILD}/weaponset_muzzle.glb", SLOTS["muzzle"])]:
    if os.path.exists(path):
        PARTS.append((name, path, slot))

bpy.ops.wm.read_factory_settings(use_empty=True)
objs = []
for name, path, slot in PARTS:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.type != 'MESH' or 'Icosphere' in o.name:
            bpy.data.objects.remove(o, do_unlink=True); continue
        o.name = f"{name}_{o.name}"
        o.parent = None
        o.matrix_world.translation = slot + OFFSETS.get(name, Vector((0, 0, 0)))
        objs.append(o)
    vs = [o.matrix_world @ v.co for o in objs if o.name.startswith(name) for v in o.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    print(f"PART {name:7s} weapon-frame bbox X[{mn.x:+.3f},{mx.x:+.3f}] "
          f"Y[{mn.y:+.3f},{mx.y:+.3f}] Z[{mn.z:+.3f},{mx.z:+.3f}]")

mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
for o in objs:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
ctr = (mn + mx) / 2; diag = (mx - mn).length

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'TEXTURE'
scn.display.shading.show_cavity = True
scn.world = bpy.data.worlds.new("w"); scn.world.color = (0.05, 0.05, 0.06)
scn.render.resolution_x = 900; scn.render.resolution_y = 520
os.makedirs(OUTDIR, exist_ok=True)
R = math.radians

def render(name, eye, euler, ortho=True):
    cd = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cd)
    scn.collection.objects.link(cam); scn.camera = cam
    cd.type = 'ORTHO'; cd.ortho_scale = diag * 1.05; cd.clip_end = diag * 20
    cam.location = ctr + Vector(eye) * diag * 2
    cam.rotation_euler = euler
    scn.render.filepath = os.path.join(OUTDIR, name)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)

render("side.png",   (1, 0, 0),        (R(90), 0, R(90)))
render("bottom.png", (0, 0, -1),       (R(180), 0, 0))
render("q34.png",    (0.8, -0.8, 0.5), (R(60), 0, R(46)))
print("RENDERED to", OUTDIR)
