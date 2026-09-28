# Church reference images — the view spec TRELLIS actually needs

**Every number here is measured, not preferred.** The floor comes from
TRELLIS's own known-good example (which produced a volumetric mesh) against the
crop that failed (which produced a flat sheet).

## THE EVIDENCE THE SPEC IS DERIVED FROM

| | subject pixels | subject vs frame | result | thin/long |
|---|---|---|---|---|
| **castle** (TRELLIS's own example, 704×704) | **183,353** opaque, bbox 545×625 | **89%** of frame height | volumetric | **0.849** |
| **church crop** (80×115 from the concept) | ~3,700 opaque | ~0.9% of the concept | **flat sheet** | **0.0114** |

**A 50× gap in subject pixels.** Upscaling did not help and cannot: a 4.5×
LANCZOS enlargement adds no information, so the model had nothing to infer
depth from and returned a relief on a plane.

---

## THE SPEC

### 1. Count and angles

**Four views**, azimuth **0° / 90° / 180° / 270°**, elevation **+15° to +20°**
(slightly above eye, looking gently down).

- TRELLIS ships `example_multi_image.py`, so multiple views are supported and
  give markedly better consistency on a subject with a distinctive silhouette
  like an onion dome.
- **If only one image is possible**, make it a **3/4 view — azimuth 30–45° off
  the main facade**, elevation +15°. A straight-on elevation is the worst
  single choice: it gives the model no depth cue at all, which is exactly the
  failure mode we already hit.
- Keep **the same distance and focal length across all four** so the building
  is the same size in each. Varying scale between views is a reconstruction
  hazard, not a stylistic choice.

### 2. Subject size — the hard floor

    subject longest dimension   >= 800 px in the delivered image
    opaque subject pixels       >= 150,000
    delivered frame             >= 1024 x 1024

**Why those numbers.** TRELLIS preprocesses internally to **518×518**. The
castle's subject spans 625 of 704 px, so after that resize it still spans ~460
px. An 800 px subject in a 1024 frame lands at ~405 px after the resize —
comfortably in the working range, with no upscaling anywhere in the chain.

**The 150,000 floor is 40× the failed case.** 9,200 px cannot happen again if
the subject simply fills the frame.

### 3. Framing

- **The building fills 80–90% of the frame's shorter dimension.** Not a wide
  shot with a church in it — a portrait *of* the church.
- **Centred**, with ~5% margin all round. Nothing clipped: ground line at the
  bottom, **finial tip inside the frame** at the top.
- **Square or near-square** (1:1). TRELLIS's own examples are square and its
  preprocessing is square; a 16:9 frame wastes half the pixels on sky.
- Whole building in every view — no crops of just the tower.

### 4. Background

- **Plain and uniform.** Flat neutral grey, white, or transparent. TRELLIS runs
  background removal, and a clean background is what makes that reliable.
- **Nothing overlapping the silhouette** — no trees, no neighbouring roofs, no
  foreground grass crossing the outline. The failed crop had another building's
  roof cutting its lower edge.
- **No strong cast shadow crossing the outline**, which reads as geometry.

### 5. Lighting

- **Flat and even.** Soft, near-shadowless, slightly frontal.
- **Avoid the concept art's lighting deliberately.** That image is a low-sun
  backlit shot with 5.5:1 contrast and god rays — beautiful, and exactly wrong
  here: deep shadow bakes shading into what the model reads as albedo, and
  silhouettes vanish into the dark side.
- No motion blur, no depth of field, no atmospheric haze.

### 6. What to include in the subject

The concept records the church as *"pale tower, dark bulbous onion dome,
finial"* — the only vertical accent in the village. **Include the full vertical
run**: base, nave, tower shaft, dome, finial. If the nave is part of the
building, include it — per the 2026-08-30 ruling the nave and spire are now
**separate entities at 1.5× and ~2.5× house height**, and the reference should
show both so their proportion is readable.

---

## DELIVERY

Anywhere convenient; I will copy them into the repo rather than work in place.
PNG preferred (lossless — JPEG ringing around a high-contrast silhouette hurts
background removal). Name them so the angle is unambiguous, e.g.
`church_az000.png`, `church_az090.png`, `church_az180.png`, `church_az270.png`.

**A validator is committed**: `scripts/check_generation_input.py` measures any
candidate against every number above and refuses with the specific figure that
failed. Run it on the images before sending if you like, or I will on receipt —
either way nothing reaches the model unmeasured.

---

# ⭐ AMENDED AND RENAMED 2026-08-30 — FLOORS APPLY PER **SET**

**Formerly `CHURCH_VIEW_SPEC.md`.** Renamed because it is general now: it
governs every generation input, not the church. References to the old name in
dated evidence (`BAKEOFF.md`, `MULTIVIEW_RESULT.md`) are left as they were —
rewriting a path inside a record falsifies what was true when it was written.

## THE RULING

**For a CONSTANT-DISTANCE multi-view set, the floors apply per SET, not per
image.**

The 800 px and fill-low floors were derived to guarantee **information
density** against an 80×115 crop carrying ~3,700 subject pixels. **Rotating a
subject at constant distance shrinks its projected extent without losing
density** — and the subject-pixel count proves it directly. Applying an extent
floor to a rotation measures the subject's SHAPE, not the input's quality.

    MASTER (derived: the max-extent view)   every floor, unchanged
      longest >= 800   subject >= 150,000   frame >= 1024   fill 0.55-0.97
      aspect <= 1.35

    ROTATIONS in the same set
      subject >= 150,000      frame >= 1024
      fill-HIGH (clipping)    aspect
      + bbox HEIGHT within +-8% of the master's
      NOT longest-side.  NOT fill-low.

    SINGLE IMAGE                            every floor, unchanged
      there is no master to inherit from, so nothing can be relaxed.

**The master is DERIVED, never declared** — the largest subject extent. A set
must not be passable by nominating its weakest image as the reference.

Run it: `python scripts/check_generation_input.py --set <images...>`

## THE CASE THIS CAME FROM

The wood-stack set. Two views fell under the 800 px floor on **width alone**:

    view    subject px   bbox      longest   verdict per-image
    az000     474,563    908x661     908     ok
    az035     491,707    908x709     908     ok   <- master
    az090     328,831    751x648     751     REFUSED
    az180     358,531    785x656     785     REFUSED

The stack's **height is 633–693 px in every view** — azimuth does not change
height — while its **width swings 908 → 733** rotating end-on. The floor bound
on width alone and height could never rescue it, because a woodpile is low and
wide.

**The church passed all four only because it is TALL** (longest ≥872 px in
every view), so no rotation could drop it under. Its clean pass HID the
interaction, which is why this was not found until the second asset.

## ⭐ THE CONSISTENCY GATE IS THE **GROUND LINE**, AND WHY HEIGHT WAS DEMOTED

**Ruled 2026-08-30 (option 1), after the first implementation refused an
honest set.**

    GATE        rotation GROUND LINE within +-3% of the master's
    SECONDARY   rotation bbox HEIGHT within +-15%, REPORTED ALWAYS,
                gating only when the ground line has ALSO failed

### THE EVIDENCE, FROM THE WOOD-STACK SET

    ground line (bbox bottom)  889, 890, 880, 889   spread  1.1%
    top edge                   229, 182, 233, 234   spread 22.5%
    bbox height                661, 709, 648, 656   spread  9.3%

**The camera demonstrably did not move** — the ground line is constant to
1.1%. The height still varied 9.3%, because the 35° silhouette is genuinely
taller: `az035`'s top sits at y=182 against 229/233/234, over the same ground
line. At ±8% on height the gate refused `az090` at 8.6% — **a false positive
on a set whose camera was fixed.**

### WHY THE GROUND LINE IS THE RIGHT QUANTITY

bbox height mixes two things: the signal (the camera moved) and the noise
(the silhouette changed with azimuth). It cannot separate them, so any
tolerance either admits real camera moves or refuses honest rotations.

The ground line does separate them. **A distance or elevation change shifts it
and rescales the whole bbox; a change of azimuth leaves the subject standing
where it stands.** It measures the thing the rule was always about.

### WHY HEIGHT IS RETAINED AT ALL

To catch a generator that **rescaled the object while holding the ground
line** — a case the ground line alone would miss. Height is therefore reported
on every rotation and cited alongside a ground-line failure as corroboration,
but never gates by itself, because honest silhouette variation lands in
exactly the same place.

### PROVEN IN THREE DIRECTIONS

`check_generation_input.py --self-test`, against the REAL wood-stack set:

    passed    master wood_stack_az035.png, at full floors
    passed    3 rotations under set rules
    REFUSED   a rotation composited FURTHER AWAY (0.75x about the frame
              centre) -- GROUND LINE at y=792, 11.0% off the master's y=890

The refusal fixture composites **only the subject's pixels**, scaled about the
frame centre, which is what moving a camera back actually does to a
projection. An earlier version pasted a scaled copy of the whole frame; the
mask locked onto the paste seam, the fake measured a 0.6% ground delta, and
the test reported a pass over a control it was never exercising.
