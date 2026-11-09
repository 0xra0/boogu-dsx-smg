"""Config-driven weapon assembly in the donor (CP77 weapon) frame.

Frame: +Y = forward/muzzle, +Z = up, X = width. Origin ~ weapon root ('barrel' bone).
Reads assembly.json; each part gets an axis-remap, uniform scale, and translation.
Renders side / top / front / 3-4 views with the donor body shown as a grey scale
reference, and saves the .blend.
"""
import bpy, sys, json, os
from mathutils import Vector, Matrix

CFG = sys.argv[-2]
OUTDIR = sys.argv[-1]
cfg = json.load(open(CFG))
os.makedirs(OUTDIR, exist_ok=True)

AX = {"+X": Vector((1,0,0)), "-X": Vector((-1,0,0)),
      "+Y": Vector((0,1,0)), "-Y": Vector((0,-1,0)),
      "+Z": Vector((0,0,1)), "-Z": Vector((0,0,-1))}

def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]

def strip_junk(objs):
    """Delete the 42-vert icosphere FX placeholder + lights/cameras; return meshes,arms."""
    meshes=[]; arms=[]
    for o in objs:
        if o.type=='MESH' and len(o.data.vertices)==42 and 'Icosphere' in o.name:
            bpy.data.objects.remove(o, do_unlink=True); continue
        if o.type in ('LIGHT','CAMERA'):
            bpy.data.objects.remove(o, do_unlink=True); continue
        if o.type=='MESH': meshes.append(o)
        if o.type=='ARMATURE': arms.append(o)
    return meshes, arms

def join(meshes, name):
    if not meshes: return None
    for o in bpy.data.objects: o.select_set(False)
    for m in meshes: m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes)>1: bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    # clear parent (armature) but keep transform, drop modifiers/groups for a clean rigid part
    obj.parent=None
    obj.modifiers.clear()
    for vg in list(obj.vertex_groups): obj.vertex_groups.remove(vg)
    return obj

def remap_matrix(spec):
    imgX, imgY, imgZ = (AX[s] for s in spec["axes"])
    R = Matrix((
        (imgX.x, imgY.x, imgZ.x, 0),
        (imgX.y, imgY.y, imgZ.y, 0),
        (imgX.z, imgY.z, imgZ.z, 0),
        (0,0,0,1)))
    s = spec["scale"]
    S = Matrix.Diagonal((s,s,s,1.0))
    t = spec.get("translate",[0,0,0])
    T = Matrix.Translation(Vector(t))
    return T @ R @ S

clean()

# --- donor reference (grey) ---
ref_objs = import_glb(cfg["donor_glb"])
rmesh, rarm = strip_junk(ref_objs)
donor = join(rmesh, "DONOR_ref")
if donor:
    m = bpy.data.materials.new("ref"); m.use_nodes=False; m.diffuse_color=(0.25,0.25,0.27,1)
    donor.data.materials.clear(); donor.data.materials.append(m)

# --- my parts ---
part_objs=[]
for p in cfg["parts"]:
    if not p.get("enabled",True): continue
    objs = import_glb(p["glb"])
    meshes,_ = strip_junk(objs)
    obj = join(meshes, p["name"])
    obj.matrix_world = remap_matrix(p)
    part_objs.append(obj)
    # report placed bbox in world
    bpy.context.view_layer.update()
    ws=[obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn=Vector((min(v[i] for v in ws) for i in range(3)))
    mx=Vector((max(v[i] for v in ws) for i in range(3)))
    print(f"PART {p['name']:16s} world_size=({mx.x-mn.x:.3f},{mx.y-mn.y:.3f},{mx.z-mn.z:.3f}) "
          f"Ymin={mn.y:+.3f} Ymax={mx.y:+.3f} Zmin={mn.z:+.3f} Zmax={mx.z:+.3f} Xctr={(mn.x+mx.x)/2:+.3f}")

COMPARE = os.environ.get("COMPARE") == "1"
if COMPARE and donor:
    donor.location.x -= 0.35  # shift donor aside for side-by-side profile compare
    def arrow(vec, col, name):
        d=Vector(vec)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=d.length,
            location=Vector((0,0,0))+d*0.5)
        c=bpy.context.active_object; c.name=name
        c.rotation_euler=d.to_track_quat('Z','Y').to_euler()
        m=bpy.data.materials.new(name); m.diffuse_color=col; c.data.materials.append(m)
    arrow((0,0.28,0),(1,0.1,0.1,1),"AX_Y_muzzle")   # red = +Y forward
    arrow((0,0,0.16),(0.2,0.4,1,1),"AX_Z_up")       # blue = +Z up

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR,"assembly.blend"))

# --- render setup ---
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
scn.display.shading.light='STUDIO'; scn.display.shading.color_type='TEXTURE'
scn.display.shading.show_cavity=True
scn.world=bpy.data.worlds.new("w"); scn.world.color=(0.04,0.04,0.05)
scn.render.resolution_x=900; scn.render.resolution_y=500

# frame all my parts (fallback to donor)
allobjs = part_objs if part_objs else ([donor] if donor else [])
mn=Vector((1e9,)*3); mx=Vector((-1e9,)*3)
for o in allobjs:
    for c in o.bound_box:
        w=o.matrix_world@Vector(c)
        for i in range(3): mn[i]=min(mn[i],w[i]); mx[i]=max(mx[i],w[i])
ctr=(mn+mx)/2; diag=(mx-mn).length

import math
def render(name, eye, euler):
    cam_d=bpy.data.cameras.new("c"); cam=bpy.data.objects.new("c",cam_d)
    scn.collection.objects.link(cam); scn.camera=cam
    cam_d.type='ORTHO'; cam_d.ortho_scale=diag*1.15
    cam.location=ctr+Vector(eye)*diag*2
    cam.rotation_euler=euler
    cam_d.clip_end=diag*20
    scn.render.filepath=os.path.join(OUTDIR,name)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)

R=math.radians
# side: camera on +X looking -X, up +Z -> +Y to the right, +Z up (no roll)
render("side.png", (1,0,0), (R(90),0,R(90)))
# top: camera on +Z looking -Z, up +Y -> +X right, +Y up
render("top.png",  (0,0,1), (0,0,0))
# 3/4
render("q34.png",  (0.8,-0.8,0.55), (R(58),0,R(46)))
print("RENDERED to", OUTDIR)
