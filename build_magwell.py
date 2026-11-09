"""Add a magazine well to the receiver.

Our Trellis2 receiver has no magazine housing at all: the magazine's top simply
passes through a flat underside, so the magazine reads as glued on rather than
inserted.  Every stock CP77 weapon has a well - a collar the magazine seats into
- and this builds one from the magazine's own measured cross-section.

Measured 2026-07-31 (magprofile.py / bodyslice.py, both in weapon space):

    magazine   a near-constant prism, X +/-0.0202, Y -0.1418..-0.0708 over the
               collar's Z range, with a tapered feed section in its top 16 mm
               and a ~7.8 deg forward rake that only amounts to ~1 mm here
    receiver   a box X +/-0.0233 through the magazine's Y band, underside
               sloping from Z=-0.028 at the rear up to Z=+0.015 at the front

so the collar is a chamfered rectangle around the magazine, its top buried
inside the receiver and its bottom a fixed DROP below the receiver's lowest
point over that footprint.

The section is NOT constant down its height - that was the first version and it
read as a sleeve.  It leaves the receiver at the receiver's own width, necks in
to hug the magazine, and opens back out into a flared mouth with a chamfered
lip, with a magazine catch on each flank.  See STATIONS below.

The collar is built CLOSED - outer wall, inner wall, and a rim annulus at each
end.  That is not tidiness: the scope shipped for three rounds with a
single-sided liner, and with backface culling on in game every place the liner
was the only surface rendered as a hole straight through the weapon.  A closed
shell can interpenetrate the receiver freely; neither needs a boolean.

Usage: bl -b -P build_magwell.py -- BODY.glb MAG.glb OUT.glb
"""
import bpy, sys, math, bmesh, mathutils
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
BODY, MAG, OUT = A[0], A[1], A[2]
# The magazine glb is PART-LOCAL; the game attaches the part at mag_slot.  The
# receiver is not offset, so the collar has to be cut where the magazine will
# ACTUALLY be, not where its mesh sits.  Without this the well lands 9.56 cm
# behind the magazine.
MAG_SLOT = Vector([float(x) for x in A[3].split(",")]) if len(A) > 3 \
    else Vector((0.0, 0.0756, 0.0068))

# The receiver's underside is MEASURED, not assumed.  It was a constant (+0.018,
# read off the Y-Z occupancy map) while the magazine sat behind the grip; moving
# the magazine to the magwell position forward of the trigger put the underside
# at about -0.039 and left the collar floating inside the receiver.  Anything
# keyed to where the magazine is has to be derived from where the magazine is.
# PROPORTIONS.  wellprofile.py measured what the first version was up against:
# with the magazine at the magwell position its exposed length below the
# receiver is 0.1101 m (underside Z=-0.0377, magazine bottom Z=-0.1478).  The
# first collar dropped 0.018 - 16% of that - and read on screen as a band round
# the magazine rather than a housing the magazine goes into.  A real magazine
# well covers roughly a third of the exposed magazine, so DROP is 0.030 (27%
# measured from the lowest point of the receiver, 37% from its rear).
BURY = 0.017           # how far the collar's top sits up inside the receiver
DROP = 0.030           # how much visible housing hangs below the receiver
NECK = 0.0022          # how far the shaft is drawn in below the receiver
NECK_H = 0.012         # how far below the receiver the neck is fully drawn in
FLARE_H = 0.006        # height of the flared lip
FLARE = 0.0035         # how far the lip stands proud of the shaft
LIP_T = 0.0020         # straight outer face of the lip before it chamfers back
CLEAR = 0.0012         # gap between magazine and collar
WALL = 0.0015          # collar wall: the receiver only gives 2.9 mm over the magazine
WALL_MAX = 0.005       # a housing has to look like one - a 1.5 mm wall reads as foil
CHAMFER = 0.0055       # corner chamfer of the rectangular section
CATCH_R = 0.0048       # magazine catch boss: radius ...
CATCH_H = 0.0026       # ... and how far it stands off the collar


def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes, arms = [], []
    for o in [x for x in bpy.data.objects if x not in before]:
        if o.type == 'ARMATURE':
            arms.append(o)
            continue
        if o.type != 'MESH' or ('Icosphere' in o.name and len(o.data.vertices) == 42):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        meshes.append(o)
    return meshes, arms


def bvh(objs):
    verts, polys = [], []
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
        bm.free()
    return mathutils.bvhtree.BVHTree.FromPolygons(verts, polys)


def outline(hx, y0, y1, c):
    """chamfered rectangle, counter-clockwise seen from above, with an extra
    point per edge so the bottom can follow the receiver's contour smoothly"""
    corners = [(hx, y1 - c), (hx - c, y1), (-hx + c, y1), (-hx, y1 - c),
               (-hx, y0 + c), (-hx + c, y0), (hx - c, y0), (hx, y0 + c)]
    pts = []
    for i, p in enumerate(corners):
        q = corners[(i + 1) % len(corners)]
        pts.append(p)
        pts.append(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2))
    return pts


bpy.ops.wm.read_factory_settings(use_empty=True)
body_meshes, body_arms = load(BODY)
body = next(o for o in body_meshes if o.name.startswith("submesh_00"))
mag_meshes, mag_arms = load(MAG)
mag = [o for o in mag_meshes if o.name.startswith("submesh_0")]

# --- find the receiver's underside over the magazine's own footprint ---------
allmv = [(o.matrix_world @ v.co) + MAG_SLOT for o in mag for v in o.data.vertices]
if not allmv:
    raise SystemExit("no magazine geometry - wrong glb?")
fx = max(abs(v.x) for v in allmv)
fy0, fy1 = min(v.y for v in allmv), max(v.y for v in allmv)
bw = [o.matrix_world @ v.co for o in [body] for v in o.data.vertices]
foot = [v for v in bw if abs(v.x) <= fx + 0.004 and fy0 <= v.y <= fy1]
if not foot:
    raise SystemExit("the receiver has no geometry over the magazine's footprint")
Z_UNDER = min(v.z for v in foot)
Z_TOP = Z_UNDER + BURY
Z_LIP = Z_UNDER - DROP
Z_BAND = (Z_LIP - 0.002, Z_TOP)
print(f"magazine footprint X+/-{fx:.4f} Y[{fy0:+.4f},{fy1:+.4f}]  "
      f"receiver underside Z={Z_UNDER:+.4f}  collar Z[{Z_LIP:+.4f},{Z_TOP:+.4f}]")

# --- measure the magazine over the collar's own Z range ---------------------
mv = [v for v in allmv if Z_BAND[0] <= v.z <= Z_BAND[1]]
if not mv:
    raise SystemExit("no magazine geometry in the collar band")
hx = max(abs(v.x) for v in mv)
y0, y1 = min(v.y for v in mv), max(v.y for v in mv)
print(f"magazine over Z{tuple(round(z, 4) for z in Z_BAND)}: X +/-{hx:.4f}  "
      f"Y[{y0:+.4f},{y1:+.4f}]  ({len(mv)} verts)")

# --- fit the collar to the receiver -----------------------------------------
# Match the receiver's own width just above its underside, so the collar reads as
# a continuation of the receiver rather than a shelf bolted across it.  An earlier
# version made the collar wider and it rendered as a flat wing across the
# buttstock.
near = [v for v in bw if y0 - 0.01 <= v.y <= y1 + 0.01
        and Z_UNDER <= v.z <= Z_UNDER + 0.014]
hx_recv = max(abs(v.x) for v in near) if near else hx + CLEAR + WALL
# Hug the magazine, capped by the receiver - not the receiver's full width.  At
# the buttstock those were nearly the same (0.0232 vs 0.0202) so matching the
# receiver worked; at the magwell the receiver is 0.0291 against a 0.0205
# magazine, and matching it left a 7 mm gap all round the magazine.
wall = max(0.0012, min(WALL_MAX, hx_recv - (hx + CLEAR)))
hx_out = min(hx_recv, hx + CLEAR + wall)
WALL = wall
# The taper is cut INWARD from hx_out, never outward.  Expanding the top to fair
# it into the receiver was the obvious way round and it does not work: the wall
# and the fairing compete for the same 5 mm between the magazine and the
# receiver, and with a wall thick enough to look like a housing there is nothing
# left (measured: hx_recv 0.0267, magazine+clearance 0.0217).  Necking the shaft
# instead gives the identical silhouette out of the same room, and it can never
# make the collar wider than the receiver - which is the "flat wing across the
# buttstock" failure this file has already been through once.
neck = max(0.0, min(NECK, hx_out - (hx + CLEAR) - 0.0012))
# The rear also has to be clamped: at this height the receiver already stops at
# Y=-0.1415 while the magazine reaches -0.1426, so an unclamped collar hangs off
# the back of the buttstock as a small floating block.
ry0 = min(v.y for v in near) if near else y0 - CLEAR - WALL
print(f"receiver just above its underside: half-width {hx_out:.4f}, "
      f"rear Y={ry0:+.4f} ({len(near)} verts)")

# BOTH outlines come from one envelope, the outer one inset by WALL to give the
# inner.  Deriving them independently is what put 43 see-through samples into the
# receiver: the inner outline reached 2.3 mm further back than the clamped outer
# one, leaving its inside-out rear face as the outermost surface at Y=-0.1438.
oy0 = max(ry0, y0 - CLEAR - WALL)
oy1 = y1 + CLEAR + WALL
outer_env = (hx_out, oy0, oy1)
inner_env = (hx_out - WALL, oy0 + WALL, oy1 - WALL)
if inner_env[0] < hx or inner_env[1] > y0 or inner_env[2] < y1:
    print(f"  note: collar clips the magazine slightly (inner {inner_env}, "
          f"magazine X+/-{hx:.4f} Y[{y0:+.4f},{y1:+.4f}]) - both are closed "
          f"shells, so this reads as interpenetration, not a hole")
inner = outline(*inner_env, CHAMFER)

# --- build it ---------------------------------------------------------------
mw = body.matrix_world
inv = mw.inverted()
bm = bmesh.new()
bm.from_mesh(body.data)
uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new()
kd = mathutils.kdtree.KDTree(len(bm.verts))
vuv = []
for i, v in enumerate(bm.verts):
    kd.insert(v.co, i)
    vuv.append(next((l[uvl].uv.copy() for l in v.link_loops), None))
kd.balance()
fallback = next((u for u in vuv if u is not None), None)


def nv(x, y, z):
    return bm.verts.new(inv @ Vector((x, y, z)))


# Explicit UVs for the geometry we build, keyed by vertex; paint() falls back to
# the nearest body vertex only for anything not listed.  That fallback ALONE is
# what the first collar used, and on a ring of new vertices it hands neighbouring
# rings unrelated UVs, so the housing rendered as vertical smeared bands - the
# same class of defect as the scope bore before it got a real unwrap.
uvset = {}


def paint(f, smooth):
    f.smooth = smooth
    for l in f.loops:
        u = uvset.get(l.vert)
        if u is None:
            _, i, _ = kd.find(l.vert.co)
            u = vuv[i] if i is not None and vuv[i] is not None else fallback
        if u is not None:
            l[uvl].uv = u


def uv_probe(pred):
    """Where the body sits in the atlas over some region of itself, and at what
    density: (median U, median V, UV units per metre).

    Taking the region's UV BOUNDING BOX instead - the obvious thing - does not
    work here.  The receiver's flanks beside the magwell are unwrapped into
    islands scattered right across the atlas (measured: U 0.04..0.86), so a
    collar stretched over that box samples the whole texture at random and comes
    out a collage.  What is wanted is a patch of the same metal at the same
    scale, so take the middle of the region and size the patch from the density.
    """
    us, vs, dens = [], [], []
    for f in bm.faces:
        if not pred(mw @ f.calc_center_median()):
            continue
        uvs = [l[uvl].uv for l in f.loops]
        a3 = f.calc_area()
        a2 = sum(abs((uvs[k] - uvs[0]).cross(uvs[k + 1] - uvs[0])) * 0.5
                 for k in range(1, len(uvs) - 1))
        if a3 > 1e-9 and a2 > 1e-12:
            dens.append(math.sqrt(a2 / a3))
        for uv in uvs:
            us.append(uv.x)
            vs.append(uv.y)
    if len(dens) < 16:
        return None
    us.sort(); vs.sort(); dens.sort()
    return us[len(us) // 2], vs[len(vs) // 2], dens[len(dens) // 2]


def span(c, d):
    """a d-wide span centred on c, slid (not squashed) to stay inside 0..1"""
    d = min(d, 1.0)
    lo = min(max(c - d / 2, 0.0), 1.0 - d)
    return lo, lo + d


def ping(i, m):
    """0 -> 1 -> 0 around a closed ring.  A plain i/m wraps from ~1 back to 0 in
    one step and that column of faces comes out mirrored and stretched; folding
    instead puts the seam on the weapon's own plane of symmetry, where the
    texture is already mirrored."""
    return 1.0 - abs(2.0 * i / m - 1.0)


def quad(a, b, c, d, smooth):
    paint(bm.faces.new((a, b, c, d)), smooth)


def tri(a, b, c, smooth):
    paint(bm.faces.new((a, b, c)), smooth)


n = len(inner)
# Z stations (z, how far the OUTER outline stands off hx_out), top to bottom.
# This profile is the whole point of the rebuild:
#
#   Z_TOP      buried in the receiver, at the receiver's own width
#   shoulder   still at the receiver's width as it emerges, so the housing reads
#              as the receiver continuing down rather than a box stuck under it
#   shaft      necked in by NECK
#   flare      the funnel mouth, standing FLARE proud of the shaft
#   lip        a LIP_T straight face then a chamfer back, so the mouth has a
#              visible thickness instead of a knife edge
#
# The previous version was three stations - top, shaft, one small flare - all at
# one width, which is a sleeve.  Every stock weapon's well changes section.
STATIONS = [(Z_TOP, 0.0),
            (Z_UNDER - 0.004, 0.0),
            (Z_UNDER - NECK_H, -neck),
            (Z_LIP + FLARE_H, -neck),
            (Z_LIP + LIP_T, FLARE),
            (Z_LIP, FLARE - 0.0015)]
assert all(a[0] > b[0] for a, b in zip(STATIONS, STATIONS[1:])), \
    f"stations must descend in Z: {[round(z, 4) for z, _ in STATIONS]}"


def ring(pts, z):
    return [nv(x, y, z) for x, y in pts]


# Both outlines are chamfered rectangles built by the same routine, so point i of
# one corresponds to point i of the other and the walls can be stitched directly.
inn = [ring(inner, z) for z, _ in STATIONS]
out = [ring(outline(outer_env[0] + e, outer_env[1] - e, outer_env[2] + e, CHAMFER), z)
       for z, e in STATIONS]

# Sample the texture the receiver's own lower flanks use, right beside the well,
# so the housing is skinned in the same metal as the part it grows out of.
PROBE = (uv_probe(lambda p: abs(abs(p.x) - hx_recv) < 0.008
                  and Z_UNDER <= p.z <= Z_UNDER + 0.040
                  and oy0 - 0.010 <= p.y <= oy1 + 0.010)
         or uv_probe(lambda p: Z_UNDER <= p.z <= Z_UNDER + 0.060
                     and oy0 - 0.030 <= p.y <= oy1 + 0.030))
if PROBE is None:
    raise SystemExit("no body faces beside the magwell to sample UVs from")
uc, vc, dens = PROBE
# U runs half the perimeter (ping() folds it), V the collar's height, both at
# the receiver's own texel density so the housing is the same material at the
# same grain as the receiver rather than a blown-up or tiled version of it.
PERIM = 2 * (2 * hx_out + (oy1 - oy0))
U0, U1 = span(uc, dens * PERIM / 2)
V0, V1 = span(vc, dens * (Z_TOP - Z_LIP))
print(f"collar UVs: {dens:.2f} uv/m beside the well, perimeter {PERIM:.4f} m -> "
      f"U[{U0:.4f},{U1:.4f}] V[{V0:.4f},{V1:.4f}]")

ns = len(STATIONS) - 1
for s in range(len(STATIONS)):
    for i in range(n):
        u = U0 + (U1 - U0) * ping(i, n)
        # the inner ring is offset in V so the top rim and the lip - the only
        # faces that join an inner vertex to an outer one - have UV area.  A
        # face whose loops share a UV samples one texel and renders flat.
        uvset[out[s][i]] = mathutils.Vector((u, V0 + (V1 - V0) * (s / ns)))
        uvset[inn[s][i]] = mathutils.Vector(
            (u, V0 + (V1 - V0) * (0.04 + 0.92 * s / ns)))

faces = 0
for s in range(len(STATIONS) - 1):
    for i in range(n):
        j = (i + 1) % n
        quad(inn[s][i], inn[s][j], inn[s + 1][j], inn[s + 1][i], False)   # inner wall
        quad(out[s][i], out[s + 1][i], out[s + 1][j], out[s][j], False)   # outer wall
        faces += 2
for i in range(n):
    j = (i + 1) % n
    quad(inn[0][i], out[0][i], out[0][j], inn[0][j], False)      # top rim, +Z
    quad(inn[-1][i], inn[-1][j], out[-1][j], out[-1][i], False)  # lip, -Z
    faces += 2
print(f"collar: {n} sections x {len(STATIONS)} stations, {faces} faces, "
      f"Z {Z_LIP:+.4f}..{Z_TOP:+.4f}, outer half-width {hx_out:.4f} (+{FLARE} flare)")

# --- magazine catch ---------------------------------------------------------
# A bare tube round a magazine is a sleeve; what makes a well read as a well on
# a game weapon is the release next to it.  A round boss just below the receiver
# on both flanks, buried into the collar wall so no seam can show, chamfered on
# its outer face so it catches a highlight.  Both flanks because the rest of the
# weapon is symmetric and a lone button on one side reads as a modelling slip.
CATCH_SEG = 10
CATCH_Y = oy0 + 0.013                    # clear of the rear corner chamfer
CATCH_Z = Z_UNDER - 0.0075               # just below the receiver, on the fairing
cfaces = 0
for side in (+1, -1):
    xs = [side * (hx_out - 0.0020), side * (hx_out + CATCH_H - 0.0010),
          side * (hx_out + CATCH_H)]
    radii = [CATCH_R, CATCH_R, CATCH_R * 0.72]
    rings = []
    for x, r in zip(xs, radii):
        rings.append([nv(x, CATCH_Y + r * math.cos(2 * math.pi * k / CATCH_SEG),
                         CATCH_Z + r * math.sin(2 * math.pi * k / CATCH_SEG))
                      for k in range(CATCH_SEG)])
    back = nv(xs[0], CATCH_Y, CATCH_Z)
    front = nv(xs[-1], CATCH_Y, CATCH_Z)
    # its own patch of the same metal, sized from the boss rather than from the
    # collar, or a button 5 mm across would wear a 5 cm slab of the texture
    bu0, bu1 = span(uc, dens * math.pi * CATCH_R)
    bv0, bv1 = span(vc, dens * 2 * CATCH_R)
    for st, frac in ((0, 0.15), (1, 0.60), (2, 0.85)):
        for k in range(CATCH_SEG):
            uvset[rings[st][k]] = mathutils.Vector(
                (bu0 + (bu1 - bu0) * ping(k, CATCH_SEG), bv0 + (bv1 - bv0) * frac))
    uvset[back] = mathutils.Vector((bu0 + (bu1 - bu0) * 0.5, bv0))
    uvset[front] = mathutils.Vector((bu0 + (bu1 - bu0) * 0.5, bv1))
    for s in range(len(rings) - 1):
        for k in range(CATCH_SEG):
            m = (k + 1) % CATCH_SEG
            a, b = rings[s], rings[s + 1]
            # winding derived for +X; mirroring x flips handedness, so the -X
            # side has to be wound the other way round or it is inside out and
            # the boss renders as a hole (the scope liner's failure, in little)
            if side > 0:
                quad(a[k], a[m], b[m], b[k], True)
            else:
                quad(a[k], b[k], b[m], a[m], True)
            cfaces += 1
    for k in range(CATCH_SEG):
        m = (k + 1) % CATCH_SEG
        if side > 0:
            tri(front, rings[-1][k], rings[-1][m], True)
            tri(back, rings[0][m], rings[0][k], True)
        else:
            tri(front, rings[-1][m], rings[-1][k], True)
            tri(back, rings[0][k], rings[0][m], True)
        cfaces += 2
print(f"magazine catch: 2 x r={CATCH_R} boss at Y{CATCH_Y:+.4f} Z{CATCH_Z:+.4f}, "
      f"{cfaces} faces")

bm.normal_update()
bm.to_mesh(body.data)
bm.free()
body.data.update()
print(f"body now v={len(body.data.vertices)} t={len(body.data.polygons)}")
assert len(body.data.vertices) < 65535, "over the 16-bit index limit"

for o in mag + mag_arms:
    bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.data.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_yup=True, export_apply=False,
                          export_skins=True, export_materials='EXPORT',
                          export_normals=True, export_tangents=True)
print("wrote", OUT)
