# BRIEF 1 — Distance is an angle: culls, LODs, proxies and the moving-camera instrument

Status: RESEARCH, with three tested tools and one draft procedure. Nothing here has touched the editor. Numbers marked DERIVED come from the tools in `scripts/`; numbers marked LITERATURE carry a source; anything marked VERIFY needs Claude Code to confirm against engine source per `docs/ue58-api-protocol.md`.

Scope: the mainline (`recipes/alpine_8k.json`, `/Game/Alpine8K`). The forge is out of scope for this brief.

---

## 0a. Ruling 2026-09-05: the judgement camera is 4K

Ryan ruled: derive at **3840×2160 / 90°** (43 px/deg, the highest resolution the eye still resolves at this FOV); check at 2560×1440 as the floor; 8K captures are an inspection tool, not a camera. Both columns below; the 4K column is the one the recipe derives from.

| species | height m | authored cull m | px at cull (1440p / 4K) | detail m (1440p / 4K) | silhouette m | vanish m |
|---|---|---|---|---|---|---|
| Conifer | 14.7 | 730.0 | 26 / 39 | 470 / 706 | 3136 / 4704 | 12544 / 18816 |
| SpruceSub | 9.0 | 730.0 | 16 / 24 | 288 / 432 | 1920 / 2880 | 7680 / 11520 |
| SpruceSapling | 4.0 | 180.0 | 28 / 43 | 128 / 192 | 853 / 1280 | 3413 / 5120 |
| Blueberry | 0.6 | 45.0 | 17 / 26 | 19 / 29 | 128 / 192 | 512 / 768 |
| Meadow | 0.4 | 50.0 | 10 / 15 | 13 / 19 | 85 / 128 | 341 / 512 |
| Boulder | 2.5 | 140.0 | 23 / 34 | 80 / 120 | 533 / 800 | 2133 / 3200 |

Every distance in §4's ladder scales ×1.5 at 4K. The design conclusion is unchanged and stronger: no tree-sized object can be culled to nothing inside an 8 km world.

## 0. The finding in one paragraph

Every foliage cull distance in `alpine_8k.json` removes an object while it is still 10–28 pixels tall at the declared render camera (90° horizontal, 2560×1440). DERIVED, `angular_budget.py`: conifer 25.8 px at 730 m, sapling 28.4 px at 180 m, boulder 22.9 px at 140 m, blueberry 17.1 px at 45 m, meadow grass 10.2 px at 50 m. The threshold below which a human cannot report an object vanishing is about 1.5 px; the threshold below which it stops reading as a *shape* is about 6 px (LITERATURE, §2). So every cull in the recipe is a visible pop, and the lesson entries about "could not measure the pop" were measuring the right defect with the wrong instrument. The 14.7 m spruce does not fall under the 6 px silhouette threshold until **3.1 km**, and under the 1.5 px vanish threshold until **12.5 km** — beyond the world's edge. The conclusion is not "raise the cull to 3 km." It is: **trees in this world must never be culled to nothing; they must be handed to a cheaper representation**, and the hand-off point is a pixel size, not a distance.

---

## 1. What the eye does (LITERATURE)

The engineering facts, chosen because each one sets a number in a recipe.

**Acuity is angular.** Standard acuity (Snellen 20/20) resolves ~1 arcminute of detail at high contrast. The finest grating a healthy adult sees at photopic luminance is ~50–60 cycles/degree; practical acuity for real scenes is 30 cpd. (Campbell & Robson 1968; Barten 1999, *Contrast Sensitivity of the Human Eye and Its Effects on Image Quality*.)

**Sensitivity peaks at coarse detail.** The contrast sensitivity function is band-pass: peak ~3–5 cpd, falling on both sides. A detail at 1 cpd needs ~3× the contrast of one at 4 cpd to be seen; at 30 cpd it needs full contrast. This is why texture *tiling* (a repeat at 2–8 cpd on screen) is so visible, and why sub-pixel geometry is not.

**Contrast threshold is a fraction, not an amount.** Weber's law: a luminance step is at threshold near ΔL/L ≈ 1–2% for a large patch at photopic levels, rising for small or brief patches. A LOD switch that changes the mean brightness of a 20 px patch by 3% is seen; by 1% it is not.

**Temporal sensitivity peaks near 5–10 Hz and dies by ~50–60 Hz** (flicker fusion). A change that completes in one frame at 60 fps is a step, maximally visible; the same change spread over 20–30 frames (0.3–0.5 s) sits below the temporal CSF for most of its energy. This is the whole justification for dithered LOD cross-fades: they move the switch's energy out of the band the eye watches.

**Masking.** Threshold rises when the change sits on a textured background of similar spatial frequency. Popping in a dense canopy is less visible than popping of a lone tree against sky — so the *acceptance* for a change should be scored against its surround, which `temporal_stability.py` approximates by normalising to local luminance and ignoring blobs under 12 px.

**The player is not looking at everything.** Foveal acuity holds within ~2° of fixation; at 10° eccentricity acuity is roughly a quarter. A still frame is judged foveally everywhere (the reviewer scans it); a *player* judges the centre and notices *motion* in the periphery — which is exactly what a pop is. Peripheral motion detection is why pops feel worse in play than they look in a screenshot.

**Depth from atmosphere.** Contrast falling with distance is a primary depth cue (aerial perspective). A far ridge rendered at near-field contrast reads as *close* and *small*. This is not a Brief 1 number but it is why the far-ridge finding in the rear station (BRIEF 2, atmosphere) matters for the world reading large.

---

## 2. The three thresholds, and where they come from

| threshold | px (at render) | basis |
|---|---|---|
| **vanish** | 1.5 | Below ~1.5 px an object is under the render's own Nyquist limit and is averaged into its neighbours by the display and by TSR; removing it changes a single pixel's value by less than the JND in nearly all cases. |
| **silhouette** | 6 | The CSF peak is ~4 cpd; an object needs ~2–3 cycles across its height to be seen as a shape rather than a blob — 4–6 px. Below this, a flat-shaded blob of the right colour and coverage is indistinguishable from the mesh (the basis for HLOD "approximated mesh" and imposters). |
| **detail** | 40 | ~1 arcmin acuity over a 40 arcmin object gives ~40 resolvable lines; above this the eye sees internal structure (branch layers, trunk gap, shadow under the canopy). This is where LOD0/LOD1, real shadows and wind matter. |

Render pixel angular size at 90° / 2560 wide is **2.1 arcmin** (DERIVED). That is coarser than a 1440p 27" monitor at arm's length (~1.3 arcmin), so **the render is the limiting instrument, not the eye**: thresholds are correctly stated in render pixels, and they will need re-deriving for a 4K target. `angular_budget.py --display-ppd` reports which side limits.

---

## 3. What the engine already provides (VERIFY each against source)

**LOD screen size.** UE switches static-mesh LODs on the projected bounding sphere: `ScreenSize ≈ 2R / (D · tan(vFOV/2))` as a fraction of screen height (`ComputeBoundsScreenSize`, SceneManagement.cpp — VERIFY the multiple; the tool prints both px and ScreenSize so a factor-of-two error would show). The important property: it is already angular. The recipe's `cull_distance_m` is the *only* distance-denominated knob in the chain, and it is the one that pops.

**Dithered LOD transitions.** Per-material `bDitheredLODTransition`, plus `r.DitheredLODTransition` — cross-fades LODs over a few frames using screen-door dither resolved by TAA/TSR. Foliage `FoliageType.bEnableCullDistance` ... the cull itself is hard unless the material fades on `CullDistanceScale`/`PerInstanceFadeAmount`. VERIFY the exact property names on `UFoliageType` and the `PerInstanceFadeAmount` material node in 5.8.

**HLOD (World Partition).** Builds a proxy for a grid cell: *instancing* (cheap, same meshes), *merged/simplified mesh* (one mesh + baked material), *approximated mesh* (voxel-based remesh — the one that works with Nanite foliage and produces the "coloured blob at the right coverage" the silhouette threshold asks for). 5.7 added **custom HLOD actors** for injecting your own proxy (Tom Looman's 5.7 notes). The community guidance for foliage is the Approximated Mesh layer and then forcing roughness=1 on the generated HLOD material. HLOD is the correct representation from the silhouette threshold (6 px, 3.1 km for a spruce) out to the horizon.

**Imposters.** The engine's *ImpostorBaker* plugin (Content/Plugins, `ImpostorBaker`) generates octahedral billboards from a static mesh; a foliage type can use an imposter as its last LOD. This is the correct representation between **detail (40 px, 470 m)** and **silhouette (6 px, 3.1 km)** for non-Nanite foliage. It carries per-view colour and normal, so a lit forest reads correctly from the vista camera; the approximated HLOD does not (flat colour).

**Nanite Foliage (5.7 experimental, extended in 5.8).** Trees as Nanite *assemblies* (instanced parts) with *voxel* LODs at distance and skinned wind; the 5.8 docs describe triangles switching to near-pixel-size voxels "imperceptible to the eye because of their size on screen," with the Witcher 4 demo at 500k instances. The **Procedural Vegetation Editor** (experimental, 5.8) generates such trees in-editor from growth rules without imported assets. If it works on your hardware, it replaces the whole LOD/imposter/cull ladder for trees with one continuous representation — and, for the forge, it is a shippable, non-Fab tree source. Two cautions: experimental, and Nanite foliage on an Intel iGPU is the kind of thing the dev-machine profile exists for. **Recommendation: evaluate on the benchmark with one species before any decision; do not migrate the world on the docs' promise** (non-negotiable: price each benefit against the artefact).

**PCG.** Engine plugin. The correct replacement for 9 MB-per-species instance JSON: a graph reads the weightmap and density parameters from a data asset the recipe writes, regenerates on terrain change, and outputs HISM instances that HLOD and imposters consume normally. 5.8 parallelised graph execution. Not required for this brief; required before density goes up 10× (WORLD_VISION's 200/ha).

**Movie Render Queue.** Engine plugin. Deterministic frame sequences from a Level Sequence camera path, with per-shot console variables and temporal sample counts. The instrument `temporal_stability.py` needs.

**Standalone game process.** `UnrealEditor-Cmd.exe <uproject> <map> -game -windowed -ResX -ResY` — a game viewport, no editor tick, `SystemLibrary.get_viewport_size` answers. The correct instrument for frame time (§6).

---

## 4. The representation ladder (the design this brief proposes)

For each object class, four bands keyed on pixel height, with the distance for the declared camera shown for the spruce (14.7 m):

| band | px tall | spruce distance (90°/1440p) | representation | what matters |
|---|---|---|---|---|
| detail | > 40 | 0–470 m | LOD0/LOD1 mesh, VSM shadows, wind, contact shadow | internal structure |
| shape | 6–40 | 470 m – 3.1 km | LOD2/3 or **imposter**; shadows from imposter or HLOD proxy | silhouette, colour, coverage |
| blob | 1.5–6 | 3.1 – 12.5 km | **HLOD approximated mesh** or canopy material on the landscape | coverage and mean colour only |
| gone | < 1.5 | beyond | nothing | — |

Two rules fall out:

1. **A cull may only sit at a band boundary where the next band exists.** Culling a mesh at 730 m is legal *only if* an imposter or HLOD takes over at 730 m. Culling to nothing is legal only below 1.5 px.
2. **Every band transition is dithered over ≥ 0.3 s at walking pace**, which at 1.4 m/s and a 470 m boundary is a 6 m fade band — trivial in distance, decisive in time.

The recipe change is therefore not "new numbers in `cull_distance_m`" but a new block:

```json
"perception": {
  "declared_camera": {"fov_h_deg": 90.0, "res": [2560, 1440]},
  "thresholds_px": {"vanish": 1.5, "silhouette": 6, "detail": 40},
  "fade_seconds": 0.35,
  "_derived_by": "scripts/angular_budget.py; distances are DERIVED per species from height_m and these thresholds, never typed"
}
```

and each species gains `height_m` (measured — `Free/_measured/pve_spruce.json` already has extents) and loses `cull_distance_m` as an authored value; `place_foliage.py` derives `cull_cm` from the thresholds at build time and writes the derivation into the instance JSON sidecar. Same shape for `rock_scatter` and grass.

---

## 5. The instrument (the tools)

All three are pure Python, numpy + PIL, tested with self-tests.

**`angular_budget.py`** — px tall / distance / UE ScreenSize per species per threshold, and a verdict for each authored cull. Run it on the recipe now; the result above is its output.

**`temporal_stability.py`** — the moving-camera instrument. Takes a frame sequence, compensates global motion by phase correlation, Weber-normalises the residual, ignores blobs under 12 px, reports per-frame changed fraction, spikes (frames a human should look at) with bounding boxes, and a sequence *score*. Self-test injects a 30×20 px brightness pop into a synthetic dolly and finds it (and its reversal) with the correct location. Compare score before/after on the same dolly path — that is the acceptance for "dither fade on" or "HLOD on."

**`lod_silhouette_check.py`** — judges a LOD chain by coverage ratio, silhouette IoU, edge error and Weber luma delta *at the pixel size each LOD is shown at*, not by triangles. Self-test passes a slightly eroded LOD1 and fails a trunk-only LOD2 (coverage 0.15). This is the gate the 2026-08-14 canopy lesson wanted.

---

## 6. The benchmark (prerequisite for everything after this brief)

Defined in `benchmark.json`: one level (`/Game/Alpine8K`), three stations (near-ground: the rear station from the 2026-09-05 render; mid-slope: treeline; vista: the 1.2 km station), one 6-second dolly at 1.4 m/s from the near-ground station, one lighting state (the recipe's), two quality profiles (`dev` = the current sg.* values; `target` = cinematic, defined in the file), captured via MRQ at the declared camera. Every brief from here on scores against these frames. The rear station's frame is the reference for Brief 2.

**Frame-time is measured in a standalone process, not the editor.** The 2026-09-05 re-baseline showed the game thread pinned at 13.9–14.15 ms on all four zones regardless of content — editor overhead under the 16.67 ms clamp, not the world. `SystemLibrary.get_viewport_size` returning `None` has the same root cause. FOR_CLAUDE_CODE task 4 gives the procedure (DRAFT, flag names to VERIFY).

---

## 7. What to try, in order, each with its measurement

1. Run `angular_budget.py` on every species and rock in the recipe; record the verdicts in LESSONS at the narrative altitude and in RECIPES as the REJECTED entry for `cull_distance_m` as an authored value.
2. Build the benchmark (stations, dolly, MRQ config, two profiles). Capture the dolly at `dev`. Run `temporal_stability.py`; this is the **baseline score**.
3. Turn on dithered LOD transitions and instance fade for all foliage types. Re-capture. Score must drop; spikes at the old cull distances must vanish or shrink.
4. Generate imposters (ImpostorBaker) for Conifer / ConiferPine / SpruceSub as the last LOD; set the mesh cull to the *detail* boundary (~470 m) and the imposter cull to the *silhouette* boundary (~3.1 km). Re-capture at the vista station: trees should now exist to the ridge. Score the dolly again.
5. Build HLOD (Approximated Mesh layer) for the foliage cells; verify the vista frame's tree coverage beyond 3 km with a simple green-fraction-in-band measurement against the same frame with HLOD off.
6. Run `lod_silhouette_check.py` on the existing LOD chains at their switch sizes. Any FAIL is a chain to rebuild by silhouette, not triangle count.
7. Only then: the Nanite Foliage / PVE evaluation on one species at the benchmark, both profiles, with frame time from the standalone process. Decide from numbers.

---

## 8. Sources

- Campbell, F.W. & Robson, J.G. (1968). Application of Fourier analysis to the visibility of gratings. *J. Physiol.* 197:551–566.
- Barten, P.G.J. (1999). *Contrast Sensitivity of the Human Eye and Its Effects on Image Quality.* SPIE Press. (The CSF model used in HDR-VDP and the JND display standards.)
- Kelly, D.H. (1979). Motion and vision II: stabilized spatio-temporal threshold surface. *JOSA* 69:1340. (Temporal CSF.)
- Luebke, D. et al. (2003). *Level of Detail for 3D Graphics.* Morgan Kaufmann. (Screen-space error, perceptual LOD, the chapter on the CSF-driven LOD selection.)
- Karis, B. (2021). *Nanite: A Deep Dive.* SIGGRAPH Advances in Real-Time Rendering. (Sub-pixel error target = 1 px edge, the basis for `r.Nanite.MaxPixelsPerEdge=1`.)
- Epic, UE 5.8 docs: *Nanite Foliage*, *Nanite Assemblies*, *5.8 Release Notes* (Procedural Vegetation Editor), *World Partition HLOD*. Tom Looman, *UE 5.7 Performance Highlights* (custom HLOD actors, Nanite foliage voxels).
- Engine source to VERIFY: `SceneManagement.cpp` (`ComputeBoundsScreenSize`), `FoliageType.h` (cull/fade fields), `MaterialExpressionPerInstanceFadeAmount`, `LaunchEngineLoop.cpp` (benchmark/standalone flags).
