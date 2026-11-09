# Diagnostic Ladder & Bisect Methodology

## 1. The Equip Freeze Problem

During custom weapon development in REDengine, authoring errors across 3D meshes, CR2W chunk tables, or TweakDB records often manifest identically: **a hard GameThread hang on equip**.

The engine watchdog triggers at 120 seconds, spinning `GameThread` at 100% CPU utilization while waiting on corrupted chunk data, infinite dependency loops, or unresolved part entities.

To eliminate multi-day guesswork, the project incorporates:
1. Automated offline acceptance checks (`check_meshes.sh` and `check_refs.py`).
2. A formal in-game **4-rung diagnostic ladder** defined in `deploy/weaponset_smg.yaml`.

---

## 2. The 4 Diagnostic Tiers

Each tier differs from its predecessor by exactly one architectural layer. By equipping each item sequentially in the CET console, developers can pinpoint the root cause in minutes:

```
[Items.WeaponSet_Test]  Control (stock Pulsar, no custom assets)
         │
         ▼ (freezes -> issue outside our mod)
[Items.WeaponSet_SMG_A] Appearance Only (our .app, stock slots)
         │
         ▼ (freezes -> fault in weaponset_smg.app or base .mesh)
[Items.WeaponSet_SMG_C] Hand-Authored Arrays (custom slot arrays, stock parts)
         │
         ▼ (freezes -> YAML syntax error, $base resolution, or inline mapping)
[Items.WeaponSet_SMG_B] Custom Part Items (our body/mags, stock Pulsar attachments)
         │
         ▼ (freezes -> fault in part .app or part .mesh rebuild)
[Items.WeaponSet_SMG]   Full Weapon (custom weapon + custom scope + custom muzzle)
```

### CET Console Equipping Commands

```lua
-- Rung 0: Control
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_Test"), 1)

-- Rung 1: Appearance isolation
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG_A"), 1)

-- Rung 2: YAML slot structure verification
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG_C"), 1)

-- Rung 3: Part item rebuild isolation
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG_B"), 1)

-- Target: Production Weapon
Game.GetTransactionSystem():GiveItem(Game.GetPlayer(), ItemID.FromTDBID("Items.WeaponSet_SMG"), 1)
```

---

## 3. Shipped Mesh Acceptance Gate (`check_meshes.sh`)

REDengine meshes authored via glTF import can silently generate zero-length vertex/index buffers inside the render blob. The file passes standard header and CR2W sanity checks, but crashes the rendering pipeline on load.

`check_meshes.sh` tests round-trip export via WolvenKit CLI before packing:
```bash
./check_meshes.sh depot_v2/weaponset/smg
```

If WolvenKit throws `byteLength 0 must be greater than or equal to 1`, the mesh is rejected and quarantined before an archive is compiled.

---

## 4. Reference Integrity Validation (`check_refs.py`)

`check_refs.py` parses all `.app`, `.csv`, `.mesh`, and `.json` references inside the packed `.archive` to ensure zero missing dependencies or unresolved CRUID hashes.
