"""Generate 4 CP77 metal_base material instances (.mi.json) referencing our
per-part xbm textures. Depot paths use backslashes (REDengine convention)."""
import json, os

DEPOT = "/mnt/sata/weapon_mod/depot"
TEXROOT = "weaponset\\smg\\textures"
MATDIR = os.path.join(DEPOT, "weaponset", "smg", "materials")
os.makedirs(MATDIR, exist_ok=True)
PARTS = ["body", "barrel", "scope", "mag"]

def tex(path):
    return {"$type": "rRef:ITexture"}  # placeholder replaced below

def texval(name, relpath):
    return {"$type": "rRef:ITexture", name: {
        "DepotPath": {"$type": "ResourcePath", "$storage": "string", "$value": relpath},
        "Flags": "Default"}}

def fval(name, v):
    return {"$type": "Float", name: v}

def vec4(name, x=1, y=1, z=1, w=1):
    return {"$type": "Vector4", name: {"$type": "Vector4", "W": w, "X": x, "Y": y, "Z": z}}

for part in PARTS:
    base = f"{TEXROOT}\\{part}"
    values = [
        texval("BaseColor", f"{base}_d.xbm"),
        vec4("BaseColorScale"),
        texval("Metalness", f"{base}_m.xbm"),
        fval("MetalnessBias", 0.0),
        fval("MetalnessScale", 1.0),
        texval("Roughness", f"{base}_r.xbm"),
        fval("RoughnessScale", 1.0),
        fval("RoughnessBias", 0.0),
        texval("Normal", f"{base}_n.xbm"),
    ]
    doc = {
        "Header": {"WKitJsonVersion": "0.0.8", "GameVersion": 2000, "DataType": "CR2W",
                   "ArchiveFileName": f"weaponset\\smg\\materials\\{part}.mi"},
        "Data": {"Version": 195, "BuildVersion": 0, "RootChunk": {
            "$type": "CMaterialInstance",
            "audioTag": {"$type": "CName", "$storage": "string", "$value": "None"},
            "baseMaterial": {"DepotPath": {"$type": "ResourcePath", "$storage": "string",
                             "$value": "engine\\materials\\metal_base.remt"}, "Flags": "Default"},
            "cookingPlatform": "PLATFORM_PC",
            "enableMask": 1, "metadata": None, "resourceVersion": 4,
            "values": values
        }, "EmbeddedFiles": []}
    }
    out = os.path.join(MATDIR, f"{part}.mi.json")
    json.dump(doc, open(out, "w"), indent=2)
    print("wrote", out)
print("done")
