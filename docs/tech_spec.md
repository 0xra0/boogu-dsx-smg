# Technical Specification: Boogu DS-X Custom Weapon Mod

## 1. Architectural Overview

The **Boogu DS-X** is an original custom Power Submachine Gun mod for *Cyberpunk 2077* (Phantom Liberty / Patch 2.0+), authored using psiberx's **ArchiveXL** and **TweakXL** toolchain.

Rather than overwriting vanilla weapon files or relying on transient script injections, the weapon is built natively on the engine's resource hierarchy:
- Base Frame: Darra Polytechnic DS1 Pulsar (`Items.Preset_Pulsar_Default`)
- Mesh & Materials: Hand-crafted carbon-composite chassis, custom receiver optics rail, custom power cell, extended magazine, custom optic, and suppressor.
- Factory Registration: `weaponset_factory.csv` registered through `weaponset_smg.xl`.
- UI Integration: Custom high-resolution HUD & inventory icon atlas (`weaponset_icon.inkatlas`).
- Localization: Onscreen text definitions registered in `weaponset\smg\local\en-us.json`.

---

## 2. Resource Hierarchy & Archive Layout

The mod archive (`weaponset_smg.archive`) contains 38 compiled resources structured within `weaponset\smg\`:

```
weaponset/smg/
├── weaponset_factory.csv              # Factory mappings for all .app resources
├── weaponset_smg.app                  # Main weapon appearance definitions
├── weaponset_smg.mesh                 # Base SMG chassis mesh
├── weaponset_base1.app                # Weapon body part appearance
├── weaponset_base1.rig                # Armature & bone mappings
├── weaponset_rcv1.app                 # Receiver appearance definition
├── weaponset_mag_std.app              # Standard magazine part appearance
├── weaponset_mag_stdr.app             # Extended magazine part appearance
├── weaponset_mag.mesh                 # Standard magazine mesh
├── weaponset_magr.mesh                # Extended magazine mesh
├── weaponset_mag_shadow.mesh          # Hand-authored magazine shadow caster
├── weaponset_scope.app                # DS-X Optic appearance definition
├── weaponset_scope.mesh               # DS-X Optic mesh
├── weaponset_muzzle.app               # DS-X Suppressor appearance definition
├── weaponset_muzzle.mesh              # DS-X Suppressor mesh
├── materials/
│   ├── body.mi                        # Material instance for SMG receiver / frame
│   ├── mag.mi                         # Material instance for magazine
│   ├── muzzle.mi                      # Material instance for suppressor
│   └── scope.mi                       # Material instance for optic
├── textures/
│   ├── body_d.xbm, body_n.xbm, ...    # Diffuse, Normal, Metalness, Roughness
│   ├── mag_d.xbm, mag_n.xbm, ...
│   ├── muzzle_d.xbm, muzzle_n.xbm, ...
│   └── scope_d.xbm, scope_n.xbm, ...
├── icon/
│   ├── weaponset_icon.inkatlas        # Inkatlas resource referencing slot_01
│   └── weaponset_icon.xbm             # Texture container for HUD and inventory icon
└── local/
    └── en-us.json                     # ArchiveXL onscreen localization JsonResource
```

---

## 3. TweakDB Records & Slot Architecture

### 3.1 Item Identification & Spawning

| Item Record | Display Name | Category | Description |
|---|---|---|---|
| `Items.WeaponSet_SMG` | **Boogu DS-X** | Weapon (Power SMG) | Custom bullpup power SMG frame |
| `Items.WeaponSet_Scope` | **DS-X Optic** | Mod / Scope | Matched carbon-shell long sight |
| `Items.WeaponSet_Muzzle` | **DS-X Suppressor** | Mod / Muzzle | Matched carbon-shell power suppressor |

CET Console spawn commands:
```lua
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG"), 1)
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_Scope"), 1)
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_Muzzle"), 1)
```

### 3.2 The Weapon Assembly Trap & Solution

In the REDengine weapon architecture, a weapon is **not** drawn from its main `.app` alone. 
Every slot in `slotPartListPreset` spawns a discrete part entity built from that part item's own appearance resource. When any attachment (scope, muzzle, mod) is equipped, the engine triggers a complete rebuild of the weapon entity from those part records.

If the stock Pulsar part items remain in `slotPartListPreset`, the engine re-attaches the vanilla Pulsar body and magazine the moment an optic is attached.

**The Solution:**
In `deploy/weaponset_smg.yaml`, we define dedicated part items and override both `slotPartList` and `slotPartListPreset`:
1. `Items.WeaponSet__base1`: Inherits `Items.w_submachinegun__darra_pulsar__base1`, points to `weaponset_base1_app`.
2. `Items.WeaponSet__mag_std`: Points to `weaponset_mag_std_app`.
3. `Items.WeaponSet__mag_stdr`: Points to `weaponset_mag_stdr_app`.
4. The Receiver (`rcv1`) slot is intentionally **not** overridden: in vanilla Pulsar, `w_submachinegun__darra_pulsar__rcv1_01.app` has `components: null` (draws no geometry). Leaving it stock avoids redundant resource evaluations during attachment rebuilds.

### 3.3 Preserving Generic Weapon Mods

Vanilla iconic weapons assign `blueprint: Items.Iconic_Ranged_Weapon_Blueprint`, which limits modding strictly to iconic perks and prevents players from installing standard weapon attachments (e.g., explosive ammo, fire rounds, damage amplifiers).

To give players full customization freedom, `blueprint` is intentionally **not overridden**, inheriting `Items.Base_Power_AR_SMG_LMG_Blueprint`. This preserves:
- Scope slot (`ScopeElement`)
- Muzzle / Power Module slot (`PowerModuleElement`)
- Generic Mod Slot 1 (`Power_AR_SMG_LMG_WeaponMod1Element`)
- Generic Mod Slot 2 (`Power_AR_SMG_LMG_WeaponMod2Element`)

---

## 4. Quality & Stat Randomization Fix

When spawning legendary weapons via script, removing `Items.QualityRandomization` while retaining `Items.ItemPlusRandomizer_MaxQuality` causes an engine hang:
`ItemPlusRandomizer` calculates `+/++` tier modifiers relative to the quality determined by `QualityRandomization`. With `QualityRandomization` stripped, the picker has no bounded baseline quality.

In `weaponset_smg.yaml`, all three stat modifier groups are explicitly mutated:
```yaml
statModifierGroups:
  - !remove Items.QualityRandomization
  - !remove Items.ItemPlusRandomizer_MaxQuality
  - !remove Items.ItemPlusRandomizer_Below_MaxQuality
```
This guarantees deterministic, stable weapon generation without engine crashes.
