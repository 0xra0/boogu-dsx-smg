"""Give every component in our .app files its own unique CRUID.

WHY (measured 2026-07-30, and it reverses an earlier note in this repo):

The build the user confirmed working in game on 2026-07-26
(`deploy/weaponset_smg.m1v2.archive.bak`) and the build that freezes on equip are
byte-identical except for one thing - every component id.  Unbundled and compared:

    weaponset_smg.app        17 comps   GOOD 0/17 ids shared with donor   NOW 17/17
    weaponset_base1.app       9 comps   GOOD 0/9                          NOW 9/9
    weaponset_mag_std.app     4 comps   GOOD 0/4                          NOW 4/4
    weaponset_mag_stdr.app    2 comps   GOOD 0/2                          NOW 2/2

    GOOD: 32 ids total, 32 distinct - nothing shared with the donor and nothing
          shared between our own apps either.

The "always copy the donor's CRUIDs verbatim" rule this repo recorded on 07-30 was
drawn from a confounded measurement: EVERY CRUID variant tested that day also
carried the `!remove Items.QualityRandomization` bug, so every one of them froze
regardless of its ids.  With that bug fixed, the plain clone (Items.WeaponSet_Test)
equips fine and Items.WeaponSet_SMG_A - which is that clone plus nothing but
`appearanceResourceName` -> our .app - still freezes.  So the .app is a second,
independent fault, and the only configuration of it ever observed to work is the
all-unique one above.

Mechanically that fits: WeaponSet_SMG_A leaves the slots stock, so the DONOR's part
entities (base1/mag_std/mag_stdr) join the graph alongside our weapon appearance.
If our appearance declares the same component ids as those donor part apps, one
entity graph ends up holding duplicate component ids for resources we do not own.
Seijax can share ids safely because it replaces all four part apps, so the donor's
never load beside it.

If part geometry later misbehaves visually (the stock body snapping back when
something is attached), the next thing to try is sharing ids between OUR weapon app
and OUR part apps - never with the donor.

CRUIDs live in three places per appearance and all three must agree:
    appearances[].components[].id
    appearances[].compiledData.Data.Chunks[].id
    appearances[].compiledData.Data.CruidDict   (index -> id)
"""
import glob, json, os, sys

DEPOT = "/mnt/sata/weapon_mod/depot_v2/weaponset/smg"
DONOR = "/mnt/sata/weapon_mod/donor/cooked/base/weapons/firearms/smg/darra_pulsar"


def fnv1a64(s):
    h = 0xCBF29CE484222325
    for c in s.encode():
        h = ((h ^ c) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def val(x):
    return x.get("$value") if isinstance(x, dict) else x


def donor_ids():
    """every component id used by the donor weapon and its part apps"""
    ids = set()
    for p in glob.glob(DONOR + "/**/*.app.json", recursive=True):
        r = json.load(open(p))["Data"]["RootChunk"]
        for a in r.get("appearances", []):
            a = a.get("Data", a)
            for c in a.get("components") or []:
                c = c.get("Data", c)
                ids.add(str(val(c.get("id"))))
    return ids


def main():
    banned = donor_ids()
    print(f"donor component ids to avoid: {len(banned)}")
    assigned = {}
    total = 0

    for path in sorted(glob.glob(DEPOT + "/*.app.json")):
        base = os.path.basename(path)
        doc = json.load(open(path))
        root = doc["Data"]["RootChunk"]
        changed = 0

        for a in root.get("appearances", []):
            a = a.get("Data", a)
            aname = str(val(a.get("name")))
            comps = a.get("components") or []
            remap = {}

            for i, c in enumerate(comps):
                cd = c.get("Data", c)
                old = str(val(cd.get("id")))
                cname = str(val(cd.get("name")))
                # deterministic, unique per (file, appearance, slot, name)
                new = str(fnv1a64(f"weaponset|{base}|{aname}|{i}|{cname}"))
                assert new not in banned, f"generated id collides with donor: {new}"
                assert new not in assigned, f"generated id collides with {assigned[new]}"
                assigned[new] = f"{base}:{aname}:{cname}"
                remap[old] = new
                if isinstance(cd.get("id"), dict):
                    cd["id"]["$value"] = new
                else:
                    cd["id"] = new
                changed += 1

            comp = a.get("compiledData")
            if isinstance(comp, dict) and isinstance(comp.get("Data"), dict):
                data = comp["Data"]
                for ch in data.get("Chunks", []):
                    old = str(val(ch.get("id")))
                    if old in remap:
                        if isinstance(ch.get("id"), dict):
                            ch["id"]["$value"] = remap[old]
                        else:
                            ch["id"] = remap[old]
                cdict = data.get("CruidDict")
                if isinstance(cdict, dict):
                    for k, v in list(cdict.items()):
                        if str(v) in remap:
                            cdict[k] = remap[str(v)]

        json.dump(doc, open(path, "w"), indent=2)
        total += changed
        print(f"  {base:28} {changed:2} component ids regenerated")

    print(f"\n{total} ids rewritten, {len(assigned)} distinct, 0 shared with the donor")


if __name__ == "__main__":
    sys.exit(main())
