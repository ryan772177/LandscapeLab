"""Measure the wider-seed kit meshes live and write them into the kit JSON."""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "Free", "_measured", "kit_medievalvillage_v2.json")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    with io.open(os.path.join(REPO, "recipes", "kit_seed_v2.txt"),
                 encoding="utf-8") as fh:
        pkgs = [ln.strip() for ln in fh if ln.strip()]

    with io.open(os.path.join(REPO, "scripts",
                              "kit_measure_v2_payload.txt"),
                 encoding="utf-8") as fh:
        tmpl = fh.read()
    assert "PKGS_JSON" in tmpl
    gen = os.path.join(REPO, "LandscapeLab", "Saved", "kit_measure_v2_gen.txt")
    with io.open(gen, "w", encoding="utf-8") as fh:
        fh.write(tmpl.replace("PKGS_JSON", repr(pkgs)))

    print("measuring %d meshes" % len(pkgs))
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         gen, "--timeout", "25"], capture_output=True, text=True)
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if i < 0:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1200:])
        return 5
    r = json.loads(t[i:j + 1])
    if r.get("error"):
        print("FAILED: " + str(r["error"])[:400])
        return 4
    if r.get("unloadable"):
        print("  UNLOADABLE (%d):" % len(r["unloadable"]))
        for u in r["unloadable"][:8]:
            print("    " + u)

    rows = sorted(r["rows"], key=lambda x: x["name"])
    print("")
    print("  %-26s %18s %9s %8s %6s %5s"
          % ("mesh", "size cm", "nanite", "LOD0 fb", "pivot", "LODs"))
    bad = 0
    for x in rows:
        tris = x.get("fallback_tris_by_lod")
        if not tris or x.get("nanite_tris") is None:
            bad += 1
        print("  %-26s %18s %9s %8s %8.1f %5d"
              % (x["name"][:26],
                 "x".join(str(v) for v in x["size_cm"]),
                 x.get("nanite_tris", "?"),
                 tris[0] if tris else "?",
                 x["pivot_base_error_cm"], x["lods"]))
    if bad:
        print("")
        print("  !! %d row(s) have NO triangle count -- that is a failed"
              " measurement, not a" % bad)
        print("     mesh with no triangles, and the row must not be consumed.")

    doc = {
        "_what": ("Wider-seed kit meshes, measured live 2026-08-30. Same "
                  "fields as the 2026-08-29 rows so the two intakes read as "
                  "ONE table."),
        "_source": ("VaultCache MedievalGame_5.3, copied by dependency "
                    "closure; see kit_medievalvillage_v2_closure.json for "
                    "the SHA-256 manifest."),
        "_seed": "recipes/kit_seed_v2.txt (Gate-A approved names)",
        "_fallback_vs_nanite": ("fallback_tris_by_lod is the chain that "
                                "renders with Nanite OFF; nanite_tris is what "
                                "renders with it on. On a Nanite mesh these "
                                "are DIFFERENT MESHES."),
        "measured": len(rows),
        "rows": rows,
    }
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("")
    print("  wrote %s (%d rows)" % (os.path.relpath(OUT, REPO), len(rows)))
    return 0 if r.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
