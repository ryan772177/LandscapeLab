"""apply_streaming_range.py — the runtime grid ranges, from the recipe.

Brief 3 Task 0 (RULED, BRIEF 3 sec 3.3). Reads recipe `streaming`
(main/instanced/merged loading ranges in cm), applies them to the three
URuntimePartitionLHGrid objects by PROPERTY SIGNATURE, reads back, saves
the map package (the hash set lives inside WorldSettings), and commits it
-- the R-LIGHTSAVE unit: apply -> read back -> save -> commit, owned by
the applying tool. Verdict from the filesystem, not the editor's reply.

⚠ ALPINE8K-ONLY: only the three range NUMBERS come from `--recipe`; the target
level (/Game/Alpine8K) and the map package (MAP_FILE) are hardcoded here and in
the payload's level gate. `--recipe` for another world would be refused at that
gate. The engine read-back is IN MEMORY (the same object just set); persistence
is proven by the git filesystem delta below, not by re-reading the saved value.

  python scripts/apply_streaming_range.py [--recipe recipes/alpine_8k.json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

REPO = bootstrap.REPO_ROOT
MAP_FILE = "LandscapeLab/Content/Alpine8K.umap"


def _git_touched():
    try:
        out = subprocess.run(
            ["git", "status", "--short", "-uall", "--", "LandscapeLab/Content"],
            cwd=REPO, capture_output=True, text=True, timeout=120)
        return {ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--timeout", type=float, default=25.0)
    a = ap.parse_args(argv)

    with open(os.path.join(REPO, a.recipe), encoding="utf-8-sig") as fh:
        rec = json.load(fh)
    st = rec.get("streaming")
    if not st:
        print("REFUSE: recipe has no `streaming` block.")
        return 2
    _need = ("main_loading_range_cm", "hlod_instanced_loading_range_cm",
             "hlod_merged_loading_range_cm")
    _missing = [k for k in _need if k not in st]
    if _missing:
        print("REFUSE: recipe streaming block missing %s." % _missing)
        return 2
    subs = {"MAIN_CM": str(int(st["main_loading_range_cm"])),
            "INST_CM": str(int(st["hlod_instanced_loading_range_cm"])),
            "MERGED_CM": str(int(st["hlod_merged_loading_range_cm"]))}
    print("targets: main %(MAIN_CM)s  instanced %(INST_CM)s  "
          "merged %(MERGED_CM)s cm" % subs)

    with open(os.path.join(REPO, "scripts", "payloads",
                           "apply_streaming_range.py"), encoding="utf-8") as fh:
        text = fh.read()
    for k, v in subs.items():
        text = text.replace("__" + k + "__", v)

    fs_before = _git_touched()
    code, d, raw = ue_exec.run(text, marker="__LL__", timeout=a.timeout,
                               stage_name="ll_apply_range", quiet=True)
    if d is None or not d.get("ok"):
        print("FAIL: payload did not complete cleanly:")
        print(json.dumps(d, indent=1)[:1800] if d else (raw or "")[-1200:])
        return 4
    # Defence in depth (rule 13): do not rely on the payload's `ok` alone --
    # re-check that all three layers came back and each applied. A payload
    # regression that set ok over an empty/partial layer set would otherwise
    # sail through, save and commit.
    layers = d.get("layers") or {}
    if len(layers) != 3 or not all(r.get("applied") for r in layers.values()):
        print("FAIL: payload reported ok but layers incomplete/unapplied: %s"
              % {k: v.get("applied") for k, v in layers.items()})
        return 4
    for role, row in d["layers"].items():
        print("  %-10s %s -> %s cm  (cell %s)  applied=%s"
              % (role, row["loading_range_before"],
                 row["loading_range_after"], row["cell_size"],
                 row["applied"]))
    save = d.get("save") or {}
    print("  map save: dirty %s saved %s still_dirty %s"
          % (save.get("dirty_map_packages"), save.get("saved"),
             save.get("still_dirty_after")))
    if save.get("still_dirty_after"):
        print("FAIL: map package still dirty after the save.")
        return 5

    fs_after = _git_touched()
    if fs_before is None or fs_after is None:
        print("FAIL: could not read git for the filesystem verdict.")
        return 5
    delta = sorted(fs_after - fs_before)
    print("  filesystem delta: %s" % (delta or "none"))
    to_commit = [f for f in delta] or (
        [MAP_FILE] if MAP_FILE in fs_after else [])
    if not to_commit:
        if not os.path.exists(os.path.join(REPO, MAP_FILE)):
            print("FAIL: no delta AND %s does not exist." % MAP_FILE)
            return 5
        print("  no file changed: on-disk state already matched "
              "(idempotent re-run). Nothing to commit.")
        return 0
    msg_path = None
    try:
        fd, msg_path = tempfile.mkstemp(prefix=".ll_range_", suffix=".txt",
                                        dir=REPO)
        with os.fdopen(fd, "w") as fh:
            fh.write("apply_streaming_range: runtime grid ranges saved\n\n"
                     "Brief 3 Task 0 (R-RANGE): main %(MAIN_CM)s, instanced "
                     "%(INST_CM)s, merged %(MERGED_CM)s cm, applied by "
                     "signature and read back.\n" % subs)
        r = subprocess.run(["git", "add", "--"] + to_commit, cwd=REPO,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print("FAIL: git add: " + (r.stderr or r.stdout).strip())
            return 5
        r = subprocess.run(["git", "commit", "-F", msg_path, "--"] + to_commit,
                           cwd=REPO, capture_output=True, text=True,
                           timeout=120)
        if r.returncode != 0:
            print("FAIL: git commit: " + (r.stderr or r.stdout).strip())
            return 5
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                           capture_output=True, text=True, timeout=120)
        print("  committed: %s  (%s)" % (h.stdout.strip(),
                                         ", ".join(to_commit)))
    finally:
        if msg_path and os.path.exists(msg_path):
            try:
                os.remove(msg_path)
            except OSError:
                pass
    print("Ranges applied, read back, SAVED and committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
