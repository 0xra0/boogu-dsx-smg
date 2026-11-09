"""Build our appearance resources from the donor Pulsar's, following the pattern
of a custom firearm mod that is known to work in this install (ExtraIconics /
Seijax: one 'default' appearance per file, mesh paths redirected, `preset` set to
the mod's own item, a separate .app per weapon part).

For each output:
  * keep ONLY the appearance named 'default' (the donor ships 8 skin variants)
  * redirect the donor mesh paths to ours
  * disable (isEnabled=0) the donor decal overlays - they are modelled onto the
    donor's geometry and would float over ours.  Components are disabled rather
    than deleted because the cooked RedPackage's HandleIds are positional.
  * leave every component CRUID EXACTLY as the donor has it - see the note on
    CRUIDS below, this is load-bearing
  * edits are applied to BOTH the raw `components` list and the cooked
    `compiledData` RedPackage (the game reads the latter)

CRUIDS ARE NOT PER-RESOURCE UNIQUE IDS - DO NOT REGENERATE THEM.
Two earlier builds did, on the assumption that a clone must not "collide" with
the resource it was cloned from.  That is backwards: a component CRUID is the
identity of a component *role*, and the game relies on the same id appearing in
several resources.

  * within one weapon, the whole-weapon .app and its part .apps describe the
    same components and vanilla gives them the same id (Pulsar: 9/9 for base1,
    4/4 mag_std, 2/2 mag_stdr).  That shared id is how the engine reconciles
    "the Barrel component of the weapon appearance IS the one the Barrel part
    entity provides" when it rebuilds the weapon out of its parts.
  * some ids are shared *across completely different weapons*, i.e. they are
    engine-wide constants: AppearanceVisualController 14627333968358193840,
    FX_muzzle_light_360 2810023434711441408, FX_muzzle_light ...412 and the
    entAppearanceProxyMeshComponent 1273696162024812544 are byte-identical in
    the vanilla Darra Pulsar app and in the Militech Ajax app.

Verified against ExtraIconics/Seijax (`sj_ajax_firestorm*.app`), the custom
firearm mod that provably works in this install: it keeps every donor id
untouched, and its part apps share 12/12, 3/3, 2/2 and 5/5 ids with its
whole-weapon app.  Regenerating ids leaves the *unattached* weapon working -
nothing is attached, so nothing is reconciled and it renders from its own app
alone - but hangs the game the instant any part entity joins the graph.  The
assertion at the bottom of this script is what stops that happening again.
"""
import json, os

DONOR_DIR = "/mnt/sata/weapon_mod/donor/cooked/base/weapons/firearms/smg/darra_pulsar"
ATT_DIR = "/mnt/sata/weapon_mod/att_donor/base/weapons/firearms/attachments"
OUT_DIR = "/mnt/sata/weapon_mod/depot_v2/weaponset/smg"
M = "base\\weapons\\firearms\\smg\\darra_pulsar\\entities\\meshes\\"
SC = "base\\weapons\\firearms\\attachments\\scope\\w_att__scope_long_01\\entities\\meshes\\"
MZ = "base\\weapons\\firearms\\attachments\\power\\w_att__power_01\\entities\\meshes\\"
OURS = "weaponset\\smg\\"

WEAPON_REDIRECT = {
    M + "w_smg__darra_pulsar__base1_01.mesh":   OURS + "weaponset_smg.mesh",
    M + "w_smg__darra_pulsar__mag_std_01.mesh":  OURS + "weaponset_mag.mesh",
    M + "w_smg__darra_pulsar__mag_stdr_01.mesh": OURS + "weaponset_magr.mesh",
}
SCOPE_REDIRECT = {SC + "w_att__scope_long_01_01.mesh": OURS + "weaponset_scope.mesh"}
MUZZLE_REDIRECT = {MZ + "w_att__power_01_01.mesh": OURS + "weaponset_muzzle.mesh"}

# Our own copy of the weapon rig, with `mag_slot` moved from the pistol grip to
# the magwell (rig_slots.py made it).  This is an ANIMATION fix, not a placement
# one: the magazine is placed by the slot either way, but with the slot left at
# the grip the magazine sat 0.187 m from its own pivot against the donor's
# 0.102 m, so everything the reload rotates about that bone swung ~1.8x too far
# and the magazine dropped from 17 cm forward of the ejection point.  With the
# slot on the magazine, mesh and pivot coincide and the animation is the donor's
# again.  Replaced everywhere, including inside `compiledData`.
RIG_REDIRECT = {"base\\weapons\\firearms\\smg\\darra_pulsar\\rig\\"
                "w_smg__darra_pulsar__base1.rig": OURS + "weaponset_base1.rig"}

# mesh components whose path contains one of these is switched off: they are
# modelled onto the donor's geometry (decals) or are donor sub-parts our single
# mesh already includes (the scope's cap and tube).  Shadow proxies stay on.
#
# `indicator` WAS in this list and that is what left the scope lens blank for a
# week.  The two `_indicator_*` meshes are NOT decoration and are not part of our
# geometry: they are the surfaces the sight picture is projected onto.  Each
# WorldWidgetComponent carries a `worlduiMeshTargetBinding` whose bindName is the
# indicator COMPONENT (w_att__scope_long_01_0532 / _6858), so disabling them
# leaves both widgets with no target and the lens renders empty - exactly the
# reported "the texture inside the scope is not filled".  Stock ships both with
# isEnabled=1; so do we.  Their material is the widget surface, not opaque metal,
# so they do not show as flat plates in game.
#
# `_cap` came out of this list on 2026-08-01 for the same reason as `indicator`.
# The scope's cap is not a sleeve over the donor's shape - it CLOSES the
# objective end (its geometry reaches r=0.0008 at Y=+0.05..+0.06).  With it
# disabled our optic was an open tube: light came straight through the bore, so
# the lens read as see-through instead of showing a picture, which is the
# "texture inside the scope is transparent" that survived the bore fix, the LOD
# fix, the texture desaturation and the UV fix.  It costs a 0.7 mm overhang on
# the +X side, where our body reaches 0.0195 and the cap 0.0202 - worth it.
#
# `decal` stays off: those meshes are modelled ONTO the donor's surfaces and
# float visibly on geometry as different as ours.
DISABLE = ("decal", "_tube")

BUILDS = [
    # (donor .app.json, output name, preset override or None, redirect map)
    (f"{DONOR_DIR}/w_smg__darra_pulsar.app.json", "weaponset_smg.app", "Items.WeaponSet_SMG", WEAPON_REDIRECT),
    # rcv1's appearance is empty even in the donor (it only carries the skin
    # variant name), but the Receiver preset entry is overridden to point here so
    # that no stock resource is left anywhere in the part chain.
    (f"{DONOR_DIR}/appearances/w_submachinegun__darra_pulsar__rcv1_01.app.json", "weaponset_rcv1.app", None, {}),
    (f"{DONOR_DIR}/appearances/w_submachinegun__darra_pulsar__base1_01.app.json", "weaponset_base1.app", None, WEAPON_REDIRECT),
    (f"{DONOR_DIR}/appearances/w_submachinegun__darra_pulsar__mag_std_01.app.json", "weaponset_mag_std.app", None, WEAPON_REDIRECT),
    (f"{DONOR_DIR}/appearances/w_submachinegun__darra_pulsar__mag_stdr_01.app.json", "weaponset_mag_stdr.app", None, WEAPON_REDIRECT),
    (f"{ATT_DIR}/scope/w_att__scope_long_01/w_att__scope_long_01.app.json", "weaponset_scope.app", "Items.WeaponSet_Scope", SCOPE_REDIRECT),
    (f"{ATT_DIR}/power/w_att__power_01/w_att__power_01.app.json", "weaponset_muzzle.app", "Items.WeaponSet_Muzzle", MUZZLE_REDIRECT),
]

def mesh_path(c):
    m = c.get("mesh")
    if isinstance(m, dict):
        dp = m.get("DepotPath")
        if isinstance(dp, dict):
            return dp.get("$value")
    return None

def edit_components(comps, redirect):
    n_red = n_off = 0
    for c in comps:
        mp = mesh_path(c)
        if mp is None:
            continue
        if mp in redirect:
            c["mesh"]["DepotPath"]["$value"] = redirect[mp]
            c["mesh"]["DepotPath"]["$storage"] = "string"
            if "meshAppearance" in c:
                c["meshAppearance"] = {"$type": "CName", "$storage": "string", "$value": "default"}
            n_red += 1
        elif any(k in mp.lower() for k in DISABLE):
            c["isEnabled"] = 0
            n_off += 1
    return n_red, n_off

def redirect_paths(node, table):
    """Rewrite any ResourcePath whose value is a key of `table`, anywhere in the
    document.  The rig hangs off entAnimatedComponent.rig, not off `mesh`, so
    edit_components never sees it - and it appears in BOTH the raw component list
    and the cooked `compiledData`, so a walk of the whole tree is the only way to
    be sure neither copy is left pointing at the donor."""
    n = 0
    if isinstance(node, dict):
        v = node.get("$value")
        if isinstance(v, str) and v in table:
            node["$value"] = table[v]
            node["$storage"] = "string"
            return 1
        for sub in node.values():
            n += redirect_paths(sub, table)
    elif isinstance(node, list):
        for sub in node:
            n += redirect_paths(sub, table)
    return n


def component_table(d):
    """{component name: CRUID} for one appearance, read from the cooked package -
    the copy the game actually loads.  Only used to verify the ids we ship are
    still the donor's; see the CRUID note at the top of this file."""
    cd = d.get("compiledData")
    if not cd:
        return {}
    t = {}
    for c in cd["Data"]["Chunks"]:
        nm = c.get("name")
        nm = nm.get("$value") if isinstance(nm, dict) else nm
        if nm:
            t[nm] = c.get("id")
    return t

ours, theirs = {}, {}          # output name -> {component name: CRUID}
os.makedirs(OUT_DIR, exist_ok=True)
for src, name, preset, redirect in BUILDS:
    j = json.load(open(src))
    rc = j["Data"]["RootChunk"]

    keep = [a for a in rc["appearances"] if a["Data"]["name"]["$value"] == "default"]
    if not keep:
        print(f"!! {name}: no 'default' appearance in {src}"); continue
    theirs[name] = component_table(keep[0]["Data"])   # snapshot before any edit
    rc["appearances"] = keep
    d = keep[0]["Data"]

    r1, o1 = edit_components(d.get("components") or [], redirect)
    r2, o2 = (0, 0)
    if d.get("compiledData"):
        r2, o2 = edit_components(d["compiledData"]["Data"]["Chunks"], redirect)

    if preset:
        rc["preset"] = {"$type": "CName", "$storage": "string", "$value": preset}

    n_rig = redirect_paths(j, RIG_REDIRECT)

    ours[name] = component_table(d)
    out = os.path.join(OUT_DIR, name + ".json")
    json.dump(j, open(out, "w"))
    print(f"{name}: redirect raw={r1} cooked={r2}, decals off raw={o1} cooked={o2}, "
          f"rig={n_rig}, {len(ours[name])} components, CRUIDs untouched -> {out}")

# --- verify: ids are the donor's, and the parts still share them with the weapon
WEAPON = "weaponset_smg.app"
print()
bad = 0
for name, t in ours.items():
    drift = [n for n, i in t.items() if theirs[name].get(n) != i]
    if drift:
        bad += len(drift)
        print(f"!! {name}: {len(drift)} CRUID(s) differ from the donor: {drift}")
for name, t in ours.items():
    if name == WEAPON or not t:
        continue
    common = set(t) & set(ours[WEAPON])
    same = [n for n in common if t[n] == ours[WEAPON][n]]
    if len(same) != len(common):
        bad += 1
    print(f"{name:24s} shares {len(same)}/{len(common)} component CRUIDs with the weapon app"
          f"{'' if len(same) == len(common) else '   <== BROKEN'}")
print("\nCRUID check:", "OK - every id is the donor's and the parts reconcile"
      if not bad else f"FAILED ({bad} problem(s))")
