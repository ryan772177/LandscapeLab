"""Read-only: are chunk-actor tile bytes present inside the RecastNavMesh actor package?
Samples W-byte windows from the tile region of each chunk package and searches the actor bytes.
Negative control: same sampling from non-nav packages of similar size (should not match)."""
import os, io, random
ROOT = r"C:\Users\Admin\UE5LandscapePipeline\LandscapeLab\Content\__ExternalActors__\Alpine8K"
ACTOR = os.path.join(ROOT, r"5\P2\BB9IBCIC8QFTD3SMC11T0V.uasset")
W = 96
PER = 25
random.seed(1234)

def entropy_ok(b):
    return len(set(b)) >= 24  # skip zero runs / low-entropy padding

chunks, others = [], []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith(".uasset"):
            continue
        p = os.path.join(dp, f)
        if p == ACTOR:
            continue
        with io.open(p, "rb") as fh:
            head = fh.read(256 * 1024)
        if b"NavigationDataChunkActor" in head:
            chunks.append(p)
        elif b"RecastNavMesh" not in head and os.path.getsize(p) > 2_000_000:
            others.append(p)

with io.open(ACTOR, "rb") as fh:
    actor = fh.read()
print("actor bytes", len(actor))

def sample(paths, label):
    tried = hit = 0
    per_file_hits = []
    for p in paths:
        with io.open(p, "rb") as fh:
            data = fh.read()
        lo, hi = int(len(data) * 0.10), int(len(data) * 0.95) - W
        h = t = 0
        guard = 0
        while t < PER and guard < PER * 20:
            guard += 1
            o = random.randint(lo, hi)
            win = data[o:o + W]
            if not entropy_ok(win):
                continue
            t += 1
            if actor.find(win) >= 0:
                h += 1
        tried += t
        hit += h
        per_file_hits.append(h)
    print("%-16s files %d  windows %d  found-in-actor %d (%.1f%%)  files with 0 hits: %d" % (
        label, len(paths), tried, hit, 100.0 * hit / max(tried, 1), sum(1 for x in per_file_hits if x == 0)))

sample(chunks, "CHUNK packages")
random.shuffle(others)
sample(others[:20], "NEG CONTROL")
