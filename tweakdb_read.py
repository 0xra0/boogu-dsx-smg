"""Minimal offline reader for Cyberpunk's r6/cache/tweakdb*.bin.

TweakDB record/flat names are stored only as hashes, so the game database cannot
be inspected with `strings`.  This is a port of the parts of WolvenKit's
WolvenKit.RED4/TweakDB/TweakDBReader.cs we need: the flat pool (grouped by type,
each group holding a value list plus name-hash -> value-index keys) and the
record pool.  Names are resolved by hashing candidates from CET's tweakdbstr
dictionary (see build of tweakdbstr.txt) rather than the other way round -
TweakDBID = crc32(name) | len(name) << 32.

Usage:
    python3 tweakdb_read.py <record-or-flat name> [...]
    python3 tweakdb_read.py --record Items.Preset_Pulsar_Default   # all its flats
"""
import struct, sys, zlib, functools

BIN = "/mnt/ssd/Cyberpunk 2077/game/prefix/drive_c/game/r6/cache/tweakdb_ep1.bin"
NAMES = "/tmp/claude-1000/-mnt-sata-ComfyUI/77f8b56b-4b89-419d-a410-234edf270702/scratchpad/tweakdbstr.txt"


def tdbid(name: str) -> int:
    b = name.encode()
    return (zlib.crc32(b) & 0xFFFFFFFF) | (len(b) << 32)


def fnv1a64(s: str) -> int:
    h = 0xCBF29CE484222325
    for c in s.encode():
        h = ((h ^ c) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# red type name -> how to read one value
SIMPLE = {
    "CName": "str", "String": "str", "TweakDBID": "u64", "raRef:CResource": "u64",
    "Float": "f32", "Bool": "b", "Uint8": "u8", "Uint16": "u16", "Uint32": "u32",
    "Uint64": "u64", "Int8": "i8", "Int16": "i16", "Int32": "i32", "Int64": "i64",
    "Color": "col", "EulerAngles": "f32x3", "Quaternion": "f32x4",
    "Vector2": "f32x2", "Vector3": "f32x3", "gamedataLocKeyWrapper": "u64",
}
TYPES = {}
for n, k in SIMPLE.items():
    TYPES[fnv1a64(n)] = (n, k, False)
    TYPES[fnv1a64("array:" + n)] = ("array:" + n, k, True)


class R:
    def __init__(self, d, p=0):
        self.d, self.p = d, p

    def take(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v

    def u8(self):  return self.take(1)[0]
    def i8(self):  return struct.unpack("<b", self.take(1))[0]
    def u16(self): return struct.unpack("<H", self.take(2))[0]
    def i16(self): return struct.unpack("<h", self.take(2))[0]
    def u32(self): return struct.unpack("<I", self.take(4))[0]
    def i32(self): return struct.unpack("<i", self.take(4))[0]
    def u64(self): return struct.unpack("<Q", self.take(8))[0]
    def i64(self): return struct.unpack("<q", self.take(8))[0]
    def f32(self): return struct.unpack("<f", self.take(4))[0]
    def b(self):   return bool(self.take(1)[0])
    def col(self): return tuple(self.take(4))
    def f32x2(self): return (self.f32(), self.f32())
    def f32x3(self): return (self.f32(), self.f32(), self.f32())
    def f32x4(self): return (self.f32(), self.f32(), self.f32(), self.f32())

    def vlq(self):
        b = self.u8()
        neg = b & 0x80
        v = b & 0x3F
        if b & 0x40:
            for shift in (6, 13, 20, 27):
                b = self.u8()
                v |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
        return -v if neg else v

    def string(self):
        n = self.vlq()
        if n == 0:
            return ""
        if n > 0:
            return self.take(n * 2).decode("utf-16-le")
        return self.take(-n).decode("utf-8", "replace")

    def value(self, kind):
        return self.string() if kind == "str" else getattr(self, kind)()


def load(path=BIN):
    d = open(path, "rb").read()
    r = R(d)
    magic = r.u32()
    blob, parser, chk = r.i32(), r.i32(), r.u32()
    flats_off, recs_off, q_off, gt_off = r.i32(), r.i32(), r.i32(), r.i32()

    flats = {}          # name hash -> (type name, value)
    r.p = flats_off
    groups = [tuple(struct.unpack("<QIII", r.take(20))) for _ in range(r.i32())]
    for type_hash, n_val, n_key, off in groups:
        if type_hash not in TYPES:
            continue
        tname, kind, is_arr = TYPES[type_hash]
        g = R(d, off)
        vals = []
        for _ in range(g.u32()):
            if is_arr:
                vals.append([g.value(kind) for _ in range(g.vlq())])
            else:
                vals.append(g.value(kind))
        for _ in range(g.u32()):
            k = g.u64(); idx = g.i32()
            flats[k] = (tname, vals[idx])

    r.p = recs_off
    records = {}
    for _ in range(r.i32()):
        rid = r.u64(); key = r.u32()
        records[rid] = key
    return flats, records


@functools.lru_cache(maxsize=1)
def name_table():
    """hash -> name, for every string CET knows about."""
    t = {}
    with open(NAMES, "rb") as f:
        for line in f:
            s = line.rstrip(b"\n").decode("utf-8", "ignore")
            if s:
                t[tdbid(s)] = s
    return t


def show(flats, records, name, resolve=True):
    names = name_table() if resolve else {}
    h = tdbid(name)
    if h in flats:
        t, v = flats[h]
        if t.endswith("TweakDBID"):
            v = [names.get(x, hex(x)) for x in v] if isinstance(v, list) else names.get(v, hex(v))
        print(f"  {name} = ({t}) {v}")
        return True
    if h in records:
        print(f"  {name}  [record]")
        return True
    return False


if __name__ == "__main__":
    args = sys.argv[1:]
    flats, records = load()
    print(f"{len(flats)} flats, {len(records)} records from {BIN}", file=sys.stderr)
    if args and args[0] == "--record":
        base = args[1]
        prefix = base + "."
        for s in open(NAMES, "rb"):
            s = s.rstrip(b"\n").decode("utf-8", "ignore")
            if s.startswith(prefix):
                show(flats, records, s)
    else:
        for a in args:
            if not show(flats, records, a):
                print(f"  {a}  -- not found")


def murmur3(data: bytes, seed: int) -> int:
    c1, c2 = 0xCC9E2D51, 0x1B873593
    h = seed & 0xFFFFFFFF
    n = len(data) // 4 * 4
    for i in range(0, n, 4):
        k = int.from_bytes(data[i:i + 4], "little")
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    k = 0
    for i, b in enumerate(data[n:]):
        k |= b << (8 * i)
    if k:
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


@functools.lru_cache(maxsize=1)
def record_types():
    """record type key (murmur3 of the gamedata<X>_Record infix) -> X"""
    import glob, os
    out = {}
    for p in glob.glob("/mnt/sata/WolvenKit/WolvenKit.RED4/Types/Classes/gamedata*_Record.cs"):
        n = os.path.basename(p)[len("gamedata"):-len("_Record.cs")]
        out[murmur3(n.encode(), 0x5EEDBA5E)] = n
    return out
