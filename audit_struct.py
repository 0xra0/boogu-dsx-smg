"""Structural audit of the shipped .mesh files.

Geometry can be perfect and the weapon still crash or draw nothing, so this
checks the metadata that has actually bitten:

  local material index   `isLocalInstance:1` entries address ONE of two arrays
                         (localMaterialBuffer.rawDataHeaders or
                         preloadLocalMaterialInstances) and nothing says which.
                         Clearing the wrong one crashed the game on equip.
  chunkMaterials         every chunk's material name must exist in
                         materialEntries, and there must be one per chunk
  lodLevelInfo           must list every LOD level the chunks actually use, or
                         the mesh has nothing to draw once the next one starts
  external materials     every .mi path must be in the depot
  bones                  a skinned chunk with no boneNames will not follow the
                         weapon

Usage: python3 audit_struct.py DEPOTDIR
"""
import json, os, sys, subprocess, tempfile, shutil, glob

DEPOT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/sata/weapon_mod/depot_v2/weaponset/smg"
ROOT = "/mnt/sata/weapon_mod"
problems, notes = [], []

work = tempfile.mkdtemp()
for m in glob.glob(os.path.join(DEPOT, "*.mesh")):
    shutil.copy(m, work)
subprocess.run([f"{ROOT}/wk", "convert", "serialize", work, "-o", work],
               capture_output=True)

for jf in sorted(glob.glob(os.path.join(work, "*.mesh.json"))):
    part = os.path.basename(jf)[:-10]
    rc = json.load(open(jf))["Data"]["RootChunk"]
    print(f"\n### {part}")

    entries = rc.get("materialEntries") or []
    ext = rc.get("externalMaterials") or []
    n_buf = len((rc.get("localMaterialBuffer") or {}).get("rawDataHeaders") or [])
    n_pre = len(rc.get("preloadLocalMaterialInstances") or [])
    names = set()
    for e in entries:
        nm = e["name"]["$value"]
        names.add(nm)
        idx = e["index"]
        if e["isLocalInstance"]:
            if idx >= max(n_buf, n_pre):
                problems.append(f"{part}: local material {nm!r} index {idx} but only "
                                f"{n_buf} buffer / {n_pre} preload entries -> equip crash")
        elif idx >= len(ext):
            problems.append(f"{part}: external material {nm!r} index {idx} of {len(ext)}")
    print(f"  materialEntries {len(entries)}  external {len(ext)}  "
          f"localBuffer {n_buf}  preload {n_pre}")
    for e in ext:
        p = e["DepotPath"]["$value"].replace("\\", "/")
        full = os.path.join(ROOT, "depot_v2", p)
        if not os.path.exists(full):
            problems.append(f"{part}: external material file missing: {p}")
        else:
            print(f"    ext -> {p}")

    apps = rc.get("appearances") or []
    if len(apps) != 1:
        notes.append(f"{part}: {len(apps)} appearance(s)")
    for a in apps:
        d = a.get("Data", a)
        cm = [c["$value"] for c in d.get("chunkMaterials", [])]
        for nm in cm:
            if nm not in names:
                problems.append(f"{part}: chunkMaterial {nm!r} is not in materialEntries")
        print(f"  appearance {d['name']['$value']}: chunkMaterials={cm}")

    blob = ((rc.get("renderResourceBlob") or {}).get("Data") or {}).get("header") or {}
    chunks = blob.get("renderChunkInfos") or []
    if chunks and apps:
        d = apps[0].get("Data", apps[0])
        if len(chunks) != len(d.get("chunkMaterials", [])):
            problems.append(f"{part}: {len(chunks)} render chunk(s) but "
                            f"{len(d.get('chunkMaterials', []))} chunkMaterial(s)")
    masks = sorted({c["lodMask"] for c in chunks})
    lvl = rc.get("lodLevelInfo")
    print(f"  chunks={[(c['lodMask'], c['numIndices'], c['numVertices']) for c in chunks]}")
    print(f"  lodMasks={masks}  lodLevelInfo={lvl}")
    for c in chunks:
        if c["numVertices"] > 65535:
            problems.append(f"{part}: a chunk has {c['numVertices']} verts, over 65535")
    want = len(masks)
    if lvl is not None and len(lvl) != want:
        problems.append(f"{part}: lodLevelInfo {lvl} has {len(lvl)} level(s) but the "
                        f"chunks use {want} ({masks}) - the higher LOD draws nothing")

    bones = [b.get("$value", b) for b in (rc.get("boneNames") or [])]
    print(f"  boneNames={bones}")
    if not bones:
        problems.append(f"{part}: no boneNames - it will not follow the weapon")

shutil.rmtree(work)
print("\n" + "=" * 70)
if notes:
    print("NOTES")
    for n in notes:
        print("  -", n)
print(f"\nSTRUCTURAL PROBLEMS: {len(problems)}")
for p in problems:
    print("  !", p)
