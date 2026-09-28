"""pass2_properties.py — Audit Pass 2: every editor-property lever vs the
LIVE 5.8 Python stub (Q7 / AUDIT C-1).

The 306 `editor_property` levers in research/audit/lever_inventory.json
are names scripts pass to get_/set_editor_property. The CONTRACT is the
reflected surface (docs/ue58-api-protocol.md), and the stub
(LandscapeLab/Intermediate/PythonStub/unreal.py, engine-generated) is
its live enumeration. A name is:

    PRESENT            spelled exactly as a stub property
    PRESENT_AS_SNAKE   an FName/PascalCase spelling whose snake_case
                       form the stub carries — valid at runtime
                       (get_editor_property resolves the FName), noted
                       so a reader knows which convention the site uses
    ABSENT             neither spelling anywhere in the stub — a
                       casualty-list candidate: renamed, removed, a
                       nested-struct FIELD (those are not stub
                       properties), or a typo. Each needs its call
                       site read; this scanner only NAMES them.

Deprecation: a stub doc row carrying "deprecated" on the property's own
line is flagged. Output: research/audit/pass2_properties.json with a
verdict per lever and the site list, plus a printed summary (counts
beside verdicts, rule 13).

    python scripts/pass2_properties.py [--stub PATH] [--selftest]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB = os.path.join(REPO, "LandscapeLab", "Intermediate", "PythonStub",
                    "unreal.py")
INVENTORY = os.path.join(REPO, "research", "audit", "lever_inventory.json")
OUT = os.path.join(REPO, "research", "audit", "pass2_properties.json")

DOC_ROW = re.compile(r"^\s*-\s*``(\w+)``\s*\(")
PROP_DEF = re.compile(r"^\s*def\s+(\w+)\(self\)")


def camel_to_snake(name):
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.replace("__", "_").lower()


def scan_stub(path):
    """One pass: (property_names, deprecated_names). Property names are
    collected from BOTH the class-doc rows and @property getter defs —
    two spellings of the stub's own surface; union, not intersection."""
    names, deprecated = set(), set()
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = DOC_ROW.match(line)
            if m:
                names.add(m.group(1))
                if "deprecated" in line.lower():
                    deprecated.add(m.group(1))
                continue
            m = PROP_DEF.match(line)
            if m and not m.group(1).startswith("_"):
                names.add(m.group(1))
    return names, deprecated


def classify(name, stub_names):
    if name in stub_names:
        return "PRESENT", name
    snake = camel_to_snake(name)
    if snake != name and snake in stub_names:
        return "PRESENT_AS_SNAKE", snake
    return "ABSENT", snake


def selftest():
    ok = True
    checks = [
        ("CellSize", "cell_size"), ("FogDensity", "fog_density"),
        ("bEnabled", "b_enabled"), ("HLODLayer", "hlod_layer"),
        ("already_snake", "already_snake"),
    ]
    for camel, want in checks:
        got = camel_to_snake(camel)
        good = got == want
        ok &= good
        print("  camel_to_snake(%r) -> %r (want %r)  %s"
              % (camel, got, want, "ok" if good else "FAIL"))
    fake = {"cell_size", "fog_density"}
    ok &= classify("CellSize", fake) == ("PRESENT_AS_SNAKE", "cell_size")
    ok &= classify("cell_size", fake) == ("PRESENT", "cell_size")
    ok &= classify("NoSuchThing", fake)[0] == "ABSENT"
    print("  classify three directions:", "ok" if ok else "FAIL")
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stub", default=STUB)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not os.path.isfile(a.stub):
        print("REFUSE: no stub at %s — the live enumeration is the "
              "contract; do not audit against memory." % a.stub)
        return 2
    stub_names, stub_deprecated = scan_stub(a.stub)
    print("stub: %d property names, %d flagged deprecated on their doc row"
          % (len(stub_names), len(stub_deprecated)))
    if not stub_names:
        print("REFUSE: zero properties parsed from the stub — the parser "
              "found nothing to compare against (rule 13).")
        return 2

    inv = json.load(io.open(INVENTORY, encoding="utf-8"))
    props = [r for r in inv["levers"] if r.get("kind") == "editor_property"]
    rows = []
    counts = {"PRESENT": 0, "PRESENT_AS_SNAKE": 0, "ABSENT": 0}
    for r in sorted(props, key=lambda x: x["name"]):
        verdict, resolved = classify(r["name"], stub_names)
        counts[verdict] += 1
        live_sites = sorted({s["site"] for s in
                             (r.get("writes") or []) + (r.get("reads") or [])
                             if not s["site"].startswith("dist/")})
        rows.append({
            "name": r["name"], "verdict": verdict, "resolved": resolved,
            "deprecated_on_doc_row": (resolved in stub_deprecated
                                      or r["name"] in stub_deprecated),
            "live_sites": live_sites,
            "has_read_back": r.get("has_read_back"),
        })
    out = {"_what": "Pass 2 (Q7): every editor_property lever vs the live "
                    "5.8 Python stub. ABSENT rows need their call sites "
                    "read — nested-struct fields and typos both land "
                    "there; the stub cannot tell them apart.",
           "stub": os.path.relpath(a.stub, REPO).replace(os.sep, "/"),
           "n_properties": len(rows), "counts": counts,
           "n_deprecated_flagged": sum(1 for r in rows
                                       if r["deprecated_on_doc_row"]),
           "rows": rows}
    io.open(a.out, "w", encoding="utf-8").write(json.dumps(out, indent=1))
    print("levers: %d | %s | deprecated-flagged %d -> %s"
          % (len(rows),
             " ".join("%s %d" % kv for kv in sorted(counts.items())),
             out["n_deprecated_flagged"], os.path.relpath(a.out, REPO)))
    for r in rows:
        if r["verdict"] == "ABSENT":
            print("  ABSENT %-38s sites: %s"
                  % (r["name"], "; ".join(r["live_sites"][:3]) or "(dist only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
