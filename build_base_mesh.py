"""Edit a donor mesh json into one of our base .mesh jsons: external metal_base
materials (one per distinct chunk material) + a single 'default' appearance
mapping the render chunks. The material list and per-chunk mapping are derived
from the exporter's chunkmap.json, so this handles both the multi-material body
(body/barrel/scope) and the single-material magazine (mag) uniformly.

Geometry buffer is left intact (it gets overwritten by the glb import --keep step).

Args:  DONOR_JSON  OUT_JSON  CHUNKMAP_JSON
"""
import json, copy, os, sys

DONOR    = sys.argv[1]
OUT      = sys.argv[2]
CHUNKMAP = sys.argv[3]
MATROOT  = "weaponset\\smg\\materials"

def cname(v): return {"$type": "CName", "$storage": "string", "$value": v}
def rref(path):
    return {"DepotPath": {"$type": "ResourcePath", "$storage": "string", "$value": path}, "Flags": "Default"}

chunk_mats = json.load(open(CHUNKMAP))                 # e.g. ["body_mat","body_mat","barrel_mat",...]
# distinct material slots, in first-seen order -> parts (strip the _mat suffix -> .mi name)
mats = list(dict.fromkeys(chunk_mats))
parts = [m[:-4] if m.endswith("_mat") else m for m in mats]

j = json.load(open(DONOR))
rc = j["Data"]["RootChunk"]

# --- materials -------------------------------------------------------------
# One external metal_base .mi per distinct chunk material, EXCEPT for names the
# donor already defines as a local instance: those chunks are kept verbatim from
# the donor (the scope's `glass` / `glasstpp` / `highlight_blocker` - see
# build_scope.py), so they must keep the donor's own material.
#
# A kept entry carries the DONOR's `index`, and that index addresses one of TWO
# different arrays depending on the mesh - this is not interchangeable:
#
#     w_att__scope_long_01_01   localMaterialBuffer 17   preload  0
#     ..._mag_std_01_shadow     localMaterialBuffer  0   preload  4
#     ..._base1_01_shadow       localMaterialBuffer  0   preload 16
#
# Clearing the wrong one leaves `isLocalInstance=1, index=N` pointing into an
# empty array.  Doing exactly that to the magazine shadow proxy on 2026-07-30
# CRASHED the game on equip, the moment the magazine part loaded.  So whenever
# any donor-local material is kept, BOTH stores are left whole; the unused
# entries are dead weight but every index stays valid.
donor_local = {m["name"]["$value"]: m for m in rc["materialEntries"] if m["isLocalInstance"]}
keep_local = [m for m in mats if m in donor_local]
entries, ext, extparts = [], [], []
for m, p in zip(mats, parts):
    if m in donor_local:
        entries.append(donor_local[m])
    else:
        entries.append({"$type": "CMeshMaterialEntry", "index": len(ext),
                        "isLocalInstance": 0, "name": cname(m)})
        ext.append(rref(f"{MATROOT}\\{p}.mi")); extparts.append(p)
rc["materialEntries"] = entries
rc["externalMaterials"] = ext
rc["preloadExternalMaterials"] = []
if not keep_local:
    rc["localMaterialBuffer"] = {"$type": "meshMeshMaterialBuffer", "materials": []}
    rc["preloadLocalMaterialInstances"] = []

# Every local index must actually address something.  This is the check that
# would have caught the crash above before it ever shipped.
n_buf = len((rc.get("localMaterialBuffer") or {}).get("rawDataHeaders") or [])
n_pre = len(rc.get("preloadLocalMaterialInstances") or [])
for e in entries:
    if e["isLocalInstance"]:
        assert e["index"] < max(n_buf, n_pre), (
            f'local material {e["name"]["$value"]!r} wants index {e["index"]} but the donor '
            f'has only {n_buf} buffer / {n_pre} preload entries')

# --- appearance: single 'default'; chunkMaterials straight from the chunkmap ---
app = copy.deepcopy(rc["appearances"][0])
app["Data"]["chunkMaterials"] = [cname(m) for m in chunk_mats]
app["Data"]["name"] = cname("default")
rc["appearances"] = [app]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(j, open(OUT, "w"))
print("wrote", OUT)
print("materialEntries:", [(m["name"]["$value"], "local" if m["isLocalInstance"] else "ext")
                           for m in rc["materialEntries"]])
print("externalMaterials:", [e["DepotPath"]["$value"] for e in rc["externalMaterials"]])
print(f"kept donor local materials: {keep_local} "
      f"(localMaterialBuffer {n_buf}, preloadLocalMaterialInstances {n_pre})")
print("appearance chunkMaterials:", [c["$value"] for c in rc["appearances"][0]["Data"]["chunkMaterials"]])
print("boneNames:", [b.get("$value", b) for b in rc.get("boneNames", [])])
