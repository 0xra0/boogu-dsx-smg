# Development Toolchain & Build Pipeline

## 1. Overview of Automation Scripts

The repository includes a suite of Python and Bash utilities for managing the weapon lifecycle:

| Script | Purpose |
|---|---|
| `pack_deploy.sh` | Runs mesh validation, purges WolvenKit sidecars, packs `depot_v2` into `.archive`, verifies references, and deploys to game. |
| `check_meshes.sh` | Acceptance test validating round-trip glTF export for all `.mesh` files. |
| `check_refs.py` | Validates archive file table and internal `.app` resource references. |
| `build_localization.py` | Compiles onscreen JSON resource for ArchiveXL translation keys. |
| `build_icon.py` | Generates inkAtlas XML/JSON records for the inventory icon atlas. |
| `build_base_mesh.py` | Extracts donor mesh headers, bounding boxes, and bone indices to create valid base geometry. |
| `build_apps_v2.py` | Configures `.app` definitions, appearances, components, and material assignments. |
| `audit_final.py` | Blender Python script auditing exported `.glb` files for degenerate triangles, UV errors, and 16-bit vertex index overflow. |
| `tweakdb_read.py` | Reads and verifies Pulsar vanilla slot records out of `tweakdb.bin`. |
| `mod_toggle.sh` | Quick toggle script to enable/disable mod files in the game directory. |

---

## 2. Build & Deploy Workflow

To compile the depot and deploy directly into Cyberpunk 2077:

```bash
# Standard build and deployment to archive/pc/mod/
./pack_deploy.sh

# Pack only without touching the game installation
./pack_deploy.sh --pack

# Hot-reload mode using RedHotTools
./pack_deploy.sh hot
```

### Hot-Reload Development with RedHotTools

When running `./pack_deploy.sh hot`, the archive is copied to `archive/pc/hot/`. 
The `RedHotTools` ArchiveWatcher automatically unloads old archives, moves the new file into `archive/pc/mod/`, flushes the resource cache, and reloads without needing to restart the game executable.

To reload YAML tweaks in the running game:
```lua
TweakXL.Reload()
```
Then drop and re-equip the weapon to rebuild the entity from updated geometry.
