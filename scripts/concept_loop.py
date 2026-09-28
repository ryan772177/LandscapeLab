"""Phase B loop v0, RENDERLESS: build a concept, measure it, report deltas.

The loop's judgement half needs pictures. Its ARITHMETIC half does not, and
that is the half this runs: counts, scales, ratios and angular extents are all
transforms, and a transform can be checked tonight while a render costs the
editor for a quarter of an hour.

Three iterations, one builder (iter0 baseline; iter1 re-derives the FOV from
the concept's recorded TERRAIN bearings; iter2, authorized 2026-08-30,
re-derives it from the CHALET extents). Each iteration changes only what the
previous one's measurements imply, so the loop is a loop rather than guesses.
"""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import concept_solve_camera as csc                    # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUTDIR = os.path.join(REPO, "_verify", "20260830_loop")


def _part_ratio(concept, part_name):
    """The ruled height_ratio for a church part, READ from the recipe
    (pipeline rule 2) -- NOT hardcoded. The report prints these as
    "(recipe N.NNx)", so N must actually come from the recipe. Raises if the
    part is absent (fail loud, like the other required-key lookups here)."""
    for it in concept["placements"]["items"]:
        if it.get("class") == "church":
            for pt in it.get("parts", []):
                if pt.get("part") == part_name:
                    return float(pt["height_ratio"])
    raise KeyError("concept has no church part %r with height_ratio "
                   "(pipeline rule 2)" % part_name)


# WHAT `deltas: []` ACTUALLY MEANS, DECLARED NEXT TO THE THING IT QUALIFIES
#
# An empty delta list says "converged on what I measure". It has never said
# "converged". On 2026-08-30 this loop reported `deltas: []` for iteration 1
# while, in the rendered frame, every kit roof splayed wider than the wall box
# under it -- because roof-to-wall FIT is not one of the dimensions below.
#
# That is not a bug. It is the arithmetic half of the loop working exactly as
# the module docstring promises. It becomes a defect only when a reader takes
# the empty list for a verdict on the picture, which is a thing a tired session
# will do unless the scope travels WITH the result.
#
# So both lists are emitted into loop_v0.json beside every `deltas` field and
# cannot be separated from it. Adding a check means adding its line here.
MEASURED_DIMENSIONS = [
    "count: chalets placed vs the concept's recorded count_range",
    "framing: chalet angular extent vs the camera half-FOV",
    "nave: height as a ratio of the chalet silhouette, vs the ruling",
    "spire: height as a ratio of the chalet silhouette, vs the ruling",
    "fov: outermost recorded terrain feature vs 0.95 of the half-width",
    "plausibility: the chalet SILHOUETTE, and every ratio-scored height "
    "derived from it, against an ABSOLUTE band -- the only check that can "
    "catch a wrong reference, because a ratio cannot",
]

NOT_MEASURED = [
    "FIT -- whether a kit roof SEATS on the wall box it covers. The roofs "
    "splay wider than their walls in both iterations and no delta above can "
    "see it (found 2026-08-30 by looking at the frame, not by the loop). "
    "Roof-to-footprint fit is RULING 4's territory -- the planner that biases "
    "footprints toward servable roofs is the code that must seat them.",
    "MATERIAL -- albedo, tonal range, exposure. The stage ground is "
    "untextured white and the loop is content with that.",
    "OCCLUSION -- whether nearer geometry hides what the bearings say is "
    "visible. Bearings are computed, not traced.",
    "LANDFORM -- terrain is DEFERRED on this stage, so nothing about a "
    "silhouette read against a hillside is tested.",
    "Anything needing a pixel. That is the render half, by construction.",
]


def build(cfg):
    with io.open(os.path.join(REPO, "scripts", "concept_build_payload.txt"),
                 encoding="utf-8") as fh:
        tmpl = fh.read()
    assert "CFG_JSON" in tmpl
    gen = os.path.join(REPO, "LandscapeLab", "Saved", "concept_build_gen.txt")
    with io.open(gen, "w", encoding="utf-8") as fh:
        fh.write(tmpl.replace("CFG_JSON", repr(cfg)))
    # ⛔ encoding IS NOT OPTIONAL. `text=True` alone decodes with the LOCALE
    # codec (cp1252 here); a byte it cannot decode kills the reader thread and
    # `p.stdout` comes back None. This function then reports "NO RESULT FROM
    # THE EDITOR -- that is 'could not look'", which is TRUE of the pipe and
    # FALSE of the editor, and sends the next session hunting the wrong thing.
    # Same defect as forge.py::_run, fixed 2026-08-30; one of the 20+ sites.
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         gen, "--timeout", "25"], capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if i < 0:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1200:])
        return None
    return json.loads(t[i:j + 1])


def report(tag, cfg, r, concept):
    print("")
    print("=== ITERATION %s ===" % tag)
    if r.get("error"):
        print("  BUILD FAILED: " + str(r["error"])[:400])
        # NN13: a FAILED build must NOT return the same empty delta list a
        # CONVERGED one does -- that empty list is persisted into loop_v0.json
        # and would read identically to agreement. Emit a sentinel delta.
        return [("build", "FAILED: " + str(r.get("error"))[:200])]
    m = r["measured"]
    lo, hi = concept["placements"]["items"][0]["count_range"]
    print("  level          %s   saved %s" % (cfg["level"], r.get("saved")))
    print("  greyboxes      %d   kit roofs %d   cleared %s   route: %s"
          % (r["greybox_count"], r["kit_roof_count"],
             r.get("cleared_prior_actors"), r.get("level_route")))
    print("  chalets        %d   recipe range [%d, %d]"
          % (m["chalets_placed"], lo, hi))
    print("  chalet walls   %.0f cm  (%d storeys x %.1f m)"
          % (m["chalet_wall_height_cm"], cfg["chalet_storeys"],
             cfg["storey_m"]))
    print("  chalet SILHOUETTE %.0f cm  (walls + kit roof -- what is seen)"
          % m["chalet_silhouette_cm"])
    print("  church nave    %.0f cm  = %.2fx silhouette   (recipe %.2fx)"
          % (m["church_nave_top_cm"], m["nave_over_silhouette"],
             cfg["nave_ratio"]))
    print("  church spire   %.0f cm  = %.2fx silhouette   (recipe %.2fx)"
          % (m["church_spire_top_cm"], m["spire_over_silhouette"],
             cfg["spire_ratio"]))
    print("  camera fov     %.1f (read back)  rot %s"
          % (m["camera_fov_readback"], m["camera_rot_readback"]))
    print("  chalet bearings %.1f .. %.1f deg, half-FOV %.1f, OUTSIDE %d"
          % (m["chalet_bearing_min_deg"], m["chalet_bearing_max_deg"],
             m["half_fov_deg"], m["chalets_outside_frame"]))

    deltas = []
    if not (lo <= m["chalets_placed"] <= hi):
        deltas.append(("count", "placed %d, recipe range [%d, %d]"
                       % (m["chalets_placed"], lo, hi)))
    if m["chalets_outside_frame"]:
        deltas.append(("framing", "%d chalet(s) outside the %.0f deg frame"
                       % (m["chalets_outside_frame"],
                          cfg["fov_horizontal_deg"])))
    # ⭐ THE CHURCH-SCALE DELTA IS RETIRED, not silenced. Schema 1.1 splits the
    # entity into nave and tower_spire, so the recipe no longer contradicts
    # itself and there is nothing left to report as a contradiction.
    #
    # What is checked now is a DIFFERENT question: does the BUILD match the
    # ruled ratios? That one can actually be satisfied, where the old one could
    # not be -- no single number was ever going to be both 1.5x and 2x.
    for part, got, want in (("nave", m["nave_over_silhouette"],
                             cfg["nave_ratio"]),
                            ("spire", m["spire_over_silhouette"],
                             cfg["spire_ratio"])):
        if got is None:
            deltas.append(("church %s" % part, "NOT MEASURED"))
        elif abs(got - want) > 0.15:
            deltas.append(("church %s" % part,
                           "built %.2fx the silhouette, recipe says %.2fx"
                           % (got, want)))
    # ⭐ THE PLAUSIBILITY BAND -- an ABSOLUTE check, added 2026-08-30.
    #
    # Every other height check here is a RATIO, and a ratio cannot detect an
    # error in the quantity it is a ratio OF: when the chalet silhouette read
    # 536.5 instead of 738.0 because the kit roof was buried in its walls,
    # nave_over_silhouette still read exactly 1.50 and spire 2.50, and not one
    # delta fired. Both terms moved together and the quotient stayed right.
    #
    # ONE band is declared -- on the silhouette -- and every part band is
    # DERIVED from it by the ruled ratio, so there is no second list to drift.
    band = None
    for _it in concept["placements"]["items"]:
        if _it.get("class") == "chalet":
            band = _it.get("silhouette_plausible_cm")
    if band:
        lo, hi = float(band[0]), float(band[1])
        sil = m["chalet_silhouette_cm"]
        if sil is not None and not (lo <= sil <= hi):
            deltas.append(("plausibility",
                           "chalet SILHOUETTE %.1f cm is OUTSIDE the plausible "
                           "band %.0f-%.0f -- a ratio check cannot see this, "
                           "which is why the band exists" % (sil, lo, hi)))
        for _part, _got, _ratio in (
                ("nave", m["church_nave_top_cm"], cfg["nave_ratio"]),
                ("spire", m["church_spire_top_cm"], cfg["spire_ratio"])):
            plo, phi = lo * _ratio, hi * _ratio
            if _got is not None and not (plo <= _got <= phi):
                deltas.append(("plausibility %s" % _part,
                               "%.1f cm is OUTSIDE %.0f-%.0f (%.2fx the "
                               "silhouette band)" % (_got, plo, phi, _ratio)))
    else:
        deltas.append(("plausibility",
                       "NO BAND DECLARED -- the concept carries no "
                       "silhouette_plausible_cm, so nothing absolute was "
                       "checked. That is 'I could not look'."))

    # every recorded terrain feature must be INSIDE the frame, with margin
    _bearings = csc.bearings(concept)
    if not _bearings:
        # No terrain features: refuse the check rather than crash on max([])
        # (the previous `bearings and [...]` had a dead `and` that did this).
        deltas.append(("fov", "NO TERRAIN FEATURES recorded -- cannot check "
                       "whether the outermost sits inside the frame. That is "
                       "'I could not look.'"))
    else:
        bmax = max(abs(f[1]) for f in _bearings)
        frac = bmax / (cfg["fov_horizontal_deg"] / 2.0)
        if frac > 0.95:
            deltas.append(("fov",
                           "outermost recorded feature sits at %.2f of the "
                           "half-width -- a feature the reader saw INSIDE the "
                           "image cannot be on the boundary" % frac))
    print("")
    if deltas:
        print("  DELTAS MEASURABLE WITHOUT A RENDER:")
        for k, why in deltas:
            print("    %-13s %s" % (k, why))
    else:
        print("  no render-free deltas remain")
    print("")
    print("  SCOPE OF THIS INSTRUMENT -- %d dimensions it CAN measure without "
          "a render, %d it cannot (some may still read 'could not look' above "
          "on this run):" % (len(MEASURED_DIMENSIONS), len(NOT_MEASURED)))
    for _d in MEASURED_DIMENSIONS:
        print("    measured      %s" % _d)
    for _d in NOT_MEASURED:
        print("    NOT measured  %s" % _d)
    return deltas


def self_test():
    """OFFLINE control for the plausibility band. No editor.

    THE CONTROL IS THIS WEEK'S ACTUAL DEFECT: feed report() the values the
    loop produced while the kit roof was buried 201.49 cm in its walls
    (silhouette 536.5, nave 804.8, spire 1341.3) and require plausibility
    deltas; feed it the corrected values and require none.

    ⭐ THE RATIOS ARE IDENTICAL IN BOTH CASES -- 1.50 and 2.50 -- which is the
    whole point. Every ratio check passed throughout the defect. Only an
    ABSOLUTE band can tell the two apart, so only an absolute band is evidence
    that the reference itself is right.
    """
    cpath = os.path.join(REPO, "recipes", "concepts",
                         "alpine_village_01.json")
    with io.open(cpath, encoding="utf-8") as fh:
        concept = json.load(fh)
    cfg = {"level": "/selftest", "chalet_storeys": 2, "storey_m": 2.0,
           "nave_ratio": 1.5, "spire_ratio": 2.5, "fov_horizontal_deg": 78.6}

    def m_for(sil, nave, spire):
        return {"chalets_placed": 16, "chalet_wall_height_cm": 400.0,
                "chalet_silhouette_cm": sil, "church_nave_top_cm": nave,
                "nave_over_silhouette": round(nave / sil, 3),
                "church_spire_top_cm": spire,
                "spire_over_silhouette": round(spire / sil, 3),
                "camera_fov_readback": 78.6,
                "camera_rot_readback": [0, 0, 0],
                "chalet_bearing_min_deg": 11.0,
                "chalet_bearing_max_deg": 33.2,
                "half_fov_deg": 39.3, "chalets_outside_frame": 0}

    def deltas_for(sil, nave, spire):
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            d = report("selftest", cfg,
                       {"measured": m_for(sil, nave, spire),
                        "greybox_count": 19, "kit_roof_count": 16,
                        "saved": True}, concept)
        return [k for k, _ in d]

    print("SELF-TEST -- the plausibility band, against this week's defect")
    print("")
    bad = deltas_for(536.5, 804.8, 1341.3)
    good = deltas_for(738.0, 1107.0, 1845.0)
    bp = [k for k in bad if k.startswith("plausibility")]
    gp = [k for k in good if k.startswith("plausibility")]
    print("  ratios are 1.50 / 2.50 in BOTH cases -- identical, and correct")
    print("  %-8s buried-roof values 536.5/804.8/1341.3 -> %s"
          % ("REFUSED" if bp else "*** PASSED ***", bp or "no deltas"))
    print("  %-8s corrected values  738.0/1107.0/1845.0 -> %s"
          % ("passed" if not gp else "*** REFUSED ***", gp or "no deltas"))
    ok = bool(bp) and not gp
    print("")
    if ok:
        print("BAND DISCRIMINATES: it refuses the reference that every ratio")
        print("check called correct, and passes the measured one.")
    else:
        print("*** THE BAND DOES NOT DISCRIMINATE ***")
    return 0 if ok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    cpath = "recipes/concepts/alpine_village_01.json"
    with io.open(os.path.join(REPO, cpath), encoding="utf-8") as fh:
        concept = json.load(fh)
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)

    fov0 = 60.0
    s0 = csc.solve(concept, fov0)
    base = {
        "level": "/Game/Scratch/Concept01_Loop",
        "iteration": "iter0",
        "offset_y_m": 0.0,
        "sun_elevation_deg": concept["atmosphere"]["sun"]["elevation_deg"],
        "sun_yaw_deg": -75.0,
        "exposure_ev": -1.923,
        "village_bearing_deg": 22.0,
        "village_distance_m": 220.0,
        "cluster_radius_m": 45.0,
        "chalet_count": 16,
        "chalet_footprint_m": [10.0, 8.0],
        "chalet_storeys": 2,
        "nave_ratio": _part_ratio(concept, "nave"),
        "spire_ratio": _part_ratio(concept, "tower_spire"),
        "storey_m": 2.0,
        "roof_package": "/Game/Meshes/Houses/Roofs/House02_Roof/SM_House02_Roof",
        "camera_height_m": s0["height_m"],
        "camera_pitch_deg": s0["pitch_deg"],
        "fov_horizontal_deg": fov0,
    }

    r0 = build(base)
    if r0 is None:
        return 5
    d0 = report("0", base, r0, concept)

    # ---- ITERATION 1: fix only what iteration 0 MEASURED ----------------
    bmax = max(abs(f[1]) for f in csc.bearings(concept))
    fov1 = round(2.0 * bmax / 0.90, 1)     # outermost feature at 0.90 of half
    s1 = csc.solve(concept, fov1)
    cfg1 = dict(base)
    cfg1.update({
        "iteration": "iter1",
        "offset_y_m": 3000.0,
        "fov_horizontal_deg": fov1,
        "camera_pitch_deg": s1["pitch_deg"],
    })
    r1 = build(cfg1)
    if r1 is None:
        return 5
    d1 = report("1", cfg1, r1, concept)
    if r1.get("error"):
        # iter2 reads r1["measured"] below; an error dict has no such key and
        # would KeyError. report() already printed BUILD FAILED for iter1.
        print("\nITERATION 2 SKIPPED: iter1 build failed.")
        return 5

    # ---- ITERATION 2: FOV from the CHALET EXTENTS, not terrain bearings ---
    # AUTHORIZED 2026-08-30. iter1 still clipped one chalet because its FOV was
    # derived from the outermost recorded TERRAIN feature, and terrain is not
    # what was running off the edge of the frame.
    #
    # ⭐ THE DERIVATION IS ONE-SHOT, NOT ITERATIVE, and that is measured rather
    # than assumed: `chalet_edge_bearing_max_deg` came back 35.39 in BOTH
    # previous iterations, across a 60.0 -> 66.7 FOV change AND a 3000 m scene
    # offset. It is invariant because `concept_solve_camera.solve()` derives
    # only PITCH from the FOV -- camera XY never moves, and a horizontal
    # bearing depends on XY alone. So one pass fixes it exactly; a loop here
    # would converge on the first step and look like it had done work.
    #
    # EACH CONSTRAINT KEEPS ITS OWN MARGIN and the BINDING one wins:
    #   terrain features   0.95 of the half-width  (the existing fov delta)
    #   chalet edges       0.90 of the half-width  (the framing delta)
    # Taking the max satisfies both instead of trading one for the other.
    edge_max = r1["measured"].get("chalet_edge_bearing_max_deg")
    if edge_max is None:
        print("\nITERATION 2 SKIPPED: iter1 reported no chalet edge bearing.")
        return 5
    need_terrain = bmax / 0.95
    need_chalet = float(edge_max) / 0.90
    fov2 = round(2.0 * max(need_terrain, need_chalet), 1)
    binding = "chalet edges" if need_chalet >= need_terrain else "terrain"
    s2 = csc.solve(concept, fov2)
    cfg2 = dict(cfg1)
    cfg2.update({
        "iteration": "iter2",
        "offset_y_m": 6000.0,
        "fov_horizontal_deg": fov2,
        "camera_pitch_deg": s2["pitch_deg"],
    })
    r2 = build(cfg2)
    if r2 is None:
        return 5
    d2 = report("2", cfg2, r2, concept)
    print("")
    print("ITERATION 2 -- FOV DERIVED FROM CHALET EXTENTS")
    print("  terrain outermost %.2f deg / 0.95 -> needs half-width %.2f"
          % (bmax, need_terrain))
    print("  chalet edge max   %.2f deg / 0.90 -> needs half-width %.2f"
          % (float(edge_max), need_chalet))
    print("  BINDING: %s   fov %.1f -> %.1f deg" % (binding, fov1, fov2))
    print("  the edge bearing is FOV-INVARIANT (35.39 in iter0 AND iter1),")
    print("  so this is a one-shot correction, not a loop step.")

    print("")
    print("WHAT CHANGED BETWEEN THE ITERATIONS, and why each")
    print("  fov  %.1f -> %.1f deg   so the outermost recorded feature sits "
          "at 0.90" % (fov0, fov1))
    print("       of the half-width instead of exactly 1.00 on the boundary")
    print("  pitch %.3f -> %.3f deg  re-derived, because pitch depends on the"
          % (s0["pitch_deg"], s1["pitch_deg"]))
    print("       vertical FOV and the vertical FOV depends on the horizontal")
    print("  church: schema 1.1 SPLITS it -- nave 1.5x and spire 2.5x of the")
    print("       chalet silhouette. The old contradiction between the prose")
    print("       and height_class is GONE rather than averaged, so both")
    print("       iterations already carry the ruled shape.")

    with io.open(os.path.join(OUTDIR, "loop_v0.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"scope": {"measured_dimensions": MEASURED_DIMENSIONS,
                             "not_measured": NOT_MEASURED,
                             "_what_deltas_empty_means":
                                 "converged on the measured_dimensions "
                                 "listed here, and on nothing else"},
                   "iteration_0": {"cfg": base, "result": r0,
                                   "deltas": d0,
                                   "measured_dimensions": MEASURED_DIMENSIONS,
                                   "not_measured": NOT_MEASURED},
                   "iteration_1": {"cfg": cfg1, "result": r1,
                                   "deltas": d1,
                                   "measured_dimensions": MEASURED_DIMENSIONS,
                                   "not_measured": NOT_MEASURED},
                   "iteration_2": {"cfg": cfg2, "result": r2,
                                   "deltas": d2,
                                   "fov_derivation": {
                                       "terrain_bmax_deg": bmax,
                                       "terrain_margin": 0.95,
                                       "chalet_edge_max_deg": float(edge_max),
                                       "chalet_margin": 0.90,
                                       "binding": binding,
                                       "fov_deg": fov2,
                                       "one_shot_because":
                                           "chalet_edge_bearing_max_deg is "
                                           "FOV-invariant -- 35.39 measured "
                                           "in iter0 AND iter1 across a FOV "
                                           "and an offset change -- because "
                                           "solve() derives only pitch from "
                                           "FOV and camera XY never moves"},
                                   "measured_dimensions": MEASURED_DIMENSIONS,
                                   "not_measured": NOT_MEASURED}}, fh,
                  indent=1)
    print("")
    print("  wrote _verify/20260830_loop/loop_v0.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
