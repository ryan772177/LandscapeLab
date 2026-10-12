"""Read-only: classify navigation packages under __ExternalActors__/Alpine8K by content signature."""
import os, io, sys, time, struct
ROOT = r"C:\Users\Admin\UE5LandscapePipeline\LandscapeLab\Content\__ExternalActors__\Alpine8K"
HEAD = 256 * 1024
CHUNK = b"NavigationDataChunkActor"
NAV = b"RecastNavMesh"

chunks, navs, other_nav = [], [], []
n = 0
total = 0
t0 = time.time()
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith(".uasset"):
            continue
        p = os.path.join(dp, f)
        n += 1
        sz = os.path.getsize(p)
        total += sz
        with io.open(p, "rb") as fh:
            head = fh.read(HEAD)
        if CHUNK in head:
            chunks.append((p, sz, os.path.getmtime(p)))
        elif NAV in head:
            navs.append((p, sz, os.path.getmtime(p), head))
print("scanned %d .uasset files, %.2f GB, %.1f s" % (n, total / 1e9, time.time() - t0))
print("chunk-actor packages (signature %r): %d, total %.2f MB (%d bytes)" % (CHUNK, len(chunks), sum(s for _, s, _ in chunks) / 1048576, sum(s for _, s, _ in chunks)))
if chunks:
    ss = sorted(s for _, s, _ in chunks)
    print("  min %.1f KB  median %.1f KB  max %.1f KB" % (ss[0] / 1024, ss[len(ss) // 2] / 1024, ss[-1] / 1024))
    mts = sorted(m for _, _, m in chunks)
    print("  mtime range %s .. %s" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(mts[0])), time.strftime("%Y-%m-%d %H:%M", time.localtime(mts[-1]))))
print("non-chunk packages containing %r: %d" % (NAV, len(navs)))
for p, s, m, head in navs:
    # print the distinct ascii tokens around RecastNavMesh to show the class
    toks = set()
    i = head.find(NAV)
    while i >= 0 and len(toks) < 12:
        j = i
        while j > 0 and 32 < head[j - 1] < 127:
            j -= 1
        k = i
        while k < len(head) and 32 < head[k] < 127:
            k += 1
        toks.add(head[j:k].decode("ascii", "replace"))
        i = head.find(NAV, i + 1)
    print("  %s  %.2f MB (%d bytes)  mtime %s" % (p, s / 1048576, s, time.strftime("%Y-%m-%d %H:%M", time.localtime(m))))
    print("     tokens:", sorted(toks))
    for extra in (b"bIsWorldPartitioned", b"TilePoolSize", b"bFixedTilePoolSize", b"RuntimeGeneration"):
        print("     name %-22s in head: %s" % (extra.decode(), extra in head))
