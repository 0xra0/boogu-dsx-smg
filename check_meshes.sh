#!/bin/sh
# Acceptance gate for every .mesh we ship.  RUN THIS BEFORE EVERY PACK.
#
#   ./check_meshes.sh            checks depot_v2/weaponset/smg/*.mesh
#   ./check_meshes.sh <dir>      checks <dir>/*.mesh
#
# WHY (2026-07-30): the magazine meshes built at 11:04 and the scope mesh built
# on 07-29 were CORRUPT - a zero-length buffer inside the render blob - and the
# game hard-hangs on equip when it loads one (120 s engine watchdog, GameThread
# spinning).  Nothing in the CR2W container, the header, the bbox, the bone list,
# the quantization or the chunk counts shows it; all of those compare clean
# against a known-good mesh.  The ONLY offline signal found was that WolvenKit's
# own exporter refuses to read the file:
#
#     weaponset_scope.mesh - byteLength 0 must be greater than or equal to 1.
#
# A mesh that cannot be exported back to glb must not be shipped.  This turns a
# multi-day in-game bisect into a five-second check.
#
# Cause: re-running `wk convert deserialize` + `wkwin import --keep` from the
# same base json and glb produces a VALID mesh, so the corruption comes from the
# build sequence (a stale or double-imported .mesh), not from the source glb -
# the glbs are structurally fine (1 mesh, 1 primitive, POSITION/NORMAL/
# TEXCOORD_0/TANGENT/JOINTS_0/WEIGHTS_0).  Rebuild recipe per mesh:
#     build_base_mesh.py <donor>.mesh.json <out>.mesh.json <chunkmap>.json
#     wk convert deserialize <dir>          # json -> empty-geometry .mesh
#     rm *.mesh.json ; cp <part>.glb <dir>
#     wkwin import <depot> --keep -o <depot>

DIR="${1:-/mnt/sata/weapon_mod/depot_v2/weaponset/smg}"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

n=0
for m in "$DIR"/*.mesh; do
  [ -f "$m" ] || continue
  cp "$m" "$WORK"/ && n=$((n + 1))
done

if [ "$n" -eq 0 ]; then
  echo "no .mesh files in $DIR" >&2
  exit 2
fi

echo "export-testing $n mesh(es) from $DIR"
/mnt/sata/weapon_mod/wkwin export "$WORK" -o "$WORK" >/dev/null 2>&1

bad=0
for m in "$WORK"/*.mesh; do
  b=$(basename "$m" .mesh)
  if [ -f "$WORK/$b.glb" ]; then
    echo "  OK       $b"
  else
    echo "  CORRUPT  $b   <-- DO NOT SHIP; rebuild it"
    bad=$((bad + 1))
  fi
done

echo
if [ "$bad" -eq 0 ]; then
  echo "all $n mesh(es) round-trip cleanly"
  exit 0
fi
echo "$bad of $n mesh(es) are corrupt" >&2
exit 1
