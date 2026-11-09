#!/bin/sh
# Toggle the "Any Gun Any Attachment" TweakXL folder off/on, for the Pulsar freeze
# bisect.  Fully reversible: the folder is only renamed, never deleted or edited.
#
#   ./agaa_toggle.sh off     move it aside  -> AGAA does not load
#   ./agaa_toggle.sh on      move it back
#   ./agaa_toggle.sh status
#
# Why: AGAA ships one yaml per weapon-category plus "all" and "with slots"
# variants, and they are MUTUALLY EXCLUSIVE - you install exactly one.  All of
# them are present here, and seven of them each replace the whole of
# Items.Base_Pulsar.slotPartList with a different array.  Every one of those
# arrays drops the four geometry slots (Receiver / Barrel / Magazine /
# MagazineEmpty) while slotPartListPreset still installs parts into them, and the
# Dec-11 variants also reference Items.SniperPossibleScopesList, a record that
# does not exist in TweakDB (4855 references across the folder).  Items.Base_Pulsar
# is the base of every Darra Pulsar, so this lands on the vanilla weapon, on our
# Boogu DS-X and on the plain-clone diagnostic control alike.

T="/mnt/ssd/Cyberpunk 2077/game/prefix/drive_c/game/r6/tweaks"
ON="$T/Any Gun Any Attachment"
OFF="$T/../_disabled_Any Gun Any Attachment"

case "$1" in
  off)
    if [ -d "$ON" ]; then
      mv "$ON" "$OFF" && echo "AGAA moved aside -> $OFF"
    else
      echo "already off"
    fi
    ;;
  on)
    if [ -d "$OFF" ]; then
      mv "$OFF" "$ON" && echo "AGAA restored -> $ON"
    else
      echo "already on"
    fi
    ;;
  status|"")
    [ -d "$ON" ]  && echo "AGAA is ON  ($(ls "$ON" | wc -l) yaml files load)"
    [ -d "$OFF" ] && echo "AGAA is OFF (parked at $OFF)"
    ;;
  *)
    echo "usage: $0 off|on|status" >&2; exit 2 ;;
esac
