# APPROACHES.md — strategies tried, and why they lived or died

Every entry records the MECHANISM, not a parameter value. A strategy marked
DEAD is never retried without new evidence.

---

## A0 — INFRASTRUCTURE (not a styling strategy; the ground everything stands on)

**Status: LIVE.** Phase 0 gates all pass.

| gate | result |
|---|---|
| import | 94,408 curves, one CURVES object, identity transform |
| smoke render | strands render, Cycles GPU, ~23 s/view |
| export path | native `bpy.ops.wm.alembic_export` |
| round trip | curve drift **0.0%**, bbox drift **0.0026%**, attributes lost **none** |
| engine identity control | `moved_max_cm` **0.0** at default params |

**Frame, measured not assumed** (`recon/geometry.json`):
up = **−Y**, front (face) = **+Z**, head centre **(0, −1.52098, 0)**, scalp
radius ~0.105 m, scene in metres.

---

## A1 — DELETE-AND-REBUILD CULL OF DEGENERATE / STRAY CURVES

**Status: DEAD. Do not retry.**

**Mechanism:** build a keep-set, create a fresh `bpy.data.hair_curves`,
`add_curves(sizes)`, copy position/radius/curve_type element-wise, swap the
object.

**How it failed:** Blender terminated with `EXCEPTION_ACCESS_VIOLATION`
(crash dump `%TEMP%\iter_000.crash.txt`) on the first real run.

**Why, established rather than guessed:** `introspect_curves.py` against this
build shows `bpy.types.Curves` exposes **no** `add_curves`, `remove_curves` or
`resize_curves` (`recon/curves_api.json`). There is no supported in-place
curve removal in 5.2's Python API, so both the rebuild and any delete-loop
fallback are off the table.

**And it was never needed.** The premise was "UE asserts
CurveNumVertices >= 2". That note came from a different file. **This exact
`.abc`, with all 1,210 of its one-point curves, imported into UE earlier the
same day at its full 94,408 curves** — measured, not assumed.

**Replaced by:** `export_abc.census()` counts and declares the degenerates
instead of removing them, and runaway strays are bounded by the edit engine's
`stray_clamp_m`, which scales a long curve about its own root and therefore
**cannot change the curve count at all**. Same outcome, on a path that cannot
crash the tool.

---

## A2 — PROCEDURAL POINT TRANSFORM ON BÉZIER CONTROL POINTS + HANDLES

**Status: LIVE — this is the working edit engine.**

**Mechanism:** read `position`, `handle_left`, `handle_right` as flat numpy
arrays; build per-point context (curve id, `t` along strand, root); build
smooth per-curve region masks from the root's position on the scalp; apply a
single pure point-transform closure to **all three arrays with identical
context**, so a control point and its two handles move together and tangents
survive.

**Why this rather than geometry nodes:** headless GN needs a node tree
authored and wired from Python, which is a second program with its own failure
modes, and every op needed here is expressible as a point transform. Kept as
the first pivot candidate if this stalls.

**Why handles are not optional:** all 94,408 curves are `curve_type` 2
(Bézier) with absolute handle positions. Moving positions alone kinks every
strand at every control point.

**Cost:** 5.3 s for a full 375,774-point pass. That is the whole reason the
loop can be run overnight.

---

## A3 — PROXY HEAD FITTED TO THE ROOT CLOUD (instrument, not a styling strategy)

**Status: LIVE.**

The download shipped only the `.abc`; the grooming head exists in UE as
`SKM_MH_Groom_Head`. Bringing it across means a cm↔m and axis-convention
transform between two apps, and a wrong alignment would silently move every
landmark it is supposed to provide.

**Instead:** fit an ellipsoid to the strand ROOTS, which are already a
measurement of the scalp and are in the hair's own frame by construction. Add
two rulers — a brow band and ear markers — placed by declared human proportion
(brow = hairline + 5 cm; ear top = hairline + 3 cm).

**It is an instrument, not anatomy.** No report may quote it as a measured
face. It exists so "does the fringe reach the brow" is something you can SEE.

**Calibration note:** the first fit used p90 of |root − centre| and produced an
X radius of 5.9 cm — because this is a CENTRE PART, most roots sit near the
midline, so a low percentile measures the parting rather than the skull.
Moved to p97.

**Roots never move under the edit engine** (every op is anchored at `t=0`), so
the proxy is identical across iterations and the rulers stay put while the
hair changes. That is what makes iterations comparable.

---

## A4 — RIGID ROTATION ABOUT THE STRAND ROOT (replaces tip translation for direction)

**Status: LIVE, and the single biggest win of the run.**

**Mechanism:** rotate each strand's points about its own root by a per-curve
angle (Rodrigues, vectorised), constant along the strand so its authored
curvature is preserved exactly and only its direction changes.

**Why it was reached for:** every earlier attempt at the reference's
wind-blown direction used `global_sweep_x/z`, which TRANSLATES tips. A
translation drags tips away from the skull and uncovers scalp — measured, left
exposure 22.9% → 30.8% at 008 and 34.4% at 009. A rotation preserves every
point's distance from its root, so the hair keeps lying on the head.

**Result, single variable (016 vs 011):**

| | front | left | top | mean | cover% |
|---|---|---|---|---|---|
| 011 translation | 25.3 | 27.9 | 55.1 | 36.10 | 58.8 |
| 016 rotation | **24.0** | **22.6** | **50.8** | **32.49** | **61.9** |

016 beats the untouched source on *every* view including the left — the first
iteration to add direction without paying scalp for it.

**And they FIGHT.** 017 ran rotation and translation together and scored 36.92,
worse than rotation alone. The translation sweep is now held at zero.

---

## A5 — CULL DEGENERATE CURVES VIA `bpy.ops.curves.delete` (A1, REVIVED ON NEW EVIDENCE)

**Status: LIVE, and MANDATORY. This reverses A1.**

A1 marked the cull DEAD, arguing it was unnecessary because the source `.abc`
with all 1,210 one-point curves had already imported into UE at full count.
**That argument was about the VENDOR file.** Importing OUR re-export killed the
editor outright:

    Assertion failed: CurveNumVertices >= 2
    GroomBuilder.cpp:2403

New evidence, so the requirement is un-killed — the only sanctioned way to
revive a dead approach.

**Mechanism that works:** edit mode → `curves.set_selection_domain(CURVE)` →
write the `.selection` attribute → `bpy.ops.curves.delete()`. The operator
path, not a rebuild. A1's rebuild via `hair_curves.new` + `add_curves` remains
DEAD (it crashes Blender).

**It asserts its own result:** the count must drop by exactly the number found
and no curve may remain under 2 points. 94,408 → 93,198, removed 1,210, zero
remaining. **All attributes survive** — `position`, `radius`, `curve_type`,
both handle sets.

---

## A6 — EXPORT AT global_scale 100.0 (units conversion, measured not assumed)

**Status: LIVE for the UE-facing exports.**

An export at 1.0 lands in UE at **1/100 scale and at the world origin**.
Measured on the identity round-trip, so it is not caused by any edit:

| groom | z range (cm) | max_curve_length |
|---|---|---|
| vendor `SC_Hairstyle_Male_11` | 138.1 → 164.2 | 26.10 |
| GL_iter000 (untouched, exported at 1.0) | 0.75 → 2.71 | 1.57 |
| GL_iter020_ue (exported at 100.0) | 119.5 → 175.7 | 47.85 |

Blender writes raw metres; UE reads them as centimetres because the vendor
`.abc` carries unit metadata Blender's exporter does not write. Exporting at
100.0 puts the groom at head height where the vendor's sits.

**Both variants are shipped.** `iter_NNN.abc` is faithful to the source's own
numeric space; `iter_NNN_ue.abc` is pre-converted and needs no import-time
setting.

---

## A7 — CLAMP STRAND LENGTH TO THE VENDOR'S EXTENT

**Status: DEAD. Do not retry.**

**Mechanism:** tighten `stray_clamp_m` until our exported extent matches the
vendor file's 26 cm `max_curve_length`.

**How it failed:** iteration 022 at 0.125 m scored **59.68% mean scalp
visibility — the worst of the entire run** (front 43.5, left 51.8, top 83.7).
It cuts the strands that were doing the covering. Iterations 012/013 had
already shown the same effect at 0.20 m, less severely.

**Why it was wrong-headed:** the extent mismatch is a SYMPTOM of A8, not a
length problem. Clamping to hide it destroys the groom.

---

## A8 — THE INPUT ITSELF IS BEING MIS-READ BY BLENDER (open, and it is the headline)

**Status: ESTABLISHED, NOT FIXED. This is the blocker to hand to the morning.**

**The evidence, three independent facts pointing one way:**

1. **The same geometry measures differently in the two apps.** UE reads the
   vendor `.abc` as `max_curve_length` **26.10** and bounds spanning 26.1 cm.
   Blender imports that identical file and reports a max strand of **1.42 m**
   with a scene bbox Y of **2.52 m**. Round-tripping Blender's read back into
   UE reproduces Blender's numbers, not the vendor's.
2. **1,210 curves arrive in Blender with a single point.** A one-point curve is
   not a hair; it is a parse artefact. UE's own builder asserts against them.
3. **UE's own translator logged the mechanism**, earlier in this project's
   editor log:

       Ensure condition failed: GlobalKnotIndex + CurveNumKnots <= NumKnots
       AlembicHairTranslator.cpp:869

   A knot-indexing failure is exactly what produces some curves with too few
   points and others with runaway extents.

**Conclusion:** Blender's Alembic importer mis-parses this file's Bézier knot
data. Everything downstream is therefore corrupted-in / corrupted-out — the
final clamp bounds the damage and the candidates are usable, but they are not
faithful to the vendor geometry.

**This also explains, in one cause, three things chased separately:** the
degenerate curves (A5), the runaway strays that forced a clamp, and the extent
mismatch that A7 died trying to hide.

**What to try next, in order:**
1. Import the `.abc` into Blender via a different path and compare strand
   statistics against UE's 26.10 — the Groom Exporter addon may ship its own
   importer, and USD or a DCC round trip are alternatives.
2. If Blender cannot read the file faithfully, do the styling in UE instead —
   the groom is already imported there correctly and this project has a working
   UE-side binding pipeline.
3. Failing both, treat the Blender read as the authored source in its own
   right. The candidates already produced are self-consistent and import
   cleanly; they simply are not the vendor's exact strands.

---

## A9 — LOCK PARTITION FROM AUTHORED CURVE INDEX (from the escalation consult)

**Status: LIVE, and it produced the best candidates of the run.**

**Triggered properly:** scores sat at 40/50 for seven iterations, which is the
brief's escalation threshold, so a fresh-context agent was consulted with the
spec, this file, the log and recon.

**Its structural diagnosis, which was correct and which I had not articulated:**
every op in the edit engine has the form `f(root_position) x g(t)` — the field
is evaluated in ROOT space, never at the point's current position. So two
strands rooted 1 mm apart receive near-identical displacement at every `t`,
**forever**. A map smooth in root space CANNOT open a gap between them.
Clumping could only trade coverage, never create separation. That is precisely
why the groom kept reading as a dense uniform mass.

**The cheap probe it suggested, and the result:** does curve INDEX carry
authored structure? Measured by `index_probe.py` —

    consecutive-index roots   4.13 mm apart
    random pairs            125.0  mm apart
    ratio                     0.033
    ratio by stride  1:0.033  2:0.049  5:0.093  10:0.166
                    50:0.310  200:0.578  1000:0.780

**The exporter emitted curves patch by patch**, and the smooth decay with
stride is the signature of the artist's own guide grouping. So a block of
consecutive indices IS an authored, spatially coherent patch — a better lock
partition than any quantised grid, and free.

**Result.** Replacing lat/long cells with index blocks:

| | mean scalp | top | tip scatter |
|---|---|---|---|
| 021, lat/long | 34.70 | 51.2 | 0.524 |
| 024, block 120 | 31.48 | 45.3 | 0.565 |
| 026, block 60 | **29.03** | **41.2** | **0.585** |

and combining 026's locks with a stronger fringe gave **028 at mean 22.93%**,
roughly half the untouched source's 43.88%.

**Still unexplored from the same consult**, and the two best remaining ideas:
- **M1, iterated Eulerian lock field** — a POSITION-evaluated potential with
  separatrices, so nearby strands diverge under iteration. Move the
  `{position, handle_left, handle_right}` triple RIGIDLY by `F(position)` so
  tangents survive exactly.
- **M2, arc-length-conserving comb** — rotate each segment's direction toward a
  target field and re-integrate from the unchanged root using the ORIGINAL
  segment lengths. Total strand length conserved by construction, so it can
  re-route crown mass to the nape without the stretching that killed 022, and
  `stray_clamp` becomes unnecessary on that path.

**And its metric criticism, which stands:** `grade_ratio` compares nape-ROOTED
to crown-ROOTED strand length, but in a layered cut the collar-length hair at
the back is over-layer hair rooted much higher. The metric can therefore only
be satisfied by the mechanism 022 proved destructive. A tip-height profile —
median tip height binned by tip `fwd` — is the faithful ruler. Not built.

---

## A10 — SEATING A PACK GROOM ON THE HERO BY VERTICAL OFFSET

**Status: DEAD as stated. The offset is not the mechanism.**

**The hypothesis, and it was a reasonable one.** Measured in UE: the hero's face
mesh spans z 140.9-178.4, while this groom's ROOTS span 138.3-161.2 — about
17 cm low. A binding projects each root onto the nearest triangle of the
target, and from 17 cm below the scalp the nearest triangle is the JAW, which
is exactly the symptom every attempt has produced. So: raise the groom by the
measured difference before binding.

**Three configurations, all seated on the jaw:**

    identity binding, no offset       binds attempt 1, JAW
    identity binding, +12 cm offset   binds attempt 1, JAW (indistinguishable)
    source-transfer binding           binds attempt 1, JAW
      source = SKM_MH_Groom_Head, target = the hero's face mesh

**And a hard edge worth recording:** a **+17 cm** offset makes the binding
BUILD but the component REFUSES it — 4 attempts, while the hero's own binding
re-assigned on attempt 1 immediately afterwards as the positive control. The
+12 cm version assigns fine. So there is a threshold at which the offset
invalidates the binding, somewhere between 12 and 17 cm, presumably where roots
push past the mesh top (178.2 against a mesh top of 178.44).

**What this rules out.** Moving the groom's DATA does not move where a BOUND
groom sits. That is the useful negative: the binding's projection dominates the
authored position, so any fix that works by translating the groom is dead
before it starts. **The problem is correspondence, not placement.**

**What it also establishes, and this is progress.** Our Blender-exported,
x100-scaled, radius-corrected groom **binds and draws on the hero's own
MetaHuman component** — assignment on attempt 1, three different ways. Every
part of the pipeline now works except where the roots land.

**What to try next, in order:**
1. **Root UVs.** This groom has NONE (recon: only position, radius, curve_type,
   handles). The vendor MetaHuman grooms that seat correctly DO carry
   `groom_root_uv`. With no UVs the binding must fall back to positional
   projection, which is exactly the behaviour observed. Authoring root UVs
   against the HERO's scalp UV layout is the first real candidate, and
   `author_hero_hair.py` already writes that attribute for the hero's own
   grooms — the machinery exists.
2. **Author on the hero's head instead of retargeting to it.** The hero's own
   Blender grooms seat correctly because they were authored on his face mesh.
   Transplanting this cut's SHAPE onto strands rooted in the hero's scalp
   sidesteps correspondence entirely.
3. The MetaHuman groom pipeline's own retarget path, which R-GROOMBIND2/3
   partially reverse-engineered.
