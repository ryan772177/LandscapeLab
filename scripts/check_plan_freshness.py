"""Is each committed PLAN still the plan its inputs would produce?

Offline and READ-ONLY. No editor, no world, no writes to any tracked file.

WHY THIS EXISTS
---------------
A plan on disk is a DERIVED RECORD (non-negotiable 15) and nothing in this repo
re-checks one. `plan_city` and `plan_encounters` write `city/*.json` and
`encounters/*.json`; the recipes and the planners underneath them move; and the
artefact keeps sitting at exactly the path a placer reads, looking current.

**This is not hypothetical. `encounters/alpine_8k_all.json` was found carrying
five encounters that its own producer now REFUSES to generate** -- the
availability denominator was corrected afterwards and the target went from 5 to
0. Anything consuming that file would place encounters in ground the player
cannot reach, in a basin that the corrected method says is safe by design.

Non-negotiable 20 is the deeper form: an adopted artefact should be hash-proven
against its source AT ADOPTION TIME. These plans carry their inputs' PATHS and
not their HASHES, so freshness cannot be read off the file. Stamping them is
OWED; until it lands, this tool answers the question from outside.

THE INSTRUMENTS, AND THEY DO NOT SHARE A SOURCE
-----------------------------------------------
    STAMP       plan_stamp.verify: does each declared input still hash to the
                value recorded in the plan's stamp block? A fact on disk, the
                cheapest, and it OUTRANKS HISTORY -- a changed hash IS a changed
                input, where a commit that touched a producer is only a
                suspicion. The CONSUMED-FIELD variant (verify_consumed) narrows
                a whole-file DIFFERS to the fields the producer actually reads.

    HISTORY     git: is any declared input committed LATER than the artefact?
                Cheap, runs on every plan, and can only ever be a SUSPICION --
                a commit that touched a planner may not have changed its output.

    REPRODUCE   re-run the producer to a TEMPORARY path and compare bytes.
                Decisive, and the only one that can say REPRODUCES. Costs a
                planner run. `--reproduce` opts in.

STAMP/HISTORY say "these inputs moved"; REPRODUCE says "and here is whether it
mattered". Agreement is independent measurements, because one reads hashes, one
reads git, and one reads the arithmetic.

WHAT IT REFUSES TO CLAIM
------------------------
An artefact whose producer cannot run offline -- `city/*_reachable.json` comes
from an in-editor payload against a BUILT navmesh -- is reported CANNOT
REPRODUCE, never FRESH. An artefact that declares no inputs is reported
UNSTAMPED, never FRESH. "I could not look" is not "I looked and it is fine"
(non-negotiable 6).

USAGE
-----
    python scripts/check_plan_freshness.py              audit the corpus
    python scripts/check_plan_freshness.py --reproduce  ...decisively
    python scripts/check_plan_freshness.py --self-test  prove the INSTRUMENT

`--self-test` is STANDALONE and never touches the corpus: it stamps a
synthetic fixture in a temp tree and mutates that. "Does this tool work?" and
"is the corpus fresh?" are different questions, and letting the second answer
the first is what broke this tool on 2026-08-30.

Exit 0  every checkable plan is fresh (or ruled DIVERGENT-BY-RULING)
Exit 1  --self-test: the instrument itself failed
Exit 3  at least one plan is STALE or its producer now REFUSES it
Exit 4  nothing could be checked at all
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import plan_stamp                                            # noqa: E402

# Where plans live. A directory with no plans is not an error.
PLAN_DIRS = ["city", "encounters", "foliage"]

# INPUT_KEYS lives in plan_stamp, NOT here. The producers stamp that key set
# and this reads it; two copies would be two lists that must agree, and adding
# an input to one and not the other is exactly the failure mode
# non-negotiable 24 describes.
INPUT_KEYS = list(plan_stamp.INPUT_KEYS)


def git(*args):
    p = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                       cwd=REPO_ROOT)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def last_commit_epoch(path):
    """Unix time of the last commit touching `path`, or None if untracked."""
    rc, out, _ = git("log", "-1", "--format=%ct", "--", path)
    if rc != 0 or not out:
        return None
    try:
        return int(out.splitlines()[0])
    except ValueError:
        return None


def sha12(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:12]


def sha12_content(path):
    """sha12 with line endings normalised, for comparing a REPRODUCED artefact
    against a committed one. See the note in reproduce(): the producers write
    CRLF on Windows and git checks out LF, so a raw-byte comparison reports a
    difference that is not one. Input STAMPING deliberately still uses sha12 --
    there the bytes on disk are the thing being attested."""
    raw = io.open(path, "rb").read().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:12]


META_KEYS = ("_input_sha256", "_consumed_sha256", "_stamp_waiver",
             "_divergence_note")


def payload_sha12(doc):
    """Canonical hash of a plan's PAYLOAD — every key except the stamp/
    waiver/note metadata. This is what a ruled _divergence_note binds to
    (R6-Q1): the note lives INSIDE the file, so a raw-bytes binding
    could never converge (writing the note moves the hash it binds).
    The payload hash moves exactly when the DIVERGENCE does."""
    p = {k: v for k, v in doc.items() if k not in META_KEYS}
    canon = json.dumps(p, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def declared_inputs(doc):
    """Repo-relative input paths a plan declares, that actually exist.

    A declared path that does NOT exist is returned separately: it is a defect
    in its own right and must not be silently dropped, or a plan that names a
    deleted recipe reads as having no inputs and therefore as unstamped.
    """
    found, missing = [], []
    for k in INPUT_KEYS:
        v = doc.get(k)
        if not isinstance(v, str) or "/" not in v:
            continue
        if os.path.exists(os.path.join(REPO_ROOT, v)):
            found.append((k, v))
        else:
            missing.append((k, v))
    return found, missing


def reproduce(doc, plan_path):
    """Re-run the producer to a temp path. Returns (verdict, detail) on an
    early exit, or (verdict, detail, payload_pair) once a comparison completes."""
    producer = doc.get("_produced_by")
    if not isinstance(producer, str):
        return "CANNOT REPRODUCE", "no _produced_by"
    abs_producer = os.path.join(REPO_ROOT, producer)
    if not os.path.exists(abs_producer):
        return "CANNOT REPRODUCE", "producer %s is absent" % producer

    src = io.open(abs_producer, encoding="utf-8", errors="replace").read()
    if "--out" not in src:
        return ("CANNOT REPRODUCE",
                "%s takes no --out, so it cannot be run to a temp path and "
                "must not be run to its real one" % producer)

    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="freshness_")
    os.close(fd)
    os.remove(tmp)
    env = dict(os.environ)
    sdir = os.path.join(REPO_ROOT, "scripts")
    env["PYTHONPATH"] = (sdir + os.pathsep + env["PYTHONPATH"]
                         if env.get("PYTHONPATH") else sdir)
    try:
        p = subprocess.run([sys.executable, abs_producer, "--out", tmp],
                           capture_output=True, text=True, cwd=REPO_ROOT,
                           env=env)
        if p.returncode != 0:
            blob = (p.stdout or "") + (p.stderr or "")
            tail = [ln for ln in blob.splitlines() if ln.strip()]
            why = tail[-1][:160] if tail else "no output"
            # !! AN ARGPARSE USAGE ERROR IS NOT A REFUSAL.
            # PRODUCER REFUSES means the producer looked at its inputs and
            # DECLINED -- a finding worth acting on. A missing required
            # argument means THIS CHECKER does not know how to invoke it,
            # which is the checker's limit, not the artefact's problem.
            # `adopt_verified_encounters` needs --rows as well as --out,
            # because reproducing it requires in-editor navmesh verdicts that
            # no offline run can recreate. Reporting that as a refusal would
            # send a reader hunting for a defect in a healthy artefact.
            if ("the following arguments are required" in blob
                    or "error: argument" in blob):
                return ("CANNOT REPRODUCE",
                        "%s needs arguments beyond --out that this checker "
                        "cannot supply (%s). The STAMP still proves its "
                        "inputs are unchanged."
                        % (producer, why.split("error:")[-1].strip()[:80]))
            # ...and the MIRROR: the producer does NOT take --out at all.
            # The `"--out" not in src` guard above misses this when the
            # STRING "--out" appears only in the producer's prose (e.g.
            # place_foliage.py names it in a docstring), so the checker runs
            # it with --out and argparse rejects it. An "unrecognized
            # arguments: --out" is the same class as the required-arguments
            # case: this checker cannot invoke the producer, which is the
            # checker's limit, not a refusal by the artefact. The STAMP (and
            # for the foliage plans a RULED _stamp_waiver — EXPECTED-
            # UNREPRODUCIBLE, stochastic placement) carries freshness.
            # Added 2026-09-19b (Brief-4 T10; place_foliage T9 rewire).
            # Anchor to the arg the checker itself supplied (--out): argparse
            # names the rejected tokens, and the checker passes only
            # `--out <tmp>`, so this fires exactly when OUR invocation is
            # rejected -- not on an "unrecognized arguments" leaking from a
            # grandchild's stderr (auditor F1). Report the argparse line, not
            # an assertion about the producer's source (auditor F2).
            if "unrecognized arguments: --out" in blob:
                return ("CANNOT REPRODUCE",
                        "%s does not accept --out, so this checker cannot run "
                        "it to a temp path (%s). The STAMP still proves its "
                        "inputs are unchanged."
                        % (producer, why.split("error:")[-1].strip()[:80]))
            return "PRODUCER REFUSES", why
        if not os.path.exists(tmp):
            return "PRODUCER REFUSES", "exited 0 and wrote nothing"
        # COMPARE CONTENT, NOT LINE ENDINGS.
        #
        # This compared RAW BYTES and reported DIFFERS on a plan that
        # reproduces perfectly. Diagnosed 2026-08-29: the producers write with
        # the platform default (CRLF on Windows) while git stores and checks
        # out LF, so the committed plan had 0 CRLF and a fresh run had 23,029.
        # The two files were byte-identical after CRLF -> LF and every parsed
        # key was equal. ANY FRESH CLONE OF THIS REPO WOULD HAVE HIT IT -- the
        # working copy only escaped because it still held the CRLF file the
        # producer originally wrote.
        #
        # This is the representation trap non-negotiable 0 is about, inside a
        # checker: comparing two things that were never in the same
        # representation and reading the difference as a finding about the
        # artefact. Normalising is not weakening the check -- a real content
        # change still moves the hash, which --self-test proves.
        same_content = sha12_content(tmp) == sha12_content(plan_path)
        # the PAYLOAD pair rides along for the ruled-divergence binding
        # (R6-Q1): metadata (stamps/waivers/notes) is excluded, so the
        # pair moves exactly when the divergence does.
        try:
            pair = (payload_sha12(json.load(io.open(plan_path,
                                                    encoding="utf-8"))),
                    payload_sha12(json.load(io.open(tmp,
                                                   encoding="utf-8"))))
        except ValueError:
            pair = None
        # THE VERDICT JUDGES THE PAYLOAD (R-PLANSTALE amendment 1e,
        # 2026-09-16): the plan IS its payload; the stamp block records
        # moving input hashes BY DESIGN, so a producer edit ripples
        # metadata through every downstream plan while the plan itself
        # is byte-identical. Whole-content identity remains reported;
        # only when the payload cannot be parsed does it decide.
        same = (pair[0] == pair[1]) if pair else same_content
        note = ""
        if pair and pair[0] == pair[1] and not same_content:
            note = "  [metadata-only drift: stamps/waivers moved, the "\
                   "plan did not]"
        return (("REPRODUCES" if same else "DIFFERS"),
                "%s vs %s%s%s" % (sha12_content(plan_path),
                                  sha12_content(tmp),
                                  ("  (payload %s vs %s)" % pair)
                                  if pair else "", note),
                pair)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _stamp_covers(doc, path):
    """Did the STAMP actually adjudicate this input path?

    HISTORY iterates the DECLARED inputs; the stamp iterates only the paths
    recorded in its hash map. Those sets can drift -- add an INPUT_KEY, or let
    a plan gain a sidecar after stamping, and HISTORY sees an input the stamp
    silently ignores. A waiver may only suppress HISTORY where a value-level
    measurement actually exists to defer to.
    """
    st = doc.get(plan_stamp.STAMP_KEY) or {}
    return path in st


def waiver_covers(doc, sbad, consumed=None):
    """Decide whether a declared _stamp_waiver excuses THIS stamp difference.

    Returns (waived, message). A waiver is a gate turned off, so it is granted
    only when it is fully specific:

      * it must name EVERY differing input -- one unnamed input and the plan
        is STALE exactly as before,
      * it must carry a non-empty `why`; a waiver with no reason is not a
        waiver, it is a silenced alarm,
      * it never applies to UNREADABLE (that is "I could not look", which is
        never a pass), and never to a failed --reproduce — with ONE ruled
        exception (R6-Q1, 2026-09-16): a `_divergence_note` carrying a
        ruling id + retires_when + a binding to the observed content-hash
        pair reads as DIVERGENT-BY-RULING via `divergence_ruled`, its own
        loud verdict — never through THIS function. Both are handled by
        the caller.

    R5 (E-4) adds two granted_for entry KINDS beside the whole-file pair:

      * {"kind": "consumed", "from": h, "to": h} binds to the CONSUMED
        subset pair (needs `consumed` = plan_stamp.verify_consumed rows),
        so an edit to unconsumed fields cannot expire the waiver while a
        consumed-field change still does;
      * {"kind": "ruled", "ruling": id, "retires_when": text} is for
        SCRIPT inputs on EXPECTED-UNREPRODUCIBLE plans only: the
        justification is change-independent (no producer edit alters
        committed rows), so it binds to the RULING, not a hash pair --
        and it REFUSES unless both fields are non-empty and the path is
        a script/payload (a JSON input has a consumed instrument and may
        not use this class).

    Kept as a function so it can be PROVEN TO REFUSE -- see self_test().
    """
    w = doc.get("_stamp_waiver")
    if not isinstance(w, dict):
        return False, ""
    named = set(w.get("inputs") or [])
    differing = set(p for p, _, _ in sbad)
    why = (w.get("why") or "").strip()
    if not differing:
        return False, ""
    uncovered = differing - named
    if uncovered:
        return False, ("WAIVER DOES NOT COVER %s -- still STALE"
                       % ", ".join(sorted(uncovered)))
    if not why:
        return False, ("WAIVER NAMES THE INPUTS BUT GIVES NO REASON -- "
                       "not a waiver, still STALE")
    # ⭐ BIND THE WAIVER TO THE HASH PAIR IT WAS GRANTED AGAINST.
    #
    # A waiver naming only a PATH excuses that path forever: the next,
    # unrelated change to the same file silently inherits this waiver's
    # justification. The reasoning was about ONE measured byte difference, so
    # it should expire the moment that difference changes.
    #
    # `granted_for` is {path: {"from": recorded12, "to": actual12}}. Declaring
    # it is optional TODAY so the existing waiver keeps working, but a waiver
    # without it is told, every run, that it cannot expire on its own.
    granted = w.get("granted_for")
    if isinstance(granted, dict) and granted:
        ruled_notes = []
        for path, rec, act in sbad:
            g = granted.get(path)
            if not isinstance(g, dict):
                return False, ("WAIVER DECLARES granted_for BUT NOT FOR %s -- "
                               "still STALE" % path)
            kind = g.get("kind") or "whole"
            if kind == "ruled":
                # R5/Q1: ruling-bound, script inputs only, both fields
                # required, and it PRINTS its ruling every run.
                if not path.endswith((".py", ".txt")):
                    return False, (
                        "RULED WAIVER REFUSED for %s -- the ruled class is "
                        "for SCRIPT inputs only; a JSON input has the "
                        "consumed-field instrument" % path)
                if not (g.get("ruling") or "").strip() \
                        or not (g.get("retires_when") or "").strip():
                    return False, (
                        "RULED WAIVER REFUSED for %s -- it must carry both "
                        "`ruling` and `retires_when`" % path)
                ruled_notes.append(
                    "RULED for %s by %s; RETIRES WHEN %s"
                    % (path, g["ruling"].strip(),
                       g["retires_when"].strip()))
                continue
            if kind == "consumed":
                crow = (consumed or {}).get(path)
                if not crow:
                    return False, (
                        "CONSUMED WAIVER REFUSED for %s -- the plan carries "
                        "no consumed stamp for it, so there is no subset "
                        "measurement to bind to" % path)
                if crow[0] != "DIFFERS":
                    # auditor F1: an UNREADABLE consumed row yields
                    # actual None -> "" and a waiver authored with
                    # to:"" would bind to a FAILED measurement. "I
                    # could not look" is never a pass.
                    return False, (
                        "CONSUMED WAIVER REFUSED for %s -- the consumed "
                        "measurement is %s, not DIFFERS; a waiver may "
                        "not bind to a failed or absent measurement"
                        % (path, crow[0]))
                _cv, _nf, c_rec, c_act = crow
                c_rec12 = (c_rec or "")[:12]
                c_act12 = (c_act or "")[:12]
                if g.get("from") != c_rec12 or g.get("to") != c_act12:
                    return False, (
                        "CONSUMED WAIVER EXPIRED for %s -- granted against "
                        "consumed %s -> %s, now %s -> %s"
                        % (path, g.get("from"), g.get("to"),
                           c_rec12, c_act12))
                continue
            if g.get("from") != rec or g.get("to") != act:
                return False, (
                    "WAIVER EXPIRED for %s -- it was granted against "
                    "%s -> %s and the file now reads %s -> %s. The reasoning "
                    "was about a specific byte difference; this is a "
                    "different one." % (path, g.get("from"), g.get("to"),
                                        rec, act))
        tail = "  [bound to the hash pair; expires if it moves]"
        if ruled_notes:
            tail = "  [" + "; ".join(ruled_notes) + "]"
        return True, why + tail
    return True, (why + "  [⚠ NOT BOUND TO A HASH PAIR -- this waiver will "
                  "excuse the NEXT change to the same file too. Add "
                  "granted_for {path: {from, to}} so it expires by itself.]")


def divergence_ruled(note, committed12, fresh12):
    """R6-Q1 (2026-09-16): may a --reproduce DIFFERS read as
    DIVERGENT-BY-RULING instead of red?

    Granted ONLY when the _divergence_note carries ALL of:
      * a non-empty `ruling` id — the divergence is itself ruled,
      * a non-empty `retires_when` — the gate that ends it is named,
      * `bound_to` {committed, fresh} equal to the OBSERVED PAYLOAD-hash
        pair (payload_sha12 — metadata excluded, because the note lives
        INSIDE the file and a raw-bytes binding could never converge) —
        the reasoning covers THIS divergence; the next, different one
        goes red again (mirror of waiver_covers' granted_for).

    Returns (ok, message). Never called for PRODUCER REFUSES — a refusal
    is not a divergence. Pure, so the self-test proves all three
    directions without running a producer.
    """
    if not isinstance(note, dict):
        return False, ""
    ruling = (note.get("ruling") or "").strip()
    retires = (note.get("retires_when") or "").strip()
    bound = note.get("bound_to")
    if not ruling or not retires:
        return False, ("divergence note lacks ruling and/or retires_when "
                       "-- declared but NOT ruled; stays red")
    if not isinstance(bound, dict) \
            or bound.get("committed") != committed12 \
            or bound.get("fresh") != fresh12:
        return False, (
            "DIVERGENCE NOTE EXPIRED -- ruled against pair %s -> %s, "
            "observed %s -> %s. The ruling covered a specific divergence; "
            "this is a different one."
            % ((bound or {}).get("committed"), (bound or {}).get("fresh"),
               committed12, fresh12))
    return True, ("DIVERGENT-BY-RULING %s; RETIRES WHEN %s; bound to "
                  "%s -> %s" % (ruling, retires, committed12, fresh12))


def _synthetic_fixture(tmp):
    """A throwaway repo root with a freshly stamped doc. MATCHES by construction.

    ⛔ THE FIXTURE MUST NOT BE A LIVE ARTEFACT. It used to be
    `city/alpine_basin_town_plan.json`, and on 2026-08-30 that broke the whole
    instrument: RULING 4 changed `recipes/city.json` and `scripts/plan_city.py`
    one commit after the plan was stamped, so `verify` correctly returned
    DIFFERS and the POSITIVE CONTROL -- which asserted MATCHES -- failed.

    **The instrument was right and the fixture was wrong.** Worse, the control
    and the artefact under test were THE SAME OBJECT, so they were never two
    measurements (non-negotiable 0). An approved, recorded, deliberately-gated
    change to the town plan silently destroyed the instrument's ability to
    certify itself, and the failure read as "the stamp checker is broken".

    Stamping into a temp tree and verifying immediately has no such coupling:
    nothing between the stamp and the check can move.
    """
    os.makedirs(os.path.join(tmp, "recipes"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
    with io.open(os.path.join(tmp, "recipes", "fixture.json"), "w",
                 encoding="utf-8") as fh:
        fh.write('{"storey_m": 2.0}')
    with io.open(os.path.join(tmp, "recipes", "world.json"), "w",
                 encoding="utf-8") as fh:
        fh.write('{"world": "fixture"}')
    with io.open(os.path.join(tmp, "scripts", "producer.py"), "w",
                 encoding="utf-8") as fh:
        fh.write("# a producer that exists\n")
    doc = {"_produced_by": "scripts/producer.py",
           "_recipe": "recipes/fixture.json",
           "_world": "recipes/world.json",
           "rows": [1, 2, 3]}
    doc[plan_stamp.STAMP_KEY] = plan_stamp.stamp(doc, tmp)
    return doc


def self_test():
    """Prove the STAMP instrument refuses. It has only seen matching inputs.

    Every stamp case runs against a SYNTHETIC fixture that is MATCHES by
    construction, so each mutation is measured against a known-good control
    rather than against whatever the repo happens to hold today. The live plan
    is still inspected, but only REPORTED -- never asserted (see below).

    A stamp check that has only ever said MATCHES is non-negotiable 2's
    untested gate; a stamp check whose control is a moving target is worse,
    because it fails for reasons that have nothing to do with the instrument.
    """
    import shutil
    import tempfile

    cases = []
    tmp = tempfile.mkdtemp(prefix="stamp_selftest_")
    try:
        doc = _synthetic_fixture(tmp)
        root = tmp

        # POSITIVE CONTROL: stamped a moment ago, nothing touched since.
        # If this fails, no refusal below proves anything.
        v, _ = plan_stamp.verify(doc, root)
        cases.append(("POSITIVE CONTROL (unmutated)", v, "MATCHES"))

        # !! EACH MUTATION IS NOW MEASURED AGAINST A **MATCHES** BASELINE.
        # Against the old stale live plan the verdict half of this next case
        # was VACUOUS -- `verify` returned DIFFERS whether or not the hash was
        # corrupted, because two real inputs already differed. Only the
        # `named` assertion was still doing work. A refusal that would have
        # happened anyway is not evidence that the gate refuses.

        # one recorded hash corrupted -> DIFFERS, naming that input
        d2 = json.loads(json.dumps(doc))
        victim = sorted(d2[plan_stamp.STAMP_KEY])[0]
        d2[plan_stamp.STAMP_KEY][victim] = "0" * 64
        v2, bad2 = plan_stamp.verify(d2, root)
        named = any(b[0] == victim for b in bad2)
        cases.append(("one input hash corrupted", v2 if named else
                      "%s but did not name %s" % (v2, victim), "DIFFERS"))

        # ...and ONLY that input is named. A verifier that reports every input
        # as differing would pass the case above while being useless.
        cases.append(("...and names ONLY the corrupted input",
                      sorted(b[0] for b in bad2), [victim]))

        # the stamp removed -> UNSTAMPED, never "fresh"
        d3 = json.loads(json.dumps(doc))
        d3.pop(plan_stamp.STAMP_KEY)
        v3, _ = plan_stamp.verify(d3, root)
        cases.append(("stamp removed", v3, "UNSTAMPED"))

        # a stamped input that no longer exists -> UNREADABLE, not MATCHES
        d4 = json.loads(json.dumps(doc))
        d4[plan_stamp.STAMP_KEY]["recipes/this_was_deleted.json"] = "0" * 64
        v4, _ = plan_stamp.verify(d4, root)
        cases.append(("a stamped input deleted", v4, "UNREADABLE"))

        # a REAL edit to a stamped input -> DIFFERS. The corrupted-hash case
        # mutates the RECORD; this mutates the WORLD, which is the direction
        # the instrument actually meets in production.
        d6 = json.loads(json.dumps(doc))
        with io.open(os.path.join(root, "recipes", "fixture.json"), "w",
                     encoding="utf-8") as fh:
            fh.write('{"storey_m": 3.2}')
        v6, bad6 = plan_stamp.verify(d6, root)
        cases.append(("a stamped input EDITED on disk",
                      v6 if any(b[0] == "recipes/fixture.json" for b in bad6)
                      else "%s but did not name it" % v6, "DIFFERS"))

        # stamping a doc with a missing declared input must REFUSE, not stamp
        # around it -- a stamp that omits what it could not read verifies clean
        # later against a plan built from something else.
        d5 = json.loads(json.dumps(doc))
        d5["_recipe"] = "recipes/this_was_deleted.json"
        try:
            plan_stamp.stamp(d5, root)
            v5 = "STAMPED ANYWAY"
        except RuntimeError:
            v5 = "REFUSED"
        cases.append(("stamping with a missing input", v5, "REFUSED"))

        # ---- R5 A4: THE CONSUMED-FIELD INSTRUMENT, THREE DIRECTIONS ----
        # The fixture recipe currently reads {"storey_m": 3.2} (the edit
        # above). Stamp its consumed subset now, then prove: an
        # UNCONSUMED edit reads MATCHES_CONSUMED, a CONSUMED edit reads
        # DIFFERS, and an empty field list REFUSES.
        d7 = json.loads(json.dumps(doc))
        d7[plan_stamp.CONSUMED_KEY] = plan_stamp.consumed_stamp(
            d7, root, {"_recipe": ["storey_m"]})
        with io.open(os.path.join(root, "recipes", "fixture.json"), "w",
                     encoding="utf-8") as fh:
            fh.write('{"storey_m": 3.2, "_comment": "unconsumed prose"}')
        c1 = plan_stamp.verify_consumed(d7, root)["recipes/fixture.json"]
        cases.append(("consumed: UNCONSUMED edit", c1[0],
                      "MATCHES_CONSUMED"))
        with io.open(os.path.join(root, "recipes", "fixture.json"), "w",
                     encoding="utf-8") as fh:
            fh.write('{"storey_m": 9.9, "_comment": "unconsumed prose"}')
        c2 = plan_stamp.verify_consumed(d7, root)["recipes/fixture.json"]
        cases.append(("consumed: CONSUMED edit", c2[0], "DIFFERS"))
        try:
            plan_stamp.consumed_subset_hash({"storey_m": 2.0}, [])
            c3 = "HASHED ANYWAY"
        except ValueError:
            c3 = "REFUSED"
        cases.append(("consumed: EMPTY field list", c3, "REFUSED"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- THE WAIVER MUST REFUSE IN THREE DIRECTIONS ---------------------
    # A waiver turns a gate off, so it gets the same treatment every other
    # gate here gets: prove it says NO before trusting it when it says yes.
    sbad_one = [("recipes/city.json", "aaaaaaaaaaaa", "bbbbbbbbbbbb")]
    sbad_two = sbad_one + [("recipes/alpine_8k.json", "cccccccccccc",
                            "dddddddddddd")]

    good = {"_stamp_waiver": {"inputs": ["recipes/city.json"],
                              "why": "a recorded reason"}}
    cases.append(("waiver naming the differing input",
                  "WAIVED" if waiver_covers(good, sbad_one)[0] else "STALE",
                  "WAIVED"))

    cases.append(("...but NOT a second, unnamed input",
                  "WAIVED" if waiver_covers(good, sbad_two)[0] else "STALE",
                  "STALE"))

    wrong = {"_stamp_waiver": {"inputs": ["recipes/somethingelse.json"],
                               "why": "a recorded reason"}}
    cases.append(("waiver naming the WRONG input",
                  "WAIVED" if waiver_covers(wrong, sbad_one)[0] else "STALE",
                  "STALE"))

    noreason = {"_stamp_waiver": {"inputs": ["recipes/city.json"], "why": ""}}
    cases.append(("waiver with no reason given",
                  "WAIVED" if waiver_covers(noreason, sbad_one)[0] else "STALE",
                  "STALE"))

    cases.append(("no waiver at all",
                  "WAIVED" if waiver_covers({}, sbad_one)[0] else "STALE",
                  "STALE"))

    # ---- THE HASH-PAIR BINDING MUST EXPIRE -------------------------------
    # A waiver bound to the pair it was granted against is the only kind that
    # retires by itself. Both directions are proven: the right pair grants,
    # a moved `to` refuses.
    rec, act = sbad_one[0][1], sbad_one[0][2]
    bound = {"_stamp_waiver": {
        "inputs": ["recipes/city.json"], "why": "a recorded reason",
        "granted_for": {"recipes/city.json": {"from": rec, "to": act}}}}
    cases.append(("waiver BOUND to the observed hash pair",
                  "WAIVED" if waiver_covers(bound, sbad_one)[0] else "STALE",
                  "WAIVED"))

    moved = {"_stamp_waiver": {
        "inputs": ["recipes/city.json"], "why": "a recorded reason",
        "granted_for": {"recipes/city.json": {"from": rec,
                                              "to": "0000deadbeef"}}}}
    cases.append(("...and EXPIRES when the file moves again",
                  "WAIVED" if waiver_covers(moved, sbad_one)[0] else "STALE",
                  "STALE"))

    # ---- R5: THE TWO NEW WAIVER KINDS REFUSE AND GRANT CORRECTLY --------
    cons_rows = {"recipes/city.json":
                 ("DIFFERS", 3, "e" * 64, "f" * 64)}
    cbound = {"_stamp_waiver": {
        "inputs": ["recipes/city.json"], "why": "a recorded reason",
        "granted_for": {"recipes/city.json": {
            "kind": "consumed", "from": "e" * 12, "to": "f" * 12}}}}
    cases.append(("consumed waiver bound to the consumed pair",
                  "WAIVED" if waiver_covers(cbound, sbad_one,
                                            cons_rows)[0] else "STALE",
                  "WAIVED"))
    cases.append(("consumed waiver with NO consumed stamp to bind to",
                  "WAIVED" if waiver_covers(cbound, sbad_one, {})[0]
                  else "STALE", "STALE"))
    cmoved = {"_stamp_waiver": {
        "inputs": ["recipes/city.json"], "why": "a recorded reason",
        "granted_for": {"recipes/city.json": {
            "kind": "consumed", "from": "e" * 12, "to": "0000dead0000"}}}}
    cases.append(("consumed waiver EXPIRES when the subset moves again",
                  "WAIVED" if waiver_covers(cmoved, sbad_one,
                                            cons_rows)[0] else "STALE",
                  "STALE"))
    cons_unreadable = {"recipes/city.json": ("UNREADABLE", 3, "e" * 64,
                                             None)}
    cblank = {"_stamp_waiver": {
        "inputs": ["recipes/city.json"], "why": "a recorded reason",
        "granted_for": {"recipes/city.json": {
            "kind": "consumed", "from": "e" * 12, "to": ""}}}}
    cases.append(("consumed waiver REFUSED on an UNREADABLE row",
                  "WAIVED" if waiver_covers(cblank, sbad_one,
                                            cons_unreadable)[0]
                  else "STALE", "STALE"))
    sbad_script = [("scripts/place_foliage.py", "a" * 12, "b" * 12)]
    ruled = {"_stamp_waiver": {
        "inputs": ["scripts/place_foliage.py"],
        "why": "EXPECTED-UNREPRODUCIBLE by ruling",
        "granted_for": {"scripts/place_foliage.py": {
            "kind": "ruled", "ruling": "R-TOWNEXCL / D-4",
            "retires_when": "regeneration un-gates (D-4/X-1)"}}}}
    cases.append(("ruled waiver on a SCRIPT input",
                  "WAIVED" if waiver_covers(ruled, sbad_script)[0]
                  else "STALE", "WAIVED"))
    ruled_json = json.loads(json.dumps(ruled))
    ruled_json["_stamp_waiver"]["inputs"] = ["recipes/city.json"]
    ruled_json["_stamp_waiver"]["granted_for"] = {
        "recipes/city.json": {"kind": "ruled", "ruling": "X",
                              "retires_when": "Y"}}
    cases.append(("ruled waiver REFUSED on a JSON input",
                  "WAIVED" if waiver_covers(ruled_json, sbad_one)[0]
                  else "STALE", "STALE"))
    ruled_bare = json.loads(json.dumps(ruled))
    ruled_bare["_stamp_waiver"]["granted_for"][
        "scripts/place_foliage.py"] = {"kind": "ruled", "ruling": " "}
    cases.append(("ruled waiver REFUSED without ruling+retires_when",
                  "WAIVED" if waiver_covers(ruled_bare, sbad_script)[0]
                  else "STALE", "STALE"))

    # ---- R6-Q1: DIVERGENT-BY-RULING, three directions -------------------
    full_note = {"why": "ruled divergence", "ruling": "storey_m 3.2->2.0 "
                 "(2026-09-08) + gated re-placement",
                 "retires_when": "the town rebuild un-gates",
                 "bound_to": {"committed": "aaa111", "fresh": "bbb222"}}
    cases.append(("ruled divergence: complete + bound -> non-red",
                  "RULED" if divergence_ruled(full_note, "aaa111",
                                              "bbb222")[0] else "RED",
                  "RULED"))
    bare_note = {"why": "kept", "retires_when": "someday"}
    cases.append(("ruled divergence: no ruling id -> red",
                  "RULED" if divergence_ruled(bare_note, "aaa111",
                                              "bbb222")[0] else "RED",
                  "RED"))
    cases.append(("ruled divergence: pair moved -> red (EXPIRES)",
                  "RULED" if divergence_ruled(full_note, "aaa111",
                                              "ccc333")[0] else "RED",
                  "RED"))

    # ---- HISTORY SUPPRESSION IS SCOPED TO WHAT THE STAMP ADJUDICATED -----
    # `_stamp_covers` is what stops a waiver excusing a HISTORY hit on an
    # input the stamp never hashed -- there is no value-level measurement to
    # defer to there, and waiving it would be "I could not look" reported as
    # "it is absent".
    stamped_doc = {plan_stamp.STAMP_KEY: {"recipes/city.json": "aaaa"}}
    cases.append(("stamp COVERS an input it hashed",
                  "YES" if _stamp_covers(stamped_doc, "recipes/city.json")
                  else "NO", "YES"))
    cases.append(("stamp does NOT cover an unhashed input",
                  "YES" if _stamp_covers(stamped_doc, "recipes/other.json")
                  else "NO", "NO"))

    # ---- THE LIVE PLAN IS REPORTED, NEVER ASSERTED ----------------------
    # Its freshness is the QUESTION this tool exists to answer, so it cannot
    # also be the CONTROL that certifies the tool. Surfaced here because a
    # reader running --self-test wants to see it; it can never fail the run.
    live = os.path.join(REPO_ROOT, "city", "alpine_basin_town_plan.json")
    live_note = "not present"
    if os.path.exists(live):
        try:
            ld = json.loads(io.open(live, encoding="utf-8").read())
            lv, lbad = plan_stamp.verify(ld, REPO_ROOT)
            live_note = lv
            if lbad:
                live_note += " (" + ", ".join(b[0] for b in lbad) + ")"
        except Exception as exc:
            live_note = "could not read: %s" % exc

    print("SELF-TEST of the STAMP instrument")
    print("  fixture: SYNTHETIC, stamped and verified in a temp tree")
    print("  observed (NOT asserted) city/alpine_basin_town_plan.json -> %s"
          % live_note)
    bad = []
    for label, got, want in cases:
        ok = (got == want)
        print("  %s %-34s -> %-22s want %s"
              % ("ok  " if ok else "FAIL", label, got, want))
        if not ok:
            bad.append(label)
    print()
    if bad:
        return 1, "%d case(s) did not behave: %s" % (len(bad), ", ".join(bad))
    return 0, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true",
                    help="prove the stamp instrument refuses a changed, "
                         "missing or absent stamp")
    ap.add_argument("--reproduce", action="store_true",
                    help="also re-run each producer to a temp path and "
                         "compare bytes (the decisive instrument)")
    args = ap.parse_args()

    if args.self_test:
        code, why = self_test()
        if code:
            print("SELF-TEST FAILED: %s" % why)
            return code
        print("SELF-TEST PASSED: the stamp refuses a changed hash, a missing "
              "input and an absent stamp,")
        print("and refuses to stamp around an input it cannot read. A MATCHES "
              "from it is evidence.")
        print()
        # ⛔ STANDALONE MODE -- IT MUST NOT FALL THROUGH TO THE CORPUS AUDIT.
        #
        # It used to. So `--self-test` exited 3 whenever ANY live plan was
        # stale, and the offline suite's "the input-stamp instrument refuses"
        # entry reported the INSTRUMENT as failing because of the state of the
        # CORPUS. That is the same coupling that broke the positive control,
        # one level up: the question "does this tool work?" was being answered
        # by "is the town plan fresh?", which is the question the tool exists
        # to ask.
        #
        # The suite already runs the corpus separately as `--reproduce`. Two
        # entries, two questions, and neither can now mask or fake the other.
        return 0

    rc, dirty, _ = git("status", "--porcelain")
    if dirty:
        print("NOTE: the tree is DIRTY. The HISTORY instrument reads COMMITS, "
              "so uncommitted edits to a recipe or a planner are invisible to "
              "it. REPRODUCE reads the working tree and does see them.")
        print()

    plans = []
    for d in PLAN_DIRS:
        ad = os.path.join(REPO_ROOT, d)
        if not os.path.isdir(ad):
            continue
        for name in sorted(os.listdir(ad)):
            if name.endswith(".json"):
                plans.append(os.path.join(d, name).replace("\\", "/"))

    if not plans:
        print("REFUSE: no plan artefacts found under %s" % ", ".join(PLAN_DIRS))
        return 4

    stale, unstamped, not_plans, checked = [], [], [], 0
    divergent_ruled = []          # R6-Q1: DIVERGENT-BY-RULING plans
    for rel in plans:
        ap_ = os.path.join(REPO_ROOT, rel)
        try:
            doc = json.loads(io.open(ap_, encoding="utf-8").read())
        except Exception as e:
            print("%-42s UNREADABLE  %s" % (rel, e))
            continue
        if not isinstance(doc, dict):
            print("%-42s NOT A PLAN  (top level is not an object)" % rel)
            continue

        # IS THIS EVEN A PLAN? `foliage/alpinelab_scatter.json` is a scatter
        # CONFIG -- prefix, ft_dir, species, place -- with no instance list at
        # all. It was reported as UNSTAMPED, which reads as "a plan we cannot
        # check" and is not true: there is nothing here to be stale about.
        #
        # The test is deliberately NARROW: a document is skipped only if it
        # carries NONE of the recognised plan payloads. A real plan that
        # happens to be empty still has its key and is still checked, so this
        # cannot become a way to quietly drop one.
        PAYLOAD_KEYS = ("instances", "encounters", "buildings", "streets",
                        "street_rows", "rows")
        if not any(k in doc for k in PAYLOAD_KEYS):
            not_plans.append(rel)
            continue

        found, missing = declared_inputs(doc)
        plan_t = last_commit_epoch(rel)

        if missing:
            print("%-42s !! DECLARES A MISSING INPUT" % rel)
            for k, v in missing:
                print("      %-20s %s   <- does not exist" % (k, v))
            stale.append(rel)
            continue
        if not found:
            unstamped.append(rel)
            continue
        if plan_t is None:
            print("%-42s UNTRACKED   no commit history -- HISTORY cannot "
                  "speak" % rel)
            newer = []
        else:
            newer = [(k, v) for k, v in found
                     if (last_commit_epoch(v) or 0) > plan_t]

        checked += 1
        verdict = "STALE" if newer else "fresh"
        print("%-42s %s by HISTORY   (%d inputs)"
              % (rel, verdict, len(found)))
        for k, v in newer:
            print("      %-20s %s   committed AFTER the plan" % (k, v))

        # THE STAMP -- the cheapest instrument, and a fact on disk rather than
        # a re-derivation. It outranks HISTORY, which can only ever suspect: a
        # commit that touched a producer is not a change to its output, but a
        # changed HASH is a change to its input.
        sv, sbad = plan_stamp.verify(doc, REPO_ROOT)
        smark = {"MATCHES": "ok  ", "DIFFERS": "!!  ",
                 "UNREADABLE": "!!  ", "UNSTAMPED": "--  "}.get(sv, "??  ")
        n_st = len(doc.get(plan_stamp.STAMP_KEY) or {})
        print("      %sSTAMP %-11s %s"
              % (smark, sv,
                 "%d inputs hashed" % n_st if n_st else
                 "no stamp -- CANNOT CHECK, which is not fresh"))
        for path, recdd, act in sbad:
            print("          %-32s recorded %s  actual %s"
                  % (path, recdd[:12], (act or "MISSING")[:12]))

        # R5 (E-4): THE CONSUMED-FIELD INSTRUMENT. For a DIFFERS path
        # whose consumed subset still hashes to its recorded value, the
        # value-level measurement says every field the producer READS is
        # unchanged — it outranks the whole-file hash AND (A1) the
        # HISTORY suspicion for that path, for the same reason the stamp
        # outranks HISTORY: a changed file is not a changed input if no
        # consumed field moved. The field count prints beside the
        # verdict (rule 13); an UNREADABLE consumed row is loud, never
        # skipped.
        consumed = plan_stamp.verify_consumed(doc, REPO_ROOT)
        cons_ok = set()
        for cpath, crow in sorted(consumed.items()):
            if crow[0] == "UNREADABLE":
                print("      !!  CONSUMED STAMP UNREADABLE for %s -- the "
                      "input is gone or not JSON" % cpath)
        if sv == "DIFFERS" and consumed:
            for path, recdd, act in list(sbad):
                crow = consumed.get(path)
                if crow and crow[0] == "MATCHES_CONSUMED":
                    cons_ok.add(path)
                    print("      ok  MATCHES_CONSUMED %s  (%d consumed "
                          "field(s) unchanged; the file differs only in "
                          "fields the producer does not read)"
                          % (path, crow[1]))
            remaining = [r for r in sbad if r[0] not in cons_ok]
            if not remaining:
                sv, sbad = "MATCHES_CONSUMED", []
            else:
                sbad = remaining

        # A DECLARED, NARROW WAIVER.
        #
        # This tool's own refusal message says "Re-run the producer, or RECORD
        # WHY THE ARTEFACT IS KEPT" -- and until 2026-08-29 there was nowhere
        # to record it, so the only way to keep a green suite was to excuse the
        # whole exit code, which would mask the next genuine staleness in the
        # same tool. A plan may now carry _stamp_waiver naming the inputs it
        # accepts as moved, and why.
        #
        # IT IS DELIBERATELY NARROW, because a waiver is a gate turned off:
        #   * it must name EVERY differing input; one unnamed input and the
        #     plan is STALE as before,
        #   * it only ever applies to STAMP DIFFERS, never to UNREADABLE (that
        #     is "I could not look") and never to a failed --reproduce,
        #   * and it PRINTS in full on every run, so it cannot rot quietly.
        waived = False
        if sv == "DIFFERS":
            waived, wmsg = waiver_covers(doc, sbad, consumed)
            if wmsg:
                print("      %s%s" % ("..  WAIVED, DECLARED   " if waived
                                      else "!!  ", wmsg))
        if sv == "UNREADABLE" or (sv == "DIFFERS" and not waived):
            if rel not in stale:
                stale.append(rel)

        # ⛔ HISTORY IS ADDITIVE, NOT AN ALTERNATIVE TO --reproduce.
        #
        # This was `elif newer:` until 2026-08-30, so under --reproduce -- the
        # mode the OFFLINE SUITE runs -- the HISTORY verdict never reached the
        # exit code at all, for any plan, waived or not. A plan that was STALE
        # by HISTORY, STAMP MATCHES and CANNOT REPRODUCE exited 0 in the
        # thorough mode and 3 in the cheap one: THE MORE DECISIVE FLAG WAS THE
        # WEAKER INSTRUMENT. Found by an advisor pass that went and measured
        # both modes instead of believing the code comment.
        #
        # A granted waiver DOES suppress HISTORY, but only for the exact paths
        # it names AND that the STAMP actually adjudicated. Where STAMP never
        # hashed an input, there is no value-level measurement to defer to and
        # the step-level proxy is the only instrument in the room -- waiving it
        # there would be "I could not look" reported as "it is absent"
        # (non-negotiable 6). STAMP and HISTORY answer the SAME proposition at
        # different resolutions for an input the stamp covers, so a waiver that
        # concedes the byte difference has already conceded the commit order;
        # HISTORY can only restate the premise, which is not corroboration.
        # R5 A1: a MATCHES_CONSUMED path suppresses HISTORY for that path
        # too — the value-level measurement (consumed fields unchanged)
        # outranks the step-level suspicion (committed later), by the
        # same rationale as the waiver suppression below.
        hist_bad = [(k, v) for k, v in newer
                    if not ((waived and _stamp_covers(doc, v))
                            or v in cons_ok)]
        if hist_bad and rel not in stale:
            stale.append(rel)
        if newer and cons_ok and not hist_bad and not waived:
            print("      ..  HISTORY SUPPRESSED by MATCHES_CONSUMED -- "
                  "the consumed fields of every later-committed input "
                  "are unchanged")
        if newer and waived and not hist_bad:
            print("      ..  HISTORY WAIVED   the same inputs the stamp "
                  "waiver names, and the stamp adjudicated every one")
        elif hist_bad and waived:
            print("      !!  HISTORY NOT WAIVED for %s -- the stamp never "
                  "hashed %s, so there is no value-level measurement to "
                  "defer to"
                  % (", ".join(k for k, _ in hist_bad),
                     "it" if len(hist_bad) == 1 else "them"))

        if args.reproduce:
            # reproduce returns a 3-tuple on the compared paths (the
            # payload pair rides along for the ruled-divergence binding)
            # and 2-tuples on its early CANNOT/REFUSES exits.
            _rp = reproduce(doc, ap_)
            v, detail = _rp[0], _rp[1]
            pay_pair = _rp[2] if len(_rp) > 2 else None
            # ASCII ONLY, and it is not a style preference. The first version
            # used an emoji here and died with UnicodeEncodeError on this
            # machine's cp1252 stdout -- at exactly the moment it had a
            # failure to report, having printed every PASS above it fine. A
            # tool that cannot print its own worst verdict reports success by
            # omission.
            mark = {"REPRODUCES": "ok  ", "DIFFERS": "!!  ",
                    "PRODUCER REFUSES": "!!  "}.get(v, "??  ")
            print("      %s%-18s %s" % (mark, v, detail))
            if v in ("DIFFERS", "PRODUCER REFUSES"):
                # A plan that will not reproduce stays red UNLESS the
                # divergence is ITSELF RULED (R6-Q1, 2026-09-16): a
                # _divergence_note carrying a ruling id, a retires_when,
                # and a binding to the OBSERVED content-hash pair reads
                # as DIVERGENT-BY-RULING — its own verdict, never
                # "fresh", printed in full every run. A waiver still
                # never applies here, and PRODUCER REFUSES is never
                # ruled-divergent (a refusal is not a divergence).
                note = doc.get("_divergence_note")
                ruled_ok = False
                if v == "DIFFERS" and pay_pair:
                    ruled_ok, rmsg = divergence_ruled(
                        note, pay_pair[0], pay_pair[1])
                    if rmsg:
                        print("      %s%s" % ("..  " if ruled_ok
                                              else "!!  ", rmsg))
                if ruled_ok:
                    divergent_ruled.append(rel)
                elif rel not in stale:
                    stale.append(rel)
                if not ruled_ok:
                    if isinstance(note, dict) and note.get("why"):
                        print("      ..  KNOWN-DIVERGENT, DECLARED   %s"
                              % note["why"])
                        if note.get("retires_when"):
                            print("          RETIRES WHEN: %s"
                                  % note["retires_when"])
                    else:
                        print("      !!  NO DIVERGENCE NOTE -- this failure "
                              "has no recorded reason. Add _divergence_note "
                              "{why, retires_when} or re-run the producer.")

    if not_plans:
        print()
        print("NOT PLANS -- no instance/encounter/row payload, so there is")
        print("nothing here to be stale about: %d" % len(not_plans))
        for n in not_plans:
            print("  - %s" % n)

    if unstamped:
        print()
        print("UNSTAMPED -- CANNOT CHECK, which is NOT the same as fresh: %d"
              % len(unstamped))
        for u in unstamped:
            print("  - %s" % u)
        print("  These declare no input paths, so neither instrument can")
        print("  speak. Stamping them is OWED (non-negotiable 20: an adopted")
        print("  artefact is hash-proven against its source). Until then they")
        print("  are unknown, and this tool says so rather than passing them.")

    if divergent_ruled:
        print()
        print("DIVERGENT-BY-RULING (%d declared) -- ruled, bound, gated; "
              "NOT counted fresh:" % len(divergent_ruled))
        for d_rel in divergent_ruled:
            print("  - %s" % d_rel)

    print()
    if not checked:
        print("REFUSE: nothing was checkable. Every plan was unreadable, "
              "untracked or unstamped.")
        return 4
    if stale:
        print("STALE OR UNREPRODUCIBLE: %d" % len(stale))
        for s in stale:
            print("  - %s" % s)
        print()
        print("A plan its producer will not reproduce is a plan nothing should "
              "consume. Re-run the producer, or record why the artefact is "
              "kept.")
        return 3
    if divergent_ruled:
        print("%d checkable plans are fresh; %d are DIVERGENT-BY-RULING "
              "(listed above, not counted fresh)."
              % (checked - len(divergent_ruled), len(divergent_ruled)))
    else:
        print("All %d checkable plans are fresh." % checked)
    if unstamped:
        print("%d plans remain UNCHECKABLE and are not covered by that."
              % len(unstamped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
