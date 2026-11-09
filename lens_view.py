"""Look THROUGH the scope's lens, the way the player does when aiming.

Every check this project has run on the optic casts rays inward from OUTSIDE the
model.  That finds holes in the shell, and our scope passes it (0.11%).  It says
nothing about what you see once the camera is at the eyepiece looking down the
bore, because a surface of revolution built to be seen from outside has its
backs to the axis - and with backface culling on, a backface is nothing at all.
"i can see transparent textures when i view the scope from the lens" is that
view, not the outside one.

So: put the camera on the optical axis at the ocular end, drop the glass (it is
transparent in game - `base\\materials\\glass_scope.mt` - so it cannot hide
anything behind it), leave backface culling ON, and render against a magenta
void.  Any magenta is something you will see straight through while aiming.

bl -b -P lens_view.py -- OUTPNG GLB[:chunkspec] [GLB ...]

  chunkspec  comma-separated chunk prefixes to SKIP, e.g. submesh_01,submesh_02
The axis is taken from the first glb's own bore: the median X,Z of its vertices
in the rearmost 10 mm, which is the eyepiece opening.
"""
import bpy, sys, os, math
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT, SPECS = A[0], A[1:]
VOID = (0.60, 0.02, 0.45, 1.0)


def load(spec):
    path, _, skip = spec.partition(":")
    skips = [s for s in skip.split(",") if s]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    out = []
    for o in [x for x in bpy.data.objects if x not in before]:
        drop = (o.type != 'MESH'
                or ('Icosphere' in o.name and len(o.data.vertices) == 42)
                or "_LOD_2" in o.name
                or any(o.name.startswith(s) for s in skips))
        if drop:
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        o.parent = None
        o.modifiers.clear()
        o.matrix_world.identity()
        out.append(o)
    return out


bpy.ops.wm.read_factory_settings(use_empty=True)
mat = bpy.data.materials.new("m")
mat.use_nodes = True
mat.use_backface_culling = True          # exactly what the engine does
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.45, 0.46, 0.48, 1)
b.inputs["Roughness"].default_value = 0.45
b.inputs["Metallic"].default_value = 0.0

objs = []
for s in SPECS:
    got = load(s)
    print(f"  {os.path.basename(s.split(':')[0]):44} {len(got)} chunk(s) "
          f"{[o.name for o in got]}")
    for o in got:
        o.data.materials.clear()
        o.data.materials.append(mat)
    objs += got
if not objs:
    raise SystemExit("nothing loaded")

vs = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
y0, y1 = min(v.y for v in vs), max(v.y for v in vs)
# the eyepiece opening: the middle of what is there in the rearmost 10 mm
rear = [v for v in vs if v.y <= y0 + 0.010]
cx = (min(v.x for v in rear) + max(v.x for v in rear)) / 2
cz = (min(v.z for v in rear) + max(v.z for v in rear)) / 2
print(f"  optic Y[{y0:+.4f},{y1:+.4f}]  eyepiece axis at X{cx:+.4f} Z{cz:+.4f}")

scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.samples = 96
scn.render.film_transparent = False
scn.view_settings.view_transform = 'Standard'
scn.render.resolution_x = scn.render.resolution_y = 900

if scn.world is None:            # read_factory_settings(use_empty=True) has none
    scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
nt = scn.world.node_tree
nt.nodes.clear()
bg = nt.nodes.new("ShaderNodeBackground")
bg.inputs[0].default_value = VOID
nt.links.new(nt.nodes.new("ShaderNodeOutputWorld").inputs["Surface"],
             bg.outputs["Background"])

# lights sit OUTSIDE the optic, so the bore is lit the way it is in game: only
# by what gets in.  A light inside would paint the inner walls and hide the
# very thing we are looking for.
for d in ((0.4, -0.5, 0.5), (-0.4, -0.3, 0.4), (0.0, 0.6, 0.5)):
    lt = bpy.data.lights.new("l", 'AREA')
    lt.energy, lt.size = 220, 0.5
    ob = bpy.data.objects.new("l", lt)
    scn.collection.objects.link(ob)
    ob.location = Vector((cx, (y0 + y1) / 2, cz)) + Vector(d)
    ob.rotation_euler = (Vector((cx, (y0 + y1) / 2, cz))
                         - ob.location).to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scn.collection.objects.link(cam)
scn.camera = cam
cam.data.lens = 85                       # the optic fills the frame, like ADS
cam.location = Vector((cx, y0 - 0.055, cz))
cam.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()

scn.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("wrote", OUT)
