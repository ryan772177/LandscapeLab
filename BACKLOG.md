# BACKLOG.md — the scope-creep valve

**Purpose.** Any idea, improvement, or discovered issue that is **not the
current session goal** gets one line here instead of an afternoon. This
is how a session about grass stays a session about grass.

**Rules.**
- Full autonomy to ADD. Anything may be appended at any time, mid-task,
  without asking.
- **Pulling from the backlog happens at session start only**, after
  reading CURRENT STATE. Not mid-session — that is the scope creep this
  file exists to stop.
- Format: `date | item | why it matters | est. size`.
- Sizes: **S** (< 1 session), **M** (1 session), **L** (multi-session),
  **?** (unknown until scoped — scoping it is itself an S).
- Deleting an entry requires either doing it or a recorded ruling that
  it will never be done. Silent deletion is not allowed.

---

## Brief 5 Daylight Density — density re-run is BLOCKED on T4 (added 2026-09-22)

`2026-09-27 | SUPERSEDED by Brief 7 Phase 3a: the density re-run RAN under R-AESTHETIC-1 (ms budgets suspended, perf recorded not gated, VRAM guard only) at the RULED caps — forest_floor m=1 (Ryan 2026-09-23), plaza 2.157 (T4 recalibration), treeline/open at target under D_max. World = 797,500 trees; -game GPU p90 12.38 / 12.69 / 9.62 ms recorded. The two T4 entries below stay as the record of WHY forest_floor is capped at 1.0; they no longer block anything. R-P3-DENSITY. | done`

`2026-09-23 | T4 gate RAN: no cheap lever recovers forest_floor headroom | Step 1 recalibrated the cost model (ff cap 2.38 -> 1.162; the 0.100 ms/1000 rate was ~9x low) and showed T4 rungs face a >=3.50 ms untouchable floor (NaniteVisBuffer=Conifer/Nanite + LumenReflections). Step 2 measured the runtime cvar levers (r.Shadow.RadiusThreshold/DistanceScale, r.Lumen.Reflections.MaxRoughnessToTrace, r.Nanite.MaxPixelsPerEdge; foliage.CullDistanceScale inert): the whole kept stack is 0.128 ms (arm B, quarter shadow distance) vs a ~2.7 ms deficit. The forest_floor cost is STRUCTURAL. T4 RUNGS DEMOTED (entry condition: only if a per-species split ever shows >= 1.5 ms non-Nanite in ShadowDepths + Basepass at forest_floor). Density at forest_floor is blocked pending Ryan: a budget re-rule (raise 13.0), an asset-write tier (FoliageType cull opt-in / per-type shadow flags, persist protocol), or accept m=1 at forest_floor and pursue density only where there is headroom (plaza cap 2.157, treeline/vista under budget). ini promotion of any cvar needs the persist protocol + a fresh ASK. See t4_step2_summary.json. | L`

`2026-09-22 | T4 rung gate session now BLOCKS any density re-run | D4 measured the density cost model wrong by 2.4-3.1 ms at forest_floor/plaza (the 0.100 ms/1000-trees "upper bound" was ~9x low — measured 0.854/0.980; the passes that grow are ShadowDepths + NaniteVisBuffer, see d4_model_error.json). A density re-run at ANY multiplier busts the GPU budget on the same broken model. FIRST STEP of the T4 session: recalibrate the zone map caps (research/brief5/scripts/zone_map.py) from d4_model_error.json's measured ms/1000-per-pass, NOT the withdrawn 0.100 rate. THEN the T4 rungs (tri-reduction pays now that NaniteVisBuffer is measured at 2.2 ms at forest_floor) + the isolation-render gate that never ran. The SpruceSub build STALL root cause is still owed before any rung rebuild (retry recipe: one species per ue_exec call + incremental on-disk progress markers). | L`

`2026-09-22 | Clutter cost (D5) still unmeasured | PCG-graph authoring was proven (Content/Scratch/PCG/PCG_ClutterSpike.uasset) but the cost arms were never captured (the overnight harness reaped the measurement twice). Owed before any clutter-density decision. | M`

`2026-09-27 | Rewrite capture.py onto shoot.py (pipeline rule 4's tool
froze the editor) | After the P2 world run, capture.py landed camera 1 of
21 and the game thread stopped ticking on camera 2 (16:09:34, RAM
1.6–4.5 GB free); killed on Ryan's order, nothing lost. shoot.py (host-side
wait, one shot) serviced every still in 4 s on the relaunched editor.
Rule 4 should name a tool that cannot block the thread it waits on:
port capture.py's recipe-camera loop onto shoot.py, one camera per call,
and run it on a fresh session after any large mutation. R-CITYSHOT
REJECTED 2026-09-27. | M`

`2026-09-27 | Scree-mask bake on the landform router | make_variant_map.py
now routes talus on the 16 m landform (audit-3, NN19) but the shipped
weightmap was baked with the raw-surface field; the next
derive_layer_weights / variant bake + reimport changes the Pass-2 scree
mask (a world change with its own stills). Do it as its own unit with
the persist protocol. | M`

## From the desk dossiers (research/desk/DOSSIER_*_2026-09-27.md; inputs, not law — open every number)

`2026-09-27 | Ecotone authoring pattern for the 2×2 atlas boundaries | Dossier 2 §D3: boundary on a landform, 200–600 m band (design suggestion, unsourced), overlapping biome tables tapered in ecological order, two region PPVs with blend radius, Local Fog Volumes in valleys, one MPC (snow/wetness/dust) lerped along the band. We have the region ruling and no transition recipe. | M`

`2026-09-27 | Far-field ring beyond the 2×2 atlas (airship altitude, ruling 2a) | FFXVI: playable ~2 km with a far field ~10×, merged by distance ("merge grid"); Rebirth: FarLand whole-level proxies. Our vista is the 8 km terrain itself; nothing beyond it. A ruling on a low-cost far ring (Gaea vista tier + merged HLOD) before any region work. | ? |`

`2026-09-27 | Nanite Foliage / PVE spike vs the imposter cards | Dossier 2: W4 demo 500k instances, 95% screen foliage, assembly trees 3.5 GB → 29 MB; Experimental in 5.8, no 5.7→5.8 asset compat. Our A2 subject is the 200–512 m imposter band. Spike: ONE species as a Nanite Foliage assembly, same station, same crops, ms + VRAM + the far-band sat/hue. Phase 3 candidate. | M`

`2026-09-27 | Landscape "flavor + tiling + detail" texel-density rule | Rebirth layered materials: non-repeating flavor + tiling + detail maps tuned so small and large rocks read the same detail density. We have macro_variation + R-TILE; no cross-scale texel-density rule. Payoff only once meshes (town kit, props) sit on the ground. | S |`

`2026-09-27 | Time-of-day acceptance still set per station | Dossier 2 §D2 step 9: noon / golden hour / overcast / night + a hero landmark at 1 km and 5 km, signed against the region palette. Our stations are fixed at one sun. Adopt when the Look is judged across the day. | S |`

## Verification and proof debt

`2026-09-11 | The perf gate is judging the 512 m world against 768 m
evidence | check_perf reads
_verify/perf/20260910_standalone4k_range768.json and reports RED
(treeline GPU 7.86 vs 7.00, over by 12%). That RED is exactly what
CAUSED the ruled fallback to 512 m -- the range changed, the culls were
re-derived, and no standalone 4K run has been taken at 512. The gate is
therefore measuring a world that no longer exists, and it will stay RED
until re-measured whatever the truth is. Needs one standalone capture
at the ruled range. NOT done in-session: budgets and captures at a new
range were outside the rulings. | S`

`2026-09-11 | 22 plans are STALE OR UNREPRODUCIBLE against their
producers | check_plan_freshness --reproduce fails on all four
alpine_8k foliage plans, both city plans, both encounter sets, and 14
plans across canyon / coast_bench / highland_lake /
spike_photo2landscape. The alpine_8k ones are a known consequence of
re-deriving culls WITHOUT re-scattering (the density prohibition), so
that subset is expected and should be recorded as such rather than
"fixed". The other-biome ones are unexplained and predate this session.
Deciding which are expected-and-annotated vs genuinely stale is the
work. | M`

**PULLED 2026-08-03 — this is the next session's goal.**

`2026-08-03 | Replay batch 1: cold-replay R0, then R3, R2, R11 | PULLED.
Documentation quality has outrun proof: 13 conforming recipes, 75
REJECTED entries, and all 13 UNPROVEN. Selection is by TRAFFIC, not by
cost — R3 (10 REJECTED), R2 (9), R11 (9) are the three most-trafficked
recipes, and the ruling is that highest-traffic recipes are where replay
failures teach the most. R0 first because it gates every other recipe's
verification. | M`

**Batch 1 was previously "R0, R1, R5, R10", chosen as the CHEAPEST to
replay.** Superseded 2026-08-03: cheapest-first optimises for a clean
result, and the point of a replay is to find the gap. Recorded rather
than silently swapped.

`2026-08-03 | Replay batch 2: cold-replay R1, R4, R5, R6 | The remaining
content-producing recipes. Needs a scratch map so a failed replay cannot
damage /Game/Alpine. | L`

`2026-08-03 | Replay batch 3: R7, R8, R9, R-ASSET | R8 and R9 are
recovery procedures that can only be replayed by deliberately inducing
the failure; R-ASSET's skeletal half has never run at all. | ?`

`2026-08-03 | Recover the 7 VALUE UNVERIFIED scene fields | R6 lists
lod_distance_factor, DirectionalLight source_type/intensity_units, and
four SkyLight fields that 5.8 refused via get_editor_property. They are
unreadable, NOT absent. Need a derivation or a different accessor. | S`

`2026-08-03 | Recover World Partition streaming settings into R0 | R0
records the landscape/proxy counts but not the streaming source or cell
size, so a fresh machine could differ invisibly. | S`

`2026-08-03 | Confirm the Windows page file was ever applied | R0 lists
32768/49152 MB as VALUE UNVERIFIED; the step needed UAC elevation and
was never confirmed. On a 15.4 GB host this is real. | S`

## Defects found and deliberately not chased

`2026-08-16 | THE ROCKS AND CLIFFS DO NOT COLLIDE — needs a ruling, not a fix
| Unit 6 made the four TREE species query-collidable and measured the cost at
+0.21 ms GameThread against a +0.5 ms bar. The other ten FT_* — Boulder,
CliffFace, CliffOutcrop x2, Talus x4, TreeStump, Scrub — are now DECLARED
"enabled": "none" in recipes/alpine.json, which is the measured truth recorded
rather than silently changed. They belong to /Game/Alpine and carry no
instances in Alpine8K, so nothing in the live world regressed. But a player
can walk through a 22 m cliff face, and when the rocks are next scattered into
a playable world that is a defect. The machinery is built: one recipe edit plus
apply_foliage_collision. What is missing is a RULING on which of them should
block, and a cost run — cliffs carry 4 simple primitives each and are far
larger than a trunk capsule. | S`

`2026-08-16 | Settle custom_navigable_geometry against a BUILT navmesh |
PHASE2_PLAN unit 6 prescribes "No", which is backwards: per
NavRelevantInterface.h, No still runs the DEFAULT collision export and
DontExport is the value that excludes, while Yes calls
DoCustomNavigableGeometryExport (InstancedStaticMesh.cpp:5435-5438) which
exports PER-INSTANCE transforms. Left at Yes (the engine default) and now
declared explicitly. Nothing can adjudicate this without a navmesh to look at,
so it belongs to unit 8. | S`

`2026-08-16 | The Conifer capsule radius is consistent, not pinned | The
geometric trace measurement brackets 0.1-1.4 cm BELOW 38.0 x scale on 3 of 4
samples. Consistent with align_to_normal 0.15 tilting the capsule axis (~6 cm
of lateral shift at the 1 m trace height on a 24 degree slope) plus the 2-5 cm
offset granularity of the probe. To pin it: trace at the instance's own base Z
rather than +100 cm, where tilt contributes nothing, or sample instances on
flat ground only. Low value — the capsule works — but the number should not be
quoted as verified until then. | S`

`2026-08-03 | RESOLVED — conifer trunks were rendering the TWIG atlas |
Root cause was NOT the opacity mask and NOT 16-bit alpha. M_fir_bark was
built without --slot, and texture_map silently last-wins on a shared
role, so it sampled twig_diff/twig_nor/twig_rough and never a bark
texture. Compounded by delete_all_material_expressions leaving 7 wired
survivors, so the first corrected rebuild changed nothing. Both fixed and
locked in R3 REJECTED. Trunks now render bark — clearest in
_verify/20260803-0222_alpine_forest-floor-backlit.png. | DONE`

`2026-08-03 | CORRECTION: the "fir was never reimported" entry was WRONG
| I wrote it from the LESSONS narrative without checking the engine.
Measured: T_fir_tree_01_bark_rough_4k and T_fir_tree_01_twig_rough_4k
were BOTH already imported from the _8bit converted sources, and
twig_alpha is RGB 8-bit — never in the 16-bit trap at all. The fir's
8-bit conversion was already complete. Lesson: a backlog claim about
project state is a measurement, and must be made against the project,
not against the log. | DONE`

`2026-08-03 | Conifers read thin/sparse versus a dense alpine forest |
With bark fixed and needles rendering, the remaining sparseness looks
like the ASSET (fir_tree_01_c is a slender, high-branching fir) plus
aggressive mid-LODs, not a defect. Decide whether to accept it, add a
second species for silhouette variety, or soften the LOD chain. Needs a
judgement call, not a bug fix. | M`

`2026-08-03 | t.MaxFPS=45 does not take effect | Live editor reports
t.MaxFPS = 0.0 despite the ini. Every other plain cvar in
[SystemSettings] matched. The GPU runs unthrottled on a machine that has
already thrown DXGI_ERROR_DEVICE_HUNG. Needs the editor-side frame limit
instead. | S`
**ROOT-CAUSED 2026-08-07, fix NOT applied (needs a restart to verify).**
Our ini is correct and correctly placed — `t.MaxFPS=45` at
`DefaultEngine.ini:178` inside `[SystemSettings]`, which is the right
section. It is applied at startup and then **overwritten**:

  1. `LandscapeLab/Saved/Config/WindowsEditor/GameUserSettings.ini:19`
     holds `FrameRateLimit=0.000000`.
  2. `UGameUserSettings::SetFrameRateLimitCVar`
     (`GameUserSettings.cpp:413-415`) does
     `GEngine->SetMaxFPS(FMath::Max(InLimit, 0.0f))` -> 0.
  3. `UEngine::SetMaxFPS` (`UnrealEngine.cpp:12247-12255`) **deliberately
     re-uses the PREVIOUS set-reason** rather than writing at its own
     priority, so it writes at the same `SetBySystemSettingsIni` level
     the ini used — and the later write wins. Priority cannot save us;
     the setter is built to overwrite whoever set it last.

So this was never a cvar that "did not apply". It applied and was
clobbered by a SECOND config file, and the one we edited is the loser.
**Non-negotiable 17, fourth instance, with a new twist: two files
disagree and the state belongs to the one nobody edited.**

CANDIDATE FIX, unverified: set `FrameRateLimit=45.000000` in that
`GameUserSettings.ini`. Caveat to settle first — `Saved/` is generated
and may be rewritten, so a durable fix probably belongs in a checked-in
`DefaultGameUserSettings.ini` instead. **Verification requires an editor
restart** (the cvar is set during startup), which is why it is not
applied here. | S

`2026-08-03 | The aerial verification camera cannot verify vegetation |
verify_aerial points at a rock-and-snow peak with half the frame in deep
shadow; the forest band is a minority of pixels. It would read ~0%
vegetation no matter how good the vegetation was. Re-aim it over the
forested valley before using it as evidence again. | S`

`2026-08-03 | No vegetation-coverage metric is trustworthy yet | Three
metrics were wrong in one session: green-dominance (fails under warm
light), absolute G-(R+B)/2 (brightness-dependent, so darkening reads as
less green), and the raw 0.00% baseline that was reported as a finding.
Need one validated against a frame with KNOWN vegetation. | S`

`2026-08-02 | Terrain stretches on steep faces | The rock layer needs
triplanar projection; UV stretching is visible on near-vertical
geometry. | M`

`2026-08-02 | Multi-object vendor import can overwrite recipe-named
meshes | An ad-hoc import creates one asset per OBJECT and the pivot
gate never inspects it. R3 and R-ASSET both record it as a KNOWN HAZARD.
| M`

## Aerial readability (ruling 2a, WORLD_VISION)

`2026-08-03 | Foliage HLOD / imposters for trees | The 730 m cull is the
affordable ceiling for real instances at 40M tris; beyond it only the
landscape material carries the forest. Imposters are the real fix for
airship altitude and the largest single item for ruling 2a. | L`

`2026-08-02 | World Partition tuning for a 2 km viewpoint | A 2 km eye
sees far more cells than a walking one; streaming was tuned for
neither. | M`

`2026-08-02 | The region boundary is a hard edge at altitude | With the
multi-region ruling this is a real authoring question: what does a
region edge look like from an airship? Design first, then implement. | ?`

`2026-09-27 | Aerial perspective: stronger blue at 1 km | Four ladders
(height-fog density/start, extinction+albedo, AP view-distance scale,
Mie×Rayleigh spectrum) could not move the ~800 m far-band hue toward
blue: every cell sits −5.3…−7.8° (warmer than 40 m) with a 0.7° spread
inside the 0.8° hue noise; sat clauses pass everywhere. Persisted
fallback (ruled): Look fog 0.0015 / 150 m, AP 1.0, mie 0.010, rayleigh
0.0331. The blue exists at the 4–8 km ridges; at 1 km the pixel is warm
sunlit haze under a 35° sun + WB 6200. Next levers are OUTSIDE the
atmosphere: a cooler Look WB or a distance-graded LUT/post tint, or a
sun-angle change — each a Look ruling, each measured with the same
crops. Table: research/brief7/a2_imposter/FOG_SPECTRUM_RESULT.md,
FOG_AP_RESULT.md, FOG_TUNE_RESULT.md. | M`

## Content headroom

`2026-08-02 | grass_medium_02 / leafy_grass unused | Larger grass
varieties already vetted through the now-safe import path; would add
silhouette variety at no new risk. | S`

`2026-08-02 | Rock026 / Rock063 / fir_tree_01_b unused | Imported and
sitting idle. Cheap variety if a recipe names them. | S`

## Structural / process

`2026-08-03 | R-ASSET's skeletal retarget half is unwritten | The IK Rig
/ IK Retargeter chain mappings are VALUE UNVERIFIED because we have
never retargeted anything. The Paragon import is the intended first
worked example. | M`

`2026-08-03 | ASSETS.md is seeded but not back-filled | Existing imports
(fir, grass, the four surface sets) predate the intake recipe and have
no licence/source rows. | S`

---

## PENDING RULINGS — Ryan's to make, blocking

`2026-08-03 | WORLD STRUCTURE: contiguous vs multi-region-by-airship |
OPEN DECISION. Previously delegated to the agent and ruled MULTI-REGION;
Ryan took the decision back on 2026-08-03. The proposal is complete in
WORLD_VISION.md (both options, pipeline implications, agent
recommendation = multi-region, matching Ryan's stated lean). BLOCKS ALL
PLACEMENT WORK. | ruling only, no build |`

Settled and NOT part of this ruling: 8064 m is the per-region size;
alpine is region one; the schema stays biome-general.

## Asset acquisition (ratified 2026-08-03, nothing acquired yet)

`2026-08-03 | Acquire + import Paragon packs: Grux, Rampage, Khaimera,
Greystone, Shinbi, Sparrow | First real character/creature content, and
R-ASSET's first worked example. UE4-era: expect 4.27 project -> migrate
to 5.8 -> IK-retarget to UE5 skeleton. | L`

`2026-08-03 | Acquire Game Animation Sample (GASP) | The locomotion
baseline every retargeted character must drive. Should land BEFORE the
Paragon retargets, since it is the retarget TARGET. | M`

`2026-08-03 | Acquire Infinity Blade environment packs | Environment kit.
Some are launcher-Vault-only, not on Fab web, so acquisition path
differs per pack. | M`

`2026-08-03 | Write R-ASSET's skeletal half from a real execution | The
IK Rig / IK Retargeter chain mappings are VALUE UNVERIFIED because
nothing has been retargeted. Must be measured during the first Paragon
import, not written from memory. | M`

## Region pipeline

`2026-08-03 | Stamp compositing step in the region recipe | StampIT
delivers terrain FEATURES (ridges, canyons, craters), not full
heightmaps. They must be BLENDED INTO a base heightmap before import --
there is no step for that today, so the stamps are inventory we cannot
yet spend. Needs: a blend operation (add/max/min with falloff mask),
placement coordinates in the recipe, and it must run BEFORE
push_heightmap so the landscape is imported once. | M`

## Project-level samples — cherry-pick later, NEVER bulk-merge

**Ryan is downloading the four 60 GB-class Vault samples overnight
(2026-08-03). Do not wait on them.** Each gets its own cherry-pick
session; the entries below are those sessions.

**Ruling 2026-08-03.** These arrive as SEPARATE PROJECTS, not
Content-folder assets. They are created as their own project and mined
selectively through R-ASSET. **We do not bulk-swallow 60 GB samples into
`LandscapeLab`** — every asset that enters does so through the intake
recipe, with a licence row and a render proof.

`2026-08-03 | Open World Demo Collection — selective migration | Highest
priority of the four: it is the closest match to what this project
actually is, and its landscape/foliage setup is directly comparable to
ours. Cherry-pick candidates: foliage assets, HLOD/imposter setup (the
open aerial-readability item), World Partition configuration. | L`

`2026-08-03 | Medieval Village — selective migration | Structures and
props for settlement POIs. Nothing here is needed before the world
structure ruling lands, since POI placement depends on it. | L`

`2026-08-03 | Electric Dreams — selective migration | Primarily a
showcase of PCG and Nanite foliage at scale. Value is the TECHNIQUE more
than the assets; treat as reference before treating as inventory. | ?`

`2026-08-03 | Project Titan — selective migration | Large community art
project. Very large on disk; audit what is actually wanted before
creating it at all. | ?`

## Hardware migration

`2026-08-03 | GPU desktop migration; R0 cold replay is its acceptance
test | If R0's written procedure alone does not reproduce an identical
editor on the new machine, R0 is wrong and the gap is the finding. Also
requires deliberately REPLACING the low-spec values (an unreviewed
r.ScreenPercentage=70 on a capable GPU is a silent quality cap) and
RE-MEASURING the 62M triangle ceiling rather than scaling it. | L`

## Pass 2 fallout (added 2026-08-03)

`2026-08-03 | Are the 16-bit ambientCG NORMAL maps harming the landscape?
| NormalDX/GL are 16-bit RGB on all five surfaces, `normal` IS in
DEFAULT_ROLES and is NOT in CONVERT_ROLES, so they are imported as-is
today. This is a DIFFERENT path from both known defects (those were
16-bit SINGLE-channel through TC_Alpha and TC_Masks; this is 3-channel
through TC_Normalmap) and it may well be fine. UNKNOWN, not cleared —
needs a render comparison against an 8-bit conversion, because R3 records
that a settings read-back passed for two sessions while the grass was
invisible. | S`

`2026-08-03 | Acquire a MEADOW GRASS ground surface | Pass 2 mandates five
surfaces and inventory holds four usable ones (Snow006, Rock051, Rock026,
Rock063, Ground037 — no meadow). Pass 2 ships four and this is the fifth.
Must come through R3 intake with a licence row, not be faked as a tint —
that is the v1.11 forest_floor hack and it is being superseded, not
copied. | S`

`2026-08-03 | Decide scree surface: Rock026 vs Rock063 by render | Measured
character only so far: Rock026 lighter (mean L 0.626, hi-freq 0.133),
Rock063 darker (0.451) and more fragmented (0.168). Rock063 is also
4096x2048 and RGBA where the others are 4096x4096 RGB, so tiling maths
that assumes square is wrong for it. Two statistics are a hypothesis, not
a choice. | S`

`2026-08-03 | Nanite state is UNKNOWN for all 38 palette assets | The
registry `NaniteEnabled` tag came back on NONE of the 940 meshes in the
three packs. Absent is not OFF. Pass 3 cannot claim "Nanite confirmed on
everything placed" without asking the editor directly. | S`

`2026-08-03 | R-STAMP / R12 / R-ATMO are unwritten for code that is
COMMITTED | composite_stamps.py, rock_scatter.py and atmosphere_solve.py
are in the repo with no recipe; rock_scatter.py's docstring cites
"RECIPES R12", which does not exist. The new-element rule is unsatisfied
for all three. R-STAMP is the most urgent because its output
(terrain/alpine_stamped.png) already exists and could be adopted by
mistake. | M`

`2026-08-03 | Acquire a dedicated SCREE / TALUS surface scan | Rock026 won
the scree ruling by DISQUALIFICATION, not on merit — Rock063 turned out to
be moss-covered vegetated bedrock. Rock026 is the only inventory candidate
of the right material class and carries recorded weaknesses: displacement
detail 0.00200 vs Rock051's 0.00623 (3.1x weaker, on the channel scree most
depends on) and low-frequency energy 2.07x Rock051 (most visible tiling at
2 km). A real angular-fragment scan beats it. R3 intake. | S`

`2026-08-03 | Rock063 as WET SHADED BEDROCK near drainage | Rejected as
scree because it is mossy — which is exactly right for permanently damp
rock beside watercourses. Different role, genuinely useful. Needs its 2:1
aspect (4096x2048) handled, since the builder uses a single scalar UV
divisor and would stretch it 2:1. | S`

## Pass 4 exit gates — tree defects from Ryan's visual review 2026-08-03

**These three together are why the forest reads "plastic" at mid-distance.
They GATE PASS 4's EXIT. Logged, deliberately NOT fixed this session.**

`RESOLVED 2026-08-04 — NO DEFECT REMAINS. See LESSONS "THE PALE ROOT FLARE WAS ALREADY FIXED". The flare is slot 3 `fir_tree_01_trunk_c`, which shares M_fir_bark with the trunk — there is no separate slot to be separately mis-bound, so the brief's premise has no referent. M_fir_bark audits clean (3 samplers, 0 mismatches); the bark atlas has NO pale region (max luma 146.6, 0.000 of texels above 150); the TWIG atlas is 74.4% flat background at luma 92.4, pale yellow-tan — the reported colour exactly. The pale flare was M_fir_bark sampling twig textures, fixed 2026-08-03. The review predates the fix.`

`SUPERSEDED 2026-08-03 | ROOT FLARE MATERIAL: flare geometry renders pale flat tan |
It is the BACKGROUND-OF-ATLAS colour, not bark. This is the SAME
MATERIAL-ROLE-BINDING DEFECT CLASS as the twig/bark incident (R3 REJECTED:
`texture_map` silently last-wins on a contested role, so M_fir_bark
sampled twig textures) -- different slot, same mechanism. Expect the root
cause to be a role binding, not a texture. When fixed, the SAMPLER AUDIT
EXTENDS TO ROOT-FLARE SLOTS EXPLICITLY -- the previous audit did not
enumerate them, which is why this survived. | M`

`2026-08-03 | ROOT FLARE GROUNDING: flares sit ON the surface like decals |
No intersection with the terrain, so the silhouette edge is a hard line.
Placement recipe (R4) needs a SINK-DEPTH parameter embedding the flare
base a few cm into the terrain, so displacement and grass break the edge.
Note this interacts with Pass 2: once the landscape material carries
height-blended displacement, sink depth must be measured against the
DISPLACED surface, not the vertex surface. | S`

`2026-08-03 | LOD COLOUR MISMATCH: trunks beyond ~50 m go uniformly pale |
The LOD/imposter tier is not colour-matched to LOD0 bark. Fix is LOD
material inheritance or an imposter re-bake. ACCEPTANCE TEST: a
continuous-zoom shot with NO VISIBLE COLOUR POP at any transition --
not a still at two distances, which is exactly the test that would pass
while the pop survives between them. Relates to the 730 m cull and the
imposter backlog item under aerial readability. | M`

`2026-08-03 | Cliff-source slope must be measured at LANDFORM scale, not
cell scale, now that detail_relief exists | The Pass 1 detail layer raised
slope>=50 from 6.66% to 9.15% of the map. Some of that is real cliff and
some is MICRO-RELIEF crossing the threshold -- +/-4.71 m ridges on 4 m
cells make locally steep pixels that are not cliffs. rock_scatter's
talus_deposit() uses `cliff_source_slope_deg` against cell-scale slope, so
detail noise can manufacture phantom rockfall sources. Fix: compute the
cliff-source test on a smoothed (landform-scale) slope field, or raise the
threshold with the change measured. Blocks nothing today; MUST be settled
before Pass 3 scatters talus meshes. | S`

`2026-08-03 | Candidate v3 terrain: RE-ERODE the adopted composition |
DEFERRED, NOT REJECTED (ruling 2026-08-03). Running hydraulic_droplets on
the adopted terrain and KEEPING the eroded height would carve drainage
through the newly stamped massifs, which may be exactly what elevates the
inter-massif traversal corridor from a gap between two lumps into a route.
It is a TERRAIN CHANGE and takes the full approval path: composition ->
hillshade render -> Ryan's confirmation. Judge it AFTER the region is
dressed, when there is something to judge the drainage read against. | M`

`2026-08-03 | Grass sub-surface: the forest-floor band selects 99.03% of its
own layer | Baked and MEASURED. The v1.11 band (120-640 m, feather 55) was
authored as a TINT over the Grass layer (0-730 m, slope 0-29). As a tint,
covering the whole layer is harmless. As a SURFACE SWAP it eliminates the
primary -- there is no meadow left, only forest floor. Three options: narrow
the band, INVERT it (forest floor becomes the Grass primary and meadow the
sub-surface at the band edges), or defer the Grass sub-surface entirely.
RULED 2026-08-03: DEFER. v1.11's tint stands; the Grass sub-surface path is
wired as a NO-OP (selector present, second surface absent) so the graph
structure is complete and testable now.
**When the decision is made, evaluate INVERT seriously alongside NARROW.**
99.03% coverage may be the selector telling us forest floor simply IS the
primary surface of a forested region, with meadow as the EXCEPTION in
clearings and the high band. The design question is which surface is the
rule and which is the exception; the coverage number is EVIDENCE, not only a
defect (CLAUDE.md non-negotiable 22). | S`

`2026-08-03 | PREREQUISITE of the forest-floor decision: intake a MEADOW-GRASS
surface | The band cannot be judged without a real second surface to judge it
against. Source: Megascans free tier, which carries alpine meadow surfaces.
**FIRST verify what is already claimed in the library — the state of Ryan's
Megascans library is a FACT TO CHECK, not to remember** (non-negotiable 17's
spirit: a record of what was claimed is not the state of the account). Then
intake through R3 with a licence row and a render proof. | S`

`2026-08-03 | Scree selector is too sparse and reads as an outline, not an
apron | Baked at saturation 0.25: 1.97% of the Rock layer, and the visual
(_verify/20260804_variant_selectors.png) shows thin curved bands at cliff
bases rather than talus cones. The deposition field is correct -- sources are
now landform-scale and the routing converged at 360 steps -- so this is a
SATURATION choice, not a physics error. Lower saturation widens coverage.
RULED 2026-08-03: **do NOT leave this as a backlog line — tune it IN-SESSION
during Pass 2's audit-and-sweep**, against the rendered apron, because
outline-becomes-cone is a VISUAL criterion and the sweep is the instrument
that shows it. Division of labour: physics PROVEN, saturation TUNED BY EYE,
exact final value LOCKED in the recipe. | in Pass 2 sweep`

`2026-08-03 | Route make_foliage_material (10 connects) and
make_layer_debug_material (30) through material_graph._ll_wire | The landscape
builder's 93 are done. connect_material_expressions returns false and connects
NOTHING on an unresolvable pin name, and the material still compiles clean
(MaterialEditingLibrary.cpp:928-943). Both remaining builders discard that
return. Each needs its own build-and-verify against the editor, which is why
they were not swept in the same commit. | S`

`2026-08-03 | Capture set has no CLIFF-FACE camera, and cross-capture frame
diffs are confounded | Triplanar could not be render-proved: no shot frames a
>=50 degree face, and diffing two captures is unusable as an instrument because
volumetric clouds and TAA move between runs (80% of forest_floor pixels changed
on a layer that is not even triplanar). Needs a camera aimed at a steep face,
added to frame_cameras, and used in the Pass 7 sweep. | S`

`2026-08-03 | The cliff_face camera frames a SHADOWED face | Terrain fills 54%
of frame and the cliff is genuinely framed, but it sits on the shaded side, so
surface detail is suppressed and the face reads as a smooth dark sheet. That is
confounded by lighting, not proof about the material. A LIT cliff camera (or a
sun-angle variant for the sweep) is needed before triplanar or detail_relief
can be judged by eye. Evidence: _verify/20260804_cliff_face_baseline.png | S`

`2026-08-03 | Scree aprons read as OUTLINES because of the deposit
DISTRIBUTION, not the saturation knob | Swept saturation against the cached
deposit: 0.25 -> 0.008 moves coverage only 1.97% -> 3.55% of the Rock layer.
The field is long-tailed; most Rock cells have near-zero talus supply whatever
the saturation. Widening aprons into CONES needs the PHYSICAL parameters --
longer runout_m (120 now), lower mfd_exponent (1.3 now, lower spreads more
laterally), or lower repose_deg -- and those live in the SHARED
foliage.rock_scatter block, so changing them moves Pass 3's talus MESHES too.
That is correct (they must agree) but it is a physical claim about this
terrain, not a tuning knob, and it wants a render of the mesh scatter beside
the texture before it is made. Settled at saturation 0.03 for now: 3.03% of the
Rock layer, a 54% increase, still a minority landform. | M`

`2026-08-03 | RESOLVED — Nanite state for the pass-3 rocks | Measured live on
all 13 admissible meshes: nanite_enabled = FALSE on every one. Definitive, not
absent. The registry tag was blank because a row without NaniteEnabled was
cached by an engine predating the tag (StaticMesh.cpp:6225 writes an explicit
"True"/"False"), i.e. "I could not look". Pass 3 does NOT enable Nanite —
that is a GPU-desktop recipe of its own, never a scatter side effect. | DONE`

`2026-08-03 | THE FAB REGISTRY'S `Materials` TAG IS NOT TRUSTWORTHY | 8 of 13
pass-3 rocks disagree with the live asset. Scree_001_A: registry says 12
material slots, the live mesh reports 1 slot / 1 section / 1 material instance
across three independent accessors. StaticMesh.cpp:6319 writes
GetStaticMaterials().Num() into that tag, so the tag MEANS slots — the cached
value is simply stale relative to the loaded asset. TRIANGLE counts, by
contrast, match live exactly on all five spot-checked meshes. So: registry
triangles TRUSTED, registry Materials NOT. Anything that budgets draw calls
from the registry must re-measure. | DONE (recorded)`

`2026-08-03 | Pass 3 budget should be re-derived on MEASURED LOD chains |
Every rock has a real 3-4 LOD chain, which the overnight ruling explicitly
assumed did NOT exist ("budget at LOD0-only until measured otherwise").
Measured LOD0->LOD3: boulder 4136->596, scree002b 11947->597, cliff
29154->1457 (5% of LOD0). The 4.0M rock ceiling was set against LOD0-only and
is therefore very conservative; re-derive it against the chains before the
talus pass, which is where the budget actually binds. | M`

`2026-08-03 | Cache the talus deposition field, keyed by a hash of its inputs |
`talus_deposit()` is deterministic given (heightmap, repose_deg,
cliff_source_slope_deg, source_smooth_m, runout_m, mfd_exponent) and costs
several minutes of MFD routing over 2017x2017 on this host. It is recomputed
from scratch on every `rock_scatter.py` run AND is needed by the Pass 2
material's scree sub-surface mask, which is the definition of a SHARED
physical fact (NN19) — so the two consumers should be reading one cached
artefact, not each re-deriving it. Cache to `terrain/` with the input hash in
the filename, and REFUSE a stale hash rather than silently recomputing or,
worse, silently using it. Blocks nothing; it costs iteration speed on every
Pass 3 tuning cycle, which is where the time is actually going tonight. | M`

`2026-08-04 | recover_state lists FT_Conifer but not FT_Boulder in foliage_types |
The `foliage_instances.by_mesh` block correctly reports both meshes (759 and
157,554), and save_level listed /Game/Foliage/FT_Boulder among the packages it
wrote, so the asset exists. Only the `foliage_types` enumeration missed it —
likely a filter or a scan that ran before the type was created. Harmless today
because the instance counts are the load-bearing record, but PROJECT_STATE is
the machine-recovered backing for the recipes, and a type list that silently
omits a real type is the kind of partial record that later reads as absence.
Find the filter and either fix it or state what it excludes. | S`

`2026-08-04 | save_level response exceeds the remote-exec deserialization limit |
A 1,330-package save returned a message the transport could not deserialize, so
the script exited 2 on a save that had SUCCEEDED (verified by a follow-up
dry-run: 1,330 dirty before, 0 after). The response echoes the entire dispatched
command back alongside a result that enumerates every package path, so the
report grows with the work and fails precisely when the operation was largest --
never in testing, where the set is small. Fix: return counts plus the first N
paths with an explicit truncation notice, full list on request, and stop echoing
the command. Until then, treat a deserialization failure from this script as
UNKNOWN, not as a failed save, and settle it with a dry-run. | M`

`2026-08-04 | One boulder of 759 sits 0.103 m off its expected ground offset |
verify_grounding reports every other instance inside a DERIVED allowance
(embed * scale * (1 - cos tilt)), and this one outside it. Not widened to
absorb it -- a tolerance chosen to make a test pass is not a tolerance. Likely
bilinear terrain sampling against a locally steep cell, but that is a
hypothesis, not a measurement. Settle it by tracing that single instance in the
editor against landscape collision, which is also the independent instrument
verify_grounding does not have. | S`

`RULED 2026-08-04 (Ryan) — ACCEPT THE PALE VERTICALS. This is the intended look of a low alpine sun, not a defect. Exposure stays solved against HORIZONTAL terrain at linear 0.32; sunlit trunks, cliff faces and boulder flanks render bright by design. Do NOT 'fix' this later by lowering sun.intensity_lux (the validator refuses it, and it would feed the atmosphere a false top-of-atmosphere value) or by lowering exposure.compensation_ev (that re-darkens the whole scene to correct one surface orientation). See R13 EXACT VALUES and REJECTED.`

`SUPERSEDED 2026-08-04 | REOPENED — sunlit VERTICAL surfaces render pale at a 12-degree sun |
Pass 4 exit gate 1 was closed on 2026-08-04 having disproved its stated cause
(a role binding). The cause is genuinely disproved -- M_fir_bark audits clean,
the bark atlas has no pale region, and the rendered trunk hue 1.000/0.904/0.754
matches bark (G<R) and not the twig background (G>R). But the SYMPTOM is
present in the corrected-sun frames: trunks read RGB 205.7/186.0/155.1, pale
cream, though 0.0% clipped.
MEASURED CAUSE: at 12 degrees elevation a sunlit vertical surface receives
58,550 lux against horizontal ground at 12,445 -- 4.7x. R13 solves exposure so
HORIZONTAL terrain sits at linear 0.32, which necessarily puts sunlit verticals
near the top of the range. The error scales as 1/tan(elevation): at 45 degrees
it vanishes.
THREE OPTIONS, NOT CHOSEN, because this is a LOOK decision: (a) expose for an
orientation-weighted mix instead of horizontal; (b) raise sun.elevation_deg so
the ratio falls; (c) accept pale verticals as the character of a low alpine
sun. Needs Ryan. | M`

`2026-08-04 | Pass 4 gate 3 (LOD colour pop) — measurement still OPEN, and the third
attempt died on RESOURCES not on method | The cameras are already in the recipe
(`lod_near` 40 m, `lod_far` 53 m, straddling the measured 46.3 m LOD0->LOD1
switch on an ISOLATED lit instance with a clear 6 m corridor). The retry under
corrected lighting was the right call -- the two earlier failures were an
intervening trunk and unsegmentable silhouettes in a 5x underlit scene, and
both causes are now gone. CORRECTED: it did NOT die. `capture.py` ran to completion, waited the full
**900 s per camera**, reported `FAIL: screenshot did not appear within 900s
(engine task_done=False)` for ridge_wide and diag_oblique, then STOPPED ITSELF
after two in-editor failures citing conduct rule 6, and exited **5**. Zero frames
were written. The trigger is the lighting change invalidating the shader cache;
1.10 GB free RAM is context that plausibly slows the recompile, but the reported
mechanism is a screenshot that never arrives, not an out-of-memory kill.
NEXT SESSION: run `capture.py --filename-tag lodpop3` FIRST, on a fresh boot
with the browser closed, before anything else touches the editor. The shaders
will already be warm from this session's compile if the DDC survived. Then
measure tree pixels in each frame -- with correct lighting the trunks are
bright (205/186/155) against darker background rather than silhouettes, so a
luminance threshold finally separates them.
WHAT IS ALREADY KNOWN, so it need not be re-derived: the pop is NOT a lost
section (all 4 LODs carry all 4 sections and both materials); the switch is at
46.3 m; the step drops 505,494 -> 126,374 triangles (-75.0%). | M`

`RESOLVED 2026-08-05 - MEASURED 1.4%, NOT A DEFECT. The framing IS achievable; the
"impossible" verdict below used an underived `score > 12` threshold instead of a
projection test. A proper cylinder-occlusion search found clear subjects immediately.
Measured on instance 325 with HUE segmentation: LOD0 side (40 m) luma 188.6, LOD1
side (53 m) luma 191.3 - delta +2.7, +1.4%, hue unchanged. The reported "trunks
beyond ~50 m go uniformly pale" is the pale-verticals effect ruled ACCEPTED in R13
2d, present at ALL ranges rather than at a transition. Caveat: one subject, and the
25-deg frame clips the tree differently at the two distances.`

`SUPERSEDED 2026-08-05 | Pass 4 gate 3 — the two-camera framing is IMPOSSIBLE, use a difference render |
MEASURED over all 85,569 lit conifers: the best achievable framing for a 40 m /
53 m camera pair has 12.43 m clearance at the near camera, 21.96 m at the far,
and only **4.00 m along the sight line** — against a conifer canopy radius of
~3.15 m, and that best case is at the map corner where density is lowest. At
24.2 stems/ha you expect 4.8 neighbours within 25 m. Four capture attempts
failed on four different proximate causes; the approach itself cannot work.
`lod_near`/`lod_far` REMOVED from the recipe.
DO INSTEAD: render the subject with and without the instance and difference the
frames — isolates the tree exactly, needs no clearance, works in a dense stand.
Mutates the world, so use a scratch level or a tagged restore point.
ALREADY KNOWN, do not re-derive: not a lost section (all 4 LODs carry all 4
sections and both materials); switch at 46.3 m; 505,494 -> 126,374 tris. | M`

`2026-08-05 | Pass 2 exit gate — the ground-to-2 km sweep, DESIGNED but NOT CAPTURED |
This is also the raw material for Pass 7 clip, so it is worth running properly.
DESIGN (regenerate exactly, do not re-derive): target = highest summit within
1 km of map centre, so a 2 km pull-back stays on the map; six stations at 60,
150, 350, 700, 1200, 2000 m along bearing 105 (the MEASURED sun bearing, so the
face under test is lit rather than terrain-shadowed); each camera at 1.7 m eye
height above its OWN local terrain — the placement rule that fixed the trunk
framing — aimed 20 m above the summit; fov 50.
For the run of 2026-08-05 the summit resolved to (-844.0, -1040.0) m at z
1406.7 m, and the six camera heights were 1350.0 / 1257.4 / 975.6 / 577.1 /
568.5 / 645.5 m.
WHAT HAPPENED: the capture terminated without completing. The log ends mid-way
through the FIRST camera (ridge_wide, which had succeeded twenty minutes
earlier), with no summary block and no exit code, and zero frames written. RAM
was 3.08-3.21 GB free throughout and the editor stayed alive at 978 MB, so the
memory explanation that fitted an earlier failure does NOT fit this one.
CAUSE NOT ESTABLISHED — recorded as unknown rather than guessed.
NEXT: re-run capture on a FRESH editor before anything else touches it. A
second stall on a camera that worked minutes before is a reproducible
editor-side condition and deserves a diagnosis, not a third retry. | M`

`RESOLVED 2026-08-06 — AND TWO CLAIMS IN THE ENTRY ABOVE ARE WRONG. Read this
before believing it. Settled from the EDITOR's own logs, which were on disk the
whole time; the entry above was written from a file listing and a process
reading. There were TWO runs, and neither is a capture.py defect.
RUN A (tag `sweep`, stamp 20260805T024527Z), from
LandscapeLab-backup-2026.08.05-02.54.43.log:
  31251  02:53:42:678Z  screenshot saved ... ridge_wide ... _sweep.png
  31261  02:53:45:995Z  screenshot saved ... diag_oblique ... _sweep.png
  31303  02:54:26:031Z  Engine exit requested (UUnrealEdEngine::CloseEditor())
TWO FRAMES WERE WRITTEN — "zero frames" is FALSE, and both files are on disk.
No fatal in that log. The editor was CLOSED, from the UI, 40 s after the second
frame, with 11 cameras still to go. The run did not stall; it was terminated.
RUN B (session 02:55:06Z-03:36:23Z): grep for "High resolution screenshot"
returns ZERO hits in the whole log — nothing was ever written. It ends at
03:36:13:629Z with EditorServer.cpp:1951 "World Memory Leaks: 1 leaks objects
and packages", Script Stack /Script/LevelEditor.LevelEditorSubsystem.LoadLevel.
THE EDITOR DIED — "the editor stayed alive" is FALSE. That crash is a complete
explanation for "log ends mid-way, no summary block, no exit code": the
script's remote connection died with the editor it was talking to.
STILL UNKNOWN, and left as such: why run B produced zero frames in the ~40 min
BEFORE the crash. Candidate documented and never fixed — LESSONS 14.7, shots do
not service unless the editor is the FOREGROUND application.
The crash itself is now FIXED at the choke point (RECIPES R17 REJECTED,
gc.collect-as-the-whole-guard) and the sweep ran 19/19 twice on 2026-08-06. |
DONE`

`RESOLVED 2026-08-05 (ruling) | Pass 5 SCOPED to ground clutter | Small rocks,
deadfall, debris at foot level from the MEASURED KiteDemo palette, as new species
through R12 machinery, judged at ground scale. Density philosophy RULED: sparse and
clustered beats uniform — clutter gathers under trees, along drainage, at cliff
bases, and the deposition and flow fields are legitimate placement priors rather
than white noise. Pass 5 is no longer an undefined title. | M`

`2026-08-05 | Dry Fallen Leaves surfaces (Quixel free tier) as forest-floor upgrade
candidates | Named future line, per ruling. Not intaken. The current forest floor is
a TINT on the Grass layer; a real fallen-leaf surface would let the forest-floor
sub-surface carry its own albedo and normal rather than modulating another
surface. Evaluate after the Wild Grass meadow intake settles the INVERT-vs-NARROW
question, because that decision determines whether forest floor is the PRIMARY of
the layer or its exception. | M`

`2026-08-05 | BLOCKER — Wild Grass and Uncut Grass are NOT in the project | Searched
exhaustively: Content/Fab/ contains ONLY the Megascans base material library
(14 M_MS_* masters, 28 QMF_* material functions, 6 T_Default* placeholders,
5 VT variants) — the shared dependency the Fab plugin installs when ANY Megascans
asset is added. It contains ZERO surface content. No asset matching *wild*, *uncut*,
*MS_* or *megascan* exists anywhere under Content except one MAWI plant master.
The other two items DID land: Content/Pack_Bonus/ (Lord Enot stylized, Grass_1/2/3
+ Stone + Tile + Wall + Wooden_Floor, 5 maps each) and
Content/MWLandscapeAutoMaterial/ (MAWI, with Landscape/Desert+Island+MountainRange
examples).
CONSEQUENCE: the meadow intake cannot start, so the Grass INVERT-vs-NARROW decision
cannot be made, so under the standing sequencing constraint the FINAL SWEEP is
blocked behind it. Everything else in the ruling set is unblocked.
NEEDS: add Wild Grass and Uncut Grass to the project from the Fab library (they are
likely acquired-but-not-added-to-project, since their dependency library installed). | S`

`CORRECTED 2026-08-05 - THE ENTRY BELOW IS WRONG. `scripts/open_level.py` already
exists and already root-caused this crash TWICE from the log, with a working fix:
`gc.collect()` to release Python `unreal.World` wrapper refs immediately before
`load_level`, atomically with the guard that had to read the world. load_level IS
callable from a payload - through that tool. My ad-hoc payload called
`get_editor_world()`, which is exactly the reference open_level.py's docstring
names as fatal. ROOT CAUSE WAS MINE: operating-loop step (a), freelancing on a
solved problem. Command-line map remains a fine way to START in a level; it is
not the only way to CHANGE level. USE `scripts/open_level.py`.`

`SUPERSEDED 2026-08-05 | NEVER call load_level from a remote-exec payload — it FATALS the editor |
`LevelEditorSubsystem.load_level("/Game/Alpine")` from Python killed the editor with
`Fatal error: EditorServer.cpp:1951 — World Memory Leaks: 1 leaks objects and
packages`, PythonScriptPlugin.dll in the callstack. load_level tears down the
outgoing world then asserts nothing references it, and THE EXECUTING PYTHON FRAME IS
A REFERENCE — the payload runs inside the world being destroyed, so the check cannot
pass and the engine aborts. Not memory pressure: 7.58 GB was free immediately after.
CORRECT FORM: pass the map on the COMMAND LINE at launch —
`UnrealEditor.exe "<project>.uproject" /Game/Alpine` — so there is no teardown.
GENERAL: an operation that destroys the context its own caller runs inside cannot be
driven from that caller. Level switch, project switch, engine restart are LAUNCH-TIME
arguments, not runtime calls. | S`

`2026-08-05 | Provenance settled: water folders are MW-sourced; ThirdPerson UNKNOWN |
`Content/watermaterials` (83 assets) and `Content/WaterPlane` (31) both date
2026-08-03 22:22, one minute after `Content/MWLandscapeAutoMaterial` (97 assets) at
22:21 — same install session. Folded under MW REFERENCE-ONLY per ruling.
`ThirdPerson` (6) and `ThirdPersonBP` (4) date 2026-08-02 21:26, the project-creation
era, consistent with Ryan's guess of a template-picker creation — but that is his
guess, not provenance, and it stands UNKNOWN until traced. Neither is referenced by
any recipe. | S`

`2026-08-05 | Surface-coherence instrument needs a photoreal specimen PER MATERIAL
FAMILY | `scripts/surface_coherence.py` is built and REFUSES on its own calibration
set: no feature separates photoreal from stylized, gap 0.0000 on all three, stylized
range entirely inside photoreal range. Diagnosis TESTED, not assumed: the photoreal
class spans snow (palette 2.11) to ground (9.51) and its within-class spread (1.47 /
0.70 / 7.40) dwarfs a zero between-class gap. MATERIAL IDENTITY DOMINATES AUTHORING
METHOD in appearance statistics — NN22 in a new costume, the statistic is only
meaningful conditioned on material.
Controlled grass-vs-grass, 2 of 3 features DO separate consistently (spec_slope
1.1224 vs [1.1422,1.4857]; norm_hf 0.6509 vs [0.7521,0.8574]), so the signal is real
and was being drowned.
FIX: one photoreal calibration specimen per material family. Today only grass has
one and it is the HOLDOUT, so promoting it to calibration destroys the only
acceptance test. Needs more photoreal surfaces (the Quixel free tier is the obvious
source), not more features.
CONSEQUENCE: Pack_Bonus stays VERDICT-PENDING. Exclusion is still expected but is
NOT recorded, because recording it would rest on my judgement rather than the
instrument — the exact problem the instrument exists to remove. | M`

`2026-08-05 | BLOCKER REPEATED — the six calibration surfaces did NOT land |
Searched exhaustively: ZERO .uasset files newer than the last catalog sweep
anywhere under Content; no new top-level folders; `Fab/Megascans/Surfaces/` still
holds only Wild_Grass_sfknaeoa and Uncut_Grass_oilpt20; the only dirt/leaf assets
are pre-existing Atlantis_Ruins and DragonCave content. The Megascans library
index `Downloaded/UAssets/uassetsData.json` is 25 bytes and reads
`{"assets": [], "version": 1}` -- an EMPTY asset list, so the library itself
believes nothing was downloaded.
SAME PATTERN AS THE FIRST WILD GRASS ATTEMPT: the shared dependency library
installs, the asset payload does not. That was fixed by re-running ADD TO PROJECT
from inside the LandscapeLab editor (Download only fetches to the local library).
NEEDED: 3 grass (not Wild), 2 fallen-leaves/forest-floor, 2 dirt/soil. Surfaces,
High tier, basecolor+normal minimum. | S`

`2026-08-05 | Dependency manifest does not exist -- creating it upgrades H12 |
Standing rule 5 says record any dependency added to the Python environment, and
there is no requirements.txt, pyproject.toml or environment.yml in this repo. A
RULE WITH NO ARTEFACT TO WRITE TO IS UNENFORCEABLE BY CONSTRUCTION. The H12 hook
reports that absence rather than nagging, which is the correct degrade. When a
manifest is created, H12 UPGRADES from advisory to recording -- it can then verify
the package was actually written down instead of only asking. | S`

`2026-08-05 | CAMPAIGN OPEN ITEM — background migration + native completion signal |
The one piece of the governance campaign designed around rather than delivered,
named rather than buried. Long probes still run through ad-hoc run_in_background
calls; the liveness protocol does not consume the native completion notification.
Sized and scheduled on its merits, not smuggled into "done". | M`

`2026-08-05 | Pack_Bonus families are mostly MAN-MADE, so only 2 of 5 pair with ours |
Pack_Bonus ships grass, stone, tile, wall, wooden_floor. Our natural-surface set is
grass, rock, snow, ground. Only GRASS and STONE have counterparts, so the coherence
instrument can only ever be calibrated for those two families against this stylized
set. Pairing Ground037 (natural gravel) against Tile_1 (man-made tile) produced an
apparent norm_hf direction inversion that is a MIS-PAIRED FAMILY, not a
counterexample -- the family must actually match or the comparison measures
material, not authoring. Judging a stylized DIRT pack would need a stylized dirt
specimen we do not have. | M`

`2026-08-05 | Coherence instrument: GRASS does not separate at n=4; verdict still
withheld | With 4 photoreal grasses (Cut, Lush, Clover, Uncut) vs 3 Pack_Bonus,
ALL THREE features overlap. The n=1 apparent separation was an artefact -- a single
point cannot overlap a range. ROCK separates (spec_slope 1.08 SD, norm_hf 1.31 SD)
but its only stylized specimens are its own calibration set, so no verdict is
issuable there either. norm_hf direction (photoreal LOWER) holds in both paired
families as a MEAN tendency, not a range separation.
NEXT: either a feature that separates grass (the current three do not), or accept
that appearance statistics cannot do this job and rule the coherence check by
PROVENANCE instead -- vendor + capture method -- which is checkable and honest.
That is a design decision for Ryan. | M`

`2026-08-05 | 7 calibration surfaces intaken for CALIBRATION USE ONLY | Under
Content/Fab/Megascans/Surfaces: Clover_vlzlbjon, Cut_Grass_sfenffsa,
Dirt_Ground_xdhhdgq, Dry_Fallen_Leaves_vetladiaw, Forest_Floor_sfjmafua,
Lush_Grass_xbrffjd, Soil_Mud_pjuph20. All High tier, B/H/N/ORM except
Dry_Fallen_Leaves which has NO _H (4 maps) -- it cannot feed the HeightLerp path
without one. basecolor+normal exported to Free/_intake/calib. NOT R-ASSET intaken,
no ASSETS.md rows, not wired -- calibration inputs only, per the brief. | S`

`2026-08-05 | BLOCKER — make_landscape_material payload: NameError _ramp is not
defined | The material builder FAILS ON EVERY RUN, including with the recipe
reverted to its last-known-good state, so this is PRE-EXISTING and not caused by
the Wild Grass wiring. `_ramp` is defined at make_landscape_material.py:1696 but
the generated payload calls it at payload line 323 -- defined after use, or emitted
in a template branch that did not fire for this configuration.
EDITOR STATE RIGHT NOW: /Game/Materials/M_AutoLandscape is EMPTY IN MEMORY AND
DIRTY. The copy ON DISK IS STILL GOOD. **DO NOT Save All and do not save the
level** until a clean build has rewritten the graph -- saving now would persist
the empty material over a good one. Discarding (closing without saving, or
reloading the asset) restores it.
FIX FIRST NEXT SESSION, before any material or sweep work. | S`

`2026-08-05 | Wild Grass wiring is READY but NOT APPLIED | recipes/alpine.json was
set to Grass.sub_surface.surface = "WildGrass", validated clean (0 violations),
and REVERTED to null only because the builder is broken for unrelated reasons. The
one-line change is the whole wiring; re-apply it once _ramp is fixed, then the
INVERT-vs-NARROW evaluation can finally run against a real meadow. | S`

---

## PROPOSAL — MEADOW EXPANSION VIA A CLEARING FIELD (2026-08-06)

**STATUS: PROPOSAL AWAITING RATIFICATION. NOT EXECUTED. Nothing below
has touched the recipe, the bakes, or the editor.** Offline analysis
only; the instrument was validated against commit a93c1e8b's recorded
numbers before predicting anything (Grass layer 44.16% exact, selector
98.13% weighted exact, meadow share 1.87% exact).

**Ruling honoured:** 1.87% of layer / 0.41% world REJECTED as
insufficient; aerial readability is first-class; the fix is a WIDER
BAND and/or a DIFFERENT SELECTOR — **never another surface swap.**
(Measured note on the 0.41%: with the denominator stated — pixels where
Grass weight > 0.5 AND baked selector <= 0.5, over the whole map — the
figure is 0.43%. Same instrument family, same verdict: under half a
percent of the world.)

### The current meadow, measured (baked artefacts, 2026-08-06)

    meadow share of Grass layer (weighted)   1.87%
    meadow world%  (hard mask / weighted)    0.43% / 0.83%
    patches 757, of which >=1 ha: THREE, >=5 ha: ONE (9.2 ha)
    median patch ~single pixels; total meadow 28 ha

One readable meadow in the entire world. From the air the Grass layer
reads as unbroken forest.

### Why widening the BAND EDGES alone is the wrong instrument

Modelled (band feather 55-80 m):

    150-600 m:  4.65% of layer, 3,651 patches but only 16 >= 1 ha
    180-560 m:  8.14%,          6,309 patches,        28 >= 1 ha
    220-520 m: 16.42%,          9,534 patches,        51 >= 1 ha

The area arrives as thousands of contour-following slivers at the band
edges — elevation fringes, not meadows. From the air that is banding,
not a mosaic. And it re-introduces the exact objection that rejected
NARROW in a93c1e8b: it severs the 120-640 m band from the physical
forest band it models, tuning a physical value to hit a coverage
number. **REJECTED as the primary mechanism.** (A small trim remains an
option if Ryan wants valley/upper fringes specifically; numbers above.)

### PROPOSED: keep the band physical, add a DIFFERENT SELECTOR — forest
### clearings

Real subalpine forest carries clearings (soil, water table, deadfall);
a clearing field is a physical statement, not a coverage tune. The
selector becomes:

    forest_floor = band(120, 640, feather 55)  x  (1 - clearing)
    clearing     = smoothstep((noise - threshold) / edge + 0.5)

**Exact proposed values** (new recipe block; name and home to be
ratified — proposed `foliage.meadow_clearings`, mirroring the
`foliage.rock_scatter` precedent of one shared block read by every
consumer, NN19):

    seed              20260806
    feature_scale_m   450.0      value noise, coarse grid ~ map/112 px,
                                 bicubic upsample, min-max normalised
    open_fraction     0.14       threshold = quantile(noise over Grass
                                 layer > 0.5, 1 - open_fraction)
    edge              0.06       smoothstep half-width in noise units
    band unchanged    120-640 m, feather 55 — NOT retuned

**Predicted numbers** (modelled offline on the adopted heightmap and
baked weightmap, 2017 px, 4 m spacing):

    meadow share of Grass layer (weighted)  15.83%
    meadow world%  (hard / weighted)         6.64% / 7.00%
    patch structure: 58 patches >= 1 ha, 18 >= 5 ha, 4 >= 20 ha,
                     largest 44.7 ha; total meadow ~432 ha
    (a sliver population at the band feather persists — the READABLE
    set is the >=1 ha patches, and that is the honest count to judge)

Smaller alternative if 16% reads as too open once rendered:
`feature_scale_m 350, open_fraction 0.10` -> 11.77% of layer / 4.84%
world, 60 patches >= 1 ha, 16 >= 5 ha, largest 17 ha.

### The % believed to achieve readability, with the reasoning shown

**Target: ~15% of the Grass layer (~6.5% of world), delivered as tens
of compact patches >= 1 ha rather than fringe area.** Reasoning per
scale:

- **Sweep near stations (60-350 m eye):** a >= 1 ha patch is ~110+ m
  across — walkable open ground with a visible far edge. 58 such
  patches vs 3 today.
- **Sweep far stations (1200-2000 m):** a >= 5 ha patch (~250 m) subtends
  ~7 deg at 2 km — an unmistakable break in the canopy. 18 such vs 1.
- **Aerial/airship altitude:** the Grass layer spans ~28.7 km2 (44.16%
  of the 8.07 km map). 18+ patches >= 5 ha is ~0.6 sizeable meadows per
  km2 of forest — a mosaic in every aerial frame. Subalpine
  forest-meadow mosaics run ~10-30% open; 15% sits inside the physical
  range, toward the forested end, which matches WORLD_VISION's dense
  alpine reading.
- At the current 1.87% there is ONE >= 5 ha meadow in the world; no
  aerial frame not aimed at it can read "meadow" at all.

### What is invalidated — ESTABLISHED vs ASSUMED, per artefact

- **Variant map**: re-baked (`make_variant_map.py` gains the clearing
  term) and `T_Alpine_Variants` re-imported at the same asset path.
  ESTABLISHED: the band is baked into the texture, not the shader
  (make_variant_map.py docstring; R2 baked-for-selection), so the
  MATERIAL GRAPH DOES NOT CHANGE. Verify at execution with the graph
  assert (EXACT) plus a render, per increment discipline.
- **Conifer placement — INVALIDATED BY DESIGN, and this is the real
  cost.** ESTABLISHED at place_foliage.py:207-213: acceptance reads the
  WEIGHTMAP channel x species slope/height band and never the variant
  map, so the pipeline would happily leave all 157,554 trees standing —
  including ~14.2% of acceptance mass inside the new clearings
  (measured against the proposed field). A meadow with 24 trees/ha on
  it is not a meadow FROM THE AIR — aerial readability is canopy
  absence, not ground texture. So the Conifer acceptance must subtract
  the SAME shared clearing field (NN19: one declaration, N readers),
  and placement re-derives: predicted ~135,209 instances (-22,345).
  Re-derivation drags: re-place (orphan-sweep discipline per the
  scatter-placement skill), verify_grounding re-run over every
  instance, capture, R5 VERIFICATION update, sun_exposure stats shift.
- **NN19/NN24 flag, pre-existing:** the 120-640 m forest band lives
  TWICE in the recipe — material.forest_floor.height_m AND species
  Conifer.height_m. This proposal keeps both values unchanged, but
  ratification should also rule on deriving them from one declaration;
  adding a third consumer (the clearing field) makes the drift hazard
  worse, not better.
- **Boulders: NOT invalidated.** ESTABLISHED at rock_scatter.py:346-385
  — the hero `layer` mask reads the baked WEIGHTMAP channel, slope,
  height band and talus exclusion; it never reads the variant map, and
  the weightmap is untouched. The 759 boulders stand.
- **Weightmap, terrain, landscape layers, Snow/Rock selectors: NOT
  touched.** The R and G variant channels re-bake bit-identical (R is
  declared inert zero; G's talus inputs are unchanged and the deposit
  is cached).
- **ASSUMED, needs a check at execution: the landscape grass system.**
  If GT_alpine_Meadow tuft spawning keys off the Grass LAYER weight it
  is unchanged; if anything keys tuft density off the forest-floor
  SELECTOR, clearings would also change tuft distribution. Not
  established this session — verify against the material graph before
  adopting.

### Execution order, when ratified (one session, M)

1. Shared block into recipes/alpine.json + schema bump; refuse-if-absent
   in both consumers (fail closed, the rock_scatter precedent).
2. `make_variant_map.py` clearing term; re-bake; coverage print states
   both denominators; re-import texture; graph assert + render.
3. `place_foliage.py` Conifer acceptance subtracts the shared field;
   re-place behind a named tag (risky-op checkpoint — mass foliage
   regeneration is on the checkpoint list); verify_grounding; capture.
4. Judge meadow readability at both sweep scales from the next sweep's
   renders, per the standing instruction in CURRENT STATE.

| est. size M | owner: ratification is Ryan's (world-design call) |

`RESOLVED 2026-08-06 (ruling, attended) | GPU frame cost measured; clouds
ruled | Measured in the editor viewport at two sweep stations: sweep_2000
GPU 94.45 ms (Frame 100.12, 1485 draws, 331.3K prims), sweep_0060 GPU
75.71 ms (Frame 80.13, 1255 draws, 302.8K prims). GPU-bound at both, Game
12-14 ms idle-waiting, VRAM 3.8/8 GB, draws modest -> cost is PER-PIXEL
SHADING, not scene bloat. CALIBRATION CLASS binds every citation: editor
viewport, Intel iGPU, 971x752, RenderRes 100%, editor perf config; NOT
shipping, NOT PIE, NOT the 5080. CLOUDS split: OFF in the interactive
editor as standing config; PERMITTED in offline renders, conditional on
measuring the per-frame render-time delta at first enablement. RE-OPEN on
5080 arrival. Pass 6 back half unblocked. Full text: RECIPES R13
ADDENDUM. | DONE`

`2026-08-06 | URGENT — an UNDECLARED VolumetricCloud actor is in the level,
and the GPU measurement was taken WITH IT PRESENT | Found by the pass audit.
The clouds ruling (R13 ADDENDUM: OFF interactive, PERMITTED offline) rests on
sweep_2000 94.45 ms / sweep_0060 75.71 ms — if that actor is ACTIVE those are
not a clouds-off baseline and the ruling was taken against a contaminated
number. Outcomes: ACTIVE -> interactive headroom is better than believed,
re-take the ruling on a clean baseline; INERT -> bookkeeping only, ruling
stands, declare the actor; UNREADABLE -> say so, do not assume inert. Blocks
Pass 6 back-half atmosphere work, which is unblocked on the strength of those
numbers. | S`

`2026-08-06 | Pass 2's "43/43 sampler audit" carries 31 results from the
WRONG-TERRAIN sweep | Audit verdict OPTIMISTIC (a CONFIRMED overturned on
refutation). No dated artefact, and absent from the ledger built to catch
exactly this. Also: the material graph is proven PRESENT, never proven
CONNECTED — a different claim. Re-run on the corrected world. | S`

`2026-08-06 | Pass 7's gate has FOUR open items, not three | The omitted one is
a STATION-SITING DEFECT that cost 2 of 6 stations (sweep_0060/0150 sit in
terrain shadow — "the lit sector is a bearing check, not a shadow march").
SWEEP_REPORT §6 undercounts. | S`

`2026-08-06 | Pass 0's palette metadata contradicts the live assets | 38/38
assets are real with exact triangles/bounds, but material_slots disagrees on 8
of 13 checkable entries (up to 12x), nanite is stale UNKNOWN, and one entry's
"not spawned" is false. Also: the VERIFICATION half of "Verification + palette"
has zero instances — decide whether DONE is the right word. | M`

## Added 2026-08-08 — from the unattended-work audit (LESSONS Division 6, entries of 2026-08-08)

`2026-08-08 | B-APPEND-GUARD: nothing enforces LESSONS.md's append-only property
| CLAUDE.md has said "Never delete from it" since the constitution was written,
and commit 538e2903 — message "Appended LESSONS.md with a one-line entry" —
took the file from 11,434 lines to 35. The rule lived in prose with nothing
behind it. Pre-commit check: assert the previous content is a PREFIX of the new
content, not merely that the line count did not fall (a guard that only counts
lines is satisfied by deleting 100 and adding 101 — non-negotiable 1 and 2).
Same guard on RECIPES.md. PREFERRED SHAPE per non-negotiable 3: an
append_lesson.py that can only concatenate makes the catastrophic value
unreachable; the guard is the fallback for hand edits. Prove it three
directions. | S`

`2026-08-08 | B-VERIFY-HASH: verification artefacts do not name the bytes they
audited | 236358db claimed "sampler audit and graph connectivity passed" for
M_AutoLandscape; newest artefacts in _verify/ were dated 20260806 and the
material was rebuilt 20260808 15:59. SECOND OCCURRENCE IN THE SAME PLACE — the
2026-08-06 pass audit already caught "43/43 samplers" carrying 31 from the
previous wrong-terrain sweep. Logged once, recurred in 72 hours, so this is an
unenforced lesson rather than an accident (non-negotiable 4). Fix: every audit
output records the SHA-256 of the .uasset it read, and any reader asserts that
hash against the file on disk before quoting the result. A date is not an
identity. Applies to audit_material_samplers, audit_material_connectivity,
measure_palette_live, read_instance_transforms — so it is shared
infrastructure on first duplication, not per-script (4a). | M`

`2026-08-08 | B-PLAN-PROVENANCE: placement plans do not record the recipe that
produced them | alpine_Conifer.json went 157,554 -> 232,389 with every row
re-seeded because one leaf of alpine.json moved 68.0 -> 100.0. Nothing in the
plan records which recipe state generated it, so the divergence was only
visible via a hand-written semantic JSON diff against HEAD. Add
source_recipe_sha256 + schema_version + seed to every generated plan, then let
verify_grounding and friends REFUSE a plan whose recipe hash does not match the
recipe on disk. This is R-STAMP's adoption discipline (non-negotiable 20)
applied to placements instead of heightmaps. | M`

`2026-08-08 | B-IMAGE-PAIR: one shared load_comparable_pair() for the image
tools | compare_images.py refuses a size mismatch; visual_diff.py silently
LANCZOS-resampled one image to fit the other and then reported the difference
as though the frames were comparable. visual_diff.py is FIXED to refuse, but
the precondition is now written TWICE, which is non-negotiable 24 exactly, and
4a promotes a trap class to shared infrastructure on its SECOND tool, not its
third. One helper used by both, returning two arrays or raising. Put the
measured capture noise floor (1.2-3.5% mean|diff| between identical-settings
runs, 2026-08-06) in its docstring — every consumer needs it to read its own
output. | S`

`2026-08-08 | B-DENSITY: adopt or discard the 68 -> 100/ha conifer density |
Preserved on branch density-100-experiment-20260808 (232,389 instances, world
saved 1,327 packages). REVERTED from main 2026-08-08 because it carried no
verification and invalidated every Pass 4 proof. To adopt: tag a restore point;
re-run verify_grounding.py, trace_grounding.py --n 500 and
read_instance_transforms.py against the new placement; take an attended GPU
reading against the 75-94 ms baseline; then update CURRENT STATE,
VERIFICATION.md and R5's counts IN THE SAME COMMIT. The count appears in at
least four records — updating one and leaving the others is the trap
non-negotiable 24 describes. ATTENDED. | M`

`2026-08-08 | B-FF16: the FF16 visual-fidelity direction — SCOPE, NOT RATIFIED |
Unattended work produced ff16_aaa_upgrade_plan.md and
ff16_visual_gap_analysis.md proposing an upgrade toward Final Fantasy XVI
fidelity: understory vegetation and multi-layer canopy, volumetric cloudscapes,
ground clutter, micro-surface displacement blending, cinematic colour grading
with soft contact shadows. MOVED to _trash/ff16_plans_20260808/ because it is a
SCOPE CHANGE (CLAUDE.md escalation 1, Ryan's call) and because as written the
documents read as a plan of record while carrying unverified state claims —
they assert volumetric clouds are "currently disabled/inert" where
read_cloud_state.py measured them ACTIVE on 2026-08-06, corroborated by a full
cloud deck in our own published frame. TWO PARTS NEED NO NEW RATIFICATION:
ground clutter is already Pass 5 (scoped 2026-08-05, RECIPES.md:3030), and
conifer density is B-DENSITY above. The rest is genuinely new scope — do not
begin it without a ruling. Standing constraint: every item costs GPU time on an
integrated GPU already at 75-94 ms, on a machine that has lost its driver to a
timeout once. | L`

`2026-08-08 | The world revert is INCOMPLETE ON DISK — blocked by the running
editor | recipes/alpine.json and foliage/alpine_Conifer.json are reverted to
68.0/ha and 157,554. The 1,327 __ExternalActors__ packages and
M_AutoLandscape.uasset are NOT: git checkout fails with "unable to unlink old
... Invalid argument" because UnrealEditor PID 6008 (started 20260808 15:55)
holds the package files open. HEAD and the index are already correct; only the
working tree is stale. The editor also holds the 232,389-conifer world IN
MEMORY, so it must be closed WITHOUT SAVING before the checkout is re-run —
saving would rewrite the density version back to disk. Sequence: close editor
without saving -> git checkout -- 'LandscapeLab/Content/__ExternalActors__'
'LandscapeLab/Content/__ExternalObjects__'
'LandscapeLab/Content/Materials/M_AutoLandscape.uasset' -> verify one sampled
package is 34,293 B -> reopen with scripts/open_level.py. ATTENDED. | S`

`2026-08-08 | check_collision_truth's default --n 100 can FAIL a correct world |
On the freshly-reopened, verified-correct world, seed 7 at n=100 returned p90
0.317 and printed "THE LANDSCAPE DOES NOT COLLIDE WHAT IT RENDERS"; the same
seed at n=500 returns p90 0.189. p90 from 100 samples is the ~10th largest
draw, and the true p90 (~0.185 m) sits close enough to the 0.30 m bar that the
estimator straddles it. A gate's sample size is part of its threshold, not a
performance knob. Fix: derive n from the margin, or report a CI and refuse a
verdict when it crosses the bar (non-negotiable 6 applies to precision, not
only to access). The 0.30 m threshold's own derivation is not in the repo
either, so this wants deriving rather than nudging. UNTIL THEN --n 500 is the
honest setting and a bare n=100 result near the bar is evidence in neither
direction. | S`

`2026-08-08 | Pass 1's per-component scope is STILL open after the SAVED clause
closed | The cold-reopen traces (n=500 x2, p90 0.182/0.189 m vs v2) are uniform
over the map, not stratified to guarantee at least one trace inside each of the
256 proxy extents. Broad staleness is excluded; per-proxy completeness is not.
A stratified variant closes it. | S`

`2026-08-08 | The ridge_wide single-camera capture wants a camera entry, not a
second recipe | recipes/alpine_ridge_rerun.json declared its OWN copy of
landscape location/scale/z_scale, the heightmap source and the parent material
alongside its one camera -- so alpine.json could move and the rerun would keep
capturing against stale geometry, silently. That is non-negotiable 19 exactly:
pass boundaries organise work, they do not partition truth, and a landscape
transform is a physical fact defined once. Unreferenced by any script, so it
was moved to _trash/superseded_recipes_20260808/ rather than left as a live
trap. To restore the capability, add ridge_wide as a CAMERA under alpine.json's
capture.cameras and select it by name -- one declaration, N projections. The
frames it already produced are untouched and still cited in LESSONS. | S`

`2026-08-08 | B-BUILD-UNKNOWN: make_landscape_material must ASK THE GRAPH
before it reports, never assert a state it did not read | A build died with
"Remote party failed to send a valid response!" (the remote-exec payload was
truncated mid-string) and printed its destructive banner -- "M_AutoLandscape
is now EMPTY in memory and dirty ... Do NOT 'Save All'". The connectivity
audit seconds later read 262/262 CONNECTED: the build had SUCCEEDED and only
the response failed to return. The banner cannot distinguish a mid-build
death from a transport failure after a clean build, so it prints the same
alarm for both -- telling the operator not to save a good graph and inviting
a destructive re-run. Non-negotiable 25 forbids fixing this with better
prose. Fix: on any transport-class exception, query the live graph
(expression count + reachability, the audit already does it in one call) and
print BUILT / EMPTY / UNKNOWN with the query that settles it. This is the
SECOND tool in this class after save_level exiting non-zero on a save that
succeeded, so non-negotiable 4a's automatic escalation applies: one shared
"did the editor-side operation actually land?" helper, used by both. | M`

`2026-08-08 | B-APPEND-GUARD now has a ROOT CAUSE, and it is standing rule 3's
own mechanism | Recorded earlier as "nothing enforces append-only". The
transcript names the two lines. (1) CORRUPTION: Add-Content with a
DOUBLE-QUOTED PowerShell string -- backtick-r and backtick-t were consumed as
CR and TAB, so a one-line entry landed as three broken ones. (2)
DESTRUCTION: after six failed repairs, `$lines[0..33]` took the FIRST 34
lines and wrote them back; 34 + 1 appended = 35, from 11,434. Standing rule 3
already sends COMMIT MESSAGES through a file BECAUSE backticks expand and
silently delete words -- the rule was scoped to an instance of the hazard
rather than to the hazard itself. Widen it: any shell-authored prose destined
for a file goes through a file. A guard that refuses a shrinking LESSONS.md
is still worth having, but the cheaper fix is upstream. | S`

`2026-08-08 | CLOSED SAME DAY -- the GitHub remote held LESSONS.md in its
DESTROYED state, and does not any more | `git remote add origin
https://github.com/ryan772177/LandscapeLab.git` + `git push -u origin main`
ran mid-session, leaving origin/main at cb41d7f7 -- the commit immediately
AFTER the truncation -- so the published LESSONS.md was 35 lines with none of
the repair. Two of my three stated options were wrong on the facts: the repo
was ALREADY PRIVATE (Ryan checked), and Ryan then pushed from PowerShell
himself. Verified: origin/main == HEAD == 58bd8252, LESSONS.md at that commit
is 12,112 lines, 0 LFS objects pending. The repair is now off-machine, which
matters for a file that has been destroyed once. NO ACTION REMAINS.
Kept as the record, and for the general point: I reported the remote state
from a snapshot and it moved under me -- `git reflog show origin/main` reads
"update by push" and is the instrument that distinguishes "someone pushed"
from "a hook pushed", which is worth knowing before suspecting a hook. | DONE`

`2026-08-08 | Split "attended" items into their attended and unattended halves
before deferring them | The triplanar LOOK sat on the board as unmeasured and
attended for two days. The RENDER half needed only frames, and three complete
19-frame sets spanning both fixes were already in captures/alpine/ -- it was
measured offline in one pass (8.3x and 4.3x the same-settings noise floor,
_verify/20260808_before_after_material_fixes.txt). Only the GPU reading ever
needed a human at a viewport overlay. Bundling them parked a measurable result
behind an unmeasurable one. Applies to every remaining "attended" row on the
board: ask which half actually needs the human. | S`

`2026-08-08 | The GPU cost of triplanar is the ONLY remaining half of R2's
attended item | Rock albedo went from one sample to three (T_Rock026_C and
T_Rock051_C each report 4 connected samples vs 2 for non-triplanar layers) on
an iGPU already at 75-94 ms, and that machine has lost its GPU to a driver
timeout once. Needs an attended viewport overlay reading, ideally against the
clouds-off baseline that now exists. Note the frames prove the feature
CHANGES the image and where; they say nothing about cost. | S`

`2026-08-08 | RATIFIED SAME DAY, see the entry below this one. Kept as the
record of what was proposed before Ryan ruled. | UNRATIFIED PROPOSAL:
plans/clip_30s_proposal.md sequences the 30s AAA clip | Written on request. NOT adopted and NOT a plan of record -- items
tagged [RYAN] are escalation 1 (imposters, RVT, meadow intake, the render
target). Key structural finding: an offline MRQ render decouples the clip from
the 12 fps viewport entirely, so the interactive GPU work is NOT on its
critical path. Largest quality gap is MISSING GEOMETRY (R12 cliff + talus mesh
roles specified, never placed), not shading. Nanite disabled on 38/38 is
near-free offline quality and kills rock LOD popping. Whole untested defect
class: every verification we own is a STILL, so wind, streaming hitches,
temporal ghosting and LOD popping across a move have never been looked at.
Recommends NOT blocking on the verification debt, with two exceptions named. |
L`

`2026-08-08 | RATIFIED: plans/clip_30s_proposal.md is the SEQUENCE OF RECORD for
the 30s clip | Ryan ruled two things. (1) THE 5080 DESKTOP IS NOT SOON and the
plan assumes it never arrives -- the iGPU is the permanent target, so the
offline MRQ path is the deliverable rather than a fallback, and 1080p is the
render target because 4K quadruples per-frame cost on the one machine we have.
(2) EXECUTION ORDER IS 1.5 -> 1.2 -> 1.1, the reverse of the section numbering:
Nanite settles before cliff geometry is placed (1.5's own note), and ground
clutter is the smaller rehearsal of the same R12 machinery that 1.1 then uses at
scale. STILL UNRATIFIED and still escalation 1: 1.3 imposters, 2.5 RVT, 1.4
meadow intake. Phase 0 items 1, 2 and 4 (subject, eye-level vs crane, two
reference stills) remain open and are needed by 3.6, not by the content work. | L`

`2026-08-08 | CORRECTED: the talus cliff-source threshold was NEVER stale --
CLAUDE.md said so for five days and the clip proposal inherited it | CLAUDE.md's
"four things a fresh session must not re-derive" item 4 said the threshold MUST
move to landform-scale slope before Pass 3. It moved 2026-08-03 in 0b6a412b,
whose subject line says exactly that: rock_scatter.landform_slope() at :173,
build_context feeding source_slope_deg at :673-684, and source_smooth_m 16.0 in
the recipe's shared block. Measured in the docstring: cell-scale >=50deg is
9.152% of the map vs ~5.3% at 16 m landform, so ~40% of cell-scale "cliff" area
is texture. CONSEQUENCE: on 2026-08-08 the paragraph was copied into the clip
proposal as THE BLOCKER ON THE LARGEST QUALITY GAP without rock_scatter.py being
opened -- non-negotiable 9 against our own artefacts. A stale line inside a
section titled "must not re-derive" is more dangerous than a stale line anywhere
else, because that heading is an instruction to trust it. Both struck in place.
Pass 3's cliff and talus roles are NOT blocked. | DONE`

`2026-08-08 | Nanite's "full-density silhouette" argument is WITHDRAWN on our own
measurement; the LOD-popping argument stands | Free/_measured/palette_live.json
records triangles for all 38 (the field the pass audit confirmed agrees on 38 of
38 -- the positive control, unlike material_slots). The palette is already
low-poly: largest ScotsPine_01 60,120; largest rock Scree_001 33,855; SM_Cliff01
29,154; and the ONLY placed rock, Medium_Boulder_001, is 4,136 tris over 4 LODs
[4136, 1186, 892, 596]. Nanite cannot add detail an asset never had, so on this
palette it buys no silhouette. What it does buy is the removal of discrete LOD
transitions, and LOD popping across a moving camera is the one defect class no
still frame in this project has ever been able to test. Enablement must be ROCK
ONLY -- the tall palette entries are masked-material foliage, a different and
more expensive Nanite path. Decide by MEASURING a Nanite on/off pair across a
move, not by enabling 38 assets on an argument. | S`

`2026-08-08 | CLOSED BY RULING: clip sequence item 1.5, Nanite, stays OFF |
Closed in about one grep, not by the render measurement I had specified. THREE
independent grounds, none sharing a source. (1) The benefit does not exist:
palette_live.json gives largest rock 33,855 tris and the only PLACED rock 4,136 --
Nanite adds no silhouette an asset never had. (2) DECISIVE: git check-ignore says
17 of 17 rock meshes are gitignored vendor content (.gitignore:92,
LandscapeLab/Content/KiteDemo/), 0 authorable -- and RECIPES.md's Fab-boundary
rule 2 names "enabling Nanite on a Fab static mesh" as its WORKED EXAMPLE of an
in-place modification that vanishes on re-download with no error. A quality
decision that cannot survive a fresh clone is not a quality decision. (3) R12 2c
already ruled "Pass 3 does not enable it"; my proposal reversed a locked ruling
without citing it. Sanctioned path if ever wanted: a REPLAYABLE RECIPE STEP, as
import_static_mesh.py:245 already does via foliage.nanite -> build_nanite.
CONSEQUENCE: 1.1 is no longer gated on 1.5. | DONE`

`2026-08-08 | RE-HOMED TO 1.1: LOD popping on rock, with the lever corrected |
The Nanite ruling leaves the popping question standing -- it is still the one
defect class no still frame in this project can test. Nanite was never the lever
on this content. lod_depth, the LOD chain and cull_distance_m are, and all three
are recipe data we own outright. R12 already measured what makes popping likely:
boulder_medium_01's vendor LOD screen sizes are 1.504 / 0.752 / 0.319 / 0.238
against the cost model's assumed 1.0 / 0.5 / 0.21 / 0.088, i.e. the vendor drops
to its DEEPEST LOD much nearer the camera than assumed. Answer it when 1.1 places
cliff and talus, on content that exists, with a distance-stepped capture series
rather than a Level Sequence -- a pop is a spike in frame-to-frame delta, and
park_viewport.py can already place the camera and prove it landed. | M`

`2026-08-08 | R12's "Not yet placed" stood FALSE for two days after its own audit
found it | The 2026-08-06 pass audit listed it under "adjacent records the audit
found WRONG" and recorded it would be "corrected in their own files, not here".
It never was, inside a LOCKED recipe -- the document step (a) tells a fresh
session to follow exactly. Struck and corrected 2026-08-08 on three
representations: 504 packages across 493 grid cells (set difference 0 vs plan),
80/80 engine traces at median +0.000 m vs collision, recover_state reading 759
boulders on the cold-reopened world. GENERAL: "corrected in its own file" is an
intention, and non-negotiable 4 already rules that the sweep happens in the SAME
COMMIT as the finding, mechanically, not as an intention recorded for later. An
audit that defers its own correction converts a defect into a defect PLUS a false
sense it was handled. | DONE`

`2026-08-08 | recipes/schema.md does NOT contain the rock-species contract it is
cited as holding | CLAUDE.md calls schema.md "its normative contract, referenced
by twelve files", and import_heightmap._validate_rock_species's docstring says
"Schema v1.20". But schema.md contains no `role`, no `mask`, no `embed_frac`, no
`density_per_hectare_on_mask`, no `exclude_talus_above`, no `lod_depth` -- grep
returns two hits for align_to_normal, both in the VEGETATION section. Its highest
revision marker is v1.16. So the rock-species schema exists only in the validator
code and in RECIPES.md R12 section 2b, and R12 2b is the de-facto spec of record.
Same class as everything else found today: a derived record (a docstring citing a
version) pointing at a document that does not contain the thing. Found while
scoping the clutter role; NOT fixed, because writing the missing section properly
is its own unit and doing it badly mid-task is worse than the gap. | M`

`2026-08-08 | 1.2 DESIGN QUESTION, needs a ruling before clutter species are
authored: the ruled density philosophy has priors for two of its three gathering
places | RECIPES.md's Pass 5 ruling says clutter "gathers under trees, along
drainage, and at cliff bases" and that deposition and flow fields are legitimate
placement priors. The rock machinery (rock_scatter role_mask, MASK_KINDS =
slope|talus|layer) covers cliff bases via the deposit field and forest floor
broadly via the layer weightmap. It has NO flow prior. Flow lives on the
VEGETATION path as place_foliage's flow_bias reading terrain/alpine_flow.png,
which is on disk and already used by the Conifer species at flow_bias 0.45. Two
tools needing the same physical field is non-negotiable 19 and 4a territory, not
a copy-paste -- if a rock mask gains flow it must read the SAME loader, defined
once. Also unsolved: "under trees" has no prior at all; the Grass-layer weightmap
is where forest COULD be, not where the 157,554 conifers ARE, and clutter
clustered under actual trunks would need the instance positions as an input. | M`

`2026-08-08 | Deadfall (vegetation_debris) CANNOT be placed today: ruling (c)
refuses its 0.419 m horizontal pivot, and the enabling work is a pivot VECTOR |
Measured 2026-08-08: SM_Vegetation_Debris_002 is 3.64 x 1.03 x 0.75 m with its
pivot 0.419 m off-centre horizontally, against ruling (c)'s limit of 0.258 m
(0.25 x the smallest horizontal dimension). Under the rock path's random yaw it
sweeps a 0.84 m circle while being only 1.03 m wide, so it would visibly wander
off its intended spot. The gate refused the whole plan, correctly, and Deadfall
was dropped rather than the gate weakened. The pivot cannot be fixed at source:
it is Fab content and R-ASSET forbids authoring into a Fab folder -- the same
boundary that closed the Nanite item. THE ENABLING WORK, and it is real: the
offset could be CANCELLED at placement by offsetting each instance by the
yaw-rotated pivot vector, so the geometry lands where the scatter aimed. That
needs the pivot DIRECTION, and rock_pivots.json stores only the MAGNITUDE
(measure_rock_meshes computes horiz_m = hypot(ox, oy) and discards the vector).
So: store origin_cm in the measurement, apply the rotated correction in
plan_species, and re-derive ruling (c) to test the RESIDUAL after correction
rather than the raw offset. That would also admit mountain_rock_closed (0.556 m,
the palette's worst). Until then, Deadfall is UNPLACEABLE and the canopy prior is
carried by TreeStump (canopy_bias 0.90) and ClutterRock (0.35). | M`

`2026-08-08 | Pass 5 clutter is authored as THREE species, not four, and the
count is deliberate | recipes/alpine.json foliage.species gains ClutterRock
(boulder_small), DrainageStone (river_rock) and TreeStump, all role=clutter,
all lod_depth 4 matching their MEASURED lod_count. Deadfall is the fourth and is
blocked above. Density, scale, embed, cull and both priors are first-pass values
chosen from measured geometry and the shipped Boulder species as precedent --
they are NOT tuned against a render and must be judged at 1.7 m eye height
before they are locked. TreeStump is deliberately sparse at 0.6/ha because it
measures 2.33 m TALL and is a landmark rather than foot-level clutter. | S`

`2026-08-08 | DECISION NEEDED: the instance system cannot deliver Pass 5's
foot-level clutter density, and the grass system already can | Measured from the
dry run, not estimated. ClutterRock 14,785 placed = 5.81/ha = one per 1,721 m2 =
41.5 m spacing = about FIFTEEN small rocks visible in its entire 90 m cull disc.
DrainageStone six. That is occasional debris, not ground texture. Foot-level
texture on the same ~2500 ha mask would cost 250,000 instances at 10 m spacing
(the WHOLE ceiling), 1,000,000 at 5 m (4x), 2,777,778 at 3 m (11.1x), against a
250,000 ceiling of which conifers already hold 157,554. THE MECHANISM THAT DOES
THIS IS ALREADY IN USE: Meadow runs system:"grass" at density_per_10m2 120 =
120,000/ha, generated by the landscape material's GrassOutput
(make_landscape_material.py:2150, LandscapeGrassType) and culled at 50 m, at ZERO
cost against the instance ceiling. RECOMMENDATION, unratified: carpet density
goes on the grass system, the instance path keeps only sparse landmark items like
TreeStump. Adopting it needs a landscape material REBUILD, which is why it is a
decision and not a tweak -- and B-BUILD-UNKNOWN is still open on that builder. | M`

`2026-08-08 | The shared centred_bias formula is weak in the POSITIVE direction
for peaked priors, measured | TreeStump planned four ways, same seed, only
canopy_bias varying, measuring distance to nearest conifer: bias 0.00 -> 17.2%
within one canopy radius; 0.45 -> 18.6%; 0.90 -> 19.4%; -0.90 -> 2.2%. Both
directions correct, so the prior is proven to work rather than merely to run --
but +0.90 buys 13% relative while -0.90 removes 7.8x. STRUCTURAL, not a tuning
miss: canopy occupancy is a PEAKED field (most candidates near 0), so its mean
sits near the bottom of the range, and clip(1 + bias*(c-mean)*2, 0, 2) has the
whole interval to push down while SATURATING against the clip at 2.0 pushing up.
Flow is a smooth field with a mid-range mean and does not have this. NOT silently
changed: the formula is shared with place_foliage and is correct there, and
place_foliage's 157,554-instance output is proven bit-identical against it. If
stronger clustering is wanted the lever is the REFERENCE (a low percentile rather
than the mean) or a non-linear occupancy -- either changes a shared definition
and needs a ruling. | S`

`2026-08-08 | RATIFIED AND DONE: carpet clutter moved to the grass system |
Ryan's ruling. ClutterRock + DrainageStone are gone from the instance path,
replaced by ONE grass species GroundClutter on the Grass layer with two
varieties (boulder_small 0.6, river_rock 0.4), density_per_10m2 1.5, cull 70 m.
On R11's own convention that is about 2,309 in the cull disc and ~2.1M triangles
against grass's locked 29.8M, at 2.58 m spacing versus the instance path's
41.5 m -- a 16x improvement, which was the point. TreeStump STAYS an instance
clutter species: it is a sparse landmark and the per-trunk canopy prior is what
the instance path is uniquely good at. STILL NOT PLACED: this needs a landscape
material REBUILD (the grass types are built by make_landscape_material.py, not by
place_foliage), and B-BUILD-UNKNOWN is open on that builder. | M`

`2026-08-08 | ACCEPTED LOSS, measured not assumed: the flow and canopy priors do
NOT survive the move to grass | make_landscape_material.py:2306 wires each grass
pin straight to the layer weight mask and nothing else, so the engine's grass
system has no per-instance prior to read. Measured before accepting it: the Grass
layer already separates forest from non-forest at 6.0x (mean 16 m forest density
0.547 inside Grass>0.5 vs 0.091 outside), which IS the "under trees" intent. The
residual spread within the layer is p10 0.21 -> p90 0.79, and buying it back
needs a baked prior texture, a material-builder multiply between the layer mask
and that texture, and a rebuild. NOT taken. Note the resolution ceiling if it
ever is: at 4 m/texel a baked canopy map cannot resolve a 3.07 m canopy, so it
would deliver forest DENSITY, not per-trunk clustering -- which is fine at carpet
density and was not fine at instance density. DrainageStone's flow character is
genuinely LOST, not reduced: the Grass layer does not predict drainage at all,
and river_rock survives only as a size/shape variety. | S`

`2026-08-08 | A rock species' RNG stream is keyed by its POSITION in the species
list, so editing the list re-rolls every LATER species | rock_scatter.py:753 does
np.random.default_rng(seed + 104729 * (index + 1)) where index is the species'
position among rock species. Observed today: removing ClutterRock and
DrainageStone shifted TreeStump from index 3 to index 1 and its plan changed from
1,208 to 1,171 instances with every row different. Boulder was unaffected only
because it is index 0 in both lists. Deterministic for a GIVEN recipe, so
pipeline rule 3 holds -- but it means a recipe edit silently relocates unrelated
species, and if TreeStump had already been PLACED this edit would have required
re-placing all of it. Keying the stream by species NAME instead would be stable
under list edits. DO NOT DO IT CASUALLY: it changes every existing stream
including Boulder's, which would move 759 boulders already saved into the world,
so it needs a re-place and a RISKY-OP checkpoint. Worth doing before more species
are placed, not after. | S`

`2026-08-08 | B-THROTTLE-GUARD: bThrottleCPUWhenNotForeground has REVERTED to
True, and nothing checks it | Ryan set it False on 2026-08-01 and LESSONS records
that as the confirmed root-cause fix for the capture stall ("IT WAS THE ROOT
CAUSE, AND THE FIX IS COMPLETE"). It is back on. Whatever reset it -- engine
update, preferences reset, another project -- the point is that a machine-global
setting this pipeline depends on has no guard and no check, so every unattended
capture and background build silently inherits it and the reversion is invisible
until it costs a session. NOT CHANGED BY ME: the file is outside both roots and
is machine-global, standing rule 1 forbids it, and the 2026-08-01 change was made
only because Ryan asked by name. CANDIDATE REMEDY: a READ-ONLY line in
resource_guard or bootstrap that reports the effective value beside RAM, so a
run declares the condition it is operating under instead of discovering it. Note
non-negotiable 17 -- read the LIVE editor where possible, not just the ini. | S`

`2026-08-08 | make_landscape_material's "NOTE: in-memory only; not saved" does not
name its subject | Printed at make_landscape_material.py:2748 inside
`if args.assign:`, it describes the ACTOR ASSIGNMENT, not the material asset --
which save_asset persisted at :2338 several steps earlier. Read plainly it says
the build was not saved, and it was: the SHA moved 3d38821e -> 84394299 and
GT_alpine_GroundClutter.uasset is on disk. The danger is that the plausible "fix"
for the misreading is to save the LEVEL, 1,328 World Partition packages, to
persist an assignment that was already persisted weeks ago. A misleading success
message costs more than a missing one because it prompts action. ONE-LINE FIX:
"NOTE: the ACTOR ASSIGNMENT is in-memory only; the material asset IS saved." | S`

`2026-08-09 | GroundClutter is LIVE but does NOT read at 1.5/10m2; the mesh is
3.7x heavier than a grass tuft so raising density is not free | DumpGrassData
after FlushCache + 240s dwell: GT_alpine_GroundClutter 862 components, 3448 KB,
exactly matching GT_alpine_Meadow -- and R11 notes a counted component
NECESSARILY holds non-zero weights because the capture path strips all-zero
types. So the wiring is right and the frame is empty. Arithmetic: 1.5/10m2 puts
~36 rocks in the ~240 m2 near-ground band and 2,309 in the 70 m disc, and none is
identifiable. Cost per instance is ~1,179 tris (crude LOD1 average) vs 316 for a
grass tuft. RECOMMENDED, NOT APPLIED: trade reach for density exactly as R11 did
for grass -- 10/10m2 at a 40 m cull gives 5,027 instances, ~5.9M tris and 1.0 m
spacing, denser than the eye needs at foot level and about a fifth of R11 grass.
NOT SETTLED: "too sparse to see" vs "not rendering" are not separated by direct
evidence; the cheap decisive test is to raise density to 20-50/10m2, flush, and
capture. | S`

`2026-08-09 | B-CLOUD-NOISE: frame-to-frame comparison is UNUSABLE on this world
while volumetric clouds are on | Two forest_floor captures 30 minutes apart with
identical settings: SKY mae 0.06469, MID 0.05308, NEAR GROUND 0.02853. The sky --
which should be the control -- moves MORE than the ground, because volumetric
clouds ANIMATE. The 2026-08-08 before/after work established a same-settings
noise floor of mean mae 0.00298, but that was measured on CLOUD-FREE frames and
does NOT transfer. Consequence: any future A/B on this world must disable clouds
first, or its noise floor is larger than the effect it is looking for. This
silently defeated the attempt to measure whether clutter appeared. | S`

`2026-08-09 | CAPTURE_IN_PROGRESS is not gitignored, so every capture run dirties
the tree and trips the session-protocol stop hook | It is capture.py's own
sentinel -- pid, start time and camera list -- written while a run is live and
cleared on orderly exit. It is transient RUN STATE, which is what .gitignore is
for, and committing it would bake a permanent "a capture is running" lie into the
repo. The cost of leaving it is worse than cosmetic: a hook that fires on a false
positive every capture trains the operator to wave it through, which is exactly
the hook you need working when the dirty path is real. One line in .gitignore. |
S`

`2026-08-09 | THE MAP EDGE IS VISIBLE FROM ridge_wide, and fog cannot hide it |
From a camera at 1654 m the landscape ends in frame as a hard vertical cut
against flat haze, located by per-column stddev at about 95% across a 1920-wide
frame (std 0.121 terrain -> 0.020 flat between x=1792 and x=1832). Crop kept.
CRUCIALLY this is NOT a fog problem: exponential height fog is height-limited by
construction, and atmosphere_solve gives 8 km opacity of 0.3889 at a 300 m camera
but only 0.0222 at 1200 m, so a camera far above the 202 m half-height layer
receives almost none of it. Raising density to hide the edge would fog the ground
stations to conceal something only the high cameras can see. It is a
CAMERA-ROUTING or DISTANT-GEOMETRY problem. Cheapest answer is the same one the
proposal gave for the two polished falloff spots: route the clip camera so the
boundary never enters frame, which is free because the edge is at a known
location. | M`

`2026-08-09 | Lumen costs 0.22 stops and the exposure needs RE-SOLVING, not
patching | Measured on ridge_wide ground luma, sRGB decoded to linear: Lumen OFF
0.3012, Lumen ON 0.3730, against R13's solved target 0.3201. So Lumen adds +23.8%
ground brightness = +0.308 stops, and returning to target means exposure bias
-1.786 -> -2.007 EV. Nothing is blown at either setting (0.000% above 0.99), so
this is a level shift not clipping. NOT APPLIED, deliberately: -1.786 was SOLVED
by atmosphere_solve, not tuned, and replacing a solved value with an arithmetic
correction from one camera is the wrong shape. Re-run the solver under the Lumen
condition. What is established is the SIZE and DIRECTION, and that the clip
proposal's 2.1 dependency is real rather than theoretical. | S`

`2026-08-09 | The fog may not be wrong at all -- "untuned" was read as "bad" |
The clip proposal calls fog "applied, rendering, NEVER TUNED" showing "heavy
aerial haze at 8.7 km", which reads as a defect. Checked against physics instead
of against the adjective: by Koschmieder sigma = 3.912/V, so the measured 8 km
opacity of 0.3889 at a 300 m camera corresponds to a visual range of about 65 km
-- clean alpine air on a clear day, a defensible value. "Untuned" means NEVER
VERIFIED, which is a different claim from KNOWN BAD, and acting on the second
when only the first is true is how a good value gets replaced by a worse one. The
parameter that DOES deserve scrutiny is start_distance_m 1500: a hard cutoff
giving exactly zero aerial perspective inside 1.5 km, where real perspective
begins immediately and merely weakly. Untested. | S`

`2026-08-09 | RESOLVED: exposure under Lumen is -1.897 EV, and it belongs in the
MRQ render recipe, not the world | atmosphere_solve is a DIRECT-LIGHT Lambertian
model with no indirect term, so re-running it under Lumen returns the identical
number -- the solver cannot see Lumen. Solver kept physical; the missing term
measured instead: bias_lumen = bias_direct - log2(gi_gain). measure_gi_gain.py
over 19 paired clouds-off frames gives a SUNLIT gain of median 1.0798 (p10 1.041,
p90 1.096, spread 0.072) across 13 cameras, so -log2 = -0.111 EV and -1.786 ->
-1.897. NOT APPLIED: the recipe holds ONE compensation_ev, and -1.897 would make
every Lumen-OFF capture render sunlit terrain at 0.2964, -7.4% against the target
the whole evidence base was built on. A second field nothing reads would be an
inert field (non-negotiable 21). R7 already splits editing from final renders, so
the exposure should split the same way and the render value belongs in Phase 4.1's
MRQ recipe, which does not exist yet. -1.897 is its first known value. | S`

`2026-08-09 | Lumen barely touches sunlit ground and transforms shadow -- measured,
and it is why the first gain estimate was wrong | Per-camera, sunlit vs shadow
gain: cliff_face 1.4774 / 8.2990, sweep_0150 - / 5.1459, trunk_base 1.0322 /
1.5383, lod_near 1.0612 / 1.4107. Sunlit ground already receives nearly all its
light directly so bounce adds ~8%; in shadow the direct term is ~0 so bounce is
ALL the light and the ratio runs 1.24-8.30. A first pass took ONE median over
every responding pixel and returned 1.5753 with a spread of 7.25 -- averaging two
different physical populations and answering a question nobody asked. The spread
WAS the finding. Consequence worth keeping: correcting exposure by -0.111 EV
holds the sunlit look where R13 put it and lets shadows lift, which is the
desirable half of GI rather than a side effect to cancel. | DONE`

`2026-08-09 | save_level's result-file fix is HALF WORKING: the two phases share
one filename | The payload now writes its full result to
Saved/landscapelab_save_result.json and returns a small marker. That worked for
the PROBE phase (marker at 07:57:08 carries result_file, 1718 owned). It then
FAILED for the SAVE phase, which fell back to printing the full 418 KB dict and
blew the transport again -- most likely because the probe's file was still held
when the save tried to overwrite it. The save itself EXECUTED (1,484 packages
written at 08:00:53); only its confirmation was lost, which is the same
"a save that SUCCEEDED reports as unknown" failure CURRENT STATE already named.
Narrowed to one cause worth fixing properly: give each phase its own filename, or
write to a temp name and rename. Until then a save must be verified from the
ARTEFACT -- package mtimes and git status -- not from the tool's own report. | S`

`2026-08-09 | Nanite REPLACES LOD0 with a reduced fallback, so the Nanite-off path
is WORSE than the original mesh | Measured on all 8: get_num_triangles(0) dropped
after the build -- boulder_medium_01 4,136 to 1,796, cliff_face_01 29,154 to
6,230, scree_slab_001 33,855 to 9,195 -- while get_num_nanite_triangles() returns
the full original count. So Nanite renders at full density and the FALLBACK path
renders at roughly 20-40% of the original LOD0. Consequence on this machine: if
Nanite ever fails to run (driver, scalability, a cooked target without it), the
rocks are lower-poly than they were before tonight, not equal. Worth a render
check under r.Nanite 0 before the clip is rendered. | S`

`2026-08-09 | FIRST LOOK AT THE PLACED CLIFFS: they read as dark blobs ON a snow
face, not as outcrops IN it | cliff_face station, CLIFFS_TALUS_LUMEN2. The
CliffOutcrop meshes ARE placed and rendering -- clearly visible as dark rock
protrusions across the steep face -- so the placement works. Two problems the
frame shows. (1) The species band is height_m [200,1700] and slope 40-78, which
at altitude catches SNOW-dominated ground, so rock outcrops sit on snow and read
as debris rather than as exposed bedrock. Restricting cliff species to the Rock
LAYER weight (or a lower height band) is the obvious fix and is recipe data.
(2) Nothing blends the mesh into the terrain, so each outcrop has a hard
intersection line -- this is exactly what RVT exists for and is the strongest
argument yet for clip-proposal item 2.5, which remains [RYAN] and unratified.
Caveat on the evidence: this station is in terrain shadow (CURRENT STATE records
luma 0.157, too dark to adjudicate), so judge it again on a lit station before
tuning. | M`

`2026-08-09 | CONFIRMED BY RENDER: GroundClutter at 10 per 10 m2 IS visible where
1.5 was not | rock_grounding station, CLIFFS_TALUS_LUMEN2. The foreground now
carries scattered small stones and debris across the forest floor where the same
ground was smooth and bare at 1.5/10m2. So the density call was right and the
earlier invisibility was density, not a rendering fault -- which is the question
the 2026-08-09 render left explicitly unsettled ("too sparse to see" vs "not
rendering"). Settled: too sparse. | DONE`

`2026-08-09 | THE 5080 ARRIVES TOMORROW. The "not soon" ruling is VOID one day
after it was made, and 26 hardware-conditioned claims re-open | Lenovo Legion Pro
7i: RTX 5080 16 GB, 64 GB RAM, 1 TB, Core Ultra 9 275HX, 16" WQXGA OLED
(2560x1600). Ryan ruled on 2026-08-08 that the desktop was NOT SOON and the plan
should assume it never arrives; that ruling is now void and everything derived
from it re-opens. NOTHING NEEDS RETRACTING -- R13's CALIBRATION CLASS says of
every GPU number "editor viewport, Intel iGPU, 971x752, editor perf config. NOT
shipping, NOT PIE, NOT the future 5080 baseline." The numbers were labelled
correctly, so they become HISTORICAL rather than WRONG. That labelling is the
single highest-value habit in this project and it just paid. | L`

`2026-08-09 | RE-OPEN LIST for the 5080, ranked. Do NOT re-litigate the items in
the second half | VOID BECAUSE HARDWARE WAS THE ONLY REASON: (1) 1080p as the
render target -- I derived it FROM the iGPU ruling; a 2560x1600 OLED plus 16 GB
VRAM makes 4K a real choice. (2) Lumen off for editing (R7) -- the whole reason
was the iGPU. (3) Clouds ruled OFF interactive on measured cost. (4) The 40M
triangle working target and R5's 62M/frame ceiling "proven to hang this GPU" --
both iGPU-derived. (5) MAX_INSTANCES 250,000, chosen "for the documented
hardware". (6) Conifer cull 730 m and the imposter question. (7) MRQ render times
and EXR output, which stop being an overnight negotiation. (8) resource_guard's
1.0 GB floor and the one-heavy-op-at-a-time rule, written for 15.4 GB.
(9) t.MaxFPS 45 and ScreenPercentage 70. DO NOT RE-OPEN: the Fab boundary
(licence and git, not hardware), Nanite's absent silhouette benefit (asset
triangle counts, unchanged), the talus and landform physics, the exposure SOLVE
method, the map edge, the cliff-band-on-snow defect, and every measurement
discipline. Those were never hardware arguments. | L`

`2026-08-09 | 16 GB VRAM IS GENEROUS, NOT UNLIMITED -- do not let the 5080 become
a licence to stop measuring | Nanite plus Lumen plus Virtual Shadow Maps plus RVT
at 2560x1600 or 4K can still pressure 16 GB, and VSM page pool is exactly the
allocation that grows with resolution and instance count. The failure mode also
changes shape rather than disappearing: an iGPU that runs out hitches visibly,
while a discrete card that runs out of VRAM stalls on host-memory paging in ways
that read as a CPU problem. The project's answer stays the same -- measure in the
new calibration class before quoting any number -- and the FIRST measurement on
the new machine should be a fresh GPU baseline at the new resolution, not a
feature. | M`

`2026-08-09 | THE NEW MACHINE IS THE ONLY REAL TEST R0 WILL EVER GET -- do not
hand-migrate | R0 (fresh machine to identical editor) has been LOCKED and
UNPROVEN since it was written, and CLAUDE.md's own replay batch says the honest
partial replay on this machine was "follow the written procedure and diff against
PROJECT_STATE.json", with the FULL acceptance test explicitly deferred to "R0 on
the future GPU desktop". That machine arrives tomorrow. Copying the project
folder across would waste the one chance to find out whether R0 is followable,
and a recipe that cannot be followed without prior knowledge is exactly what
UNPROVEN means. PROCEDURE: clone the repo, git lfs pull, re-download the
gitignored vendor packs from Fab (KiteDemo 6.36 GB is load-bearing at 1,400
references; StampIt and Fab/ are needed; DragonCave and Atlantis_Ruins were
removed 2026-08-09 and should NOT be re-downloaded), pip install numpy Pillow
scipy per R0's corrected preconditions, then run recover_state.py and diff.
EVERY GAP FOUND IS THE DELIVERABLE, not a clean pass. | M`

`2026-08-09 | Machine-global changes made on the OmniBook do not migrate, and two
of them matter | powercfg AC timeouts and the screensaver were set to 0 at Ryan's
request 2026-08-09 so the overnight run would not be interrupted -- reverse them
on this machine when convenient. bThrottleCPUWhenNotForeground had REVERTED to
True and is the root cause of the capture stall class (B-THROTTLE-GUARD); set it
False on the new machine EARLY, before the first unattended run, rather than
discovering it again. The DDC, Saved/ and Intermediate/ do not migrate and should
not be copied. | S`

`2026-08-10 | SIX FAB MATERIAL INSTANCES WERE MODIFIED IN PLACE AND NO RECIPE
RECORDS IT | check_fab_boundary exits 5 on the new machine: 6 KiteDemo MI_ assets
CHANGED. This is NOT migration damage and the discriminating check says so --
all six differ in SIZE, not merely mtime, and the copy preserved mtime on 359 of
365 files, so mtime is a trustworthy signal here. All six carry the identical
mtime 2026-08-09 01:00:57, one write event, 26 minutes after the baseline's
newest recorded mtime (00:34:09). So an operation during the cliff/talus session
rewrote them. MI_Cliff01, MI_MediumBoulder_0012, MI_MountainRock,
MI_MountainRock_Closed, MI_Scree_001_CC, MI_Scree002_NEW -- which are exactly the
materials of the rocks that world places. This is HOLE 2, the case that script
exists to catch: gitignored, so a re-download silently reverts them, and the
rocks would change appearance with no diff anywhere. MI_MediumBoulder_0012 is the
odd one -- it SHRANK 132,829 -> 11,826 bytes, a 91% loss, where the other five
grew by ~4 KB; that asymmetry is unexplained and should be looked at before the
change is blessed. ACTION: identify what those edits were, express them as
replayable recipe steps per the script's own rule, THEN re-baseline. Do not
re-baseline first -- that discards the only evidence. | M`

`2026-08-10 | THE INCOMPLETE MIGRATION HAS A ROOT CAUSE AND IT IS A RUNNING
EDITOR | The move left 2 LFS objects behind (external actors of /Game/Alpine).
Cause: UnrealEditor PID 15820 was launched at 21:33 from
C:/Migration/LandscapeLab_repo/LandscapeLab 5.8/LandscapeLab.uproject -- the
STAGING folder -- and the repo was moved at 21:49 out from under it. A process
holding files open is the same mechanism the 2026-08-08 handoff records as
"unable to unlink old ... Invalid argument", where two bulk checkouts reported
exit 0 while writing nothing. GENERAL RULE, and it is the one worth keeping: a
bulk file operation must verify no process holds the tree open BEFORE it runs,
and must verify the DESTINATION afterwards rather than trusting its own exit
code. migrate_to_drive.ps1 verified counts and bytes and still missed this,
because 2 files out of 23,050 is inside the noise of any count-based check --
only a per-object identity check found it. | M`

`2026-08-11 | THE TERRAIN'S SILHOUETTE DETAIL IS CAPPED BY SAMPLING, NOT BY
MATERIAL -- 4.00 m PER HEIGHTMAP TEXEL | Ryan pointed out the map is 2017x2017,
not 4K, and the arithmetic makes it a structural finding rather than a note:
2017 vertices at scale_xy_cm 400.0 gives (2017-1)x400 cm = 8.064 km per side,
6,503 ha, and 4.00 METRES PER TEXEL. A cliff lip, a ledge and a crisp arete are
all sub-4 m features, so they cannot be represented at all -- the "smooth rolling
mounds" in every ground frame are the heightmap's Nyquist limit, NOT a texture,
tint or lighting defect. This reclassifies gap 2 of the AAA list. No amount of
triplanar, macro variation, detail relief or GI creates silhouette that is not in
the geometry; those buy SURFACE detail against a smooth profile, which is exactly
what the frames show. THREE ROUTES, and they are not equivalent: (a) more texels
at the same extent -- 4033 gives 2 m, 8129 gives 1 m -- which means re-importing
terrain and re-deriving weightmaps and all 171,069 placements, invalidating
Pass 1 and every grounding proof; (b) shrink the world at the current resolution,
which trades the open-world premise; (c) LANDSCAPE NANITE + DISPLACEMENT, which
adds real silhouette ABOVE the heightmap frequency without touching the heightmap
or any placement -- ruled out historically on the iGPU and now the obvious
candidate on a 5080 with 16 GB. Route (c) is the only one that does not
invalidate existing work, so cost it FIRST. Note the Gaea AlpineLab_v1 build is
4033^2, i.e. already double, which makes it the natural place to test the
resolution question without touching /Game/Alpine. | L`

`2026-08-11 | TWO REMOTE-EXEC CLIENTS AGAINST ONE EDITOR: THE SECOND ONE STEALS
THE FIRST ONE'S CONNECTION, AND THE VICTIM JUST HANGS | I ran render_condition.py
twice while capture.py held a command connection to the same node, as a
regression check. The capture then produced ZERO frames and logged nothing for
~15 minutes while its process stayed alive -- no error, no timeout, no refusal.
The editor served my render_condition calls normally throughout, so the editor
was healthy and only the capture was dead. This is a NEW instance of the stall
class BACKLOG already tracks under capture, and it has a much simpler cause than
throttling: one command connection per node. THE DIAGNOSTIC THAT SETTLED IT was
the EDITOR's log, not the capture's stdout -- the editor log's newest line was my
own render_condition payload, with no capture activity anywhere after it, which
says the capture was not talking to the editor at all. GUARD WORTH BUILDING: a
lock or a liveness check so a second remote-exec client REFUSES while a capture
holds the connection, rather than silently winning. Until then the operational
rule is: nothing touches the editor while a capture runs. | M`

`2026-08-12 | ROUTE (c) NANITE LANDSCAPE DISPLACEMENT -- fully scoped and cited,
NOT built. The engine side is already permissive; the work is the MATERIAL |
STATE READ FROM THE LIVE EDITOR (scripts/read_nanite_state.py, new): r.Nanite
1.0, r.Nanite.Tessellation 1.0, r.Landscape.AllowNanitePerClusterDisplacement
Disable 1.0, r.Nanite.MaxPixelsPerEdge 4.0. Landscape_Alpine and all 256
LandscapeStreamingProxy report enable_nanite FALSE, nanite_lod_index 0,
nanite_max_edge_length_factor 16.0, nanite_position_precision 0,
nanite_skirt_enabled False, material /Game/Materials/M_AutoLandscape. THE ONLY
REAL GATE IS THE PER-ACTOR enable_nanite. API, each name verified against THIS
install rather than remembered: LandscapeProxy.enable_nanite (PythonStub 531548);
Material.enable_tessellation (371966, "Required for displacement to work");
Material.displacement_scaling (371954); Material.displacement_fade_range (371953);
enable_displacement_fade (371958); TC_DISPLACEMENTMAP notes "For Nanite
displacement use TC_Alpha" (15024). ORDER MATTERS AND THE OBVIOUS ORDER IS WRONG:
enabling enable_nanite FIRST renders the same 4 m heightmap geometry as a Nanite
mesh and buys NO silhouette at all, while costing a Nanite build across 257
actors and a save of the main world -- cost with no benefit, and it would need
redoing after the material lands. Do the MATERIAL first. THE MATERIAL IS THE REAL
WORK AND IT HAS A KNOWN HAZARD: M_AutoLandscape is built by
make_landscape_material.py, which CLEARS THE GRAPH DESTRUCTIVELY before rebuilding
(non-negotiable 24's motivating case), and B-BUILD-UNKNOWN is still open on that
builder. Hand-wiring a Displacement pin in the editor would vanish on the next
rebuild, so the displacement output belongs IN THE BUILDER, not in the graph by
hand. Displacement source should be a real high-frequency height signal, not
noise -- the 4 m cap means the detail must come from somewhere the heightmap does
not have, e.g. the surface height maps already imported (T_Rock051_D, T_Snow006_D,
T_Ground037_D) blended by the same weights the albedo uses. SEQUENCE: (1) add the
Displacement output + enable_tessellation + displacement_scaling to
make_landscape_material.py, behind a recipe flag, and rebuild ATTENDED; (2) verify
the graph with audit_material_connectivity on the NEW bytes; (3) THEN set
enable_nanite on the 257 actors under a RISKY-OP tag; (4) build Nanite; (5)
capture and compare against 5080sp100 with edge energy, NOT mae -- mae cannot tell
sharper from differently blurry, which is the lesson the ScreenPercentage A/B
already paid for. | L`

`2026-08-12 | MATERIAL DISPLACEMENT IS FEASIBLE AND FULLY CITED, AND IT NEEDS A
MATERIAL-ATTRIBUTES RESTRUCTURE -- do not start it on a tired context | THE
BLOCKER, AND IT IS NOT THE ONE ANYBODY WOULD GUESS: MP_Displacement EXISTS at
value 32 (SceneTypes.h:181) but is marked UMETA(Hidden), so UHT never emitted it
into the Python MaterialProperty enum -- which lists MP_FRONT_MATERIAL 30,
MP_MATERIAL_ATTRIBUTES 33, MP_MAX 35, with 31 and 32 simply absent. PROVEN
UNREACHABLE, with a positive control so this is not a bad access path:
MaterialProperty(32) -> "Cannot create instances of enum types",
MaterialProperty.cast(32) -> "Cannot cast type 'int' to 'MaterialProperty'",
while MaterialProperty.MP_MAX reads <MaterialProperty.MP_MAX: 35> in the same
payload. SO connect_material_property CANNOT WIRE THE DISPLACEMENT OUTPUT.
THE ROUTE THAT REMAINS, every link opened rather than remembered:
MaterialExpressionMakeMaterialAttributes carries "FExpressionInput Displacement"
at line 77 of its header (Engine/Public/Materials/
MaterialExpressionMakeMaterialAttributes.h); MP_MATERIAL_ATTRIBUTES (33) IS
exposed to Python; and Material.use_material_attributes (PythonStub 372058) reads
"when true, the material attributes pin is used instead of the regular pins".
Material.enable_tessellation (False today), displacement_scaling
({magnitude 4.0, center 0.5}), enable_displacement_fade (False) and
displacement_fade_range ({4.0, 1.0}) are all readable AND writable on
M_AutoLandscape right now. WHY THIS IS NOT A SMALL EDIT: the builder currently
connects THREE separate outputs (make_landscape_material.py:2113-2122 ->
MP_BASE_COLOR, MP_ROUGHNESS, MP_NORMAL). Going through material attributes means
every one of them re-routes into a MakeMaterialAttributes node, on the MAIN
world's material, behind delete_all_material_expressions (the destructive clear
that is non-negotiable 24's own motivating case), with B-BUILD-UNKNOWN still open
on that builder, and with a LandscapeGrassOutput custom output in the same graph
(:2300) whose survival across the clear is relied upon (:1217). A mistake here
renders the landscape as UE's default checkerboard, which has already happened
once on this project. SEQUENCE WHEN IT IS DONE: (1) RISKY-OP tag first; (2) add
the material-attributes path to the BUILDER behind a recipe flag, never by hand
in the editor, or it vanishes on the next rebuild; (3) preflight EVERY new
texture BEFORE the clear -- the skill's rule, and the sub-surface case is what it
cost; (4) rebuild ATTENDED; (5) audit_material_connectivity on the NEW bytes,
expecting 0 orphans, plus audit_material_samplers; (6) confirm grass still spawns,
since the grass output shares this graph; (7) only THEN enable_nanite on the 257
actors and build; (8) compare with EDGE ENERGY, not mae. DISPLACEMENT SOURCE:
the _D height maps are already declared in the builder (surface_d / sub_d,
:633-636) but ONLY when a sub-surface is active -- so the displacement path needs
them unconditionally, which is itself a change to the single declaration. | L`

`2026-08-11 | NORMALISE EACH DISPLACEMENT MAP IN THE GRAPH — center 0.5 is
NOT neutral and up to half the amplitude is a DC offset | MEASURED, not
suspected. The five surface height maps have means Ground037 0.5257,
Rock051 0.6005, Snow006 0.6490, Rock026 0.7602, Rock063 0.7311 — NOT ONE
is 0.5. displacement = (v - Center) * Magnitude, so at the shipped
magnitude 0.16 every surface takes a CONSTANT upward lift of +2.06 to
+20.82 cm against a +/-40 cm amplitude, and because the lift differs per
surface there is a step of up to ~19 cm at layer boundaries that is not
relief. A fully-mipped sample returns the map's MEAN, not 0.5, so the
"degraded state is the identity" guarantee that the macro-variation map
genuinely has does NOT hold for displacement. displacement_scaling.center
is ONE material-level scalar and the maps disagree, so no value of it
fixes this. THE FIX: subtract each map's own mean in the graph before
compositing, so the composited displacement is centred by construction.
THE TRAP IN THE FIX, and it is why this is not a 20-minute job: the mean
must come from the IMPORTED ASSET, not the source PNG. The imported
textures may be resized or compressed (the AlpineLab masks were capped at
2048 and moved to BC4), so a mean measured from Free/*.png is a DERIVED
RECORD about a different artefact (NN15). Measure it in the editor at
build time, or bake it into the recipe with the asset's SHA-256 beside it.
Positive control: after the fix, the composited displacement over the
whole terrain must have mean ~0.5 and the per-surface step must vanish. | M`

`2026-08-11 | DISCRIMINATE WHY forest_floor GAINED ROCKS — grass clutter
or exposed boulders? ONE CAPTURE SETTLES IT | The 5080disp forest_floor
frame has dozens of small dark rocks the 5080sp100 baseline does not.
TWO EXPLANATIONS FIT AND THEY IMPLY OPPOSITE ACTIONS. (a) GroundClutter
is a GRASS species (SM_Boulder05a + SM_River_Rock_01, 10 per 10 m2, cull
40 m) and the rebuild MODIFIED GT_alpine_GroundClutter.uasset — CURRENT
STATE had the clutter material rebuild recorded as still owed. If so this
is the clutter finally spawning: a WIN. (b) the 759 hero boulders are
embedded 0.18-0.40 m and the displacement amplitude is +/-0.40 m, so the
displaced render surface exposes them: a COST that scales with amplitude.
Density argues for (a) — the new rocks are numerous and small, the hero
boulders are 759 over 6,503 ha and are the large pale ones already
visible in the baseline. THE TEST: capture forest_floor once with
`grass.Enable 0`, or count Medium_Boulder_001 in frame. Do this BEFORE
acting on the embedment item below, which is conditional on (b). | S`

`2026-08-11 | RE-DERIVE ROCK EMBEDMENT AGAINST THE DISPLACED SURFACE, or
lower the amplitude — CONDITIONAL on the item above resolving to (b) |
Nanite displacement moves the RENDER surface only;
collision stays on the heightfield and all 171,069 instances are grounded
to the heightmap. The 759 hero boulders are embedded 0.18-0.40 m (R12) and
the shipped amplitude is +/-0.40 m — THE SAME ORDER — so wherever
displacement pushes the surface down locally an embedded rock is exposed.
The MECHANISM is certain; whether the forest_floor frame SHOWS it is not
— see the discrimination item above. Three options and they are not
equivalent: (a) reduce amplitude_m until
the exposure is invisible — cheapest, costs silhouette; (b) deepen
embedment by the amplitude — costs a re-place of 759 boulders and does
nothing for the 13,515 cliff/talus rocks; (c) sample the same _D maps in
the SCATTER to offset each instance by its own local displacement — the
only correct one, and it is NN19's shape (one physical fact, two
consumers, define it once). Note (c) needs the displacement field
available offline, which the graph normalisation above would also need. |
M`

`2026-08-11 | AN INSTRUMENT FOR SILHOUETTE, because edge energy is not one
| measure_edge_energy.py works and is positive-controlled (-16.1% on blur,
+30.9% on sharpen), but it counts high-frequency ALBEDO contrast, and
displacement TRADES that for geometry whose shading varies smoothly across
facets. Result: the single most improved frame in the whole set,
sweep_0060, measured -23.11% — the WORST of 19 — while going from a flat
smeared texture to real ledges and self-shadowing. Whole-frame mean
-1.02% would have read as "displacement made it worse" to anyone who did
not open the PNGs. What would actually answer the question: edge energy
conditioned on the HORIZON BAND (silhouette against sky is where new
relief shows as new edges, and the whole-frame denominator drowns it —
NN22); or a depth-buffer / world-normal statistic, which needs a capture
path that writes a G-buffer rather than a tonemapped PNG. The second is
strictly better and strictly more work. Until one exists, displacement
verdicts REQUIRE looking at frames and that must be said out loud rather
than implied. | M`

`2026-08-11 | THE LANDSCAPE NANITE STATE IS IN MEMORY AND UNSAVED — decide
deliberately | enable_nanite is true on all 257 actors and 256 carry a
built Nanite mesh, but NOTHING WAS SAVED: the world on disk is still
non-Nanite. This was deliberate sequencing (measure before writing 1,484
packages) and it leaves a live foot-gun — a "Save All" or an editor-close
save prompt would persist it, and so would any script that saves the
level. The material IS on disk (M_AutoLandscape.uasset, committed), so the
disk world currently references a displacement material it cannot render.
That combination is HARMLESS (enable_tessellation on a non-Nanite
landscape does nothing) but it is not a state anyone chose. Either save
deliberately under a RISKY-OP tag once the centring fix lands, or set
enable_nanite back to false and re-enable after. Do NOT leave it
undeclared. | S`

`2026-08-11 | read_nanite_state.py's material block was DECLARED AND NEVER
FILLED for its whole life — sweep for others | _out["material"] was
initialised in the payload's first version, the docstring said "so the
displacement question has an address", and nothing ever populated or
printed it. An inert field in the one instrument built to answer the
question (NN21: a silent channel is an inert field). Fixed 2026-08-11.
THE SWEEP IS THE BACKLOG ITEM: grep every payload in scripts/ for keys
initialised into an _out dict and never assigned. This is mechanical and
NN4 says it belongs in the same commit as the fix — it was not done,
because the fix landed mid-unit; do it before the next instrument is
written. | S`

`2026-08-11 | THE 1 VERTEX/METRE RE-TERRAIN — RULED IN by Ryan 2026-08-11
("adopt everything that results in improved landscape quality and
resolution"). SCOPED HERE, NOT STARTED. | THIS IS THE REAL FIX FOR THE
SMOOTH SILHOUETTE. Every other lever — triplanar, macro variation, detail
relief, GI, and now Nanite displacement — buys SURFACE detail against a
smooth SILHOUETTE, which is exactly what every frame has shown. The
terrain is 2017 verts at 400 cm = 4.00 m per heightmap texel over
8.064 km, so a cliff lip, a ledge and a crisp arete are all sub-texel and
CANNOT BE REPRESENTED. Displacement (2026-08-11) adds relief below that
cap and is worth keeping, but it does not retire this.

THE MIGRATION IS CLEANER THAN IT LOOKS, and the numbers say so:
    current  2016 quads / 32 components = 63 quads/comp (63 x 1 section)
    target   8128 quads / 32 components = 254 quads/comp (127 x 2 sections)
    SAME 1024 components, SAME 256 streaming proxies, 4x quads per
    component, 16.2x vertices (4,068,289 -> 66,080,641)
    extent 8064 m -> 8128 m (+0.8%), scale_xy_cm 400 -> 100
So World Partition layout, proxy count and OFPA structure are UNCHANGED.
That is the difference between a re-terrain and a re-architecture.

NOT BLOCKED. The standards doc's own component math (64x64) is WRONG —
that yields 16257 verts, not 8129; 32x32 is right, verified
arithmetically. And CLAUDE.md's "Gaea is blocked by licensing" line was
STALE: Gaea 2.3.0.1 Indie has an 8K export cap since 2026-08-09 and
8129 < 8192, so the source heightmap is reachable. `resize_gaea_build.py`
already does the 4096->4033 style resize and R1's "crop, never resample"
was narrowed to allow it when the WHOLE PACKAGE agrees.

WHAT IT COSTS, stated so nobody discovers it mid-flight:
  * Pass 1 is invalidated. A new heightmap is a new world surface.
  * ALL 171,069 PLACEMENTS re-derive. The plans are computed offline from
    the heightmap so re-running is scripted, but the ACCEPTANCE MASKS
    MOVE and the counts will change — precedent: 160,448 -> 157,554 when
    the surface last moved. Do not promise the same trees.
  * Weightmaps, aux maps, the variant/selector bake and the macro map all
    re-bake at the new resolution.
  * Rock embedment, talus deposition and the flow prior all re-derive
    from the new surface (they read foliage.rock_scatter, so ONE source).
  * DDC and package size: the 194 MB .umap and the 11 GB Content tree
    grow. Disk is NOT the constraint any more (720 GB free); RAM at
    31.4 GB is, and the AlpineLab night run already hit a 994 MiB DDC
    limit on 4033 masks.

SEQUENCE, and step 0 is the point:
  0. DO IT ON `AlpineLab_v1` FIRST, NOT ON /Game/Alpine. That world
     exists precisely as the evaluation terrain, is already 4033, and
     BACKLOG 2026-08-11 (the earlier resolution entry) already says it is
     "the place to test the resolution question without touching
     /Game/Alpine". Prove the component layout, the import, the Nanite
     build and the frame cost at 1 m/vertex there.
  1. Gaea build at 8192 -> resize to 8129, `verify_build.py` exit 0 with
     the registration control reproducing.
  2. RISKY-OP tag. The landscape is created BY HAND in Landscape Mode
     (UE 5.8 Python cannot create one — R-GAEA step 4, still true).
  3. Import, then re-bake every derived map before anything is placed.
  4. Re-place, in ONE run, all species (the orphan sweep deletes anything
     not in the current run).
  5. Re-verify grounding against COLLISION, not the heightmap.
  6. Re-measure frame cost. 16x vertices on a 5080 laptop is the open
     risk, and it is a MEASUREMENT not a guess.

~~DECIDE FIRST: keep 8.128 km, or shrink to ~4 km?~~ **CLOSED
2026-08-11, AND IT WAS NEVER OPEN.** Ryan's criterion was "whatever gives
the most polished look and details"; the extent half was already ruled.
`WORLD_VISION.md:171` — **"World structure: 8064 m is the PER-REGION size
— CONFIRMED"**, reference class Witcher 3 / Final Fantasy / Tales /
Amalur, restated at :198 as settled with only contiguous-vs-multi-region
left open. Shrinking the region would have reversed a ratified ruling.
**The shrink option should never have been offered** — it was put to Ryan
without opening the file that had already closed it, which is
non-negotiable 9 on the person who keeps citing it. Kept struck as the
record.

SO THE TARGET IS FIXED: **1 m/vertex at full region size — 8129²,
66,080,641 vertices.** Note the extent lands at 8128 m, +0.8% over the
confirmed 8064 m, because 8064 does not tile at 254 quads/component
(8064/254 = 31.75). Hitting 8064 m exactly needs 126 quads/component ->
64×64 = **4096 components**, four times the current count, to save 64
metres. Take the 0.8%: the ruling is a reference CLASS, not a
tolerance, and 1024 components is the layout the world already has.

The remaining unknown is therefore NOT the design, it is the COST: can
this machine render 66 M vertices of Nanite landscape with tessellation
and displacement on? That is step 0's whole purpose and it is a
measurement, not an estimate. | L`

`2026-08-11 | capture.py EXITS 0 ON A SHORT RUN — it cannot count its own
output | The 5080hqfix sweep wrote 18 of 19 frames (ridge_wide never
written) and returned 0 with no mention of the shortfall. This is the
PRODUCER-side half of the verify_frames defect fixed the same day: the
verifier could not scope its input, and the capture cannot count its
output. Either alone is survivable; together they produced "19 of 19,
the instrument produced evidence" over a run that made 18, and that
sentence reached a report. ridge_wide HAS FORM — it is the same camera
that timed out and never wrote during the 2026-08-08 shader stall, so
this is a recurrence, not a one-off. THE FIX: capture.py knows how many
cameras it was asked for and how many files it wrote; it must compare
them and exit non-zero on a shortfall, naming the cameras. Note it
already prints the written filenames, so the count is in hand and simply
never asserted (NN25: a claim worth making in a message is a claim worth
asserting). ALSO WORTH FINDING OUT: why ridge_wide specifically. Two
skips on one camera across two sessions is a pattern, and the 2026-08-08
note attributes that one to a shader stall during a long compile. | S`

`2026-08-11 | AN INSTRUMENT FOR A DC OFFSET AND A LAYER-BOUNDARY STEP —
the centring fix has no way to be judged | _centred_height is
structurally verified (298/298 reachable, +20 nodes as designed, every _D
connected twice, 37 samplers clean) and its VISUAL benefit is UNMEASURED,
because edge energy is blind to it by construction: centring changes the
DC offset, not the relief amplitude. Worked on Rock026 at magnitude 0.16,
scale_z 500 — before (raw-0.5) gives +8.8..+28.8 cm, after (raw-mean)
gives -12.0..+8.0 cm; BOTH SPANS ARE 20 cm. The measurement came back
mean -0.87% with 11 of 18 inside the noise floor, exactly as predicted
beforehand. WHAT WOULD ACTUALLY TEST IT: (a) the layer-boundary step —
sample the rendered surface height across a Snow/Rock or Rock/Grass
boundary and look for a ~19 cm discontinuity that should now be gone;
needs a height read the capture path does not provide. (b) The DC lift is
measurable against COLLISION, which does not move with displacement: the
render/heightfield gap should now be symmetric about zero instead of
biased outward by +2..+21 cm per surface. That is check_collision_truth's
shape but pointed at the RENDER rather than the heightmap, and no
instrument reads the rendered surface height. Until one exists the fix
stands on an ANALYTIC argument and the record says so. | M`


---

## 2026-08-17 — B-FITCOHERENCE: DOES THE FIT MOVE TEETH AND EYES COHERENTLY?

**Ruled by Ryan 2026-08-17 as an OPEN QUESTION TO LOG, NOT SOLVE NOW.**
Parked here deliberately so the geometry-first pass is not blocked on it.

**The question.** Pass 1 edits HEAD-mesh vertices and lets
`import_from_face_dna` re-fit the parametric state. The fit path is what
makes a raw vertex edit safe at all — `FitToFaceDna` REGENERATES model state
from geometry, so rig self-consistency is enforced by the engine rather than
by our edit discipline. **That is the claim. It is not yet measured.**

Specifically: when head-mesh vertices move the JAW region, do the separate
`teeth_lod0_mesh`, `eyeLeft/Right`, `saliva` and `eyeshell` meshes follow
coherently, or does the jaw move through them?

**Why the current instrument cannot answer it.** The capture stage renders a
FRONTAL NEUTRAL face with the mouth closed. **The teeth are hidden.** A
frontal neutral render is structurally incapable of adjudicating this, which
is exactly the class of gap this project logs rather than lets a green
statistic cover.

**The measured geometry that makes it a real risk** (from
`ReadDNAMeshes`, DNA space, X=Left Y=Up Z=Front, cm):

    head_lod0_mesh    24,049 verts   Y 140.878 .. 178.439
    teeth_lod0_mesh    4,246 verts   Y 156.547 .. 162.072
    saliva_lod0_mesh     660 verts   Y 158.600 .. 161.108
    eyeLeft_lod0_mesh    770 verts   Y 165.627 .. 168.458

The 2026-08-17 jaw arm selected **1,661 of 24,049** head vertices in
Y 148..158, Z 4..15 — a band that reaches the bottom of the teeth. So the
edit and the teeth overlap in Y, and nothing has yet checked what the fit did
to the teeth.

**What would actually test it, none of which the frontal stage provides:**
- An OPEN-MOUTH or three-quarter pose render, which needs a posed capture
  the current locked-frontal instrument deliberately does not do.
- `ReadDNAMeshes` on the character's re-exported DNA after a fit, comparing
  the teeth mesh bounds before and after. Cheap, offline, and it does not
  need a render — but it measures the DNA, not the assembled result.
- An animation-time check: play a jaw-open animation and look for the teeth
  clipping through the lower lip.

**THE GATE, RULED BY RYAN 2026-08-17: HERO SIGN-OFF.** Not Pass 1, not gain
calibration — **the final declaration that the hero is done.**

    INSTRUMENT   a JAW-OPEN render (the frontal neutral stage cannot do it;
                 the teeth are hidden with the mouth closed)
    PASS         teeth and eyes track the reshaped jaw with NO intersection
                 and NO float
    STATUS       MANDATORY, and the evidence line justifying that is the
                 measured overlap below

*(The ruling that created this item ended mid-sentence — "an animation-time
check before the" — and Ryan confirmed that was the last line. The gate above
was ruled separately and deliberately afterwards, so it is his and not a
back-fill.)*

**Priority: after a likeness pass produces a face worth animating.** It is a
correctness check on the fit, not a blocker on measuring gains. | M


---

## 2026-08-18 (later) — B-HAIRGROOM: THE HAIR GROOM DRAWS NOTHING

**Timeboxed investigation expired; parked here with findings, per Ryan's
ruling.** Beard, moustache and eyebrows render correctly; hair does not. The
hero is bearded, browed, and bald.

**ADDED TO THE SIGN-OFF GATE, beside B-FITCOHERENCE.** A bald-but-otherwise-
likened hero does not block gain calibration. It does block declaring the
hero done.

### ELIMINATED — DO NOT RE-WALK THESE

- **Not a missing selection.** All four grooms read back PRESENT from the
  instance's own selection dump.
- **Not a missing component.** The Hair `GroomComponent` exists on the
  preview actor and reports `visible: true`.
- **Not a missing asset.** `groom_asset` resolves to `Hair_M_Layered` and a
  binding asset is attached.
- **Not the capture path.** Beard, Mustache and Eyebrows are the SAME
  component class rendering through the SAME SceneCapture, and they draw.
- **Not async build time.** The log's
  `Waiting for groom bindings to be ready 0/1 (Hair_M_Layered_Binding)` lines
  all predate the re-apply; none appear after it, and a render minutes later
  is still bald.
- **Not the parameter surface.** Colour writes to the Hair item returned true
  alongside the other three (12 of 12), so selection and parameters both
  work on Hair specifically.
- **Not specific to `Hair_M_Layered`.** A second hair asset,
  `WI_Hair_S_BobLayered`, was swapped in and also drew nothing.

### THE LIVE LEAD, AND IT IS CORRELATIONAL

    Hair_M_Layered      enable_global_interpolation  True    fails
    Hair_S_BobLayered   enable_global_interpolation  True    fails
    Beard_M_Stubble     enable_global_interpolation  False   renders

Global interpolation drives strands from the BINDING'S GUIDES, and the
recorded historical failure for these assets is *"guide roots are not close
enough to the target mesh"*. Two hairs with the flag fail; three non-hairs
without it render. **The split tracks the flag exactly — and that is a
correlation over five assets, not a mechanism.** No hair with the flag FALSE
has been tested, and no non-hair with it TRUE.

### WHAT TO DO NEXT, IN ORDER

1. **Find a hair groom with `enable_global_interpolation` FALSE and try it.**
   If it renders, the flag is implicated and the question becomes why the
   guides are invalid for this head. If it also fails, the flag is
   coincidence and hair-vs-not is the real axis.
2. **Rebuild the binding explicitly against the current mesh.** The bindings
   in use are engine-shipped assets built against the MetaHuman archetype;
   this head has been geometry-edited. A binding rebuilt against the frozen
   mesh is the obvious repair and was never attempted.
3. **Force an opaque debug material on the Hair component and re-render.**
   If a silhouette appears, it is the hair material at this exposure; if
   not, the geometry never reaches the rasteriser.
4. **Differential against a normal editor viewport screenshot** — purely as
   an instrument comparison, to tell whether SceneCapture is the variable.
   Not a measurement and does not enter the record.

**DO NOT EDIT THE ENGINE-SHIPPED GROOM ASSETS to test the flag.** They are
vendor content under `/MetaHumanCharacter/`, and this project's Fab-boundary
rule names exactly that class of change as one that vanishes on
re-download. Swap assets or rebuild a binding into project content instead.

### THE DOCTRINE THIS BOUGHT — SETTLING CANNOT SEE ABSENCE

The capture's reproduce-gate proves a frame is STABLE, not that it is
COMPLETE. Two frames agreeing on a missing element pass every statistical
check in the instrument, and that is exactly what happened: the hair was
absent from every capture for a whole session while every gate stayed green.

**Presence of expected elements is a CHECKLIST ASSERTION, not a statistical
one.** `manifest.capture.presence` now names the components that must be
rendering, lists Hair under `known_absent` with this item's id so its absence
is DECLARED rather than tolerated, and `use_preview_mesh` reports each groom
component's asset and visibility on every run. | M


---

## 2026-08-18 (later still) — B-HAIRGROOM UPDATE: BINDING STALENESS ELIMINATED, BY READING

Ryan ruled one bounded binding-rebuild test before gain calibration. **The
rebuild was not performed, because reading the existing bindings answered the
question and refuted the hypothesis.**

    Hair      target_skeletal_mesh  /Engine/Transient/FaceMesh_68   MATCHES
    Eyebrows  target_skeletal_mesh  /Engine/Transient/FaceMesh_68   MATCHES
    Beard     target_skeletal_mesh  /Engine/Transient/FaceMesh_68   MATCHES

    binding objects: /Engine/Transient...GroomBindingAsset_51 / _52 / _54

The bindings are **TRANSIENT and rebuilt by every `assemble_for_preview`
against the current mesh** — the GroomBindingAsset numbers change between
probes for that reason. There is nothing stale to rebuild.

**OUTCOME B, with the design concern CLOSED rather than budgeted:**

- Binding staleness is eliminated as a cause.
- **The fit loop needs NO binding-rebuild step.** The compounding-degradation
  risk that justified the test does not exist on this path, because the
  engine rebuilds bindings against the current mesh on every preview
  assemble. The retroactive trigger ("first presence failure on beard/brows")
  is therefore not expected to fire; it stays in the presence manifest as a
  cheap guard, not as an anticipated event.

**AND THE REMAINING LEAD IS SHARPER.** Hair and Beard now have IDENTICAL
binding configuration — same source mesh `SKM_Groom_Head_Legacy02`, same
target, 100 interpolation points, matching section 0, same LODs, same
`GroomBindingMeshType.SKELETAL_MESH` — and one renders while the other does
not. The difference is NOT the binding's configuration. It is in the groom
asset or the binding's built data, which is where
`enable_global_interpolation` lives (True on both failing hairs, False on
the working beard).

### THE ELIMINATION LIST IS NOW COMPLETE ENOUGH TO PARK

Not selection. Not the component. Not the assets. Not the capture path. Not
async build time. Not the parameter surface. Not specific to
`Hair_M_Layered`. **Not binding staleness, and not binding configuration.**

### NEXT, WHENEVER IT IS PICKED UP

1. Find a hair groom with `enable_global_interpolation` FALSE and try it —
   still the single highest-information test, and now the only cheap one
   left.
2. Force an opaque debug material on the Hair component: silhouette or no
   silhouette separates "material at this exposure" from "geometry never
   reaches the rasteriser".
3. Differential against a normal editor viewport screenshot, purely as an
   instrument comparison.

Vendor groom assets remain untouched, per the Fab-boundary rule. | M


---

## 2026-08-19 — B-HAIRGROOM UPDATE: THE PROBLEM IS WIDER THAN HAIR, AND THE GATE MISSED IT

**New fact, and it changes the shape of the item.** In the ASSEMBLED,
in-level build (`BP_MHC_AlpineHero` spawned in Alpine8K, durable bindings, not
the transient preview), the close portrait shows **no beard, no moustache and
no brows either** — the three that DO draw through the preview-actor path.

    preview-actor path (face stage)      3 of 4 draw   hair absent
    assembled BP in the level            0 of 4 visible in the render

So the axis is no longer only hair-vs-not; a PATH difference is now in play.
Not yet separated from the cheaper explanation: stubble at 2.1 m with the jaw
in shadow may simply be sub-pixel. **That is one difference-render away and
the test comes before the theory.**

### EVERYTHING TRIED, AND WHY EACH ONE FAILED TO EXPLAIN IT

| # | Hypothesis | How it was tested | Why it is out |
|---|---|---|---|
| 1 | Groom never selected | instance's own selection dump | all four read back PRESENT |
| 2 | Component missing | component enumeration on the preview actor | `GroomComponent` exists, `visible: true` |
| 3 | Asset unresolved | read `groom_asset` / `binding_asset` | resolves to `Hair_M_Layered` + a binding |
| 4 | The capture path cannot draw grooms | same component class, same SceneCapture | beard/moustache/brows DID draw through it |
| 5 | Async binding build unfinished | log timeline | `Waiting for groom bindings to be ready 0/1` all PREDATE the re-apply; a render minutes later is still bald |
| 6 | Parameter surface unreachable | 12 colour writes across four items | all 12 returned true, Hair included |
| 7 | Specific to `Hair_M_Layered` | swapped `WI_Hair_S_BobLayered` | also drew nothing |
| 8 | Binding staleness | READ the bindings instead of rebuilding | transient and rebuilt by EVERY `assemble_for_preview` against the current mesh; target matched on all three |
| 9 | Binding configuration differs | compared Hair vs Beard field by field | IDENTICAL — same source mesh `SKM_Groom_Head_Legacy02`, same target, 100 interpolation points, matching section, same LODs, same binding type — and one renders |
| 10 | The whole-rig lock or the shape edits broke it | grooms re-read on the LOCKED character | all four selected, bound, visible, after the lock |

### THE LIVE LEAD, STILL CORRELATIONAL

    Hair_M_Layered      enable_global_interpolation  True    fails
    Hair_S_BobLayered   enable_global_interpolation  True    fails
    Beard_M_Stubble     enable_global_interpolation  False   renders

Five assets, no mechanism, and no hair with the flag FALSE has ever been
tried. The recorded historical error for these assets is *"guide roots are not
close enough to the target mesh"*, which is what global interpolation depends
on.

### NEVER TRIED — the cheap ones, in order

1. **A hair groom with `enable_global_interpolation` FALSE.** Still the single
   highest-information test.
2. **A binding rebuilt into PROJECT content against the frozen mesh.** Vendor
   groom assets stay untouched (Fab-boundary rule).
3. **An opaque debug material on the Hair component.** A silhouette separates
   "material invisible at this exposure" from "geometry never reaches the
   rasteriser".
4. **A hidden/shown DIFFERENCE RENDER** — now the first test, because it also
   fixes the gate below and answers the new assembled-path question.
5. Differential against a normal viewport screenshot, as an instrument
   comparison only.

### AND THE GATE THAT WAS SUPPOSED TO CATCH THIS DID NOT

The presence gate was implemented as component state — asset + binding +
`visible` — and returned `ships_as DELIVERABLE` on a render with no visible
grooms at all. **`settling cannot see absence` became `a checklist cannot see
absence either`** the moment the checklist read properties instead of pixels.
A component can be present, bound, visible and drawing nothing; B-HAIRGROOM
has been saying precisely that about Hair for two days, and this gate would
have passed Hair too.

**The fix is the difference render, and it is the same trick the body ruler
already uses:** photograph the frame twice, once with the required grooms
hidden, and require a non-empty difference where each groom sits. A groom that
draws nothing produces an identical frame, and identical frames are the one
thing a difference mask cannot miss. | M

## 2026-08-19 (night) — B-HAIRGROOM: CLOSED. NOT AN ASSET DEFECT.

**Cause: a groom finishes over frames after its assets first become resident in
an editor session, and every "bald" render was taken before it finished.**
Measured in a cold editor, first placement, nothing changed between the two
readings but the frames spent: Hair 33,743 -> 96,246 px; Eyebrows 3,564 ->
19,205; Beard 9,153 -> 13,149. The first reading calls Eyebrows ABSENT. It was
not absent, it was unfinished. Hair is the heaviest of the four and converges
last, which is why hair alone looked permanently broken.

**The convergence is paid once per EDITOR SESSION, not per spawn** — a respawn
in a warm editor converges immediately — which is why the failure looked
intermittent and asset-shaped for two days.

Narrative: `LESSONS.md` 2026-08-19 (night). Specification: `RECIPES.md`
**R-HEROGROOM**, with its REJECTED section.

### WHAT IS NOW SETTLED, AND WHAT NEVER NEEDED DOING

- `Hair_M_Layered` renders at **83x** the repeat floor, untouched. No vendor
  groom asset was edited, no project-content duplicate was made, and none is
  needed.
- **The `enable_global_interpolation` lead is retired, and the correlation is
  explained rather than merely dropped:** the two hairs carrying the flag are
  also the two heaviest grooms, and heavier grooms converge later. A clean
  correlation over five assets pointing at nothing is worth recording as a
  shape — it was the best available lead and it was still wrong.
- **Row 4 of the elimination table was retired on a confounded comparison.**
  "The capture path cannot draw grooms" was ruled out because beard and
  moustache DID draw through the same SceneCapture — true, and it does not
  clear the row, because the two paths also differed in how long the assets had
  been resident. **An elimination is only as strong as the alternative it rules
  out.**
- The externally-briefed main-view mechanism was **tested and refuted here**: a
  fresh respawn with the editor viewport 180 deg away matched the
  main-view-on numbers to 1.3%. Kept as a repeatable control
  (`place_hero_in_world.py --main-view`), not as doctrine.

### THE ONE THING THAT REPLACES IT

Every groom-bearing capture is now gated by `groom_presence.py` at the framing
it will ship at. The old gate read component properties and returned
DELIVERABLE on a bald portrait; this one hides each groom and requires the
picture to change, with a positive control, a stability map and a reproduce
check, all fail-closed. | DONE

## 2026-08-19 (night) — NEW: THE MOUSTACHE ONLY READS AT 0.9 m

Not a defect and not urgent. `Mustache_M_Stubble` clears the presence bar at
0.9 m (3.3x floor) and sits at 2.2x at 1.1-1.3 m, reproducibly. It is stubble
on an upper lip and it is the faintest thing on the character. If a moustache
is meant to read at conversational distance that is an ART CALL about which
groom is selected, not a bug — recorded so nobody re-opens it as one. | S

## B-GITHISTORY — the repo cannot push, and it is not the DiffLocks npz

*Raised 2026-08-22. OPERATOR infrastructure decision, parked deliberately.*

Two oversized RAW blobs sit in HISTORY. Both were untracked later (commit
1b87f49f, "Untrack Blender's .blend1 auto-backups"), so neither is at HEAD —
but GitHub rejects on PUSHED HISTORY, not on HEAD:

    hero/blender/AlpineHero_Snap_deform.blend1    106,124,151 B   OVER the
                                                                  100 MiB limit
    hero/blender/AlpineHero_Snap_nearest.blend1    72,495,294 B   under, large

Found by a sanity scan while repairing the DiffLocks npz blob. That repair is
complete and correct — the npz is a 134-byte LFS pointer and off every ref —
and it was NOT sufficient: the push is still blocked, by something older. The
blob fix would have looked like a success while every push still failed.

Clearing them means rewriting 407 commits (git-filter-repo or lfs migrate
class), which changes every commit hash in the repo. That is a calm-morning
operator decision, not a working-session side effect.

Until then: the repo simply does not push. Nothing else is affected — local
history, LFS, and every tool are unharmed.

## Doc consolidation — findings owed (2026-08-29)

`2026-08-29 | landmark.spire_mesh is an INERT FIELD | Declared in
recipes/city.json and read by nobody; scripts/city_place_payload.txt:77
hardcodes ("spire", "/Engine/BasicShapes/Cone.Cone"). The two agree today so
nothing is broken -- change the recipe value and the spire will not change.
Violates pipeline rule 2 and non-negotiable 24, and is a RECURRENCE of the
class the same recipe already records fixing for meshes.roof on 2026-08-25.
Fix belongs in the payload, which mutates the world and wants an editor to
test. | S`

`2026-08-29 | Five gate booleans are decorative mirrors | city.json gates
all_inside_radius / no_footprint_overlap / streets_are_one_network, and
encounters.json all_reachable_from_player_start /
min_separation_from_archetypes, are read by nothing under scripts/. The
INVARIANTS are enforced unconditionally in plan_city (rej["outside_radius"],
rej["overlap"], plaza-component prune), so this is not an unenforced gate --
it is a flag that looks like a switch and is not. They sit beside
max_pad_cut_fill_m / min_buildings / min_street_segments, which ARE read, so
the block reads as uniform. Ruling needed: read them, or move them under a
documentation key. | S`

`2026-08-29 | Annotating a recipe costs downstream stamps | Writing the two
notes above INTO recipes/city.json moved its SHA-256 and made
city/alpine_basin_town_reachable.json report STAMP DIFFERS. The town plan
regenerated with ONLY _input_sha256 changed (303 buildings, streets, counts,
landmark, spire all byte-identical), but the sidecar is produced by an
in-editor payload and cannot be refreshed offline. Notes were reverted.
Worth knowing before anyone documents inside a hashed input again. | S`

`2026-08-29 | plans/characters_brief.md left LIVE but flagged | Its skeleton
ruling was partly superseded by Ryan's MetaHuman ruling; its 102-animation
inventory is still what ABP_Unarmed drives. Split, archive, or leave? Operator
ruling. | S`

`2026-08-29 | The three plans/*_lanes directories were indexed, not quarantined
| 31 files, ~338 KB of agent lane output from 2026-08-15. They are INPUTS whose
outputs (PHASE2_PLAN, WORLD_ARCHITECTURE, terrain/regions) are live, and they
sit under plans/ where nobody mistakes them for doctrine. Moving them risked
burying a measurement for tidiness. Say the word and they move. | S`

**PATH NOTE, 2026-08-29 (doc consolidation).** Entries above reference
`VERIFICATION.md`, `plans/clip_30s_proposal.md` and other pre-8K docs at their
ORIGINAL paths. Those files were not deleted; they moved to
`docs/archive/pre8k/` and each carries a banner naming what superseded it. The
original wording is left untouched on purpose -- rewriting a path inside a
recorded ruling falsifies what was true when it was written. Full mapping and
evidence: `docs/_consolidation_inventory.md` section 2.

## storey_m ruling — follow-ups (2026-08-29)

`2026-08-29 | THE PLACED TOWN NOW DISAGREES WITH ITS PLAN | The operator ruled
buildings.storey_m 3.2 -> 2.0 and the plan was regenerated: heights are now
6/8/10/12 m. THE 303 BUILDINGS STANDING IN /Game/Alpine8K ARE STILL AT
6.4/9.6/12.8 m, because placement needs an editor and the town is due to be
re-emitted from the kit anyway. city_verify_payload WILL REPORT A MISMATCH
against the live world until then, and that is CORRECT, not a defect. Closed by
re-placing, or by the kit re-emission. | M`

`2026-08-29 | RETIRE the reachability sidecar's _stamp_waiver |
city/alpine_basin_town_reachable.json carries a declared waiver because
recipes/city.json moved for the storey_m ruling. Reachability depends on
building FOOTPRINTS and the STREET network, both proven byte-identical across
the change (303 of 303), so no row can have changed -- but the honest state is
WAIVED, not re-verified. Re-run scripts/city_reachable_region_payload.txt
against a built navmesh, re-stamp, and DELETE the waiver key. A waiver left in
place after its reason is gone is the same rot as a stale finding code. | S`

## Concept pipeline — briefed, waiting on Gate A (2026-08-29)

`2026-08-29 | PHASE C0 donor FBX is AMBIGUOUS -- do not start until settled |
The brief names "Medival House _.fbx" in Downloads. Three candidates are there
and they are NOT the same asset:
  medieval-house.zip           31.7 MB, 2026-08-27  <- most likely; brief says
                                                        it may still be zipped
  medieval_houses_10.fbx        0.37 MB, 2026-08-25  <- DUBINIEC, and ASSETS.md
                                                        line 544 records its
                                                        licence as NOT RECORDED,
                                                        evaluation only
  medieval_houses_textures.zip  204 MB,  2026-08-25  <- Dubiniec's textures
CONFUSING THESE WOULD MEAN BUILDING A MATERIAL PIPELINE ON AN ASSET WE MAY NOT
SHIP. The brief's description (Blender-exported binary FBX, ~10 diffuse-only
Phong slots, TILING Poly Haven CC0 maps) matches the .zip, not the Dubiniec
FBX, whose textures are a separate 204 MB archive. Confirm which before
extracting. Also: refs/textures_v1/ does not exist yet -- C0 cannot start
without the operator's generated set. | S`

`2026-08-29 | Second kit intake on a wider seed | MODULAR_ASSETS (96 meshes),
Roofs (10), Construction_Pieces (10) cover most of what the concepts need and
what I would otherwise have called "needs authoring" -- HBeam_* for the timber
upper storey, BoardWall, GableSet, PorchBase, LanternPost, Outcrop*,
SM_OldWoodenBench, wheels. One run of scripts/intake_kit_closure.py with a
wider seed; the closure walker and the collision gate already exist. | S`

`2026-08-29 | recipes/alpine_8k.json declares NO rock scatter species | The
list is EMPTY. rock_scatter.py is built and proven and recipes/alpine.json
declares ten; the 8K world inherited the machinery and none of the content.
Both concepts show river stones and scree, so this blocks part of the concept
loop -- and it was invisible until the recipe was opened rather than the
tooling consulted. Needs a ruling on which species and what density. | S`

`2026-08-29 | WATER IS A SYSTEM AND HAS NO BRIEF | Both concepts carry running
water; this project has never used water. The engine ships WaterBody classes
(256 references in the 5.8 stub) but there is no water in any recipe, no
shoreline handling, and no interaction with the landscape material or the
navmesh. Concept 01 can be built without it; concept 02 cannot be matched
without it. Should NOT be smuggled into the concept loop as a prop. | M`

## Performance law — follow-ups (2026-08-30)

`2026-08-30 | FIND A CAPTURE PATH FOR nanite_triangles, texture_memory_mb AND
draw_calls | These three are declared null and UNMEASURED in
recipes/perf_budgets.json, and the operator ruled they stay that way rather
than being guessed -- but THEY CANNOT STAY NULL FOREVER, because the forge's
per-asset rule (max_tris / max_texture_mb per asset class) is what stops
generated assets blowing the budget one at a time, and today that rule is
enforced only against numbers a human typed. The CSV profiler as invoked
captures FrameTime, GameThreadTime, RenderThreadTime, GPUTime and RHIThreadTime
and nothing else. Candidate routes, none tried: additional CSV categories via
`CsvCategory <name> enable` -- and the argument MUST be the word "enable",
because `CsvCategory VSM 1` is a SILENT NO-OP this project already paid for on
2026-08-15; `stat rhi` scraped from the viewport, which has no automation path
here yet; or the Nanite/streaming stat commands read through a payload.
Whichever is chosen must produce an ARTEFACT, not a viewport reading -- the
2026-08-06 pass audit filed attended overlay readings as unverifiable by
construction. | M`

`2026-08-30 | A MOVING-CAMERA FLYTHROUGH, to sit beside the fixed stations |
perf_flythrough measures STEADY-STATE cost at four fixed stations, and says so
in the recipe, in the tool and in every artefact it writes. It therefore cannot
see streaming transients, World Partition pop-in, or first-traversal shader
hitches -- which are exactly the costs a player feels as stutter rather than as
low frame rate. The fixed stations stay: they are what makes two sessions
comparable. A moving pass is an ADDITION, and it needs its own thinking about
what statistic even means anything when the camera is in motion. | M`

<!-- ARCHIVED-PATHS-DECLARED -->

## Kit render follow-ups (2026-08-29)

`2026-08-29 | FRAME COST of the kit is still unmeasured | Arithmetic only:
~9 modules per house at ~12k Nanite tris is ~110k per house, ~33M across 303
buildings. Nanite's territory, but a number is not a measurement. Needs
measure_pie_cost.py or an editor-viewport A/B with a representative wall of
modules standing. Do it BEFORE the town re-emits, not after. | S`

`2026-08-29 | city_shot_payload's watcher has been wrong 4 of 4 times | It
exits 1 reporting ok:false over frames that exist -- both of today's landed
around 840 s, after it gave up. The payload ALREADY computes a `_before` set of
the screenshot directory at the top and then never uses it for this. Make it
poll that directory for a new file instead of waiting on a fixed budget. A tool
whose verdict you have learned to ignore is a delay, not a tool. | S`

`2026-08-29 | The 630 s post-capture wedge is still unexplained | Reproduced
twice more today: frame written, then 0.02-0.05 CPU-s per wall-second with
Responding=False, recovering to 6.55 after roughly the documented 630 s. Five
occurrences across three sessions now. Worth a bounded investigation before any
render-heavy session, because it costs ~11 min of dead remote-exec channel per
frame. | M`

---

## Concept render batch — findings (2026-08-30)

`2026-08-30 | ROOF MESHES DO NOT SEAT ON THEIR WALL BOXES | FOLDED INTO
RULING 4 -- see below. Not an independent unit. | S`

**AMENDED the same day, and the first wording was wrong twice over.** It said
the roof is "scaled to the footprint": it is NOT scaled at all -- the builder
spawns SM_House02_Roof at its native 8.99 x 9.17 m on a box scaled to
10.0 x 8.0 m, and `_r2` never gets `set_actor_scale3d`. It also implied a
free-standing fix. It is not free-standing: **roof-to-footprint fit at
placement is exactly what ruling 4 governs**, so the fix belongs to ruling 4's
implementation, where the planner that biases footprints toward servable roofs
is the same code that must seat a roof to its wall bounds. The +-20% bar
applies to roof fit as it does to walls.

**And the measurement that makes it ruling 4's problem rather than the concept
stage's:** `roof_servability.fits(10.0, 8.0, (8.99, 9.17), 0.20)` returns
**True**. The pairing is 10% short in X and 15% proud in Y, the two compound
into the splayed silhouette instead of cancelling, and the bar passes it. The
audit and the planner agree with each other -- 325 both ways -- and both agree
with a tolerance a rendered frame disagrees with.

Three sub-items, written up in full in
`_verify/20260830_overnight/ROOF_SERVABILITY.md`:

`2026-08-30 | R4a: the +-20% bar is per-axis and unsigned | A shortfall on one
axis and an overhang on the perpendicular one both pass in full and compound
visually. Bound the SIGNED residuals jointly. The number wants deriving from
renders -- +-20% was never validated against a picture. | M`

`2026-08-30 | R4b: servable_by returns the FIRST fit, not the best | roof_spans
sorts ascending by max span, so it selects the SMALLEST passing roof. Correct
as the boolean plan_city.py:430 needs for roof_servable; WRONG the moment
anything places the roof_candidate it also records. Forward hazard, not yet a
live defect -- the town is still engine primitives. Fix before the kit town is
placed: return the minimum residual. | S`

`2026-08-30 | R4c: concept_build_payload asks this module nothing | It takes a
hardcoded roof_package and spawns it at native scale. Drive the choice through
servable_by or scale the roof to the wall bounds -- the concept stage must not
be a second place that answers the fit question its own way. | S`

`2026-08-30 | THE CONCEPT LOOP'S ARITHMETIC HALF CANNOT SEE FIT | **DONE
same day.** scripts/concept_loop.py now declares MEASURED_DIMENSIONS (5) and
NOT_MEASURED (5), prints both under every verdict, and writes both into
loop_v0.json beside each `deltas` field and once at top level as `scope`. An
empty delta list now carries "converged on the measured_dimensions listed here,
and on nothing else" in the same object, so the scope cannot be separated from
the result it qualifies. Adding a check means adding its line. | S`

`2026-08-30 | EVIDENCE that the 630 s wedge IS the render, not a sequel to it |
2026-08-30 iter0 shot: the LOG ITSELF froze -- zero lines between
`Cmd: HighResShot 1` at 19:11:58 and the payload's return at 19:25:59 -- with
the editor at 0.015-0.019 cpu-s/wall-s throughout, then the frame written at
19:26:00.244 and remote exec answering immediately after. That is one
observation and does not close the older item above; it does say the next
investigation should test "the render blocks the game thread for ~14 min"
BEFORE testing "something wedges the editor after a frame". | S`

## Concept iter1 frame — findings (2026-08-30)

`2026-08-30 | STAGE_GROUND SPANS +-2000 m AND ITERATION 1 STAGES AT 3000 m |
The iter1 frame is 54.31% pure black below the horizon: the village floats over
a void. Stage_Ground is a 1 m Plane at scale 4000, created ONCE at the origin
under `if "Stage_Ground" not in _labels`, so no iteration staged beyond +-2000 m
ever gets ground. Either scale the plane from the largest offset_y_m the run
will use, or create ground per iteration at the iteration's own origin. The
payload's `ground_check` REPORTED THIS CORRECTLY -- "COULD NOT LOOK, no ground
hit under the camera XY" -- while every other instrument said success. | S`

`2026-08-30 | chalets_outside_frame COUNTS CENTRES, NOT EXTENTS | It compares
chalet centre bearings to the half-FOV, so a chalet whose centre sits at 0.9975
of the half-width reads as inside while half its body is off-frame. Measured:
iter1 reports 0 outside and the village touches column 1262 of 1263. Compare
the building's silhouette edges, not its centre. | S`

`2026-08-30 | THE ITER1 FOV WIDENING FIXED THE WRONG QUANTITY | fov1 =
2*bmax/0.90 uses the largest TERRAIN FEATURE bearing (30.0 deg). The chalets
sit at 33.22 deg, beyond every terrain feature, and were never re-checked
against the new FOV. So the delta that "closed" between iterations closed on a
different quantity from the one that was visibly wrong -- which is how
deltas:[] and a clipped village coexist. | S`

`2026-08-30 | city_shot_payload's OUTDIR COPY IS DEAD CODE | Line 233 copies
the frame to OUTDIR/NAME.png and sits AFTER the raise on the absent-frame path.
The watcher has never succeeded, so the copy has never run, and every frame in
_verify/ was placed there by hand. Falls out for free when the watcher moves
host-side. A self-banking step that has never executed reads, in source,
exactly like one that works. | S`

`2026-08-30 | PARK THE VIEWPORT SIZE BEFORE A SHOT SERIES | iter0 came out
2032x1273 and iter1 1263x1349 because foregrounding the editor with
ShowWindow(SW_RESTORE) resized the window and HighResShot captures the active
viewport. highres_shot.py calls a different resolution a different CALIBRATION
CLASS, so the pair cannot be diffed. Set an explicit viewport size, or take a
series without touching the window. | S`

`2026-08-30 | MOVE THE SHOT WATCHER OFF THE GAME THREAD | The single highest-
value fix on this list: it removes ~14 minutes of dead channel PER FRAME, the
false ok:false verdict, the "wedge", and the dead OUTDIR copy, all of which are
one defect. See RECIPES R-CITYSHOT AMENDED 2026-08-30b for the mechanism and
the six measurements. | M`

## Offline suite — two PRE-EXISTING failures, surfaced 2026-08-30

**Both were failing before this session's edits** (identical output from two
suite runs, and `git diff HEAD` shows `check_plan_freshness.py`, `city/` and
`foliage/` untouched). Recorded because they were being carried silently.

`2026-08-30 | THE SUITE EXITS 0 WITH FAILURES | run_offline_suite.py printed
"FAILURES: 3" and exited 0, and that exit code was read as a pass in this
session before the tail was looked at. An exit code that does not track the
verdict is the R-CITYSHOT watcher defect in another tool: a signal you have to
remember not to trust. Make the runner exit non-zero on any undeclared
failure. | S`

`2026-08-30 | THE PLAN-STAMP INSTRUMENT FAILS ITS OWN POSITIVE CONTROL | check_
plan_freshness.py --self-test: the UNMUTATED case reports DIFFERS where it
should report MATCHES. All nine mutation cases behave correctly, and the live
--reproduce path does emit "STAMP MATCHES" for real plans, so this looks like a
defect in the self-test FIXTURE rather than in the instrument -- but that is a
guess and the point of a positive control is that it removes the guess. Until
it passes, the instrument cannot certify itself and its STALE verdicts cannot
be fully trusted, INCLUDING the one below. | S`

`2026-08-30 | city/alpine_basin_town_plan.json IS UNREPRODUCIBLE | Already known
-- the storey_m ruling changed the planner and the canonical plan describes the
PLACED town rather than what the planner now emits. Duplicates the 2026-08-29
"THE PLACED TOWN NOW DISAGREES WITH ITS PLAN" entry; kept here only so the
suite's third failure has a home and is not re-diagnosed from scratch next
session. Clears when the operator rules on re-placing the town. | -`

`2026-08-30 | THE PLAN-STAMP POSITIVE CONTROL -- **DONE**, and the finding was
the opposite of the fear | The instrument was CORRECT; its positive control was
the LIVE city/alpine_basin_town_plan.json, which ruling 4 legitimately made
stale one commit after stamping. verify() reported the truth and the assertion
was wrong. Fixed with a synthetic inert fixture; --self-test made standalone so
it stops reporting corpus state under the instrument's name; mutation cases
re-based onto a MATCHES baseline (their verdict half was vacuous); two cases
added. 12 cases, exit 0. Re-audit banked at _verify/20260830_stamp/ -- 18
MATCHES, 2 DIFFERS, NO VERDICT CHANGED. The instrument was UNCERTIFIED, never
wrong. R-STAMP + LESSONS 2026-08-30. | S`


`2026-08-30 | FORGE STAGE 4b: A REAL RETOPOLOGY PASS, WITH A GENUS TARGET |
NOT AUTHORIZED TODAY -- backlogged honestly. Stage 4 decimates and meets the
triangle budget while preserving topology exactly: the church is 60,000 tris
at genus 61, chi -120, unchanged from its 381,364-tri original. For a static
landmark seen at distance the operator has ruled 61 handles mostly cosmetic,
and the field is now named `tri_within_budget` so it cannot over-read. A real
pass is voxel remesh -> decimate, which DOES change topology, with a declared
genus target and a before/after report like stage 4's. Cost: remesh loses
surface detail, so the target trades handles against silhouette fidelity and
wants a rendered A/B rather than an arithmetic one. | M`

`2026-08-30 | THE FORGE'S SMART UV UNWRAP IS GREYBOX-GRADE AND SAYS SO |
stage 6 runs Smart UV Project when a mesh arrives with no UVs, which is every
TRELLIS mesh. It is a MACHINE unwrap: adequate for a generated greybox, not a
layout anything gets hand-painted on. Recorded in the report as
`uv_action` so a later texturing unit knows which it inherited. If a forged
asset is ever promoted to hand-authored art, the unwrap is the first thing to
redo. | S`

## Wood stack references — REFUSED at the input floor (2026-08-30)

`2026-08-30 | THE WOOD STACK REF SET FAILS 2 OF 4, AND IT IS A SUBJECT-SHAPE
INTERACTION WITH THE SPEC, NOT OPERATOR ERROR | az090 (751 px longest) and
az180 (785 px) fall under CHURCH_VIEW_SPEC's 800 px floor. MEASURED CAUSE: the
stack's HEIGHT is 633-693 px in EVERY view -- constant, correctly, because
azimuth does not change height -- while its WIDTH swings 908 -> 733 as it
rotates end-on. The floor binds on width alone and height can never rescue it,
because a woodpile is low and wide. The church passed all four only because it
is TALL: its longest dimension is >=872 px in every view, so no rotation could
drop it under. THE FIX THAT KEEPS THE SPEC INTACT: re-render the identical
framing at a 1280 (or 1536) frame -- every pixel dimension scales, all four
clear 800 (916/981/1135/1135 at 1280), and composition, distance and focal
length are untouched; broadside stays at 89% of frame width. DO NOT move the
camera closer for only the failing views: constant distance across views is
the spec's own rule and it calls varying scale a reconstruction hazard. |
OPERATOR |`

`2026-08-30 | THE 80-90% FILL BAND MAY NOT SURVIVE A NON-EQUIDIMENSIONAL
SUBJECT | Separate from the pixel floor and NOT fixed by a bigger frame: the
wood stack's end-on views measure 73% and 77% fill against a 80-90% band,
because from the end it simply occupies less of the frame at the same
distance. Fill and constant-distance conflict for any subject that is not
roughly equidimensional. Either the band relaxes for such subjects with a
recorded reason, or the spec accepts that only the broadside views sit inside
it. Worth settling before the third forge asset rather than re-arguing per
subject. | S`

`2026-08-30 | ⭐ RESOLVED — THE TWO WOOD-STACK REF ENTRIES ABOVE ARE CLOSED BY
THE PER-SET RULING, WITHOUT A RE-RENDER | Both entries above proposed operator
work: re-render at 1280 to clear the 800 px floor, and settle the 80-90% fill
band for non-equidimensional subjects. The per-SET ruling (2026-08-30) made
both unnecessary. Rotations are NOT held to longest-side or fill-low -- only
the master is -- so az090/az180 pass at 751/785 px and 73%/77% fill as
written. The refs were never re-rendered and the spec was not relaxed; the
floors were applied at the level they were always about. The wood stack forged
at 133.3 s, exit 0. NOTE the diagnosis in the first entry was CORRECT and is
worth keeping: the floor binds on WIDTH for a low wide subject and height can
never rescue it. That is why the master is DERIVED as the max-extent view
rather than declared. | DONE`

`2026-08-30 | THE FORGE PASSED A RATIFIED VRAM FLOOR BY 1.2% AND SAID NOTHING |
wood_stack peaked at 14,870 MiB against 15,045 MiB free -- 175 MiB of
headroom. VRAM fit is one of the four ratified ABSOLUTE acceptance floors, and
a pass at 1.2% margin prints identically to a pass at 40%. Anything heavier
than a 1.4M-vertex asset should be assumed not to fit until measured. FIX:
report headroom as a number in the stage-3 line and in forge_report.json, and
WARN below a threshold (10%?) without refusing -- the floor is fit, not
comfort, so this is a warning and not a gate. Pick the threshold from the two
runs we have (church 10,082 / wood_stack 14,870) plus the next one. | M`

`2026-08-30 | 20+ `text=True` SUBPROCESS SITES DECODE WITH THE LOCALE CODEC |
`forge.py::_run` was fixed after a PROVEN failure: cp1252 cannot decode 0x8F,
TRELLIS emits tqdm bars (U+258F = E2 96 8F), the reader thread died, and
`stdout` came back None -- which stage 3's `(p.stdout or "")` would have
turned into a false "could not look". `grep -n "text=True" scripts/*.py | grep
-v encoding=` lists 20+ more, including capture.py, check_plan_freshness.py,
concept_loop.py and nanite_batch_build.py. NOT swept blind, deliberately:
changing 20 decoders at once with a failing case for only one of them is how a
fix becomes the next defect. Do it with a test per site, or add a shared
`run()` helper and migrate call sites onto it one at a time. | M`

`2026-08-30 | STAGE 10 MEASURES LIKE A CHURCH NO MATTER WHAT IT IMPORTS | The
DESTRUCTIVE half is fixed -- DEST/NAME are templated and an unsubstituted
DEST fails closed -- but the MEASURING half is still church semantics:
`forge_scale_payload.txt` emits `church_top_cm`, `church_base_cm`,
`church_footprint_cm`, `church_over_chalet`, labels the actor `Forge_Church`,
and asserts `_ruling_1_target = 2.5` against a chalet companion built from
CHALET_W/D/WALL constants. For the wood stack the scale applies and reads back
correctly while every one of those keys is misnamed and the ratio is
meaningless. forge.py prints a NOT-GENERAL warning instead of pretending
otherwise. FIX: rename the output keys to asset-neutral ones
(`top_cm`/`base_cm`/`footprint_cm`), make the companion + ruling comparison
OPTIONAL and recipe-driven (only the church declares a ratio_against), and
keep the orientation gate as-is since it is already general. THEN run stage 10
for the wood stack -- it has NOT been run. | M`

`2026-08-30 | ⭐ DONE — STAGE 10 GENERALISED AND RUN FOR THE WOOD STACK | The
entry above ("STAGE 10 MEASURES LIKE A CHURCH NO MATTER WHAT IT IMPORTS") is
CLOSED. Output keys are asset-neutral (top_cm/base_cm/footprint_cm), the label
and the scale rationale are passed in, the ratio is reported ONLY when the
recipe declares ratio_against, and the level is per-asset. Also added, beyond
the original brief: the declared target is now CHECKED against the read-back
(height_error_cm, height_within_1pct), and forge_record_stage10.py folds the
result into forge_report.json + ASSETS.md instead of it being retyped. Wood
stack measured 120.0 cm top against a 120.0 cm target, error 0.00, orientation
gate passed, 14,996 tris. | DONE`

`2026-08-30 | THE KIT CHALET'S ROOF READS AS A GNARLED ARCH, NOT A ROOF |
OBSERVATION from the stage-10 frames, not a blocker. ROOF_PKG
(/Game/Meshes/Houses/Roofs/House02_Roof/SM_House02_Roof) renders in
woodstack_beside_kit.png as a thin organic arch straddling the wall box --
it does not read as a house roof at all. The MEASUREMENT is unaffected and
appears correct: chalet_silhouette_cm comes back 536.5, exactly the
reference_cm the church recipe declares, on both the church run and this one.
So this is a question about WHICH MESH that package is, not about the number.
Worth resolving before the companion is used as a visual reference in anything
an operator judges by eye. | S`

- **brief_loop cycle judge** (2026-09-03, scoutproof): when a flat_site's
  slope rule and elev-band rule are jointly unsatisfiable (rough base
  terrain vs shallow carve), the judge oscillates between regimes
  (anchor 95 -> 42 planing, then reset to 94, twice over 14 iterations)
  and burns the whole cap before the honest refusal. Detect the
  regime alternation (slope-branch <-> elev-branch, 2 full cycles) and
  refuse early with "criteria jointly unsatisfiable at this site".
  Evidence: _trash/scoutproof_oscillated + task log 2026-09-03.

- **Ground cover needs a REPRESENTATION in the band below its cull**
  (2026-09-08, ruled). Ryan ruled that Meadow (50 m) and Blueberry (45 m)
  KEEP their authored culls, and the `silhouette` alternative is closed on
  the measurement: Meadow's silhouette boundary is 123.8 m, still inside the
  256 m World Partition streaming range (`RuntimePartition.cpp:27`), so it
  narrows the gap without closing it. HLOD proxies only take over BEYOND that
  range, so ground cover has nothing standing in for it between its cull and
  256 m at any threshold. **The cull is not the variable — the missing band
  is.** Options not yet costed: a ground-cover imposter/card layer, a
  terrain-material detail-blend that fakes it past the cull, or accepting the
  gap and measuring how it reads. Until one exists the authored culls stand.
  Evidence: LESSONS 2026-09-08k and 2026-09-08m, R-CULLDERIVE.

- **RETIRE the `_stamp_waiver` on `city/alpine_basin_town_plan.json`**
  (2026-09-08). The waiver is honest about being MATERIAL, not inert:
  `scripts/plan_city.py` 72118abd4195 -> c70ad130b051 (abe88eae, RULING 4)
  now consumes `buildings.roof_servability`, so re-running the planner today
  produces different roofs from the 303 on disk. The servability output
  already exists as `city/alpine_basin_town_plan_roofbias.json` (**348
  roofs**) and has never been adopted; CLAUDE.md's CURRENT SPEC still records
  303. Adopting it is a TOWN decision gated on the Medieval Village kit, not a
  freshness decision. **Retire this waiver when the town is rebuilt from the
  kit** — at that point the plan is regenerated and the waiver must be deleted
  rather than re-granted. It expires by itself if any named input moves again
  (`granted_for` is bound).

- **RETIRE the `_stamp_waiver` on
  `city/alpine_basin_town_plan_roofbias.json`** (2026-09-08). This variant's
  `recipes/city.json` stamp (1a86693e4c2d) predates the storey ruling, so its
  building heights are the OLD `storey_m` 3.2 and it is **not buildable as it
  stands**. It is kept as the record of what roof servability produced. If it
  is ever adopted it must be REGENERATED against the current recipe first, and
  the waiver deleted.

- **A `_frozen` marker for evidence plans, so waivers stop doing that job**
  (2026-09-08). 14 of the 18 waivers granted today are foliage plans for the
  pre-8K world and four `_verify/` benchmark spikes. They are supposed to be
  stale — they record what was placed WHEN THE BENCHMARK WAS MEASURED, and
  regenerating them would mutate `_verify/` evidence that CLAUDE.md holds is
  "cited, never obeyed". `check_plan_freshness` has no concept of an artefact
  that is deliberately frozen, so a waiver is standing in for the missing
  concept — and a waiver is a gate turned off, which is the wrong instrument
  for "this is correct as it is". Add `_frozen: {why, since}` handled as its
  own verdict (FROZEN, not WAIVED) and convert those 14. Evidence: LESSONS
  2026-09-08m.

- **LOD switches carry a TONAL step, not a silhouette one** (2026-09-08, E2).
  Every failing row of the LOD silhouette audit failed on `luma_delta_weber`
  alone -- never on coverage or IoU -- rising monotonically with LOD index on
  all three non-Nanite species (ConiferPine 0.108 -> 0.328, SpruceSub 0.053 ->
  0.086, SpruceSapling 0.350 -> 0.605 at their current switch sizes, against a
  0.03 threshold). This corroborates `measure_lod_materials.py`'s recorded
  "trunks beyond ~50 m go uniformly pale", which already established that
  every LOD carries LOD0's materials across the same sections -- so it is the
  material's DISTANCE behaviour, not a lost section.
  **NOT ACTIONABLE AS MEASURED**: `luma_delta_weber` normalises by mean luma,
  and these captures were lit by the level's own sun at 2.5 km with the
  subject largely backlit and dim, which inflates the ratio. Re-measure under
  controlled lighting (a dedicated key light, or an emissive-neutral setup)
  before proposing any material change.
  Evidence: `_verify/bench/2026-09-07/lod_silhouette.json`, LESSONS
  2026-09-08s, R-LODSILHOUETTE.

- **The perf budgets were ratified against an EDITOR baseline whose
  measurement is a 60 Hz cap** (2026-09-08, E3). `check_perf.py`'s RED on
  plaza (Game 14.00 vs 12.00) is the editor's frame cap, not the world:
  editor FrameTime p50 is 16.67 ms at ALL FOUR stations and GameThreadTime
  tracks it (13.90-14.15) regardless of content. Standalone at 4K, same
  stations, 25 s windows: Game 3.85-4.05 ms, every zone under both budgets.
  **NEEDS A RULING, not a script.** Options, none taken: (a) leave the
  budgets as an editor-side regression tripwire and stop reading them as
  world cost; (b) restate them against a standalone baseline; (c) keep both,
  policed separately. The editor number is not wrong -- it measures a
  different thing -- so this is a decision about what the budget is FOR.
  Also fix on whichever path: `_verify/perf/20260905_fov90.json` records
  `viewport_size: null`, so its GPU figures cannot be placed beside anyone
  else's (rule 12).
  Evidence: `_verify/perf/standalone_2026-09-07/perf_standalone.json`,
  LESSONS 2026-09-08t, R-PERFSTANDALONE.

- **A sunlit dolly heading has not been chosen** (2026-09-08, E4). The 3 s
  dolly along near_ground's own forward vector does NOT stay out of canopy
  shadow: the lit share of the ground half falls 41.1% -> 17.7% over 4.2 m
  (dappled meadow shadow, not a solid edge). E4 said capture once and do not
  score, so no heading was re-chosen and no threshold was moved to make it
  pass. If a sunlit 3 s path is wanted, it needs picking -- candidates: rotate
  the heading toward the sun (azimuth 285 deg, elevation 12 deg), or move the
  origin a few metres into the lit patch visible in frame_0000. Choosing one
  is a decision, not a fix.
  Evidence: `_verify/bench/2026-09-07/dolly_sunlit.json`, frames 0000/0089,
  LESSONS 2026-09-08u, R-BENCHDOLLY.

- **A multi-angle survey of a sample project needs a mechanism we do not have**
  (2026-09-08, census). `-ExecCmds` fires every command in one batch at
  startup, so `HighResShot` is issued in the same breath as `BugItGo` and the
  frame is captured before the camera settles -- three attempts on City
  Sample, including `ghost` no-clip flight and `r.HighResScreenshotDelay`, all
  produced five frames of the same plaza. `-ExecutePythonScript` cannot help:
  it calls `UUnrealEdEngine::CloseEditor()` when the script returns, so a tick
  callback never runs. Candidates not tried: a camera actor possessed by a
  Level Sequence rendered through MRQ (the Bench_Dolly pattern, which works in
  our project), or enabling `bRemoteExecution` in the sample's config so
  ue_exec and shoot.py can drive it -- the latter is a config write outside
  this repo and needs an explicit ruling under standing rule 1.
  Evidence: `research/census/shots/CitySample/README.md`.

- **The shot-differentiation check ranked the failure above the success**
  (2026-09-08, census). Written to catch "the camera never moved", then
  calibrated against the known-bad set: bad scored 10.37, good 9.77. Shader
  compilation progresses between launches and recolours a static scene by
  more than a camera move changes it; greyscale downscaling does not suppress
  it. The check now reports NO VERDICT. A real one needs to compare
  STRUCTURE, not intensity -- edge maps, feature matching, or the rendered
  camera transform read back from the log rather than the pixels.

- 2026-09-10 | Brief 2b: correct the sun temperature | The recipe sun at
  7800 K is suspect for a low alpine sun (natural 4500-5500 K at 12 deg
  elevation), REGISTERED in Ryan's 2026-09-10 ruling. When it moves,
  grade.white_temp_k follows it by R-GRADE's rule (= the sun, never above).
  One variable, one capture. | S

- 2026-09-10 | OPEN QUESTION: the 0-dirty editor close wedge | R-EDITOR-CLOSE
  fourth occurrence deadlocked with NOTHING dirty: window destroyed, process
  wedged idle (0.1 s CPU/10 s, 12 GB RSS, remote exec dead). The dirty-modal
  theory cannot explain it. RULED 2026-09-10: logged as open, NO investigation
  that session; the census/quiet/retry/kill gate handles it operationally
  either way. Diagnosing needs a teardown stack (procdump or ensure
  -log tail at close), which is its own session. | ?

- 2026-09-10 | Brief 2c: Lumen far-field on RT-enabled HLOD proxies |
  RELABELLED from "Brief 2b" by ruling 2026-09-10 (that name now means the
  executed sun-temperature correction). Spec: FOR_CLAUDE_CODE Task 7 --
  proxies rebuilt support_ray_tracing=True, r.LumenScene.FarField=1,
  FarField.MaxTraceDistance 1e6; scored on vista far-band shadow_tint_B and
  peak VRAM at open. Ryan rules go/no-go on the numbers; R-RTFENCE stays
  on. Separate session, ruling first. | M

- 2026-09-10 | Clouds coverage 0.1 capture | RULED 2026-09-10:
  Cloud_GlobalCoverage 0.3 rendered as NEAR-TOTAL OVERCAST on the vista
  still. Next cloud capture runs at 0.1 with the parameter READ BACK from
  the reloaded /Game/Bench/MI_AlpineClouds and the vista sky luma reported
  against the pre-cloud 0.7311. Not run in the 2026-09-10 session by
  ruling. | S

- 2026-09-11 | Brief 5 experiment: instanced-HLOD range vs approximate
  hand-off | REGISTERED BY RULING: treeline GPU only dropped 7.86 -> 7.52
  when the main range fell 768 -> 512, so most of its rise belongs to the
  2 km INSTANCED layer, not the main grid. The experiment: sweep the
  instanced range (2 km vs 1 km vs the old 512) against where the
  approximate/merged layer takes over, scored on treeline/vista GPU p90
  (standalone class) and the vista mid-band look. Decides how much of the
  512-era headroom the instanced layer is worth. R-RANGE carries the
  tables. | M

## OWED — .git history rewrite to reclaim frame bytes (Ryan's go) — added 2026-09-15
`_verify/**/*.png` and `_verify/**/*.exr` were untracked 2026-09-15 (closure
D-1 item 4): 2,860 frames removed from the index (kept on disk), new ones
ignored. This stops the bleed but does NOT shrink `.git` — the ~1.2 GB of
historical bench/hero frames still live in history. A `git filter-repo`
pass would reclaim them; it rewrites every commit hash, so it is Ryan's
call and a dedicated operation, not a side effect of a working session.
`_trash/` is 6.9 GB and was NOT emptied this session.

## Rulings owed (Ryan)

`2026-09-16 | plan_city off-network building threshold needs Ryan's ruling
| recipes/city.json:152 carries _THRESHOLD_NEEDS_A_RULING: the
max_orphan_building_fraction 0.05 is provisional, chosen ABOVE this
town's measured 3.6% so the gate went live without condemning the
committed town. Alternatives: 0.0 (current town FAILS, plan_city cannot
reproduce its own committed plan, breaks pipeline rule 3) or report-only.
The request had lived only in the recipe comment and
commits/msg_debt_sweep.txt:46 — invisible at session start until this
line (Pass 5 batch 4). | S`

`2026-09-16 | alpine_8k.json FAILS its own offline validator (pre-existing,
found during Pass 3) | import_heightmap --recipe recipes/alpine_8k.json
--offline REFUSES on two counts at HEAD (verified pre-dating the Pass-3
edits): (1) dot-p-y substring 'shade_reference.py' in the lighting block
(the R-METER guard); (2) unknown key foliage.species[0].card. Either the
recipe carries stale prose/keys or the validator's key set lags the
schema — needs a ruling on which side moves. alpine.json validates clean.
| S`

`2026-09-16 | exclude-only biome glob can cross biomes | place_foliage
exclude_only globs foliage/{biome}_*.json, and biome 'alpine' also
matches alpine_8k_*.json — a --recipe recipes/alpine.json --exclude-only
run would rewrite an alpine_8k tree plan against alpine's exclusion
(species names overlap; found by the Pass-3 auditor, pre-existing).
Unreachable today only because alpine.json lacks settlement_exclusion
and refuses first. Tighten the glob or match plans to the recipe's
biome_id exactly. | S`

`2026-09-16 | truth-run expected-set transport size unconfirmed |
bench_capture --truth now (correctly) queries the expected set at the
truth range (~12 km), which returns every spatially-loaded main-grid
actor in one remote-exec JSON reply, and the sidecar stores the full
name list. No size guard exists in bench_expected_set.py or the
transport; confirm a multi-thousand-name reply survives before relying
on a truth-run residency verdict (auditor question, Pass 3). | S`

`2026-09-16 | verify_landscape's DEFAULT_RECIPE points at the pre-8K world
| A bare `python scripts/verify_landscape.py` inherits landscape_spec's
default recipes/alpine.json — the legacy /Game/Alpine world CLAUDE.md
marks as HISTORY. Fail direction is SAFE (the level gate exits 7 when
/Game/Alpine8K is open), but the default silently verifies against a
dead spec; deserves a ruling on the landscape_spec side (change the
shared default vs per-tool defaults). Found by the Pass-3 reading. | S`

`2026-09-16 | shell-side write-target scanning for the path hooks |
guard.py's engine-file/outside-repo/LESSONS-append-only/vendor rules
bind only to Write|Edit|NotebookEdit; shell redirects and sed -i bypass
them (Pass-3 reading F9, recorded in GOVERNANCE_MIGRATION). Design a
Bash|PowerShell rule scanning commands for redirects/copies targeting
ENGINE_SUFFIXES, LESSONS.md and out-of-root paths without drowning in
false positives. | M`

`RESOLVED 2026-09-21 (Item 8) — MEASURED. The MRQ StartConsoleCommands channel
delivered wp.Runtime.HLOD 0 on a -game command-line render AFTER world load and
it APPLIED: GPUSceneInstanceCount dropped 61,427 (4.37%) in the HLOD-off arm at
both stations (the counter v3 could not move). HLOD proxy GPU share = 0.576 ms
(1.2%, x2.9 the A/A floor -> MEASURED) at treeline, 0.457 ms (below its noisier
floor -> MEASURED-NEGLIGIBLE) at vista; per-pass drop is NaniteVisBuffer +
ShadowDepths + Basepass. Pixel diff 0.20% of non-sky (~3x the A/A pixel floor),
far below the derived 0.05727 beyond-512 fraction -> the instanced tree proxies
are a thin subset of the far field; cheap by construction. Fence held (census
CLEAN, world byte-identical, scratch deleted, 0 DEVICE_HUNG). Two caveats: the
~49 ms/frame is MRQ full-quality 4K (transfer the SHARE FRACTION, not the ms);
and a -game MRQ renders off the profiled game loop (window on GPU/Basepass>0, not
GPUTime). B5.19 = M. Evidence: research/brief5/input/item8_share.json + for_desk/
INDEX_i8.md. NOT PUSHED.`

`2026-09-20 | Brief 5 item 8: measure the HLOD proxy GPU share in a -game MRQ
HLOD-toggle pass | Baseline v3 left this INCONCLUSIVE -- the one open number.
The -game startup ExecCmds channel cannot toggle wp.Runtime.HLOD post-stream
(FAutoConsoleCommand, one-shot pre-stream; as-is vs hidden byte-identical on
every render counter -- research/brief5/input/hlod_task2_gamepath.md), and the
editor renders real cells at full residency (proxies hidden, so an actor-hide
A/B measures nothing). The clean path is a -game MoviePipeline render of a
vista/treeline Level Sequence with HLOD on vs off delivered AFTER world load
(the untested -game MRQ command-line + a post-load exec channel). Composition is
already known (Instanced=INSTANCING lowest-LOD ISM, Merged=MESH_APPROXIMATE,
rendering beyond 512 m -- cheap by construction); this is the ms share / live
pixel fraction only. Same session also closes the derived proxy_fraction 0.05727
vs the live fraction. Candidate positive control: wp.Runtime.ToggleDrawRuntimeHash2D
(doc-sourced runtime view of loaded HLOD cells, WP-HLOD 5.8 doc; UNVERIFIED in
5.8 live enumeration -- enumerate before use). DEVICE_HUNG-history machine -> its
own dedicated session. | L`

`2026-09-20 | LFS-migrate the >100MB non-LFS blobs OR the close-out push cannot
complete | github.com hard-rejects non-LFS files >100MB; history has .exr captures
123-133MB each (_verify/bench/**, 5.3GB) + 19.4GB of non-LFS .png. push_chunked.py
advances the branch until it hits a >100MB commit then stops (research/GIT_LFS_AUDIT.md).
Fix = git lfs migrate import --include=".exr,.png,..." on a coordinated history
rewrite (all clones re-pull) + the proposed .gitattributes additions. Forbidden
without Ryan (rewrite/force). Decide: migrate, or stop committing large captures
(gitignore _verify/bench/**/*.exr like the perf CSVs). | L`
`2026-09-20 | Brief 5 desk deliverable (brief5_desk.zip) never landed on disk |
The overnight queue's T0-T6 (LOD ladder, canopy cover, see-it A/B, hold, rungs,
HLOD staleness) are all blocked for lack of BRIEF.md/FOR_CLAUDE_CODE.md/
lod_ladder.py/canopy_cover.py/derived_ladder.json. Resend/place the zip and the
queue can run as written. | -`

`2026-09-21 | Brief 5 T4: add intermediate LOD rungs to ScotsPineTall_01 +
spruce_half_01 to bring forest_floor back under the 12.5 ms budget | Brief 5 R3
proved the persisted hold is LIVE and costs +1.597 ms at forest_floor (p90 12.645
> 12.5 by 0.145 ms) because the 128-512 m band now renders full LOD2/LOD3 geometry
instead of the card. T4 inserts reduced-tri geometric LODs between the last real
LOD and the card, target_tris from research/brief5/derived/derived_ladder.json
(rule target_tris(D)=tris_anchor*(D_anchor/D)^2, constant on-screen tri density).
ConiferPine: +2 rungs before the card -- 1444 tris @ engage 180.8 m (SS 0.11894),
361 tris @ 361.6 m (SS 0.05947); full chain tris [27824,11062,5777,1444,361,32]
@ SS [1.50451,0.33642,0.23788,0.11894,0.05947,0.03818] (4 LOD -> 6). SpruceSub:
+2 rungs -- 647 tris @ 85.0 m (SS 0.17503), 162 tris @ 170.0 m (SS 0.08752); chain
tris [20695,10347,5174,2587,647,162,6] @ SS [1.0,0.99,0.6,0.35,0.17503,0.08752,
0.02642] (5 LOD -> 7). Conifer (Norway Spruce) is Nanite single-rep -> no ladder;
SpruceSapling has no card -> no action. Projected forest_floor tri cut (uniform-
density ESTIMATE): ConiferPine 3.10M -> 0.93M (-70%), SpruceSub 1.45M -> 0.17M
(-88%), added geometry ~4.55M -> ~1.10M (-76%) -> should clear 12.5 ms. BUILD is
all WRITES, out of the R1-R4 read/2-mesh fence: (1) SetLodReductionSettings per
new LOD or SetLods with a reduction chain -- B5.21: SetLods REGENERATES the chain
from LOD0, so _SRC-back up, apply, verify LOD0-2 tri counts UNCHANGED; (2)
SetLodScreenSizes with the 6/7-entry arrays; (3) R1 persist protocol (modify(True)
+ save only_if_is_dirty=False + cold distinct-process readback of per-LOD tri
counts + screen sizes). OPEN GATES before running: texel_gate NEEDS_READBACK
(frame_px = atlas size + frame grid, desk Task 2, card texel budget unverified);
B5.11 crown-thinning risk at 1444/361/647/162 tris (per-rung visual check);
acceptance = re-run R3 forest_floor p90 <= 12.5 ms. Needs fence lift + auditor
gate + risky-op tag. | L`

## Brief 5 Part C — owed after Overnight Queue 2 (2026-09-21)

`RULED 2026-09-22 (Ryan): forest_floor budget = 12.5 (R5-1 stands); the Queue-2 header's 13.0
is DROPPED. density_project.py re-run and DENSITY_PLAN.md updated: forest_floor proj 13.474 is
OVER 12.5 by 0.974, and the current hold 12.645 already busts 12.5 by 0.145. DONE.`

`2026-09-21 | Clutter cost measurement (game-thread + GPU ms per 1000 by class) | The P3
acceptance. PCG-graph authoring was PROVEN this session but the cost arms were defeated by the
overnight harness (background-command reaper + editor unresponsiveness), NOT the approach. The
gated harness is staged: run scratchpad/pcg_measure_fast.py (base 1000, no GC) FOREGROUND against
an already-loaded editor for game-thread cost; a -game MRQ pass on a saved scratch level for GPU.
input/clutter_inventory.json fixes the spawn set. | S supervised |`

`2026-09-21 | forest_floor post-hold per-tree rate + in-game HLOD share | The DENSITY_PLAN
forest_floor growth is a pre-hold lower bound (0.1003 card-era rate on a post-hold baseline); a
post-hold rate re-measure tightens it. And item 8 measured the HLOD share only at treeline/vista
(MRQ) -- forest_floor/plaza HLOD growth under the density multiplier is unmeasured; needs a
PIE-side in-game HLOD share. | S each |`

`2026-09-21 | Enable PCG Biome Core (+ PCGBiomeSample, PCGGeometryScriptInterop) | Confirmed
present in the 5.8 install (Engine/Plugins/Experimental). Deferred overnight as non-essential
(P3 uses core PCG) + experimental-open risk under autonomy. One .uproject edit behind a
checkpoint tag, editor-opens-clean-twice verify. | S supervised |`

`2026-09-23 | Scattered-cumulus cloud material (Brief 7 L0 fallback) | The engine
SimpleVolumetricCloud (MI_AlpineClouds, child of m_SimpleVolumetricCloud_Inst) cannot produce
scattered cumulus with >=60% clear sky at the vista -- coverage 0.20/0.08/0.03 all render a broken
deck (research/brief7/stills/p0_cloud/). The cloud actor Lighting_alpine_8k_Clouds is DISABLED for
Brief 7 P1-P3 (hidden_in_game + component visible=False; open SkyAtmosphere per Ryan's "open sky
beats a lid"). To restore clouds: author or source a WeatherMap-driven volumetric cloud material
(discrete cumulus, coverage that actually clears sky), bind it to the component, re-enable the
actor, re-verify at the vista. | M |`

`2026-09-23 | Foliage-LOD settle for cold-editor captures (Brief 7) | A ~1.8 s boost + 4 s
HighResShot poll in a FRESH editor leaves near-field foliage at card LODs (visible in
research/brief7/stills/p0_L0/near_ground_look.png); a warm editor renders full geometry. Clean
near-field deliverable stills need a longer settle (more ticks) or a warm-up pass before the shot.
Add a --settle option to shoot.py / a foliage-LOD-resolved wait. | S |`
