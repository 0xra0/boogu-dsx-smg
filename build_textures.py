"""Import the staged PNGs into depot .xbm files with the right CP77 texture
group / BC compression per map type.

The Linux build of WolvenKit.CLI cannot load PNG/JPG (RedImage goes through
WIC, which is Windows-only), so texture import runs through the wine CLI. The
import settings come from that build's appsettings.json, which only holds ONE
XbmImportArgs block - so we do one pass per texture group, each with its own
raw tree, all landing in the same depot.

Usage: python3 build_textures.py [part ...]     (default: body mag)
"""
import json, os, shutil, subprocess, sys

ROOT = "/mnt/sata/weapon_mod"
STAGE = f"{ROOT}/staging_v2/textures"
RAW = f"{ROOT}/imp_v2"
DEPOT = f"{ROOT}/depot_v2"
DEPOT_REL = os.path.join("weaponset", "smg", "textures")
SETTINGS = "/mnt/sata/weapon_mod/wkcli_win/appsettings.json"
PARTS = sys.argv[1:] or ["body", "mag"]

# suffix -> (texture group, compression, isGamma)
GROUPS = {
    "d": ("TEXG_Generic_Color",     "TCM_QualityColor", True),   # BC7 sRGB albedo
    "r": ("TEXG_Generic_Grayscale", "TCM_QualityR",     False),  # BC4 roughness
    "m": ("TEXG_Generic_Grayscale", "TCM_QualityR",     False),  # BC4 metalness
    "n": ("TEXG_Generic_Normal",    "TCM_Normalmap",    False),  # BC5 normal
}

def winpath(p):
    return "Z:" + os.path.abspath(p).replace("/", "\\")

def set_args(group, compression, gamma):
    j = json.load(open(SETTINGS))
    j["XbmImportArgs"] = {"TextureGroup": group, "Compression": compression,
                          "IsGamma": gamma, "GenerateMipMaps": True,
                          "IsStreamable": True, "RawFormat": "TRF_TrueColor"}
    json.dump(j, open(SETTINGS, "w"), indent=2)

# one raw tree per distinct (group, compression, gamma) so each import pass sees
# only the files it has the right settings for
passes = {}
for part in PARTS:
    for suffix, cfg in GROUPS.items():
        src = f"{STAGE}/{part}_{suffix}.png"
        if not os.path.exists(src):
            print(f"  skip {src} (missing)"); continue
        key = cfg
        d = os.path.join(RAW, cfg[0].replace("TEXG_", "").lower(), DEPOT_REL)
        os.makedirs(d, exist_ok=True)
        shutil.copy(src, d)
        passes.setdefault(key, os.path.join(RAW, cfg[0].replace("TEXG_", "").lower()))

os.makedirs(DEPOT, exist_ok=True)
for (group, compression, gamma), rawdir in passes.items():
    set_args(group, compression, gamma)
    print(f"== import {group} {compression} gamma={gamma}: {rawdir}")
    r = subprocess.run([f"{ROOT}/wkwin", "import", winpath(rawdir), "-o", winpath(DEPOT)],
                       capture_output=True, text=True)
    tail = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()][-3:]
    print("   " + "\n   ".join(tail))

print("\n-- depot textures --")
outdir = os.path.join(DEPOT, DEPOT_REL)
for f in sorted(os.listdir(outdir)) if os.path.isdir(outdir) else []:
    print(f"  {os.path.getsize(os.path.join(outdir, f)):>10} {f}")
