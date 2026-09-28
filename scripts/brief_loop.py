"""brief_loop.py — iterate stamp placements until the surface meets the brief.

The side-project benchmark (2026-08-31, _verify/20260831_coast_benchmark)
found that every terrain fix came from MEASURING the stamped surface, and
that blind parameter nudges converge on nothing. This automates exactly that
measure-first loop: composite -> probe the STAMPED output against the brief's
acceptance criteria -> adjust ONE bounded knob per failing check -> repeat.

WHAT IT NEVER DOES: adopt. The loop reads and writes stamps.output only —
the artefact the compositor already owns and rewrites. heightmap.source is
never touched (NN20; adoption stays a hash-proven manual step).

FAIL DIRECTION: a failure here would mean an unguarded edit to a recipe, so
everything fails CLOSED — malformed acceptance refuses before any run,
unknown placement ids refuse, and hitting the iteration cap exits nonzero
with the measurements that refused (a cap hit is a REFUSAL, not a result).

INSTRUMENT PREMISE, stated: probes read the stamped 16-bit PNG in a box
around a world point, with the compositor's own mapping — origin comes from
`landscape.location_cm`, NOT from a centred formula. The 2026-08-31 audit
caught the centred version as a coincidence: it equals location_cm for the
coast recipe (-201800 cm = -(1009*4)/2 m) and is half a cell off for
alpine_8k (-406400 cm is (n-1)-centred) — a plausible-but-shifted probe,
this project's worst measurement class. Slope is CELL-SCALE slope at the
recipe's spacing; with no detail-relief declared that approximates landform
slope, and the moment a recipe declares detail relief this premise breaks —
the probe would need landform smoothing first.

Acceptance schema (in the LAYOUT BRIEF json, key "acceptance"):

    {"id": "harbor_cove", "kind": "flat_site", "placement": "harbor_cove",
     "at_m": [-250.0, 250.0], "box_m": 320.0,
     "elev_m": [20.0, 60.0], "slope_mean_deg_max": 5.0}

    {"id": "north_peaks", "kind": "peak", "placement": "north_peaks",
     "at_m": [500.0, -1450.0], "box_m": 800.0,
     "max_elev_m": [700.0, 1400.0]}

Adjustment rules — derived, one knob per check per iteration, always logged:
  flat_site  slope too high   -> amplitude_m scaled by want/measured
                                 (carve relief is linear in amplitude),
                                 clamped to [0.3, 0.9] per step, floor 5 m
  flat_site  elevation off    -> anchor_m shifted by (target mid - measured
                                 mean), only once slope passes; FLOORED at
                                 0.0 — a site needing a negative anchor pins
                                 there and the cap refusal will say so
  peak       max height low/high -> amplitude_m scaled toward the band edge,
                                 clamped to [0.5, 2.0] per step, cap 1500 m

Ordering lint: any non-MIN placement (ADD/MAX/MASKED) whose footprint covers
a flat_site probe and runs AFTER that site's MIN carve makes the carve unable
to rule the surface (the coast benchmark's root defect, found at 33 deg mean
slope). Default REFUSE; --reorder moves all MIN carves after everything
else, logged.

Exit codes: 0 all checks pass; 2 refused (before any run, or mid-loop when a
compositor run or probe refuses); 3 iteration cap hit; selftest exits 1 on
any selftest failure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))

MAX_ITERS_DEFAULT = 6


class Refuse(Exception):
    pass


# ---------------------------------------------------------------- validation

_REQ = {
    "flat_site": ("id", "placement", "at_m", "box_m", "elev_m",
                  "slope_mean_deg_max"),
    "peak": ("id", "placement", "at_m", "box_m", "max_elev_m"),
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_acceptance(acc, placements_by_id):
    """Shape AND type before content: audit F5 — presence checks alone let
    malformed values crash mid-loop instead of refusing here."""
    if not isinstance(acc, list) or not acc:
        raise Refuse("brief has no non-empty 'acceptance' list")
    for i, c in enumerate(acc):
        if not isinstance(c, dict):
            raise Refuse("acceptance[%d] is not an object" % i)
        kind = c.get("kind")
        if kind not in _REQ:
            raise Refuse("acceptance[%d]: unknown kind %r (know: %s)"
                         % (i, kind, sorted(_REQ)))
        missing = [k for k in _REQ[kind] if k not in c]
        if missing:
            raise Refuse("acceptance[%d] (%s): missing %s"
                         % (i, c.get("id", "?"), missing))
        if c["placement"] not in placements_by_id:
            raise Refuse("acceptance[%d]: placement %r not in recipe (have: %s)"
                         % (i, c["placement"], sorted(placements_by_id)))
        at = c["at_m"]
        if (not isinstance(at, list) or len(at) != 2
                or not all(_num(v) for v in at)):
            raise Refuse("acceptance[%d]: at_m must be [x, y] numbers" % i)
        if not _num(c["box_m"]) or c["box_m"] <= 0:
            raise Refuse("acceptance[%d]: box_m must be a positive number" % i)
        if kind == "flat_site" and not _num(c["slope_mean_deg_max"]):
            raise Refuse("acceptance[%d]: slope_mean_deg_max must be a number"
                         % i)
        for band in ("elev_m", "max_elev_m"):
            if band in c:
                b = c[band]
                if (not isinstance(b, list) or len(b) != 2
                        or not all(_num(v) for v in b) or b[0] >= b[1]):
                    raise Refuse("acceptance[%d]: %s must be [lo, hi] numbers"
                                 % (i, band))


def lint_ordering(placements, checks):
    """The coast defect as a lint: MIN carve at index i, any NON-MIN blend
    at index j > i whose bbox covers the carve's probe point -> the carve
    cannot rule (audit F7: MAX/MASKED defeat it the same way ADD does)."""
    bad = []
    for c in checks:
        if c["kind"] != "flat_site":
            continue
        target = c["placement"]
        idx = {p["id"]: k for k, p in enumerate(placements)}
        ti = idx[target]
        x, y = c["at_m"]
        for k in range(ti + 1, len(placements)):
            p = placements[k]
            if p["blend"] == "MIN":
                continue
            half = p["size_m"] / 2.0
            if (abs(x - p["centre_m"][0]) <= half
                    and abs(y - p["centre_m"][1]) <= half):
                bad.append((target, p["id"]))
    return bad


# --------------------------------------------------------------- measurement

def load_height_m(path, z_scale_m):
    a = np.asarray(Image.open(path))
    if a.dtype != np.uint16:
        raise Refuse("%s is not 16-bit (%s); a broken read must refuse, not "
                     "measure garbage" % (path, a.dtype))
    return a.astype(np.float64) / 65535.0 * z_scale_m


def probe(h, spacing_m, origin_m, x_m, y_m, box_m):
    # The compositor's own mapping (composite_stamps.py:461, :1088): origin
    # comes from landscape.location_cm, never from a centred formula (audit
    # F3 — the centred version is half a cell off on (n-1)-centred recipes).
    ox_m, oy_m = origin_m
    half = int(round(box_m / 2.0 / spacing_m))
    if half < 1:
        raise Refuse("box_m %.1f is under one cell (%.1f m); an empty probe "
                     "window must refuse, not crash" % (box_m, spacing_m))
    r0 = int(round((y_m - oy_m) / spacing_m))
    c0 = int(round((x_m - ox_m) / spacing_m))
    if (r0 - half < 0 or c0 - half < 0
            or r0 + half > h.shape[0] or c0 + half > h.shape[1]):
        raise Refuse("probe at (%.0f, %.0f) box %.0f m leaves the map"
                     % (x_m, y_m, box_m))
    w = h[r0 - half:r0 + half, c0 - half:c0 + half]
    gy, gx = np.gradient(w, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return {"elev_min": float(w.min()), "elev_mean": float(w.mean()),
            "elev_max": float(w.max()), "slope_mean": float(slope.mean()),
            "slope_p90": float(np.percentile(slope, 90))}


# -------------------------------------------------------------- site scout

# Plateau clearance over the tallest ground in the box. ONE constant:
# the judge's target rule, the scout's viability test and the scout
# trigger all use it — two copies would let the scout accept sites the
# judge refuses (audit 2026-09-03 F4).
CLEARANCE_M = 3.0


def scout_site(h, spacing_m, origin_m, at_m, box_m, band_hi,
               clearance_m=CLEARANCE_M):
    """Probe rings around a refused MAX flat_site for the nearest box a
    plateau inside the band CAN rule (terrain elev_max + clearance <=
    band_hi). Returns (x, y, probe) or None.

    Mechanizes the manual coastforge shore probe (2026-09-02, done by
    hand twice): the search is LOCAL by design — radii 0.5..3.0 box
    widths, 16 bearings — because a site more than a few boxes away is
    a different composition, which is the author's call, not a knob.
    Nearest satisfying ring wins; within a ring, lowest terrain wins.
    """
    x0, y0 = at_m
    for rf in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        r = rf * box_m
        best = None
        for k in range(16):
            ang = k * math.pi / 8.0
            x, y = x0 + r * math.cos(ang), y0 + r * math.sin(ang)
            try:
                m = probe(h, spacing_m, origin_m, x, y, box_m)
            except Refuse:
                continue  # off-map candidate: skip, not fatal
            if m["elev_max"] + clearance_m <= band_hi:
                if best is None or m["elev_max"] < best[2]["elev_max"]:
                    best = (round(x, 1), round(y, 1), m)
        if best is not None:
            return best
    return None


# --------------------------------------------------------------- adjustments

def judge_and_adjust(check, m, placement):
    """Returns (passed, message, mutated) — mutates at most ONE knob."""
    if check["kind"] == "flat_site":
        want = check["slope_mean_deg_max"]
        lo, hi = check["elev_m"]

        # MAX plateau rule (2026-09-03, forge duskhighland): every rule
        # below is calibrated for ADD/MIN, and both its knob directions
        # are WRONG for a MAX surface — reducing amplitude lowers the
        # plateau INTO the flank (measured: amplitude driven 130 -> 5,
        # slope stuck at the raw flank's 15.8 deg for six iterations).
        # For MAX the single correct knob is the plateau height
        # (anchor + amplitude): set it above the tallest ground in the
        # box (m['elev_max'] + clearance) so max() rules everywhere,
        # clamped inside the elev band. If the flank tops out above the
        # band, no plateau can rule the box — geometry, not knobs.
        if placement.get("blend") == "MAX":
            if m["slope_mean"] <= want and lo <= m["elev_mean"] <= hi:
                return (True, "flat (MAX plateau): slope %.1f deg, elev "
                        "%.1f m" % (m["slope_mean"], m["elev_mean"]), False)
            anchor = placement.get("anchor_m", 0.0)
            need = m["elev_max"] + CLEARANCE_M
            if need > hi:
                return (False, "MAX plateau: terrain tops %.1f m in the "
                        "box; no plateau inside [%.0f, %.0f] can rule it "
                        "— move the site or the band (geometry, not "
                        "knobs)" % (m["elev_max"], lo, hi), False)
            tgt = min(hi, max(need, (lo + hi) / 2.0))
            new_amp = round(min(1500.0, tgt - anchor), 1)
            old = placement["amplitude_m"]
            if abs(new_amp - old) < 0.05:
                return (False, "MAX plateau already at %.1f m and still "
                        "failing (slope %.1f, elev %.1f) — geometry, not "
                        "knobs" % (anchor + old, m["slope_mean"],
                                   m["elev_mean"]), False)
            placement["amplitude_m"] = new_amp
            return (False, "MAX plateau %.1f -> %.1f m (above box max "
                    "%.1f, inside band): amplitude %.1f -> %.1f"
                    % (anchor + old, anchor + new_amp, m["elev_max"],
                       old, new_amp), True)

        if m["slope_mean"] > want:
            old = placement["amplitude_m"]
            if old > 5.05:
                f = max(0.3, min(0.9, want / m["slope_mean"]))
                placement["amplitude_m"] = max(5.0, round(old * f, 1))
                return (False, "slope %.1f > %.1f deg -> amplitude %.1f -> "
                        "%.1f" % (m["slope_mean"], want, old,
                                  placement["amplitude_m"]), True)
            # Amplitude is at its floor and slope still fails: the slope is
            # the UNDERLYING surface showing through where the carve does
            # not reach (canyon-wall case, 2026-08-31 overnight — amp
            # pinned at 5.0 for four iterations while slope sat at 23 deg).
            # The knob that widens the planed area is the ANCHOR: cut
            # deeper. Bounded 15% per step; anchor 0 leaves nothing to cut
            # toward and the cap refusal is then the honest answer.
            olda = placement.get("anchor_m", 0.0)
            if olda <= 0.0:
                return (False, "slope %.1f deg with amplitude at floor and "
                        "anchor 0 — no knob left" % m["slope_mean"], False)
            placement["anchor_m"] = round(olda * 0.85, 1)
            return (False, "slope %.1f deg, amplitude at floor -> planing "
                    "deeper: anchor %.1f -> %.1f"
                    % (m["slope_mean"], olda, placement["anchor_m"]), True)
        if not (lo <= m["elev_mean"] <= hi):
            old = placement.get("anchor_m", 0.0)
            if m["elev_mean"] > hi and old <= 0.05:
                # Site TOO HIGH with the anchor already floored: the carve
                # profile (anchor + stamp*amplitude) is what holds it up,
                # so the knob is AMPLITUDE — a shallower profile cuts
                # deeper under MIN. (2026-09-02 coast recarve: ocean floor
                # 96 m over a [4, 20] band with anchor at 8; the anchor
                # rule alone dead-ends at 0 and refuses.)
                olda = placement["amplitude_m"]
                tgt = (lo + hi) / 2.0
                f = max(0.2, min(0.9, tgt / max(m["elev_mean"], 1.0)))
                placement["amplitude_m"] = max(5.0, round(olda * f, 1))
                return (False, "elev mean %.1f ABOVE [%.0f, %.0f] with "
                        "anchor floored -> amplitude %.1f -> %.1f"
                        % (m["elev_mean"], lo, hi, olda,
                           placement["amplitude_m"]), True)
            if m["elev_mean"] < lo and old >= hi:
                # A MIN carve can only LOWER terrain. If the site reads
                # BELOW the band while the anchor already sits at or above
                # the band top, no anchor value can raise it — something
                # else carved this ground away (2026-09-01 canyon: the
                # corridor cut the ledge to 111 m and the old rule chased
                # the anchor to 1598 m, mutating nothing observable).
                return (False, "elev mean %.1f BELOW [%.0f, %.0f] with "
                        "anchor %.1f already at band top — a MIN carve "
                        "cannot raise terrain; the deficit is another "
                        "placement's carve (geometry, not knobs)"
                        % (m["elev_mean"], lo, hi, old), False)
            tgt = (lo + hi) / 2.0
            # never raise the anchor past the band top: beyond it the
            # anchor cannot be the binding constraint
            new = max(0.0, min(hi, round(old + tgt - m["elev_mean"], 1)))
            placement["anchor_m"] = new
            return (False, "elev mean %.1f outside [%.0f, %.0f] -> anchor "
                    "%.1f -> %.1f" % (m["elev_mean"], lo, hi, old, new),
                    True)
        return (True, "flat: slope %.1f deg, elev %.1f m"
                % (m["slope_mean"], m["elev_mean"]), False)

    lo, hi = check["max_elev_m"]
    if m["elev_max"] < lo or m["elev_max"] > hi:
        tgt = lo * 1.05 if m["elev_max"] < lo else hi * 0.95
        f = max(0.5, min(2.0, tgt / max(m["elev_max"], 1.0)))
        old = placement["amplitude_m"]
        placement["amplitude_m"] = min(1500.0, max(20.0, round(old * f, 1)))
        return (False, "peak %.1f outside [%.0f, %.0f] -> amplitude %.1f -> "
                "%.1f" % (m["elev_max"], lo, hi, old,
                          placement["amplitude_m"]), True)
    return (True, "peak: max %.1f m" % m["elev_max"], False)


# ---------------------------------------------------------------------- loop

def _inside_repo(path):
    p = os.path.abspath(path)
    return os.path.commonprefix([p, REPO + os.sep]) == REPO + os.sep


def run_compositor(recipe_path):
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "composite_stamps.py"),
         "--recipe", recipe_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise Refuse("compositor exit %d:\n%s\nstderr tail:\n%s"
                     % (r.returncode, (r.stdout or "")[-1200:],
                        (r.stderr or "")[-600:]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe")
    ap.add_argument("--brief")
    ap.add_argument("--max-iters", type=int, default=MAX_ITERS_DEFAULT)
    ap.add_argument("--reorder", action="store_true",
                    help="move MIN carves after ADDs when the lint fires, "
                         "instead of refusing")
    ap.add_argument("--no-scout", action="store_true",
                    help="disable the site scout: refuse MAX geometry "
                         "instead of relocating to a nearby viable site")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.recipe or not a.brief:
        ap.error("--recipe and --brief are required (unless --selftest)")

    recipe_path = os.path.abspath(a.recipe)
    try:
        if not _inside_repo(recipe_path):
            raise Refuse("recipe %s escapes REPO_ROOT; this tool WRITES the "
                         "recipe and must not write outside the repo"
                         % recipe_path)
        brief_path = os.path.abspath(a.brief)
        if not _inside_repo(brief_path):
            raise Refuse("brief %s escapes REPO_ROOT; the scout WRITES the "
                         "brief and must not write outside the repo"
                         % brief_path)
        with open(recipe_path, encoding="utf-8") as fh:
            recipe = json.load(fh)
        with open(brief_path, encoding="utf-8") as fh:
            brief = json.load(fh)
        placements = recipe["stamps"]["placements"]
        by_id = {p["id"]: p for p in placements}
        checks = brief.get("acceptance")
        validate_acceptance(checks, by_id)

        bad = lint_ordering(placements, checks)
        if bad:
            if not a.reorder:
                raise Refuse(
                    "ordering lint: %s — an ADD after a flat_site's carve "
                    "covers its probe; the carve cannot rule the surface. "
                    "Re-run with --reorder to move carves last." % bad)
            adds = [p for p in placements if p["blend"] != "MIN"]
            mins = [p for p in placements if p["blend"] == "MIN"]
            recipe["stamps"]["placements"] = placements = adds + mins
            print("REORDERED carves-last: %s" % [p["id"] for p in placements])

        ls = recipe["landscape"]
        spacing_m = float(ls["scale_xy_cm"]) / 100.0
        z_scale_m = float(ls["z_scale_cm"]) / 100.0
        origin_m = (float(ls["location_cm"][0]) / 100.0,
                    float(ls["location_cm"][1]) / 100.0)
        out_png = os.path.join(REPO, recipe["stamps"]["output"])
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    except (KeyError, ValueError, OSError) as e:
        print("REFUSE: unreadable inputs: %r" % e)
        return 2

    scouted = set()  # at most one relocation per check id per run
    for it in range(1, a.max_iters + 1):
        with open(recipe_path, "w", encoding="utf-8") as fh:
            json.dump(recipe, fh, indent=2)
        try:
            run_compositor(recipe_path)
            h = load_height_m(out_png, z_scale_m)
        except Refuse as e:
            print("REFUSE (iter %d): %s" % (it, e))
            return 2

        print("--- iteration %d ---" % it)
        all_pass = True
        for c in checks:
            try:
                m = probe(h, spacing_m, origin_m, c["at_m"][0], c["at_m"][1],
                          c["box_m"])
            except Refuse as e:
                print("REFUSE (iter %d): %s" % (it, e))
                return 2
            pl = by_id[c["placement"]]
            ok, msg, mutated = judge_and_adjust(c, m, pl)
            # SITE SCOUT (2026-09-03): the MAX flank-above-band refusal
            # means no plateau at THIS site can work — but a nearby site
            # may. Relocate at most once per check, announce loudly, and
            # only when scouting is on and the refusal is that exact
            # class (a MAX flat_site, judge left every knob alone).
            if (not ok and not mutated and not a.no_scout
                    and c["kind"] == "flat_site"
                    and pl.get("blend") == "MAX"
                    # ONLY the flank-above-band class (audit F2): the
                    # at-target-still-failing refusal has an unknown
                    # cause a local move may not escape — scouting it
                    # would burn the one relocation on a guess
                    and m["elev_max"] + CLEARANCE_M > c["elev_m"][1]
                    and c["id"] not in scouted):
                found = scout_site(h, spacing_m, origin_m, c["at_m"],
                                   c["box_m"], c["elev_m"][1])
                scouted.add(c["id"])
                if found is not None:
                    nx, ny, m2 = found
                    dx, dy = nx - c["at_m"][0], ny - c["at_m"][1]
                    pl["centre_m"] = [round(pl["centre_m"][0] + dx, 1),
                                      round(pl["centre_m"][1] + dy, 1)]
                    c["at_m"] = [nx, ny]
                    msg += (" | SCOUTED: relocated %.0f m to (%.0f, %.0f)"
                            " where box max is %.1f m — placement and "
                            "probe moved together"
                            % (math.hypot(dx, dy), nx, ny, m2["elev_max"]))
                    mutated = True
                    # a relocated probe can land under a later ADD —
                    # the exact defect the ordering lint exists for
                    # (audit F5): refuse rather than iterate against a
                    # probe another stamp rules
                    relint = lint_ordering(placements, checks)
                    if relint:
                        print("  %-18s ADJ   %s" % (c["id"], msg))
                        print("REFUSE (iter %d): scout relocation "
                              "created an ordering violation %s — the "
                              "move is not viable" % (it, relint))
                        return 2
                    # the check lives in the BRIEF; downstream gates
                    # (sightline) target its box, so persist the move —
                    # and the recipe's matching centre shift in the
                    # SAME block, or any early exit leaves the two
                    # disagreeing on disk (audit F3)
                    with open(brief_path, "w", encoding="utf-8") as fh:
                        json.dump(brief, fh, indent=2)
                    with open(recipe_path, "w", encoding="utf-8") as fh:
                        json.dump(recipe, fh, indent=2)
                else:
                    msg += (" | scout found no band-satisfying site "
                            "within 3 box-widths — the refusal stands")
            print("  %-18s %s  %s" % (c["id"], "PASS" if ok else "ADJ ", msg))
            all_pass = all_pass and ok
        if all_pass:
            with open(recipe_path, "w", encoding="utf-8") as fh:
                json.dump(recipe, fh, indent=2)
            print("ALL CHECKS PASS after %d iteration(s). stamps.output is "
                  "current; ADOPTION IS NOT DONE (hash-proven manual step)."
                  % it)
            return 0

    print("REFUSE (exit 3): iteration cap %d hit with checks still failing "
          "— the measurements above are the result; do not widen the "
          "tolerances to make this pass." % a.max_iters)
    return 3


# ------------------------------------------------------------------ selftest

def selftest():
    """Three directions on the pure logic: block the violation, pass the
    legitimate case, block when broken."""
    fails = []

    def expect(cond, name):
        print("  %-52s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # BLOCK WHEN BROKEN: malformed acceptance shapes refuse
    for label, acc in [
            ("missing field refuses", [{"kind": "flat_site", "id": "x"}]),
            ("unknown kind refuses", [{"kind": "volcano", "id": "x"}]),
            ("empty list refuses", []),
            ("unknown placement refuses",
             [{"kind": "peak", "id": "x", "placement": "ghost",
               "at_m": [0, 0], "box_m": 100, "max_elev_m": [1, 2]}]),
            ("inverted band refuses",
             [{"kind": "peak", "id": "x", "placement": "p",
               "at_m": [0, 0], "box_m": 100, "max_elev_m": [2, 1]}])]:
        try:
            validate_acceptance(acc, {"p": {}})
            expect(False, label)
        except Refuse:
            expect(True, label)

    # PASS the legitimate case
    try:
        validate_acceptance(
            [{"kind": "flat_site", "id": "s", "placement": "p",
              "at_m": [0, 0], "box_m": 100, "elev_m": [10, 30],
              "slope_mean_deg_max": 5.0}], {"p": {}})
        expect(True, "well-formed acceptance passes")
    except Refuse:
        expect(False, "well-formed acceptance passes")

    # measurement agrees with an analytic specimen: a plane of known slope,
    # probed at its centre with an explicit (0, 0) origin
    spacing = 4.0
    n = 100
    rise_per_cell = spacing * np.tan(np.radians(10.0))
    plane = np.arange(n)[:, None] * rise_per_cell * np.ones((n, n))
    centre = n * spacing / 2.0
    m = probe(plane, spacing, (0.0, 0.0), centre, centre, 200.0)
    expect(abs(m["slope_mean"] - 10.0) < 0.15,
           "10-deg plane measures 10 deg (got %.2f)" % m["slope_mean"])

    # probe leaving the map refuses instead of clipping silently
    try:
        probe(plane, spacing, (0.0, 0.0), 1e6, centre, 200.0)
        expect(False, "off-map probe refuses")
    except Refuse:
        expect(True, "off-map probe refuses")

    # sub-cell box refuses instead of crashing on an empty window
    try:
        probe(plane, spacing, (0.0, 0.0), centre, centre, 1.0)
        expect(False, "sub-cell box refuses")
    except Refuse:
        expect(True, "sub-cell box refuses")

    # 8-bit input refuses instead of measuring garbage. Audit B1: the
    # specimen lives INSIDE the repo and is removed as a single file —
    # no system temp dir, no recursive-delete cleanup.
    scratch = os.path.join(REPO, "_verify", "20260831_brief_loop",
                           "selftest_scratch_8bit.png")
    os.makedirs(os.path.dirname(scratch), exist_ok=True)
    Image.fromarray(np.zeros((8, 8), np.uint8)).save(scratch)
    try:
        load_height_m(scratch, 2000.0)
        expect(False, "8-bit heightmap refuses")
    except Refuse:
        expect(True, "8-bit heightmap refuses")
    finally:
        os.remove(scratch)

    # adjustment moves the knob the right DIRECTION, bounded
    pl = {"amplitude_m": 100.0, "anchor_m": 20.0}
    c = {"kind": "flat_site", "slope_mean_deg_max": 5.0, "elev_m": [20, 60]}
    ok, _, _ = judge_and_adjust(
        c, {"slope_mean": 20.0, "elev_mean": 40.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl)
    expect(not ok and pl["amplitude_m"] == 30.0,
           "slope 4x too high -> amplitude x0.3 (floor of the step clamp)")
    # Audit B2: the old expectation here asserted 10.0 where the documented
    # rule (anchor += target_mid - measured_mean, floored at 0) yields 0.0.
    # The SELFTEST was the broken instrument. Both branches now covered:
    ok, _, _ = judge_and_adjust(
        c, {"slope_mean": 3.0, "elev_mean": 90.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl)
    expect(not ok and pl["anchor_m"] == 0.0,
           "elev 50 high -> anchor 20-50 pins at the 0.0 floor")
    pl2 = {"amplitude_m": 100.0, "anchor_m": 20.0}
    ok, _, _ = judge_and_adjust(
        c, {"slope_mean": 3.0, "elev_mean": 10.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl2)
    expect(not ok and pl2["anchor_m"] == 50.0,
           "elev 30 low -> anchor 20+30=50 (unfloored branch)")
    pl3 = {"amplitude_m": 5.0, "anchor_m": 200.0}
    ok, _, _ = judge_and_adjust(
        c, {"slope_mean": 23.0, "elev_mean": 40.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl3)
    expect(not ok and pl3["anchor_m"] == 170.0,
           "slope fails at amp floor -> anchor planes deeper x0.85")
    pl4 = {"amplitude_m": 5.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        c, {"slope_mean": 23.0, "elev_mean": 40.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl4)
    expect(not ok and not mut and pl4["anchor_m"] == 0.0,
           "no knob left at anchor 0 -> reported, nothing mutated")
    pl5 = {"amplitude_m": 12.0, "anchor_m": 45.0}
    ok, _, mut = judge_and_adjust(
        c, {"slope_mean": 3.0, "elev_mean": 10.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl5)
    expect(not ok and mut and pl5["anchor_m"] == 60.0,
           "anchor raise CLAMPED at band top (45+30=75 -> 60)")
    pl6 = {"amplitude_m": 12.0, "anchor_m": 60.0}
    ok, _, mut = judge_and_adjust(
        c, {"slope_mean": 3.0, "elev_mean": 10.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl6)
    expect(not ok and not mut and pl6["anchor_m"] == 60.0,
           "below band with anchor at band top -> no knob, not mutated")
    # derive by hand from the rule: mean 96 over band [20,60] with anchor
    # floored -> tgt 40, f = clamp(40/96) = 0.417, amp 400 -> 166.7
    pl7 = {"amplitude_m": 400.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        c, {"slope_mean": 3.0, "elev_mean": 96.0, "elev_max": 0,
            "elev_min": 0, "slope_p90": 0}, pl7)
    expect(not ok and mut and pl7["amplitude_m"] == 166.7,
           "above band at anchor floor -> amplitude x(tgt/mean) = 166.7")

    # MAX plateau rule, derived by hand from the rule text. Band
    # [200, 300], want 6 deg. Box terrain tops at 236 -> need 239,
    # tgt = max(239, 250) = 250, amplitude = 250 - anchor 0 = 250.
    cmax = {"kind": "flat_site", "slope_mean_deg_max": 6.0,
            "elev_m": [200, 300]}
    plm = {"blend": "MAX", "amplitude_m": 130.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        cmax, {"slope_mean": 15.8, "elev_mean": 206.7, "elev_max": 236.0,
               "elev_min": 165.0, "slope_p90": 0}, plm)
    expect(not ok and mut and plm["amplitude_m"] == 250.0,
           "MAX too low -> plateau raised above box max (250.0)")
    plm2 = {"blend": "MAX", "amplitude_m": 250.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        cmax, {"slope_mean": 0.6, "elev_mean": 249.9, "elev_max": 250.0,
               "elev_min": 249.5, "slope_p90": 0}, plm2)
    expect(ok and not mut, "MAX plateau in band and flat -> passes")
    plm3 = {"blend": "MAX", "amplitude_m": 100.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        cmax, {"slope_mean": 20.0, "elev_mean": 350.0, "elev_max": 420.0,
               "elev_min": 250.0, "slope_p90": 0}, plm3)
    expect(not ok and not mut and plm3["amplitude_m"] == 100.0,
           "MAX with flank above band -> geometry refusal, no mutation")
    plm4 = {"blend": "MAX", "amplitude_m": 250.0, "anchor_m": 0.0}
    ok, _, mut = judge_and_adjust(
        cmax, {"slope_mean": 9.0, "elev_mean": 240.0, "elev_max": 247.0,
               "elev_min": 200.0, "slope_p90": 0}, plm4)
    expect(not ok and not mut,
           "MAX at target height still failing -> reported, not mutated")

    # site scout, three directions on a synthetic field: a 300 m ridge
    # through the origin, flat 100 m ground elsewhere (spacing 4 m,
    # origin (0,0), map 400x400 cells = 1600 m square)
    field = np.full((400, 400), 100.0)
    field[:, 190:210] = 300.0  # north-south ridge at x = 760..840 m
    # 1: refused site ON the ridge -> scout finds flat ground nearby;
    #    band_hi 160 needs elev_max <= 157
    got = scout_site(field, 4.0, (0.0, 0.0), [800.0, 800.0], 100.0, 160.0)
    expect(got is not None and got[2]["elev_max"] == 100.0,
           "scout relocates off the ridge to 100 m ground")
    if got is not None:
        d = math.hypot(got[0] - 800.0, got[1] - 800.0)
        expect(d <= 3.0 * 100.0 + 1.0,
               "scout stays within 3 box-widths (%.0f m)" % d)
    # 2: BLOCK WHEN BROKEN — a field that is high everywhere yields None
    got2 = scout_site(np.full((400, 400), 300.0), 4.0, (0.0, 0.0),
                      [800.0, 800.0], 100.0, 160.0)
    expect(got2 is None, "scout on all-high terrain returns None")
    # 3: nearest ring wins — site at the ridge's east edge: every
    #    0.5-box (50 m) candidate's window still overlaps the ridge,
    #    the 1.0-box ring (100 m) clears it, so distance is ~100 m
    got3 = scout_site(field, 4.0, (0.0, 0.0), [820.0, 800.0], 100.0, 160.0)
    expect(got3 is not None
           and 99.0 <= math.hypot(got3[0] - 820.0,
                                  got3[1] - 800.0) <= 101.0,
           "scout takes the nearest satisfying ring (~100 m)")

    # ordering lint: sees the coast defect, ignores the fixed order
    plc = [{"id": "carve", "blend": "MIN", "centre_m": [0, 0], "size_m": 400},
           {"id": "cliff", "blend": "ADD", "centre_m": [0, 0], "size_m": 800}]
    chk = [{"kind": "flat_site", "placement": "carve", "at_m": [0, 0],
            "box_m": 100, "elev_m": [0, 1], "slope_mean_deg_max": 1}]
    expect(lint_ordering(plc, chk) == [("carve", "cliff")],
           "lint catches ADD-after-carve over the probe")
    expect(lint_ordering(list(reversed(plc)), chk) == [],
           "lint passes carves-last")

    print("%d failure(s)" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
