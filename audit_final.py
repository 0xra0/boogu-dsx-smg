"""Audit every shipped mesh for the defect classes this project has actually hit.

Run against the glbs exported back out of the depot (audit_final.sh does that),
so it inspects what is in the archive, not what it was built from.

Checks, each one earned by a real bug:
  see-through   first triangle met from outside faces away -> a hole in game,
                where backface culling is on.  This is the scope defect.
  vert budget   65535 per chunk (IBCT_IndexUShort); the glTF exporter splits at
                every UV/normal seam so the Blender count is not the shipped one
  degenerate    zero-area triangles, which break tangent generation
  loose         vertices in no face, and faces in no LOD
  uv            missing or out-of-range UVs (hand-built geometry defaults to 0,0)
  scale         a part that is wildly the wrong size for its slot

bl -b -P audit_final.py -- GLBDIR
"""
import bpy, sys, os, math, bmesh, mathutils, random, glob
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
GLBDIR = A[0]
VERT_LIMIT = 65535
problems = []
notes = []


def flag(part, msg):
    problems.append(f"{part}: {msg}")


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    out, arms = [], []
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE':
            o.matrix_world.identity()
            arms.append(o)
            continue
        if o.type != 'MESH' or ('Icosphere' in o.name and len(o.data.vertices) == 42):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        out.append(o)
    return sorted(out, key=lambda o: o.name), arms


def tri_soup(objs):
    verts, polys, normals = [], [], []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        m = o.matrix_world
        for f in bm.faces:
            i = len(verts)
            for v in f.verts:
                verts.append(m @ v.co)
            polys.append((i, i + 1, i + 2))
            normals.append((m.to_3x3() @ f.normal).normalized())
        bm.free()
    return verts, polys, normals


def see_through(objs, samples=5000, seed=1):
    verts, polys, normals = tri_soup(objs)
    if not polys:
        return 0, 0, []
    tree = mathutils.bvhtree.BVHTree.FromPolygons(verts, polys)
    lo = Vector((min(v[i] for v in verts) for i in range(3)))
    hi = Vector((max(v[i] for v in verts) for i in range(3)))
    rad = (hi - lo).length
    random.seed(seed)
    solid = holed = 0
    where = []
    for _ in range(samples):
        target = Vector((random.uniform(lo[i], hi[i]) for i in range(3)))
        t = random.uniform(0, math.pi)
        p = random.uniform(0, 2 * math.pi)
        d = Vector((math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t)))
        loc, nrm, idx, dist = tree.ray_cast(target + d * rad, -d, 3 * rad)
        if loc is None:
            continue
        if normals[idx].dot(d) > 0:
            solid += 1
        else:
            holed += 1
            if len(where) < 5:
                where.append(tuple(round(c, 4) for c in loc))
    return solid, holed, where


print("=" * 78)
for path in sorted(glob.glob(os.path.join(GLBDIR, "weaponset_*.glb"))):
    part = os.path.basename(path)[:-4]
    objs, arms = load(path)
    if not objs:
        flag(part, "no mesh chunks at all")
        continue
    print(f"\n### {part}")
    if not arms:
        flag(part, "no armature - the mesh will not skin to its bone")
    lods = {}
    for o in objs:
        lod = 2 if "_LOD_2" in o.name else 1
        lods.setdefault(lod, []).append(o)
        nv, nf = len(o.data.vertices), len(o.data.polygons)
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        lo = Vector((min(v[i] for v in vs) for i in range(3)))
        hi = Vector((max(v[i] for v in vs) for i in range(3)))
        print(f"  {o.name:22} v={nv:6} t={nf:6}  "
              f"X[{lo.x:+.4f},{hi.x:+.4f}] Y[{lo.y:+.4f},{hi.y:+.4f}] Z[{lo.z:+.4f},{hi.z:+.4f}]")
        if nv > VERT_LIMIT:
            flag(part, f"{o.name} has {nv} verts, over the {VERT_LIMIT} 16-bit index limit")
        elif nv > VERT_LIMIT * 0.92:
            notes.append(f"{part}/{o.name}: {nv} verts, within 8% of the {VERT_LIMIT} limit")
        # degenerate + loose
        bm = bmesh.new()
        bm.from_mesh(o.data)
        deg = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
        loose = sum(1 for v in bm.verts if not v.link_faces)
        uvl = bm.loops.layers.uv.active
        baduv = 0
        if uvl is None:
            flag(part, f"{o.name} has no UV layer")
        else:
            for f in bm.faces:
                for l in f.loops:
                    u = l[uvl].uv
                    if not (-4 < u.x < 5 and -4 < u.y < 5):
                        baduv += 1
        bm.free()
        if deg:
            flag(part, f"{o.name} has {deg} zero-area triangle(s)")
        if loose:
            notes.append(f"{part}/{o.name}: {loose} loose vertex/vertices")
        if baduv:
            # submesh_04 is the donor's glasstpp, kept byte-identical; stock has
            # the same 12 out-of-range loops, so it is theirs, not ours
            (notes if o.name.startswith("submesh_04") else problems).append(
                f"{part}/{o.name}: {baduv} loop(s) with UVs outside 0-1"
                + (" (donor chunk, same in stock)" if o.name.startswith("submesh_04") else ""))
    # PER CHUNK, not per LOD group.  Grouping hid the answer: the donor chunks we
    # keep verbatim are thin single-sided sheets - `glass` and `glasstpp` are flat
    # discs, `highlight_blocker` is an open tube that never renders - so they are
    # backfaces from one side BY DESIGN and score 43-92% in stock exactly as they
    # do here.  Lumped together they made our own body look broken when measured
    # against stock it is far cleaner (0.03% vs 7.24%).
    DONOR_CHUNKS = {"submesh_01", "submesh_02", "submesh_04"}
    for o in objs:
        solid, holed, where = see_through([o])
        tot = solid + holed
        pct = 100.0 * holed / tot if tot else 0.0
        donor = any(o.name.startswith(d) for d in DONOR_CHUNKS)
        tag = "donor sheet, expected" if donor else ("OK" if pct < 1.0 else "SEE-THROUGH")
        print(f"  {o.name:22} see-through {holed:4}/{tot:4} ({pct:5.2f}%)  [{tag}]")
        if not donor and pct >= 1.0:
            flag(part, f"{o.name} is {pct:.2f}% see-through ({holed}/{tot}) at {where}")

print("\n" + "=" * 78)
if notes:
    print("NOTES")
    for n in notes:
        print("  -", n)
print(f"\nPROBLEMS: {len(problems)}")
for p in problems:
    print("  !", p)
