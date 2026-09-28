"""summarise.py — pull the report groups out of the ledgers.

The ledgers are a MECHANICAL index: they are deliberately over-inclusive
so nothing is missed, and their precision is stated rather than assumed.
This pulls the high-signal rows per group so the prose report can cite
file:line without a human re-reading 35,376 claims.
"""
import io
import json
import os
import re
from collections import Counter, defaultdict


def _find_repo(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md")
        d = nd


REPO = _find_repo(__file__)
A = os.path.join(REPO, "research", "audit")
L = lambda n: json.load(io.open(os.path.join(A, n), encoding="utf-8"))

claims = L("claims_ledger.json")
findings = L("findings_ledger.json")
scripts = L("script_claims.json")
tools = L("tools_of_record.json")
levers = L("lever_inventory.json")
api = L("api_inventory.json")

out = {}

# WRONG: a contradiction whose later side carries a reversal marker
wrong = []
for c in claims["claims"]:
    for x in c["contradicted_by"]:
        if x["reversal_marker"]:
            wrong.append({"earlier": c["file_line"],
                          "earlier_claim": c["claim"][:200],
                          "parameter": x["parameter"],
                          "values": x["values"],
                          "later": x["other"],
                          "later_claim": x["other_claim"][:200]})
# One row per PARAMETER, not per numeric pair: a single line holding
# four numbers generates six pairs, and reporting all six reads as six
# contradictions where there is one.
seen = set()
wrong_u = []
for w in wrong:
    k = (w["parameter"], w["earlier"], w["later"])
    if k in seen:
        continue
    seen.add(k)
    wrong_u.append(w)
byparam = {}
for w in wrong_u:
    byparam.setdefault(w["parameter"], []).append(w)
wrong_u = [v[0] for v in byparam.values()]
out["WRONG"] = wrong_u

# STALE: a claim whose own text says it was superseded
stale = [c for c in claims["claims"]
         if re.search(r"SUPERSEDED|RETIRED|no longer|REJECTED and REPLACED|"
                      r"struck|withdraw", c["claim"], re.I)]
out["STALE"] = [{"at": c["file_line"], "claim": c["claim"][:220],
                 "dated": c["dated"]} for c in stale]

# DEAD: pipeline scripts nothing calls, and levers with a write but no
# read-back, and levers seeded as non-existent
dead_scripts = [s for s in scripts["scripts"]
                if s["nothing_calls_it"]
                and s["product"] == "landscape pipeline"]
out["DEAD_SCRIPTS"] = [{"file": s["file"], "purpose": s["purpose"][:120],
                        "has_test": s["selftest"]} for s in dead_scripts]
dead_levers = [e for e in levers["levers"]
               if e["notes"] and any("DOES NOT EXIST" in n or "dead" in n
                                     for n in e["notes"])]
out["DEAD_LEVERS"] = [{"name": e["name"], "notes": e["notes"],
                       "n_writes": len(e["writes"]),
                       "n_reads": len(e["reads"])} for e in dead_levers]
no_readback = [e for e in levers["levers"]
               if e["writes"] and not e["has_read_back"]]
out["LEVERS_WRITTEN_NEVER_READ_BACK"] = [
    {"name": e["name"], "kind": e["kind"], "n_writes": len(e["writes"]),
     "first_site": e["writes"][0]["site"]} for e in no_readback]

# UNAPPLIED
un = [f for f in findings["findings"] if not f["applied"]]
out["UNAPPLIED"] = [{"at": f["file_line"], "finding": f["finding"][:240],
                     "dated": f["dated"], "numbers": f["numbers"],
                     "identifiers": f["identifiers"]} for f in un]

# DUPLICATE: the same finding text recorded in >1 place
dup = [f for f in findings["findings"] if f.get("also_at")]
out["DUPLICATE"] = [{"canonical": f["file_line"],
                     "also_at": f["also_at"],
                     "text": f["finding"][:180]} for f in dup]

# tools
out["TOOLS"] = {k: [t for t in tools["tools"] if t["status"] == k]
                for k in ("listed-but-missing", "listed-but-unused")}

# API: rank the silent returners
sf = api["silent_failure_calls"]
by = defaultdict(lambda: {"sites": 0, "consumed": 0, "why": "",
                          "examples": []})
for s in sf:
    e = by[s["api"]]
    e["sites"] += 1
    e["why"] = s["why_silent"]
    if s["consumed_by"]:
        e["consumed"] += 1
        if len(e["examples"]) < 3:
            e["examples"].append({"site": s["site"],
                                  "line": s["line"][:140],
                                  "consumed_by": s["consumed_by"][:140]})
UNCONDITIONAL = {"connect_material_expressions",
                 "delete_all_material_expressions", "get_lod_material_slot",
                 "get_console_variable_string_value",
                 "get_inputs_for_material_expression", "save_asset",
                 "get_assets", "does_asset_exist"}
ranked = sorted(by.items(),
                key=lambda kv: (kv[0] in UNCONDITIONAL,
                                kv[1]["consumed"]), reverse=True)
out["API_SILENT_RANKED"] = [{"api": k, **v} for k, v in ranked]

io.open(os.path.join(A, "report_groups.json"), "w",
        encoding="utf-8").write(json.dumps(out, indent=1))

for k in ("WRONG", "STALE", "DEAD_SCRIPTS", "DEAD_LEVERS",
          "LEVERS_WRITTEN_NEVER_READ_BACK", "UNAPPLIED", "DUPLICATE"):
    print("%-34s %d" % (k, len(out[k])))
print("TOOLS listed-but-missing        %d" % len(out["TOOLS"]["listed-but-missing"]))
print("TOOLS listed-but-unused        %d" % len(out["TOOLS"]["listed-but-unused"]))
print()
print("top silent-failure APIs:")
for r in out["API_SILENT_RANKED"][:6]:
    print("   %-38s sites %4d  consumed %3d" % (r["api"], r["sites"],
                                                r["consumed"]))
