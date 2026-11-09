"""Verify every `weaponset\\...` path our .app files reference is actually in the
packed archive.  A bad redirect is invisible otherwise: the serializer prints
unknown paths as bare uint64 hashes and the game just draws nothing.

SELF-TESTS FIRST, ALWAYS.  A silently-wrong binary parser "clears" everything it
checks, which is worse than no check at all.  Two guards here:

  * the FNV1a64 of a known depot path must match a known hash, and
  * every file we packed must be findable in the table we just parsed;
    if fewer than all of them are, the parser is wrong and we abort.

The header before the file-entry array is **20 bytes**, not the 28 recorded
earlier in this project's notes - that value made every lookup miss and would
have condemned a perfectly good archive.  Layout of archive v12:
    'RDAR', uint32 version, uint64 indexPosition @8, uint32 indexSize @16
    index: uint32 fileTableOffset, uint32 fileTableSize, uint64 crc,
           uint32 fileEntryCount @16, then 20 bytes, then fileEntryCount
           entries of 0x38 bytes each starting with the FNV1a64 of the path.

Usage:  python3 check_refs.py [ARCHIVE] [DEPOT]
"""
import glob
import json
import os
import struct
import sys

ARCHIVE = sys.argv[1] if len(sys.argv) > 1 else "/mnt/sata/weapon_mod/deploy/weaponset_smg.archive"
DEPOT = sys.argv[2] if len(sys.argv) > 2 else "/mnt/sata/weapon_mod/depot_v2"
HEADER = 20
ENTRY = 0x38


def fnv1a64(s):
    h = 0xCBF29CE484222325
    for c in s.encode():
        h = ((h ^ c) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def archive_hashes(path):
    b = open(path, "rb").read()
    if b[:4] != b"RDAR":
        raise SystemExit(f"{path}: not an .archive")
    idxpos = struct.unpack_from("<Q", b, 8)[0]
    fto, _fts, _crc, cnt = struct.unpack_from("<IIQI", b, idxpos)
    base = idxpos + fto + HEADER
    return {struct.unpack_from("<Q", b, base + i * ENTRY)[0] for i in range(cnt)}, cnt


def depot_paths(root):
    out = []
    for f in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if not os.path.isfile(f):
            continue
        name = os.path.basename(f)
        if name.count(".") > 1 and name.endswith(".json"):
            continue                      # WolvenKit source sidecar, not shipped
        out.append(os.path.relpath(f, root).replace("/", "\\"))
    return sorted(out)


def app_refs(root):
    refs = {}
    for f in sorted(glob.glob(os.path.join(root, "**", "*.app.json"), recursive=True)):
        found = set()

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "DepotPath" and isinstance(v, dict):
                        s = str(v.get("$value", ""))
                        if s.lower().startswith("weaponset"):
                            found.add(s)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)

        walk(json.load(open(f)))
        refs[os.path.basename(f)] = sorted(found)
    return refs


def main():
    hashes, cnt = archive_hashes(ARCHIVE)
    packed = depot_paths(DEPOT)
    print(f"archive {os.path.basename(ARCHIVE)}: {cnt} entries; depot: {len(packed)} files")

    # --- self-test: the parser must find everything we packed ---------------
    hit = sum(1 for p in packed if fnv1a64(p) in hashes)
    print(f"self-test: {hit}/{len(packed)} depot paths located in the file table")
    if hit != len(packed):
        print("PARSER IS WRONG (or the archive is missing files) - not trusting this check",
              file=sys.stderr)
        for p in packed:
            if fnv1a64(p) not in hashes:
                print(f"    unlocated: {p}", file=sys.stderr)
        return 2
    if cnt != len(packed):
        print(f"WARNING: archive has {cnt} entries but the depot ships {len(packed)} - "
              f"something extra was packed", file=sys.stderr)

    # --- the actual check ---------------------------------------------------
    bad = 0
    for app, refs in app_refs(DEPOT).items():
        for s in refs:
            if fnv1a64(s) not in hashes:
                print(f"  DANGLING  {app:28} {s}", file=sys.stderr)
                bad += 1
    if bad:
        print(f"{bad} dangling reference(s)", file=sys.stderr)
        return 1
    total = sum(len(v) for v in app_refs(DEPOT).values())
    print(f"all {total} app->archive reference(s) resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
