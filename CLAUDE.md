# CLAUDE.md — Agent & Developer Instructions

## Project Overview
**Boogu DS-X** (`boogu-dsx-smg`) is a custom bullpup Power Submachine Gun mod for *Cyberpunk 2077* (Patch 2.0+ / Phantom Liberty). It provides custom 3D models, textures, animations rig bindings, custom magazine, custom scope, custom suppressor, and inventory icons using ArchiveXL and TweakXL.

> **Project Status**: Work In Progress (WIP) — Development Paused / On Hold. The repository is preserved as a clean reference snapshot and working build.

---

## Key Item Records & CET Commands

- Weapon: `Items.WeaponSet_SMG` (Boogu DS-X SMG)
- Scope: `Items.WeaponSet_Scope` (DS-X Optic)
- Muzzle: `Items.WeaponSet_Muzzle` (DS-X Suppressor)

Spawn items in the Cyber Engine Tweaks console (one line each):
```lua
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG"), 1)
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_Scope"), 1)
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_Muzzle"), 1)
```

---

## Directory Layout
- `mod/`: Production-ready mod files formatted for direct deployment (`archive/pc/mod/` and `r6/tweaks/`).
- `depot_v2/`: Active WolvenKit project depot containing all source `.mesh`, `.app`, `.xbm`, `.mi`, `.rig`, and `.json` resources.
- `preview/`: High-resolution render previews and contact sheets.
- `docs/`: Technical specifications, diagnostic ladder, and toolchain guides.
- `models/images/`: 2D/3D visual reference designs.

---

## Essential Commands & Tooling

- Mesh validation gate: `./check_meshes.sh depot_v2/weaponset/smg`
- Reference audit: `python3 check_refs.py mod/archive/pc/mod/weaponset_smg.archive depot_v2`
- Rebuild & deploy archive: `./pack_deploy.sh`
- Hot-reload via RedHotTools: `./pack_deploy.sh hot`
- Diagnostic ladder item spawning: See `docs/diagnostic_ladder.md`

---

## Technical Architecture Rules
1. **Never override blueprint with iconic blueprint**: Retain `Items.Base_Power_AR_SMG_LMG_Blueprint` to preserve generic mod attachment slots.
2. **Rebuild-from-parts safety**: When editing slot geometry, always override both `slotPartList` and `slotPartListPreset` to prevent stock Pulsar mesh re-attachment.
3. **Stat modifier groups**: Strip `QualityRandomization`, `ItemPlusRandomizer_MaxQuality`, and `ItemPlusRandomizer_Below_MaxQuality` in lockstep to avoid `+/++` calculation hangs on Legendary generation.
4. **Mesh bounds and vert count**: Ensure mesh chunks never exceed 65,535 vertices (`IBCT_IndexUShort`).
