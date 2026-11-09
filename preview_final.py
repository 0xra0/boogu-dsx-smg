"""Render the weapon EXACTLY as shipped, so a defect is seen here and not in game.

This exists because every earlier preview rendered the wrong thing.  They loaded
`build_v3/*.glb` - the INPUT to the mesh build - one part at a time, with no
backface culling and no attachments.  That is how three rounds of "fixed" scope
and magazine went out without anyone ever looking at the assembled result.

What this renders instead:
  * the meshes that are actually in the archive (exported back out of the depot
    .mesh files by preview_final.sh), not the glbs they were built from
  * every part at its rig slot, plus the donor sub-meshes the scope's .app
    loads alongside ours (_cap, _indicator_front, _indicator_rear, _decal_01)
  * LOD1 only - the engine draws one level, and mixing them looks like shards
  * BACKFACE CULLING ON, against a loud magenta void.  Any magenta seen through
    the weapon is a hole that will be see-through in game.  This is the single
    check that would have caught the scope defect on day one.

Usage: bl -b -P preview_final.py -- GLBDIR OUTDIR
"""
import bpy, sys, os, json
from mathutils import Vector

A = sys.argv[sys.argv.index("--") + 1:]
GLBDIR, OUTDIR = A[0], A[1]
TEX = "/mnt/sata/weapon_mod/staging_v2/textures"
os.makedirs(OUTDIR, exist_ok=True)

VOID = (0.60, 0.02, 0.45, 1.0)      # nothing on the weapon is this colour
SKIP = {"weaponset_magr", "weapon_placeholder"}

# The magazine meshes are PART-LOCAL and the game attaches the part at mag_slot.
# Drawing them at the origin is why every preview here showed the magazine in
# the right place while the game put it 9.56 cm further back - the single bug
# that made four "fixed" magazine builds all look wrong in game.  Any mesh bound
# to the Magazine / MagazineReload slot gets this.
MAG_SLOT = Vector((0.0, 0.0756, 0.0068))
MESH_SLOT = {"weaponset_mag": MAG_SLOT,
             "weaponset_magr": MAG_SLOT,
             "weaponset_mag_shadow": MAG_SLOT}

# part -> (appearance, own mesh, rig slot in weapon space, albedo png)
# The magazine's mesh is authored in weapon space and its slot really is zero;
# the scope and muzzle meshes are bone-local and sit at their slots.
PARTS = [
    ("body",   "weaponset_smg.app.json",     "weaponset_smg",
     Vector((0.0, 0.0000, 0.0000)), "body_d.png"),
    ("mag",    "weaponset_mag_std.app.json", "weaponset_mag",
     Vector((0.0, 0.0000, 0.0000)), "mag_d.png"),
    ("scope",  "weaponset_scope.app.json",   "weaponset_scope",
     Vector((0.0, 0.1120, 0.0896)), "scope_d.png"),
    ("muzzle", "weaponset_muzzle.app.json",  "weaponset_muzzle",
     Vector((0.0, 0.2971, 0.0307)), "muzzle_d.png"),
]


def enabled_meshes(appjson):
    """mesh basenames the appearance actually draws.

    Honouring isEnabled is the whole point.  The scope's .app references the
    donor's _cap, _decal_01 and both _indicator_* meshes but ships them all with
    isEnabled=0; drawing them anyway put a fake white flap and a band across the
    optic and nearly cost a round "fixing" components that were already off.
    Shadow proxies are skipped too - they cast but never draw.
    """
    if not os.path.exists(appjson):
        print(f"  no appearance at {appjson}, falling back to the part mesh only")
        return None
    rc = json.load(open(appjson))["Data"]["RootChunk"]
    apps = rc.get("appearances") or []
    if not apps:
        return None
    d = apps[0].get("Data", apps[0])
    out, off = [], []
    for c in d.get("components", []):
        cd = c.get("Data", c)
        if "MeshComponent" not in cd.get("$type", ""):
            continue
        path = ((cd.get("mesh") or {}).get("DepotPath") or {}).get("$value", "")
        if not isinstance(path, str) or not path:
            continue
        base = path.replace("\\", "/").split("/")[-1]
        base = base[:-5] if base.endswith(".mesh") else base
        if not cd.get("isEnabled", 1):
            off.append(base)
        elif "_shadow" in base:
            off.append(base + " (shadow)")
        elif base in SKIP:
            # weaponset_magr is the alternate magazine variant - the game swaps
            # one in, so drawing both stacks two magazines in the same place;
            # weapon_placeholder is a vanilla stub with nothing to show
            off.append(base + " (alternate)")
        else:
            out.append(base)
    print(f"    draws {out}")
    if off:
        print(f"    skips {off}")
    return out


def material(name, png):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    # Trellis2 bakes lighting into the albedo, so treat it as a plain diffuse
    # sheet.  Metallic here blew the first sheet out to featureless white.
    bsdf.inputs["Roughness"].default_value = 0.60
    bsdf.inputs["Metallic"].default_value = 0.0
    p = os.path.join(TEX, png) if png else None
    if p and os.path.exists(p):
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(p)
        m.node_tree.links.new(bsdf.inputs["Base Color"], tex.outputs["Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.34, 0.35, 0.37, 1)
    return m


def glass_material():
    """the donor's lens, which is NOT our albedo.

    Painting scope_d over chunk 2 made the first sheet's sight picture a mess of
    circuit-board noise that does not exist in game - a preview artefact that
    would have sent yet another round chasing the wrong defect."""
    m = bpy.data.materials.new("glass")
    m.use_nodes = True
    m.use_backface_culling = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.10, 0.16, 0.20, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Metallic"].default_value = 0.30
    return m


def load(path, slot, mat, chunk_mats=None):
    """chunk_mats maps an object-name prefix to a material, or to None to skip
    the chunk entirely (highlight_blocker never draws in game)"""
    if not os.path.exists(path):
        print(f"  MISSING {path}")
        return []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    out = []
    for o in [x for x in bpy.data.objects if x not in before]:
        if o.type == 'ARMATURE':
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        if o.type != 'MESH' or ('Icosphere' in o.name and len(o.data.vertices) == 42):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        if "_LOD_2" in o.name:          # the engine draws one LOD level
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        use = mat
        if chunk_mats:
            for pref, override in chunk_mats.items():
                if o.name.startswith(pref):
                    use = override
                    break
        if use is None:
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        o.parent = None
        o.modifiers.clear()
        o.matrix_world.identity()
        o.matrix_world.translation = slot
        o.data.materials.clear()
        o.data.materials.append(use)
        out.append(o)
    return out


bpy.ops.wm.read_factory_settings(use_empty=True)
objs = []
magobjs = []
# our scope mesh ships five chunks; chunk 1 is highlight_blocker, which never
# draws, and chunk 2 is the donor's glass
SCOPE_CHUNKS = {"submesh_01": None, "submesh_02": glass_material()}
donor_mat = material("donor", None)
for name, appj, own, slot, png in PARTS:
    print(f"  {name:7} slot {tuple(round(c, 4) for c in slot)}")
    draw = enabled_meshes(os.path.join(GLBDIR, appj))
    if draw is None:
        draw = [own]
    mine = material(name, png)
    for base in draw:
        got = load(os.path.join(GLBDIR, base + ".glb"), MESH_SLOT.get(base, slot),
                   mine if base == own else donor_mat,
                   SCOPE_CHUNKS if base == own and name == "scope" else None)
        if got:
            print(f"      {base:34} {len(got)} chunk(s)")
        if base == "weaponset_mag":
            magobjs += got
        objs += got
if not objs:
    raise SystemExit("nothing loaded")

mn = Vector((1e9,) * 3)
mx = Vector((-1e9,) * 3)
for o in objs:
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
ctr = (mn + mx) / 2
span = (mx - mn)
print(f"  assembled bbox X[{mn.x:+.4f},{mx.x:+.4f}] Y[{mn.y:+.4f},{mx.y:+.4f}] "
      f"Z[{mn.z:+.4f},{mx.z:+.4f}]")

scn = bpy.context.scene
scn.render.engine = 'BLENDER_EEVEE'
scn.view_settings.view_transform = 'Standard'      # don't crush the albedo
scn.view_settings.look = 'None'

# The magenta void must be VISIBLE but must not LIGHT anything, or it tints the
# whole weapon pink and the sheet becomes useless for judging colour.  Split it
# on Is Camera Ray: magenta straight to the lens, near-black for lighting.
scn.world = bpy.data.worlds.new("w")
scn.world.use_nodes = True
nt = scn.world.node_tree
bg = nt.nodes["Background"]
lp = nt.nodes.new("ShaderNodeLightPath")
mixer = nt.nodes.new("ShaderNodeMixRGB")
mixer.inputs["Color1"].default_value = (0.05, 0.05, 0.06, 1)   # ambient
mixer.inputs["Color2"].default_value = VOID                     # what the camera sees
nt.links.new(mixer.inputs["Fac"], lp.outputs["Is Camera Ray"])
nt.links.new(bg.inputs["Color"], mixer.outputs["Color"])
bg.inputs[1].default_value = 1.0

for p, e in (((0.45, -0.35, 0.50), 34), ((-0.50, 0.35, 0.35), 22),
             ((0.20, 0.55, -0.40), 14), ((-0.20, -0.55, 0.20), 14)):
    ld = bpy.data.lights.new("l", 'AREA')
    ld.energy = e
    ld.size = 0.9
    lo = bpy.data.objects.new("l", ld)
    scn.collection.objects.link(lo)
    lo.location = ctr + Vector(p)
    lo.rotation_euler = (ctr - lo.location).to_track_quat('-Z', 'Y').to_euler()

cd = bpy.data.cameras.new("c")
cam = bpy.data.objects.new("c", cd)
scn.collection.objects.link(cam)
scn.camera = cam
cd.clip_end = 100


def shot(tag, loc, at, ortho=None, w=1100, h=760):
    cd.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cd.ortho_scale = ortho
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scn.render.resolution_x = w
    scn.render.resolution_y = h
    scn.render.filepath = os.path.join(OUTDIR, f"{tag}.png")
    bpy.ops.render.render(write_still=True)
    print("  shot", tag)


L = max(span.y, span.z)
shot("01_left",   ctr + Vector((-0.9, 0, 0)), ctr, ortho=L * 1.08, w=1400, h=700)
shot("02_right",  ctr + Vector((0.9, 0, 0)),  ctr, ortho=L * 1.08, w=1400, h=700)
shot("03_top",    ctr + Vector((0, 0, 0.9)),  ctr, ortho=L * 1.08, w=1400, h=700)
shot("04_frontq", ctr + Vector((0.34, 0.30, 0.22)), ctr)
shot("05_rearq",  ctr + Vector((0.34, -0.34, 0.20)), ctr)
# The two areas that have been wrong, close up.  The magazine's centre is
# MEASURED from the loaded mesh - it was a hardcoded point, so every time the
# magazine moved the close-up kept framing where it used to be.
if magobjs:
    mmn = Vector((1e9,) * 3)
    mmx = Vector((-1e9,) * 3)
    for o in magobjs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mmn[i] = min(mmn[i], w[i])
                mmx[i] = max(mmx[i], w[i])
    magc = (mmn + mmx) / 2
    print(f"  magazine centre {tuple(round(c, 4) for c in magc)}")
else:
    magc = Vector((0, -0.06, -0.045))
shot("06_magazine", magc + Vector((0.30, -0.06, 0.06)), magc)
shot("07_magazine_left", magc + Vector((-0.30, -0.06, 0.06)), magc)
sc = next(p[3] for p in PARTS if p[0] == "scope") + Vector((0, 0, 0.031))
shot("08_scope", sc + Vector((0.22, -0.10, 0.10)), sc)
shot("09_sight_picture", sc + Vector((0, -0.30, 0.002)), sc + Vector((0, 0.2, 0.002)),
     w=900, h=900)
print("DONE")
