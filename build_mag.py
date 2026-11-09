"""Build a single-bone attached part - magazine, scope or muzzle - as its own
mesh, skinned to the donor part's bone so the game's animations drive it (the
magazine drops on reload, attachments follow the weapon).

Every such donor glb is a self-contained single-bone rig: the bone (mag_std /
mag_stdr / scope / muzzle) sits at the origin and the geometry is expressed in
bone-local space, so the base rig's world transform does NOT transfer. Instead
we orient our part with the given axes, FIT it into the donor part's bone-local
bounding box (uniform scale by the longest axis + centre match) so it lands
where the game expects that part, apply the tuning scale/offset, bind it rigidly
to the bone, split to <=MAX_FACES chunks and export a glb + chunkmap json."""
import bpy, sys, json, os, bmesh, math
from mathutils import Vector, Matrix

ARGS  = sys.argv[sys.argv.index("--") + 1:]
DONOR = ARGS[0]        # donor mag glb (armature source: mag_std at origin)
SRC   = ARGS[1]        # my magazine glb
OUT   = ARGS[2]        # output glb

# orientation of the source magazine -> donor mag-local frame, and the decimate
# budget; both overridable so the same script serves different source sets.
MAG_AXES   = ARGS[3].split(",") if len(ARGS) > 3 else ["+X", "+Y", "-Z"]
MAG_TARGET = int(ARGS[4]) if len(ARGS) > 4 else 5000
# The bbox fit matches the donor magazine's longest axis, but a source magazine
# with different proportions then comes out too chunky, and it lands where the
# DONOR's magazine sat rather than in our body's magazine well. These tune it:
# an extra uniform scale about the fitted centre, and a translation in mag-bone
# local space (the bone is what the reload animation drives, so the magazine
# still drops correctly from wherever we put it).
MAG_SCALE  = float(ARGS[5]) if len(ARGS) > 5 else 1.0
MAG_OFFSET = Vector([float(x) for x in ARGS[6].split(",")]) if len(ARGS) > 6 else Vector((0, 0, 0))
# chunk material name; the same fit-into-the-donor's-bbox logic builds any
# single-bone attached part (magazine, scope, muzzle), only the material differs
MAT        = ARGS[7] if len(ARGS) > 7 else "mag_mat"
MAX_FACES  = 21000

def weld_decimate(obj, target_faces):
    """Weld, flatten the redundant tessellation, THEN collapse what is left.

    Going straight to COLLAPSE from the ~250k Trellis2 source melts the model:
    the sources are hard-surface - flat panels, sharp bevels, an octagonal scope
    body - and a pure quadric collapse spends its budget evenly and rounds every
    crisp edge off.  Rendered side by side at the same 20-25k budget, collapse-only
    produced a lumpy blob with a shattered rail while the source was a clean optic;
    that, not Trellis2, is why the in-game parts looked "weird and not beautiful".

    A DISSOLVE (planar) pass first removes only edges between near-coplanar faces,
    which costs nothing visually and takes the scope 253786 -> 171816 tris, so the
    collapse that follows has far less to remove and keeps the silhouette.  Planar
    alone cannot reach budget (69706 tris even at a 30 degree limit - the Trellis2
    surface is subtly curved everywhere), so both passes are needed.

    Weld distance is 1e-4, not 1e-5: the sources arrive with 142132 non-manifold
    edges and welding drops that to 2190, which is what lets either decimator work
    at all.
    """
    for x in bpy.data.objects: x.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
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
    # smooth by angle + edge split, same reason as rig_export.py: the source glbs
    # have no normals, so flat shading would give every face its own 3 verts.
    for p in obj.data.polygons: p.use_smooth = True
    md = obj.modifiers.new("split", "EDGE_SPLIT")
    md.use_edge_angle = True; md.split_angle = math.radians(35.0); md.use_edge_sharp = True
    bpy.ops.object.modifier_apply(modifier="split")
    print(f"  OPT {obj.name}: {n0} -> {len(obj.data.polygons)} faces (welded+decimated)")
# BONE is auto-detected from the donor mag glb (a single-bone rig: mag_std / mag_stdr)

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
        if o.type=='MESH': ms.append(o)
        elif o.type=='ARMATURE': ar.append(o)
    return list(dict.fromkeys(ms)), list(dict.fromkeys(ar))

def orient_matrix(axes):
    ix,iy,iz=(AX[s] for s in axes)
    return Matrix(((ix.x,iy.x,iz.x,0),(ix.y,iy.y,iz.y,0),(ix.z,iy.z,iz.z,0),(0,0,0,1)))

def world_bbox(obj):
    vs=[obj.matrix_world @ v.co for v in obj.data.vertices]
    mn=Vector((min(v.x for v in vs),min(v.y for v in vs),min(v.z for v in vs)))
    mx=Vector((max(v.x for v in vs),max(v.y for v in vs),max(v.z for v in vs)))
    return mn,mx,(mn+mx)/2,(mx-mn)

bpy.ops.wm.read_factory_settings(use_empty=True)

# --- donor mag armature (keep mag_std), drop donor geometry ---
dm,da=strip(import_glb(DONOR))
arm=da[0]
arm.matrix_world = Matrix.Identity(4)
bpy.context.view_layer.update()
BONE = arm.data.bones[0].name   # single-bone mag rig (mag_std or mag_stdr)
# donor mag mesh bbox in mag_std-local (mag_std forced to origin) = fit target
dtarg=[o for o in dm if o.type=='MESH']
_,_,DC,DS=world_bbox(dtarg[0])
print("ARM bones:", [b.name for b in arm.data.bones])
print(f"DONOR mag bbox center=({DC.x:+.4f},{DC.y:+.4f},{DC.z:+.4f}) size=({DS.x:.4f},{DS.y:.4f},{DS.z:.4f})")
for m in dm: bpy.data.objects.remove(m,do_unlink=True)

# --- import my magazine, orient with M1 axes ---
ms,ar=strip(import_glb(SRC))
for a in ar: bpy.data.objects.remove(a,do_unlink=True)
for m in ms: m.parent=None; m.modifiers.clear()
for o in bpy.data.objects: o.select_set(False)
for m in ms: m.select_set(True)
bpy.context.view_layer.objects.active=ms[0]
if len(ms)>1: bpy.ops.object.join()
mag=bpy.context.view_layer.objects.active
mag.name="mag"
for vg in list(mag.vertex_groups): mag.vertex_groups.remove(vg)
mag.matrix_world = orient_matrix(MAG_AXES)
bpy.context.view_layer.update()
_,_,MC,MS=world_bbox(mag)
print(f"MY mag (oriented) center=({MC.x:+.4f},{MC.y:+.4f},{MC.z:+.4f}) size=({MS.x:.4f},{MS.y:.4f},{MS.z:.4f})")

# --- fit: uniform scale by longest axis, match centers, then apply tuning ---
scale = max(DS) / max(MS) * MAG_SCALE
fit = (Matrix.Translation(DC + MAG_OFFSET) @ Matrix.Diagonal((scale,scale,scale,1.0)) @
       Matrix.Translation(-MC)) @ mag.matrix_world
mag.matrix_world = fit
for o in bpy.data.objects: o.select_set(False)
mag.select_set(True); bpy.context.view_layer.objects.active=mag
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
_,_,FC,FS=world_bbox(mag)
print(f"FIT scale={scale:.4f} -> center=({FC.x:+.4f},{FC.y:+.4f},{FC.z:+.4f}) size=({FS.x:.4f},{FS.y:.4f},{FS.z:.4f})")

# weld + decimate to weapon budget (before the chunk split)
weld_decimate(mag, MAG_TARGET)

# --- split into <=MAX_FACES chunks along longest axis (16-bit index limit) ---
def split_object(obj, n, axis):
    if n<=1: return [obj]
    coords=sorted(f.center[axis] for f in obj.data.polygons)
    thr=[coords[int(len(coords)*k/n)] for k in range(1,n)]
    pieces=[]
    for b in reversed(thr):
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

nf=len(mag.data.polygons)
n=max(1, math.ceil(nf/MAX_FACES))
axis=max(range(3), key=lambda i: mag.dimensions[i])
pieces=split_object(mag, n, axis)
print(f"MAG faces={nf} -> {n} chunk(s) along axis {axis}")

# --- name, rigid-bind each chunk to mag_std ---
final=[]; chunkmap=[]
for idx,obj in enumerate(pieces):
    obj.name=f"submesh_{idx:02d}"
    for vg in list(obj.vertex_groups): obj.vertex_groups.remove(vg)
    vg=obj.vertex_groups.new(name=BONE)
    vg.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    obj.parent=arm
    m=obj.modifiers.new("Armature","ARMATURE"); m.object=arm
    chunkmap.append(MAT)
    final.append(obj)
    print(f"  CHUNK {idx} {obj.name} verts={len(obj.data.vertices)} faces={len(obj.data.polygons)}")

cmpath = os.path.splitext(OUT)[0] + "_chunkmap.json"
json.dump(chunkmap, open(cmpath,"w"))
print("MAG_CHUNKMAP", cmpath, chunkmap)

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
