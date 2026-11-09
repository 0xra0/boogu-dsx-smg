#!/bin/sh
# Toggle OUR weapon mod (Boogu DS-X) on/off, whole or by LAYER.  Fully reversible:
# files are only moved to a parking folder, never deleted or edited.
#
#   ./mod_toggle.sh on        everything live
#   ./mod_toggle.sh off       everything parked
#   ./mod_toggle.sh assets    ONLY the .archive + .xl live   (no TweakXL records)
#   ./mod_toggle.sh tweaks    ONLY the .yaml live            (no assets)
#   ./mod_toggle.sh status
#
# ---------------------------------------------------------------------------
# ESTABLISHED 2026-07-30, single variable, AGAA parked throughout:
#     mod off -> vanilla Darra Pulsar equips fine
#     mod on  -> freeze (120s engine watchdog kills the game)
# So the cause is in these three files.  Which one is still open.
#
# The mod has two independent layers:
#
#   tweaks  r6/tweaks/weaponset_smg.yaml
#           TweakXL records.  Only ever CREATES Items.WeaponSet_* records via
#           $base clones; never writes a vanilla record name.
#
#   assets  archive/pc/mod/weaponset_smg.archive  (36 files, all weaponset\smg\*)
#           archive/pc/mod/weaponset_smg.xl       (factory csv + localization)
#           The .app appearances, meshes, materials and textures.
#
# Why 'assets' is the first thing to test: when the mod was fully installed, BOTH
# Items.WeaponSet_Test (a plain clone of the stock preset, nothing of ours in it)
# AND the genuine vanilla Items.Preset_Pulsar_Default froze.  A record-level fault
# cannot reach a weapon whose records we never touched, so the suspicion falls on
# the asset layer, which the engine resolves globally.
#
# BOTH tests are performed the same way: equip a VANILLA Darra Pulsar.
# (Our own weapon does not exist in either split - 'assets' has no records to
# spawn it from, and 'tweaks' has no appearance for it to load.)
#
#   assets -> freezes  : the .archive or .xl poisons the Pulsar globally;
#                        no TweakXL record is involved at all
#   tweaks -> freezes  : a record we create leaks into the vanilla weapon
#   neither freezes    : the two layers are only lethal together
# ---------------------------------------------------------------------------

CMD="${1:-status}"

G="/mnt/ssd/Cyberpunk 2077/game/prefix/drive_c/game"
PARK="/mnt/sata/weapon_mod/parked"

# layer|live path|parked name
PAIRS="tweaks|$G/r6/tweaks/weaponset_smg.yaml|weaponset_smg.yaml
assets|$G/archive/pc/mod/weaponset_smg.archive|weaponset_smg.archive
assets|$G/archive/pc/mod/weaponset_smg.xl|weaponset_smg.xl"

# apply <layer-to-enable>   ("all" = every layer, "none" = no layer)
apply() {
  want="$1"
  mkdir -p "$PARK"
  echo "$PAIRS" | while IFS='|' read -r layer live name; do
    [ -n "$name" ] || continue
    if [ "$want" = "all" ] || [ "$want" = "$layer" ]; then
      # should be LIVE
      if [ -f "$live" ]; then
        echo "  live    $name"
      elif [ -f "$PARK/$name" ]; then
        mv "$PARK/$name" "$live" && echo "  ON      $name"
      else
        echo "  MISSING $name  (not in game dir, not in $PARK)" >&2
      fi
    else
      # should be PARKED
      if [ -f "$live" ]; then
        mv "$live" "$PARK/$name" && echo "  off     $name"
      elif [ -f "$PARK/$name" ]; then
        echo "  parked  $name"
      else
        echo "  MISSING $name  (not in game dir, not in $PARK)" >&2
      fi
    fi
  done
}

case "$CMD" in
  on)     echo "=> ALL layers live";                        apply all    ;;
  off)    echo "=> ALL layers parked";                      apply none   ;;
  assets) echo "=> assets only (.archive + .xl), no yaml";  apply assets ;;
  tweaks) echo "=> tweaks only (.yaml), no assets";         apply tweaks ;;
  status)
    echo "$PAIRS" | while IFS='|' read -r layer live name; do
      [ -n "$name" ] || continue
      if   [ -f "$live" ];        then echo "LIVE    [$layer] $name"
      elif [ -f "$PARK/$name" ];  then echo "PARKED  [$layer] $name"
      else                             echo "MISSING [$layer] $name"; fi
    done
    exit 0 ;;
  *)
    echo "usage: $0 on|off|assets|tweaks|status" >&2; exit 2 ;;
esac

echo
echo "--- now ---"
"$0" status
echo
echo "Restart the game, then equip a VANILLA Darra Pulsar."
