"""Bind the church's material instances to its mesh slots, and read back.

    python scripts/assign_church_materials.py

The pairing comes from `recipes/church_materials.json` -- each role declares
the `slot` it belongs to -- so the mapping is DECLARED in the recipe rather
than positional in a script. The payload refuses any slot name the mesh does
not actually have, rather than falling back to an index.

PAIRS travels into the payload as a Python literal written to a FILE, never
through a shell: PowerShell strips double quotes out of a --set value, so a
JSON blob handed through the shell arrives as a Python syntax error (recorded
in c0_build_materials.py, and hit again on the forge lineup this week).

Exit codes:
  0  every slot matched what was asked for AND the mesh persisted to disk
  3  the assignment failed, or the mesh was assigned in memory but save_asset
     returned False (assigned-not-saved is not success)
  5  no JSON came back from the editor -- that is 'could not look'
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    man = json.load(io.open(os.path.join(REPO, "recipes",
                                         "church_materials.json"),
                            encoding="utf-8"))
    mesh = man["mesh"]
    dest = mesh.rsplit("/", 1)[0]
    pairs, placeholders = {}, []
    for role, spec in man["roles"].items():
        pairs[spec["slot"]] = dest + "/MI_Church_" + role
        if spec.get("placeholder"):
            placeholders.append((spec["slot"], role))

    tmpl = io.open(os.path.join(REPO, "scripts", "assign_slots_payload.txt"),
                   encoding="utf-8").read()
    assert "PAIRS_JSON" in tmpl
    src = tmpl.replace("PAIRS_JSON", repr(pairs)).replace("__MESH__", mesh)
    gen = os.path.join(REPO, "LandscapeLab", "Saved",
                       "assign_church_gen.txt")
    os.makedirs(os.path.dirname(gen), exist_ok=True)
    io.open(gen, "w", encoding="utf-8").write(src)

    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         gen, "--timeout", "25"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if not (0 <= i < j):
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1200:])
        return 5
    r = json.loads(t[i:j + 1])

    print("mesh   %s" % mesh)
    print("slots  %s" % r.get("slots_before"))
    print("")
    for row in r.get("readback", []):
        print("  %-18s <- %s" % (row["slot"], row["material"]))
    print("")
    if not r.get("ok"):
        print("ASSIGNMENT FAILED: %s" % str(r.get("error"))[:400])
        return 3
    print("all slots match what was asked for: %s" % r.get("all_match"))
    if not r.get("saved"):
        print("SAVE NOT VERIFIED: save_asset did not report the mesh persisted "
              "-- assigned in memory but not written to disk.")
        return 3
    if placeholders:
        print("")
        print("⛔ SLOTS STANDING ON A PLACEHOLDER, waiting on the operator:")
        for slot, role in placeholders:
            print("     %-18s role %s" % (slot, role))
        print("   These render, and they are NOT the artefact of record.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
