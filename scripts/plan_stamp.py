"""The single declaration of what a PLAN's inputs are, and their hashes.

Imported by every plan PRODUCER (plan_city, plan_encounters, place_foliage,
rock_scatter, adopt_verified_encounters, stamp_plan — which WRITE the stamp) and
by check_plan_freshness/restamp_consumed (which READ it). One declaration, many
consumers.

WHY IT IS A MODULE AND NOT THREE COPIES
---------------------------------------
`INPUT_KEYS` is a requirement checked in more than one place: a producer stamps
them, a checker verifies them. Non-negotiable 24 -- two lists that must agree
are one list, badly stored, and the test is whether adding an input key can be
done in one place and forgotten in another. Written three times it can; written
once it cannot.

WHY A STAMP AT ALL
------------------
Non-negotiable 20: an adopted artefact is hash-proven against its source AT
ADOPTION TIME. Before this, plans carried their inputs' PATHS and not their
HASHES, which is the live-pointer problem -- "is this plan current" was
answerable only by re-running the producer, whose own inputs may have moved
since. A stamp makes staleness a FACT ON DISK.

    `encounters/alpine_8k_all.json` sat in the repo carrying five encounters
    that its producer had stopped generating, and nothing could tell.

WHAT THE STAMP DOES NOT DO
--------------------------
It proves the INPUTS are unchanged. It does not prove the OUTPUT is what those
inputs would produce today -- a non-deterministic producer, or one whose
behaviour depends on something it does not declare, can still drift. Only
re-derivation settles that, which is why `check_plan_freshness.py --reproduce`
exists and why the stamp is the CHEAP instrument, not the authority.
"""
import hashlib
import io
import json
import os

# Keys whose value is a repo-relative path to an INPUT of the plan.
# `_produced_by` is an input too: a planner change can move its output.
INPUT_KEYS = ("_produced_by", "_recipe", "_world", "_biome",
              "_terrain_source", "_character", "_reachable_sidecar",
              # Added 2026-09-12b with the foliage settlement exclusion.
              # The committed town plan is a REAL input to any plan that
              # excludes the town from itself: move a building and the
              # foliage plan is stale, with nothing else on disk saying so.
              # Absent keys are skipped above, so plans that avoid no town
              # are unaffected.
              "_city_plan",
              # Added 2026-09-19 with the Brief-4 foliage regeneration. Two
              # more REAL inputs to a foliage plan: the PLANTING FIELD the
              # placement samples (regenerate it and the plan is stale) and
              # the derived WATER union mask it filters against (rebuild it
              # when a lake moves and the plan is stale) -- the same
              # live-pointer fact the _city_plan entry closed for the town.
              # Absent keys are skipped, so plans with no water/planting
              # field are unaffected.
              "_planting_field", "_water_mask")

STAMP_KEY = "_input_sha256"

# R5 (2026-09-16, E-4): the CONSUMED-FIELD stamp. The whole-file stamp
# above answers "did any input byte change"; this answers "did a field
# the producer actually READS change". A recipe edit to prose or an
# unconsumed block no longer stales every plan built from it. Non-JSON
# inputs (scripts, PNGs) have no field structure and stay whole-file.
CONSUMED_KEY = "_consumed_sha256"


def sha256_file(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def _dotpath(doc, path):
    """-> (present, value) for a dot-separated key path into a JSON doc.

    Absence is a FACT distinct from null (R5 amendment A2): a deleted
    consumed field must read as a change, and `None` is a legal value.
    """
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def consumed_subset_hash(json_doc, fields):
    """sha256 of the CANONICAL form of the consumed subset (R5 A2/A3).

    Canonical: json.dumps of the PARSED values, sorted keys, fixed
    separators — immune to whitespace/CRLF/key-order edits. An absent
    field contributes the distinct token ["<path>", 0, None] against a
    present ["<path>", 1, value], so absent != null. An empty or
    malformed field list REFUSES (raises ValueError) — a subset hash
    over nothing would verify everything (rule 13's zero-count shape).
    """
    if (not isinstance(fields, (list, tuple)) or not fields
            or not all(isinstance(f, str) and f.strip() for f in fields)):
        raise ValueError(
            "consumed_subset_hash: the consumed-field list must be a "
            "non-empty list of key paths, got %r — a hash over zero "
            "fields would match every edit" % (fields,))
    parts = []
    for f in sorted(set(fields)):
        present, v = _dotpath(json_doc, f)
        parts.append([f, 1, v] if present else [f, 0, None])
    canon = json.dumps(parts, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def consumed_stamp(doc, repo_root, declarations):
    """{repo_rel_path: {"fields": [...], "sha256": ...}} for each declared
    JSON input. `declarations` maps INPUT KEY (e.g. "_recipe") -> field
    list. REFUSES (raises) on a declared key whose path is missing,
    non-JSON, or whose field list is empty — same fail-closed posture as
    stamp() above.
    """
    out = {}
    for key, fields in sorted((declarations or {}).items()):
        rel = doc.get(key)
        if not isinstance(rel, str) or "/" not in rel:
            # SAME predicate as declared_inputs: a value that is not a
            # repo-relative forward-slash path (absent, or an absolute
            # scratch path from a prover run) is SKIPPED here exactly as
            # the whole-file stamp skips it — refusing made every
            # gate-prover run crash at exit 1 (suite, 2026-09-16). Only a
            # genuinely empty `declarations` refuses below (line 131); the
            # all-skipped case returns {} (see below) — an absent
            # instrument, not a refusal.
            continue
        ap = os.path.join(repo_root, rel)
        try:
            parsed = json.load(io.open(ap, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                "consumed_stamp: %s (%s) is not readable JSON: %s"
                % (key, rel, exc))
        out[rel] = {"fields": sorted(set(fields)),
                    "sha256": consumed_subset_hash(parsed, fields)}
    if not declarations:
        raise ValueError("consumed_stamp: no declarations given — a plan "
                         "stamped with an empty consumed set would "
                         "verify against every edit")
    # ALL declarations skipped (every input was a scratch/absolute path,
    # a prover run): return {} — the ABSENCE of the instrument, which
    # verify_consumed treats as "no consumed stamp" and the whole-file
    # hash stays authoritative. NOT a refusal: refusing crashed every
    # gate prover; and not a false-verify: {} never upgrades anything.
    return out


def verify_consumed(doc, repo_root):
    """-> {path: (verdict, n_fields, recorded, actual_or_None)}.

    Verdicts per path: MATCHES_CONSUMED (recomputed subset hash equals
    the recorded one — using the fields the PLAN recorded, so an updated
    module declaration only applies to newly stamped plans), DIFFERS,
    or UNREADABLE (file gone or not JSON — never silently skipped).
    The recorded/actual hashes ride along so a waiver can bind to the
    CONSUMED pair. Returns {} when the plan carries no consumed stamp.
    """
    rec = doc.get(CONSUMED_KEY)
    if not isinstance(rec, dict) or not rec:
        return {}
    out = {}
    for rel, entry in sorted(rec.items()):
        fields = (entry or {}).get("fields")
        recorded = (entry or {}).get("sha256")
        ap = os.path.join(repo_root, rel)
        try:
            parsed = json.load(io.open(ap, encoding="utf-8"))
            actual = consumed_subset_hash(parsed, fields)
        except (OSError, ValueError):
            out[rel] = ("UNREADABLE", len(fields or []), recorded, None)
            continue
        out[rel] = (("MATCHES_CONSUMED" if actual == recorded
                     else "DIFFERS"), len(fields), recorded, actual)
    return out


def declared_inputs(doc, repo_root):
    """-> (found, missing), each a list of (key, repo-relative path).

    A declared path that does NOT exist is returned separately rather than
    dropped. A plan naming a deleted recipe would otherwise read as a plan with
    no inputs, and therefore as merely unstamped instead of broken.
    """
    found, missing = [], []
    for k in INPUT_KEYS:
        v = doc.get(k)
        if not isinstance(v, str) or "/" not in v:
            continue
        if os.path.exists(os.path.join(repo_root, v)):
            found.append((k, v))
        else:
            missing.append((k, v))
    return found, missing


def stamp(doc, repo_root):
    """The {path: sha256} map for everything `doc` declares as an input.

    REFUSES on a declared-but-absent input rather than stamping around it: a
    stamp that silently omits an input it could not read is a stamp that will
    later verify clean against a plan built from something else.
    """
    found, missing = declared_inputs(doc, repo_root)
    if missing:
        raise RuntimeError(
            "cannot stamp: %d declared input(s) do not exist -- %s"
            % (len(missing), ", ".join("%s=%s" % kv for kv in missing)))
    if not found:
        raise RuntimeError(
            "cannot stamp: the document declares no input paths. Add at least "
            "_produced_by and _recipe before writing it, or a reader has no "
            "way to tell this plan from a stale one.")
    return {v: sha256_file(os.path.join(repo_root, v)) for _, v in found}


def verify(doc, repo_root):
    """-> (verdict, rows). Verdict is one of:

        MATCHES      every stamped input hashes to its recorded value
        DIFFERS      at least one input has changed since the plan was written
        UNSTAMPED    no stamp -- CANNOT CHECK, which is not the same as fresh
        UNREADABLE   a stamped input is gone or cannot be read

    rows is [(path, recorded, actual_or_None)] for anything that did not match,
    so a caller can name WHICH input moved rather than only that one did.
    """
    rec = doc.get(STAMP_KEY)
    if not isinstance(rec, dict) or not rec:
        return "UNSTAMPED", []
    bad = []
    unreadable = False
    for path, recorded in sorted(rec.items()):
        ap = os.path.join(repo_root, path)
        if not os.path.exists(ap):
            bad.append((path, recorded, None))
            unreadable = True
            continue
        try:
            actual = sha256_file(ap)
        except OSError:
            # exists but cannot be read (permission, is-a-directory): the
            # "cannot be read" half of the UNREADABLE contract above, which
            # otherwise crashed here instead of yielding a verdict (2026-09-17)
            bad.append((path, recorded, None))
            unreadable = True
            continue
        if actual != recorded:
            bad.append((path, recorded, actual))
    if unreadable:
        return "UNREADABLE", bad
    return ("DIFFERS" if bad else "MATCHES"), bad
