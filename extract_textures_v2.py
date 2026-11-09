"""Pull the baked textures out of each v2 source glb and write the maps the CP77
metal_base material wants.

The v2 Trellis2 exports carry only baseColor (4096, RGBA) + the glTF-packed
metallicRoughness (4096, RGB: G=roughness, B=metalness) - no normal map - so we
emit _d/_m/_r and a flat _n placeholder. Albedo keeps more resolution than the
data maps because it is the only one that shows detail at viewmodel distance.
"""
import json, struct, io, os, sys
from PIL import Image

SRC = "/mnt/sata/weapon_mod/source_v2"
OUT = "/mnt/sata/weapon_mod/staging_v2/textures"
PARTS = {"body": "weapon_body.glb", "mag": "weapon_magazine.glb",
         "scope": "weapon_scope.glb", "muzzle": "weapon_muzzle.glb"}
ONLY = sys.argv[1:] or list(PARTS)

ALBEDO_SIZE = 2048
DATA_SIZE = 1024

def glb_images(path):
    with open(path, "rb") as f:
        f.read(12)
        clen, _ = struct.unpack("<II", f.read(8)); js = json.loads(f.read(clen))
        blen, _ = struct.unpack("<II", f.read(8)); buf = f.read(blen)
    out = []
    for im in js["images"]:
        bv = js["bufferViews"][im["bufferView"]]
        off = bv.get("byteOffset", 0)
        out.append(Image.open(io.BytesIO(buf[off:off + bv["byteLength"]])))
    mat = js["materials"][0]["pbrMetallicRoughness"]
    return out, mat

os.makedirs(OUT, exist_ok=True)
for part in ONLY:
    imgs, mat = glb_images(os.path.join(SRC, PARTS[part]))
    base = imgs[mat["baseColorTexture"]["index"]].convert("RGB")
    mr = imgs[mat["metallicRoughnessTexture"]["index"]].convert("RGB")
    base = base.resize((ALBEDO_SIZE, ALBEDO_SIZE), Image.LANCZOS)
    mr = mr.resize((DATA_SIZE, DATA_SIZE), Image.LANCZOS)
    r, g, b = mr.split()                       # glTF packing: G=roughness B=metalness
    base.save(f"{OUT}/{part}_d.png")
    g.save(f"{OUT}/{part}_r.png")
    b.save(f"{OUT}/{part}_m.png")
    # flat tangent-space normal so metal_base always has a normal to sample
    Image.new("RGB", (64, 64), (128, 128, 255)).save(f"{OUT}/{part}_n.png")
    print(f"{part:7s} d={base.size} r={g.size} m={b.size} n=(64, 64) flat")
print("wrote", OUT)
