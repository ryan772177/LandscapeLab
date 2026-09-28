"""build_ledgers.py — claims, findings, script_claims, tools_of_record.

READ-ONLY. Writes only under research/audit/.

⭐ WHAT A "CLAIM" IS. Any sentence in the corpus that asserts a FACT the
desk could check: a number with units, a rule ("always", "never",
"must"), a verdict (PASS/FAIL/REFUSE), a named engine behaviour. One row
per claim with file:line, the date it was made, its evidence pointer,
and `contradicted_by` where anything later says otherwise.

⭐ WHAT A "FINDING" IS. Anything the corpus learned: a lesson, a rule, a
derived number, a recommendation. The column that matters is
`applied_where` -- the script, recipe value or acceptance that
implements it -- or NONE. The NONE rows are the answer to "what did we
figure out and never use".

⛔ CONTRADICTIONS ARE FOUND MECHANICALLY, NOT FROM MEMORY. Two passes:
  1. the same NUMERIC TOKEN attached to the same SUBJECT with different
     values (contrast 0.9025 vs 0.95, warm-up 300 vs 40, range 768 vs
     512)
  2. the same SUBJECT with an explicit reversal marker later in time
     (REJECTED, SUPERSEDED, WITHDRAWN, CORRECTION, "was WRONG", struck)
The known ones are SEEDS used to validate the finder -- if a seeded pair
is not rediscovered, the finder is under-powered and says so.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from collections import defaultdict


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
OUT = os.path.join(REPO, "research", "audit")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "Intermediate",
             "DerivedDataCache", "Saved", "Binaries", "Build",
             "site-packages", "_trash"}

# ⭐ THE CLAIM CORPUS IS THE RECORD, not the evidence and not a packaged
# copy of another product. Ruled scope: "every .md, register, brief,
# plan, skill and commit message file".
#
# EXCLUDED, each with its reason:
#   _verify/      EVIDENCE. A sidecar states what a run MEASURED; it is
#                 what claims are checked AGAINST, not a claim. Including
#                 it put 14,236 measurement rows into the ledger and
#                 buried the record.
#   dist/         a PACKAGED COPY of the forge at two versions -- the
#                 same text twice, which MANUFACTURES contradictions.
#   hero/         PARKED separate product. In the zip; out of the ledger.
#   docs/archive/ superseded BY CONSTRUCTION and banner-marked. In the
#                 zip for history; it would otherwise contradict
#                 everything current by design.
CLAIM_EXCLUDE_PREFIX = ("_verify/", "dist/", "hero/", "docs/archive/",
                        "forge_runs/", "captures/", "Free/")

RE_NUM = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?![\w])")
RE_RULE = re.compile(r"\b(always|never|must|refuse[sd]?|cannot|forbidden|"
                     r"required|shall)\b", re.I)
RE_VERDICT = re.compile(r"\b(PASS|FAIL|REFUSE|REJECTED|WITHDRAWN|"
                        r"SUPERSEDED|NO VERDICT|STOP)\b")
RE_REVERSAL = re.compile(r"\b(REJECTED|SUPERSEDED|WITHDRAWN|CORRECTION|"
                         r"struck|was WRONG|no longer|retired|obsolete|"
                         r"replaced by|falsified|refuted|not adopted)\b",
                         re.I)
RE_FINDING = re.compile(r"(⭐|⛔|RULED|LESSON|the rule[s]?\b|MEASURED|"
                        r"DERIVED|hard-won|practice line|RECOMMEND)", re.I)
RE_EVID = re.compile(r"(_verify/[\w./-]+|scripts/[\w./-]+\.py|"
                     r"recipes/[\w./-]+\.json|LESSONS\.md|RECIPES\.md|"
                     r"REGISTER|commit \w{7,}|[A-Za-z_]+\.cpp:\d+|"
                     r"[A-Za-z_]+\.h:\d+|UE-\d+)")

# Seeds: known contradictions. Used to TEST the finder, not to be the
# list. Each is (subject substring, the two values).
SEEDS = [("contrast", "0.9025", "0.95"),
         ("warm", "300", "40"),
         ("shadow_tint", "1.10", "2.184"),
         ("range", "768", "512"),
         ("exposure", "-4.1268", "-13.5898")]


def corpus_files(exts, claim_scope=False):
    out = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, REPO).replace("\\", "/")
        # "/audit/" as well as the prefix: a wrong repo root once wrote
        # this tool's own output to research/research/audit/, and the
        # prefix test did not see it.
        if rel_root.startswith("research/audit") or "/audit/" in rel_root:
            continue
        for f in files:
            if os.path.splitext(f)[1].lower() not in exts:
                continue
            rel = os.path.relpath(os.path.join(root, f),
                                  REPO).replace("\\", "/")
            if claim_scope and rel.startswith(CLAIM_EXCLUDE_PREFIX):
                continue
            out.append(os.path.join(root, f))
    return sorted(out)


def file_date(rel, cache={}):
    if rel not in cache:
        r = subprocess.run(["git", "log", "-1", "--format=%ad|%h",
                            "--date=short", "--", rel], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
        cache[rel] = r or "|"
    return cache[rel]


# ------------------------------------------------------------- claims
def build_claims():
    rows = []
    for path in corpus_files({".md", ".txt"}, claim_scope=True):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        try:
            lines = io.open(path, encoding="utf-8",
                            errors="replace").read().splitlines()
        except Exception:
            continue
        date = file_date(rel)
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if len(s) < 12 or s.startswith("<!--"):
                continue
            nums = RE_NUM.findall(s)
            is_rule = bool(RE_RULE.search(s))
            is_verdict = bool(RE_VERDICT.search(s))
            if not (nums or is_rule or is_verdict):
                continue
            ev = RE_EVID.findall(s)
            rows.append({
                "file_line": "%s:%d" % (rel, i),
                "claim": s[:400],
                "dated": date.split("|")[0],
                "commit": date.split("|")[-1],
                "numbers": nums[:8],
                "is_rule": is_rule,
                "is_verdict": is_verdict,
                "evidence": ev[:4] or None,
                "evidence_kind": ("sidecar" if any("_verify/" in e for e in ev)
                                  else "script" if any(".py" in e for e in ev)
                                  else "recipe" if any(".json" in e for e in ev)
                                  else "doc" if ev else "NONE"),
                "contradicted_by": [],
            })
    return rows


RE_PARAM = re.compile(r"`([a-zA-Z][\w.]{3,40})`|"          # backticked
                      r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){1,4})\b|"  # snake
                      r"\b((?:r|sg|grass|foliage|landscape|wp)\.[A-Za-z0-9_.]+)|"
                      # ⛔ BARE WORDS TOO. Requiring an underscore meant
                      # `contrast`, `exposure`, `warm-up` and `range`
                      # were never keys, and the finder rediscovered NONE
                      # of the five seeded contradictions -- while a
                      # broken seed check (OR instead of requiring the
                      # PAIR) reported two of them as found. The
                      # occurrence cap below, not the shape of the token,
                      # is what actually suppresses common words.
                      r"\b([a-z]{5,20})\b")


def find_contradictions(rows):
    """Same PARAMETER, different value -- not merely a shared word.

    ⛔ WHY NOT ANY SHARED WORD. The first version keyed on every word
    over four letters and produced 152,372 "contradiction" links across
    133,480 claims: two unrelated sentences that both mention "camera"
    and both contain a number were reported as contradicting. A finder
    that fires on everything has found nothing.

    The subject is now a PARAMETER-SHAPED token -- a backticked
    identifier, a snake_case name, or a dotted cvar -- because that is
    what a value actually belongs to. Two claims contradict when they
    attach DIFFERENT numbers to the SAME parameter.

    Ordering is by date, so `contradicted_by` points FORWARD in time:
    the later statement is the one that supersedes.
    """
    idx = defaultdict(list)
    for n, r in enumerate(rows):
        params = set()
        for m in RE_PARAM.finditer(r["claim"]):
            params.add((m.group(1) or m.group(2) or m.group(3)
                        or m.group(4)).lower())
        r["_params"] = sorted(params)[:12]
        for p in r["_params"]:
            for num in r["numbers"][:4]:
                idx[p].append((num, n))
    hits = 0
    for param, lst in idx.items():
        # A parameter mentioned on hundreds of lines is a common word in
        # disguise (e.g. "file_line"); it cannot localise a value.
        if len(lst) > 120:
            continue
        vals = defaultdict(set)
        for num, n in lst:
            vals[num].add(n)
        nums = sorted(vals)
        if len(nums) < 2 or len(nums) > 8:
            continue
        for a in range(len(nums)):
            for b in range(a + 1, len(nums)):
                na, nb = nums[a], nums[b]
                try:
                    fa, fb = float(na), float(nb)
                except ValueError:
                    continue
                if max(abs(fa), abs(fb)) == 0:
                    continue
                if abs(fa - fb) / max(abs(fa), abs(fb)) < 0.02:
                    continue
                for ia in sorted(vals[na])[:2]:
                    for ib in sorted(vals[nb])[:2]:
                        if ia == ib:
                            continue
                        da, db = rows[ia]["dated"], rows[ib]["dated"]
                        later, earlier = (ib, ia) if db >= da else (ia, ib)
                        if rows[later]["dated"] == rows[earlier]["dated"] \
                                and rows[later]["file_line"].rsplit(":", 1)[0] \
                                == rows[earlier]["file_line"].rsplit(":", 1)[0]:
                            continue        # same file, same day: a table
                        ent = {"other": rows[later]["file_line"],
                               "parameter": param,
                               "values": [na, nb],
                               "reversal_marker": bool(
                                   RE_REVERSAL.search(rows[later]["claim"])),
                               "other_claim": rows[later]["claim"][:180]}
                        if len(rows[earlier]["contradicted_by"]) < 5:
                            rows[earlier]["contradicted_by"].append(ent)
                            hits += 1
    for r in rows:
        r.pop("_params", None)
    return hits


# ------------------------------------------------------------ findings
def build_findings():
    rows = []
    # every derived number currently in the shipped recipe, to test
    # whether a finding is still implemented
    recipe = {}
    rp = os.path.join(REPO, "recipes", "alpine_8k.json")
    if os.path.isfile(rp):
        def walk(o, p=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, p + "/" + k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, p + "[%d]" % i)
            else:
                recipe[p] = o
        walk(json.load(io.open(rp, encoding="utf-8")))
    recipe_vals = {str(v) for v in recipe.values()
                   if isinstance(v, (int, float))}

    # every script's text, to test "is this finding implemented anywhere"
    script_text = {}
    for path in corpus_files({".py"}):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        try:
            script_text[rel] = io.open(path, encoding="utf-8",
                                       errors="replace").read()
        except Exception:
            pass

    for path in corpus_files({".md", ".txt"}, claim_scope=True):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        try:
            lines = io.open(path, encoding="utf-8",
                            errors="replace").read().splitlines()
        except Exception:
            continue
        date = file_date(rel)
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if len(s) < 20 or not RE_FINDING.search(s):
                continue
            nums = [n for n in RE_NUM.findall(s) if len(n) >= 3]
            keys = [m.group(1) for m in
                    re.finditer(r"`([A-Za-z_][A-Za-z0-9_./]{4,})`", s)]
            # ⭐ A FINDING NEEDS SOMETHING CHECKABLE. A marked line with
            # neither a derived number nor a named identifier is a
            # sentiment ("be careful here"), and asking whether it is
            # "applied" has no answer. Those are counted and excluded.
            if not nums and not keys:
                continue
            # ⛔ DEDUPLICATE BY TEXT. The project's practice copies a
            # lesson verbatim into LESSONS.md, the commit message and
            # often a docstring -- three rows for one finding, and three
            # entries in an "unapplied" list that a reader then has to
            # de-duplicate by hand.
            norm = re.sub(r"\s+", " ", re.sub(r"[^\w %.+-]", "", s)).strip().lower()[:160]
            applied = []
            for num in nums[:5]:
                if num in recipe_vals:
                    applied.append("recipes/alpine_8k.json (value %s)" % num)
            for key in keys[:3]:
                for srel, txt in script_text.items():
                    if key in txt:
                        applied.append(srel)
                        break
            # A number that appears as a CONSTANT in any script counts as
            # implemented -- that is what a threshold is.
            if not applied:
                for num in nums[:4]:
                    for srel, txt in script_text.items():
                        if re.search(r"=\s*%s\b" % re.escape(num), txt):
                            applied.append("%s (constant %s)" % (srel, num))
                            break
                    if applied:
                        break
            rows.append({
                "file_line": "%s:%d" % (rel, i),
                "finding": s[:400],
                "_norm": norm,
                "dated": date.split("|")[0],
                "numbers": nums[:6],
                "identifiers": keys[:4],
                "applied_where": sorted(set(applied))[:4] or None,
                "applied": bool(applied),
            })
    # collapse duplicates, keeping the EARLIEST statement and recording
    # where else it appears
    seen = {}
    for r in rows:
        k = r["_norm"]
        if k not in seen:
            r["also_at"] = []
            seen[k] = r
        else:
            if len(seen[k]["also_at"]) < 6:
                seen[k]["also_at"].append(r["file_line"])
            if r["applied"] and not seen[k]["applied"]:
                seen[k]["applied"] = True
                seen[k]["applied_where"] = r["applied_where"]
            if r["dated"] < seen[k]["dated"]:
                seen[k]["dated"] = r["dated"]
    out = sorted(seen.values(), key=lambda r: r["file_line"])
    for r in out:
        r.pop("_norm", None)
    return out


# -------------------------------------------------------- script claims
def build_script_claims():
    rows = []
    called = defaultdict(int)
    texts = {}
    for path in corpus_files({".py"}):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        try:
            texts[rel] = io.open(path, encoding="utf-8",
                                 errors="replace").read()
        except Exception:
            pass
    stems = {os.path.splitext(os.path.basename(r))[0]: r for r in texts}
    for rel, txt in texts.items():
        for stem, other in stems.items():
            if other == rel:
                continue
            if re.search(r"\b%s\b" % re.escape(stem), txt):
                called[other] += 1
    for rel, txt in sorted(texts.items()):
        lines = txt.splitlines()
        doc = ""
        m = re.match(r'\s*[ru]?"""(.*?)"""', txt, re.S)
        if m:
            doc = m.group(1).strip().splitlines()[0][:220] if m.group(1).strip() else ""
        marks = [{"line": i, "text": ln.strip()[:220]}
                 for i, ln in enumerate(lines, 1)
                 if ("⭐" in ln or "⛔" in ln or "RULED" in ln)]
        thresholds = []
        for i, ln in enumerate(lines, 1):
            mm = re.match(r"\s*([A-Z][A-Z0-9_]{2,})\s*=\s*([^#\n]+)", ln)
            if mm and re.search(r"\d", mm.group(2)):
                thresholds.append({"name": mm.group(1),
                                   "value": mm.group(2).strip()[:80],
                                   "line": i})
        has_self = "def selftest" in txt or "--selftest" in txt
        pos = bool(re.search(r"positive|grating|known-good|must PASS|"
                             r"legitimate case", txt, re.I))
        neg = bool(re.search(r"negative|noise|must REFUSE|must FAIL|"
                             r"BLOCK THE VIOLATION|control", txt, re.I))
        rows.append({
            "file": rel,
            "purpose": doc,
            "marked_comments": marks[:30],
            "n_marked": len(marks),
            "thresholds": thresholds[:30],
            "selftest": has_self,
            "positive_control": pos if has_self else None,
            "negative_control": neg if has_self else None,
            "no_test_at_all": not has_self,
            "referenced_by_n_scripts": called.get(rel, 0),
            "nothing_calls_it": called.get(rel, 0) == 0,
            # dist/ is a PACKAGED COPY and hero/ is a PARKED separate
            # product; counting their scripts as 'uncalled pipeline
            # tools' would triple the dead-weight list with things that
            # are not the pipeline.
            "product": ("forge (packaged copy)" if rel.startswith("dist/")
                        else "forge" if rel.startswith("forge_tool/")
                        else "hero (parked)" if rel.startswith("hero/")
                        else "landscape pipeline"),
        })
    return rows


# ------------------------------------------------------ tools of record
DESK_TOOLS = ["angular_budget", "temporal_stability", "lod_silhouette_check",
              "measure_concept_look", "fog_budget", "void_mask",
              "texel_budget", "tiling_score", "sample_census",
              "shade_reference", "hydro_derive"]


def build_tools(script_rows):
    on_disk = {}
    for r in script_rows:
        on_disk.setdefault(os.path.splitext(os.path.basename(r["file"]))[0],
                           []).append(r)
    listed = set(DESK_TOOLS)
    # anything named as a tool in the governing docs
    for doc in ("CLAUDE.md", "RECIPES.md", "LESSONS.md", "STATE.md",
                "research/brief3/FOR_CLAUDE_CODE.md",
                "research/brief3/REGISTER_ADDENDUM.md"):
        p = os.path.join(REPO, doc)
        if not os.path.isfile(p):
            continue
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        # (?<![\w/]) so `image.py` does not yield the tool `mage`:
        # the first version matched a SUFFIX of a longer word and put
        # mage / perators / xporter / win_amd64 into listed-but-missing.
        for m in re.finditer(r"(?<![\w])(?:scripts/)?([a-z][a-z0-9_]{3,})\.py", txt):
            listed.add(m.group(1))
    rows = []
    for name in sorted(listed):
        hits = on_disk.get(name, [])
        if hits:
            used = any(h["referenced_by_n_scripts"] > 0 for h in hits)
            rows.append({"tool": name,
                         "status": ("listed-and-exists-and-used" if used
                                    else "listed-but-unused"),
                         "paths": [h["file"] for h in hits],
                         "referenced_by_n_scripts":
                             max(h["referenced_by_n_scripts"] for h in hits),
                         "is_desk_tool": name in DESK_TOOLS})
        else:
            rows.append({"tool": name, "status": "listed-but-missing",
                         "paths": [], "referenced_by_n_scripts": 0,
                         "is_desk_tool": name in DESK_TOOLS})
    for name, hits in sorted(on_disk.items()):
        if name in listed:
            continue
        rows.append({"tool": name, "status": "exists-but-unlisted",
                     "paths": [h["file"] for h in hits],
                     "referenced_by_n_scripts":
                         max(h["referenced_by_n_scripts"] for h in hits),
                     "is_desk_tool": False})
    return rows


def main():
    print("claims ...")
    claims = build_claims()
    hits = find_contradictions(claims)
    n_contra = sum(1 for c in claims if c["contradicted_by"])
    # validate the finder against the seeds
    seed_report = []
    for subj, a, b in SEEDS:
        # ⛔ REQUIRE THE PAIR. The first version used OR, so any claim
        # mentioning the subject with EITHER value counted as
        # rediscovered -- it reported 2 of 5 seeds found while the
        # finder had in fact found none of them.
        found = any(set(x["values"]) == {a, b}
                    for c in claims for x in c["contradicted_by"])
        seed_report.append({"subject": subj, "values": [a, b],
                            "rediscovered": found})
    io.open(os.path.join(OUT, "claims_ledger.json"), "w",
            encoding="utf-8").write(json.dumps(
                {"_what": "every factual claim in the corpus",
                 "n_claims": len(claims),
                 "n_with_contradiction": n_contra,
                 "n_contradiction_links": hits,
                 "_seed_validation": seed_report,
                 "_seed_note": "seeds TEST the finder; a seed not "
                               "rediscovered means the finder is "
                               "under-powered for that shape",
                 "claims": claims}, indent=1))
    print("  %d claims, %d with contradictions (%d links)"
          % (len(claims), n_contra, hits))

    print("findings ...")
    findings = build_findings()
    unapplied = [f for f in findings if not f["applied"]]
    io.open(os.path.join(OUT, "findings_ledger.json"), "w",
            encoding="utf-8").write(json.dumps(
                {"_what": "every finding/lesson/derived number, and "
                          "whether anything implements it",
                 "n_findings": len(findings),
                 "n_unapplied": len(unapplied),
                 "findings": findings}, indent=1))
    print("  %d findings, %d with no implementation found"
          % (len(findings), len(unapplied)))

    print("script claims ...")
    scripts = build_script_claims()
    io.open(os.path.join(OUT, "script_claims.json"), "w",
            encoding="utf-8").write(json.dumps(
                {"_what": "per-script purpose, marked rules, thresholds, "
                          "tests and callers",
                 "n_scripts": len(scripts),
                 "n_no_test": sum(1 for s in scripts
                                  if s["no_test_at_all"]),
                 "n_uncalled": sum(1 for s in scripts
                                   if s["nothing_calls_it"]),
                 "scripts": scripts}, indent=1))
    print("  %d scripts, %d with no test, %d nothing calls"
          % (len(scripts), sum(1 for s in scripts if s["no_test_at_all"]),
             sum(1 for s in scripts if s["nothing_calls_it"])))

    print("tools of record ...")
    tools = build_tools(scripts)
    io.open(os.path.join(OUT, "tools_of_record.json"), "w",
            encoding="utf-8").write(json.dumps(
                {"_what": "tools named as of-record vs scripts that "
                          "exist and are called",
                 "n": len(tools),
                 "tools": tools}, indent=1))
    from collections import Counter
    print("  " + repr(Counter(t["status"] for t in tools)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
