"""Generate the ArchiveXL factory csv (appearance-resource name -> .app path).
Mirrors how the base game registers weapon appearances in
base\\gameplay\\factories\\items\\weapons\\weapons_appearances.csv, and how the
working ExtraIconics mod registers its custom guns (preload = true).
"""
import json, os

OUT = "/mnt/sata/weapon_mod/depot_v2/weaponset/smg/weaponset_factory.csv.json"
ROWS = [
    ["weaponset_smg_app",       "weaponset\\smg\\weaponset_smg.app",       "true"],
    ["weaponset_rcv1_app",      "weaponset\\smg\\weaponset_rcv1.app",      "true"],
    ["weaponset_base1_app",     "weaponset\\smg\\weaponset_base1.app",     "true"],
    ["weaponset_mag_std_app",   "weaponset\\smg\\weaponset_mag_std.app",   "true"],
    ["weaponset_mag_stdr_app",  "weaponset\\smg\\weaponset_mag_stdr.app",  "true"],
    # attachments (their own items, usable on any weapon that takes the donor part)
    ["weaponset_scope_app",     "weaponset\\smg\\weaponset_scope.app",     "true"],
    ["weaponset_muzzle_app",    "weaponset\\smg\\weaponset_muzzle.app",    "true"],
]

doc = {
    "Header": {"WKitJsonVersion": "0.0.8", "GameVersion": 2000, "DataType": "CR2W",
               "ArchiveFileName": "weaponset\\smg\\weaponset_factory.csv"},
    "Data": {"Version": 195, "BuildVersion": 0, "RootChunk": {
        "$type": "C2dArray",
        "compiledData": ROWS,
        "compiledHeaders": ["name", "path", "preload"],
        "cookingPlatform": "PLATFORM_PC",
        "data": [], "headers": []
    }, "EmbeddedFiles": []}
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(doc, open(OUT, "w"), indent=2)
print("wrote", OUT)
for r in ROWS:
    print("  ", r)
