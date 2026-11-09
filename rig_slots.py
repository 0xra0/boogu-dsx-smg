"""Print a weapon rig's slot bones in WEAPON/MESH space.

The .rig stores each bone parent-relative and in its own axis convention (Y up,
Z forward), and `barrel` - the parent of every slot - carries a 180-degree
rotation about (0, 1/root2, 1/root2) that performs the conversion.  Composing
that by hand is how sign errors creep in, so compute it instead of assuming:

    world = R_barrel * T_slot     with R a 180-degree turn about n,
            v' = 2(n.v)n - v

Sanity check built in: scope_slot must come out at (0, +0.1120, +0.0896) and
muzzle_slot at (0, +0.2971, +0.0307), which are the values mag_placement.py has
always used for those two and which are known good in game.

Usage: python3 rig_slots.py RIG.rig [OUT.rig BONE X,Y,Z]
       with the optional args, writes a copy of the rig with BONE moved to the
       given WEAPON-space position.
"""
import json, math, os, shutil, subprocess, sys, tempfile

ROOT = "/mnt/sata/weapon_mod"
RIG = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 3 else None
MOVE_BONE = sys.argv[3] if len(sys.argv) > 3 else None
MOVE_TO = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None


def quat_rot(q, v):
    """rotate v by quaternion q = (i, j, k, r)"""
    i, j, k, r = q
    n = math.sqrt(i * i + j * j + k * k)
    if n < 1e-9:
        return list(v)
    if abs(r) < 1e-6:                       # 180 degrees: v' = 2(n.v)n - v
        ax = (i / n, j / n, k / n)
        d = sum(a * b for a, b in zip(ax, v))
        return [2 * d * ax[c] - v[c] for c in range(3)]
    # general case
    u = (i, j, k)
    dot = sum(a * b for a, b in zip(u, v))
    uu = sum(a * a for a in u)
    cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return [2 * dot * u[c] + (r * r - uu) * v[c] + 2 * r * cr[c] for c in range(3)]


work = tempfile.mkdtemp()
shutil.copy(RIG, work)
base = os.path.basename(RIG)
subprocess.run([f"{ROOT}/wk", "convert", "serialize", work, "-o", work],
               capture_output=True)
jf = os.path.join(work, base + ".json")
doc = json.load(open(jf))
rc = doc["Data"]["RootChunk"]
names = [b.get("$value", b) for b in rc.get("boneNames", [])]
tr = rc.get("boneTransforms", [])
par = rc.get("boneParentIndexes", [])

barrel = names.index("barrel") if "barrel" in names else None
qb = None
if barrel is not None:
    r = tr[barrel].get("Rotation", {})
    qb = (r.get("i", 0), r.get("j", 0), r.get("k", 0), r.get("r", 1))

print(f"{'bone':22} {'rig T (x, up, fwd)':34} weapon-space (x, fwd, up)")
world = {}
for i, n in enumerate(names):
    t = tr[i].get("Translation", {})
    v = (t.get("X", 0.0), t.get("Y", 0.0), t.get("Z", 0.0))
    w = quat_rot(qb, v) if (qb and par[i] == barrel) else list(v)
    world[n] = w
    print(f"  {n:20} ({v[0]:+.4f},{v[1]:+.4f},{v[2]:+.4f})   "
          f"({w[0]:+.4f},{w[1]:+.4f},{w[2]:+.4f})")

ok = True
for bone, want in (("scope_slot", (0.0, 0.1120, 0.0896)),
                   ("muzzle_slot", (0.0, 0.2971, 0.0307))):
    if bone in world:
        got = world[bone]
        if max(abs(got[c] - want[c]) for c in range(3)) > 5e-4:
            ok = False
            print(f"  CHECK FAILED {bone}: got {got}, expected {want}")
print("axis-conversion self-check:", "OK" if ok else "FAILED - do not trust the numbers")

if OUT and MOVE_BONE:
    if MOVE_BONE not in names:
        raise SystemExit(f"{MOVE_BONE} not in {names}")
    idx = names.index(MOVE_BONE)
    # weapon -> rig is the same 180-degree turn (it is its own inverse)
    back = quat_rot(qb, MOVE_TO)
    old = tr[idx]["Translation"]
    print(f"\nmoving {MOVE_BONE}: weapon {world[MOVE_BONE]} -> {MOVE_TO}")
    print(f"  rig T ({old.get('X'):+.5f},{old.get('Y'):+.5f},{old.get('Z'):+.5f})"
          f" -> ({back[0]:+.5f},{back[1]:+.5f},{back[2]:+.5f})")
    old["X"], old["Y"], old["Z"] = back[0], back[1], back[2]
    json.dump(doc, open(jf, "w"))
    subprocess.run([f"{ROOT}/wk", "convert", "deserialize", work], capture_output=True)
    made = os.path.join(work, base)
    if not os.path.exists(made):
        raise SystemExit("deserialize produced no .rig")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    shutil.copy(made, OUT)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
shutil.rmtree(work)
