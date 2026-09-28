# ⛔ SUPERSEDED — session report, superseded by STATE.md. History only, never a source.

# MORNING REPORT — overnight run 2026-08-18/19

## THE LANDSCAPE RENDER EXISTS

    _verify/20260819_hero_in_world/hero_wide_20260819T065430Z_b.png    <- lead
    _verify/20260819_hero_in_world/hero_portrait_20260819T065430Z_b.png
    _verify/20260819_hero_in_world/hero_env_20260819T065430Z_b.png

The hero stands in the Alpine8K forest, facing camera, textured, lit by the
low alpine sun, ground-clamped by line trace at z 31019.47 with 256 landscape
proxies resident. Pose verified by the project's own acceptance test —
**head 160.6 cm above root** (a collapsed reference skeleton reads ~6 cm).
Components present: Body, Face, and groom components Hair / Eyebrows /
Mustache / Beard with their assets resolved.

**WHICH STATE IS IN THAT PICTURE, PLAINLY:** it is
`MHC_AlpineHero_Scratch2` — an expendable duplicate carrying the converged
shape (residual 0.1668 cm), assembled OPTIMIZED/HIGH. **The working character
`MHC_AlpineHero` was never written tonight** and is byte-identical to its
backup (`78f8c8d2…`), as is the master (`13ec8deb…`).

**WHAT IS WRONG WITH THE PICTURE, equally plainly:** he is in default
undergarments (wardrobe was never in scope), he is bald and no beard or brow
reads even in the close portrait, and the frames are **not fully settled** —
17–23% of pixels still move between two captures 60 warm-up frames apart, so
virtual texture streaming had not converged. The image is honest about what it
is: best available, not a finished beauty shot.

**AND ONE THING THE PORTRAIT SAYS THAT NO NUMBER TONIGHT SAID:** the assembled
BODY reads androgynous — the chest and shoulder line do not read as the
masculine build the working character was configured for
(`Masculine/Feminine` −2.0, recorded 2026-08-16). Nothing tonight touched that
constraint; the only body write was Height 178.196 → 182.0 → restored, as a
lock falsifier. So either the setting did not survive into
`MHC_AlpineHero_Scratch2`, or it does not survive assembly, or it never
reached the mesh in the first place — this project has a recorded instance of
exactly that third case, where a ±2.0 `Masculine/Feminine` swing produced
byte-identical body bounds INCLUDING the baseline. **UNDIAGNOSED, and it is
the first thing a face-focused night would fail to notice.** The face was
measured to 0.0007 cm and nobody was measuring his shoulders.

---

## THE MAP — every mechanism and caveat measured tonight

1. **`import_whole_rig=True` is exact application, and it reproduces.** An
   import of the UNEDITED canonical DNA returns the parametric face to within
   **0.005 cm on every named measure** — an order below the noise floor.
   Render delta 1.05x floor.
2. **The parametric path's ceiling is the fitter, not edited geometry.** Floor
   at an edited state: whole-rig **0.056 cm** (depth 1), **0.094 cm**
   (depth 2), against the fit path's **0.27 cm** and a REFUSAL. Depth 2 is
   1.13x the whole-rig canonical floor.
3. **There is no accumulation penalty in the measured range.** Same jaw mask:
   depth 1 delivers 0.58, depth 2 (chained onto the chin edit) delivers 0.70.
   Chaining RAISED delivery.
4. **Delivery is direction- and amplitude-dependent.** Same jaw mask:
   +1.000/side gives 1.16 cm of width per side-cm; −0.729 gives 2.60; −0.302
   gives 3.20; −0.245 gives 4.53. A landmark on the silhouette does not move
   with the local vertex.
5. **The fitted regions are COUPLED — a Jacobian, not four gains.** Iteration 3
   reduced the jaw narrowing command and the jaw came out NARROWER, because
   the cheek and temple widening propping that landmark out was reduced in the
   same step.
6. **A mask must reach the landmark it drives.** The manifest's `temple_width`
   box (Y 171–177) sits on the CROWN: 446 weighted vertices, 0.16 cm of width
   per side-cm. Re-aimed to Y 163–172 it selects 3194 (2045 core) and delivers
   **1.03** — 6.4x. A mask that misses reads as a region that resists.
7. **Rebuild the edit chain from canonical every iteration.** Whole-rig
   replaces rather than adds, so a mis-estimated ratio re-aims the whole move.
   Iteration 1 overshot to worse-than-canonical and cost nothing.
8. **`compare_face_state` is USELESS on a whole-rig character.** Its "gold
   data" is character 2 of the comparison
   (`MetaHumanCharacterEditorSubsystem.cpp:2567`), so the Error line on every
   import is OUR OWN diagnostic. The value is a **constant 18.1982937 at
   vertex 7** across identity, depth 1, depth 2 and jaw-only — including the
   import that reproduced the face to 0.005 cm.
9. **`reload_packages` (`--restore`) FATALS THIS EDITOR.** Twice tonight,
   `EXCEPTION_ACCESS_VIOLATION reading 0x470` seconds after
   `LogUObjectGlobals: Reloading 1 Package(s)` — once on a whole-rig character
   and once on the master, which had **never** taken a whole-rig import. So
   whole-rig is NOT the discriminating variable.
10. **The undo is a closed-editor disk restore, and it is now PROVEN:**
    converged 0.1668 cm → damaged 1.2531 cm → restored **0.1661 cm**, with the
    damaged arm as the discriminating control. Bytes are not the proof; the
    re-render is.
11. **The assemble and its save are ONE operation.** `build_meta_human`
    leaves every package dirty, and twice tonight the editor stopped answering
    remote execution immediately afterwards (one core spinning, working set
    flat, **zero log growth**) — so a second call to save could never be
    delivered and 91 freshly built packages died with the process. Saving
    inside the same payload landed 83 of 89.
12. **Assemble and render belong in different editor sessions.** The
    post-assemble editor never recovered; a fresh one placed and rendered
    without trouble.
13. **Virtual textures need FRAMES, not flags.** With
    `r.Streaming.FullyLoadUsedTextures 1` set, the first in-world pass still
    rendered the skin as mip-tile patchwork and the canopy as unresolved VT
    tiles. 300 warm-up captures fixed the look; two captures 60 frames apart
    still differ by 17–23% of pixels, so it is converging, not converged.
14. **Body parameters still write after three whole-rig imports.** Height
    178.196 → 182.0 TOOK on both a never-imported control and the whole-rig
    scratch. **The advertised permanent body-type lock has not been observed
    on any surface we can read** (`fixed_body_type` reads False on all three
    characters).
15. **UE struct Arrays iterate as COPIES.** Mutating the loop variable and
    passing the same list back changes nothing and the setter reports success
    — which looked exactly like the lock in (14). Rebuild the array by index.
    Same trap this project hit on `Masculine/Feminine`.
16. **Eye colour: the durable asset surface did NOT reach the render.**
    `eyes_settings.eye_*.iris.global_tint/global_saturation` written and read
    back off the asset (1.0→0.15/0.13/0.12, sat 1.7→0.4), `commit_eyes_settings`
    called, preview re-assembled — and the iris measured **(212.9, 137.8,
    34.0)** against **(213.9, 139.4, 34.3)** before. Unchanged. The reference
    iris measures **(26, 20, 17)**; ours is amber. UNSOLVED.
17. **The MetaHuman Blueprint's forward axis is not +X.** A look-at yaw of 180
    photographed his profile; **−90 from the look-at** faces him at the camera.
18. **`--set` values starting with `/Game/` are rewritten by Git Bash** unless
    `MSYS_NO_PATHCONV=1`; `load_asset` then returns None and it reads as a
    missing asset.
19. **`ue_exec --timeout` is a DISCOVERY window spent in full**, not an
    execution budget. A 180 s value inside a 120 s shell timeout killed the
    client before the payload was ever sent, and read as "the operation
    failed".
20. **The stage framing search is deterministic**: rebuilt after a restart it
    returned a bit-identical camera (distance 84.087153), so cross-session cm
    comparisons hold.

---

## THE SHAPE RESULT

    iter 1   1.8308 cm   OVERSHOT, worse than canonical
    iter 2   0.7260
    iter 3   0.5245
    iter 4   0.4122
    iter 5   0.1668      chin +0.016  jaw +0.001  cheek +0.098  temple +0.052

**89% of the canonical residual closed, all four fitted regions inside the
0.15 cm deadband**, every capture settled, every render coherent — no seams,
no faceting. Chain, boxes, deltas and the final DNA hash (`7c3a0dc6…`) are in
`_verify/hero_likeness/shape_chain_converged.json`, replayable onto the
working character in minutes once the lock is ratified.

**AND THE HONEST HALF: the metric converging is not the likeness converging.**
`brow_height` finishes at **−0.5730 cm**, the largest single residual on the
board, and is unaddressable frontally — its landmark sits in the eye band,
which is the ruler, and the reference's brow shelf is substantially a shadow.
The rendered face is coherent and still smooth, young and round-ish against a
weathered 40s reference. Widths at three heights plus a chin drop cannot
express age, brow, skin or iris.

---

## PER-TRACK STATUS

| Track | State |
|---|---|
| 1. Accumulation test | **DONE.** Depth 2 passes on floor; no depth penalty. |
| 2. THE LOCK | **HELD by advisor ruling.** Not performed. Gates 1–3 now met. |
| 3. Post-lock identity | Not reached (depends on 2). |
| 4. B-FITCOHERENCE | **NOT DONE.** No jaw-open render. Teeth are untouched in the DNA by construction, so the question is real and open. |
| 5. Shape loop | **DONE on scratch**, converged 0.1668 cm. |
| 6a. Eye colour | **ATTEMPTED, FAILED.** Asset property took; render did not move. |
| 6b. Hair | **NOT ATTEMPTED** — the night went to the lock evidence and the landscape. B-HAIRGROOM unchanged. |
| 6c. Landscape placement | **DONE.** Renders above. |
| 6d. Retarget | Not reached. |

## RESIDUAL TABLE (converged state, cm, against the SHAPE reference)

    chin_height   +0.0162      brow_height  -0.5730   UNADDRESSABLE
    jaw_width     +0.0013      nose_bridge  +0.1745   UNADDRESSABLE
    cheek_width   +0.0977      eye_spacing  -0.0008
    temple_width  +0.0516      TOTAL (4 fitted)  0.1668

## COMMITS

    7401edf9  The shape loop converges on the whole-rig path: 1.5382 -> 0.1668 cm
    (earlier) The whole-rig arm holds its own ruler: 0.056 cm at a 2 cm edited state
    (earlier) Depth 2 holds the floor; the jaw ratio needs its mask; --restore fatals
    (earlier) The gold-data error is our own compare_face_state; advisor holds the lock
    (earlier) The lock's missing falsifier now exists: disk restore proven, 0.0007 cm

## ADVISOR

One consultation, logged in `ADVISOR_LOG.md`. **Load-bearing: it reversed the
pre-authorized next action.** It held the lock on three grounds — the letter
of the gate had failed and re-reading a bar is the moved-bar pattern; the
pre-authorisation's risk map was stale by three findings made after it was
written; and the marginal value of locking at 5am was near zero because the
edit chain replays in minutes. It also spotted the gold-data error in an
artefact I had already committed without asking whether it fired on THIS
import. Two of its three grounds are now closed by measurement (items 8 and
10 above).

## THE SINGLE RECOMMENDED NEXT RULING

**Ratify the ratio bar as per-(region × mask) and authorise the lock**, or
decline it. Everything else is ready: the shape chain replays deterministically
onto the working character, the disk-restore undo is proven on the same asset
class, the gold-data error is explained, backups are hash-recorded at
`_trash/hero_likeness_backups/20260819T052015Z/`, and the `--restore` guard is
live. The remaining gates are (4) post-lock identity within floor and (5)
working-character ratios matching the scratch gain table — both mechanical
once you say go.

**Second, cheaper ruling if you want a visible win first:** eye colour is one
parameter and currently does not reach the render (item 16). It is the largest
appearance gap after grooming and it does not touch geometry, so the ceiling
does not apply.
