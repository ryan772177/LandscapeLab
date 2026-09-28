"""Is this image big enough, and framed well enough, to reconstruct from?

WHY, IN ONE MEASUREMENT
-----------------------
    castle (TRELLIS's own example)   183,353 subject px   -> thin/long 0.849
    church crop from the concept       ~3,700 subject px  -> thin/long 0.0114

A 50x gap in subject pixels, and the difference between a volume and a flat
sheet. The failure was NOT the model -- a positive control through the
identical code path proved that -- it was the input, and an input's adequacy is
measurable BEFORE spending a GPU minute on it.

⛔ WHAT THE SUBJECT COUNT DOES **NOT** DO, stated because the first draft of
this docstring claimed otherwise. It counts pixels in the DELIVERED image, and
it cannot see that they were upscaled: the failed 80x115 crop, blown up to
518x518, measures 139,958 subject pixels here -- not the ~3,700 it actually
carries. Upscaling adds no information but it does add pixels, and a pixel
count cannot tell the two apart.

**The FRAME floor is what catches that**, which is why it exists as a separate
check: a >=1024 delivered frame means nothing upstream had to enlarge. The
failed crop trips it, along with three other checks. Two independent bounds,
because either alone is foolable.

WHAT IT CANNOT JUDGE
--------------------
Angle, lighting flatness and background cleanliness are in the spec
(`_verify/20260830_bakeoff/GENERATION_VIEW_SPEC.md`) and only partly measurable
here. This tool measures SIZE, FRAMING, ASPECT and BACKGROUND UNIFORMITY, and
reports the rest as unjudged rather than implying it checked them.

Usage:
    python scripts/check_generation_input.py <image> [<image> ...]
    python scripts/check_generation_input.py --self-test
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Image.MAX_IMAGE_PIXELS = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MIN_SUBJECT_PX = 150000      # 40x the failed case; castle measured 183,353
MIN_LONGEST = 800            # -> ~405 px after TRELLIS's internal 518 resize
MIN_FRAME = 1024             # so nothing is upscaled anywhere in the chain
FILL_LO, FILL_HI = 0.55, 0.97   # subject vs the frame's SHORTER dimension
ASPECT_MAX = 1.35            # square-ish; 16:9 wastes half the frame on sky

# ⭐ SET MODE. Ruled 2026-08-30: for a CONSTANT-DISTANCE multi-view set, the
# floors apply per SET, not per image.
#
# WHY. The 800 px and fill-low floors were derived to guarantee INFORMATION
# DENSITY against an 80x115 crop that carried ~3,700 subject pixels. Rotating
# a subject at constant distance shrinks its projected extent WITHOUT losing
# density -- and the subject-pixel count proves it directly: the wood stack's
# end-on views measure 328k-358k against a 150k floor. Applying an extent
# floor to a rotation measures the subject's SHAPE, not the input's quality.
#
# Measured case: the wood stack's HEIGHT is 633-693 px in every view (azimuth
# does not change height) while its WIDTH swings 908 -> 733. Two views fell
# under 800 on width alone. The church passed all four only because it is
# TALL -- longest >=872 in every view -- so its clean pass HID the interaction.
#
# The consistency check replaces what the extent floor was doing: azimuth does
# not change height, so a bbox-height jump between views means the generator
# moved the camera or changed scale -- which is the reconstruction hazard the
# spec actually names.
# ⭐ THE CONSISTENCY GATE IS THE GROUND LINE. Ruled 2026-08-30 after the first
# implementation refused an honest set.
#
# bbox HEIGHT was the obvious proxy and it is a NOISY one: it mixes the thing
# being detected (the camera moved) with a thing that is expected (the
# silhouette changes with azimuth). Measured on the wood-stack set:
#
#     ground line (bbox bottom)  889, 890, 880, 889   spread  1.1%
#     top edge                   229, 182, 233, 234   spread 22.5%
#     bbox height                661, 709, 648, 656   spread  9.3%
#
# The camera demonstrably did not move -- the ground line is constant to 1.1%
# -- and the height still varied 9.3%, because the 35 degree silhouette is
# genuinely taller (az035's top at y=182 against 229/233/234, over the same
# ground). At +-8% on height the gate refused az090 at 8.6%: a false positive
# on a set whose camera was fixed.
#
# The GROUND LINE is what actually moves when the camera does: a distance or
# elevation change shifts it and rescales the whole bbox, while azimuth leaves
# the subject standing where it stands.
GROUND_TOL = 0.03            # THE GATE. rotation ground line vs the master's.
HEIGHT_TOL = 0.15            # SECONDARY, reported always; see judge_set.


def subject_mask(im):
    """Opaque pixels if there is alpha; else pixels differing from the border.

    The border estimate is the honest fallback: a flat studio background is
    what the spec asks for, so "unlike the corners" is a fair proxy for
    subject. It is reported as an ESTIMATE so a plain-background photo is not
    confused with a true alpha cut-out.
    """
    a = np.asarray(im)
    if a.ndim == 3 and a.shape[2] == 4 and a[..., 3].min() < 250:
        return a[..., 3] > 16, "alpha"
    rgb = np.asarray(im.convert("RGB")).astype(np.float64)
    h, w = rgb.shape[:2]
    k = max(2, min(h, w) // 64)
    corners = np.concatenate([
        rgb[:k, :k].reshape(-1, 3), rgb[:k, -k:].reshape(-1, 3),
        rgb[-k:, :k].reshape(-1, 3), rgb[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    d = np.abs(rgb - bg).sum(-1)
    return d > 40.0, "background-estimate"


def measure(path):
    """Measurements only. No verdict -- the rules differ per mode."""
    with Image.open(path) as im:
        W, H = im.size
        m, how = subject_mask(im)
    r = {"path": path, "frame": (W, H), "mask": how, "fail": []}
    n = int(m.sum())
    r["subject_px"] = n
    ys, xs = np.nonzero(m)
    if n == 0:
        r["fail"].append("NO SUBJECT FOUND -- could not measure, not a pass")
        return r
    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    r["bbox"] = (bw, bh)
    # The GROUND LINE -- the subject's lowest row. It is the quantity that
    # actually moves when the CAMERA moves: a distance change shifts the
    # ground line and rescales the whole bbox, while a change of azimuth
    # leaves the subject standing in the same place and only alters its
    # silhouette. Measured and reported in set mode so the two can be told
    # apart. See LESSONS 2026-08-30.
    r["ground_y"] = int(ys.max())
    r["top_y"] = int(ys.min())
    r["longest"] = max(bw, bh)
    r["fill"] = max(bw, bh) / float(min(W, H))
    r["aspect"] = max(W, H) / float(min(W, H))

    return r


def _f_subject(r):
    n = r["subject_px"]
    if n < MIN_SUBJECT_PX:
        return ("subject %d px < %d (the 80x115 crop had ~3,700 and "
                "returned a flat sheet)" % (n, MIN_SUBJECT_PX))


def _f_frame(r):
    W, H = r["frame"]
    if min(W, H) < MIN_FRAME:
        return ("frame %dx%d smaller than %d -- something in the chain will "
                "upscale" % (W, H, MIN_FRAME))


def _f_longest(r):
    if r["longest"] < MIN_LONGEST:
        return "subject longest side %d px < %d" % (r["longest"], MIN_LONGEST)


def _f_fill_lo(r):
    if r["fill"] < FILL_LO:
        return ("subject fills %.0f%% of the short side, want >=%.0f%% -- "
                "this is a wide shot, not a portrait of it"
                % (100 * r["fill"], 100 * FILL_LO))


def _f_fill_hi(r):
    if r["fill"] > FILL_HI:
        return ("subject fills %.0f%% -- likely CLIPPED at the frame edge; "
                "leave ~3%% margin (the floor is FILL_HI=0.97)"
                % (100 * r["fill"]))


def _f_aspect(r):
    if r["aspect"] > ASPECT_MAX:
        return ("aspect %.2f:1 -- use a square-ish frame, TRELLIS "
                "preprocesses to 518x518" % r["aspect"])


PER_IMAGE = (_f_subject, _f_frame, _f_longest, _f_fill_lo, _f_fill_hi,
             _f_aspect)
# A rotation is NOT held to longest-side or fill-LOW. It IS held to fill-HIGH,
# because clipping destroys information at any extent.
ROTATION = (_f_subject, _f_frame, _f_fill_hi, _f_aspect)


def judge(path):
    """Full per-image floors. What a SINGLE input is held to."""
    r = measure(path)
    if "bbox" not in r:
        return r
    for fn in PER_IMAGE:
        msg = fn(r)
        if msg:
            r["fail"].append(msg)
    return r


def judge_set(paths):
    """Set mode: one master at full floors, rotations at set floors.

    The MASTER is DERIVED, not declared -- the view with the largest subject
    extent, which is the broadside. Deriving it means a set cannot be made to
    pass by nominating its weakest image as the reference.
    """
    rows = [measure(p) for p in paths]
    usable = [r for r in rows if "bbox" in r]
    if not usable:
        for r in rows:
            r["fail"].append("NO SUBJECT FOUND -- could not measure")
        return rows, None
    master = max(usable, key=lambda r: (r["longest"], r["subject_px"]))
    master["role"] = "MASTER (max extent)"
    for fn in PER_IMAGE:
        msg = fn(master)
        if msg:
            master["fail"].append(msg)

    mh = master["bbox"][1]
    mg = master["ground_y"]
    for r in usable:
        if r is master:
            continue
        r["role"] = "rotation"
        for fn in ROTATION:
            msg = fn(r)
            if msg:
                r["fail"].append(msg)
        dh = abs(r["bbox"][1] - mh) / float(mh)
        dg = abs(r["ground_y"] - mg) / float(mg)
        r["height_delta"] = dh
        r["ground_delta"] = dg

        # THE GATE: the ground line. A distance or elevation change moves it.
        ground_bad = dg > GROUND_TOL
        height_bad = dh > HEIGHT_TOL

        if ground_bad:
            msg = ("GROUND LINE at y=%d is %.1f%% off the master's y=%d (max "
                   "%.0f%%) -- the subject is not standing where it stood, so "
                   "the camera distance or elevation CHANGED between views. "
                   "That is the reconstruction hazard the spec names."
                   % (r["ground_y"], 100 * dg, mg, 100 * GROUND_TOL))
            if height_bad:
                # Both moved: a genuine re-shoot from elsewhere. Cite both, so
                # the reader is not left wondering whether height was checked.
                msg += (" bbox height is ALSO %.1f%% off (max %.0f%%), which "
                        "corroborates it." % (100 * dh, 100 * HEIGHT_TOL))
            r["fail"].append(msg)
        elif height_bad:
            # Height alone does NOT gate. A generator that rescaled the object
            # while holding the ground line would land here, and it is worth
            # SAYING so -- but honest silhouette variation lands here too, and
            # refusing it is what the first implementation got wrong.
            r["note"] = (
                "bbox height %.1f%% off the master (max %.0f%%) while the "
                "GROUND LINE holds at %.1f%% -- silhouette variation, not a "
                "camera move. Reported, not gated. If this is large AND the "
                "subject should be rigid, suspect a rescale."
                % (100 * dh, 100 * HEIGHT_TOL, 100 * dg))
    return rows, master


def report(rows):
    bad = 0
    for r in rows:
        print("  %s" % r["path"])
        if "bbox" in r:
            extra = ""
            if r.get("role"):
                extra = "  [%s]" % r["role"]
            if "ground_delta" in r:
                extra += "  ground %+.1f%% / height %+.1f%% vs master" % (
                    100 * r["ground_delta"], 100 * r["height_delta"])
            print("      frame %dx%d  subject %d px  bbox %dx%d  fill %.0f%%"
                  "  (%s)%s" % (r["frame"][0], r["frame"][1], r["subject_px"],
                                r["bbox"][0], r["bbox"][1], 100 * r["fill"],
                                r["mask"], extra))
        for f in r["fail"]:
            print("      !! %s" % f)
        if r.get("note"):
            print("      .. %s" % r["note"])
        if not r["fail"]:
            print("      ok")
        else:
            bad += 1
    print("")
    print("  NOT JUDGED HERE: angle, lighting flatness, silhouette occlusion.")
    print("  Those are in GENERATION_VIEW_SPEC.md and are not measurable from")
    print("  one image; this tool does not imply it checked them.")
    print("")
    if bad:
        print("REFUSE: %d of %d image(s) fall short." % (bad, len(rows)))
        return 4
    print("all %d image(s) meet the measured floor." % len(rows))
    return 0


def self_test():
    """Inputs whose outcomes are already known must be judged right.

    Per-image floors first, then SET mode against the real wood-stack set --
    the case that produced the 2026-08-30 ruling -- in three directions: the
    master passes in full, the rotations pass under set rules, and a rotation
    shot from further away is REFUSED by the height-consistency check.
    """
    import glob
    import tempfile
    print("SELF-TEST -- against inputs whose RESULTS are already known")
    print("")
    ok = True
    cases = []
    p = os.path.join(REPO, "_verify", "20260830_bakeoff",
                     "church_input_518.png")
    if os.path.isfile(p):
        cases.append((p, True, "the crop that produced a FLAT SHEET"))
    with tempfile.TemporaryDirectory() as td:
        # A synthetic that meets the floor: 1200^2 frame, ~900 px subject.
        a = np.full((1200, 1200, 3), 240, np.uint8)
        a[150:1050, 250:950] = 60
        good = os.path.join(td, "good.png")
        Image.fromarray(a).save(good)
        cases.append((good, False, "a synthetic that MEETS the floor"))
        for path, want_fail, label in cases:
            r = judge(path)
            got_fail = bool(r["fail"])
            good_case = got_fail == want_fail
            ok = ok and good_case
            print("  %-8s %-44s %s"
                  % ("REFUSED" if got_fail else "passed", label,
                     "" if good_case else "*** WRONG ***"))
            if got_fail:
                print("           -> %s" % r["fail"][0][:90])
    # ---- SET MODE, against the REAL wood-stack set ----------------------
    # ⭐ A REAL-WORLD POSITIVE CONTROL, not a synthetic one. This is the exact
    # set that exposed the per-image floor as measuring the wrong thing: two
    # rotations fell under 800 px on WIDTH alone while carrying 328k-358k
    # subject pixels against a 150k floor. If set mode ever stops passing it,
    # the ruling has been undone by an edit.
    print("")
    print("SET MODE -- the wood-stack set, the real case the ruling came from")
    wsd = os.path.join(REPO, "refs", "wood_stack_refs")
    ws = sorted(glob.glob(os.path.join(wsd, "*.png")))
    if len(ws) < 3:
        print("  SKIPPED -- %s holds %d image(s); cannot exercise set mode"
              % (wsd, len(ws)))
        print("  (that is a SKIP, not a pass)")
    else:
        rows, master = judge_set(ws)
        m_ok = master is not None and not master["fail"]
        rots = [r for r in rows if r is not master]
        r_ok = all(not r["fail"] for r in rots)
        print("  %-8s master %s"
              % ("passed" if m_ok else "REFUSED",
                 os.path.basename(master["path"]) if master else "(none)"))
        if master and master["fail"]:
            print("           -> %s" % master["fail"][0][:88])
        print("  %-8s %d rotation(s) under SET rules"
              % ("passed" if r_ok else "REFUSED", len(rots)))
        for r in rots:
            if r["fail"]:
                print("           -> %s: %s"
                      % (os.path.basename(r["path"]), r["fail"][0][:80]))
        ok = ok and m_ok and r_ok

        # ...AND IT MUST STILL REFUSE. A height-mismatched rotation means the
        # camera moved between views. Built by PADDING a real rotation's frame
        # so its subject occupies a smaller share -- i.e. exactly what shooting
        # from further away looks like -- rather than by editing a number.
        with tempfile.TemporaryDirectory() as td2:
            # ⛔ COMPOSITE ONLY THE SUBJECT PIXELS, scaled about the frame
            # centre -- which is what moving the camera further away actually
            # does to a projection.
            #
            # The first version of this fake pasted a 0.75-scaled COPY OF THE
            # WHOLE FRAME onto a background canvas. The paste left a
            # rectangular seam, `subject_mask` locked onto that rectangle
            # instead of the subject, and the fake measured a ground delta of
            # 0.6% -- it was not simulating distance at all, and the test
            # reported a pass over a control that was never being exercised.
            # A fixture that does not construct the condition it names is
            # worse than no fixture.
            victim = rots[0]["path"] if rots else ws[-1]
            with Image.open(victim) as im0:
                im = im0.convert("RGB")
                vm, _ = subject_mask(im0)
            W, H = im.size
            vys, vxs = np.nonzero(vm)
            x0, x1, y0, y1 = (int(vxs.min()), int(vxs.max()),
                              int(vys.min()), int(vys.max()))
            k = 0.75
            cx, cy = W / 2.0, H / 2.0
            subj = im.crop((x0, y0, x1 + 1, y1 + 1))
            msk = Image.fromarray((vm[y0:y1 + 1, x0:x1 + 1] * 255)
                                  .astype(np.uint8), mode="L")
            nw, nh = max(1, int(subj.width * k)), max(1, int(subj.height * k))
            subj = subj.resize((nw, nh), Image.LANCZOS)
            msk = msk.resize((nw, nh), Image.LANCZOS)
            bgcol = tuple(np.median(np.asarray(im)[:8, :8].reshape(-1, 3),
                                    axis=0).astype(int))
            canvas = Image.new("RGB", (W, H), bgcol)
            # scale the bbox corners about the centre, as a projection would
            px = int(round(cx + k * (x0 - cx)))
            py = int(round(cy + k * (y0 - cy)))
            canvas.paste(subj, (px, py), msk)
            bad = os.path.join(td2, "further_away.png")
            canvas.save(bad)
            others = [w for w in ws if w != victim]
            rows2, master2 = judge_set(others + [bad])
            badrow = [r for r in rows2 if r["path"] == bad][0]
            # Look for the GROUND LINE refusal -- the gate as ruled
            # 2026-08-30. This assertion previously matched "bbox HEIGHT",
            # and when the gate moved to the ground line the test went on
            # reporting a pass over a fake that was no longer being caught by
            # the string it was searching for. A test that greps for a message
            # is coupled to the message; it is asserting on prose.
            hits = [f for f in badrow["fail"] if "GROUND LINE" in f]
            refused = bool(hits)
            print("  %-8s a rotation shot from FURTHER AWAY (0.75x)"
                  % ("REFUSED" if refused else "*** PASSED ***"))
            if refused:
                print("           -> %s" % hits[0][:88])
            else:
                print("           -> ground %.1f%% / height %.1f%% vs master"
                      % (100 * badrow.get("ground_delta", 0),
                         100 * badrow.get("height_delta", 0)))
            ok = ok and refused

    print("")
    print("validator %s" % ("DISCRIMINATES" if ok else "!! DOES NOT"))
    return 0 if ok else 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--set", action="store_true", dest="as_set",
                    help="judge these images as ONE constant-distance "
                         "multi-view set: the derived MASTER takes the full "
                         "floors, rotations take set floors plus a GROUND-LINE "
                         "consistency check (bbox height is only a secondary, "
                         "non-gating diagnostic -- ruled 2026-08-30). A single "
                         "image under --set is still judged in full -- there is "
                         "no master to inherit from.")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.images:
        print("REFUSE: no image given. An empty check is not a pass.")
        return 2
    print("GENERATION-INPUT CHECK -- floors measured from TRELLIS's own")
    print("known-good example (183,353 subject px) against the crop that")
    print("failed (~3,700).")
    print("")
    if a.as_set and len(a.images) > 1:
        rows, master = judge_set(a.images)
        print("  SET MODE -- floors apply per SET (ruled 2026-08-30).")
        if master is not None:
            print("  master DERIVED as the max-extent view: %s"
                  % os.path.basename(master["path"]))
            print("  rotations are NOT held to longest-side or fill-low; they")
            print("  ARE held to subject px, frame, clipping, aspect, and a")
            print("  GROUND-LINE match within +-%.0f%% of the master."
                  % (100 * GROUND_TOL))
            print("  bbox height is a SECONDARY diagnostic at +-%.0f%%, "
                  "reported always," % (100 * HEIGHT_TOL))
            print("  and gating only when the ground line has ALSO failed.")
            gy = [r["ground_y"] for r in rows if "ground_y" in r]
            if len(gy) > 1:
                import statistics as _st
                spread = (max(gy) - min(gy)) / float(_st.median(gy))
                print("")
                print("  DIAGNOSTIC, not a gate -- GROUND LINE spread %.1f%% "
                      "across the set." % (100 * spread))
                print("  A camera that MOVED shifts the ground line and "
                      "rescales the whole bbox;")
                print("  a change of AZIMUTH leaves the subject standing in "
                      "the same place and")
                print("  only alters its silhouette. A tight ground line "
                      "beside a loose bbox")
                print("  height means the SUBJECT changed shape, not the "
                      "camera.")
        print("")
        return report(rows)
    if a.as_set:
        print("  --set given with ONE image: judged in FULL. There is no")
        print("  master to inherit from, so nothing can be relaxed.")
        print("")
    return report([judge(p) for p in a.images])


if __name__ == "__main__":
    sys.exit(main())
