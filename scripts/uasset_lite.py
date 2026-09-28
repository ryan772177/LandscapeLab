"""uasset_lite.py -- READ-ONLY reader for uncooked UE 5.8 package headers.

Enough of `FPackageFileSummary` to reach the NAME TABLE, plus a scanner for
one exact tagged-property shape. Nothing here writes, and nothing here needs
an editor -- that is the entire point.

⭐ WHY THIS EXISTS. On 2026-09-14 an editor read-back reported 32x32 landscape
HLOD textures for a cell whose build inputs predict 1024, then reported 1024
for the same cell minutes later. Non-negotiable 8 says verify with a DIFFERENT
instrument than the one that made the claim; here the editor IS the claim, so
the second instrument has to be the bytes on disk.

⛔ DO NOT GROW THIS INTO A PACKAGE LOADER. It reads the summary, the name
table, and int32 properties whose tag shape it fully verifies. Anything more
(exports, bulk data, Oodle payloads) belongs in the engine, which already has
a correct implementation.

VERSION CONSTANTS, counted from `ObjectVersion.h:40-109` -- INITIAL_VERSION is
1000 and every subsequent enumerator is +1:

    PACKAGE_SAVED_HASH              = 1016   (FIoHash, 20 bytes, + TotalHeaderSize)
    PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012   (FPropertyTypeName node list)

TAG LAYOUT, from `PropertyTag.cpp:411-500` and `PropertyTypeName.cpp:41-43`:

    Name        FName           8 bytes  (int32 NameIndex, int32 Number)
    TypeName    node list      12 bytes  (FName 8 + int32 InnerCount) per node
    Size        int32           4 bytes
    Flags       EPropertyTagFlags  1 byte
    <value>                     Size bytes

verified against a real package: consecutive `SizeX`/`SizeY` int tags are
exactly 29 bytes apart, and 8 + 12 + 4 + 1 + 4 = 29.
"""
from __future__ import annotations

import struct

PACKAGE_FILE_TAG = 0x9E2A83C1
PACKAGE_SAVED_HASH = 1016


class _R:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.raw(-n * 2).decode("utf-16-le", "replace").rstrip("\x00")
        return self.raw(n).decode("latin-1").rstrip("\x00")


def read_summary(data):
    r = _R(data)
    tag = r.u32()
    if tag != PACKAGE_FILE_TAG:
        raise ValueError(f"not a UE package (tag 0x{tag:08X})")
    s = {}
    legacy = r.i32()
    s["LegacyFileVersion"] = legacy
    if legacy >= 0:
        raise ValueError("UE3-era package")
    if legacy != -4:
        r.i32()                       # LegacyUE3Version, unused
    s["FileVersionUE4"] = r.i32()
    s["FileVersionUE5"] = r.i32() if legacy <= -8 else 0
    s["FileVersionLicenseeUE4"] = r.i32()

    if s["FileVersionUE5"] >= PACKAGE_SAVED_HASH:
        s["SavedHash"] = r.raw(20).hex()
        s["TotalHeaderSize"] = r.i32()

    n = r.i32()                       # custom versions, "Optimized" format
    if not (0 <= n < 500):
        raise ValueError(f"implausible custom version count {n}")
    s["NumCustomVersions"] = n
    r.p += n * 20                     # FGuid(16) + int32 Version

    if s["FileVersionUE5"] < PACKAGE_SAVED_HASH:
        s["TotalHeaderSize"] = r.i32()

    s["PackageName"] = r.fstring()
    s["PackageFlags"] = r.u32()
    s["NameCount"] = r.i32()
    s["NameOffset"] = r.i32()
    return s


def read_names(data, summary):
    """FNameEntrySerialized = FString + uint16 hash + uint16 hash."""
    r = _R(data, summary["NameOffset"])
    names = []
    for _ in range(summary["NameCount"]):
        nm = r.fstring()
        r.u16()
        r.u16()
        names.append(nm)
    return names


def name_index(names, want):
    for i, n in enumerate(names):
        if n == want:
            return i
    return None


def find_int_properties(data, names, prop_name):
    """Every int32 tagged property called `prop_name`, as (offset, value).

    The whole 25-byte tag prefix is verified -- name, type `IntProperty`,
    InnerCount 0, Size 4, Flags 0 -- so a coincidental byte match is rejected
    rather than reported. Returns [] when the name is not in the table.
    """
    ni = name_index(names, prop_name)
    ti = name_index(names, "IntProperty")
    if ni is None or ti is None:
        return []

    prefix = struct.pack("<iiiiii", ni, 0, ti, 0, 0, 4)   # 24 bytes
    out, pos = [], 0
    while True:
        off = data.find(prefix, pos)
        if off < 0:
            return out
        pos = off + 1
        if off + 29 > len(data):
            continue
        if data[off + 24] != 0x00:                        # Flags must be None
            continue
        out.append((off, struct.unpack_from("<i", data, off + 25)[0]))


def find_double_properties(data, names, prop_name):
    """Every `DoubleProperty` called `prop_name`, as (offset, value).

    Same verified-prefix discipline as `find_int_properties`; only the type
    name and the payload width differ (8 bytes, so the record is 33 not 29).

    ⛔ TYPE IS NOT GUESSABLE FROM THE NAME. `UHLODLayer::LoadingRange` is a
    `double` and `CellSize` is an `int32` (`HLODLayer.h:127,131`), and an
    int32 scan over LoadingRange reports "not found" -- which reads as
    "absent" rather than "wrong reader". Check the header.
    """
    ni = name_index(names, prop_name)
    ti = name_index(names, "DoubleProperty")
    if ni is None or ti is None:
        return []

    prefix = struct.pack("<iiiiii", ni, 0, ti, 0, 0, 8)   # 24 bytes
    out, pos = [], 0
    while True:
        off = data.find(prefix, pos)
        if off < 0:
            return out
        pos = off + 1
        if off + 33 > len(data):
            continue
        if data[off + 24] != 0x00:                        # Flags must be None
            continue
        out.append((off, struct.unpack_from("<d", data, off + 25)[0]))


def texture_source_dims(path):
    """(SizeX, SizeY) for every FTextureSource in the package, in file order."""
    with open(path, "rb") as fh:
        data = fh.read()
    summary = read_summary(data)
    names = read_names(data, summary)
    xs = find_int_properties(data, names, "SizeX")
    ys = find_int_properties(data, names, "SizeY")
    return [(x[1], y[1]) for x, y in zip(xs, ys)], summary, names
