"""M1: fuse the 4 assembled parts into one mesh, rigid-bind to the donor weapon
root bone ('barrel'), export a glb WolvenKit can import onto the donor rig.

Reuses assembly.json transforms. Keeps 4 material slots (body/barrel/scope/mag)
so each part keeps its own baked textures.
"""
import bpy, sys, json, os, bmesh, math
from mathutils import Vector, Matrix

CFG   = sys.argv[-3]
DONOR = sys.argv[-2]   # donor base mesh glb (armature source)
OUT   = sys.argv[-1]   # output glb
cfg = json.load(open(CFG))

# Trellis2 source parts are 250k+ faces, so weld coincident verts (UV-safe: UVs
# are per-loop) then decimate each part to a real weapon budget before splitting.
# Reference budget: the donor Pulsar body is 38.6k tris at LOD0.
# Per-part target comes from the config ("decimate"), else DEF_TARGET.
DECIMATE_TARGET = {p["name"]: p["decimate"] for p in cfg["parts"] if "decimate" in p}
DEF_TARGET = 10000

SMOOTH_ANGLE = 35.0   # degrees; edges sharper than this stay hard

def weld_decimate(obj, target_faces):
    for x in bpy.data.objects: x.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    # Weld positions (per-loop UVs preserved), planar-dissolve the redundant
    # tessellation, then collapse only what is still over budget.  Full reasoning
    # in build_mag.py: a straight COLLAPSE from the 250k source rounds off every
    # crisp edge on what is a hard-surface model, and that - not Trellis2 - is
    # why the in-game parts looked melted.
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    n0 = len(obj.data.polygons)
    if n0 > target_faces:
        md = obj.modifiers.new("planar", "DECIMATE")
        md.decimate_type = "DISSOLVE"; md.angle_limit = math.radians(5.0)
        bpy.ops.object.modifier_apply(modifier="planar")
        bm = bmesh.new(); bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(obj.data); bm.free(); obj.data.update()
        n1 = len(obj.data.polygons)
        print(f"  OPT {obj.name}: {n0} -> {n1} faces (planar 5deg)")
        if n1 > target_faces:
            md = obj.modifiers.new("dec", "DECIMATE")
            md.decimate_type = "COLLAPSE"; md.use_collapse_triangulate = True
            md.ratio = target_faces / n1
            bpy.ops.object.modifier_apply(modifier="dec")
    smooth_shade(obj)
    print(f"  OPT {obj.name}: {n0} -> {len(obj.data.polygons)} faces (welded+decimated)")

def smooth_shade(obj):
    """The source glbs carry no NORMAL attribute, so Blender shades them flat and
    the glTF exporter then gives every face its own 3 verts (a 24k-tri part
    exports as 72k verts, past the 65535 16-bit submesh limit). Smooth by angle
    with an edge split: curved surfaces share verts and read as curved, edges
    sharper than SMOOTH_ANGLE stay hard."""
    import math as _m
    for p in obj.data.polygons: p.use_smooth = True
    md = obj.modifiers.new("split", "EDGE_SPLIT")
    md.use_edge_angle = True; md.split_angle = _m.radians(SMOOTH_ANGLE)
    md.use_edge_sharp = True
    for x in bpy.data.objects: x.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="split")

AX = {"+X":Vector((1,0,0)),"-X":Vector((-1,0,0)),"+Y":Vector((0,1,0)),
      "-Y":Vector((0,-1,0)),"+Z":Vector((0,0,1)),"-Z":Vector((0,0,-1))}

def import_glb(p):
    before=set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=p)
    return [o for o in bpy.data.objects if o not in before]

def strip(objs):
    ms=[]; ar=[]
    for o in objs:
        if o.type=='MESH' and len(o.data.vertices)==42 and 'Icosphere' in o.name:
            bpy.data.objects.remove(o,do_unlink=True); continue
        if o.type in ('LIGHT','CAMERA'): bpy.data.objects.remove(o,do_unlink=True); continue
        (ms if o.type=='MESH' else ar if o.type=='ARMATURE' else []).append(o) if o.type in ('MESH','ARMATURE') else None
        if o.type=='MESH': ms.append(o)
        elif o.type=='ARMATURE': ar.append(o)
    # dedupe
    ms=list(dict.fromkeys(ms)); ar=list(dict.fromkeys(ar))
    return ms,ar

def remap(spec):
    ix,iy,iz=(AX[s] for s in spec["axes"])
    R=Matrix(((ix.x,iy.x,iz.x,0),(ix.y,iy.y,iz.y,0),(ix.z,iy.z,iz.z,0),(0,0,0,1)))
    s=spec["scale"]
    return Matrix.Translation(Vector(spec.get("translate",[0,0,0]))) @ R @ Matrix.Diagonal((s,s,s,1.0))

bpy.ops.wm.read_factory_settings(use_empty=True)

# donor armature (keep), drop donor geometry
dm,da=strip(import_glb(DONOR))
arm=da[0]
for m in dm: bpy.data.objects.remove(m,do_unlink=True)
# clear any leftover object rotation on armature so bones sit in world frame we built in
arm.matrix_world = Matrix.Identity(4)
print("ARM bones:", [b.name for b in arm.data.bones])

# import + transform + rename-material each part, collect
parts=[]
for p in cfg["parts"]:
    if not p.get("enabled",True): continue
    ms,ar=strip(import_glb(p["glb"]))
    for a in ar: bpy.data.objects.remove(a,do_unlink=True)
    for m in ms: m.parent=None; m.modifiers.clear()
    # join this part's submeshes into one object (single material slot)
    for o in bpy.data.objects: o.select_set(False)
    for m in ms: m.select_set(True)
    bpy.context.view_layer.objects.active=ms[0]
    if len(ms)>1: bpy.ops.object.join()
    obj=bpy.context.view_layer.objects.active
    obj.name=p["name"]; obj.matrix_world=remap(p)
    for vg in list(obj.vertex_groups): obj.vertex_groups.remove(vg)
    parts.append(obj)

# CP77 render chunks use 16-bit indices -> <=65535 verts/submesh. glTF splits
# verts at UV/normal seams (~2.4x), so split any part whose estimated post-export
# vert count would exceed the limit into spatial chunks (same material each).
import bmesh, json as _json, math as _math
ROOT="barrel"
ORDER=[p["name"] for p in cfg["parts"] if p.get("enabled",True)]   # follow the config
MAX_FACES=30000   # verts, not faces, are the real 16-bit limit; smoothing keeps ~1 vert/face

def split_object(obj, n, axis):
    """Split obj's faces into n spatial groups along axis (quantile planes computed
    once on the full object; peel groups off the top). Returns list of objects."""
    if n<=1: return [obj]
    coords=sorted(f.center[axis] for f in obj.data.polygons)
    thr=[coords[int(len(coords)*k/n)] for k in range(1,n)]   # ascending boundaries
    pieces=[]
    for b in reversed(thr):                                  # peel highest group first
        bpy.ops.object.mode_set(mode='OBJECT')
        for x in bpy.data.objects: x.select_set(False)
        obj.select_set(True); bpy.context.view_layer.objects.active=obj
        bpy.ops.object.mode_set(mode='EDIT')
        bm=bmesh.from_edit_mesh(obj.data)
        for f in bm.faces: f.select=(f.calc_center_median()[axis]>=b)
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        pieces.extend(o for o in bpy.context.selected_objects if o!=obj and o.type=='MESH')
    pieces.append(obj)
    return pieces

final=[]; chunkmap=[]
for name in ORDER:
    obj=next(o for o in parts if o.name==name)
    for x in bpy.data.objects: x.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    weld_decimate(obj, DECIMATE_TARGET.get(name, DEF_TARGET))
    nf=len(obj.data.polygons)
    n=max(1, _math.ceil(nf/MAX_FACES))
    dims=obj.dimensions; axis=max(range(3), key=lambda i: dims[i])
    pieces=split_object(obj, n, axis)
    print(f"PART {name}: faces={nf} -> {n} chunk(s) along axis {axis}")
    for pc in pieces:
        chunkmap.append(f"{name}_mat")
        final.append(pc)

# assign ordered names + rigid bind each chunk to root bone
for idx,obj in enumerate(final):
    obj.name=f"submesh_{idx:02d}"
    for vg in list(obj.vertex_groups): obj.vertex_groups.remove(vg)
    vg=obj.vertex_groups.new(name=ROOT)
    vg.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    obj.parent=arm
    m=obj.modifiers.new("Armature","ARMATURE"); m.object=arm
    print(f"  CHUNK {idx} {obj.name} mat={chunkmap[idx]} verts={len(obj.data.vertices)}")

_json.dump(chunkmap, open(os.path.join(os.path.dirname(OUT),"chunkmap.json"),"w"))
print("CHUNKMAP", chunkmap)

for x in bpy.data.objects: x.select_set(False)
arm.select_set(True)
for o in final: o.select_set(True)
bpy.context.view_layer.objects.active=arm
os.makedirs(os.path.dirname(OUT),exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
    use_selection=True, export_yup=True, export_apply=False,
    export_skins=True, export_materials='EXPORT',
    export_normals=True, export_tangents=True)
print("EXPORTED", OUT)
