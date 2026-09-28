"""restyle_p234.py -- passes 2, 3 and 4 of the art spec, sharing one frame.

    blender --background <in.blend> --python this.py -- <out.blend> <pass> [params.json]

    pass = p2 | p3 | p4

One file because all three need the same frame, the same scalp fit, the same
anatomy and the same rigid-rotation helper, and three copies of that is how two
lists that must agree drift apart. The three ops themselves are independent.

SPEC -> MECHANISM

  P2, spec 3  lowest bang tips terminate AT or ABOVE the eyebrow ridge
              -> per front strand, scale about its root so its LOWEST point
                 sits at brow_up. Shorten only (k <= 1): a fringe that gets
                 longer is not a trim.
  P2, spec 3  nothing touches the eyes
              -> the same clamp, measured afterwards as the count of front
                 points below brow_up. It must be zero.
  P2, spec 3  asymmetric feathered sweep toward his RIGHT
              -> rigid rotation about the root toward -side (side is his LEFT,
                 so -side is his right), weighted by how frontal the root is.
  P2, spec 3  broken into distinct separated clusters, never a solid sheet
              -> front tips gathered toward N cluster centres, gather strength
                 ramped along the strand so roots stay spread and tips group.

  P3, spec 4  REDUCE global strand density
              -> cull curves by a deterministic hash of their index, so the
                 same seed always removes the same strands and a re-run is
                 reproducible. Culling is the one op here that is not
                 reversible in-place, so the source blend is never overwritten.
  P3, spec 4  reduce root-to-tip width multiplier (finer hairs)
              -> the `radius` POINT attribute, rewritten with a taper:
                 base * (root_scale -> tip_scale) along t.
  P3, spec 4  compensate with root stiffness + increased root standoff angle
              -> rigid rotation about the root TOWARD the scalp normal, so the
                 strand leaves the skull at a steeper angle and the silhouette
                 gains volume WITHOUT strand count.

  P4, spec 5  strong primary clumping into distinct chunky locks
              -> partition by curve INDEX BLOCK. That is not arbitrary: the
                 escalation consult on 2026-08-22 measured consecutive-index
                 roots sitting 4.13 mm apart against 125 mm for random pairs,
                 so index order carries the generator's own grouping. Strands
                 are drawn toward their block's mean curve.
  P4, spec 5  clump profile wide at root, aggressive taper to sharp fine tips
              -> gather strength follows t^taper, so roots keep their spread
                 and tips converge hard.
  P4, spec 5  minor secondary clumping + length variance for flyaways
              -> a second partition at a finer block size and lower strength,
                 then a random subset scaled slightly longer about the root.

Rotations are rigid about the root throughout; roots never move and that is
asserted. Length is preserved by every op EXCEPT the two that are explicitly
about length (the P2 trim and the P4 flyaways), which report their own deltas.
"""

import hashlib
import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "scripts", "blender"))
from head_frame import measure_head

P = {
    # ---- P2 fringe
    "front_fwd_pct": 72.0,      # roots above this fwd percentile are "front"
    "front_up_hi": 0.80,        # and below this normal-dot-up
    "brow_margin_cm": 3.4,      # tips stop this far ABOVE the brow
    "front_root_above_brow_cm": 1.5,   # a fringe is rooted above the brow
    "trim_k_floor": 0.14,       # never cut a strand below this fraction
    "eye_band_lo": 165.6,       # measured DNA eye band, CLAUDE.md
    "eye_band_hi": 168.5,
    "eye_half_width_cm": 6.0,
    "eye_clear_step_deg": 3.0,
    "eye_clear_cap_deg": 40.0,
    "eye_clear_max_iter": 18,
    "face_zone_margin_cm": 1.0,
    "face_zone_half_width_cm": 8.0,
    "sweep_right_deg": 26.0,    # magnitude of the fringe sweep
    "sweep_toward": "his_left",  # his_left = the VIEWER'S RIGHT. The operator
                                 #  asked for the bang moved from the left brow
                                 #  to the right one AS SEEN ON SCREEN, which is
                                 #  his own left. Flipped from "his_right".
    "fringe_clusters": 9,
    "fringe_gather": 0.55,
    "fringe_gather_taper": 2.0,
    # ---- P3 body
    "keep_frac": 0.88,          # legacy, unused once the cull went spatial
    "keep_frac_side": 0.50,     # B2: thin the sides so the ear shows
    "keep_frac_crown": 1.00,    # B4: keep the crown closed
    "keep_up_lo": 0.05,
    "keep_up_hi": 0.55,          # density DOWN -- 0.62 opened the scalp
                                #  (B4 2.88% -> 7.45%); the spec asks
                                #  for density down COMPENSATED by lift,
                                #  so lift carries more of it now
    "ear_lat_cm": 5.6,          # roots this far off midline are over the ear
    "ear_up_lo_cm": 4.0,
    "ear_up_hi_cm": 3.5,
    "ear_length_scale": 0.30,   # B2: 0.62 moved ear cover 1.00 -> 0.984
    "radius_base": 0.0125,      # was 0.018 -- finer hairs
    "radius_root_scale": 1.35,
    "radius_tip_scale": 0.25,
    "standoff_deg": 58.0,       # root lift -- raised from 14; at 14 the
                                #  gated mean was only 4.8 deg
    "standoff_up_lo": 0.05,
    # ---- P4 character
    "clump_block": 90,
    "clump_strength": 0.96,     # B6 needs within-clump spread BELOW
                                #  between-clump spread; 0.62 left 62%
    "clump_taper": 1.9,
    "clump2_block": 40,
    "clump2_strength": 0.22,
    "flyaway_frac": 0.045,
    "flyaway_scale": 1.28,
    "seed": 20260823,
}


def unit(v, eps=1e-12):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def fit_sphere(pts):
    A = np.hstack([2 * pts, np.ones((pts.shape[0], 1))])
    b = (pts ** 2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(1e-9, sol[3] + (c ** 2).sum())))


def rot_about_root(A, roots, axis, ang):
    k = unit(axis)
    c = np.cos(ang)[:, None]
    s = np.sin(ang)[:, None]
    rel = A - roots[:, None, :]
    out = np.empty_like(A)
    for j in range(A.shape[1]):
        v = rel[:, j, :]
        out[:, j, :] = (v * c + np.cross(k, v) * s
                        + k * (k * v).sum(1, keepdims=True) * (1.0 - c))
    return roots[:, None, :] + out


def lengths(A):
    return np.linalg.norm(np.diff(A, axis=1), axis=2).sum(1)


def gather_to_groups(A, roots, gid, strength, taper):
    """Pull each strand toward its group's mean curve, ramped along t."""
    k = A.shape[1]
    rel = A - roots[:, None, :]
    order = np.argsort(gid, kind="stable")
    gsorted = gid[order]
    starts = np.searchsorted(gsorted, np.unique(gsorted))
    means = np.zeros_like(rel)
    sums = np.zeros((gid.max() + 1, k, 3))
    cnt = np.bincount(gid, minlength=gid.max() + 1).astype(float)
    np.add.at(sums, gid, rel)
    gm = sums / np.maximum(cnt, 1)[:, None, None]
    means = gm[gid]
    t = (np.arange(k) / max(1, k - 1)) ** taper
    w = (strength * t)[None, :, None]
    return roots[:, None, :] + rel * (1 - w) + means * w


def load(ob):
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    k = d.curves[0].points_length
    return d, buf.reshape(n, 3).astype(np.float64).reshape(-1, k, 3), k


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend, which = tail[0], tail[1].lower()
    if len(tail) > 2 and os.path.isfile(tail[2]):
        with open(tail[2], "r", encoding="utf-8") as fh:
            P.update(json.load(fh))
    rng = np.random.default_rng(P["seed"])

    ob = pick_curves_object(bpy)
    d, A, k = load(ob)
    roots = A[:, 0, :]
    n_cur = A.shape[0]

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    up = np.array([0.0, 0.0, 1.0])
    fwd = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fwd)               # his LEFT
    anat = measure_head(V, up, fwd, side)
    centre, R = fit_sphere(roots)
    u = unit(roots - centre)
    up_dot = u @ up

    rep = {"pass": which, "curves_in": int(n_cur), "params": dict(P),
           "anatomy": anat, "L_in_mean": round(float(lengths(A).mean()), 4)}
    B = A.copy()

    # ---- PASS SPLIT, forced by the benchmark set.
    #
    # P2 originally did the face-zone cull AND the fringe work AND the eye
    # clear. It cleared the eye box to zero -- and after P3 and P4 ran, the
    # benchmarks read 2,381 points back in it. The standoff rotation and the
    # clumping both move strands, and neither knows about a constraint that was
    # satisfied two passes earlier.
    #
    # A CONSTRAINT ENFORCED BEFORE THE OPS THAT CAN VIOLATE IT IS NOT ENFORCED.
    # So the cull (about DENSITY, must precede the density pass) and the
    # fringe/eye work (a CONSTRAINT, must follow everything) are separated:
    #
    #     p0  face-zone cull only                                 before P3
    #     p5  fringe + sweep + clusters + eye clear + hard clear   LAST
    #
    # `p2` still runs both, kept as the record of how it was first built.
    do_cull = which in ("p0", "p2")
    do_fringe = which in ("p5", "p2")

    if which in ("p0", "p2", "p5"):
        # A FRINGE IS ROOTED ABOVE THE BROW. The first version selected only on
        # "frontal" and "not crown", and it caught the vellus / neckline layer
        # -- the 8,678 sub-millimetre strands identified 2026-08-22 as rooted
        # 6.5 cm LOWER than normal hair -- plus the sideburn roots. Those sit
        # BELOW brow_up, so no scaling about the root can ever lift their tips
        # above it: trim_k collapsed onto its 0.15 floor (mean 0.189, i.e. the
        # fringe cut to a fifth of its length) and 249,979 points were still
        # below the brow afterwards. The op was destroying the fringe and
        # failing its own check at the same time.
        brow = anat["brow_up"] + P["brow_margin_cm"]
        front = ((roots @ fwd) > np.percentile(roots @ fwd, P["front_fwd_pct"])) \
            & (up_dot < P["front_up_hi"]) \
            & (roots[:, 2] > anat["brow_up"] + P["front_root_above_brow_cm"])
        rep["front_strands"] = int(front.sum())
        rep["_front_excluded_low_roots"] = int(
            (((roots @ fwd) > np.percentile(roots @ fwd, P["front_fwd_pct"]))
             & (up_dot < P["front_up_hi"])
             & (roots[:, 2] <= anat["brow_up"]
                + P["front_root_above_brow_cm"])).sum())

        if not do_fringe:
            # emptying `front` makes the trim, the sweep and the clustering all
            # no-ops in one place, rather than three separate guards that can
            # disagree
            front = np.zeros(n_cur, dtype=bool)
            rep["fringe_skipped"] = True
        # --- trim: shorten so the lowest point sits at the brow. SHORTEN ONLY.
        lo = B[:, :, 2].min(1)
        need = front & (lo < brow)
        rel_lo = lo - roots[:, 2]
        target = brow - roots[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            kf = np.where(rel_lo < -1e-6, target / rel_lo, 1.0)
        kf = np.clip(np.where(need, kf, 1.0), P["trim_k_floor"], 1.0)
        B = roots[:, None, :] + (B - roots[:, None, :]) * kf[:, None, None]
        rep["trimmed_strands"] = int(need.sum())
        rep["trim_k"] = {"min": round(float(kf[need].min()), 4),
                         "mean": round(float(kf[need].mean()), 4)} \
            if need.any() else None

        # --- sweep toward his RIGHT (-side)
        w = np.where(front, 1.0, 0.0)
        ang = np.radians(P["sweep_right_deg"]) * w
        axis = np.repeat(up[None, :], n_cur, axis=0)
        # rotating about +up carries a forward strand toward -side or +side
        # depending on handedness; pick the sign that DECREASES tip-side and
        # verify it rather than reasoning about it
        # ---- WHICH WAY THE FRINGE SWEEPS, and the ambiguity is worth naming.
        #
        # `side` is cross(up, fwd) = the character's OWN LEFT. A viewer facing
        # him sees his left on THEIR RIGHT, so "the bang over the left eyebrow"
        # means opposite things depending on who is speaking. The operator is
        # looking at a render, so their words are viewer-relative and the
        # parameter is named for the character to keep the code unambiguous:
        #
        #   sweep_toward "his_right"  -> tip_side NEGATIVE -> viewer's LEFT
        #   sweep_toward "his_left"   -> tip_side POSITIVE -> viewer's RIGHT
        #
        # The sign is still CHOSEN BY MEASUREMENT rather than reasoned about --
        # both rotations are applied, the resulting mean tip-side is read, and
        # the one that moves it the wanted way wins. A handedness argument that
        # is wrong sweeps the fringe INTO the face and every read-back agrees.
        t0 = (B[:, -1, :] @ side)[front].mean()
        Bp = rot_about_root(B, roots, axis, ang)
        Bm = rot_about_root(B, roots, axis, -ang)
        tp = (Bp[:, -1, :] @ side)[front].mean()
        tm = (Bm[:, -1, :] @ side)[front].mean()
        _want_pos = (P["sweep_toward"] == "his_left")
        _use_plus = (tp > tm) if _want_pos else (tp < tm)
        B = Bp if _use_plus else Bm
        rep["sweep_sign_check"] = {
            "sweep_toward": P["sweep_toward"],
            "before_tip_side": round(float(t0), 4),
            "plus": round(float(tp), 4), "minus": round(float(tm), 4),
            "chose": "+" if _use_plus else "-",
            "tip_side_after": round(float(tp if _use_plus else tm), 4),
            "moved_the_wanted_way": bool(
                ((tp if _use_plus else tm) > t0) == _want_pos)}

        # --- clusters
        if front.any():
            fr = np.where(front)[0]
            key = np.arctan2(roots[fr] @ side, roots[fr] @ fwd)
            gid = np.zeros(n_cur, dtype=np.int64)
            gid[fr] = (np.argsort(np.argsort(key)) *
                       P["fringe_clusters"] // max(1, fr.size)) + 1
            B2 = gather_to_groups(B, roots, gid, P["fringe_gather"],
                                  P["fringe_gather_taper"])
            B = np.where(front[:, None, None], B2, B)

        # ---- WHO OWNS THE EYE-BOX POINTS? Ask before applying another fix.
        eye_lo0, eye_hi0 = P["eye_band_lo"], P["eye_band_hi"]
        fwd_cut = np.percentile(V @ fwd, 96)

        def box_mask(X):
            p = X.reshape(-1, 3)
            m = ((p[:, 2] > eye_lo0) & (p[:, 2] < eye_hi0)
                 & ((p @ fwd) > fwd_cut)
                 & (np.abs(p @ side) < P["eye_half_width_cm"]))
            return m.reshape(X.shape[0], X.shape[1])

        own = box_mask(B).any(1)
        if own.any():
            rz = roots[own][:, 2]
            rep["eye_box_owners"] = {
                "strands": int(own.sum()),
                "root_up_pct": [round(float(np.percentile(rz, q)), 2)
                                for q in (5, 50, 95)],
                "rooted_below_brow_pct": round(
                    float((rz < anat["brow_up"]).mean() * 100), 2),
                "in_front_band_pct": round(
                    float(front[own].mean() * 100), 2)}

        # ---- CULL THE STRANDS ROOTED ON HIS FACE.
        #
        # The diagnostic above is what redirected this. The eye-box occupants
        # are not the fringe -- they are overwhelmingly rooted BELOW the brow,
        # on the forehead, temples and face itself, and no amount of styling a
        # fringe reaches them. Rotating them about the root just swings a strand
        # that grows out of an eyebrow into a different part of the eye: 18
        # iterations at a 40 degree cap moved the count 16,206 -> 15,357.
        #
        # This is R-HAIRFACE exactly, on a different groom. That recipe records
        # the authored groom growing hair at z <= 168.7 against a hairline at
        # 171.68, both guards fooled because they read a surface NORMAL and a
        # MetaHuman face carries eyelids and sockets whose normals do not point
        # forward. The fix there was a POSITION-based face zone, and it is the
        # fix here: DiffLocks placed roots wherever its npz put them, and some
        # of them are on his face.
        face_zone = ((roots[:, 2] < anat["brow_up"] + P["face_zone_margin_cm"])
                     & ((roots @ fwd) > np.percentile(V @ fwd, 82))
                     & (np.abs(roots @ side) < P["face_zone_half_width_cm"]))
        rep["face_zone_cull"] = {
            "strands": int(face_zone.sum()),
            "pct_of_groom": round(float(face_zone.mean() * 100), 2)}
        if not do_cull:
            face_zone = np.zeros(n_cur, dtype=bool)
            rep["face_zone_cull"]["applied"] = False
        keep_face = ~face_zone
        B = B[keep_face]
        A = A[keep_face]
        roots = roots[keep_face]
        front = front[keep_face]
        n_cur = B.shape[0]

        # ---- CLEAR THE EYES EXPLICITLY. A trim does not get there on its own.
        #
        # With the fringe band corrected the trim still left 16,206 points in
        # the eye box, because `trim_k` bottoms out at its floor for strands
        # rooted near the brow and shortening any further would delete the
        # fringe rather than lift it. Length was the wrong lever: the spec wants
        # the fringe PRESENT and OFF the eyes, which is a direction, not a size.
        #
        # So: rotate offending strands about the lateral axis until their points
        # leave the box, a few degrees at a time, with a hard cap. The sign is
        # CHOSEN BY MEASUREMENT on the first iteration rather than reasoned
        # about -- the same discipline the sweep uses, because a handedness
        # argument that is wrong produces a confident groom pushed INTO the face.
        eye_lo0, eye_hi0 = P["eye_band_lo"], P["eye_band_hi"]
        face_y0 = V @ fwd
        fwd_cut = np.percentile(face_y0, 96)

        def in_box(X):
            p = X.reshape(-1, 3)
            m = ((p[:, 2] > eye_lo0) & (p[:, 2] < eye_hi0)
                 & ((p @ fwd) > fwd_cut)
                 & (np.abs(p @ side) < P["eye_half_width_cm"]))
            return m.reshape(X.shape[0], X.shape[1])

        rep["eye_clear_iterations"] = []
        axis_s = np.repeat(side[None, :], n_cur, axis=0)
        sign = None
        total = np.zeros(n_cur)
        for it in range(P["eye_clear_max_iter"] if do_fringe else 0):
            bad = in_box(B).any(1)
            if not bad.any():
                break
            step = np.radians(P["eye_clear_step_deg"]) * bad
            if sign is None:
                cp = in_box(rot_about_root(B, roots, axis_s, step)).sum()
                cm = in_box(rot_about_root(B, roots, axis_s, -step)).sum()
                sign = 1.0 if cp < cm else -1.0
                rep["eye_clear_sign_check"] = {"plus": int(cp), "minus": int(cm),
                                               "chose": "+" if sign > 0 else "-"}
            room = np.clip(P["eye_clear_cap_deg"] - total, 0, None)
            step = np.minimum(np.degrees(step), room)
            total += step
            B = rot_about_root(B, roots, axis_s, sign * np.radians(step))
            rep["eye_clear_iterations"].append(
                {"iter": it, "strands": int(bad.sum()),
                 "points_in_box": int(in_box(B).sum())})
        rep["eye_clear_rotation_deg"] = {
            "mean_of_moved": round(float(total[total > 0].mean()), 2)
            if (total > 0).any() else 0.0,
            "max": round(float(total.max()), 2)}

        # ---- HARD CLEAR. The spec says nothing touches the eyes; 0.15% is not
        # nothing. What survives the cull and the rotation is a few hundred
        # strands that cannot be steered out without deforming them visibly, so
        # they are removed. At this fraction the cost is not visible and the
        # constraint becomes STRUCTURAL rather than gated -- an eye that cannot
        # have hair in it beats an eye that is checked for hair.
        still = box_mask(B).any(1)
        rep["hard_clear_strands"] = int(still.sum())
        rep["hard_clear_pct"] = round(float(still.mean() * 100), 4)
        if still.any() and do_fringe:
            B = B[~still]
            A = A[~still]
            roots = roots[~still]
            front = front[~still]
            keep_face[np.where(keep_face)[0][still]] = False
            n_cur = B.shape[0]

        # ---- THE EYE CHECK IS AN EYE BOX, NOT "BELOW THE BROW".
        #
        # "front points below the brow" counts a sideburn strand hanging past
        # the cheek as hair in his eyes, and misses a strand swept in from the
        # side that actually crosses them. The spec item is "nothing touches
        # the eyes", so measure the EYES.
        #
        # The band is the project's own measured record for this DNA:
        # "teeth Y 156.5..162.1; eyes Y 165.6..168.5" (CLAUDE.md, DNA space,
        # Y up). It is used in preference to `anat["eye_band_up"]`, which on
        # this mesh returns socket 170.084 and brow 170.440 -- 0.36 cm apart,
        # far too tight to be a real socket-to-brow distance, so that part of
        # the anatomy is still marginal here even after the nose fix.
        eye_lo, eye_hi = P["eye_band_lo"], P["eye_band_hi"]
        pts = B.reshape(-1, 3)
        face_y = V @ fwd
        in_eye = ((pts[:, 2] > eye_lo) & (pts[:, 2] < eye_hi)
                  & ((pts @ fwd) > np.percentile(face_y, 96))
                  & (np.abs(pts @ side) < P["eye_half_width_cm"]))
        rep["points_in_eye_box"] = int(in_eye.sum())
        rep["points_in_eye_box_pct"] = round(
            float(in_eye.mean() * 100), 4)
        rep["eye_clear"] = bool(in_eye.sum() == 0)
        rep["_eye_box"] = {"up": [eye_lo, eye_hi],
                           "half_width_cm": P["eye_half_width_cm"],
                           "source": "CLAUDE.md measured DNA eye band"}
        rep["front_lowest_tip_up"] = round(float(B[front][:, :, 2].min()), 3) \
            if front.any() else None

    elif which == "p3":
        h = np.frombuffer(
            hashlib.sha256(np.arange(n_cur).tobytes()
                           + str(P["seed"]).encode()).digest() * (n_cur // 32 + 1),
            dtype=np.uint8)[:n_cur].astype(np.float64) / 255.0
        # ---- THE CULL IS SPATIAL, because the benchmarks pull opposite ways.
        #
        # B4 wants no scalp through the TOP; B2 wants the SIDES thin enough to
        # show part of the ear. A single global keep-fraction trades one against
        # the other: at 0.62 the scalp opened to 7.45%, at 0.88 the ears stayed
        # 86% covered. Neither is a compromise, both are just the wrong knob.
        #
        # A haircut is not uniformly dense either. Keep the crown, thin the
        # sides: keep_frac interpolates from `keep_frac_side` at the ear line to
        # `keep_frac_crown` at the top, by the root's own normal-dot-up.
        ud = ((roots - centre)
              / np.maximum(np.linalg.norm(roots - centre, axis=1),
                           1e-9)[:, None]) @ up
        t_up = np.clip((ud - P["keep_up_lo"]) /
                       max(1e-6, P["keep_up_hi"] - P["keep_up_lo"]), 0, 1)
        kf_local = (P["keep_frac_side"]
                    + (P["keep_frac_crown"] - P["keep_frac_side"]) * t_up)
        keep = h < kf_local
        rep["keep_frac_spatial"] = {
            "side": P["keep_frac_side"], "crown": P["keep_frac_crown"],
            "actual": round(float(keep.mean()), 4)}
        rep["culled"] = {"from": int(n_cur), "to": int(keep.sum()),
                         "keep_frac_actual": round(float(keep.mean()), 4)}
        B = B[keep]
        roots_k = B[:, 0, :]
        uk = unit(roots_k - centre)
        # root lift toward the scalp normal
        m = unit(B[:, -1, :] - roots_k)
        axis = np.cross(m, uk)
        na = np.linalg.norm(axis, axis=1)
        axis[na < 1e-9] = up
        gate = np.clip((uk @ up - P["standoff_up_lo"]) /
                       max(1e-6, 1.0 - P["standoff_up_lo"]), 0, 1)
        B = rot_about_root(B, roots_k, axis, np.radians(P["standoff_deg"]) * gate)
        rep["standoff_deg_mean"] = round(
            float((P["standoff_deg"] * gate).mean()), 3)

        # ---- SHORTEN OVER THE EARS so part of the ear shows.
        # Benchmark B2 read the ears 100% covered. The reference shows them
        # partly. This is a LENGTH trim confined to the strands whose roots sit
        # over the ear laterally and at ear height -- not a global shortening,
        # which would undo L1.
        latk = roots_k @ side
        earband = (np.abs(latk) > P["ear_lat_cm"]) \
            & (roots_k[:, 2] < anat["brow_up"] + P["ear_up_hi_cm"]) \
            & (roots_k[:, 2] > anat["brow_up"] - P["ear_up_lo_cm"])
        sc = np.where(earband, P["ear_length_scale"], 1.0)
        B = roots_k[:, None, :] + (B - roots_k[:, None, :]) * sc[:, None, None]
        rep["ear_band"] = {"strands": int(earband.sum()),
                           "scale": P["ear_length_scale"]}
        rep["_radius"] = {"base": P["radius_base"],
                          "root_scale": P["radius_root_scale"],
                          "tip_scale": P["radius_tip_scale"]}

    elif which == "p4":
        blk = np.arange(n_cur) // max(1, P["clump_block"])
        B = gather_to_groups(B, roots, blk.astype(np.int64),
                             P["clump_strength"], P["clump_taper"])
        blk2 = np.arange(n_cur) // max(1, P["clump2_block"])
        B = gather_to_groups(B, roots, blk2.astype(np.int64),
                             P["clump2_strength"], P["clump_taper"])
        fly = rng.random(n_cur) < P["flyaway_frac"]
        sc = np.where(fly, P["flyaway_scale"], 1.0)
        B = roots[:, None, :] + (B - roots[:, None, :]) * sc[:, None, None]
        rep["clumps"] = {"primary": int(blk.max() + 1),
                         "secondary": int(blk2.max() + 1),
                         "flyaways": int(fly.sum())}
        # did the clumping actually tighten the tips?
        def spread(X):
            g = X[:, -1, :]
            gm = np.zeros((blk.max() + 1, 3))
            np.add.at(gm, blk, g)
            gm /= np.maximum(np.bincount(blk, minlength=blk.max() + 1), 1)[:, None]
            return float(np.linalg.norm(g - gm[blk], axis=1).mean())
        rep["tip_spread_in_clump_cm"] = {
            "before": round(spread(A), 4), "after": round(spread(B), 4)}
    else:
        raise SystemExit("REFUSE: unknown pass " + which)

    rk = B[:, 0, :]
    ak = A[:len(B), 0, :] if which == "p3" else A[:, 0, :]
    rep["root_shift_max_cm"] = round(
        float(np.linalg.norm(rk - (roots[keep] if which == "p3" else roots),
                             axis=1).max()), 10)
    if rep["root_shift_max_cm"] > 1e-9:
        rep["error"] = "REFUSE: an op moved a root."
        print("__PX__" + json.dumps(rep, default=str))
        raise SystemExit(3)
    rep["L_out_mean"] = round(float(lengths(B).mean()), 4)

    # ---- write back. P2 and P3 both change the CURVE COUNT, so they rebuild.
    # P2 culls the face-zone roots; P3 culls for density. `keep` is whichever
    # mask this pass applied, so the root UVs travel with the strands that
    # survive -- a rebuild that kept the ORIGINAL UV array would re-pair every
    # remaining strand with the wrong root, silently.
    if which in ("p0", "p2", "p5", "p3"):
        keep = keep_face if which in ("p0", "p2", "p5") else keep
        n_src = len(d.curves)
        uvsrc = d.attributes.get("groom_root_uv")
        uv = np.zeros(n_src * 2, dtype=np.float32)
        uvsrc.data.foreach_get("vector", uv)
        uv = uv.reshape(n_src, 2)[keep]
        surf, uvmap = d.surface, d.surface_uv_map
        for o in [x for x in bpy.data.objects if x.type == "CURVES"]:
            bpy.data.objects.remove(o, do_unlink=True)
        nm = "AlpineHero_DiffLocks_" + which.upper()
        hc = bpy.data.hair_curves.new(nm)
        nob = bpy.data.objects.new(nm, hc)
        bpy.context.scene.collection.objects.link(nob)
        nob.parent = head
        nob.matrix_parent_inverse = head.matrix_world.inverted()
        hc.add_curves([k] * len(B))
        hc.attributes["position"].data.foreach_set(
            "vector", B.reshape(-1, 3).astype(np.float32).ravel())
        a2 = hc.attributes.get("groom_root_uv") or hc.attributes.new(
            "groom_root_uv", "FLOAT2", "CURVE")
        a2.data.foreach_set("vector", uv.astype(np.float32).ravel())
        # P2 rebuilds only because it CULLS; the width taper belongs to P3 and
        # applying it here would mean two passes owning one visual property.
        # Carry P2's radii through unchanged, sliced by the same keep mask.
        if which in ("p0", "p2", "p5"):
            rsrc = np.zeros(n_src * k, dtype=np.float32)
            d.attributes["radius"].data.foreach_get("value", rsrc)
            rad = rsrc.reshape(n_src, k)[keep].ravel().astype(np.float32)
        else:
            t = np.linspace(0.0, 1.0, k)
            prof = (P["radius_root_scale"]
                    + (P["radius_tip_scale"] - P["radius_root_scale"]) * t)
            rad = np.tile(P["radius_base"] * prof, len(B)).astype(np.float32)
        r2 = hc.attributes.get("radius") or hc.attributes.new(
            "radius", "FLOAT", "POINT")
        r2.data.foreach_set("value", rad)
        hc.surface = surf
        hc.surface_uv_map = uvmap
        rep["rebuilt"] = {"curves": len(B), "points": len(hc.points),
                          "radius_min": float(rad.min()),
                          "radius_max": float(rad.max())}
    else:
        d.attributes["position"].data.foreach_set(
            "vector", B.reshape(-1, 3).astype(np.float32).ravel())

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["saved"] = out_blend
    print("__PX__" + json.dumps(rep, default=str))


if __name__ == "__main__":
    main()
