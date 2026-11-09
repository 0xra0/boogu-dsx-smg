"""Build the scope mesh, keeping the donor's optical chunks.

Same fit as build_mag.py (orient our glb, scale it into the donor part's
bone-local bbox, rigid-bind to the single bone), but the scope cannot be a
single-material replacement of the whole donor mesh: the lens is a *chunk* of
that mesh.  The donor's default appearance maps five render chunks

    0 masksset (body, LOD1)   1 highlight_blocker   2 glass
    3 maskssettpp (body, LOD2)                      4 glasstpp

and `glass` is the material that shows the world when aiming - the scope's
on_weapon_ui world widget draws over it.  Replacing all five with our own opaque
material is why the modded optic showed the green display and no image.  So we
keep chunks 1, 2 and 4 verbatim from the donor (their materials come along in
the donor .mesh's localMaterialBuffer, see build_base_mesh.py) and only supply
chunks 0 and 3 - the LOD1 and LOD2 copies of our own body.

Args (after --):  DONOR_GLB  SRC_GLB  OUT_GLB  AXES  TARGET  [SCALE] [OFFSET] [MAT]
"""
import bpy, sys, json, os, bmesh, math
from mathutils import Vector, Matrix

A = sys.argv[sys.argv.index("--") + 1:]
DONOR, SRC, OUT = A[0], A[1], A[2]
AXES   = A[3].split(",") if len(A) > 3 else ["-X", "-Y", "+Z"]
TARGET = int(A[4]) if len(A) > 4 else 20000
SCALE  = float(A[5]) if len(A) > 5 else 1.0
OFFSET = Vector([float(x) for x in A[6].split(",")]) if len(A) > 6 else Vector((0, 0, 0))
MAT    = A[7] if len(A) > 7 else "scope_mat"

# donor object name -> (our output index, chunk material, LOD).  Everything is
# LOD1: the donor's LOD2 set (a 1971-tri body + a 16-tri lens) has no useful
# counterpart here, because collapse-decimating our source that far shatters it
# (see the decimation floor in the project notes), and a scope is small enough
# that one level costs nothing.
# Donor chunks kept verbatim -> (our chunk index, chunk material, LOD level).
# The LOD2 pair is NOT optional.  Dropping it (as this script used to) is the one
# structural difference left between our scope and the stock one: a field-by-field
# diff of the two .mesh files came back with exactly one mismatch,
#     lodLevelInfo   stock [0, 1]   ours [0]
# i.e. our mesh declares a single LOD level and has nothing at all to draw once
# the second one takes over.  Stock chunk 3 is a 1971-tri body and chunk 4 its
# `glasstpp` lens; note that stock's LOD2 body is SOLID - ray-cast down the
# optical axis it is hit at t=[0.0452, 0.1578] whereas its LOD1 body is bored -
# so the scope is see-through up close and filled at range.  Only chunk 0 gets
# bored (bore_scope.py takes meshes()[0]), which reproduces that exactly.
KEEP = {
    "submesh_01_LOD_1": (1, "highlight_blocker", 1),
    "submesh_02_LOD_1": (2, "glass",             1),
    "submesh_04_LOD_2": (4, "glasstpp",          2),
}
LOD2_TARGET = 2000              # stock LOD2 body is 1971 tris
BODY_DONOR = "submesh_00_LOD_1"         # the chunk our geometry replaces (fit target)

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


def world_bbox(obj):
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return mn, mx, (mn + mx) / 2, (mx - mn)


def weld_decimate(obj, target_faces):
    """Weld hard, planar-dissolve, then collapse.  Full reasoning in build_mag.py:
    a straight COLLAPSE from the 250k source rounds off every crisp edge and is
    what made the in-game scope a lumpy blob rather than the clean optic the
    source actually is."""
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
    for p in obj.data.polygons: p.use_smooth = True
    md = obj.modifiers.new("split", "EDGE_SPLIT")
    md.use_edge_angle = True; md.split_angle = math.radians(35.0); md.use_edge_sharp = True
    bpy.ops.object.modifier_apply(modifier="split")
    print(f"  OPT {obj.name}: {n0} -> {len(obj.data.polygons)} faces")


bpy.ops.wm.read_factory_settings(use_empty=True)

# --- donor: keep the armature and the optical chunks, measure the body chunk ---
dm, da = strip(import_glb(DONOR))
arm = da[0]
arm.matrix_world = Matrix.Identity(4)
bpy.context.view_layer.update()
BONE = arm.data.bones[0].name
by_name = {o.name: o for o in dm}
if BODY_DONOR not in by_name:
    raise SystemExit(f"donor has no {BODY_DONOR}; has {sorted(by_name)}")
_, _, DC, DS = world_bbox(by_name[BODY_DONOR])
print(f"ARM bone={BONE}  DONOR body centre=({DC.x:+.4f},{DC.y:+.4f},{DC.z:+.4f}) "
      f"size=({DS.x:.4f},{DS.y:.4f},{DS.z:.4f})")
kept = {}
for name, o in by_name.items():
    if name in KEEP:
        idx, mat, lod = KEEP[name]
        kept[idx] = (o, mat, lod)
        mn, mx, c, s = world_bbox(o)
        print(f"  KEEP {name} -> chunk {idx} ({mat}, LOD{lod}) "
              f"faces={len(o.data.polygons)} centre=({c.x:+.4f},{c.y:+.4f},{c.z:+.4f})")
    else:
        bpy.data.objects.remove(o, do_unlink=True)

# --- our scope: orient, fit into the donor body's bbox, apply tuning ---
ms, ar = strip(import_glb(SRC))
for a in ar: bpy.data.objects.remove(a, do_unlink=True)
for m in ms: m.parent = None; m.modifiers.clear()
for o in bpy.data.objects: o.select_set(False)
for m in ms: m.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1: bpy.ops.object.join()
mine = bpy.context.view_layer.objects.active
mine.name = "ours"
for vg in list(mine.vertex_groups): mine.vertex_groups.remove(vg)
ix, iy, iz = (AX[s] for s in AXES)
mine.matrix_world = Matrix(((ix.x, iy.x, iz.x, 0), (ix.y, iy.y, iz.y, 0),
                            (ix.z, iy.z, iz.z, 0), (0, 0, 0, 1)))
bpy.context.view_layer.update()
_, _, MC, MS = world_bbox(mine)
scale = max(DS) / max(MS) * SCALE
mine.matrix_world = (Matrix.Translation(DC + OFFSET) @
                     Matrix.Diagonal((scale, scale, scale, 1.0)) @
                     Matrix.Translation(-MC)) @ mine.matrix_world
for o in bpy.data.objects: o.select_set(False)
mine.select_set(True); bpy.context.view_layer.objects.active = mine
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
_, _, FC, FS = world_bbox(mine)
print(f"FIT scale={scale:.4f} centre=({FC.x:+.4f},{FC.y:+.4f},{FC.z:+.4f}) "
      f"size=({FS.x:.4f},{FS.y:.4f},{FS.z:.4f})")

weld_decimate(mine, TARGET)
# The real limit is 65535 VERTICES per chunk (IBCT_IndexUShort), not faces, and
# the glTF exporter splits a vertex at every UV/normal seam.  Measured on this
# model that lands at 2.13 verts/tri (20000 tris -> 42591 verts), so the old flat
# 21000-face guard was leaving ~23000 verts of headroom unused and needlessly
# starving a hard-surface part of detail.  Budget by the quantity that actually
# overflows, with margin, and let the ratio be measured rather than assumed.
VERTS_PER_TRI = 2.3            # measured 2.13, rounded up
VERT_BUDGET = 62000            # 65535 minus room for the kept donor chunks
max_faces = int(VERT_BUDGET / VERTS_PER_TRI)
est = len(mine.data.polygons) * VERTS_PER_TRI
print(f"  budget: {len(mine.data.polygons)} faces ~= {est:.0f} verts "
      f"(limit {VERT_BUDGET}, max_faces {max_faces})")
if len(mine.data.polygons) > max_faces:
    raise SystemExit(f"our chunk has {len(mine.data.polygons)} faces ~ {est:.0f} verts; "
                     f"the 16-bit index limit needs <= {max_faces} faces, lower TARGET")

kept[0] = (mine, MAT, 1)

# --- chunk 3: our own LOD2 body, the counterpart to stock's maskssettpp -------
# A STRAIGHT COPY of LOD1, and that is a deliberate trade, not laziness.
#
# Stock's LOD2 body is 1971 tris and watertight.  Ours cannot be decimated to
# anything like that without tearing, because the Trellis2 source is not a
# manifold: welded at 1e-4 it still carries ~2200 non-manifold edges, so the
# collapser stalls (2000 requested, 13146 delivered) AND punches holes on the
# way.  Audited on the shipped mesh, three attempts all landed in the same
# place - decimating the finished LOD1: 95/4045 see-through samples; decimating
# the raw source instead: 89; adding holes_fill + recalc_face_normals: 87, with
# 542 boundary edges still open.  Stock's is 0.
#
# Copying LOD1 gives a LOD2 with exactly LOD1's audited quality (23/4383, which
# is better than stock's own LOD1 at 193/4381) for the price of ~13000 extra
# triangles that are only ever drawn at distance.  Holes are visible; a bigger
# distance mesh is not.  Revisit if the source is ever regenerated as a clean
# closed manifold, which is the only thing that would make a real LOD2 possible.
for x in bpy.data.objects:
    x.select_set(False)
mine.select_set(True)
bpy.context.view_layer.objects.active = mine
bpy.ops.object.duplicate()
lod2 = bpy.context.view_layer.objects.active
lod2.modifiers.clear()
kept[3] = (lod2, MAT, 2)
print(f"  LOD2 body: copy of LOD1, {len(lod2.data.polygons)} faces, "
      f"{len(lod2.data.vertices)} verts")

# --- name in chunk order, rigid-bind everything to the single bone ---
final, chunkmap = [], []
for idx in sorted(kept):
    obj, mat, lod = kept[idx]
    obj.name = f"submesh_{idx:02d}_LOD_{lod}"
    obj.modifiers.clear()
    for vg in list(obj.vertex_groups): obj.vertex_groups.remove(vg)
    vg = obj.vertex_groups.new(name=BONE)
    vg.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    obj.parent = arm
    m = obj.modifiers.new("Armature", "ARMATURE"); m.object = arm
    chunkmap.append(mat)
    final.append(obj)
    print(f"  CHUNK {idx} {obj.name} mat={mat} verts={len(obj.data.vertices)} "
          f"faces={len(obj.data.polygons)}")

cmpath = os.path.splitext(OUT)[0] + "_chunkmap.json"
json.dump(chunkmap, open(cmpath, "w"))
print("MAG_CHUNKMAP", cmpath, chunkmap)

for x in bpy.data.objects: x.select_set(False)
arm.select_set(True)
for o in final: o.select_set(True)
bpy.context.view_layer.objects.active = arm
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
    use_selection=True, export_yup=True, export_apply=False,
    export_skins=True, export_materials='EXPORT',
    export_normals=True, export_tangents=True)
print("EXPORTED", OUT)
