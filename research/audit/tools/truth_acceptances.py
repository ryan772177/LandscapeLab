"""truth_acceptances.py -- every acceptance taken on a "truth" capture.

READ-ONLY. Audit item 3.

⛔ "TRUTH" NAMES TWO DIFFERENT INSTRUMENTS IN THIS CORPUS, and conflating
them is the whole risk this tool exists to avoid:

  A. `--instrument truth`   EDITOR + HighResShot, all regions force-loaded.
                            NO MoviePipeline at all, so NO GameOverride,
                            so NO LOD0 / HLOD-off / view-distance x50.
                            `bench_capture.py` takes this branch before
                            the MRQ path and returns from it.
  B. `--truth`              MRQ render WITH MoviePipelineGameOverrideSetting.
                            This is the one that carries use_lod_zero,
                            disable_hlods, override_view_distance_scale,
                            texture_streaming DISABLED and the rest.

A sidecar can carry BOTH, ONE, or NEITHER. The contamination question --
"did this acceptance measure LOD, HLOD, cull or draw distance while the
instrument was silently forcing all four?" -- applies to B and NOT to A,
because A never installs the setting. Reporting a single "truth" count
would merge a population that has the defect with one that cannot.

`"truth": null` appears in most sidecars as a DECLARED ABSENCE, so a
grep for the word "truth" over-reports by roughly ten to one. Presence
of the key is not the signal; a non-null value is.
"""
import io
import json
import os
import re

# Subjects for which the GameOverride values are not a detail but the
# measurement itself. An acceptance about draw distance, taken with
# view_distance_scale forced to 50, measured the override.
CONTAMINATION = {
    "lod": re.compile(r"\blod\b|lod_?bias|force_?lod|lod0|screen_?size",
                      re.I),
    "hlod": re.compile(r"hlod", re.I),
    "cull": re.compile(r"cull|cull_?distance", re.I),
    "draw_distance": re.compile(r"draw_?distance|view_?distance|"
                                r"loading_?range|streaming_?range", re.I),
}


def _find_repo(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md above %s" % start)
        d = nd


REPO = _find_repo(__file__)
VERIFY = os.path.join(REPO, "_verify")


def classify(doc, blob):
    """Which truth mechanism, if any, produced this artefact."""
    kinds = []
    if doc.get("instrument") == "truth":
        kinds.append("A:editor+HighResShot (no GameOverride)")
    t = doc.get("truth")
    if isinstance(t, dict) and t:
        kinds.append("B:MRQ --truth (GameOverride INSTALLED)")
    # A sidecar may record the override read-back directly. That is the
    # strongest evidence of B and does not depend on the truth key.
    for j in doc.get("jobs", []) or []:
        if isinstance(j, dict) and j.get("game_overrides_readback"):
            kinds.append("B:MRQ --truth (GameOverride READ BACK)")
            break
    return sorted(set(kinds))


rows = []
for root, dirs, files in os.walk(VERIFY):
    dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
    for f in files:
        if not f.endswith(".json"):
            continue
        p = os.path.join(root, f)
        try:
            blob = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "truth" not in blob.lower():
            continue
        try:
            doc = json.loads(blob)
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        kinds = classify(doc, blob)
        if not kinds:
            continue
        flags = sorted(k for k, rx in CONTAMINATION.items() if rx.search(blob))
        rows.append({
            "sidecar": os.path.relpath(p, REPO).replace("\\", "/"),
            "acceptance": doc.get("tag") or doc.get("_what")
            or os.path.splitext(f)[0],
            "date": doc.get("date") or doc.get("written_utc")
            or os.path.basename(root),
            "profile": doc.get("profile"),
            "instrument": doc.get("instrument"),
            "truth_mechanisms": kinds,
            "subjects_mentioned": flags,
            "git_sha": doc.get("git_sha"),
        })

rows.sort(key=lambda r: (str(r["date"]), r["sidecar"]))
only_b = [r for r in rows
          if any(k.startswith("B:") for k in r["truth_mechanisms"])]
flagged = [r for r in only_b if r["subjects_mentioned"]]

out = {
    "_what": "every _verify artefact produced by a truth capture, split "
             "by WHICH truth instrument",
    "_two_instruments": {
        "A": "--instrument truth: editor + HighResShot, force-loaded. No "
             "MoviePipeline, therefore NO GameOverride. Cannot carry the "
             "LOD0/HLOD-off/view-distance contamination.",
        "B": "--truth: MRQ with MoviePipelineGameOverrideSetting, which "
             "installs use_lod_zero, disable_hlods, "
             "override_view_distance_scale=True + view_distance_scale, "
             "texture_streaming DISABLED, flush_grass_streaming, "
             "flush_streaming_managers, use_high_quality_shadows.",
    },
    "_flag_meaning": "subjects_mentioned lists which of lod / hlod / cull "
                     "/ draw_distance the sidecar's own text mentions. It "
                     "is a TRIAGE SIGNAL, not a verdict: a mention is not "
                     "proof the acceptance measured that subject, and a "
                     "silent sidecar is not proof it did not. Each row "
                     "still needs reading.",
    "n_truth_artefacts": len(rows),
    "n_mechanism_B": len(only_b),
    "n_mechanism_B_mentioning_a_contaminable_subject": len(flagged),
    "rows": rows,
}
dst = os.path.join(REPO, "research", "audit", "inputs",
                   "truth_acceptances.json")
with io.open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)

print("truth artefacts: %d   mechanism B (GameOverride): %d   "
      "B mentioning lod/hlod/cull/draw: %d"
      % (len(rows), len(only_b), len(flagged)))
print("")
print("%-52s %-12s %-9s %s" % ("sidecar", "date", "profile", "subjects"))
for r in only_b:
    print("%-52s %-12s %-9s %s"
          % (r["sidecar"].replace("_verify/bench/", ""), r["date"],
             r["profile"] or "-",
             ",".join(r["subjects_mentioned"]) or "-"))
print("")
print("--- mechanism A only (editor+HighResShot, no GameOverride) ---")
for r in rows:
    if not any(k.startswith("B:") for k in r["truth_mechanisms"]):
        print("  %-50s %s" % (r["sidecar"].replace("_verify/bench/", ""),
                              ",".join(r["subjects_mentioned"]) or "-"))
print("")
print("wrote %s (%d bytes)" % (dst, os.path.getsize(dst)))
