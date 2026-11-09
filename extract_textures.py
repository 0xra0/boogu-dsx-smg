"""Pull baked textures out of each source part glb and split the glTF packed
metallic-roughness (G=roughness, B=metalness) into separate maps that the CP77
metal_base material expects. Writes PNGs to staging/textures/<part>_{d,n,m,r}.png
"""
import trimesh, numpy as np, os
from PIL import Image

SRC = "/mnt/sata/weapon_mod/source"
OUT = "/mnt/sata/weapon_mod/staging/textures"
os.makedirs(OUT, exist_ok=True)

PARTS = {
    "body":   "weapon_body.glb",
    "barrel": "weapon_barrel_v2.glb",
    "scope":  "weapon_scope.glb",
    "mag":    "weapon_magazine.glb",
}

for part, fn in PARTS.items():
    s = trimesh.load(os.path.join(SRC, fn), process=False)
    g = list(s.geometry.values())[0]
    mat = g.visual.material
    base = mat.baseColorTexture.convert("RGB")
    nrm  = mat.normalTexture.convert("RGB")
    mr   = np.asarray(mat.metallicRoughnessTexture.convert("RGB"))
    rough = Image.fromarray(mr[..., 1])   # G = roughness
    metal = Image.fromarray(mr[..., 2])   # B = metalness
    base.save(f"{OUT}/{part}_d.png")
    nrm.save(f"{OUT}/{part}_n.png")
    rough.save(f"{OUT}/{part}_r.png")
    metal.save(f"{OUT}/{part}_m.png")
    print(f"{part:8s} d={base.size} n={nrm.size} r={rough.size} m={metal.size}")
print("done")
