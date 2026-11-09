"""Build weaponset_smg.app from the donor Pulsar .app. In the 'default' appearance
(both the raw `components` list AND the cooked `compiledData` RedPackage the game
actually uses at runtime): redirect the body + both magazine meshes to ours, and
blank the donor decal/shadow mesh paths. The two magazines stay separate skinned
components (mag_std drops on reload, mag_stdr is the reload spare), so the mag
animates instead of being fused into the body."""
import json, os

DONOR = "/mnt/sata/weapon_mod/donor/cooked/base/weapons/firearms/smg/darra_pulsar/w_smg__darra_pulsar.app.json"
OUT   = "/mnt/sata/weapon_mod/depot/weaponset/smg/weaponset_smg.app.json"
D = "base\\weapons\\firearms\\smg\\darra_pulsar\\entities\\meshes\\"

# donor mesh path -> our mesh (skinned components keep their bone binding: base1->barrel,
# mag_std_01->mag_std, mag_stdr_01->mag_stdr)
REDIRECT = {
    D + "w_smg__darra_pulsar__base1_01.mesh":    "weaponset\\smg\\weaponset_smg.mesh",
    D + "w_smg__darra_pulsar__mag_std_01.mesh":   "weaponset\\smg\\weaponset_mag.mesh",
    D + "w_smg__darra_pulsar__mag_stdr_01.mesh":  "weaponset\\smg\\weaponset_magr.mesh",
}

def get_mesh_path(c):
    m = c.get("mesh")
    if isinstance(m, dict):
        dp = m.get("DepotPath")
        if isinstance(dp, dict): return dp.get("$value")
    return None

def set_mesh_path(c, val):
    c["mesh"]["DepotPath"]["$value"] = val
    c["mesh"]["DepotPath"]["$storage"] = "string"

def edit_components(comps):
    n_redirect = n_blank = 0
    for c in comps:
        mp = get_mesh_path(c)
        if mp is None:
            continue
        if mp in REDIRECT:
            set_mesh_path(c, REDIRECT[mp])
            if "meshAppearance" in c:
                c["meshAppearance"] = {"$type": "CName", "$storage": "string", "$value": "default"}
            n_redirect += 1
        else:
            continue  # leave every non-redirected mesh (placeholder, donor decal/
                      # shadow) pointing at its real base-game resource. Blanking
                      # them to "" left a dangling FNV("") hash ref — a suspect for
                      # the equip-time engine watchdog hang, so stop blanking.
    return n_redirect, n_blank

j = json.load(open(DONOR))
rc = j["Data"]["RootChunk"]
d = rc["appearances"][0]["Data"]            # 'default' appearance

r1, b1 = edit_components(d["components"])
# same edits inside the cooked RedPackage the game uses at runtime
chunks = d["compiledData"]["Data"]["Chunks"]
r2, b2 = edit_components(chunks)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(j, open(OUT, "w"))
print(f"raw components: redirected={r1} blanked={b1}")
print(f"compiledData chunks: redirected={r2} blanked={b2}")
print("wrote", OUT)
