"""Render one built part on its own with a labelled 1 cm grid, so positions can
be read straight off the picture in weapon-frame metres (Y forward, Z up).
Used to find where the body's own magazine well is.

Usage: blender -b -P preview_body.py -- OUT.png GLB [GLB2 dy,dz ...]
"""
import bpy, sys, os, math
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
VIEW = "side"
if ARGS[0].startswith("view="):
    VIEW = ARGS.pop(0).split("=", 1)[1]     # side | bottom | top
OUT = ARGS[0]
ITEMS = []
for a in ARGS[1:]:
    p, _, off = a.partition("@")
    o = Vector([0, 0, 0]) if not off else Vector([float(x) for x in off.split(",")])
    ITEMS.append((p, o))

bpy.ops.wm.read_factory_settings(use_empty=True)
objs = []
for path, off in ITEMS:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in [x for x in bpy.data.objects if x not in before]:
        if o.type != 'MESH' or 'Icosphere' in o.name:
            bpy.data.objects.remove(o, do_unlink=True); continue
        o.parent = None
        o.matrix_world.translation = off
        objs.append(o)

mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for o in objs:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
print(f"BBOX X[{mn.x:+.3f},{mx.x:+.3f}] Y[{mn.y:+.3f},{mx.y:+.3f}] Z[{mn.z:+.3f},{mx.z:+.3f}]")

# 1 cm grid in the YZ plane, drawn behind the model as thin bars
grid = bpy.data.materials.new("grid"); grid.diffuse_color = (0.9, 0.25, 0.1, 1)
major = bpy.data.materials.new("major"); major.diffuse_color = (0.1, 0.8, 1.0, 1)
def bar(centre, size):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
    c = bpy.context.object
    c.scale = size
    return c
y0, y1 = math.floor(mn.y * 100) / 100, math.ceil(mx.y * 100) / 100
z0, z1 = math.floor(mn.z * 100) / 100, math.ceil(mx.z * 100) / 100
t = 0.0004
for i in range(int(round((y1 - y0) * 100)) + 1):
    y = y0 + i / 100
    c = bar((0.06, y, (z0 + z1) / 2), (0.001, t, (z1 - z0)))
    c.data.materials.append(major if abs(y * 100 - round(y * 100 / 5) * 5) < 1e-6 else grid)
for i in range(int(round((z1 - z0) * 100)) + 1):
    z = z0 + i / 100
    c = bar((0.06, (y0 + y1) / 2, z), (0.001, (y1 - y0), t))
    c.data.materials.append(major if abs(z * 100 - round(z * 100 / 5) * 5) < 1e-6 else grid)

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'MATERIAL'
scn.display.shading.show_cavity = True
scn.world = bpy.data.worlds.new("w"); scn.world.color = (0.05, 0.05, 0.06)
ctr = (mn + mx) / 2
# frame on the longer of the two visible axes, so a tall part (a magazine) is
# not cropped the way framing on Y alone would crop it
across = (mx.z - mn.z) if VIEW == "side" else (mx.x - mn.x)
span = max(mx.y - mn.y, across) + 0.02
scn.render.resolution_x = int(1200 * (mx.y - mn.y + 0.02) / span)
scn.render.resolution_y = int(1200 * (across + 0.02) / span)
cd = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cd)
scn.collection.objects.link(cam); scn.camera = cam
cd.type = 'ORTHO'; cd.ortho_scale = max(mx.y - mn.y, across) + 0.02; cd.clip_end = 10
if VIEW == "side":
    cam.location = Vector((ctr.x + 2, ctr.y, ctr.z))
    cam.rotation_euler = (math.radians(90), 0, math.radians(90))
else:
    sgn = -1 if VIEW == "bottom" else 1
    cam.location = Vector((ctr.x, ctr.y, ctr.z + sgn * 2))
    cam.rotation_euler = (0 if sgn > 0 else math.radians(180), 0, math.radians(90))
scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT, scn.render.resolution_x, "x", scn.render.resolution_y)
ppm = (mx.y - mn.y + 0.02) / scn.render.resolution_x        # metres per pixel
lo = mn.z - 0.01 if VIEW == "side" else mn.x - 0.01
print(f"MAP  y = {mn.y - 0.01:+.4f} + px*{ppm:.6f}"
      f"   {'z' if VIEW == 'side' else 'x'} = {lo + ppm * scn.render.resolution_y:+.4f} - py*{ppm:.6f}")
