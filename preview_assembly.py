"""Render a weapon body + its magazine exactly as the engine composes them, so a
placement bug can be SEEN instead of inferred from bbox algebra.

Both the body mesh and the magazine mesh are exported from CP77 in their own
bone-local space.  The magazine entity's root bone (`mag_std`) is attached to
the body rig's `mag_slot`, so:

    mag_in_weapon_space = MAGSLOT * mag_vertex

Calibration, not assumption: run this on the DONOR pair first.  The donor
magazine is known to sit correctly in the donor gun, so whichever MAGSLOT makes
the donor render look assembled is the right one, and the same one then shows
where OUR magazine actually lands.

Usage:  blender -b -P preview_assembly.py -- BODY.glb MAG.glb OUT.png [dx,dy,dz]
"""
import bpy, sys, math
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
BODY, MAG, OUT = A[0], A[1], A[2]
OFF = Vector([float(x) for x in A[3].split(",")]) if len(A) > 3 else Vector((0, 0, 0))

bpy.ops.wm.read_factory_settings(use_empty=True)


def load(path, colour, offset=Vector((0, 0, 0))):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    objs = []
    for o in new:
        if o.type != 'MESH':
            continue
        if 'Icosphere' in o.name and len(o.data.vertices) == 42:
            continue                      # origin marker the export scripts add
        o.parent = None
        o.matrix_world.translation = offset
        o.rotation_euler = (0, 0, 0)
        o.scale = (1, 1, 1)
        m = bpy.data.materials.new("m")
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs[0].default_value = colour
        o.data.materials.clear()
        o.data.materials.append(m)
        objs.append(o)
    for o in new:
        if o not in objs:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in objs:
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        print(f"   loaded {o.name:22} v={len(vs):6} "
              f"X[{min(v.x for v in vs):+.4f},{max(v.x for v in vs):+.4f}] "
              f"Y[{min(v.y for v in vs):+.4f},{max(v.y for v in vs):+.4f}] "
              f"Z[{min(v.z for v in vs):+.4f},{max(v.z for v in vs):+.4f}]")
    return objs


body = load(BODY, (0.55, 0.58, 0.50, 1))          # olive - the gun
mag = load(MAG, (0.90, 0.25, 0.15, 1), OFF)       # red   - the magazine

allo = body + mag
lo = Vector((1e9,) * 3)
hi = Vector((-1e9,) * 3)
for o in allo:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        lo = Vector((min(lo[i], w[i]) for i in range(3)))
        hi = Vector((max(hi[i], w[i]) for i in range(3)))
mid = (lo + hi) / 2
span = max(hi - lo)
print(f"assembly bbox  X[{lo.x:+.4f},{hi.x:+.4f}] Y[{lo.y:+.4f},{hi.y:+.4f}] Z[{lo.z:+.4f},{hi.z:+.4f}]")

# side-on orthographic view down -X: the axis a magazine offset shows up in
cam_d = bpy.data.cameras.new("c")
cam_d.type = 'ORTHO'
cam_d.ortho_scale = span * 1.15
cam = bpy.data.objects.new("c", cam_d)
bpy.context.scene.collection.objects.link(cam)
cam.location = mid + Vector((span * 2, 0, 0))
cam.rotation_euler = (math.pi / 2, 0, math.pi / 2)
bpy.context.scene.camera = cam

for v, e in ((Vector((1, -1, 1)), 3.0), (Vector((-1, 1, 0.5)), 1.5)):
    ld = bpy.data.lights.new("l", 'SUN')
    ld.energy = e
    lo_ = bpy.data.objects.new("l", ld)
    bpy.context.scene.collection.objects.link(lo_)
    lo_.rotation_euler = v.normalized().to_track_quat('-Z', 'Y').to_euler()

s = bpy.context.scene
s.render.engine = 'BLENDER_WORKBENCH'
s.render.resolution_x = 1400
s.render.resolution_y = 900
s.render.film_transparent = False
s.display.shading.light = 'STUDIO'
s.display.shading.color_type = 'MATERIAL'
s.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("wrote", OUT)
