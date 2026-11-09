#!/bin/sh
# Rebuild our attached-part .mesh files from their build glbs and install them
# into the depot.  Every part is built in its own scratch directory, so a
# `wkwin import` can never pick up a stray glb from a previous part, and the
# result is gated by check_meshes.sh before anything is packed.
#
#   ./rebuild_meshes.sh              rebuild the parts listed below
#   ./rebuild_meshes.sh mag scope    rebuild just those
#
# The recipe per part (see check_meshes.sh for why a mesh must round-trip):
#   build_base_mesh.py DONOR.mesh.json OUT.mesh.json CHUNKMAP   materials+chunks
#   wk convert deserialize DIR                                  json -> .mesh
#   rm *.mesh.json ; drop the glb in
#   wkwin import DIR --keep -o DIR                              geometry in
set -e

ROOT=/mnt/sata/weapon_mod
DEPOT=$ROOT/depot_v2/weaponset/smg
GLB=$ROOT/build_v3
CM=$ROOT/build_v2
DP=$ROOT/donor/cooked/base/weapons/firearms/smg/darra_pulsar/entities/meshes
AP=$ROOT/att_donor/base/weapons/firearms/attachments/scope/w_att__scope_long_01/entities/meshes
MP=$ROOT/att_donor/base/weapons/firearms/attachments/power/w_att__power_01/entities/meshes

# part | donor mesh json | chunkmap
PARTS="weaponset_smg|$DP/w_smg__darra_pulsar__base1_01.mesh.json|$CM/chunkmap.json
weaponset_mag|$DP/w_smg__darra_pulsar__mag_std_01.mesh.json|$CM/weaponset_mag_chunkmap.json
weaponset_magr|$DP/w_smg__darra_pulsar__mag_stdr_01.mesh.json|$CM/weaponset_magr_chunkmap.json
weaponset_mag_shadow|$DP/w_smg__darra_pulsar__mag_std_01_shadow.mesh.json|$CM/weaponset_mag_shadow_chunkmap.json
weaponset_scope|$AP/w_att__scope_long_01_01.mesh.json|$CM/weaponset_scope_chunkmap.json
weaponset_muzzle|$MP/w_att__power_01_01.mesh.json|$CM/weaponset_muzzle_chunkmap.json"

WANT="$*"

echo "$PARTS" | while IFS='|' read -r name donor chunkmap; do
  [ -n "$name" ] || continue
  if [ -n "$WANT" ]; then
    case " $WANT " in
      *" ${name#weaponset_} "*) ;;
      *" $name "*) ;;
      *) continue ;;
    esac
  fi
  [ -f "$GLB/$name.glb" ] || { echo "  SKIP $name  (no $GLB/$name.glb)"; continue; }

  W=$(mktemp -d)
  echo "=== $name"
  python3 "$ROOT/build_base_mesh.py" "$donor" "$W/$name.mesh.json" "$chunkmap" >/dev/null
  "$ROOT/wk" convert deserialize "$W" >/dev/null 2>&1
  [ -f "$W/$name.mesh" ] || { echo "  deserialize produced no .mesh" >&2; rm -rf "$W"; exit 1; }
  rm -f "$W"/*.mesh.json
  cp "$GLB/$name.glb" "$W/"
  before=$(stat -c%s "$W/$name.mesh")
  # wkwin returns 3 even on a fully successful import, and it also reports
  # success-shaped output when it imports nothing (a glb with no TANGENT data,
  # say), so its exit code is useless in both directions - trust the file.
  "$ROOT/wkwin" import "$W" --keep -o "$W" >"$W/import.log" 2>&1 || true
  if grep -q 'Error' "$W/import.log" || [ "$(stat -c%s "$W/$name.mesh")" = "$before" ]; then
    echo "  IMPORT FAILED:" >&2
    grep -E 'Error|Imported' "$W/import.log" >&2 || cat "$W/import.log" >&2
    rm -rf "$W"
    exit 1
  fi
  cp "$W/$name.mesh" "$DEPOT/$name.mesh"
  echo "  installed $(stat -c%s "$DEPOT/$name.mesh") bytes -> $DEPOT/$name.mesh"
  rm -rf "$W"
done

echo
"$ROOT/check_meshes.sh"
