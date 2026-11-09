"""Look down our built scope from the shooter's eye, the way the ADS camera does,
and from the side, with the donor's lens chunks drawn in.  Answers the question
that decides how the scope has to be rebuilt: is there a bore through our model,
or is the eyepiece end solid (which is what "aiming shows only the green texture"
would mean)?

Usage: bl -b -P preview_scope.py -- OUT_PREFIX OURS.glb DONOR.glb
"""
import bpy, sys, os, math
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
OUT, OURS, DONOR = A[0], A[1], A[2]

bpy.ops.wm.read_factory_settings(use_empty=True)

def imp(path, keep=None, colour=None, name=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    out = []
    for o in [x for x in bpy.data.objects if x not in before]:
        if o.type != 'MESH':
            if o.type == 'ARMATURE':
                o.matrix_world.identity()
            continue
        if 'Icosphere' in o.name:      # glTF importer placeholder, 42 verts
            bpy.data.objects.remove(o, do_unlink=True); continue
        if keep is not None and not any(k in o.name for k in keep):
            bpy.data.objects.remove(o, do_unlink=True); continue
        o.data.materials.clear()
        if colour:
            m = bpy.data.materials.new(name or "c"); m.diffuse_color = colour
            o.data.materials.append(m)
        out.append(o)
    return out

ours = imp(OURS, colour=(0.55, 0.58, 0.6, 1), name="ours")
# donor: submesh_01 = highlight_blocker, submesh_02 = glass (the ocular lens)
glass = imp(DONOR, keep=("submesh_02",), colour=(0.1, 0.9, 0.3, 1), name="glass")

def bbox(objs):
    mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return mn, mx

for label, objs in (("ours", ours), ("glass", glass)):
    mn, mx = bbox(objs)
    print(f"{label:6s} X[{mn.x:+.4f},{mx.x:+.4f}] Y[{mn.y:+.4f},{mx.y:+.4f}] Z[{mn.z:+.4f},{mx.z:+.4f}]")

gmn, gmx = bbox(glass)
eye = Vector(((gmn.x + gmx.x) / 2, gmn.y - 0.03, (gmn.z + gmx.z) / 2))   # behind the ocular
print("EYE", tuple(round(v, 4) for v in eye))

scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'MATERIAL'
scn.world = bpy.data.worlds.new("w"); scn.world.color = (0.02, 0.02, 0.03)
cd = bpy.data.cameras.new("c"); cam = bpy.data.objects.new("c", cd)
scn.collection.objects.link(cam); scn.camera = cam

amn, amx = bbox(ours + glass)
ctr = (amn + amx) / 2

VIEWS = {
    # down the barrel from behind the ocular - this is what ADS sees
    "eye":  (eye, (math.radians(90), 0, 0), 'PERSP'),
    "side": (Vector((ctr.x + 1, ctr.y, ctr.z)), (math.radians(90), 0, math.radians(90)), 'ORTHO'),
    "top":  (Vector((ctr.x, ctr.y, ctr.z + 1)), (0, 0, math.radians(90)), 'ORTHO'),
}
for name, (loc, rot, kind) in VIEWS.items():
    cam.location = loc; cam.rotation_euler = rot
    cd.type = kind
    cd.ortho_scale = max(amx - amn) * 1.15
    cd.lens = 35
    cd.clip_start = 0.001; cd.clip_end = 10
    scn.render.resolution_x = scn.render.resolution_y = 700
    scn.render.filepath = f"{OUT}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scn.render.filepath)
