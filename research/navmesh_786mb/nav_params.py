"""Read-only: locate the dtNavMeshParams block written at PImplRecastNavMesh.cpp:559-567
(NumTiles i32, orig[3], tileWidth, tileHeight, maxTiles i32, maxPolys i32) by searching for
tileWidth==tileHeight==1596 (84 cells x 19 cm), as double or float, and decode around it."""
import io, struct, sys
P = sys.argv[1]
with io.open(P, "rb") as fh:
    data = fh.read(64 * 1024 * 1024) if len(sys.argv) < 3 else fh.read()
found = 0
for fmt, sz in (("<d", 8), ("<f", 4)):
    pat = struct.pack(fmt, 1596.0) * 2
    i = data.find(pat)
    while i >= 0 and found < 5:
        found += 1
        orig = struct.unpack("<3" + fmt[1], data[i - 3 * sz:i])
        num_tiles = struct.unpack("<i", data[i - 3 * sz - 4:i - 3 * sz])[0]
        max_tiles, max_polys = struct.unpack("<ii", data[i + 2 * sz:i + 2 * sz + 8])
        print("%s at offset %d: NumTiles=%d orig=%s tileW=tileH=1596 maxTiles=%d maxPolys=%d" % (
            fmt, i, num_tiles, orig, max_tiles, max_polys))
        i = data.find(pat, i + 1)
print("matches:", found)
