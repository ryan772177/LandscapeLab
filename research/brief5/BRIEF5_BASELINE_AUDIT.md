# Brief 5 baseline (v2) — desk audit, 2026-09-20

Audited: `BASELINE.md`, `PCG_NOTES.md`, all nine `input/` files, three scripts.
Checked against Epic's 5.8 pages (each served `application_version=5.8`):
WP-HLOD, Using PCG Generation Modes, Biome Core Reference Guide, Nanite Foliage,
Scalability Reference. Desk tier is web docs only; anything marked
"header" still needs Claude Code's local 5.8 header:line.

**Bottom line.** The per-pass table, the census counts, the LOD read-backs, the
dolly manifest and the replay inventory hold. The two headline conclusions do
not: "HLOD share RESOLVED — NEGLIGIBLE" is not a measurement, and "density is
cheap" was measured at stations where almost no trees are on screen. Brief 5
should not be derived from either until the re-measure below lands.

Severity: **A** = changes a conclusion, **B** = wrong/unsupported statement,
**C** = hygiene.

---

## A1 — The HLOD "nearest 2.2–3.5 km" figure is an artefact

`hlod_share_enumerate.json`: all eight sampled HLOD actors — different cells
(`X-14_Y-16`, `X6_Y2`, `X-3_Y11` …), both L0 and L1 — report the **same three
distances** (2238.6 / 3500.3 / 2381.5 m). Actors in different cells cannot be
equidistant from three stations. The probe measured distance to one shared
point (almost certainly `get_actor_location()` returning a common origin for
every `WorldPartitionHLOD` actor), not to the proxies. It also contradicts the
recipe: with main range 512 m and HLOD ranges 1.024 km / 2 km, proxies must
begin just past 512 m, not at 2.2 km.

Everything built on it falls: "distant HLOD is Nanite at 2 km+, covers few
pixels, near-free" is an explanation of a number that was never real.

## A2 — The editor actor-hide A/B has no positive control

The 0.015 ms delta proves the hidden flag flipped (1042/1042). It does not
prove the proxies were being **drawn** beforehand.

- 5.8 WP-HLOD doc: HLODs "visualize unloaded World Partition grid cells"; in
  the editor the proxy shows (blue, HLOD Coloration) only once you move away
  from the source actors.
- The session's own STATUS file says the same thing three ways: the proxy band
  renders "only in an actual `-game` process"; the editor "still renders real
  cells".

So the A/B was run in the one environment the repo's own tools say does not
render the band. A delta of zero from hiding something that was not on screen
is not a measured zero. This is the project's own doctrine — agreement among
instruments that share a source is one measurement — and here the "corroborating"
`-game` A/B is explicitly recorded as never having applied.

**Status to record: INCONCLUSIVE, unchanged from v1.** Not RESOLVED.

## A3 — `wp.Runtime.HLOD` is a console *command*, not a cvar

Epic's API reference lists it as `EnableHLODCommand`, an `FAutoConsoleCommand`
in `WorldPartition/HLOD/HLODRuntimeSubsystem.h` (page served for 5.4 — confirm
at the 5.8 header). Consequences: a bare-query "echo read-back" can never work
(commands have no value to echo), it needs a live world, and startup
`-ExecCmds` fires too early. The v1 "0/2 parsed" and the v2 "Warning: deferred"
are both this. The fix is a post-world-load delivery channel, not a different
spelling.

## A4 — "Density is cheap" was measured where there is no density in view

Census, visible live trees per station: treeline **0**, vista **34**, plaza
**903**, main_street **919** — out of 185,385. No perf station looks at forest.
The treeline hide removed 10,860 GPUScene instances, none of them in the
declared frustum. So:

- `0.107 ms / 10k (treeline)` is the cost of instances that were **off screen**.
  It is not a marginal cost of visible density and must not be used to size a
  denser forest.
- `0.023 ms / 10k (plaza)` is 126k instances that are overwhelmingly landscape
  grass. The two figures are different populations and are not comparable.
- A `forest_floor` station already exists (the 2026-08-15 PVE frame-cost pass
  used it). That is where this number has to come from.

The desk's own line from the last prompt — "the forest can plausibly be several
times denser for well under a millisecond" — is **withdrawn** until then.

## A5 — The treeline foliage delta is inside run-to-run noise

The D1/D2/D4 sweep changed nothing, so it is three repeats of the same scene:
treeline 7.229 / 7.239 / 7.143 (spread 0.096 ms), plaza 9.441 / 9.520 / 9.467
(spread 0.079 ms). The treeline foliage cost, 0.116 ms, is the same size as
that spread, from one run per arm. Plaza's 0.286 ms is ~3.6× the spread and
survives. GPUScene count swung 196,553 → 167,914 → 155,054 at plaza (−21%)
across "identical" runs and is labelled "streaming variance"; if that is the
noise, then "removed 126,386" carries tens of thousands of uncertainty, and if
it is not noise it is unexplained. Either way a noise floor has to be measured
before any sub-0.2 ms delta is quoted.

## A6 — The pass table cannot say "this is not the forest"

`GPU/<pass>` columns split by render pass, never by content. The only Nanite
tree (Norway Spruce) lands inside NaniteVisBuffer / NaniteBasePass; every tree
lands inside ShadowDepths / ShadowProjection (sun elevation 12°, long shadows).
"Nothing here is a foliage-instance line" is true of any scene. Shadows are
14–18 % of both frames and are the most likely place tree cost hides. The
attribution that works with no new levers: run `--csv-gpu-stats` in **both**
arms of the hide A/B and diff per pass.

## A7 — What the far forest actually is has not been read back

BASELINE calls the proxies "merged Nanite proxies". The actors are named
`Alpine8K_HLODLayer_Instanced_L0/L1` under a `…_Merged` folder. Per the 5.8
doc an **Instancing** layer replaces meshes with ISMs "using the lowest Level
of Detail". For this forest that would mean: Scots pine → 32-tri billboard,
spruce_half → 6-tri imposter, sapling → 326 tris, and **Norway Spruce (Nanite,
1 LOD) → the full Nanite mesh again**, out to 2 km. That is a Brief 5-shaping
fact and it is currently a guess in both directions. Read back each HLOD
layer's `LayerType` and the components the built actors actually hold.

## A8 — "Every tree is only ever seen at DETAIL" hides the billboard switch

True of angular size; misleading about representation. Mesh-baked switches:
Scots pine → billboard at ScreenSize 0.168, spruce_half → imposter at 0.17.
Desk estimate (formula to be confirmed at header, bounds to be read back): at
90° hFOV 16:9, ScreenSize ≈ 1.78·R/D, so a tree with R≈13 m flips to a 32-tri
billboard at ≈ 140 m — while it is still ~350 px tall at the 4K judgement
camera, nearly 9× the 40 px detail threshold. From there to the 512 m cull,
two of the four species are cards. Brief 5 needs a representation-by-distance
table (metres and pixels), not the band table alone.

Also unflagged: recipe says ScotsPine LODs `[0.5, 0.21, 0.088]`, billboard at
0.088; the asset says four LODs ending at 0.168. Recipe and asset disagree by
~2× on where the billboard starts.

---

## B1 — BASELINE contradicts itself on the open question

§6: "Biggest open question: the HLOD-proxy + landscape GPU share … the same
number item 3d could not measure." Closing summary: "NOT the open number …
closed." JSON `_v2` string still says "HLOD A/B inconclusive" while
`hlod_gpu_share.verdict` says RESOLVED.

## B2 — The shipped JSON is not reproducible from the shipped assembler

`assemble_baseline_v2.py` hard-codes `"verdict": "INCONCLUSIVE"` with the
`-game` numbers. The zip's JSON says RESOLVED with editor numbers, so it was
edited after assembly (or by a script not in the zip). Re-running the assembler
silently reverts it. `treeline_ms_per_10k: 0.107` / `plaza: 0.023` are literals,
not computed.

## B3 — `foliage.DensityScale` was the wrong tool for an up-sweep, by the docs

5.8 Scalability Reference: FoliageQuality maps DensityScale 0.25 → 1.0, and
foliage static meshes participate only if the type has **Enable Density
Scaling** set (Epic's guidance: on for grass-like detail, off for trees). It is
a scalability *down*-lever with per-type opt-in. ">1 is a no-op" is right in
effect, but the baseline never read back `enable_density_scaling` per
FoliageType, so it is unknown which types even the DensityScale-0 hide touched
(ShowFlag.Foliage did the visible work). "No budget crossing exists via
density" should read "this lever cannot test it".

## B4 — PCG_NOTES §3 swaps the two injection stages

Notes say exclusions are "injected near the very end of the pipeline just
before spawning" and build the fit argument on it ("same drop-after-placement
semantics our recipe already relies on"). In the 5.8 Reference Guide that
sentence belongs to **Custom Biome Data (Global Biome Core)**. **Exclusions are
Local Biome Core** — they act per biome actor, before recursion/child assets,
assemblies and the global priority difference. The settlement-exclusion fit is
still reasonable, but it is not the post-filter equivalence claimed, and
child assets spawned from surviving parents near the boundary are not covered
by it.

(The deputy's flag on "three injection kinds" is correct and the error was the
desk's: the doc defines two — exclusions and custom biome data. Withdrawn.)

## B5 — Three of the five UNVERIFIED flags are answered by the page cited

Same Reference Guide:
- Default partition is **256×256 m** from the PCGWorldActor Partition Grid Size
  — matches the probe's CDO 25600.
- Biome Core runtime: grid **3200 → Generation Radius 4800 cm**, grid **6400 →
  9600 cm**, mesh scatter at **800 cm**; "increasing these radius values …
  increas[es] the number of runtime partition actors and PCG points".
- The `.npz` water mask is a **Filter**, not injected data: filtering is its
  own Local-stage concept (Height/Density by default; Biome Sample adds
  per-tile texture-projection filters and a documented
  **WaterDistanceMin/Max** option against a configured water level).

This changes §2's mapping. Epic's reference runtime generation works at
**48–96 m**, GPU-spawned straight into the GPU scene, for ground detail around
the camera. It is not a 512 m conifer mechanism; it is a candidate for the
meadow gap (grass culled at 50 m, nothing to 512 m) — and "out to 512 m" in §4
is ~5× Epic's reference radius, so it is a thing to measure, not assume.

## B6 — PCG_NOTES smaller misses

- Generation sources: doc lists four (editor viewport, player, **World
  Partition streaming sources**, PCG Generation Source components); notes say
  "player/camera by default".
- The documented `pcg.RuntimeGeneration.*`, `pcg.FrameTime` (16.667 ms),
  `pcg.EditorFrameTime` (50 ms) cvars are on the cited page; baseline says PCG
  cvars "not captured".
- Notes cite `BASELINE.md:16-19, 21-28, 25, 47-50, 70-74`. Those are v1 line
  numbers; v2 has different content at every one. The conclusion paragraph
  still names the HLOD share as the biggest open question while BASELINE v2
  calls it closed.
- PVE: 5.8 doc confirms Experimental, 5.7 assets incompatible, default output
  Nanite Foliage, static mesh optional. Nanite Foliage itself is **Experimental**
  and off by default (Project Settings > Rendering). The baseline never reads
  back whether it is on, though the Conifer was exported Voxelize with
  `create_nanite_foliage:true`.

---

## C — Hygiene

- `density_census.py in_frustum()` returns a 2-tuple on `d < 1e-6` and a
  4-tuple otherwise; the caller unpacks four. Latent crash.
- Census visibility tests the tree **base point** with no occlusion. A 29 m
  spruce whose base is below frame still fills it. The 61 treeline
  "elevation" exclusions are this. Rename `visible` → `in_frustum_in_cull` or
  test the base–top segment.
- BASELINE §3 presents the LOD table as this session's editor read-back;
  the assembler reads `_verify/bench/2026-09-07/tree_lod_probe.json`. 13 days
  old. Say so, or re-probe.
- HLOD A/B resolution/profile is not recorded; the derivation it is compared
  with was dev 2560×1440, the perf runs 3840×2160.
- Dolly: the 09-07 set is recorded as actor-heading FAILED yet contributes 89
  of the 356 "ready" pairs. Usable pairs from passed sets: 267.
- Reference coverage, replay inventory: honest about their limits; no findings.

## What holds

Per-pass GPU tables (as pass attribution), census totals and per-species
counts, band-ring radii, LOD/triangle read-backs (modulo date), PCGWorldActor
absent + CDO 25600, plugin readiness, PVE status, "evaluate, don't migrate".
