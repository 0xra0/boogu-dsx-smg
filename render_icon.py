"""Render the assembled weapon on a transparent background for the inventory
icon.  Rendered at 4x and downscaled by build_icon.py for clean edges.

Usage: blender -b -P render_icon.py -- OUT.png [WIDTH HEIGHT]
"""
import bpy, sys, os, math
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
W = int(ARGS[1]) if len(ARGS) > 1 else 1280
H = int(ARGS[2]) if len(ARGS) > 2 else 640

"""build_v3 holds the parts that have been reworked since build_v2 (the shifted
magazines, the bored scope, the shadow proxies); anything untouched, like the
body, is still only in build_v2.  Prefer v3, fall back to v2, so the icon always
renders the geometry that is actually shipped."""
def BUILD_glb(name):
    for d in ("/mnt/sata/weapon_mod/build_v3", "/mnt/sata/weapon_mod/build_v2"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise SystemExit(f"no glb named {name} in build_v3 or build_v2")


BUILD = "/mnt/sata/weapon_mod/build_v3"
# The magazine IS drawn at mag_slot, and this line was right the first time.
# It was removed on 2026-07-30 as a "compensation" for a magazine believed to be
# shipped 9.56 cm too far forward.  That reading was backwards: the icon was
# correct precisely BECAUSE it applied the slot, which is what the game does when
# it attaches the magazine part entity.  Taking it out made the icon agree with
# the (wrong) preview and disagree with the game - and the user reporting exactly
# that, "in inventory shown correct, in game shown very shitty", is what finally
# pinned the bug down.  See mag_placement.py for the rig derivation.
MAG_SLOT = Vector((0.0, 0.0756, 0.0068))
PARTS = [("body", BUILD_glb("weaponset_smg.glb"), Vector((0, 0, 0))),
         ("mag",  BUILD_glb("weaponset_mag.glb"), MAG_SLOT)]

bpy.ops.wm.read_factory_settings(use_empty=True)
objs = []
for name, path, slot in PARTS:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in [x for x in bpy.data.objects if x not in before]:
        if o.type != 'MESH' or 'Icosphere' in o.name:
            bpy.data.objects.remove(o, do_unlink=True); continue
        o.parent = None
        o.matrix_world.translation = slot
        objs.append(o)

mn = Vector((1e9,)*3); mx = Vector((-1e9,)*3)
for o in objs:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
ctr = (mn + mx) / 2

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'TEXTURE'
scn.display.shading.show_cavity = True
scn.render.film_transparent = True
scn.render.image_settings.file_format = 'PNG'
scn.render.image_settings.color_mode = 'RGBA'
scn.render.resolution_x = W; scn.render.resolution_y = H

cd = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cd)
scn.collection.objects.link(cam); scn.camera = cam
cd.type = 'ORTHO'
# fit the weapon into the icon's aspect ratio with a small margin
span_y = (mx.y - mn.y); span_z = (mx.z - mn.z)
cd.ortho_scale = max(span_y, span_z * W / H) * 1.06
cd.clip_end = 100
cam.location = ctr + Vector((3, 0, 0))
cam.rotation_euler = (math.radians(90), 0, math.radians(90))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT, W, "x", H)
