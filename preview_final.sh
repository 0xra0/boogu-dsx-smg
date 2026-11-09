#!/bin/sh
# Show the weapon as it will actually appear in game, from the SHIPPED meshes.
#
#   ./preview_final.sh            render from depot_v2 (what pack_deploy ships)
#   ./preview_final.sh OUTDIR     write the shots somewhere specific
#
# The point of this script is that it starts from the .mesh files in the depot -
# it exports them back out to glb and renders those - so it cannot silently show
# an older build the way rendering build_v3/*.glb does.  Backface culling is on
# and the background is magenta: any magenta visible through the weapon is a
# hole that will be see-through in game.
#
# Output: OUTDIR/contact.png (all views on one sheet) plus the individual shots.
set -e

ROOT=/mnt/sata/weapon_mod
DEPOT=$ROOT/depot_v2/weaponset/smg
ATT=$ROOT/att_donor/base/weapons/firearms/attachments/scope/w_att__scope_long_01/entities/meshes
OUT=${1:-$ROOT/preview}
W=$(mktemp -d)

echo "== exporting shipped meshes out of the depot"
for m in weaponset_smg weaponset_mag weaponset_scope weaponset_muzzle; do
  [ -f "$DEPOT/$m.mesh" ] || { echo "  MISSING $DEPOT/$m.mesh" >&2; exit 1; }
  cp "$DEPOT/$m.mesh" "$W/"
done
# the donor parts the scope's appearance references.  Most are isEnabled=0 and
# must NOT be drawn - preview_final.py reads the .app files below and honours
# that.  Drawing them unconditionally made the cap and the widget quads look
# like stray geometry poking out of the optic; they never render in game.
for m in cap indicator_front indicator_rear decal_01; do
  cp "$ATT/w_att__scope_long_01_01_$m.mesh" "$W/" 2>/dev/null || true
done
# The appearances, so the preview draws exactly what the game does.  Take the
# AUTHORED .app.json, not a serialize of the binary: WolvenKit can only turn a
# ResourcePath back into a string if it knows the hash, and our own depot paths
# are not in the vanilla dictionary, so a round-trip hands back bare uint64s
# like 7446650262204831031 and every one of our meshes goes missing.
for a in weaponset_smg weaponset_mag_std weaponset_scope weaponset_muzzle; do
  cp "$DEPOT/$a.app.json" "$W/" 2>/dev/null || true
done
echo "  $(ls "$W"/*.app.json 2>/dev/null | wc -l) appearance(s) read"
"$ROOT/wk" export "$W" --format glb -o "$W" >/dev/null 2>&1 || true
# A mesh carrying EMBEDDED textures kills the native exporter - DirectXTexNet
# needs WIC, which only exists under wine ("The type initializer for
# 'DirectXTexNet.TexHelper' threw an exception").  weaponset_muzzle.mesh is one,
# so it silently went missing from the first contact sheet.  Retry those one at
# a time with the wine build rather than dropping them from the preview.
for m in "$W"/*.mesh; do
  b=$(basename "$m" .mesh)
  [ -f "$W/$b.glb" ] && continue
  echo "  $b: native exporter failed, retrying under wine"
  "$ROOT/wkwin" export "$m" --format glb -o "$W" >/dev/null 2>&1 || true
done
n=$(ls "$W"/*.glb 2>/dev/null | wc -l)
[ "$n" -ge 4 ] || { echo "  only $n glb(s) came out of the exporters" >&2; exit 1; }
echo "  $n mesh(es) exported"

mkdir -p "$OUT"
# blender must not inherit the conda env: its bundled python fails to import
# even stdlib modules ("No module named 'math'") when CONDA_PREFIX is set.
env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u CONDA_PYTHON_EXE \
    PATH=/usr/local/bin:/usr/bin:/bin \
    blender -b --factory-startup -P "$ROOT/preview_final.py" -- "$W" "$OUT" \
    2>&1 | grep -E '^  |^DONE|Error' || true

python3 "$ROOT/contact_sheet.py" "$OUT" "$OUT/contact.png"
rm -rf "$W"
echo
echo "open $OUT/contact.png"
