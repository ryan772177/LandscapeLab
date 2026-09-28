"""Do the SAVED BYTES carry the Nanite state?

Reads the .uasset files on disk directly. That is a DIFFERENT
REPRESENTATION from the live editor (which is where every other check so
far has looked) and from the filesystem mtime. Pass 1 sat recorded as
"saved and verified" for three days on side-records exactly like mtimes.

POSITIVE CONTROL FIRST, and it is the point of the script: a search that
finds a token everywhere proves nothing unless it is also shown to be
ABSENT where it should be. So the same scan runs over actor packages that
are NOT landscape proxies, and those must come back clean.
"""
import os, re, subprocess, sys

REPO = r"C:\Users\Admin\UE5LandscapePipeline"
ACTORS = os.path.join(REPO, "LandscapeLab", "Content", "__ExternalActors__", "Alpine")

TOKENS = [b"LandscapeNaniteMesh", b"bEnableNanite", b"LandscapeNaniteComponent"]

# The packages the save touched, from the commit we just made (count printed
# below -- not hardcoded, so it tracks whatever HEAD actually wrote).
out = subprocess.run(
    ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
    cwd=REPO, capture_output=True, text=True).stdout
saved = [p.strip() for p in out.splitlines()
         if "__ExternalActors__" in p and p.strip().endswith(".uasset")]
saved_abs = {os.path.normcase(os.path.join(REPO, p.replace("/", os.sep)))
             for p in saved}
print("packages written by the save :", len(saved_abs))

all_pkgs = []
for root, _dirs, files in os.walk(ACTORS):
    for f in files:
        if f.endswith(".uasset"):
            all_pkgs.append(os.path.join(root, f))
print("total actor packages on disk :", len(all_pkgs))

controls = [p for p in all_pkgs
            if os.path.normcase(p) not in saved_abs]
print("control set (NOT saved)      :", len(controls))
print()


def hits(path):
    try:
        with open(path, "rb") as fh:
            b = fh.read()
    except Exception:
        return None
    return {t.decode(): b.count(t) for t in TOKENS}


def summarise(label, paths, limit=None):
    n = 0
    withtok = 0
    unreadable = 0
    per = {t.decode(): 0 for t in TOKENS}
    sample = paths if limit is None else paths[:limit]
    for p in sample:
        h = hits(p)
        n += 1
        if h is None:
            unreadable += 1
            continue
        if any(v > 0 for v in h.values()):
            withtok += 1
        for k, v in h.items():
            if v:
                per[k] += 1
    print("%-28s scanned %5d   carrying a Nanite token %5d   unreadable %d"
          % (label, n, withtok, unreadable))
    for k, v in per.items():
        print("      %-28s present in %5d" % (k, v))
    return withtok, n, unreadable


print("=== THE SAVED PACKAGES (expect: Nanite tokens present) ===")
w_s, n_s, u_s = summarise("saved by this operation", sorted(saved_abs))
print()
print("=== POSITIVE CONTROL: packages the save did NOT touch ===")
print("    (EVERY non-saved actor package under this dir -- may include")
print("     foliage/rock actors, and if a second landscape's proxies live")
print("     here they would carry the token and BREAK this control; all")
print("     scanned must be CLEAN, or the token is noise)")
CONTROL_CAP = 400
w_c, n_c, u_c = summarise("not saved", sorted(controls), limit=CONTROL_CAP)
print()

# NN13 / rule 13: a verdict needs a non-empty, FULLY-scanned sample on both
# arms; a zero or partial count REFUSES rather than passing.
if n_s == 0:
    print("REFUSE: 0 saved packages to check. This reads `git show HEAD`, so "
          "run it ON the save commit whose packages it verifies -- a PASS over "
          "zero saved packages is not 'the bytes carry Nanite'.")
    sys.exit(2)
if u_s:
    print("REFUSE: %d of %d saved packages were UNREADABLE; whether they carry "
          "the state is unknown, which is not a pass." % (u_s, n_s))
    sys.exit(2)
if len(controls) > n_c:
    print("REFUSE: %d control packages exist but only %d were scanned (cap "
          "%d). 'absent from EVERY control' cannot be claimed over a sample -- "
          "raise CONTROL_CAP to cover them all."
          % (len(controls), n_c, CONTROL_CAP))
    sys.exit(2)

ok = (w_s == n_s) and (w_c == 0)
print("VERDICT:", "the saved bytes carry the Nanite MARKERS (token PRESENCE, "
      "not a decode of the enabled-flag VALUE) and the markers are "
      "discriminating (absent from all %d controls)" % n_c
      if ok else
      "INCONCLUSIVE — see the counts above")
sys.exit(0 if ok else 1)
