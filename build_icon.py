"""Turn the rendered weapon PNG into the item icon: a 320x160 .xbm plus the
.inkatlas that names the slot the TweakDB `icon` flat points at.

Sizes and texture settings copied from Storm_Blade, a custom weapon mod that
displays correctly in this install (its item-icon atlas is 5 x 320x160 slots;
we only need one).  Run render_icon.py first.
"""
import json, os, subprocess
from PIL import Image

ROOT = "/mnt/sata/weapon_mod"
RAW = f"{ROOT}/staging_v2/icon_raw.png"
RAWDIR = f"{ROOT}/imp_v2/icon"
DEPOT = f"{ROOT}/depot_v2"
REL = os.path.join("weaponset", "smg", "icon")
SETTINGS = f"{ROOT}/wkcli_win/appsettings.json"
W, H = 320, 160

# --- downscale the render to icon size, keeping alpha ---
os.makedirs(os.path.join(RAWDIR, REL), exist_ok=True)
img = Image.open(RAW).convert("RGBA").resize((W, H), Image.LANCZOS)
png = os.path.join(RAWDIR, REL, "weaponset_icon.png")
img.save(png)
print("icon png", img.size, "->", png)

# --- import to xbm (icon settings: BC7 with alpha, mipchain, linear) ---
j = json.load(open(SETTINGS))
j["XbmImportArgs"] = {"TextureGroup": "TEXG_Generic_Color", "Compression": "TCM_QualityColor",
                      "IsGamma": False, "GenerateMipMaps": True, "IsStreamable": True,
                      "RawFormat": "TRF_TrueColor"}
json.dump(j, open(SETTINGS, "w"), indent=2)
winp = lambda p: "Z:" + os.path.abspath(p).replace("/", "\\")
r = subprocess.run([f"{ROOT}/wkwin", "import", winp(RAWDIR), "-o", winp(DEPOT)],
                   capture_output=True, text=True)
xbm = os.path.join(DEPOT, REL, "weaponset_icon.xbm")
print("xbm:", os.path.getsize(xbm) if os.path.exists(xbm) else "MISSING",
      [l for l in (r.stdout + r.stderr).splitlines() if "rror" in l][:2])

# --- inkatlas with a single part covering the whole texture ---
def mapper(name, left, right):
    return {"$type": "inkTextureAtlasMapper",
            "clippingRectInPixels": {"$type": "Rect", "bottom": 0, "left": 0, "right": 0, "top": 0},
            "clippingRectInUVCoords": {"$type": "RectF", "Bottom": 1, "Left": left, "Right": right, "Top": 0},
            "partName": {"$type": "CName", "$storage": "string", "$value": name}}

doc = {
    "Header": {"WKitJsonVersion": "0.0.8", "GameVersion": 2000, "DataType": "CR2W",
               "ArchiveFileName": "weaponset\\smg\\icon\\weaponset_icon.inkatlas"},
    "Data": {"Version": 195, "BuildVersion": 0, "RootChunk": {
        "$type": "inkTextureAtlas",
        "activeTexture": "StaticTexture",
        "cookingPlatform": "PLATFORM_PC",
        "dynamicTexture": {"DepotPath": {"$type": "ResourcePath", "$storage": "uint64", "$value": "0"}, "Flags": "Soft"},
        "dynamicTextureSlot": {"$type": "inkDynamicTextureSlot", "parts": [],
                               "texture": {"DepotPath": {"$type": "ResourcePath", "$storage": "uint64", "$value": "0"}, "Flags": "Soft"}},
        "isSingleTextureMode": 1,
        "parts": [], "slices": [],
        "slots": {"Elements": [{"$type": "inkTextureSlot", "parts": [mapper("slot_01", 0, 1)],
                                "texture": {"DepotPath": {"$type": "ResourcePath", "$storage": "string",
                                            "$value": "weaponset\\smg\\icon\\weaponset_icon.xbm"}, "Flags": "Default"}}]},
        "texture": {"DepotPath": {"$type": "ResourcePath", "$storage": "string",
                    "$value": "weaponset\\smg\\icon\\weaponset_icon.xbm"}, "Flags": "Default"},
        "textureResolution": "UltraHD_3840_2160"
    }, "EmbeddedFiles": []}
}
out = os.path.join(DEPOT, REL, "weaponset_icon.inkatlas.json")
json.dump(doc, open(out, "w"), indent=2)
print("wrote", out)
