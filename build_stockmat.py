"""DIAGNOSTIC: build one of our .mesh jsons that keeps the DONOR's stock
multilayered materials (instead of our metal_base .mi) so our geometry renders
with a shader the game has definitely already compiled. Isolates "our material /
shader deadlock" from "our mesh geometry" for the equip-time watchdog hang.

Args: DONOR_MESH_JSON  OUR_OUT_JSON  CHUNKMAP_JSON
"""
import json, sys

DONOR, OUT, CHUNKMAP = sys.argv[1], sys.argv[2], sys.argv[3]
chunk_mats = json.load(open(CHUNKMAP))          # one entry per render chunk
j = json.load(open(DONOR))
rc = j["Data"]["RootChunk"]

# keep donor materialEntries + localMaterialBuffer as-is (real multilayered mats).
mat0 = rc["materialEntries"][0]["name"]["$value"]   # e.g. "default"

# single 'default' appearance, every one of our chunks -> the donor's first material
app = rc["appearances"][0]
app["Data"]["name"] = {"$type": "CName", "$storage": "string", "$value": "default"}
app["Data"]["chunkMaterials"] = [
    {"$type": "CName", "$storage": "string", "$value": mat0} for _ in chunk_mats
]
rc["appearances"] = [app]

json.dump(j, open(OUT, "w"))
print(f"wrote {OUT}: {len(chunk_mats)} chunks -> donor material '{mat0}', "
      f"{len(rc.get('materialEntries',[]))} materialEntries kept")
