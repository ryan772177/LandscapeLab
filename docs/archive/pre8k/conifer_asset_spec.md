> # ⛔ SUPERSEDED — describes the pre-8K / pre-kit design. Do not apply.
>
> Quarantined 2026-08-29 by the doc-consolidation unit. **Nothing in this
> file may drive a decision.** It is kept verbatim because this project
> never deletes a record; the content below the banner is byte-identical to
> what it was before the move.
>
> **Why it is dead — because it SUCCEEDED.** This is the acceptance spec for
> replacing `fir_tree_01`, ruled 2026-08-13.
>
> **The purchase was made.** 2026-08-15 adopted `SM_PVE_Norway_Spruce_01_A`
> (29.31 m Nanite, real needle geometry) in place of `fir_tree_01_c_LOD0`,
> and the forest was re-scattered to 219,659 instances across four tiers.
> Archived as **completed**, not as wrong.
>
> *Moved from its original path by `git mv`, so `git log --follow` still
> reaches its whole history.*

---

# CONIFER ASSET SPEC — what to buy on Fab, and why

**Purpose.** `fir_tree_01` is the measured weak point of every alpine render
this project has produced. This is the acceptance spec for its replacement,
written so the asset can be judged ON THE STORE PAGE before money is spent, and
re-judged by measurement after it arrives.

Ruled 2026-08-13: source a better conifer from Fab.

---

## 1. WHY WE ARE REPLACING IT — measured, not an opinion

| Property | `fir_tree_01` | Why it fails |
|---|---|---|
| Twig atlas opaque coverage | **24.02%** | Canopy reads as bare poles. Three quarters of every foliage card is empty. |
| Alpha character | **effectively BINARY** — 25.06% at clip 0.1 vs 23.56% at 0.5 | **The opacity threshold is NOT the lever.** Moving it buys ~1.5%. This cannot be fixed in the material. |
| Needle albedo (where opaque) | mean RGB **85 / 81 / 49** | Dark olive-brown with **green BELOW red**. Alpine conifers read cool green; this reads dead. |
| Height (`_c` variant, the one used) | **14.52 m** | A young fir. Mature alpine spruce is 20–35 m. |
| Canopy radius | **3.068 m** | Narrow, consistent with a young tree. |
| LOD0 triangles | **505,494** | Heavy for what it delivers. |
| Provenance | **UNRECORDED** in `ASSETS.md` — predates R-ASSET | Licence and source unknown. Replacing it closes a register gap too. |

**The verdict that matters:** at 157,554 instances this reads as *scrub, not an
alpine forest*, and the record explicitly warns not to fix it in the material
before deciding whether the ASSET is the answer. It is the answer.

**One thing it is NOT:** this is not an LOD problem. A foreground tree at ~5 m
is as bare as the distant ones — that was checked.

---

## 2. HARD REQUIREMENTS — reject the asset if any of these fail

1. **Species.** An alpine conifer: Norway spruce (*Picea abies*), Silver fir
   (*Abies alba*), Subalpine fir (*Abies lasiocarpa*), Engelmann spruce, or
   European larch. Spire-shaped mature crown, not a rounded ornamental.
2. **Maturity.** Supplied heights reaching **18–35 m**. If every variant is
   under 15 m it is the same problem we already have.
3. **CANOPY DENSITY — the single most important criterion.** The foliage atlas
   must be visibly dense, or the branches must carry enough card geometry that
   density comes from the mesh. **Target ≥ 45% opaque coverage** against our
   24.02%. On a store page, judge this from the *unlit wireframe/foliage
   close-up shots*, not the beauty render — a beauty render at distance hides
   exactly this defect.
4. **Needle colour: green must exceed red.** Ours is 85/81/49. Reject
   yellow-brown or olive-dominant needle atlases.
5. **LODs supplied: at least 4**, ideally with a billboard/imposter for
   distance. We cull at 730 m today and imposters are on the backlog.
6. **Pivot at the trunk base, centred in XY.** This project has a documented
   pivot-offset defect class; a `vegetation_debris` asset was REFUSED for a
   0.419 m horizontal pivot offset. A tree whose pivot is at the bounding-box
   centre buries half of it by construction.
7. **Separate material slots for bark and foliage.** Non-negotiable here:
   `M_fir_bark` was once built without `--slot` and `texture_map` silently
   last-wins on a contested role, so trunks rendered the TWIG atlas. Distinct,
   clearly named slots make that class of bug detectable.
8. **Textures 4K minimum, 8K preferred** given the 8K direction: albedo,
   normal, roughness, opacity. **8-bit sRGB albedo and 8-bit normal.** A 16-bit
   single-channel map hits a documented import trap in this pipeline
   (`scripts/texture_16bit.py`) and needs conversion before import.
9. **Licence: Fab standard, usable in a commercial game.** It gets an
   `ASSETS.md` row with source, licence, role and render proof — no asset
   without a row.
10. **Format: FBX preferred** (it goes through `scripts/blender/` normalisation
    and `measure_rock_meshes.py`-class intake). A UAsset-only drop is usable
    but skips our normalisation.

---

## 3. STRONGLY PREFERRED, not disqualifying

- **3–5 distinct variants.** Repetition across 157,554 instances is visible.
  (Note: the current pack ships 3 and we use exactly 1 — budget for that.)
- **Wind / pivot-painter vertex colours** for canopy motion.
- **LOD0 under ~200k triangles.** Ours is 505,494 and the whole canopy is worth
  less than that suggests.
- **A snow-dusted or winter variant** — this is a snow-line alpine scene.
- **Nanite-ready.** Note the caveat: alpha-tested foliage under Nanite has
  trade-offs, and the project's standing ruling is that Nanite stays OFF on
  vendor foliage meshes (they are gitignored, so the flag vanishes on
  re-download).

---

## 4. BUDGET CONTEXT — hand these numbers to the decision

    current placement    157,554 conifers at 68.0 / hectare
    current cull         730 m
    current LOD chain    505,494 / 126,374 / 22,293 / 3,892
    worst-case load      39.6M triangles in the cull disc
    8129 scatter budget  250,000 instance ceiling

**Worst-case load is density x cull-disc area — a LOCAL quantity**, so a denser
tree does not scale cost by the instance count; it scales by what is inside the
cull disc. A 200k-triangle LOD0 with a genuinely dense canopy is a better buy
than a 505k one that reads as scrub.

---

## 5. HOW IT GETS VERIFIED WHEN IT ARRIVES — decided in advance

So the purchase is judged by the same instruments that condemned the incumbent,
not by a fresh impression:

1. **Alpha coverage on the foliage atlas** — the exact measurement that gives
   24.02% today. Acceptance: **≥ 45%**, and report the clip-0.1-vs-0.5 spread
   so "is it binary?" is answered rather than assumed.
2. **Needle albedo patch mean where opaque.** Acceptance: **G > R**.
3. **Mesh intake** — triangles per LOD, real LOD screen sizes, pivot offset,
   dimensions. Vendor LOD screen sizes have been wrong before
   (`boulder_medium_01` shipped 1.504 / 0.752 / 0.319 / 0.238 against an assumed
   1.0 / 0.5 / 0.21 / 0.088), so they get measured, not read off the store page.
4. **Render A/B at fixed stations** against the incumbent, single variable,
   same exposure. `forest_floor` and a near/far LOD pair are the discriminating
   cameras. **Edge energy is the metric, not mae** — mae cannot tell sharper
   from differently blurry.
5. **`ASSETS.md` row** with source, licence, role and the render proof.

**And one honest note on the exposure:** frames captured before 2026-08-13's
exposure re-solve sit at `-1.786` EV; the scene is now `-1.867`. Any A/B against
older canopy frames must account for 0.08 EV, or be re-shot.

---

## 6. WHAT I CANNOT DO FOR YOU HERE

I cannot browse Fab, verify a licence, or judge a specific product's atlas from
its store page — so **no specific product is recommended in this document.**
The criteria above are written to be checkable by you on the page. If you paste
me a candidate's spec sheet or screenshots I can check it against section 2
line by line, and once the files are on disk every number in section 5 is
measurable.
