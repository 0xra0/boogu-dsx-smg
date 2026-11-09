#!/bin/sh
# Pack the depot into weaponset_smg.archive and deploy it (plus the .xl and the
# TweakXL .yaml) into the game.  Nothing here is clever - it exists so the pack
# is reproducible and always runs the mesh gate first.
#
#   ./pack_deploy.sh            gate, pack, deploy to archive/pc/mod  (normal)
#   ./pack_deploy.sh hot        same, but deploy to archive/pc/hot    (iterating)
#   ./pack_deploy.sh --pack     gate and pack only, don't touch the game
#
# HOT MODE.  RedHotTools is installed and its ArchiveWatcher watches
# `archive/pc/hot`, so an archive dropped there is hot-installed into the
# RUNNING game - no relaunch.  Observed end to end at 22:18 on 2026-07-30:
#
#     [ArchiveWatcher] Watching "C:\game\archive\pc\hot" for changes...
#     [ArchiveLoader] Archives reload requested...
#     [ArchiveLoader] Found archives:  - weaponset_smg.archive
#     [ArchiveLoader] Unloading game archives...
#     [ArchiveLoader] Moving updated archives...
#     [ArchiveLoader] Loading updated archives...
#     [ArchiveLoader] Resetting resource cache...
#     [ArchiveLoader] Reloading archive extensions...
#     [ArchiveLoader] Archives reload completed.
#
# `hot` is a DROP-BOX, not a location: RedHotTools MOVES the archive out of it
# into archive/pc/mod (overwriting what was there) and leaves hot/ empty.  So
# there is never a double registration to manage, and nothing to park or undo -
# after a hot deploy the install is in exactly the state a normal deploy leaves
# it.  It also resets the resource cache, which is what makes a changed .mesh
# actually take effect rather than serving the copy already in memory.
#
# The archive is the only thing the watcher handles.  For the other two:
#
#     TweakXL.Reload()        re-reads r6/tweaks/weaponset_smg.yaml
#     ArchiveXL.Reload()      re-reads the .xl (factories + localization)
#
# Those are what the RedHotTools overlay's own Tweaks/Archives buttons call -
# its modules/hot/main.lua has the native RedHotTools.ReloadTweaks/ReloadArchives
# commented out in favour of them.  RedHotTools.ReloadScripts() is the redscript
# one; we ship no scripts, so it is never needed here.
#
# The packroot is built by COPYING the depot and dropping the WolvenKit source
# sidecars (*.mesh.json, *.app.json, en-us.json.json).  Those are inputs, not
# resources: packing them would put junk paths in the archive.  en-us.json
# itself IS a shipped resource (the localization JsonResource) and must stay.
set -e

ROOT=/mnt/sata/weapon_mod
DEPOT=$ROOT/depot_v2
OUT=$ROOT/deploy
GAME="/mnt/ssd/Cyberpunk 2077/game/prefix/drive_c/game"

"$ROOT/check_meshes.sh"
echo

PACKROOT=$(mktemp -d)
trap 'rm -rf "$PACKROOT"' EXIT
cp -r "$DEPOT"/. "$PACKROOT"/
# Drop every WolvenKit source sidecar.  A sidecar is always `<name>.<ext>.json`
# - two dots - so match that rather than listing extensions: the old
# mesh/app/json-only list silently shipped `weaponset_icon.inkatlas.json` as a
# 38th resource once build_icon.py started writing it.  The localization
# resource `local/en-us.json` has a single dot and correctly survives.
find "$PACKROOT" -name '*.*.json' -delete
n=$(find "$PACKROOT" -type f | wc -l)
echo "packroot files: $n"
find "$PACKROOT" -type f | sed "s|$PACKROOT/||" | sort | sed 's/^/  /'

"$ROOT/wk" pack "$PACKROOT" -o "$OUT" >/dev/null 2>&1 || true
ARCHIVE=$(find "$OUT" -maxdepth 1 -name '*.archive' -newer "$PACKROOT" 2>/dev/null | head -1)
[ -n "$ARCHIVE" ] || ARCHIVE="$OUT/$(basename "$PACKROOT").archive"
if [ ! -f "$ARCHIVE" ]; then
  echo "pack produced no archive" >&2
  exit 1
fi
mv -f "$ARCHIVE" "$OUT/weaponset_smg.archive"
echo
echo "packed $(stat -c%s "$OUT/weaponset_smg.archive") bytes -> $OUT/weaponset_smg.archive"
echo
python3 "$ROOT/check_refs.py" "$OUT/weaponset_smg.archive" "$DEPOT"

[ "$1" = "--pack" ] && exit 0

# The .xl always lives in archive/pc/mod - ArchiveXL only scans that folder -
# and it just names resource paths, so it resolves whichever archive supplies
# them.  Only the .archive moves.
cp -f "$OUT/weaponset_smg.xl" "$GAME/archive/pc/mod/weaponset_smg.xl"
echo "deployed  archive/pc/mod/weaponset_smg.xl"
cp -f "$OUT/weaponset_smg.yaml" "$GAME/r6/tweaks/weaponset_smg.yaml"
echo "deployed  r6/tweaks/weaponset_smg.yaml"

if [ "$1" = "hot" ]; then
  mkdir -p "$GAME/archive/pc/hot"
  cp -f "$OUT/weaponset_smg.archive" "$GAME/archive/pc/hot/weaponset_smg.archive"
  echo "dropped   archive/pc/hot/weaponset_smg.archive  <- watched"
  # RedHotTools moves it into archive/pc/mod within a second or so; wait for
  # that rather than reporting a deploy that may not have landed
  i=0
  while [ -f "$GAME/archive/pc/hot/weaponset_smg.archive" ] && [ $i -lt 20 ]; do
    sleep 1
    i=$((i + 1))
  done
  if [ -f "$GAME/archive/pc/hot/weaponset_smg.archive" ]; then
    echo "  still sitting in hot/ after ${i}s - is the game running?" >&2
    echo "  (it is picked up on next launch either way)" >&2
  else
    echo "hot-installed after ${i}s -> archive/pc/mod/weaponset_smg.archive"
    LOG=$(ls -t "$GAME/red4ext/plugins/RedHotTools/"RedHotTools-*.log 2>/dev/null | head -1)
    [ -n "$LOG" ] && grep -a 'ArchiveLoader' "$LOG" | tail -8 | sed 's/^/  /'
  fi
  echo
  echo "Now in the CET console:  TweakXL.Reload()   (only if the yaml changed)"
  echo "Then re-equip the weapon so the entity is rebuilt from the new meshes."
else
  cp -f "$OUT/weaponset_smg.archive" "$GAME/archive/pc/mod/weaponset_smg.archive"
  echo "deployed  archive/pc/mod/weaponset_smg.archive"
fi
echo
"$ROOT/mod_toggle.sh" status
