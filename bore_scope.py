"""Cut the optical bore through our scope body so the sight picture is visible.

WHY (measured 2026-07-30):

`build_scope.py` already keeps the donor's `highlight_blocker` and `glass`
chunks, so the lens the world-widget draws onto IS in our mesh.  But the
Trellis2 scope body we supply as chunk 0 is SOLID - the source model has no
bore.  Ray-cast down the optical axis of the shipped mesh (X=0, Z=0.0310,
along +/-Y) and our body chunk is hit twice, entering and exiting:

    glass disc          t = 0.0148          (the eyepiece, Y = +0.0552)
    our body chunk      t = 0.0285 .. 0.1214   <- a 9.3 cm solid plug

You look through the eyepiece and hit opaque `scope_mat` immediately behind it,
which is exactly the reported symptom: no image, just the flat green material.

The bore is sized off the donor's own optics, not guessed:

    highlight_blocker   X[-0.0155,+0.0155]  Z[+0.0155,+0.0465]  -> r 0.01550
    glass               X[-0.0151,+0.0151]  Z[+0.0159,+0.0460]  -> r 0.01505

so the tube is centred on (X=0, Z=0.0310) and the bore is cut at the glass
radius: any smaller and a ring of our body would sit in front of the lens edge.

Only chunk 0 is touched.  The blocker and the glass are left byte-identical -
they are the donor's, and the mesh's local material buffer indexes them.

Usage:  blender -b -P bore_scope.py -- IN.glb OUT.glb [radius] [maxfaces]
"""
import bpy, sys, bmesh, math, mathutils
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = A[0], A[1]
R = float(A[2]) if len(A) > 2 else 0.01505      # glass radius
MAXF = int(A[3]) if len(A) > 3 else 21000       # build_mag.py MAX_FACES
AXIS_X, AXIS_Z = 0.0, 0.0310                    # optical centre, weapon frame
LENGTH = 0.30                                   # longer than the scope either way

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)


def meshes():
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        if 'Icosphere' in o.name and len(o.data.vertices) == 42:
            continue
        out.append(o)
    return sorted(out, key=lambda o: o.name)


def bbox(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    return (Vector((min(v[i] for v in vs) for i in range(3))),
            Vector((max(v[i] for v in vs) for i in range(3))))


def report(tag):
    for o in meshes():
        lo, hi = bbox(o)
        print(f"  {tag} {o.name:22} v={len(o.data.vertices):6} t={len(o.data.polygons):6}  "
              f"X[{lo.x:+.4f},{hi.x:+.4f}] Y[{lo.y:+.4f},{hi.y:+.4f}] Z[{lo.z:+.4f},{hi.z:+.4f}]")


def axis_hits(o):
    """t values where the optical axis crosses this object (world space)"""
    import mathutils
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    m = o.matrix_world
    origin = Vector((AXIS_X, -0.15, AXIS_Z))
    d = Vector((0, 1, 0))
    ts = []
    for f in bm.faces:
        a, b, c = (m @ v.co for v in f.verts)
        h = mathutils.geometry.intersect_ray_tri(a, b, c, d, origin)
        if h:
            ts.append(round((h - origin).length, 4))
    bm.free()
    return sorted(ts)


report("before")
body = meshes()[0]
assert body.name.startswith("submesh_00"), f"expected submesh_00 first, got {body.name}"
print(f"  axis hits before: body={axis_hits(body)}")


def open_edges(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n


# DO NOT WELD HERE.  An earlier version did (`remove_doubles`, needed for the
# boolean attempt below) and it silently ruined the model: `build_scope.py` ends
# with an EDGE_SPLIT at 35 degrees, which is what gives this hard-surface part
# its crisp bevels and flat panels, and welding merges those split normals back
# together so every edge turns soft.  Rendered side by side, the same 20k mesh
# went from a clean faceted optic before the weld to a melted lump after it.
# The face-radius cut below needs no welded topology at all, so it simply does
# not weld - the ~52000 split verts are carried straight through.
print(f"  body in: v={len(body.data.vertices)} t={len(body.data.polygons)} "
      f"non-manifold edges={open_edges(body)} (split normals preserved)")

# A boolean DIFFERENCE is the obvious tool and it does NOT work here: even
# welded, the Trellis2 body still has ~2500 non-manifold edges, so there is no
# enclosed volume for the solver to subtract from and EXACT silently unions the
# cutter in instead (the body's Y range grew to the cutter's own -0.15).  So cut
# the bore directly: drop every face that reaches into the optical tube, then
# build a real tube in its place.
lo, hi = bbox(body)
m = body.matrix_world
inv = m.inverted()


def radial(co):
    w = m @ co
    return math.hypot(w.x - AXIS_X, w.z - AXIS_Z)


# Decimate BEFORE the tube goes in.  The old order built the liner first and
# then decimated, which handed the collapse a clean 48-sided cylinder to chew
# on; the tube is the one part of this mesh that has to stay exact.
bm = bmesh.new()
bm.from_mesh(body.data)
bm.faces.ensure_lookup_table()
doomed = [f for f in bm.faces if any(radial(v.co) < R for v in f.verts)]
print(f"  removing {len(doomed)} face(s) that reach inside r={R}")
bmesh.ops.delete(bm, geom=doomed, context='FACES')
bm.to_mesh(body.data)
bm.free()
body.data.update()

if len(body.data.polygons) > MAXF:
    md = body.modifiers.new("dec", 'DECIMATE')
    md.ratio = MAXF / len(body.data.polygons)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="dec")

# --- the tube -------------------------------------------------------------
# An inward-facing liner alone is NOT enough, and shipping one is what kept the
# scope "transparent inside" through three rounds of fixes.  Measured on the
# shipped mesh 2026-07-31, casting inward from outside the model and asking
# whether the first triangle met faces the camera:
#
#     pre-bore   828/828 front-facing, 0 see-through
#     bored       733/828 front-facing, 95 see-through, ALL at Y -0.055..-0.025
#     stock       794/828 front-facing, 28 see-through (the open top, by design)
#
# The reason is in the model, not the cut: over Y -0.055..-0.040 our Trellis2
# scope tapers to a stalk only r=0.0010..0.0148, well inside the r=0.01505 bore,
# so the cut deletes the whole rear of the body and leaves the liner as the only
# surface there - and a liner is single-sided and points at the axis, so with
# backface culling on in game that entire rear quadrant renders as nothing and
# you see straight through the scope.
#
# So build a closed tube instead: inner wall at R facing the axis, outer wall at
# R_OUT facing away, and an annulus at each end joining the two.  Now every ray
# from outside meets a front face no matter what the body does.
#
# R_OUT has to thread between the donor parts the appearance draws over us:
#
#     _cap.mesh     inner radius 0.0160..0.0169, and only back to Y=-0.0205
#     _decal_01     inner radius 0.0206 at the rear
#
# hence a wide eyepiece tube at the rear where nothing covers us, stepping down
# under the cap.  Ends are clamped into the body's own Y range so the tube never
# sticks out past the model.
R_REAR, R_FRONT = 0.0195, 0.0152         # inside _decal_01 / inside _cap
STATIONS = [(lo.y, R_REAR), (-0.0250, R_REAR), (-0.0150, R_FRONT), (hi.y, R_FRONT)]
STATIONS = [(max(lo.y, min(hi.y, y)), r) for y, r in STATIONS]

segs = 48
bm = bmesh.new()
bm.from_mesh(body.data)

# UVs for the tube: a REAL cylindrical unwrap, not a nearest-vertex copy.
#
# Copying each new vertex's UV from the nearest surviving body vertex is what the
# first version did, and it puts all three corners of a face on almost the same
# texel - the face then samples one colour and renders as a flat untextured
# patch.  Measured on the shipped mesh: 249 of our body's faces had a collapsed
# UV (1.19%) against stock's 22 (0.12%), and that is what "the scope is not fully
# filled with texture" is.
#
# Instead, unwrap the tube properly - angle across U, length along V - into the
# UV rectangle that the body already occupies right next to the bore, so the tube
# reads as the same material as its surroundings and every face gets real texel
# coverage.
uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new()


def radial_of(co):
    w = m @ co
    return math.hypot(w.x - AXIS_X, w.z - AXIS_Z)


band = []
for v in bm.verts:
    if R <= radial_of(v.co) <= R + 0.012:
        for l in v.link_loops:
            band.append(l[uvl].uv.copy())
if len(band) < 16:                       # fall back to the whole mesh
    band = [l[uvl].uv.copy() for f in bm.faces for l in f.loops]
us = sorted(u.x for u in band)
vs = sorted(u.y for u in band)
# trim the outliers so one stray seam vertex cannot stretch the patch
lo_i, hi_i = int(len(us) * 0.10), int(len(us) * 0.90)
U0, U1 = us[lo_i], us[max(hi_i, lo_i + 1)]
V0, V1 = vs[lo_i], vs[max(hi_i, lo_i + 1)]
print(f"  tube UV patch U[{U0:.4f},{U1:.4f}] V[{V0:.4f},{V1:.4f}] "
      f"from {len(band)} neighbouring loops")

vert_uv = {}


def ringverts(y, r, vparam):
    """ring of segs verts; each carries its (angle, length) UV parameters"""
    out = []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        nv = bm.verts.new(inv @ Vector((AXIS_X + r * math.cos(a), y,
                                        AXIS_Z + r * math.sin(a))))
        vert_uv[nv] = (U0 + (U1 - U0) * (k / segs),
                       V0 + (V1 - V0) * vparam)
        out.append(nv)
    return out


def quad(v0, v1, v2, v3, smooth):
    f = bm.faces.new((v0, v1, v2, v3))
    f.smooth = smooth
    for l in f.loops:
        uv = vert_uv.get(l.vert)
        if uv is not None:
            l[uvl].uv = uv
    return f


made = 0
# inner and outer walls, one strip per station gap.  The two walls get their own
# vertices rather than sharing with the annuli, so the rims stay crisp under
# smooth shading instead of rounding off.
span = max(hi.y - lo.y, 1e-6)


def vp(y):
    return (y - lo.y) / span


for (y0, r0), (y1, r1) in zip(STATIONS, STATIONS[1:]):
    if abs(y1 - y0) < 1e-6:
        continue
    ia, ib = ringverts(y0, R, vp(y0)), ringverts(y1, R, vp(y1))
    oa, ob = ringverts(y0, r0, vp(y0)), ringverts(y1, r1, vp(y1))
    for k in range(segs):
        j = (k + 1) % segs
        quad(ia[k], ia[j], ib[j], ib[k], True)      # normal points at the axis
        quad(oa[k], ob[k], ob[j], oa[j], True)      # normal points away
        made += 2
# End annuli: rear faces back down the sights, front faces up the barrel.  Their
# two rings sit at the SAME y, so they must be given different V or the rim faces
# collapse in UV and go flat - the very defect this unwrap exists to remove.
ri, ro = ringverts(lo.y, R, 0.00), ringverts(lo.y, STATIONS[0][1], 0.06)
fi, fo = ringverts(hi.y, R, 1.00), ringverts(hi.y, STATIONS[-1][1], 0.94)
for k in range(segs):
    j = (k + 1) % segs
    quad(ri[k], ro[k], ro[j], ri[j], False)
    quad(fi[k], fi[j], fo[j], fo[k], False)
    made += 2

bm.normal_update()
bm.to_mesh(body.data)
bm.free()
body.data.update()
print(f"  tube: {made} face(s), inner r={R}, outer r={R_REAR} rear -> {R_FRONT} front, "
      f"over Y[{lo.y:+.4f},{hi.y:+.4f}]")

report("after ")
hits = axis_hits(body)
print(f"  axis hits after : body={hits}")
assert not hits, f"BORE FAILED - the body still blocks the optical axis at {hits}"
assert len(body.data.vertices) < 65535, "over the 16-bit index limit"

# export_tangents is not optional: `wkwin import` refuses a glb without TANGENT
# ("One or more geometry entries in GLTF do not contain Tangents data").
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_yup=True, export_apply=False,
                          export_skins=True, export_materials='EXPORT',
                          export_normals=True, export_tangents=True)
print("wrote", OUT)
