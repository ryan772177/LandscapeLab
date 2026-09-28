"""check_perf.py — the performance law, enforced. Offline, no editor.

Selects the STANDALONE `_verify/perf/*.json` whose declared loading range
matches the world's (ruled 2026-09-11; `--label` forces a specific one, and a
range miss or ambiguous match REFUSES) and holds it against the budgets in
`recipes/perf_budgets.json`. RED when a zone breaks its budget, naming the zone
and the delta.

WHY IT IS OFFLINE
-----------------
The measuring is expensive and needs a warm editor; the ENFORCING must be cheap
enough to run in the suite every time. So the flythrough writes an artefact and
this reads it. Same split as the city verifier: recipe declares, instrument
measures, suite enforces.

THREE STATES, AND THEY ARE NOT THE SAME
---------------------------------------
    PASS        measured, within budget
    RED         measured, over budget -- names the zone and the delta
    NO BUDGET   the recipe has not been ratified yet.

**NO BUDGET IS NOT A PASS.** Until the operator ratifies at Gate E, this exits
non-zero with a distinct code so the suite can carry it as a declared FINDING
rather than silently reporting green over an unenforced law. A perf checker
that says "ok" because nobody set a number is the untested gate of
non-negotiable 2.

MEASUREMENT CLASS IS ENFORCED (ruled 2026-09-10)
------------------------------------------------
When the recipe sets gates.require_measurement_class_standalone, an
artefact must declare `_measurement_class` containing "STANDALONE" or it
is REFUSED (exit 6). Editor-class numbers may not source or satisfy a
budget: the editor clamps its tick to the rate it is already running at
(EditorEngine.cpp:2523-2566), and E3 measured the editor's GameThreadTime
tracking that clamp at 13.9-14.15 ms across all four zones while the
standalone game thread reads ~3.9 ms. The plaza-Game RED that stood for
four days was that clamp, not the content.

Exit: 0 pass · 3 no ratified budget (a FINDING) · 4 a zone is RED ·
5 no data OR refused selection (no artefact at the world's range, ambiguous
matches, or a present artefact in which ZERO zones were actually judged) ·
6 REFUSED, artefact is not standalone-class.
(--self-test failure also exits 4: a broken checker and a breach both
mean "do not trust green".)
"""
import argparse
import glob
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE = os.path.join(REPO, "recipes", "perf_budgets.json")
PERFDIR = os.path.join(REPO, "_verify", "perf")

METRIC = "GPUTime"
STAT = "p90"
_WHY = ("p90, not mean: a budget is about the frames that hurt. FrameTime "
        "is judged too since 2026-09-10 -- the standalone class the gate "
        "enforces has no editor clamp, so it is a real cost signal there.")


def class_ok(mclass):
    """True when the declared measurement class is standalone.

    The check is on the DECLARATION, deliberately: an artefact that does
    not say what instrument produced it is refused rather than assumed
    (an absent class is "I could not look", never "standalone").
    """
    return "STANDALONE" in str(mclass or "").upper()


def newest(label=None):
    pat = "*_%s.json" % label if label else "*.json"
    files = sorted(glob.glob(os.path.join(PERFDIR, pat)),
                   key=os.path.getmtime)
    return files[-1] if files else None


def by_declared_range(range_cm):
    """The standalone artefact whose DECLARED loading range matches the
    world's. Returns (path, candidates) -- path None if none matches.

    RULED BY RYAN 2026-09-11. `newest()` picks by MTIME, and on
    2026-09-11 that meant the 768 m artefact was judging a world ruled to
    512 m: treeline read GPU 7.86 vs 7.00 and the gate went RED -- while
    the 512 m artefact, already on disk, passes every zone. **That RED was
    itself the measurement that CAUSED the fallback to 512.** The gate
    was re-reporting the disease as the diagnosis.

    A perf artefact is only evidence about the world it was measured in.
    Matching is therefore on the RANGE, and a miss REFUSES -- "no
    artefact at this world's range" is honest; judging against another
    world's is not.

    ⛔ AMENDED 2026-09-14: RETURNS EVERY MATCH, AND AMBIGUITY REFUSES.
    This used to `return` on the FIRST match in sorted order. On 2026-09-14
    a second 512 m artefact was added and the gate silently judged the
    2026-09-10 one -- printing a clean PASS about a run four days older than
    the one being checked, with no indication it had chosen. First-sorted is
    not a selection rule, it is a coin toss with a stable bias: adding a
    newer measurement of the SAME world can never displace an older one, so
    the gate gets quietly staler as the project gains evidence.

    Picking the NEWEST would be just as wrong in the other direction -- that
    is the mtime rule the 2026-09-11 ruling removed, and it is what let a
    768 m artefact judge a 512 m world. There is no safe automatic tiebreak
    between two artefacts that both legitimately describe this world, so the
    honest move is to refuse and make the operator name one.
    """
    cands, matches = [], []
    for p in sorted(glob.glob(os.path.join(PERFDIR, "*.json"))):
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        r = d.get("declared_loading_range_cm")
        cands.append((p, r, d.get("_measurement_class")))
        # An artefact that DECLARES itself superseded is not a candidate.
        # This is how a genuine ambiguity gets resolved without deleting or
        # moving evidence: the old file stays citable (RECIPES.md and the
        # claims ledger both reference it by path), and the decision about
        # WHICH run describes the world now lives in the data rather than in
        # whoever typed the last command line. Reverse it by deleting the
        # key.
        if d.get("_superseded_by"):
            continue
        if r is not None and int(r) == int(range_cm) and class_ok(
                d.get("_measurement_class")):
            matches.append(p)
    return matches, cands


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    rec = json.load(io.open(RECIPE, encoding="utf-8"))
    budgets = (rec.get("budgets") or {}).get("per_zone_ms")
    game_budgets = (rec.get("budgets") or {}).get("per_zone_game_ms")
    tol = float((rec.get("gates") or {}).get("tolerance_frac", 0.1))

    if a.self_test:
        # NON-NEGOTIABLE 2: prove it refuses before trusting a pass.
        print("SELF-TEST — each case must produce the stated verdict")
        fake = {"stations": [{"zone": "plaza",
                              "stats_ms": {METRIC: {STAT: 10.0},
                                           "GameThreadTime": {STAT: 10.0}}}]}
        cases = [
            ("within budget", {"plaza": 12.0}, 0.1, "PASS"),
            ("over budget", {"plaza": 8.0}, 0.1, "RED"),
            ("just inside tolerance", {"plaza": 9.2}, 0.1, "PASS"),
            ("outside tolerance", {"plaza": 8.9}, 0.1, "RED"),
            ("no budget declared", None, 0.1, "NO BUDGET"),
        ]
        bad = 0
        for name, b, t, want in cases:
            got = judge(fake, b, t, b)[0]
            ok = got == want
            print("  %-26s -> %-10s want %-10s %s"
                  % (name, got, want, "ok" if ok else "!! WRONG"))
            bad += 0 if ok else 1

        # The invalidated-basis path, in BOTH directions: a zone whose camera
        # moved must not be judged, and must not silently disappear either.
        v, rows = judge(fake, {"plaza": 8.0}, 0.1, {"plaza": 8.0},
                        invalidated={"plaza"})
        ok = (v == "PASS" and len(rows) == 1 and rows[0].get("no_verdict")
              and "NO VERDICT" in rows[0]["line"])
        print("  %-26s -> %-10s want %-10s %s"
              % ("invalidated basis", "NO VERDICT" if rows and
                 rows[0].get("no_verdict") else v, "NO VERDICT",
                 "ok" if ok else "!! WRONG"))
        bad += 0 if ok else 1
        # ...and the same zone WITHOUT the flag must still go RED, or the
        # guard would be a way to silence a genuine breach.
        v2 = judge(fake, {"plaza": 8.0}, 0.1, {"plaza": 8.0})[0]
        ok2 = v2 == "RED"
        print("  %-26s -> %-10s want %-10s %s"
              % ("same zone, flag absent", v2, "RED", "ok" if ok2 else "!! WRONG"))
        bad += 0 if ok2 else 1

        # Measurement-class gate, three directions (ruled 2026-09-10):
        # pass the standalone declaration, refuse the editor one, refuse
        # the ABSENT one -- an artefact that does not say what measured
        # it must not slide through as standalone.
        for name, mc, want in (
                ("standalone class passes", "STANDALONE -game, 4K", True),
                ("editor class refused", "EDITOR VIEWPORT", False),
                ("absent class refused", None, False)):
            got = class_ok(mc)
            ok = got == want
            print("  %-26s -> %-10s want %-10s %s"
                  % (name, got, want, "ok" if ok else "!! WRONG"))
            bad += 0 if ok else 1

        # Frame budget: over and within, and absent-budget stays silent
        # (the selftest cases above ran judge WITHOUT a frame budget and
        # must keep passing -- that is the silence direction).
        ffake = {"stations": [{"zone": "plaza",
                               "stats_ms": {METRIC: {STAT: 1.0},
                                            "GameThreadTime": {STAT: 1.0},
                                            "FrameTime": {STAT: 20.0}}}]}
        v_over = judge(ffake, {"plaza": 12.0}, 0.1, {"plaza": 12.0},
                       frame_budget=16.6)[0]
        ffake["stations"][0]["stats_ms"]["FrameTime"][STAT] = 10.0
        v_in = judge(ffake, {"plaza": 12.0}, 0.1, {"plaza": 12.0},
                     frame_budget=16.6)[0]
        for name, got, want in (("frame over budget", v_over, "RED"),
                                ("frame within budget", v_in, "PASS")):
            ok = got == want
            print("  %-26s -> %-10s want %-10s %s"
                  % (name, got, want, "ok" if ok else "!! WRONG"))
            bad += 0 if ok else 1

        # ARTEFACT SELECTION BY DECLARED RANGE, three directions. Added
        # 2026-09-11 with the selection itself: the old mtime pick had no
        # test at all, which is why a 768 m artefact judged a 512 m world
        # for a day without anything noticing.
        import tempfile as _tf
        global PERFDIR
        _real = PERFDIR
        with _tf.TemporaryDirectory() as td:
            PERFDIR = td

            def _w(nm, rng, mc):
                d = {"stations": [], "_measurement_class": mc}
                if rng is not None:
                    d["declared_loading_range_cm"] = rng
                with io.open(os.path.join(td, nm), "w", encoding="utf-8") as f:
                    json.dump(d, f)

            _w("a_range512.json", 51200, "STANDALONE -game, 4K")
            _w("b_range768.json", 76800, "STANDALONE -game, 4K")
            _w("c_undeclared.json", None, "STANDALONE -game, 4K")
            _w("d_editor512.json", 51200, "EDITOR VIEWPORT")
            sel = [("matching range is selected",
                    by_declared_range(51200)[0], "a_range512.json"),
                   ("a range with no artefact REFUSES",
                    by_declared_range(25600)[0], None),
                   ("the other range is not substituted",
                    by_declared_range(102400)[0], None)]
            for name, got, want in sel:
                # by_declared_range now returns a LIST of every match
                # (amended 2026-09-14); the self-test asserts on the single
                # expected winner, so unwrap and treat "more than one" as a
                # distinct, visible outcome rather than silently taking [0].
                if isinstance(got, list):
                    got = got[0] if len(got) == 1 else (None if not got
                                                        else "AMBIGUOUS")
                g = (got if got == "AMBIGUOUS"
                     else os.path.basename(got)) if got else None
                ok = g == want
                print("  %-26s -> %-10s want %-10s %s"
                      % (name, g, want, "ok" if ok else "!! WRONG"))
                bad += 0 if ok else 1
            # an EDITOR-class artefact at the right range must NOT win
            _w("a_range512.json", 51200, "EDITOR VIEWPORT")
            got = by_declared_range(51200)[0]
            got = got[0] if isinstance(got, list) and got else (
                None if isinstance(got, list) else got)
            ok = got is None or "editor" not in os.path.basename(got)
            print("  %-26s -> %-10s want %-10s %s"
                  % ("editor class not selected",
                     os.path.basename(got) if got else None, "not editor",
                     "ok" if ok else "!! WRONG"))
            bad += 0 if ok else 1
        PERFDIR = _real

        n = len(cases) + 2 + 3 + 2 + 4
        print()
        print("self-test: %d of %d correct" % (n - bad, n))
        return 4 if bad else 0

    # SELECT BY THE WORLD'S RANGE, not by mtime (ruled 2026-09-11).
    # --label still forces a specific artefact for diagnostics.
    # THE RANGE COMES FROM THE WORLD RECIPE, NOT THE BUDGET RECIPE.
    # `rec` here is perf_budgets.json -- budgets are ratified separately
    # from any one world. The loading range is a property of the WORLD,
    # and reading it off the budget file silently returned None, which is
    # how this selection quietly fell back to mtime on its first run.
    world_range_cm = None
    _wp = os.path.join(REPO, "recipes", "alpine_8k.json")
    if os.path.isfile(_wp):
        _w = json.load(io.open(_wp, encoding="utf-8"))
        world_range_cm = ((_w.get("streaming") or {})
                          .get("main_loading_range_cm"))
    if a.label:
        path = newest(a.label)
    elif world_range_cm is not None:
        matches, cands = by_declared_range(world_range_cm)
        if len(matches) > 1:
            # ⛔ AMBIGUITY REFUSES. Two artefacts legitimately describe this
            # world at this range and there is no safe automatic tiebreak --
            # first-sorted silently freezes the gate on the oldest, newest is
            # the mtime rule the 2026-09-11 ruling removed. Make it explicit.
            print("check_perf — REFUSED: %d STANDALONE artefacts declare the "
                  "world's loading range of %d cm (%.0f m). Naming one is the "
                  "operator's call, not the glob's."
                  % (len(matches), int(world_range_cm),
                     float(world_range_cm) / 100.0))
            for p in matches:
                print("    %s" % os.path.basename(p))
            print("  Re-run with --label <suffix>, e.g. --label %s"
                  % os.path.basename(matches[-1]).rsplit("_", 1)[-1][:-5])
            print("  Picking first-sorted would report a PASS about whichever")
            print("  file happened to sort first, and would never displace it")
            print("  as newer measurements arrive.")
            return 5
        path = matches[0] if matches else None
        if not path:
            print("check_perf — REFUSED: no STANDALONE artefact declares "
                  "the world's loading range of %d cm (%.0f m)."
                  % (int(world_range_cm), float(world_range_cm) / 100.0))
            print("  A perf artefact is evidence about the world it was")
            print("  measured in. Judging this world against another's is")
            print("  how the 768 m RED was re-reported after the ruling")
            print("  that RED itself caused. Artefacts seen:")
            for p, r, mc in cands:
                print("    %-46s range %-8s %s"
                      % (os.path.basename(p),
                         ("%d cm" % int(r)) if r is not None else "UNDECLARED",
                         "standalone" if class_ok(mc) else "not standalone"))
            print("  Run scripts/perf_standalone.py at the ruled range.")
            return 5
    else:
        path = newest(a.label)
    if not path:
        print("NO DATA: no artefact under _verify/perf/. Run "
              "scripts/perf_flythrough.py. This is 'I could not look', which "
              "is not a pass.")
        return 5

    data = json.load(io.open(path, encoding="utf-8"))

    # MEASUREMENT-CLASS GATE (ruled 2026-09-10). Refuse BEFORE judging:
    # an editor-class artefact judged against standalone budgets produces
    # verdicts of unknown class in either direction.
    if bool((rec.get("gates") or {}).get(
            "require_measurement_class_standalone", False)):
        mclass = data.get("_measurement_class")
        if not class_ok(mclass):
            print("check_perf — %s" % os.path.relpath(path, REPO))
            print("REFUSED: the budgets are ratified for the STANDALONE")
            print("class and this artefact declares %r." % (mclass,))
            print("An editor-class number tracks the editor's tick clamp")
            print("(EditorEngine.cpp:2523-2566) — it reported a plaza-Game")
            print("RED for four days that no content change caused. Run")
            print("scripts/perf_standalone.py and judge that artefact.")
            return 6

    invalidated = [s["zone"] for s in (rec.get("spline") or {}).get("stations", [])
                   if s.get("basis_invalidated")]
    frame_budget = (rec.get("target") or {}).get("frame_budget_ms")
    verdict, rows = judge(data, budgets, tol, game_budgets, invalidated,
                          frame_budget)

    print("check_perf — %s" % os.path.relpath(path, REPO))
    print("  metric: %s %s   (%s)" % (METRIC, STAT, _WHY))
    print("  class : %s"
          % str(data.get("_measurement_class") or "UNDECLARED")[:96])
    print()
    for r in rows:
        print("  %-12s %s" % (r["zone"], r["line"]))
    print()
    if verdict == "NO BUDGET":
        print("NO RATIFIED BUDGET — recipes/perf_budgets.json carries "
              "per_zone_ms: null.")
        print("This is a FINDING, not a pass: the law is written and unratified.")
        return 3
    if verdict == "RED":
        print("RED — at least one zone is over budget.")
        return 4

    # ZERO-COMPARISON REFUSAL (non-negotiable 13). `judge` seeds worst="PASS"
    # and only ever downgrades it inside the station loop, so an artefact with
    # NO stations, or one whose every station is invalidated, reaches here as a
    # "PASS" over zero budget comparisons. (The all-UNBUDGETED case is already
    # caught above as NO BUDGET -> exit 3.) A PASS beside a zero sample count is
    # silence wearing agreement's clothes; refuse and report the count.
    judged = sum(1 for r in rows if r.get("had_budget"))
    if judged == 0:
        why = ("the artefact declares no stations"
               if not rows else
               "every station is invalidated (camera re-derived), so none was "
               "judged against a budget")
        print("REFUSED: 0 of %d zones produced a budget comparison — %s. A "
              "PASS over zero comparisons is not agreement (non-negotiable 13)."
              % (len(rows), why))
        return 5

    ratified = bool((rec.get("gates") or {}).get("ratified", False))
    if not ratified:
        print("Every zone is within the PROPOSED budgets (+%.0f%% tolerance)."
              % (tol * 100))
        print()
        print("BUT THE BUDGETS ARE NOT RATIFIED — recipes/perf_budgets.json has")
        print("gates.ratified = false. This is a FINDING, not a pass: a suite")
        print("that reports green over a law nobody agreed to is worse than one")
        print("with no perf check at all. Flip it at GATE E.")
        return 3

    print("PASS — every zone within budget (+%.0f%% tolerance)." % (tol * 100))
    return 0


def judge(data, budgets, tol, game_budgets=None, invalidated=None,
          frame_budget=None):
    """Check EVERY declared budget, not just the GPU one.

    per_zone_game_ms exists because the baseline showed the GAME THREAD is the
    binding thread at all four zones. A checker that read only the GPU budget
    would leave that declaration inert -- a field that reads like a setting and
    polices nothing, which is the exact class flagged twice elsewhere in this
    repo today (landmark.spire_mesh, and five decorative gate booleans).

    `invalidated` names zones whose STATION CAMERA HAS MOVED since the budget
    was ratified. Those get NO VERDICT, never PASS and never RED. A budget is a
    number about a viewpoint; re-deriving the viewpoint leaves the number
    describing a camera that no longer exists, and comparing a fresh
    measurement against it produces a verdict of unknown class -- the same
    reasoning the FOV gate already applies when a read-back disagrees by more
    than 0.05 deg (perf_flythrough, 2026-09-05). Added 2026-09-05 when
    `treeline` and `vista` were re-derived; see R-BENCHSTATION.
    """
    rows, worst = [], "PASS"
    invalidated = set(invalidated or ())

    def bump(v):
        nonlocal worst
        if v == "NO BUDGET":
            worst = "NO BUDGET"
        elif v == "RED" and worst != "NO BUDGET":
            worst = "RED"

    for st in data.get("stations", []):
        zone = st.get("zone")
        stats = st.get("stats_ms") or {}
        if zone in invalidated:
            gpu = (stats.get(METRIC) or {}).get(STAT)
            game = (stats.get("GameThreadTime") or {}).get(STAT)
            rows.append({"zone": zone, "had_budget": False, "no_verdict": True,
                         "line": ("NO VERDICT — station camera re-derived; the "
                                  "ratified budget describes the OLD viewpoint. "
                                  "measured GPU %s Game %s, unjudged until "
                                  "re-measured and re-ratified."
                                  % ("%.2f" % gpu if gpu is not None else "n/a",
                                     "%.2f" % game if game is not None else "n/a"))})
            continue
        parts, any_budget = [], False
        metrics = [("GPU", METRIC, budgets),
                   ("Game", "GameThreadTime", game_budgets)]
        if frame_budget is not None:
            # One frame budget, every zone (ruled 2026-09-10: 16.6 ms on
            # FrameTime p90, meaningful only in the standalone class the
            # gate above enforces). Absent -> no Frame row at all, so the
            # editor-era selftest cases stay valid.
            metrics.append(("Frame", "FrameTime",
                            {zone: float(frame_budget)}))
        for label, metric, table in metrics:
            val = (stats.get(metric) or {}).get(STAT)
            if val is None:
                parts.append("%s: NO MEASUREMENT" % label)
                bump("RED")
                continue
            if not table or zone not in table:
                parts.append("%s %.2f (no budget)" % (label, val))
                bump("NO BUDGET")
                continue
            any_budget = True
            b = float(table[zone])
            if val > b * (1.0 + tol):
                parts.append("%s %.2f vs %.2f ** OVER by %.2f (%.0f%%) **"
                             % (label, val, b, val - b, 100.0 * (val - b) / b))
                bump("RED")
            else:
                parts.append("%s %.2f vs %.2f ok" % (label, val, b))
        rows.append({"zone": zone, "line": "   ".join(parts),
                     "had_budget": any_budget})
    return worst, rows


if __name__ == "__main__":
    sys.exit(main())
