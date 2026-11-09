"""Generate the ArchiveXL onscreen-localization resource holding the weapon's
display name and description.  Registered through weaponset_smg.xl and referenced
from the TweakXL item as displayName / localizedDescription.

Edit NAME / DESC below to rename the weapon; no other file needs changing.
"""
import json, os

OUT = "/mnt/sata/weapon_mod/depot_v2/weaponset/smg/local/en-us.json.json"

ENTRIES = [
    ("WeaponSet_SMG_name", "Boogu DS-X"),
    ("WeaponSet_SMG_desc",
     "A one-off build on a Darra Polytechnic DS1 frame: carbon-composite shell, "
     "reworked optics rail and a hand-wired power cell. Unregistered, unlicensed "
     "and very loud."),
    ("WeaponSet_Scope_name", "DS-X Optic"),
    ("WeaponSet_Scope_desc",
     "Matched carbon-shell sight from the DS-X kit. Fits any rail that takes a "
     "long scope."),
    ("WeaponSet_Muzzle_name", "DS-X Suppressor"),
    ("WeaponSet_Muzzle_desc",
     "Matched carbon-shell can from the DS-X kit. Fits any barrel that takes a "
     "power-weapon muzzle."),

    # Diagnostic ladder - see the bisect note in weaponset_smg.yaml.  Each rung
    # differs from its neighbour by exactly one step; EQUIP each in turn and the
    # first that freezes names the layer at fault.  Drop all of these, and the
    # matching records, once the freeze is found.
    ("WeaponSet_Test_name", "DS-X TEST 0 (control, nothing custom)"),
    ("WeaponSet_Test_desc",
     "Diagnostic 0 of 4: a plain clone of the stock Pulsar preset - no asset or "
     "wiring of ours at all. Equip it. If this freezes, the problem is not this "
     "mod."),
    ("WeaponSet_SMG_A_name", "DS-X TEST A (our appearance only)"),
    ("WeaponSet_SMG_A_desc",
     "Diagnostic 1 of 4: our appearance resource, every slot left stock. Equip "
     "it. If this freezes, the fault is in our .app or a mesh in it."),
    ("WeaponSet_SMG_C_name", "DS-X TEST C (our arrays, stock parts)"),
    ("WeaponSet_SMG_C_desc",
     "Diagnostic 2 of 4: stock appearance and stock parts, but the slot arrays "
     "written by hand. Equip it. If this freezes, the fault is in how those "
     "arrays are authored and no asset of ours is involved."),
    ("WeaponSet_SMG_B_name", "DS-X TEST B (our parts, stock lists)"),
    ("WeaponSet_SMG_B_desc",
     "Diagnostic 3 of 4: our body and magazines wired in, but only the Pulsar's "
     "own three attachment lists. Equip it. If C works and this freezes, the "
     "fault is in our part items or their appearance resources."),
]

doc = {
    "Header": {"WKitJsonVersion": "0.0.8", "GameVersion": 2000, "DataType": "CR2W",
               "ArchiveFileName": "weaponset\\smg\\local\\en-us.json"},
    "Data": {"Version": 195, "BuildVersion": 0, "RootChunk": {
        "$type": "JsonResource",
        "cookingPlatform": "PLATFORM_PC",
        "root": {"HandleId": "0", "Data": {
            "$type": "localizationPersistenceOnScreenEntries",
            "entries": [
                {"$type": "localizationPersistenceOnScreenEntry",
                 "femaleVariant": text, "maleVariant": "",
                 "primaryKey": "0", "secondaryKey": key}
                for key, text in ENTRIES
            ]}}
    }, "EmbeddedFiles": []}
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(doc, open(OUT, "w"), indent=2)
print("wrote", OUT)
for k, t in ENTRIES:
    print(f"  {k}: {t[:60]}")
