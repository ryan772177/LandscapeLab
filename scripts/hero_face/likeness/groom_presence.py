"""groom_presence.py — the presence gate, measured in PIXELS, and it must
REPRODUCE before it is allowed a verdict.

WHY THE OLD GATE FAILED
-----------------------
The presence gate used to assert COMPONENT STATE: groom asset set, binding
set, `visible` true. On 2026-08-19 it returned `ships_as DELIVERABLE` on a
portrait with no beard, no moustache and no brows in it. A component can be
present, bound, visible and drawing nothing.

    settling cannot see absence   ->   a checklist cannot see absence either

That is the same defect twice. A statistical settle-gate proves a frame is
STABLE, not COMPLETE; a property checklist proves the SETUP is complete, not
the FRAME. Neither of them ever looks at the thing being claimed.

WHAT THIS DOES INSTEAD
----------------------
Photographs the subject with every groom shown, then once per groom with that
ONE groom hidden, and requires a non-empty difference where the groom sits. A
groom that draws nothing produces an identical frame, and identical frames are
the one thing a difference mask cannot miss.

THE THREE THINGS THAT MAKE IT EVIDENCE RATHER THAN A NUMBER
------------------------------------------------------------
1. THE REPEAT FLOOR. The same state is photographed four times; the floor is
   the residual disagreement of the all_a-vs-all_b reference pair, measured
   only over pixels the other frames (b,c,d) agree are stable. This scene does
   not re-render itself identically, so a difference that does not beat the
   floor is not evidence of a groom. The floor is measured in the same session
   every run: a floor belongs to its editor session and cannot be inherited.

2. THE POSITIVE CONTROL. A groom whose hide produces an identical frame is
   INDISTINGUISHABLE from a hide that never took effect, and those two
   readings mean opposite things -- "the groom draws nothing" versus "I could
   not look". So the payload also hides something that certainly draws (the
   face mesh) through the same call in the same payload. If that does not move
   the frame, this tool REFUSES rather than reporting zeros.

3. THE REPRODUCE GATE, AND IT IS THE ONE THAT SOLVED THE CASE.
   GROOMS CONVERGE OVER FRAMES AFTER THEY ARE SPAWNED. Measured 2026-08-19 in
   a cold editor, first spawn, nothing changed between the two runs:

       groom       first run      second run     converged value
       Hair          33,743          96,246        96,147 - 97,338
       Eyebrows       3,564          19,205        18,904 - 18,911
       Beard          9,153          13,149        12,555 - 12,809

   The first run called Eyebrows and Mustache ABSENT. They were not absent;
   they were not finished. A single-shot verdict on a freshly placed character
   is therefore worthless in the direction that matters -- it manufactures
   false ABSENCES -- and that is exactly how a hair groom spent two days
   recorded as broken. So the measurement is taken TWICE and the two must
   agree within `--tolerance` before any verdict is issued. A still-converging
   subject produces a REFUSAL, not a reading.

All three fail closed: an unreadable control, a floor that swamps the signal,
or a measurement that will not reproduce produces a REFUSAL, never a pass.

EXIT CODES
    0  every required groom is PRESENT in pixels, and it reproduced
    2  bad arguments / manifest missing
    3  no editor matched UE_PROJECT_ROOT (standing rule 7)
    5  payload error
    6  a required groom is ABSENT -- the gate did its job
    7  the instrument could not discriminate: control failed, floor too high,
       the reproduce gate compared zero grooms, or the two passes disagree
       because the grooms are still converging. NO VERDICT.
    8  --no-reproduce single pass: looked, every required groom present ONCE,
       but a single pass is NOT a reproduced verdict (it manufactures false
       absences on a freshly placed subject). NO VERDICT.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

import numpy as np
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts import ue_exec                      # noqa: E402

DEFAULT_MANIFEST = os.path.join(_HERE, "manifest.json")
PAYLOAD = os.path.join(_HERE, "groom_presence_payload.txt")

# A per-channel delta below this is not a pixel that changed; it is encoder
# and temporal-accumulation dither. Kept explicit so a later reader can see
# the number rather than infer it from behaviour.
DELTA_THRESHOLD = 8.0

# How far above the repeat floor a groom's difference must sit to count. Not
# tuned to make anything pass: the control shows what a REAL hide looks like
# and runs 800-1300x the floor, so this bar is nowhere near the interesting
# region.
FLOOR_FACTOR = 3.0

# A scalp hair whose binding never finished building draws only its
# free-hanging ends: big pixel count, bald crown. Below this share of its own
# pixels in the head's top third, "present" is reported as SCALP-BALD instead.
# Legitimately receding styles will trip it too -- that is a handful of frames
# to eyeball, against 38 silent wrong ones.
CROWN_MIN_FRAC = 0.10


def _load(p: str) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def _delta(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.shape != b.shape:
        raise ValueError("frame sizes differ: %s vs %s" % (a.shape, b.shape))
    return np.abs(a - b).max(axis=2)


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    """Grow a boolean mask by r pixels, without a scipy dependency.

    Foliage does not merely flicker in place: a needle edge moves, so the
    pixel BESIDE an unstable one is unstable on the next frame. An undilated
    mask leaves a fringe of those behind and they read as signal.
    """
    if r <= 0:
        return mask
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def _changed(a: np.ndarray, b: np.ndarray, stable: np.ndarray,
             thr: float = DELTA_THRESHOLD) -> dict:
    d = _delta(a, b)
    mask = (d > thr) & stable
    n = int(mask.sum())
    out = {"changed_px": n,
           "frac_of_stable": float(n) / max(int(stable.sum()), 1),
           "changed_px_whole_frame": int((d > thr).sum())}
    if n:
        ys, xs = np.nonzero(mask)
        out["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        out["centroid"] = [float(xs.mean()), float(ys.mean())]
    return out


def _one_pass(args, out_dir: str, stamp: str) -> tuple:
    """Run the payload once and reduce it. Returns (code, dict).

    code 0 = a reading was produced; anything else is a refusal to read.
    """
    with open(PAYLOAD, "r", encoding="utf-8") as fh:
        text = fh.read()
    for k, v in (("LABEL", args.label), ("CAPL", args.capture_label),
                 ("OUT_DIR", out_dir.replace("\\", "/")), ("STAMP", stamp),
                 ("WARM", str(args.warm)), ("REWARM", str(args.rewarm)),
                 ("AA_METHOD", str(args.aa))):
        text = text.replace("__" + k + "__", v)

    rc, d, _raw = ue_exec.run(text, timeout=args.timeout,
                              stage_name="groom_presence", quiet=True)
    if rc == 3:
        return 3, {}
    if d is None:
        print("COULD NOT LOOK: the payload produced no marker.")
        return 5, {}
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 5, {}
    for r in d.get("refusals", []):
        print("REFUSAL FROM THE PAYLOAD:", r)

    shots_list = d.get("shots")
    if not shots_list:
        print("COULD NOT LOOK: the payload returned no shots.")
        return 5, {}
    try:
        shots = {s["tag"]: os.path.join(out_dir, s["png"]) for s in shots_list}
    except (KeyError, TypeError) as e:
        print("COULD NOT LOOK: a shot entry is malformed (%s)." % e)
        return 5, {}
    absent = [t for t, p in shots.items() if not os.path.isfile(p)]
    if absent:
        print("COULD NOT LOOK: frames never landed on disk:", absent)
        return 5, {}

    need = ["all_a", "all_b", "all_c", "all_d"]
    for t in need:
        if t not in shots:
            print("REFUSE: missing the %s frame; the stability map and the "
                  "floor cannot both be measured. NO VERDICT." % t)
            return 7, {}
    img = {t: _load(shots[t]) for t in need}

    # WHICH PIXELS CAN BE TRUSTED AT ALL. Built from b, c and d -- the three
    # unchanged-state frames that are NOT the reference the signal is measured
    # against. A mask fitted to `a` would be fitted to the very noise it is
    # meant to be independent of.
    unstable = ((_delta(img["all_b"], img["all_c"]) > DELTA_THRESHOLD)
                | (_delta(img["all_b"], img["all_d"]) > DELTA_THRESHOLD)
                | (_delta(img["all_c"], img["all_d"]) > DELTA_THRESHOLD))
    unstable = _dilate(unstable, 2)
    stable = ~unstable
    n_stable = int(stable.sum())
    total = int(stable.size)
    if n_stable < total * 0.05:
        print("REFUSE: almost nothing in this frame reproduces. NO VERDICT.")
        return 7, {}

    floor = _changed(img["all_a"], img["all_b"], stable)["changed_px"]
    bar = max(floor * FLOOR_FACTOR, 200)

    ctl_tag = "control_minus_face"
    if ctl_tag not in shots:
        print("REFUSE: no positive control frame. NO VERDICT.")
        return 7, {}
    ctl = _changed(img["all_a"], _load(shots[ctl_tag]), stable)
    if ctl["changed_px"] <= bar:
        print("REFUSE: hiding something that certainly draws did not move the "
              "frame beyond the floor (%d vs bar %d). The hide is not reaching "
              "the renderer, so a groom reading zero would mean I COULD NOT "
              "LOOK. NO VERDICT." % (ctl["changed_px"], bar))
        return 7, {}

    # THE CROWN BAND. A presence gate certifies PRESENCE and nothing adjacent:
    # measured 2026-08-19, a hair whose binding never finished building draws
    # only its free-hanging ends and reads 155,153 px / 87x floor while the
    # scalp is BALD. That passed every check and was committed as a working
    # route. So the head's own top third is measured separately, and a hair
    # that is "present" entirely below it is reported as SCALP-BALD.
    face_mask = (_delta(img["all_a"], _load(shots[ctl_tag])) > DELTA_THRESHOLD) \
        & stable
    crown = np.zeros_like(stable)
    if face_mask.any():
        fys, fxs = np.nonzero(face_mask)
        y0, y1 = int(fys.min()), int(fys.max())
        x0, x1 = int(fxs.min()), int(fxs.max())
        # Top third of the head silhouette, widened sideways so a fringe or a
        # side fall still counts as scalp coverage.
        cy1 = y0 + int((y1 - y0) * 0.33)
        pad = int((x1 - x0) * 0.15)
        crown[max(y0 - pad, 0):cy1,
              max(x0 - pad, 0):min(x1 + pad, crown.shape[1])] = True
        crown &= stable

    results = {}
    for name in sorted(d.get("grooms", {})):
        tag = "minus_" + name
        if tag not in shots:
            results[name] = {"verdict": "NO FRAME", "changed_px": 0}
            continue
        c = _changed(img["all_a"], _load(shots[tag]), stable)
        dd = _delta(img["all_a"], _load(shots[tag]))
        c["crown_px"] = int(((dd > DELTA_THRESHOLD) & crown).sum())
        c["crown_frac"] = (c["crown_px"] / c["changed_px"]) if c["changed_px"] else 0.0
        c["verdict"] = "PRESENT" if c["changed_px"] > bar else "ABSENT"
        # Only meaningful for scalp hair. A beard below the jaw is SUPPOSED to
        # have no crown coverage, and flagging it would be noise.
        if name == "Hair" and c["verdict"] == "PRESENT" and \
                c["crown_frac"] < CROWN_MIN_FRAC:
            c["verdict"] = "SCALP-BALD"
        results[name] = c

    return 0, {"stable_px": n_stable, "total_px": total, "floor_px": floor,
               "bar_px": bar, "control_px": ctl["changed_px"],
               "control_component": d.get("control"), "aa": d.get("aa"),
               "viewport": d.get("viewport"), "frame_count": d.get("frame_count"),
               "grooms": d.get("grooms"), "results": results, "out_dir": out_dir}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--label", default="HeroInWorld")
    ap.add_argument("--capture-label", default="HeroShot_Capture")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--warm", type=int, default=30)
    ap.add_argument("--rewarm", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--stamp", default=None)
    ap.add_argument("--aa", type=int, default=0,
                    help="r.AntiAliasingMethod for the run (0 = none, the "
                         "default). -1 leaves the renderer alone.")
    ap.add_argument("--tolerance", type=float, default=0.30,
                    help="how far the two passes may disagree per groom "
                         "before this refuses to issue a verdict. Drift is "
                         "(hi-lo)/hi, so 0-100%%. Converged passes agree "
                         "within ~1.3%%; a converging one moved ~65%% (the "
                         "Hair 33,743->96,246 first-vs-second jump), so 30%% "
                         "separates them with room to spare.")
    ap.add_argument("--no-reproduce", action="store_true",
                    help="single pass. FOR LOOKING, NOT FOR A VERDICT: a "
                         "single pass on a freshly placed character "
                         "manufactures false ABSENCES.")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.manifest):
        print("REFUSE: no manifest at", args.manifest)
        return 2
    with open(args.manifest, "r", encoding="utf-8") as fh:
        man = json.load(fh)
    presence = man.get("capture", {}).get("presence", {})
    required = list(presence.get("required_components", []))
    if not required:
        print("REFUSE: manifest declares no required components. A gate with "
              "nothing to require cannot fail, and a gate that cannot fail is "
              "not a gate.")
        return 2

    stamp = args.stamp or datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or os.path.join(
        REPO_ROOT, "_verify", "groom_presence", stamp)
    os.makedirs(out_dir, exist_ok=True)

    print("subject          :", args.label)
    print("required         :", ", ".join(required))
    print()

    code, p1 = _one_pass(args, out_dir, stamp + "_p1")
    if code:
        return code
    print("PASS 1  floor %d px | control %s hidden %d px (%.0fx floor)"
          % (p1["floor_px"], p1["control_component"], p1["control_px"],
             p1["control_px"] / max(p1["floor_px"], 1)))
    for n in sorted(p1["results"]):
        r = p1["results"][n]
        print("        %-10s %-10s %8d px (%.1fx floor)  crown %.0f%%"
              % (n, r["verdict"], r["changed_px"],
                 r["changed_px"] / max(p1["floor_px"], 1),
                 100.0 * r.get("crown_frac", 0.0)))

    final = p1
    if not args.no_reproduce:
        print()
        code, p2 = _one_pass(args, out_dir, stamp + "_p2")
        if code:
            return code
        print("PASS 2  floor %d px | control %s hidden %d px (%.0fx floor)"
              % (p2["floor_px"], p2["control_component"], p2["control_px"],
                 p2["control_px"] / max(p2["floor_px"], 1)))
        drift = {}
        for n in sorted(p2["results"]):
            r2 = p2["results"][n]
            r1 = p1["results"].get(n, {"changed_px": 0})
            lo = max(min(r1["changed_px"], r2["changed_px"]), 1)
            hi = max(r1["changed_px"], r2["changed_px"], 1)
            rel = (hi - lo) / float(hi)
            drift[n] = rel
            print("        %-10s %-10s %8d px (%.1fx floor)  crown %.0f%%"
                  "  drift %.1f%%"
                  % (n, r2["verdict"], r2["changed_px"],
                     r2["changed_px"] / max(p2["floor_px"], 1),
                     100.0 * r2.get("crown_frac", 0.0), 100.0 * rel))
        final = p2
        final["drift"] = drift

        # NN13/rule 13: a reproduce gate that compared ZERO grooms is not
        # agreement, it is silence. Refuse, and report the count beside the
        # verdict either way.
        if not drift:
            print()
            print("REFUSE: the reproduce gate compared 0 grooms (the payload "
                  "returned no grooms to hide). A gate over zero samples is "
                  "not agreement. NO VERDICT.")
            return 7
        print("        reproduce: compared %d groom(s) across two passes"
              % len(drift))

        moving = [n for n, v in drift.items() if v > args.tolerance]
        if moving:
            print()
            print("REFUSE: %s changed by more than %.0f%% between two "
                  "identical passes, so this subject is STILL CONVERGING and "
                  "any verdict now is a guess. Grooms finish over frames after "
                  "they are spawned -- measured 2026-08-19, a first pass "
                  "called Eyebrows ABSENT at 3,564 px and the next pass read "
                  "19,205 px with nothing changed. Spend more frames (re-run "
                  "this tool) and gate on the run that reproduces. NO VERDICT."
                  % (", ".join(sorted(moving)), 100.0 * args.tolerance))
            return 7

    report = {
        "stamp": stamp, "subject": args.label, "out_dir": out_dir,
        "delta_threshold": DELTA_THRESHOLD, "floor_factor": FLOOR_FACTOR,
        "tolerance": args.tolerance, "reproduced": not args.no_reproduce,
        "crown_min_frac": CROWN_MIN_FRAC,
        "required": required,
        "pass1": {k: p1[k] for k in ("floor_px", "control_px", "results")},
        "final": {k: final[k] for k in
                  ("floor_px", "bar_px", "control_px", "control_component",
                   "stable_px", "total_px", "aa", "viewport", "frame_count",
                   "grooms", "results")},
        "drift": final.get("drift"),
    }
    rp = os.path.join(out_dir, "groom_presence.json")
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print()
    print("report:", rp)

    absent_required = [n for n in required
                       if final["results"].get(n, {}).get("verdict") != "PRESENT"]
    if absent_required:
        print()
        print("ABSENT, REQUIRED: %s" % ", ".join(absent_required))
        print("VERDICT: this render is a DIAGNOSTIC, not a deliverable.")
        return 6
    print()
    if args.no_reproduce:
        print("LOOKED (--no-reproduce, single pass): every required groom "
              "puts pixels on the screen ONCE. A single pass manufactures "
              "false absences on a freshly placed subject, so this is NOT a "
              "reproduced verdict and NOT a deliverable. NO VERDICT.")
        return 8
    print("VERDICT: every required groom puts pixels on the screen, twice. "
          "DELIVERABLE with respect to grooms at THIS framing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
