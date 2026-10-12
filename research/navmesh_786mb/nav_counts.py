"""Read-only. Actor: NavMeshVersion i32, SizeBytes u32, NumTiles i32 (RecastNavMesh.cpp:1308-1316, PImpl :559).
Chunk: NavMeshVersion i32, SizeBytes i64, TileNum i32 (RecastNavMeshDataChunk.cpp:101-106,158).
Sum TileNum over chunk packages; header match requires SizeBytes within file and > 4."""
import io, os, struct
ROOT = r"C:\Users\Admin\UE5LandscapePipeline\LandscapeLab\Content\__ExternalActors__\Alpine8K"
ACTOR = os.path.join(ROOT, r"5\P2\BB9IBCIC8QFTD3SMC11T0V.uasset")
with io.open(ACTOR, "rb") as fh:
    head = fh.read(8192)
off = 4260 - 3 * 8 - 4  # NumTiles offset found by nav_params.py
ver, sizeb, ntiles = struct.unpack("<iIi", head[off - 8:off + 4])
print("actor: NavMeshVersion=%d SizeBytes=%d (%.2f MB) NumTiles=%d; file=%d" % (ver, sizeb, sizeb / 1048576, ntiles, os.path.getsize(ACTOR)))
vpat = struct.pack("<i", ver)
tot_tiles = 0; tot_blob = 0; n = 0; bad = []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith(".uasset"):
            continue
        p = os.path.join(dp, f)
        with io.open(p, "rb") as fh:
            data = fh.read()
        if b"NavigationDataChunkActor" not in data[:262144]:
            continue
        n += 1
        hits = []
        i = data.find(vpat)
        while i >= 0:
            sz, tn = struct.unpack("<qi", data[i + 4:i + 16])
            if 4 < sz <= len(data) - i and 0 < tn < 100000 and sz > len(data) * 0.5:
                hits.append((i, sz, tn))
            i = data.find(vpat, i + 1)
        if len(hits) != 1:
            bad.append((p, hits))
            continue
        tot_tiles += hits[0][2]; tot_blob += hits[0][1]
print("chunk packages %d, decoded %d, ambiguous %d" % (n, n - len(bad), len(bad)))
print("chunk TileNum total %d, nav blob total %.2f MB" % (tot_tiles, tot_blob / 1048576))
for p, h in bad[:5]:
    print("  ambiguous", p, h[:4])
