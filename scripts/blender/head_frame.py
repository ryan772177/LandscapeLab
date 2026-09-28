"""head_frame.py -- the ONE measurement of a MetaHuman head's anatomy.

Imported by BOTH `author_hero_hair.py` (which uses the brow to decide where
roots may be placed) and `hero/groomloop/scripts/survey_head.py` (which
publishes it to every styling agent). It exists because those two had the brow
as two separate constants and both were wrong by the same 3.68 cm.

THE DEFECT THIS CLOSES, stated once so it is not re-derived. preview_hair.py put
the eye band at z_lo + 0.62..0.80 * height, and author_hero_hair.py gated the
face zone at face_zone_z_frac 0.80 of the same bounds. Same arithmetic, two
files -- so the agreement between them was ONE measurement, and the eye band had
never been measured from the head at all. It placed the brow at 170.93 on the
hero, and a line drawn there on his own bare-head render sits three centimetres
up his forehead (_verify/20260822_hero_authored/BROW_CHECK.png). Every guard
that "kept hair out of his eyes" was defending his forehead, which is why four
attempts at a fringe produced nothing.

HOW THE BROW IS ACTUALLY FOUND. The eye socket is the RECESS on the front of the
face, and it is OFF THE MIDLINE -- a first attempt took the frontmost vertex per
height band across the whole face and returned a point 2 cm below the crown,
because the frontmost vertex at eye height is the brow ridge itself. So: sample a
column at the eye's own lateral offset, walk up from the nose tip, take the first
local minimum in forward extent as the socket, and take the forward PEAK just
above it as the brow ridge.

    hero, 3.2-4.4 cm off midline
        cheek        ~11.9 forward
        SOCKET        11.41   z 165.1 - 165.5
        BROW RIDGE    12.63   z 167.4 - 167.9
        forehead     falls monotonically above 170.7
"""

import numpy as np

EYE_COLUMN_CM = (3.2, 4.4)      # lateral offset where the socket lives
NOSE_COLUMN_CM = 1.5            # midline column that finds the nose tip


def measure_head(verts, up, fwd, side):
    """verts: (N,3) world-space head vertices. Returns a dict of measured bands.

    Every OPERATIVE value is measured -- none of the returned bands is a
    fraction of the mesh bounds, which is the construction that produced the
    defect above. Two non-operative uses of bounds remain and are deliberate:
    the neck-cut search only BRACKETS where to look (30-75%% of bounds), and
    `_superseded_fraction_brow_up` is emitted solely as the discredited
    comparison value, never used.
    """
    V = np.asarray(verts, dtype=np.float64)
    z, y, x = V @ up, V @ fwd, V @ side
    z_lo, z_hi = float(z.min()), float(z.max())
    height = z_hi - z_lo

    # THE NECK CUT, so a sphere is fitted to a skull and not to a bust.
    # Taken where the cross-section is narrowest between the jaw and the
    # shoulders -- a measurement, not a chosen fraction.
    nbins = 60
    edges = np.linspace(z_lo, z_hi, nbins + 1)
    mids = 0.5 * (edges[:-1] + edges[1:])
    widths = np.full(nbins, np.nan)
    for i in range(nbins):
        m = (z >= edges[i]) & (z < edges[i + 1])
        if m.sum() >= 8:
            s = x[m]
            widths[i] = float(s.max() - s.min())
    cand = np.isfinite(widths) & (mids > z_lo + 0.30 * height)
    cand &= mids < z_lo + 0.75 * height
    # With zero qualifying bins np.where(cand, widths, inf) is all-inf and
    # nanargmin silently returns index 0 -- a meaningless neck_z near z_lo.
    # Refuse instead: this is the "measurement, not a chosen fraction" contract.
    if not cand.any():
        raise SystemExit("REFUSE: no width bin with >=8 verts in the 30-75%% "
                         "band; the neck cut cannot be measured on this mesh.")
    neck_z = float(mids[int(np.nanargmin(np.where(cand, widths, np.inf)))])

    sk = z >= neck_z
    crown_z = float(z[sk].max())

    # THE NOSE IS ON THE SKULL, NOT THE NECK -- and this line did not say so.
    #
    # It searched the WHOLE mesh for the frontmost midline vertex. On a head
    # mesh that stops at the jaw that is the nose. On the MetaHuman FACE MESH,
    # which carries a neck down to z 140.878, the frontmost midline vertex is
    # the THROAT, and it returned nose_tip_up 145.067 -- 16 cm BELOW the brow it
    # then went on to compute, and below the neck cut at 157.466. Every value
    # downstream of it was nonsense, and none of it raised: `above = cm >
    # nose_z` simply admitted the whole head, so a socket was still "found".
    #
    # Measured on dl_L1.blend: the module's own SUPERSEDED fallback (0.80 of
    # bounds = 170.925) was closer to the truth than its measurement. A fix that
    # is worse than the guess it replaced, on one class of input, is the exact
    # failure this module was written to prevent.
    #
    # `sk` is already the above-the-neck-cut mask. For a head-only mesh it
    # covers everything and this is a no-op, so the other two consumers are
    # unaffected.
    nose_m = sk & (np.abs(x) < NOSE_COLUMN_CM)
    if nose_m.sum() < 8:
        raise SystemExit(
            "REFUSE: fewer than 8 midline vertices above the neck cut at "
            "%.3f; the nose cannot be located on this mesh." % neck_z)
    nose_z = float(z[nose_m][int(np.argmax(y[nose_m]))])

    col = sk & (np.abs(x) >= EYE_COLUMN_CM[0]) & (np.abs(x) < EYE_COLUMN_CM[1])
    bands = np.linspace(neck_z, crown_z, 60)
    cm, ce = [], []
    for i in range(len(bands) - 1):
        m = col & (z >= bands[i]) & (z < bands[i + 1])
        if m.sum() >= 4:
            cm.append(0.5 * (bands[i] + bands[i + 1]))
            ce.append(float(y[m].max()))
    cm, ce = np.array(cm), np.array(ce)
    above = cm > nose_z
    sm, se = cm[above], ce[above]
    # Too few populated bands to look for a local minimum at all: distinguish
    # this "too sparse" cause from the genuine "no recess" one below, which
    # otherwise reports the wrong reason.
    if len(se) < 3:
        raise SystemExit(
            "REFUSE: only %d populated bands in the %.1f-%.1f cm eye column "
            "above the nose; too sparse to locate a socket." % (len(se),
                                                                *EYE_COLUMN_CM))
    si = next((i for i in range(1, len(se) - 1)
               if se[i] <= se[i - 1] and se[i] <= se[i + 1]), None)
    if si is None:
        raise SystemExit(
            "REFUSE: no eye-socket recess found in the %.1f-%.1f cm column. "
            "The brow cannot be measured on this mesh, and a fraction of the "
            "bounds is exactly the guess this module exists to replace."
            % EYE_COLUMN_CM)
    socket_z = float(sm[si])
    brow_z = float(sm[si + int(np.argmax(se[si:si + 8]))])

    return {
        "mesh_bounds_up": [round(z_lo, 3), round(z_hi, 3)],
        "neck_cut_up": round(neck_z, 3),
        "crown_up": round(crown_z, 3),
        "nose_tip_up": round(nose_z, 3),
        "eye_socket_up": round(socket_z, 3),
        "brow_up": round(brow_z, 3),
        "eye_band_up": [round(socket_z - (brow_z - socket_z), 3),
                        round(brow_z, 3)],
        "_superseded_fraction_brow_up": round(z_lo + 0.80 * height, 3),
        "_producer": "scripts/blender/head_frame.py measure_head()",
    }


def fit_skull_sphere(verts, up, neck_z, from_frac=0.35):
    """Least-squares sphere through the upper skull -> (centre, radius).

    THE CENTROID IS NOT THE CENTRE. Roots and scalp vertices live on a CAP, so
    their centroid sits near the top of the skull -- measured z 174.14 on a head
    spanning 140.9 to 178.4 -- which puts a crown mask's own origin above the
    crown. Fitting solves for the centre the cap is a cap OF.
    """
    V = np.asarray(verts, dtype=np.float64)
    z = V @ up
    sk = V[z >= neck_z]
    # An empty above-neck set must REFUSE, not compute: the old ternary called
    # sk[:, 0].max() on the empty array (a guaranteed ValueError) and read
    # world-x rather than the up-projection.
    if sk.shape[0] == 0:
        raise SystemExit("REFUSE: no vertices above the neck cut %.3f; the "
                         "skull sphere cannot be fitted." % neck_z)
    crown = float((sk @ up).max())
    P = sk[(sk @ up) >= neck_z + from_frac * (crown - neck_z)]
    # A sphere needs 4 non-degenerate points; lstsq would otherwise return a
    # silent minimum-norm garbage centre/radius on 0-3 points.
    if P.shape[0] < 4:
        raise SystemExit("REFUSE: only %d skull-cap points above the %.2f "
                         "fraction; cannot fit a sphere." % (P.shape[0],
                                                             from_frac))
    a = np.empty((P.shape[0], 4), dtype=np.float64)
    a[:, :3] = 2.0 * P
    a[:, 3] = 1.0
    sol, *_ = np.linalg.lstsq(a, (P ** 2).sum(axis=1), rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(sol[3] + float((c ** 2).sum()), 1e-12)))
