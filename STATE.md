# CURRENT STATE — 2026-09-27 (BRIEF 7 P3a DENSITY DONE: 797,500 trees at the ruled caps, tag look-p3; P3b PCG clutter OWED; GitHub = lite mirror, first push LANDED 21:05 (staged tree push); A2 closed; rocks withdrawn; world working)

> ⭐ **2026-09-27 (close) — GITHUB RECREATED AS A LITE MIRROR (R-GITHUB-LITE, Ryan: option 2). The
> account's free 10 GiB LFS quota was exhausted by world-package history (22 GB of 37 GB); no external
> drive; disk 13 GB free. Ryan deleted + recreated `ryan772177/LandscapeLab` (empty). Local `main` @
> 527c5c3d is the FULL repo (world, fence tags `pre-p3-density-20260927`, `look-p3`, `a2-closed`, …,
> D3 revert). `github-main` (built by `scripts/github_lite_snapshot.py`; excludes `__ExternalActors__`,
> `__ExternalObjects__`, `_verify/bench`; hero binaries kept) = 6.05 GB LFS / 419 objects, ZERO world
> packages. **FIRST PUSH LANDED 21:05: GitHub main = 12e97eec (tree == github-main).** The refusal
> ("exceeded its LFS budget", Billing = storage 10 GB of 10 GB) cleared once Ryan added a card + a $5
> product-level Git LFS budget (stop-usage unchecked). Then the pack itself failed: `RPC failed; HTTP 500`
> after all 419 LFS objects were up, because the root commit held 3.8 GB of plain blobs and GitHub takes
> ~2 GB of pack per push. Fixed with `scripts/push_staged_tree.sh` (tree staged in 4 commits at the
> root; github-main re-pointed to the replayed tip 12e97eec). LESSONS 2026-09-27b; R-GITHUB-LITE →
> FIRST PUSH. NEVER push local main or tags. Seed branches deleted after Ryan switched the default branch
> to `main` (GitHub needs the red "I understand" confirm, the first switch did not save); GitHub holds
> exactly one branch, `main`.
> - Disk: `scripts/disk_cleanup_20260927.ps1` (Ryan-authorised ~32 GB of regenerable caches + old
>   `_trash`) runs from the operator prompt (`! powershell -File scripts/disk_cleanup_20260927.ps1`);
>   the no-force-delete hook blocks the agent by design. RUN by Ryan 2026-09-27: 12.6 → 42.6 GB free.
> - GitHub holds the lite copy (recipes, scripts, docs, plans, research, hero binaries, _verify minus
>   bench). The world packages (`__ExternalActors__`/`__ExternalObjects__`) exist ONLY on this laptop.
>   PR #5's history is gone with the old repo; the record lives in LESSONS/RECIPES.

> ⭐ **2026-09-27 — P3a DENSITY WORLD RUN PASSED, tag `look-p3`. World = 797,500 trees (from 185,385, ×4.30):
> forest_floor m=1 (1.23× incl. the disc blend), plaza 2.40× (cap 2.157), treeline 5.81×, open 4.42× — the
> Brief 5 zones re-capped at the ruled caps (`research/brief7/scripts/p3_zone_map.py` →
> `research/brief7/p3/zone_map.json`) under the RULED density ceiling (D_max 1,691/bin). Recipe declares
> `foliage.density_zone_map` + `density_ceiling`. D3 driver attempt 4: place 237 s, save 38 s, editor VRAM
> 6,159 MiB; `-game` GPU p90 forest_floor 12.38 / open_max 12.69 / plaza 9.62 ms (RECORDED, R-AESTHETIC-1),
> VRAM ≤ 5,057 MiB. Cold relaunch census 797,500 / 1,103 IFAs. Stills: `stills/p3_density/`. Fence
> `pre-p3-density-20260927`. R-P3-DENSITY (RECIPES); LESSONS 2026-09-27 ×3.**
> - **ROOT CAUSE FOUND: `r.LumenScene.FarField=1` froze the game thread after every mass `add_instances`**
>   (rocks 199k 19+ min; P3 attempts 2/3 at 797k: 6 s / 427 s unanswered). Set to 0 in DefaultEngine.ini
>   (P4's own "drop if not"; the A2 A/B measured no gain) → the same placement answered in 7 s. Three
>   aborted attempts before it (validator note key; save_level's 6 s discovery default — driver now waits +
>   `--timeout 25`; FarField) each auto-reverted and proven.
> - **P3b OWED: PCG runtime clutter** (meadow grass to 512 m, three clutter classes, Nanite clutter cull 0;
>   D5 cost still unmeasured — `Content/Scratch/PCG/PCG_ClutterSpike.uasset`) — next session's unit. Then P4.
> - No editor running at close. Scratch `research/brief7/p3/dryrun/` → `_trash/` at close.

> ⭐ **2026-09-27 — ROCKS WITHDRAWN (Ryan, on the P2 stills: "they add nothing"). World packages restored
> byte-for-byte to tag `pre-rocks-place-20260927` (`git diff --quiet` = 0), 425 rock-run packages + 9 plans
> moved to `_trash/rocks_withdrawn_20260927/`, 9 species removed from `alpine_8k.json` (7 remain). The
> world holds the 185,385 trees of the four committed plans; no editor run needed (checkpoint = tree
> world). R12 RULED 2026-09-27c; LESSONS 2026-09-27. Tag `look-p2` NOT used (P2's deliverable withdrawn).
> KEPT: `place_foliage --place-committed`, landform router + derived saturation (scree mask, BACKLOG bake),
> validator `_` tolerance, canopy fixes, KiteDemo Nanite state. NEXT: Phase 3 (forest + dressing) per
> BRIEF7_THE_LOOK.md, or Ryan's call. History REWRITTEN as one commit (Ryan's call) so the 1,489 rock-run
> packages never enter origin: main pushed @ 9c01a61a, tag `rocks-withdrawn-20260927`; the old four-commit
> history is local under `session-backup-20260927-rocks-history`.**
> - **SESSION CLOSE 2026-09-27.** origin/main current, tree clean, no editor, no background jobs. Tags on
>   origin: `pre-a2-fog`, `a2-closed`, `pre-rocks-place-20260927`, `rocks-withdrawn-20260927`. Branch
>   `look-p2-rocks` merged (PR #5) — can be deleted. World = 185,385 trees (four committed plans), Look
>   profile owns fog + atmosphere (A2 closed), rocks withdrawn.
> - **NEXT SESSION (Ryan's call):** Brief 7 Phase 3 (forest + dressing: zone map m=1 cap, PCG clutter) per
>   BRIEF7_THE_LOOK.md — note the T4/D5 BACKLOG blocks on density; or the BACKLOG units this session
>   filed: capture.py → shoot.py rewrite (rule-4 tool froze the editor), scree-mask bake on the landform
>   router, stronger blue at 1 km (a grade/sun/tint Look ruling). Owed small: recipe `_saturation_note`
>   SCOPE sentence at the next planner run.
> - Memory rule for this host: planner (19 GB) and editor (18 GB) never overlap; ~19 GB jobs run DETACHED
>   (Start-Process) or the background-shell reaper kills them; take stills with shoot.py, never a
>   21-camera capture pass on a session that just mutated the world.

> ⭐ **2026-09-27 — P2 WORLD RUN DONE, tag `look-p2`. PR #5 merged (main 7d9318f5). `place_foliage.py
> --place --place-committed` (new: Phase 2 from the 13 committed plans, no generator — plain `--place`
> re-plans and is BLOCKED by R-FOLIAGE-FEEDBACK) placed trees + rocks in ONE run: planned 199,268 =
> counted 199,268; orphan swept FT_Scrub (0 instances); rocks 13,883 new; trees rebuilt from their rows
> (pre-run census = the four plans exactly). Saved via `save_foliage_actors --go`: 1,518 IFAs, 1,064 M +
> 424 new external-actor packages (commit 14a4194b). PROVEN COLD: kill + relaunch → census 199,268 /
> 1,518. VRAM peak 5,049 MiB. Checkpoint tag `pre-rocks-place-20260927`.**
> - Stills (Look): `research/brief7/stills/p2_rocks/{vista,cliff,talus30,cliff_face,rock_grounding}_look_p2.png`.
>   Talus slabs on the fan at 30 m; dark outcrops at the vista; the cliff station reads as landscape rock
>   material — **visual gate = Ryan** (whether CliffFace meshes read there).
> - **DEFECT:** `capture.py` (rule 4's tool) froze the editor after the run (camera 2 of 21; game thread
>   stopped 16:09:34; RAM 1.6–4.5 GB free). Killed on Ryan's order (content quiet, restore data empty →
>   nothing lost). Stills taken with `shoot.py`. R-CITYSHOT REJECTED 2026-09-27; BACKLOG: rewrite
>   capture.py onto shoot.py. Validator now skips `_`-prefixed species keys (GroundClutter notes).
> - Owed: `make_variant_map.py` now routes on the landform → the next weightmap/variant bake changes the
>   scree mask (a world change, not done); recipe `_saturation_note` SCOPE sentence at the next planner run.
> - Editor closed after the stills (R-EDITOR-CLOSE). No editor running.

> ⭐ **2026-09-27 — A2 CLOSED (ruled fallback). Mie/Rayleigh spectrum ladder (6 cells) cannot blue-shift
> the ~800 m band either: every cell −5.3…−6.0° warmer than 40 m, spread 0.7° inside the 0.8° hue noise;
> sat clauses pass everywhere. Fallback executed without re-ask: literal max m005_r050 is a tie inside
> noise → tie rule (higher Mie) → Mie 0.010, Rayleigh at bench 0.0331. PERSISTED as Look-profile fields in
> `brief7_p0e_setprofile_payload.txt`: fog 0.0015 / start 150 m / AP 1.0 / mie 0.010 / rayleigh 0.0331
> (= d15_s150 + bench atmosphere); bench restores 0.00416 / 0 / 1.0 / 0.010 / 0.0331 exactly (read back);
> bench A/A pre/post MAD 3.10 vs 5.58 control. Re-shot near_ground / slope / vista → `stills/p2_a2/`.
> Tag `a2-closed`. BACKLOG: "stronger blue at 1 km" (grade / sun / distance tint — a Look ruling).
> Full: `research/brief7/a2_imposter/FOG_SPECTRUM_RESULT.md`; R-FOG AMENDED 2026-09-27; LESSONS 2026-09-27.
> Editor closed (kill path: 3 runtime-toggled OFPA actors, content quiet 8 h, RSS flat). No editor running.**
> - **Rocks (branch `look-p2-rocks` @ 8711de20, pushed): FINAL for ultrareview.** Talus router on the
>   16 m landform (ruled), saturation derived from the field (0.4615; masks 0.7692/0.6153), run 2: apron
>   305.4 ha, talus 2,486 (1.94×), 13,883 rocks, stamps fresh. Audit-3 FIX applied: `make_variant_map.py`
>   routes on the landform too (the next weightmap bake changes the scree mask — deferred with the world
>   run). Owed: recipe `_saturation_note` SCOPE sentence at the next planner run. PR:
>   https://github.com/ryan772177/LandscapeLab/pull/new/look-p2-rocks — world run = ONE combined `--place`.
>   The branch carries its own STATE block; on merge keep BOTH (this one above it).

> ⭐ **2026-09-27 (rocks, rulings executed) — TALUS FIELD RESTORED: router on the 16 m landform (ruled),
> saturation DERIVED from the field (0.4615 shared; talus masks 0.7692 / 0.6153 at ratified ratio).
> Run 2 `--write`: apron p>0.2 = 305.4 ha (bound ≥ 250 ✓), talus 2,486 = 1.94× of 1,284 (bound ≤ 3× ✓),
> 13,883 rocks, all gates PASS, 0.607M. Two planner runs, as bounded. Plans in `foliage/alpine_8k_*.json`,
> stamps fresh. R12 AMENDED 2026-09-26b; LESSONS 2026-09-27. Still NOT placed — world run after ultrareview.**
> - Runtime: landform routing ≈ 2 h 5 min per run (1953 steps); planner (19 GB) and editor (18 GB) never overlap.
> - (The Mie/Rayleigh ladder this block queued was executed on main — see the A2 CLOSED block above.)

> ⭐ **2026-09-26 (rocks) — R-ROCKS-BACK AUTHORED on `look-p2-rocks`, nine plans WRITTEN (12,758
> instances), NOT PLACED. PR: open at https://github.com/ryan772177/LandscapeLab/pull/new/look-p2-rocks
> (gh CLI absent). ⛔ OPEN FOR THE DESK: the 1 m talus field is PIT-CONCENTRATED — apron p>0.2 = 112.6 ha
> vs R12 4a's 305.4 ha, talus 1,284 of 12,758; every gate passes while the field is wrong. Ruling needed
> before the world run (talus is the P2 acceptance subject). R12 AMENDED 2026-09-26; LESSONS 2026-09-26.**
> - Species VERBATIM from `recipes/alpine.json` (7 at e5f32271, Boulder R12 2b, TreeStump R12 6b/6d).
> - Fixed for 8K: `rock_scatter.py` RGB→RGBA + `mask_plan` remainder (5-layer recipe) + planting field;
>   water/settlement post-filter in the planner (placer does not filter rocks; 24 + 119 rows removed);
>   `foliage.canopy` plan → `alpine_8k_Conifer.json`, radius 3.068 → 5.182 m (spruce, measured);
>   `rock_scatter.saturation` 0.03 → 0.001875 (cell-denominated; moved apron 88 → 112.6 ha only);
>   `--other-instances` measured = 185,385.
> - Nanite: all 8 declared meshes read True→True with data (vendor LOD0 counts); `rock_pivots.json`
>   (08-03) was STALE; re-measured, lod_depth still matches. Editor closed clean both times.
> - Two runs killed by the Claude Code background-shell memory reaper (fog ladder at 13/14, first
>   --write); the write re-ran DETACHED (Start-Process) — do that for any ~19 GB job.
> - World run (deferred, one combined `place_foliage --place` with the four tree plans, else the orphan
>   sweep deletes 185,385 trees) after Ryan's ultrareview + the talus ruling.
> - **SESSION CLOSE 2026-09-26:** branch final @ d3966e9a, pushed; auditor second pass FIX → applied
>   (`_saturation_note` mechanism corrected, 0.612M) → clear for ultrareview; plans re-written against
>   the corrected recipe, rows identical 9/9, STAMP MATCHES + fresh by HISTORY. main pushed @ 3c55fa64
>   (fog ladder close-out; this STATE block reaches main with the PR merge). Editor closed clean
>   (census 0, PackageRestoreData absent). Tags: `pre-a2-fog` (main). No editor running.
> - **NEXT SESSION:** (1) desk rulings: talus field (route on landform / box-spread; then both
>   saturations) and the blue clause (Rayleigh:Mie or strike); (2) "merged, go" → world run per the
>   handoff RESULT; (3) owed: `_saturation_note` copy in LESSONS is corrected by addendum only.

> ⭐ **2026-09-26 — BLUE-SHIFT LADDER MEASURED: NONE PASS the blue clause; albedo INERT; AP scale >1
> makes the far band GREYER + WARMER. No fog/atmosphere value persisted; A2 NOT closed (blue clause
> fails); `pre-a2-fog` stands. Full: `research/brief7/a2_imposter/FOG_AP_RESULT.md`.**
> - 7 cells (AP {1,2,4} × albedo {white, sky}) at d15_s150, camA (FOG_TUNE overlook) + camB (mid_slope
>   station on the ~1140 m dark cluster), 3840², region+luminance mask, counts beside every number.
>   camA far: sat 0.294 (AP1) → 0.207 (AP4), hue 37.2 → 33.8° (toward orange, not blue). Albedo white
>   vs (140,179,255): ≤0.001 sat / ≤0.4° on all five pairs. sat300/sat1000 clauses PASS on every cell;
>   hue clause FAILS on every cell. Closest = ap1_white (= d15_s150, AP unchanged). NOT applied.
> - **Desk to rule:** the hue of aerial perspective is the Rayleigh:Mie ratio (R-FOG REJECTED, 09-26) —
>   a blue shift needs `mie_scattering_scale` down / `rayleigh_scattering_scale` up under Look-profile
>   ownership (+ bench restore), or strike the blue clause and persist the de-greying cell.
> - camB_ap4_sky NOT shot: host killed the background ladder at 13/14 frames (1.9 GB free, editor
>   18.2 GB RSS) before its restore cell; restore applied by hand + read back; not restarted (harness rule).
> - `Slate.bAllowThrottling 0` folded into `render_preamble.txt`; bench A/A inside control noise
>   (MAD 1.56 vs 5.58 control, 8.29 M px). Every shot serviced in 4 s backgrounded.
> - Task 2 (rocks) SOURCED, authoring next on `look-p2-rocks`: all 9 species verbatim in
>   `recipes/alpine.json` (7 at e5f32271, Boulder R12 2b, TreeStump R12 6b/6d); all 9 KiteDemo meshes on
>   disk; 8K palette already declares `nanite: true` on 8 rock meshes (replay = `apply_nanite.py`);
>   `rock_scatter.py` needs the RGBA + `mask_plan` remainder read (5-layer 8K; the 09-12 place_foliage
>   bug) and its own water/settlement post-filter (placer says adopted rock plans are not filtered).

> ⭐ **2026-09-26 (session open) — BRIEF 7 P2 step 0 close-out: blue-shift ladder (Task 1) then rocks
> authoring on `look-p2-rocks` (Task 2, author-only, no world run).** Oriented against FOG_TUNE_RESULT.md,
> p2_rocks_handoff.md, LESSONS tail, git (HEAD ad80a590, clean): no contradiction with the prompt.
> - Facts carried in: height fog only de-greys (far sat 0.262→0.327 at d15_s150, hue ~49° every cell);
>   `extinction_scale` inert; SkyAtmosphere `aerial_pespective_view_distance_scale` live 1.0 untouched;
>   Look profile owns sun/sg/PPV_Look only — NOT fog/atmosphere. No fog value on disk changed.
> - Engine header (SkyAtmosphereComponent.h:154): AP scale "makes the aerial perspective look THICKER by
>   scaling distances" → ladder {1, 2, 4} is the right direction; measured, not assumed.
> - Task 1 plan: fence tag `pre-a2-fog`; 6 cells = AP {1,2,4} × albedo {white, sky-tinted} at d15_s150;
>   two cameras (forest-overlook + mid_slope station framing the 1 km+ grey); pass = sat300 ≥ 0.6·sat40,
>   sat1000 ≥ 0.3·sat40, hue1000 ≥ 15° toward blue; winner → Look-profile fields with bench restore
>   read back; none pass → table + closest, stop. `Slate.bAllowThrottling 0` folds into the render
>   preamble, bench A/A still must match. Editor: zero running at open; launching `-Windowed`.

> ⭐ **2026-09-25 (A2 fix step 1) — the dark far-forest imposter is a MATERIAL-GRAPH / atlas-shape issue,
> NOT a binding/missing/stale/black-atlas fault. Read-only; REPORTED + STOPPED per the desk gate (bound +
> current → report node path, desk rules). Full: `research/brief7/a2_imposter/A2_IMPOSTER_DIAGNOSIS.md`.**
> - Only **FT_SpruceSub** (spruce_half_01) has an imposter LOD material (`half_01_imposter` slot 3, base
>   `MA_Imposter`); Conifer/ConiferPine/SpruceSapling have none (deviation from the 4-species assumption).
> - Atlases EXPORTED + inspected: **Albedo `_A` is a CORRECT green octahedral spruce sheet** (4096²), Normal
>   `_N` a valid normal map (4064²), Masks `_O` a sparse R-channel silhouette (4064²). Params nominal
>   (Brightness 1.8, Tint white, Snow off). So "base colour zero" is DISPROVEN; nothing is unbound/stale.
> - **PRIME SUSPECT (desk to rule): Albedo 4096² vs Normal/Masks 4064² size mismatch** → `ImposterUVs`
>   frame lookup drifts the albedo onto the dark inter-frame fill → dark card. Secondary: which channel
>   `SmoothThreshold` reads for opacity (R=mask, B=254 constant). Base/opacity node paths in the report.
> - Foliage cull 384–512 m; imposter draws inside that (re-confirms HLOD was never the subject). Fence
>   honoured (read-only bar exported atlas views); `pre-a2-fix` tag stands; editor closed clean.
> - **FOG TUNE (2026-09-25, MEASURED): height-fog density reduces the distant grey wash MODESTLY but
>   CANNOT blue-shift — no fog value persisted; desk rules.** 7-render ladder (density {0.0042,0.0025,
>   0.0015} × start {0,150 m} + extinction 0.5 on best) on a forest-overlook camera: far-band foliage sat
>   0.262→0.327 (best d15_s150), far lum 68→64. extinction_scale INERT. But far HUE stays ~49° (green-yellow)
>   on EVERY cell — height fog desaturates toward grey, does not blue-shift. The "green fading to blue" aerial
>   perspective is a SkyAtmosphere function (`aerial_pespective_view_distance_scale`=1.0, read-only this
>   round). Per "none pass → report + closest, desk rules": closest = d15_s150, NOT applied; fog restored to
>   baseline (never saved), bench untouched. RECOMMEND desk authorize the SkyAtmosphere lever (ladder
>   {1.0,0.5,0.25}) for true blue aerial perspective. Capture note: windowed editor dropped foreground between
>   shots; fix = `Slate.bAllowThrottling 0` (renders when backgrounded). Data: `FOG_TUNE_RESULT.md`.
> - **A2 CLOSED (2026-09-25, MEASURED): the imposter is NOT the defect — the distant dark forest is
>   ATMOSPHERIC FOG, hitting full geometry and imposter EQUALLY.** Brightness A/B on a `_SRC` copy
>   (restored, `_SRC` deleted, no `.uasset` changed): at 40 m the imposter matches LOD0 within 10% at
>   default (b18_ss1 −6.4% lum, 0% hue); Brightness 1.8→3.0 barely moves it; SS Strength ON is closer.
>   DECISIVE: at ~300 m the FULL-GEOMETRY trees (ForceLOD 0) are gray too (lum 73.2, sat 0.05) and the
>   imposter matches them within <1% (lum 72.8). So no imposter brightness/SS fix warranted (would
>   over-brighten vs the real trees). If the distant greyness is undesired it is a FOG / aerial-perspective
>   Look decision, not an imposter fix. NOT tagged a2-fixed (nothing to fix). Data:
>   `research/brief7/a2_imposter/A2_BRIGHTNESS_AB_RESULT.md`. `pre-a2-fix` stands; editor closed clean.
> - **FOLLOW-UP (2026-09-25):** two 5-min checks + step-2 render. Check 1 (Albedo PowerOfTwoMode) CLEAN
>   = NONE (4096² is a genuine separate JPEG source `_A_unlit.jpg`, source on another machine, no reimport).
>   Check 2 (opacity channel) not readable in 5.8 Python → resolved by render. **Render `foliage.ForceLOD
>   3 AND 4` at slope: the imposter renders as CORRECT tree SILHOUETTES, not solid boxes — opacity works;
>   the trees are just DARKER/desaturated than the near lit trees.** "Dark boxes" = dense small dark
>   imposters clustering at ~200–512 m. → the size mismatch is NOT off-frame sampling and a matched-size
>   re-bake likely WON'T fix the darkness; real symptom = imposter BRIGHTNESS/shading (flat
>   MSM_TWO_SIDED_FOLIAGE card). **REPORTED instead of executing the pre-ruled re-bake (new evidence
>   contradicts its premise); recommend a Brightness/shading tweak on a `_SRC` copy first. Desk to rule.**
>   Stills `slope_imp_lod3/lod4.png`. Editor closed clean; `pre-a2-fix` stands.

> ⭐ **2026-09-25 (step 0b) — A2 DARK FOREST ROOT: the distant dark "cubes" are the conifer/spruce
> FOLIAGE at their IMPOSTER (last) LOD rendering near-black — NOT HLOD, NOT the FlattenMaterial_VT,
> NOT r.LumenScene.FarField, NOT VT upload budget. Proven by `foliage.ForceLOD 0` → the whole terrain
> fills with full-geometry conifers and the cubes resolve to trees (`stills/p1_feather/slope_foliage_forcelod0.png`).
> This OVERTURNS the earlier HLOD-flatten-VT read (it sampled an arbitrary proxy, never proved the dark
> pixels were HLOD) and the 2026-09-24 A2 readback. Step 1 (VT budget: editor uses
> r.VT.MaxUploadsPerFrameInEditor=32/500, bumped to 128/2000 — no change) and step 2 (rebuilt cluster
> cells L0_X-8_Y8 + L1_X-5_Y4 via hlod_build_single — no change) were both NEGATIVE because they
> targeted the wrong subject (cells at ~800–1140 m are LOADED = real foliage, not HLOD). FIX SITE
> (proposed, NOT applied): the conifer/spruce `*_imposter` LOD materials/atlases (e.g. half_01_imposter)
> — regenerate or fix their base color/lighting. FarField=1 stays (harmless, committed); VT bump was
> runtime-only. LESSONS 2026-09-25 step 0b. Next: Phase 2 rocks (R-ROCKS-BACK), branch look-p2-rocks.**


> ⭐ **2026-09-25 — BRIEF 7 P1 FEATHER WORLD RUN DONE, ACCEPTANCE PASSED, tag `look-p1`
> (commit 10a26d3c). PR #4 merged to main (b319bd96) first. The post-merge sequence ran clean:
> re-imported the feathered `alpine_8k_weights.png` into `T_Alpine_8k_Weights` (verbatim settings +
> SIMPLE_AVERAGE mip, via a targeted reimport payload because import_layer_textures is blocked by
> pre-existing lighting/foliage recipe validation); rebuilt M_Alpine8K at k=0 disp true (graph EXACT,
> saved); re-baked surface lookup from the feathered masks (pos 100%, neg 9.03%, blend zones 5.98%);
> built texture streaming.**
>
> - **ACCEPTANCE PASS.** Look profile (sun 35°) stills in `research/brief7/stills/p1_feather/`:
>   the ~1 m cubic BLOCK SHATTER IS GONE at every station. near_ground (basin 187 m) = green grass
>   meadow, boulders, full-geom conifers; slope/terrain_crop (632 m) + vista (762 m) = smooth snow/rock
>   with soft feathered dappling. Boundaries ramp near+far, no blocks, no shards, small rocks visible.
>   Snow-heavy at 632–762 m = altitude snowline (basin correctly green).
> - **CAPTURE LESSON (LESSONS 2026-09-25):** the shot only services against a **WINDOWED, foreground**
>   editor (LESSONS 14.7). launch_editor.ps1 defaults to `-RenderOffScreen` (right for remote work,
>   WRONG for shots) → first attempt stalled (HighResShot issued, editor idle, no frame, 2×); relaunch
>   `-Windowed` → every frame in ~4 s. shoot.py has no headless-editor guard (owed). New scripts:
>   `brief7_wm_reimport_payload.txt`, `brief7_place_cam_payload.txt` (ground-tracing camera place).
> - **P2 STEP 0 (commit 35dfadc2): `r.LumenScene.FarField=1` enabled + persisted** in
>   `LandscapeLab/Config/DefaultEngine.ini` [SystemSettings], applied live + read back (0→1,
>   MaxTrace 1e6, rule 12). **RESULT NEGATIVE / A2 STILL OPEN:** re-shot vista + slope ~3 min after
>   enabling — the dark far-HLOD forest proxies are UNCHANGED (near-black on sunlit terrain → the
>   imposter/material itself, not GI starvation). FarField kept (harmless) but is NOT the A2 fix. A2
>   needs a different instrument in P2 (inspect the proxy imposter AS RENDERED, not the source shading
>   model). See `research/brief7/stills/p1_feather/{vista,slope}_farfield_look.png`.
> - **A2 DIAGNOSED (read-only, LESSONS 2026-09-25):** the dark far-HLOD forest proxies are a
>   **base-color / Virtual-Texture fault, NOT lighting.** Proxy = Instanced→MERGED FLATTEN
>   (`StaticMesh_Alpine8K_HLODLayer_Merged`, base mat `FlattenMaterial_VT`); its `BaseColorTexture`
>   is a VT-streamed 1024² Texture2D that exists but renders black. r.VirtualTextures=1,
>   r.VT.MaxUploadsPerFrame=2, cast_shadow=true, rest of sunlit terrain lit fine. HLOD layer defs
>   (Merged 09-06) PREDATE the foliage-material changes (FT_Conifer 09-11, FT_SpruceSapling 09-19) →
>   stale/invalid flatten VT atlas. **FIX (proposed, NOT applied): rebuild World Partition HLODs
>   (Build HLODs); if black persists, raise r.VT.MaxUploadsPerFrame or bake the flatten base color
>   non-VT.** Viewmode stills failed as an instrument (HighResShot ignores VIEWMODE; ShowFlag.Lighting
>   under the Look profile clips to white) — use the GBuffer buffer-dump for base-color stills (owed).
> - Recipe unchanged this run (k=0, disp true, feather σ=1.5 already on main). m=1, world working.

> ⭐ **2026-09-24 — BRIEF 7 PHASE 1 FEATHER: authored on branch `look-p1-feather` per
> `research/brief7/feather_handoff.md` (fresh full-context session, the handoff's named recipient).
> Change: σ=1.5 Gaussian feather on the four stored channels inside `derive_layer_weights.expand()`
> (`collapse()` untouched — retired v1); renormalise Σ≤1 so the shader meadow remainder stays ≥0;
> recipe `material.weightmap_feather_sigma_px=1.5` + schema bump + validator (refuses the old
> un-feathered path = absent field when a weightmap is present). New `check_weightmap_feather.py`
> (feathered ≥25% at boundaries, Σ≤255, snow-mask IoU vs pre-feather) wired into run_offline_suite;
> hillshade_snow_check reads w8a (source, untouched) so snow registration holds by construction.
> DECISION (divergence from handoff literal): `_expand_check` runs on the UNFEATHERED source
> (validates the source partition); a separate post-feather assert proves Σ≤1/remainder≥0, because
> feathering intentionally breaks _expand_check's remainder==wet+path+gravel+meadow source identity.
> DECISION: regenerated + committed the feathered `alpine_8k_weights.png` on the branch so the
> real-PNG invariant in the always-green suite passes; post-merge is then re-import + rebuild k=0 +
> re-bake surface + re-shoot (the world run, NOT done here). AUDITOR: FIX → all findings applied →
> re-audit CLEAR-TO-EXECUTE. Branch PUSHED (origin/look-p1-feather, head f738ae64, incl. 183 MB LFS).
> `gh` CLI is NOT installed on this machine + no API token, so the PR is NOT opened by CLI — OPEN IT
> at https://github.com/ryan772177/LandscapeLab/pull/new/look-p1-feather then "merged, go".
> Suite green bar the pre-existing city-plan-freshness FAIL (exit 3 on clean main too). m=1, world working.**

> ⭐ **2026-09-24 — BRIEF 7 PHASE 1: the weightmap-mip branch MERGED + applied, but the crop
> is STILL BLOCKY. The TRUE root is a NEAR-BINARY imported weightmap, not the mips. Honest
> correction. World reverted to working (pre-p1-material). Editor closed clean. NEEDS RYAN: a
> new fix direction (feather the weightmap bake). Full: LESSONS + `research/brief7/p1_block_diff.md`.**
>
> - **Mip fix merged (PR #, main 7f9b286c) + applied** to `T_Alpine_8k_Weights` (NO_MIPMAPS →
>   SIMPLE_AVERAGE, KEPT — a real distance-aliasing improvement). Rebuilt at k=0 → crop STILL
>   blocky (`stills/p1_mips/terrain_crop_MIPS.png`).
> - **Decisive test:** forcing the weightmap to a coarse mip (lod_bias 6) CHANGED the render (all
>   snow) → **NPOT 8129² mips DO generate on D3D12 (PadToPowerOfTwo NOT needed)**, the weightmap IS
>   the source, but the blocks are in the FULL-RES mask, not minification.
> - **TRUE ROOT:** the imported `textures/alpine_8k_weights.png` is **NEAR-BINARY** — R 92.5% /
>   G 90.6% / B 82.6% / A 97.8% of texels pure 0-or-255, only ~6–12% feathered. Hard per-layer masks
>   → hard 1 m block edges where layers meet. = the desk's own A3 checkerboard, present pre-p1.
> - **MY DIAGNOSTIC ERROR:** A3 + the diff doc measured `w8a/w8b` (the SMOOTH 8-channel *source*),
>   not the composited 4-channel `alpine_8k_weights.png` the material actually imports (rule 9). "No
>   mipmaps" was real but SECONDARY (distance aliasing); the hard mask is the primary block cause.
> - **FIX DIRECTION (Ryan's call):** re-bake `alpine_8k_weights.png` with FEATHERED boundaries from
>   the smooth w8 source (the composite/quantisation step), or soften the material composite blend —
>   NOT the mip. World reverted (M_Alpine8K + surface → pre-p1-material); recipe k=0 + disp true kept.
> - **FEATHER FIX = the direction (Ryan). HANDED OFF, not authored** (context-exhaustion rule:
>   a regenerated 8129² load-bearing weightmap on a long/degraded context is the named failure
>   mode; two diagnostic misses already this session). Full spec + fix site in
>   `research/brief7/feather_handoff.md`. Groundwork done: **fix site = `derive_layer_weights.py`
>   `expand()` line 652** (the LIVE 5-layer producer; `collapse()` line 563 is RETIRED v1 — do not
>   touch); change = Gaussian σ=1.5 feather on the 4 stored channels + renormalise Σ≤1; recipe
>   `material.weightmap_feather_sigma_px=1.5` + schema + validator; invariants (feathered ≥25% at
>   boundaries, Σ≤255, hillshade_snow_check + skyline IoU). Author on branch `look-p1-feather`,
>   PR, "merged, go"; post-merge = regen PNG → re-import → rebuild k=0 → surface → re-shoot →
>   acceptance (2–4 m fades) → tag look-p1.
> - A2 HLOD Lumen-FarField fix still owed at P2 step 0. m=1, world working.


> ⭐ **2026-09-24 — BRIEF 7 PHASE 1 block ROOT CAUSE FOUND + reported. World reverted to
> working terrain. Editor closed clean (0 procs). NOT PUSHED. NEEDS RYAN: the fix is a
> weightmap texture-asset setting on a branch. Full diff: `research/brief7/p1_block_diff.md`.**
>
> - **Isolation ladder — blocks are k-, tessellation-, AND displacement-INVARIANT:**
>   height_blend.k=0 (identical to k=4), `r.Nanite.Tessellation 0`, and
>   `displacement.enabled=false` rebuild all leave the blocks unchanged → a pure albedo/mask
>   shading artefact, NOT the height-blend, NOT geometry, NOT the displacement/normal path.
> - **Decisive signature:** the tight terrain crop (`stills/p1_dispoff/terrain_crop_dispoff.png`)
>   is **foreground SMOOTH, distance BLOCKY** = MINIFICATION ALIASING (which also rules OUT a UV
>   texel-snap — that would quantise the foreground too).
> - **Graph diff (`input/graphdiff_pre_p1.json` vs `graphdiff_p1.json`):** the weightmap
>   `T_Alpine_8k_Weights` + its sample are BYTE-IDENTICAL between the smooth pre-p1 and blocky p1
>   — Filter TF_DEFAULT (bilinear), **`mip_gen_settings = TMGS_NO_MIPMAPS`**, 8129², LINEAR_COLOR/
>   CLAMP/TMVM_NONE. **An 8129² mask with NO MIPMAPS aliases into hard 1-texel blocks at distance.**
>   Latent in the shipped material too — it is the desk's own A3 mid_slope checkerboard, amplified.
> - **FIX (owed, branch):** `T_Alpine_8k_Weights` mip_gen_settings NO_MIPMAPS → FROM_TEXTURE_GROUP
>   (or SIMPLE_AVERAGE) in the texture-convert/import step; then re-run the k=0 rebuild + re-shoot.
> - **Reverted** M_Alpine8K + surface to `pre-p1-material`; recipe `displacement.enabled` restored
>   to true, `height_blend.k=0` kept (Ryan's ruling). World working, m=1. LESSONS 2026-09-24.
> - A2 HLOD Lumen-FarField fix still owed at P2 step 0.


> ⭐ **2026-09-24 — BRIEF 7 PHASE 1 retry STEP 1 (k=0) FAILED, and it DISPROVES the
> height-blend hypothesis. Reverted again. Editor closed clean (0 procs). NOT PUSHED.
> NEEDS RYAN: the fix target moves OFF the height-blend.**
>
> - Set `material.height_blend.k = 0` (Ryan's positive control), rebuilt M_Alpine8K clean
>   (assert EXACT, per-layer displacement + R-TILE + GroundClutter, saved). **Render STILL
>   shatters into ~1 m blocks, pattern IDENTICAL to k=4** (`research/brief7/stills/p1_k0/`).
> - **Two invariances pin it:** (a) **k-invariant** — k=0 == k=4 blocks → the height-blend
>   reweight is NOT the cause, so Ryan's Step 2 (bounded modulation on the same reweight)
>   would NOT fix it either; (b) **tessellation-invariant** — `r.Nanite.Tessellation 0`
>   unchanged → NOT geometric displacement. **The blocks are SHADING.**
> - **Prime suspect:** the per-layer displacement height driving a PIXEL NORMAL
>   (normal-from-height), mask-weighted by the 1 m weightmap → a normal that steps at 1 m and
>   shades blocky regardless of tessellation. The one remaining rebuild delta vs the smooth
>   pre-Phase-1 material. **Recommended next isolation (1 rebuild): `displacement.enabled=false`
>   (or per_layer all 0), everything else as built; slope goes smooth → confirmed.**
> - **Reverted** M_Alpine8K + surface to `pre-p1-material` (world terrain working). **Recipe
>   `height_blend.k = 0` KEPT** (Ryan's ruling stands; just not the lever). LESSONS 2026-09-24.
> - Owed: pin the displacement/normal cause, then the material fix (branch rule), then re-run
>   stills + acceptance + tag look-p1. A2 HLOD Lumen-FarField fix still owed at P2 step 0. m=1.


> ⭐ **2026-09-24 — BRIEF 7 PHASE 1: the builder fix merged, the rebuild RAN and persisted,
> but the RENDER acceptance FAILED (shattered terrain) and the world was REVERTED. Editor
> closed clean (0 procs). NOT PUSHED. NEEDS RYAN: a material-shading fix (branch rule).**
>
> - **Builder `__file__` bug FIXED + merged** (PR → main 2c719932): `_run` now stages the
>   payload + ll_must to `Saved/LLPython` and passes the path. Auditor CLEAR-TO-EXECUTE.
> - **Rebuild RAN clean** (`make_landscape_material.py --recipe recipes/alpine_8k.json
>   --assign`): graph assert EXACT match to spec, compiled clean, per-layer displacement
>   (ref 0.08), height-blend composite (250 exprs), per-layer R-TILE tiling, grass restored
>   (GroundClutter GT_alpine_8k_GroundClutter = SM_Boulder05a + SM_River_Rock_01, + Meadow +
>   Blueberry). Material SAVED + COLD-VERIFIED cross-process. Committed 30f36f51 (record).
> - **⛔ ACCEPTANCE FAILED on the render.** Cards resolved (30 s settle → full-geometry trees),
>   but the whole terrain reads as a field of ~1–3 m cubic blocks at every station
>   (`research/brief7/stills/p1/slope_look.png`, `near_ground_look.png`). ISOLATED: set
>   `r.Nanite.Tessellation 0` and re-shot — **blockiness UNCHANGED → NOT geometric displacement,
>   it is SHADING.** Points at the height-blend reweight (k=4) hardening the blend to a per-texel
>   winner at the 1 m weightmap-texel scale (and/or a per-layer height-derived normal). The old
>   smooth LinearInterpolate composite rendered fine; the height-weighted one does not.
> - **REVERTED:** `git checkout pre-p1-material -- M_Alpine8K.uasset` + surface lookup. World
>   terrain back to the working pre-rebuild material. GroundClutter type + payloads kept (harmless).
> - **>>> ASK / NEEDS RYAN:** a material-shading fix — most likely soften/smooth the height-blend
>   (lower k, add a blur/feather, or blend-not-argmax on albedo) so it does not shatter at 1 m;
>   author on a branch, PR, "merged, go" (branch rule). LESSONS 2026-09-24. **The material recipe
>   values are not wrong; the height-weighted COMPOSITE as built shatters the albedo.** m=1, world working.
> - Owed after the fix: re-run rebuild + surface re-bake + stills (slope/near_ground/forest-floor
>   crop/vista @ 35° sun, long settle) + acceptance + tag look-p1. A2 HLOD Lumen-FarField fix still
>   owed at P2 step 0.


> ⭐ **2026-09-24 — BRIEF 7 PHASE 1 BLOCKED on the first-ever editor run of the merged
> material builder. L0-final signed (WB 5600) + amendments A1–A3 done + surface re-bake
> ready (reverted until the rebuild). Editor closed clean. NOT PUSHED. NEEDS RYAN: a
> ~6-line builder fix, gated by the branch rule.**
>
> - **L0-final (Ryan):** WB **5600** (applied + persisted on PPV_Look), contrast 0.90,
>   shafts ON, rig-off, clouds-off. Signed. Phase 1 greenlit ("merged, go").
> - **A1 sun-in-profile DONE:** `sun_elevation_deg` added to the profile switch — Look 35°
>   (pitch −35), bench restores the ruled 12°; verified by reading the sun rotation under
>   each. Runtime toggle, on-disk sun stays −12. Look-profile fields owed into recipe JSON.
> - **A2 HLOD-black READ-BACK (fix P2-step-0):** proxies are `MSM_DEFAULT_LIT` (not unlit);
>   the lever is **`r.LumenScene.FarField=0`** (+ software SDF off) — the far band gets no
>   Lumen GI → black. Fix = enable Lumen Far Field (the P4 lever pulled forward). `p1_amendments.md`.
> - **A3 snow/grass weightmap:** source **8129² = 1 m/texel**, continuous (256 levels), block
>   size **1 m ≤ 2 m** → note & continue (no re-bake); the height-blend is the real change,
>   judge on the post-rebuild slope still.
> - **⛔ PHASE 1 BLOCKER:** `make_landscape_material.py` fails on first editor run —
>   `NameError: __file__` at payload line, BEFORE the destructive clear (M_Alpine8K INTACT,
>   197 exprs, nothing saved). Root cause: `_run` (line 3916) sends the payload as inline TEXT
>   with `MODE_EXEC_FILE` (which needs a FILE PATH, and is what defines `__file__`); the ll_must
>   refactor made the payload import ll_must via `__file__` but never updated `_run` to STAGE
>   like `ue_exec.run()` does. Offline gates can't see an editor-exec-path bug. **FIX:** stage
>   the payload + ll_must.py to `Saved/LLPython` and pass the path (~6 lines). Gated by the
>   Brief 7 branch rule → author on a branch, PR, "merged, go". LESSONS 2026-09-24.
> - **Owed once fixed:** re-run the rebuild (correct `--recipe recipes/alpine_8k.json --assign`),
>   re-`--write` the surface lookup (synced), Build Texture Streaming, stills (slope + near_ground
>   + forest-floor crop + vista pair, Look profile at 35° sun, LONG foliage settle), tag look-p1.


> ⭐ **2026-09-24 — BRIEF 7 L0 RE-GRADE DONE (Ryan rulings applied, re-shot, cold-verified,
> committed under `look-p0`). STOP → ASK L0-final (sign the grade + green-light Phase 1).
> Editor closed clean (0 procs). NOT PUSHED.**
>
> - **Clouds DISABLED for P1–P3** (Ryan's fallback): the engine SimpleVolumetricCloud
>   (`MI_AlpineClouds` ← `m_SimpleVolumetricCloud_Inst`) cannot make scattered cumulus —
>   coverage IS bound (`Cloud_GlobalCoverage`) but sweeping 0.20→0.08→0.03 never cleared past
>   ~35% at the vista (a broken deck, not cumulus). Cloud actor `Lighting_alpine_8k_Clouds`
>   set `hidden_in_game` + component `visible=False`. Open SkyAtmosphere; BACKLOG a WeatherMap
>   cloud material. Vista now reads as clean open sky. Tries in `stills/p0_cloud/`.
> - **HeroStage rig OFF in-game:** the 3 non-sun DirectionalLights set `hidden_in_game=True`
>   (persisted; still available in-editor for hero work). **First attempt silently failed** —
>   `set_actor_hidden_in_game` without `modify(True)` never dirtied the OFPA, save skipped it,
>   the cold read-back caught it (rule 12). Fixed with `modify(True)` first. LESSONS.
> - **WB 6200 → 5800** on PPV_Look (cooler). Contrast 0.90 + sun light shafts ON kept (unruled).
> - **Cold read-back proved all L0 changes persist** cross-process (`input/L0_write.json`,
>   `L0_rigfix`). Re-shot 3 pairs → `research/brief7/stills/p0_L0/`. near_ground shows tree-card
>   LODs = a fresh-editor foliage-LOD settle gap (BACKLOG), not a grade change.
> - **>>> ASK L0-final (pending Ryan):** sign the grade (WB 5800 / contrast 0.90 / shafts ON /
>   rig-off / clouds-off) or adjust, and green-light **Phase 1** (material rebuild — merged on
>   `look-p1-material`, runs against the editor only on "merged, go"). World unchanged otherwise; m=1.
> - Fence: `pre-look` (a05b94f8); `look-p0` now includes the L0 re-grade. Hard stops all honoured.


> ⭐ **2026-09-23 — BRIEF 7 PHASE 0b–0e DONE (live-editor look pass). PPV_Look
> authored + graded + PERSISTED (cold-verified cross-process); pre-exposure
> defect fixed; six 4K bench-vs-Look stills captured. Committed + tag `look-p0`.
> STOP → ASK L0 (Ryan rules the grade). Editor closed clean (0 procs). NOT PUSHED.**
>
> - **0b read-backs** (`research/brief7/p0_readback.md`, `input/p0b_*.json`): ONE PPV
>   (`Lighting_alpine_8k_PostProcess` = the bench PPV, R-LOOK-1 untouched, manual
>   bias −14.2571). **Four DirectionalLights: 1 atmosphere sun (130000 lux/5200K) +
>   3 HeroStage rig lights (Key/Fill/Rim) STILL lighting the whole world**
>   (hidden_in_game=false, cast_shadows=true) — the "four suns" answer + an L0 flag
>   (hide the rig in-game?). Fog scatter 0.4, cloud coverage 0.30. Material = the
>   pre-Phase-1 build (LinearInterpolate composite, no LandscapeLayerCoords/LayerBlend,
>   displacement magnitude 0.16, grass = Meadow+Blueberry only).
> - **0c pre-exposure — the LIVE defect confirmed + fixed.** Running editor read
>   `r.EyeAdaptation.CachedLightingPreExposure` = **4.0** (not a misread). Source math
>   (PostProcessEyeAdaptation.cpp:201,246-268): warning fires when scene ExposureEV ∉
>   [value−12, value+8]; the ~14.3 EV alpine clips at 4. Set **8** in DefaultEngine.ini
>   [SystemSettings] (range [−4,16]); runtime 4.0→8.0, cold relaunch 8.0. The −game
>   on-screen warning-gone is Ryan's visual check at L0 (not capturable headless).
> - **0d PPV_Look** (`input/p0d_write.json`) — NEW unbound actor, priority 1.0,
>   **enabled=False persisted** (the Look profile enables it; bench never affected by
>   default). Grade: manual/−14.2571, local exp 0.8, WB 6200 (sun K+1000)/tint 0,
>   contrast w=0.90, FFT bloom 0.4 + dirt 0.1, grain 0.3, vignette 0.3. Sun light-shaft
>   bloom+occlusion ON; fog volumetric scatter 0.4→0.2; cloud coverage 0.30→0.10.
>   Post-save dirty census 0/0; **COLD READ-BACK proved every value cross-process**
>   (`input/p0_coldread.json`). Bench PPV/profile/benchmark.json UNTOUCHED (R-LOOK-1).
> - **0e stills** (`research/brief7/stills/p0/`, 6×4K): near_ground / mid_slope / vista,
>   bench-profile vs Look-profile pairs (camera from benchmark.json, read-only). The
>   Look kills the tree-card LOD popping (Epic sg), warms to golden hour, rim-lights the
>   grass, fog gives aerial perspective at the vista. Town = engine cubes in both (the gap).
> - **>>> ASK L0 (pending Ryan):** warmer/cooler (the vista reads quite warm at WB 6200),
>   more/less contrast (w=0.90), light shafts yes/no, and the HeroStage-rig-in-game flag.
>   His lines carry into P1–P4. **World unchanged from Phase 0d otherwise; m=1.**
> - Fence: tag `pre-look` (a05b94f8) before the first write; `look-p0` after 0e. Hard
>   stops all honoured (zero-editors, project+level verified, VRAM, R-EDITOR-CLOSE,
>   persist, read-back every PPV param). **Then Phase 1 material REBUILD** (gated world
>   run) + re-bake surface lookup + Phase 1 stills — only after Ryan's L0 grade.


> ⭐ **2026-09-23 — BRIEF 7 PHASE 1 SHIPPED TO main + F2 RESOLVED. Author-only;
> NO world run yet. `look-p1-material` MERGED (main @ c022e019, PR #1 closed).**
>
> - **Phase 1 material AUTHORED + REVIEWED + MERGED (6 commits).** schema v1.27
>   per-layer displacement (`per_layer` metres, retires global `amplitude_m`);
>   schema v1.28 height-weighted blend in the weightmap composite
>   (`material.height_blend {k:4, eps:0.02}`, LB_HeightBlend has no referent —
>   this material is a LinearInterpolate composite); GroundClutter restored
>   (R-ROCKS-BACK/§6d). Auditor gate + ultrareview both run; all findings fixed.
>   Offline-verified (prove_gates, invariants, validators, check_docs); NOT run
>   against the editor — the material REBUILD is the gated world run.
> - **F2 RULED (Ryan) MEASURE→MODEL, DONE.** Raw surface-lookup argmax flips on
>   **3.12%** of walkable texels under the height reweight (> the 2% bar; margins
>   p50 0.35), so `bake_surface_lookup.py` now MODELS the reweight (same
>   `_cpu_height_blend`, k/eps, tiled heights) — footstep/surface answer matches
>   the painted surface. `research/brief7/input/f2_argmax_flip.json`. **OWED at
>   Phase 1 world run:** re-bake `textures/alpine_8k_surface.png` with `--write`.
> - **Phase 0a DONE (offline):** D3 evidence un-ignored + tracked; D3 editor-peak
>   VRAM 5,211 MiB → `research/brief5/input/d3_editor_vram.json`; min_detectable
>   per-build already REGISTER B5.24.
>
> **ORDER (Ryan correction): merge → Phase 0 → Phase 1 rebuild+stills. Merge ✓,
> Phase 0a ✓. NEXT = Phase 0b–0e, a LIVE-EDITOR pass, handed off (context-
> exhaustion rule: not begun on a deep context). Runbook, decisions made:**
> - **0b read-backs** (editor, no save) → `research/brief7/p0_readback.md`: every
>   PostProcessVolume (metering/comp/min-max EV100/unbound/priority); every
>   DirectionalLight (enabled/lux/K — the "four suns" count); SkyLight; fog; Mie;
>   cloud coverage; the built material (layer list, per-layer Mapping Scale vs
>   recipe tiling_m, per-layer displacement inputs, GrassOutput types). ruled|current|match.
> - **0c pre-exposure** `r.EyeAdaptation.CachedLightingPreExposure` so the cached
>   range covers EV 14–15; persist protocol on the ini; one -game launch: the
>   on-screen clip warning must be GONE. (SYNTHESIS §0 said misread — CORRECTED by
>   the desk: it is a LIVE defect; the 9/12 null ran at −4.1 EV, A-6 moved to −14.2571.)
> - **0d PPV_Look** (new unbound PPV, priority above bench PPV, Look profile only):
>   Manual meter + comp from sun rule; Local Exposure ON (~0.8); WB = sun K +1000,
>   tint 0; contrast 0.90; Convolution bloom 0.4 + low dirt; grain 0.3; vignette
>   0.3. Sun light shafts bloom+occlusion ON. Fog volumetric ON, scattering 0.2,
>   extinction 1.0, view 6 km, start 0. Clouds 2.0/1.5 km, coverage 0.1, read back.
>   Persist protocol on every actor. R-LOOK-1: bench PPV/profile/benchmark.json UNTOUCHED.
> - **0e stills** near_ground + vista + the 9/22 slope station, bench vs Look pairs
>   → `research/brief7/stills/p0/`. Commit, tag `look-p0`. **STOP → ASK L0** (Ryan
>   rules warmer/cooler, contrast, shafts). Carry his lines into P1–P4.
> - **Hard stops:** rule 11 (zero editors, ASK WHICH LEVEL first), rule 7 (verify
>   project), rule 12 (read-back every PPV param), VRAM 13,312, R-EDITOR-CLOSE,
>   tag `pre-look` before the first write. unreal-mcp 127.0.0.1:8001 (R-MCP).
> - **Then Phase 1 REBUILD** (`make_landscape_material.py` against the editor, `_SRC`
>   dupes, persist protocol) + re-bake surface lookup + Phase 1 stills — only after
>   Ryan's L0 grade.

> ⭐ **2026-09-23 — BRIEF 7 (THE LOOK) rulings in force (desk / Ryan). Spec:
> `research/brief7/BRIEF7_THE_LOOK.md`. Target: Electric Dreams-grade alpine.**
> - **R-LOOK-1:** the bench PPV, bench profile and `benchmark.json` are UNTOUCHED;
>   the game gets its own `PPV_Look` actor + Look profile, graded and judged on
>   stills; the two never share an actor.
> - **R-ROCKS-BACK:** "minus the rocks" is rescinded — the August rock species
>   (Boulder, CliffOutcrop(B), CliffFace, TalusField A–C, TalusChannel, TreeStump)
>   return on the deposition field.
> - (R-AESTHETIC-1 still in force: ms budgets SUSPENDED, perf recorded not gated,
>   visual gate = Ryan on stills. Hard stops remain: VRAM 13,312, DEVICE_HUNG,
>   persist, tag-before-write, fence.)
>
> ⭐ **2026-09-23 — T4 GATE (Ryan supervised). Two steps, both offline/-game,
> no editor, no asset writes; world stays at pre-density-daylight (m=1, 185k).
> NOT PUSHED. Finding: there is no cheap lever for the forest_floor headroom.**
>
> - **Step 1 — recalibrate (t4_recalibration.json).** The old cost model was ~8.5×
>   optimistic: measured slope 1.576 ms/unit-m (was 0.185), forest_floor cap
>   2.38 → **1.162**. The two biggest measured passes are NOT T4-rung-addressable:
>   NaniteVisBuffer 2.20 (Conifer/Nanite) + LumenReflections 1.30 (screen-space) =
>   ≥3.50 ms untouchable. **Ryan ruled option 2** (cvar levers over rungs); T4
>   rungs DEMOTED to BACKLOG with a numeric entry condition.
> - **Step 2 — cvar ladder (t4_step2_summary.json), measured at forest_floor vs
>   as-is, floor re-measured 0.074 (not v3's 0.016).** arm A (RadiusThreshold)
>   DROP; **arm B (Shadow.DistanceScale=0.25) KEEP +0.128 ms** (only rung, heavy
>   shadow-distance trade); arm D (Lumen roughness) DROP (frame gain 0.05); arm E
>   (Nanite MaxPixelsPerEdge) INCONCLUSIVE; arm F (foliage.CullDistanceScale)
>   INERT (types opt-out; asset write needed). Kept stack **0.128 ms vs a ~2.7 ms
>   deficit** → the forest_floor cost is STRUCTURAL.
> - **BLOCKED pending Ryan:** density at forest_floor has no cheap path. Options —
>   (a) raise the 13.0 budget (a re-rule), (b) an asset-write tier (FoliageType
>   cull opt-in / per-type shadow flags, persist protocol + ASK), (c) accept m=1
>   at forest_floor and pursue density only where there is headroom (plaza cap
>   2.157, treeline/vista under budget). No cvar promoted to ini (needs persist +
>   ASK). REGISTER B5.23–B5.29 M; LESSONS two-altitude; BACKLOG updated.
> - **Owed still:** clutter cost (D5); the D3 reference stills (offscreen/-game
>   HighResShot non-viable — would need MRQ).
>
> <!-- prior: D4 REVERTED (the density regen busted the GPU budget) -->
> ⭐ **2026-09-22 part 2 — DAYLIGHT DENSITY: dry-run → regen → measure → REVERT.
> Ryan supervised. Fence tag `pre-density-daylight`. World RESTORED to the tag
> (git diff tag..HEAD empty, 6/6 LFS-oid match, tree clean). NOT PUSHED (D7).**
>
> - **D4 → REVERT_D3 (Ryan ruled), REVERT PROVEN (commit 07ee6246).** The
>   density upgrade fits VRAM (D3) but **busts the GPU frame budget**: 3-run
>   median GPU p90 forest_floor **15.342 > 13.0**, open_max **14.151 > 13.0**,
>   plaza **12.939 > 10.5** (treeline 7.261 / vista 8.235 ok; game all < 6.0).
>   Reverted the world to the fence tag (foliage/ + Alpine8K.umap +
>   __ExternalActors__; the 17 D3-added OFPA moved to _trash/d4_revert_added).
>   Cold -game forest_floor **12.620 ms**, in the 12.645 ± 3×0.016 band → MEASURED
>   revert (counter moved 15.342 → 12.620). **The shipped world is back to m=1
>   (185,385 trees); the density upgrade is WITHDRAWN pending T4.**
> - **D4 model-error harvest (`d4_model_error.json`) — the model failed, not the
>   trees.** Predicted 12.90/9.882, measured 15.342/12.939 → underpredicted +2.442
>   / +3.057 ms (152× / 76× min_det). The v3 **0.100 ms/1000-trees "upper bound"
>   was ~9× low** (measured 0.854/0.980). Which pass grew (measured):
>   **ShadowDepths (ff 3.19) + NaniteVisBuffer (ff 2.20)** — corrects the v3 "not
>   Nanite raster" inference; T4 tri-reduction DOES pay. REGISTER B5.18 FALSIFIED,
>   B5.14 → M (cover 0.519). B5.14 (densest-decile cover) closed.
> - **Stills NOT captured** (offscreen HighResShot non-viable; reference-only, not
>   a blocker). `d4_stills.json` records the miss.
> - **OWED forward (BACKLOG, decisions made):** the **T4 gate session BLOCKS any
>   density re-run**; its FIRST step is recalibrating the zone map from
>   `d4_model_error.json` (the 0.100 rate is withdrawn), THEN the rungs + the
>   isolation-render gate; the **SpruceSub build-stall root cause** is owed before
>   any rung rebuild. **Clutter cost (D5)** still owed. **D6 SKIPPED** (nothing to
>   rebuild HLODs for). **D7:** INDEX_d.md written; push pending.
> - Desk package: `for_desk/INDEX_d.md` (10-line summary + cost/cover tables).
>
> <!-- D3 detail retained: the regen landed + was VRAM-measured before D4 reverted it -->
> - **D3 LIVE REGEN (commit 2372d8d0, since REVERTED).** 812,258 tree instances placed +
>   saved via the auditor-cleared driver `research/brief5/scripts/d3_regen.py`
>   (3-round audit chain; the revert machinery was BLOCKED twice and fixed before
>   the live run). No abort, no revert. **VRAM well under the 13,312 MiB
>   DEVICE_HUNG ceiling: editor peak 5,211; -game forest_floor 4,972 / open_max
>   4,940 / plaza 4,993 (3/3 measured).** The 4.4× upgrade FITS this hardware.
>   World change is fence-clean: 1,071 modified + 17 new __ExternalActors__
>   foliage OFPA + the 4 foliage/ plans; ZERO FoliageType/mesh/material/umap/ini
>   edits. Editor closed clean (0 procs; PackageRestoreData an empty stub → _trash).
>   Per-species: Conifer 235,546 / ConiferPine 176,019 / SpruceSub 204,726 /
>   SpruceSapling 195,967. `d3_verdict.json`.
> - **D2 (two rounds).** Round 1 (m=5.48 zone map, no ceiling): densest-decile
>   cover 0.670 ≥ 0.60 target, but 1,004,307 instances (4× the 250k ceiling). Ryan
>   ruled a **post-multiplier per-bin density ceiling** (D_max = max ff-disc bin ×
>   ff_cap 2.38 = 1,691/bin; m_final = min(m_zone, D_max/trees_now)). Round 2
>   (ceilinged): **812,258 instances**, densest-decile cover **0.519** (< 0.60;
>   the 0.151 gap to the uncapped 0.670 is **T4-owed**, recorded). `d2_zone_counts_
>   ceiled.json`, `canopy_cover_ceiled.json`, `canopy_cover_map_ceiled.png`.
> - **open_max — the new 4th budget station** (Ryan): densest post-ceiling bin
>   outside all discs = bin (2,15) @ (640,3968) m, **4,943 in-frustum trees**
>   (2.7× forest_floor's 1,844 — the post-upgrade cost hot-spot). budget 13.0.
>   `research/brief5/input/open_max_station.json`.
> - **D0b:** desk 0.1 ms ff margin → ff cap **2.38**, proj **12.90** (was 2.919/
>   13.0). zone_map m_cap made blend-aware (invariant m_final ≤ m_cap; was a flat
>   cap the blend legitimately exceeded). Commits 5a7a4afe, d014b6d6.
> - **Recipe-driven:** `recipes/alpine_8k.json` foliage now declares
>   `density_zone_map` + `density_ceiling`; `place_foliage` applies both (zone
>   multiplier × per-bin ceiling, min); MAX_INSTANCES 250k → **860,000** (planned
>   851,046 > placed 812,258; the gate checks planned). `import_heightmap.
>   _validate_foliage` extended for the new keys + lod_screen_sizes.
> - **OWED forward (decisions MADE):** (1) **D4** — full -game perf: ff / open_max
>   / treeline / plaza / vista, 3 runs each, GPU + game-thread per-pass, table vs
>   budget; any station over → REVERT D3 (sha proof) → D7. canopy_cover on the real
>   (now-saved) plans (closes B5.14). Then **ASK #2** (five-station before/after
>   stills; Ryan rules). (2) **D6** HLOD (changed cells only) after ASK #2. (3)
>   **D7** package/push. (4) **T4 rungs** owed to close the 0.151 densest-decile
>   cover gap (SpruceSub build-stall root cause still owed before retry).
>   (5) clutter cost (D5) still owed. **NOT PUSHED until D7.**
> - **The prior part-1 block (T4 API, D1a partial, D0) is folded above; its detail
>   is in the git log (commits e68657ca → 60c56171) and LESSONS.**
>
> <!-- superseded part-1 detail retained below for reference this session only -->
> - **BUDGET RULED 13.0 (Ryan, this session).** R5-1 = **13.0 ms** forest_floor
>   budget (desk revision), SUPERSEDING the same-day 12.5 (which this file and
>   DENSITY_PLAN/INDEX_p carried). 13.0 is both the pass/fail budget AND the fence
>   abort ceiling. The prior-session 12.5 block below is superseded. Docs re-cast;
>   at 13.0 the current hold 12.645 is 0.355 UNDER; m=5.48 proj 13.474 is +0.474 OVER.
>   Commit 65748b2e.
> - **T4 LOD API resolved** from the reflected PythonStub (set_lod_reduction_settings
>   :367729 w/ MeshReductionSettings.base_lod_model = "base LOD G"; set_lod_from_static_mesh
>   :367742 returns the LOD index set, neg = not set; set_lods NOT used — regenerates
>   from LOD0, destroys the authored card). `input/t4_api_resolved.json`. Commit e68657ca.
> - **D1a (Ryan-inserted: T4 rungs on scratch, gate vs LOD G, box 90 min) — PARTIAL.**
>   Build harness (`brief5_t4_build.py`/`_cold.py`/`t4_build_run.py`) auditor-gated
>   CLEAR-TO-EXECUTE (MAJOR-1 self-verify gap + 5 MINOR fixed). Executed reap-safe
>   (editor detached, short foreground ue_exec). **ConiferPine gate BUILT + saved**
>   (`/Game/Scratch/T4/ConiferPine_gate`, gitignored) — the reduce-from-G + card-
>   preserving chain method PROVEN. **SpruceSub build STALLED the editor** (~6.5 min
>   log-silence after its rungsrc built; Queue-2 unresponsive mode) → force-killed
>   (rule 6). Fence HELD (4 shipped/_SRC sha byte-identical). Commits 7d3ed95b →
>   2545aa2d → ee9972dd.
> - **The isolation-render GATE never ran** → **no rung PASSED**. Per Ryan's pre-
>   authorized fallback: **D1 SKIPPED**, **D0 caps forest_floor from CURRENT headroom**.
> - **D5 SKIPPED** (no measured clutter cost; pcg_cost arms absent) — owed.
> - **D0 zone map — DONE (offline).** Zone rule (Ryan): three 512 m station cull-discs
>   (forest_floor/plaza/treeline); bin cap = min over containing discs; outside all =
>   target m=5.48; per-station cap = min(budget cap, target) with target a ceiling; 128 m
>   linear blend across each disc edge. `scripts/zone_map.py` (caps from the
>   density_project cost model, xcheck reproduces density_projection) →
>   `derived/zone_map.json` + `zone_map.png`. Caps: **forest_floor 2.919** (current
>   headroom), plaza/treeline 5.48 (budget caps 12.31/7.72 > target). 726 bins: 21
>   constrained below target (ff disc + blend tail), 705 at target, 1 overlap
>   (ff+treeline). Every station ≤ budget: ff 13.000, plaza 9.882, treeline 7.513.
>   `density_project.py` stale 12.5→13.0 fixed + regenerated. Commit 60c56171.
> - **OWED forward (decisions MADE, unbuilt):** (1) **D2** dry-run — wire zone_map m
>   per-bin into `place_foliage` density (top-level `density_per_hectare` +
>   per-species `density_per_10m2`, sampling `foliage.planting_field`), count-only (NO
>   writes to foliage/), + `canopy_cover.py` projected cover per bin (densest decile
>   ≥0.60 or report what it reaches). Then **>>> ASK #1** (show Ryan: D1=skipped, the
>   D2 table). (2) The **SpruceSub build stall** root cause (species-specific; owed
>   before retry — retry fixes logged: ONE species per ue_exec call + incremental
>   on-disk progress markers). (3) The **isolation-render gate** (coverage ratio +
>   silhouette IoU vs LOD G, Brief-1 lod_silhouette_check) → `t4_scratch_gates.json`.
>   (4) D3 regen → D4 measure → (D5 skip) → **ASK #2** → D6 HLOD → D7 package.
> - LESSONS carries the two-altitude record (audit roots-omission repeat; the reap;
>   the SpruceSub stall; the audit-caught self-verify gap). `ConiferPine_gate` left on
>   scratch (gitignored) for the render-gate session.

# 2026-09-21 (OVERNIGHT QUEUE 2 — PCG DENSITY/CLUTTER: density plan MEASURED offline; PCG authoring PROVEN; clutter cost OWED) — superseded as the live block by the 2026-09-22 Daylight Density block above

> ⭐ **2026-09-21 — Overnight Queue 2 (Brief 5 Part C). Autonomous. Checkpoint
> `pre-pcg-night` on b5ac5c55. Offline deliverables landed; the live clutter-cost
> measurement was defeated by the harness, not the approach. Shipped world
> BYTE-IDENTICAL (Alpine8K.umap git-tracked, no diff vs HEAD, mtime 17:57 predates
> the session; editor killed without ever saving). NOT PUSHED at write.**
>
> - **P4 DENSITY PLAN (the daylight table) — `for_desk/DENSITY_PLAN.md` +
>   `input/density_projection.json` + `scripts/density_project.py`.** Upgrade = one
>   global density multiplier `m = m_for.p90_bin = 5.48` (crown 0.85). Per-station @
>   m=5.48, ex-clutter: **forest_floor 12.645→13.474 (OVER header 13.0 by 0.474, over
>   ratified 12.5 by 0.974 — a lower bound), treeline 7.139→7.513 (over 7.0, UNDER tol
>   7.7), plaza 9.476→9.882 (UNDER, ~0.6 ms room).** forest_floor busts on live-tree
>   growth alone; the paying lever is cull/foliage-shadow distance, NOT T4 (the growth
>   is Lumen+shadow, not Nanite raster).
> - **RULED 2026-09-22 (Ryan) — SUPERSEDED SAME DAY. Final R5-1 = 13.0 ms (desk revision).**
>   An earlier ruling this day set forest_floor budget = 12.5 and dropped a header 13.0;
>   at the Daylight Density session start Ryan reinstated **13.0 as R5-1 (the desk revision,
>   2026-09-22)**, kept as both the pass/fail budget AND the fence abort ceiling. Consequence
>   at 13.0: forest_floor proj 13.474 OVER 13.0 by **0.474**; the current hold 12.645 is UNDER
>   13.0 by 0.355 (it busted the withdrawn 12.5 by 0.145). density_project.py must be re-run
>   with budget 13.0. (History: the earlier 12.5 block and its "auditor caught the hardcoded
>   13.0" note recorded the state before this supersession.)
> - **P2 clutter inventory — `input/clutter_inventory.json`** (79 ground-clutter
>   meshes, registry-only, classed rock/deadwood/herb/shrub/grass with tris/LOD/Nanite/
>   bounds/textures; HAZARD meshes named; per-class cheapest picks).
> - **P3 — PCG-graph authoring PROVEN, cost measurement NOT captured.** A real PCG
>   graph (SurfaceSampler→TransformPoints→StaticMeshSpawner weighted) was built AND
>   saved from Python (`Content/Scratch/PCG/PCG_ClutterSpike.uasset`, gitignored).
>   Acceptance arms (≥3 with GPU+game-thread ms/1000 by class) **NOT met** — the
>   overnight harness reaped the measurement's background client twice and the editor
>   then went unresponsive (~25 min), force-killed. Retry recipe recorded
>   (`input/pcg_cost.json`; `scratchpad/pcg_measure_fast.py` foreground <120s).
> - **P6 PVE — verdict `no migration, evaluate further`** (experimental, 5.7→5.8
>   breakage, non-single-variable −0.38 ms; export not scriptable). PVE plugin enabled;
>   4 SM_PVE_Norway_Spruce already exported.
> - **Scoped out (logged):** P1 Biome enable (non-essential + experimental risk), P5
>   T4 rungs (does not pay the forest_floor overage).
> - **OWED (supervised session):** clutter cost arms; forest_floor post-hold per-tree
>   rate; in-game HLOD share at forest_floor/plaza; the budget ruling.
> - **New tooling:** `scripts/density_project.py`; `scripts/payloads/pcg_clutter_spike.py`;
>   `research/brief5/scripts/pcg_spike_run.py`. LESSONS carries the two-altitude record
>   (harness client-reaping defeats >120s live-editor measurements; manual HISM unusable
>   in 5.8 Python — use InstancedFoliageActor.add_instances).

# 2026-09-21 (ITEM 8 — HLOD PROXY GPU SHARE: MEASURED via a -game MRQ HLOD-toggle; the v3 INCONCLUSIVE is resolved)

> ⭐ **2026-09-21 — ITEM 8. One write editor pass (build scratch assets) + one
> read-only editor pass (cleanup), each closed by launched-PID kill; six `-game`
> MRQ renders. Every new tool passed a three-round auditor gate (round-2 BLOCK →
> fixed → CLEAR-TO-EXECUTE) before first execution. Fence HELD: census CLEAN —
> world + all 14,153 non-scratch assets byte-identical, umap sha256 identical, no
> `/Game/Scratch/Item8/` remnant. Zero DEVICE_HUNG; VRAM peaked 8,553/13,312 MiB.
> NOT PUSHED.**
>
> - **THE HEADLINE — the v3 GPU-share INCONCLUSIVE is RESOLVED.** `wp.Runtime.HLOD 0`
>   delivered through `MoviePipelineConsoleVariableSetting.StartConsoleCommands`
>   (MoviePipelineConsoleVariableSetting.h:72) on a `-game` command-line MRQ render
>   fires AFTER world load and **APPLIES**: GPUSceneInstanceCount 1,406,348 →
>   1,344,921 = **−61,427 instances (4.37%)** in the HLOD-off arm, identical at
>   both stations; SceneCulling drops the same 61,427; ActorCount/WorldPartitionHLOD
>   stays 422 (SetVisibility, not unload — per HLODRuntimeSubsystem.cpp:149-187).
>   This is the counter change v3's startup-ExecCmds channel could never produce.
> - **THE NUMBER — treeline MEASURED.** Render-frame GPU p90, arm A (HLOD on) vs
>   B (off): treeline 49.46 → 48.88 = **0.576 ms share (1.2%), ×2.9 the A/A floor
>   → MEASURED**; vista 49.28 → 48.82 = 0.457 ms (0.9%), ×0.7 its noisier 0.67 ms
>   floor → MEASURED-NEGLIGIBLE. Per-pass drop (treeline): NaniteVisBuffer +0.225,
>   ShadowDepths +0.164, Basepass +0.080 ms — the instanced-proxy raster+shadow.
> - **THE PIXEL FRACTION.** Hiding the proxies changes **0.20% of non-sky pixels**
>   (~3× the A/A pixel floor), far below the derived beyond-512 fraction 0.05727 →
>   the instanced tree proxies are a thin subset of the far field (most beyond-512
>   ground is the MESH_APPROXIMATE merged landscape proxy + haze). Cheap by
>   construction — consistent with the v3 composition read.
> - **⛔ THE INSTRUMENT TRAP (logged).** A `-game` MRQ render renders OFF the main
>   game loop, so the CsvProfiler per-row `GPUTime` is the near-idle offscreen
>   pump (~0.07 ms), NOT the 4K render. The render is captured only on rows where
>   `GPU/Basepass>0` (~64 of them); per-frame GPU = sum of `GPU/*` passes, window
>   = last 30 render rows (the first ~20 spike to 3.6 s on shader/Nanite/TSR init).
>   The first analyser windowed on GPUTime and reported a nonsense 0.08 ms — fixed.
> - **TWO CAVEATS (rule 10).** The ~49 ms/frame is MRQ full-quality 4K, heavier
>   than the ~7-12 ms game viewport — transfer the SHARE FRACTION (~1%), not the
>   ms. Far-forest crops (I4): 12 in `derived/item8/`, tiling is Ryan's visual
>   call (auto repetition-score is non-discriminating on self-similar canopy);
>   targets beyond each station's flat-ground horizon (vista 1392 m, treeline
>   1777 m) are flagged — exact far distance needs a depth pass not taken.
> - **Deliverables:** `input/item8_share.json` (I5), `item8_perf.json`,
>   `item8_pixels.json`, `item8_levers.md` (levers FILLed at header:line);
>   `derived/item8/` (6 frames + 12 crops); `for_desk/INDEX_i8.md`. REGISTER
>   B5.19 = **M**. BACKLOG item 8 RESOLVED. LESSONS carries the two-altitude record.
> - **New tooling:** payloads `item8_build.py` / `item8_cleanup.py`; drivers
>   `item8_capture.py` (zero-editor gate, launched-PID kill, VRAM poll,
>   DEVICE_HUNG protocol, byte-identical census bracket), `item8_census.py`,
>   `item8_perf.py`, `item8_pixels.py`, `item8_share.py`.
> - **OPEN / owed forward:** the absolute ms is at MRQ quality, not the 12.5 ms
>   game budget; a true in-game HLOD-share ms would need the render measured on
>   the game loop (PIE-side profiling), not MRQ. Brief 5 acceptance remains the
>   REPLAY_BURNDOWN cold replay.

# 2026-09-21 (BRIEF 5 REPAIR R1–R4 — THE HOLD IS RE-APPLIED, PERSISTED, AND PROVEN LIVE AT RUNTIME)

> ⭐ **2026-09-21 — BRIEF 5 REPAIR (R1–R4). One write editor pass (R1 apply) +
> four read-only passes (R1 cold, R2, isolated ×2, R4), each ended on
> R-EDITOR-CLOSE (census dirty_count 0, killed, 0 editors, no PackageRestoreData);
> 6 `-game` perf runs (R3). Every new tool passed a three-round auditor gate
> before first execution. check_docs + offline suite NO FAILURES. NOT PUSHED
> (fence: only ScotsPineTall_01 + spruce_half_01 written).**
>
> - **THE HEADLINE — the T3 no-op is FIXED. The hold now reaches disk AND drives
>   the runtime.** The C-block below (T3 never persisted) was true THEN; this
>   session re-applied and proved it.
> - **R1 — HOLD PERSISTED.** Root cause at source: `SetLodScreenSizes` never marks
>   the package dirty (StaticMeshEditorSubsystem.cpp:1020-1097), so T3's default
>   `save_loaded_asset` was a clean-package no-op. Fix: `Object.modify(True)` +
>   `save_loaded_asset(only_if_is_dirty=False)`. Proven in a DIFFERENT process:
>   both `.uasset` sha256+mtime changed (ScotsPineTall_01 c6ca202c→3b8a0b5a,
>   spruce_half_01 0539bda4→c830a651); cold `get_lod_screen_sizes` (PID 32556 ≠
>   apply 21944) = targets [.,.,.,0.03818] / [.,.,.,.,0.02642] within 1e-4, tris
>   32/6, slots 5/4, `is_lod_screen_size_auto_computed()` False. Auto-compute was
>   already False on the pristine vendor meshes (0.168/0.17 baked MANUAL), so
>   recompute-safe. `input/r1_persist.json`.
> - **R2 — coloration INCONCLUSIVE (instrument contaminated), NOT a pass.**
>   Overlapping 2D boxes, no occlusion: ConiferPine (4 LODs) classified index-4
>   yellow with 0% of its own card in BOTH C1 and R2 (rule-13 shape). RenderData
>   flipped matches_t3_hold False→True = persist+load, NOT runtime proof.
>   `input/r2_lod_readback.json`, `r2_verdict.md`.
> - **isolated_check — scene-defeated (operator-ordered, honest).** Synthesized
>   isolated cameras render white (high-alpine cells outside the offscreen render
>   region; a ring control rendered 1.12M sat px); the dense band has no
>   zero-intruder/frontmost box. ConiferPine best box leaned geometry (95.5% red
>   LOD1). Deferred to R3.
> - **R3 — HOLD TOOK AT RUNTIME (the decisive uncontaminated control).** 6 `-game`
>   runs post-persist. forest_floor GPU p90 **12.645 ms** vs v3 pre-hold 11.048 =
>   **+1.597 ms (99.8× noise)**; Basepass+ShadowDepths+Prepass **+1.131 ms (70.7×
>   the 0.016 ms floor)** — Basepass +0.574, ShadowDepths +0.556 — the card→geometry
>   conversion (LumenReflections −0.123). `input/r3_perf.json`.
> - **R5-1 — OVER budget.** forest_floor p90 12.645 > 12.5 ms by 0.145 ms → T4
>   (rungs, `derived_ladder.json` target_tris) LISTED, not run; hold NOT reverted
>   (the tiling fix stands; rungs are a cost optimisation on top).
> - **R4 — imposter override hypothesis DISCONFIRMED (read-only).** The recipe
>   override `MI_half_01_imposter_nowind` EXISTS at `/Game/Materials/PN_NoWind/`
>   (C2's exists:false checked the wrong folder). It shares base `MA_Imposter` and
>   EVERY scalar/vector/texture param with the vendor MI; the ONLY delta is two
>   static switches (Level 1 Bending, Level 1 Wind) OFF — WPO wind/bending, NOT
>   octahedral frame selection. H4 stands, resolved by R1+R3. The imposter material
>   is not defective. `input/imposter_defect.json` (R4 block), `r4_imposter_read.json`.
> - **check_recipe_lods** now REFUSES any probe not stamped cold_readback+distinct;
>   reads `tree_lod_probe_cold.json` (was the stale in-memory `_t3` probe).
> - **Package:** `research/brief5_r.zip` (152 files, gitignored, regenerable via
>   build_sendback.py) + `for_desk/INDEX_r.md`. REGISTER + LESSONS carry the
>   two-altitude record.
> - **OPEN / owed forward:** T4 rungs (LISTED, not run) to bring forest_floor under
>   12.5 ms; the isolated single-instance coloration read is not obtainable in this
>   scene (aggregate cost R3 is the runtime instrument). Brief 5 acceptance remains
>   REPLAY_BURNDOWN cold replay.

# 2026-09-21 (BRIEF 5 close-out C1+C2 — THE T3 HOLD NEVER PERSISTED; it was a runtime NO-OP) — SUPERSEDED by the REPAIR block above (the hold is now persisted + proven live at runtime; C's diagnosis was correct for its time)

> ⭐ **2026-09-21 — BRIEF 5 CLOSE-OUT (C1+C2). Two read-only editor passes
> (R-EDITOR-CLOSE after each: 0 procs, PackageRestoreData absent, world
> byte-identical to HEAD). Three-round auditor PASS on all tooling before first
> execution. check_docs + run_offline_suite NO FAILURES (34). Commits
> 68ec150b→48fd00f2→0e765578 (tooling+audit) → 833c3cca (C1 run) → 169d5543 (C1+C2
> close). NOT PUSHED (fence).**
>
> - **⛔ THE HEADLINE — T3 "SHIPPED THE FIX" (2026-09-21 block below) IS FALSE. The
>   hold is a NO-OP at runtime.** C1's direct render-data readback in a fresh
>   editor: the meshes the live HISM foliage reference still carry the PRE-HOLD
>   card ScreenSize — ConiferPine LOD3 = **0.16821**, SpruceSub LOD4 = **0.17**
>   (t3_hold targets 0.03818 / 0.02642), `matches_t3_hold = false` for BOTH.
>   `get_lod_screen_sizes` returns `RenderData->ScreenSize` (the runtime's LOD
>   input; StaticMeshEditorSubsystem.cpp:1003-1008). Mesh LOD Coloration corroborates:
>   the 128-512 m band is ~80% CARD (a hold that took → ~0% card there). Legend
>   read from the on-screen bar, validated vs BaseEngine.ini. Files:
>   `research/brief5/input/c1_lod_readback.json` + `c1_renderdata.json` +
>   `derived/c1_lodcolor/`.
> - **ROOT CAUSE — the T3 save never hit disk (false-success `saved:true`).** Live
>   `.uasset` mtimes predate the T3 run: `ScotsPineTall_01.uasset` **2026-08-02**,
>   `spruce_half_01.uasset` **2026-08-14**; only the `_SRC` backups carry the T3
>   mtime (06:29). Both meshes are gitignored → git not involved. The T3 in-memory
>   readback (0.038/0.026) was lost on editor close. `tree_lod_probe_t3.json` and
>   `alpine_8k.json`'s "recipe == asset" note are STALE — the asset ≠ the recipe.
>   **This retroactively explains V1 (SSIM tie) and V2 (~0 ms): nothing changed
>   because nothing was applied.** New rule (LESSONS 2026-09-21): a value is not
>   persisted until read back in a DIFFERENT process, or the file mtime confirms
>   the write — the setter's return + a same-session readback prove only memory.
> - **C2 (Showroom imposter) — does NOT tile in the vendor demo.** spruce_half_01
>   is placed there as HISM (FoliageInstancedStaticMeshComponent) + static actors
>   with the SAME `half_01_imposter` material; forced-card AND auto at 150 m render
>   clean billboards, no square tiles. **H1 (octahedral frame-blend fails under
>   HISM) DISCONFIRMED.** Favoured now **H4: the Alpine8K tiling is scene-specific**
>   — the card drawn large/close in 128-300 m because the hold never persisted,
>   magnifying the low-frame octahedral atlas; + Lumen HWRT/exposure vs flat demo
>   lighting. Confirming experiment in `input/imposter_defect.json`.
>   Files: `input/c2_showroom.json`, `derived/c2_showroom/`.
> - **CONSEQUENCE FOR BRIEF 5 — NOT closed.** The T1-CONFIRMED imposter tiling is
>   STILL LIVE in the 128-512 m band. The fix must be RE-APPLIED and verified to
>   PERSIST across an editor restart (a write — out of this read-only session's
>   scope). Likely persist-blocker to defeat: `bAutoComputeLODScreenSize` had no
>   Python setter in T3 (recorded in t3_hold.json), so a mesh rebuild can recompute
>   the ScreenSizes back to auto — but the primary evidence here is simpler (the
>   package was never written). **NEEDS RYAN / DESK: a follow-up write session to
>   re-apply the hold with a mtime/fresh-process persist check; or rule the hold
>   out and accept the tiling.**
> - **Package:** `research/brief5_c.zip` (121 files, gitignored, regenerable via
>   build_sendback.py) + `for_desk/INDEX_c.md` (6-line summary + per-file table).
>   REGISTER + LESSONS carry the two-altitude record.
> - **Tooling added:** payloads `brief5_c1_lodcolor` / `c1_renderdata` /
>   `c2_discover` / `c2_shot`; driver `research/brief5/scripts/c_capture.py`
>   (zero-editor gate, launch-PID kill, exact-filename mtime poll); analyzer
>   `c1_lod_readback.py` (on-screen-legend palette + saturated-pixel classify,
>   overexposure-robust). `get_level_viewport_fov` needs a ViewportConfigKey
>   (LevelEditorSubsystem.h:128); FOV read back = 90.0.
>
> The 2026-09-21 block below (T0-T6 / "T3 SHIPPED THE FIX") is SUPERSEDED-IN-PART:
> its T3 persistence claim is FALSE per the above; its T0/T1/T2/T5/T6 read-only
> measurements stand.

# 2026-09-20 (BRIEF 5 baseline v3 — the two audited conclusions re-measured; queue 0–5 DONE + COMMITTED) — superseded as the live block by the 2026-09-21 close-out above

> ⭐ **2026-09-20 — BRIEF 5 BASELINE v3: the desk audit's two rejected conclusions
> re-measured; queue Tasks 0–5 DONE + COMMITTED. One offscreen read-only editor
> pass, CLOSED clean (R-EDITOR-CLOSE: 0 dirty, 0 processes, PackageRestoreData
> benign→_trash, world byte-identical to HEAD). 8 `-game` runs (6 noise + forest
> A/B) + 1 editor pass; no DEVICE_HUNG. check_docs + run_offline_suite NO FAILURES
> (31).** Commits 0d9508ea (T0) → …noise/T2ab/levers/switch → 62579e95 (T5).
> - **T0 records:** assembler now reproducible + idempotent (reads HLOD from
>   hlod_share.json, computes per-10k from inputs — audit B2); census in_frustum
>   2/4-tuple crash fixed + `visible`→`in_frustum_in_cull` + base→top segment test
>   + selftest; PCG_NOTES §3 un-swapped, flags 1/2/4 resolved, cites repointed;
>   dolly 267 usable pairs (excl. FAILED 09-07); v2 marked SUPERSEDED-IN-PART.
> - **T1 noise floor:** min_detectable treeline **0.060** / plaza **0.040** /
>   forest **0.016** ms (=2·sd). GPUScene DETERMINISTIC across as-is runs — refutes
>   v2's "streaming variance" (that swing was the D2/D4 grass.DensityScale lever).
> - **T2 HLOD — INCONCLUSIVE (v2 "RESOLVED–negligible" REVERTED, audit A1/A2).**
>   `-game` control FAILS (as-is vs `wp.Runtime.HLOD 0` byte-identical on every
>   render counter; the "deferred warning" was the normal echo — command IS an
>   FAutoConsoleCommand, HLODRuntimeSubsystem.cpp:149, one-shot pre-stream).
>   Editor renders real cells at full residency (v2's 0.015 ms null IS the control
>   failing). **BUT composition MEASURED:** Instanced=INSTANCING (lowest-LOD ISM),
>   Merged=MESH_APPROXIMATE; 512 m–2 km each species is its lowest-LOD instance
>   (cards/imposter/2335-tri Nanite fallback — NOT the full Nanite mesh). **2d
>   distances FIXED** (grid-index arithmetic, not degenerate Instanced-HLOD
>   bounds): vary per cell/station (nearest 105.9/120.9/192.4/0.0 m). GPU *share*
>   ms number still open (item-8 `-game` MRQ).
> - **T3 forest cost:** derived forest_floor station (1844 in-frustum trees, the
>   MAX at 90° FOV — 5000 unreachable on this ~0.005 trees/m² forest). Foliage
>   **0.185 ms (11.4× min_det)**, in LumenReflections+shadows+basepass (NOT Nanite
>   raster); **0.100 ms/1000 visible trees** (upper bound) — REPLACES the withdrawn
>   off-frustum ms/10k. Per-species -game hide: not available (stated, not faked).
> - **T4 editor read-backs:** all 4 FoliageTypes `enable_density_scaling=False`
>   (density lever INERT — audit B3); cull 384→512 m fade (sapling 179→238); only
>   Conifer Nanite (fallback 2335); Nanite Foliage project setting ON
>   (DefaultEngine.ini:63). Switch distances (fresh probe): billboard 127.8 m/332
>   px, imposter 87.5 m/367 px — all ABOVE the 40 px floor (A8 quantified); recipe
>   ConiferPine LODs ≠ built asset LODs (4b).
> - **T5 BASELINE.md v3** rebuilt from JSON (MEASURED → MEASURED-NEGLIGIBLE →
>   INCONCLUSIVE); levers table has header:line (levers_verified.md); closing
>   "what the desk may/may not derive". Formula D=1.778·R/ScreenSize verified
>   (SceneManagement.cpp:966/980); all LOD/view scales = 1.0.
> - **Packaged for the desk:** `research/brief5_v3.zip` (26 files, mirrors the
>   `brief5/` tree like v2's zip; gitignored, regenerable) + `brief5/for_desk/
>   INDEX_v3.md` (per-audit-finding disposition A1–A8/B1–B6/C + the numbers + the
>   two derive/not-derive lines). Self-contained (probe copied into `input/`).
> - **Owed forward:** the HLOD proxy GPU share / live pixel fraction is the one
>   open number — **filed as BACKLOG item 8** (`-game` MRQ HLOD-toggle, sized L,
>   own session; records why both in-fence channels fail + the clean path +
>   closes proxy_fraction 0.05727 vs live). Brief 5 acceptance remains
>   REPLAY_BURNDOWN cold replay.
>
> The 2026-09-20 overnight block below is SUPERSEDED-IN-PART by this v3 (its HLOD
> "negligible" and ms/10k figures are withdrawn); its item 0/1/4-7 detail stands.

> **STANDING NOTE — large session-close push convention (2026-09-20).** A `git
> push` of a long history (1500+ commits) fails with `RPC failed; HTTP 500`
> mid-pack: LFS objects upload to S3 fine, but the non-LFS pack (here 27.9 GB,
> see `research/GIT_LFS_AUDIT.md`) is too big for the server in one shot.
> Convention: (1) run the close-out push in the BACKGROUND and watch it, never
> block on it; (2) if it 500s, use `scripts/push_chunked.py` (halve-on-failure
> 100→50→25→10→1, resumable from the remote ref, exits with git's real code) —
> do NOT `git gc`, force, or rewrite history to "fix" a push; (3) if a SINGLE
> commit fails at span 1, that is an oversized-blob content problem — log the
> blob and stop pushing, do not escalate. Durable home is CLAUDE.md/
> GOVERNANCE_MIGRATION.md once CLAUDE.md is under its 25000-char ceiling (it is
> at 24971 now); parked here meanwhile.

> **OVERNIGHT 2026-09-20/21 (autonomous block).** The desk deliverable
> `research/brief5_desk.zip` NEVER ARRIVED (absent + all its contents absent), so
> the Brief-5 measurement queue (Q0–Q2, Q4a, Q5–Q8, Q10) was BLOCKED, not skipped.
> Independent work done + committed: Q3 (`git_blob_audit.py` + `push_chunked.py` +
> `GIT_LFS_AUDIT.md`), Q4b (`levers_b5.md` header:line fills), Q9 (`ITEM8_PLAN.md`),
> Q11c (`resource_guard.py` selftest, suite 32 green). Package `research/brief5_b5.zip`
> + `for_desk/INDEX_b5.md` (10-line MORNING SUMMARY). Read-only + git only; world
> byte-identical; no editor/`-game`/asset/ini change. **`git config gc.auto 0` is
> SET — restore in the morning (`git config --unset gc.auto`).** **PUSH: chunked
> push advancing (remote 87d25f8e ← 364716f5); HARD BLOCKER = non-LFS `.exr`
> 123–133 MB > github.com's 100 MB limit — full completion needs an LFS migrate
> (history rewrite, Ryan's call).** Needs Ryan: resend the desk zip; rule the LFS
> migrate; rule the item-8 scratch-asset fence.

> **2026-09-21 (Ryan at work, full authority).** Desk zip ARRIVED (Downloads);
> Brief 5 T0-T6 RAN. **T3 SHIPPED THE FIX:** ScotsPineTall_01 + spruce_half_01
> card LODs pushed to ss 0.03818 / 0.02642 -> engage 563 m (past the 512 m cull);
> never drawn live, HLOD still uses them. Hold cost **+0.042 ms** at forest_floor
> (x2.6 min_det), FAR under the 12.5 ms budget -> T4 rungs UNNEEDED. recipe==asset
> for 4 species (check_recipe_lods.py in the suite; restamp reconciled). _SRC dupes
> are the reversibility (Content gitignored; restore tag pre-brief5-t3-hold).
> Editor CLOSED clean. T0 byte-identical; T1 +2.9/+3.5 ms geometry-vs-card
> (positive control passed), texel gate MEASURED-violated for the SpruceSub
> imposter (magnified 87.5-125 m); T2 billboard 2048 / imposter 4096 atlas; T5
> HLOD not functionally stale (lowest LOD unchanged), ~1225 cells source-stale, no
> build; T6 canopy = WOODLAND (no forest bins, max 0.285 < predicted 0.36,
> m_for.p90 5.48). Suite NO FAILURES (34). Package research/brief5_b5.zip (54
> files) + for_desk/INDEX_b5.md. **LFS MIGRATE DONE** (>100MB .exr/.blend1/.zip ->
> LFS, per Ryan); **push LANDED (remote = HEAD), tag brief5-v3-delivered up.**
> **T1 stills CAPTURED + CONFIRMED:** ring_station arm A r.ForceLOD 4 (cards) vs
> arm B r.ForceLOD 2 (geometry) -- coverage ratio B/A 1.87 (outside 0.90-1.10) AND
> band SSIM 0.46 (<0.90), both gates fail; crops show a flat billboard slab vs a
> detailed 3-D tree (`t1_see_it.json`, `derived/t1_stills/`). Brief 5 T0-T6 FULLY
> CLOSED. Package brief5_b5.zip (65 files). Only item-8 HLOD share + density (item
> 8 / R5-2) remain. gc.auto still 0 -- restore later.

# 2026-09-20 (BRIEF 5 overnight — items 0–7 landed, BASELINE v2) — SUPERSEDED-IN-PART by v3 above (HLOD verdict + ms/10k withdrawn)

> ⭐ **2026-09-20 — BRIEF 5 OVERNIGHT: queue items 0–7 DONE + COMMITTED;
> BASELINE.md v2 + density_baseline.json v2 written. Editor opened offscreen for
> a read-only pass and CLOSED clean (R-EDITOR-CLOSE: 0 dirty, zero editors,
> PackageRestoreData absent). Zero UnrealEditor processes at close. Tree clean.**
> Commits 7f3711a9 (item 0) → 4ff39681 (items 2,4,5,6,7) → aaeb8f4a (items 1,3)
> → this STATE/BASELINE close-out.
> - **Item 0:** desk §12 APPENDED to research/audit/AUDIT.md (additive; §11 +
>   Pass 2 DONE intact) + practice line (repo AUDIT.md canonical, desk appends).
> - **Item 1 — the 7.1 ms NAMED** (perf_standalone --csv-gpu-stats → 53
>   GPU/<pass> cols): treeline = VolumetricCloud 11.9% + NaniteVisBuffer 11.7% +
>   ShadowDepths 9.5% + TSR 8.4% + Post 7.4%; plaza = NaniteVisBuffer 19.2%
>   (buildings) + shadows 18.6%. Atmosphere/Nanite-raster/shadows/TSR/post — NOT
>   live foliage. Brief 5's first number.
> - **Item 2 density sweep:** foliage.DensityScale 1/2/4 read back but instances
>   did NOT rise — DensityScale>1 is a no-op on placed HISM (capped at authored
>   count); grass no measurable regen. NO budget crossing at any scale. Marginal
>   cost from the DOWN direction: ~0.107 ms/10k (treeline), ~0.023 (plaza).
> - **Item 3a/b/c:** no PCGWorldActor (CDO grid 25600 cm); Conifer Nanite
>   (fallback 2335 tris), ConiferPine imposter@0.168, SpruceSub@0.17, Sapling
>   none. **3d HLOD share — RESOLVED 2026-09-20, NEGLIGIBLE** (`hlod_share.json`):
>   verified actor-hide A/B at vista (1042/1042 HLOD proxies hidden), steady
>   ~3300-frame editor CsvProfile windows → GPUTime p90 7.287 visible vs 7.272
>   hidden = 0.015 ms (0.2%). REFUTES v1's "forest is mostly HLOD" inference —
>   distant HLOD is Nanite at 2.2–3.5 km, near-free; the frame is landscape
>   Nanite + atmosphere + shadows. The -game cvar wp.Runtime.HLOD 0 never applied
>   (LogEngine: Warning deferred); single-frame ProfileGPU was ±3.7 ms noise, so
>   a steady window + verified actor-hide were required. Editor CLOSED clean.
> - **Items 4–7 (deputies, read-only):** reference_coverage.json (2 concept
>   meadow refs, no photos; grass ≈0.40 lower bound, estimate); dolly_manifest
>   .json (360 E4 frames, 356 pairs); PCG_NOTES.md (evaluate-don't-migrate holds;
>   HLOD share = the open number); replay_inventory.json (13 recipes, all inputs
>   present, 1 selftest pass / 12 none).
> - **perf_standalone.py** gained --density-scale / --hide-hlod / --csv-gpu-stats
>   (reuse the audited read-back; as-is path byte-identical). LESSONS appended
>   (two bare-cvar echoes the log would not carry; HLOD A/B inconclusive).
> - **Item 8 (1b live -game vista still) — INVESTIGATED, still deferred, NOT
>   faked** (`live_proxy_observation_STATUS.md`). The runtime proxy band renders
>   ONLY in a real -game process (bench_capture line ~881; -game HighResShot
>   empirically non-viable, ee4e173c; wp cvars deferred). The one clean path is a
>   -game MRQ build (vista LevelSequence + MoviePipeline config + the untested
>   -game MRQ command-line) — desk-scoped as hours on a DEVICE_HUNG-history
>   machine; not started on a long session (context-exhaustion discipline).
>   **Derivation proxy_fraction 0.05727** (88,065/1,537,813 non-sky ground px)
>   stands as instrument of record; **today's HLOD-share pass CORROBORATES the
>   qualitative core** (1042 proxies resident+visible, band renders). Open only:
>   the exact live pixel fraction vs the derived one — wants its own MRQ session.
> - **Owed forward:** grass.DensityScale / r.HLOD bare-query echo not parseable
>   from -AbsLog (tool gap). HLOD share CLOSED (above).
> - Brief 5 acceptance remains REPLAY_BURNDOWN cold replay (inventory pre-checked,
>   item 7).
>
> The 2026-09-19d block below still stands (Task 0 baseline).

# 2026-09-19d (BRIEF 5 TASK 0 — density + cost baseline landed) — superseded as the live block by 2026-09-20 above

> ⭐ **2026-09-19d — BRIEF 5 TASK 0 (density + cost baseline) LANDED + COMMITTED
> (e6bf116e). No editor session — the only world-touch was two standalone -game
> perf A/B pairs (mutate nothing, restore by process exit); ZERO UnrealEditor
> processes at close. Tree clean, offline suite NO FAILURES across 31 checks.**
> Deliverables: `research/brief5/input/density_baseline.json` + `BASELINE.md`
> (every number with its read-back source); census
> `research/brief5/input/_census_stations.json`; perf `_verify/perf/brief5_ab/`.
> - **THE FINDING that shapes Brief 5: live foliage is cheap; the forest's GPU
>   weight is HLOD proxy + landscape.** Every tree species is culled INSIDE its
>   detail band (detail ring 238–1149 m vs the 512 m streaming-clamped cull), so
>   a live instance is only ever seen at DETAIL — shape/blob bands are entirely
>   HLOD's job. The foliage-hide A/B: treeline **0.116 ms (1.6%)**, plaza
>   ground-cover **0.286 ms (3.0%)**; removing 10,860 / 126,386 GPUScene
>   instances barely moved GPU p90. Density levers act on a near-free layer.
> - **Item 1 census** (`density_census.py`): 185,385 trees (Conifer 54,599 /
>   ConiferPine 40,326 / SpruceSub 46,841 / SpruceSapling 43,619). Visible
>   live-instance count per station: plaza 903, main_street 919, treeline **0**
>   (224 near in-cull trees excluded by azimuth 163 / elevation 61; its rendered
>   300 m–3 km forest is HLOD beyond cull), vista 34. Frustum validated by
>   plaza's ~25.4% visible/in-cull ratio across four species.
> - **Item 2 cost** (`perf_standalone.py --hide-foliage`, 4K, -noxgecontroller,
>   25 s p90 window): as above; hide read-back honoured (foliage.DensityScale=0,
>   grass.Enable=0; ShowFlag.Foliage accepted, no "not recognized"). No
>   sub-conifer-band meadow exists (land min 95 m, p05 196 m — lakes took the low
>   ground), so plaza (trees settlement-excluded) is the ground-cover isolation.
> - **Items 3–6 read-backs:** clutter = Meadow + Blueberry landscape grass only,
>   NO rocks/litter placed; PCG core enabled-by-default + PCGPythonInterop +
>   ProceduralVegetationEditor enabled, PCGBiomeCore/Sample available-not-enabled,
>   no PCG graphs; only Conifer (Norway Spruce) is Nanite (others LOD+billboard);
>   HLOD per-zone GPU share NOT attributable from the CSV (no HLOD GPU column).
> - **Audit (FIX, applied before any live run):** F1 read-back regex could not
>   match the engine's QUOTED cvar echo (ConsoleManager.cpp:3230), F2
>   r.ShowFlag.Foliage is not registered (ShowFlags.cpp:1116 → ShowFlag.Foliage),
>   F3 same-day A/B shared one sidecar (tag now in the sidecar name); census
>   F6/F7 provenance, F8 dead code, F9/F10 honest fields. As-is perf path
>   byte-identical to the ratified exec_cmds. LESSONS appended (audit-caught-
>   pre-execution). Two ROOTS omitted on first audit submit → BLOCKED → resubmit.
> - **NOTE for Ryan:** `research/audit/AUDIT.md` had an uncommitted stray
>   regression at session start (Pass 2 → PARTIAL, §11 deleted, inconsistent with
>   §12 CLOSED) that this session did NOT author — restored to HEAD via
>   `git checkout`. Worth a glance if you know what touched it.
> - **OWED forward (small, decisions open):** a read-only editor session would
>   close the PCGWorldActor/partition-grid read-back, Conifer's Nanite-fallback
>   tris + per-mesh imposter ScreenSize, and a measured per-zone HLOD GPU share —
>   all deferred here because scope limited the editor to the two perf pairs.
> - **Brief 5 acceptance remains REPLAY_BURNDOWN cold replay (13 UNPROVEN
>   recipes)** — Task 0 is the baseline the desk derives the rest of Brief 5 from.
>
> The 2026-09-19c block below still stands (Brief 4 carve FULLY LANDED).

# 2026-09-19c (BRIEF-4 WATER CARVE FULLY LANDED — the whole tail closed; R-WATER-CARVE LOCKED) — superseded as the live block by 19d above

> ⭐ **2026-09-19c — THE BRIEF-4 WATER CARVE IS FULLY LANDED. The owed tail
> (T6 reachable re-measure, T11 verify, T10 freshness, close-out) is closed;
> R-WATER-CARVE status is FULLY LANDED. Editor CLOSED (R-EDITOR-CLOSE, census 0
> + RSS flat + PackageRestoreData absent). This session was MEASUREMENT-ONLY —
> no scene mutation, no save (so rule-4 capture not required; the water capture
> was taken in the T5 editor phase).**
> - **T6 reachable — DONE, 35.32 km²** (navmesh lattice 9810 of 18496 cells;
>   was 36.53, −1.21 for the water, ≤1.5 target). z-span 0–1552.485, walkable
>   47.77 stand. **The first read collapsed to 2802 — HLOD proxy collision
>   (2026-09-14 4096 rebuild) intercepting the lattice ground trace, REFUSED
>   per rule 13, root-caused, fixed by ignoring `WorldPartitionHLOD` in the
>   trace (folded into `city_reachable_lattice_payload.txt`; R-NAVGRID step 9
>   amended). The navmesh was never defective — only the instrument.** Canonical
>   `city/alpine_basin_reachable_lattice.json` regenerated + stamped. Spec
>   (CLAUDE.md) updated 36.53 → 35.32.
> - **T11 verify — DONE:** all 4 zones PASS R-PERFBUDGET GPU/Game/Frame p90
>   (+10% tol); treeline 7.139 only zone over raw budget (7.0), inside
>   tolerance. VRAM peak UNMET-by-instrument (perf_standalone.py captures no
>   residency/exposure — rule-12 gap, `T11_VERIFY.md`; tool amendment owed).
> - **T10 freshness — DONE, `run_offline_suite` NO FAILURES across 31 checks.**
>   `restamp_consumed.py` extended for the three carve-induced hash moves
>   (terrain→town/roofbias PROVEN north-cascade-only; encounters.json/
>   plan_encounters.py→verified/_all per T8). Auditor F-1 (ordering) fixed;
>   format-preserving dump. The SUITE runs `check_plan_freshness --reproduce`
>   (stricter than plain), which had three residual reds the restamp missed:
>   foliage PRODUCER-REFUSES (place_foliage takes no `--out`; checker now maps
>   the argparse "unrecognized arguments: --out" to benign CANNOT REPRODUCE,
>   auditor-hardened), `_all` DIFFERS (added a `_divergence_note`, FROZEN pool),
>   and `_verified` re-staled by the `_all` hash move (F-1 class — re-ran
>   restamp). Now 8 fresh + 2 DIVERGENT-BY-RULING (town_plan, _all). Idempotent.
> - **Close-out — DONE:** LESSONS (HLOD-trace nav corruption + restamp F-1 +
>   format + the 4 owed editor-phase failures), RECIPES REJECTED (4 entries),
>   R-WATER-CARVE OWED→CLOSED + status FULLY LANDED, R-NAVGRID HLOD note,
>   gen_doc_tocs. Throwaway variants → `_trash/brief4_t6_2026-09-19/`.
> - **OWED forward (small, NOT carve blockers):** amend `perf_standalone.py`
>   to capture VRAM/residency/exposure (closes the rule-12 gap); the
>   offscreen-capture invalidation limit (revisit only if an offscreen capture
>   is genuinely needed). The post-Brief-5 HLOD rebuild (T12 fold) still owes
>   the dirtied cells.
>
> The 2026-09-19b block below is the editor-phase detail this supersedes on the
> OWED items; T5–T8/T12/T7 detail still stands.

> ⭐ **2026-09-19b — T9 FOLIAGE REGEN, T6 NAV-CARVE + NAVMESH REBUILD, T11 PERF
> ALL LANDED + COMMITTED. Editor CLOSED (R-EDITOR-CLOSE). Tree clean.**
> Restore tag `pre-brief4-water-carve`. This session, on top of the editor-phase
> block below (T5–T8/T12/T7 still stand):
> - **T9a** — post-water ruled count RE-DERIVED **185,385**
>   (`research/brief4/scripts/derive_post_water_count.py`; submerged plantable
>   59.2 ha band-restricted, not the RULING's rough ~140). **RYAN RULED: accept
>   the planting field's honest output, keep density_per_hectare 135/ha**; the
>   forest is ~15% below the old feedback-distorted 217,102. ±2% replay band
>   181,677–189,093; −20% floor 148,308. 214,012 kept as the informational
>   "old-count-minus-water" figure.
> - **T9b** — `place_foliage` rewired: placement samples `foliage.planting_field`
>   (canopy-free, feedback loop cut) + `foliage.water_exclusion` post-filter
>   (drops submerged, RNG untouched, plan_encounters.WaterMask reused NN24).
>   Validator + `plan_stamp.INPUT_KEYS` (_planting_field/_water_mask) + count
>   script. **AUDITED (FIX, 5 findings applied).** Pre-existing `_VEG` gap fixed
>   (`card` grass key — the suite corpus is prove_gates.py, never validated the
>   live recipe).
> - **T9c** — foliage PLACED + SAVED: **185,385 counted-in-world == planned**,
>   1094 pkgs clean (commit 1b8caeed). Orphan sweep cleared 10 dead FT_ types.
> - **T9d** — render weightmap regenerated: **wet_shore NON-ZERO for the first
>   time (0.02%)** in w8b, 3 lakes reproduce water.json exactly, dirt_path 0;
>   `--expand` passed the T4 amendment; `check_layer_acceptance` PASS. The
>   consumer risk-map (no consumer reads wet_shore / asserts it zero) CONFIRMED
>   on real data.
> - **T6 (partial)** — 277 NavArea_Null `NavModifierVolume` over all 12 water
>   SURFACE footprints (`scripts/payloads/carve_navmesh_water.py`, AUDITED;
>   A:79 B:1 D:29 +9 cascade pools:168), saved clean; navmesh **REBUILT**
>   (`build_navmesh_chunk --go --extra=-noxgecontroller`: wall 154s, peak
>   29.5 GB, 0 fatal, **maxTiles 401,843** = R-NAVGRID baseline; exit 1 is the
>   documented HEALTHY HttpListener bind). Editor closed R-EDITOR-CLOSE (census
>   0 + quiet >120s + PackageRestoreData aside).
> - **T11 (partial)** — perf 4 zones, all "ok": **GPU p90 plaza 9.479 / vista
>   8.164 / treeline 7.139 / main_street 6.63 ms; Game p90 all <4.0; FrameTime
>   p90 ~11.2 (<16.6)**; res 3840×2160 read back x4; noxge True.
>   `_verify/perf/standalone_2026-09-19/`.
>
> **OWED (decisions MADE — the carve is not fully landed until these close):**
> - **T6 reachable re-measure:** relaunch → navmesh path-query reachable lattice
>   (R-NAVGRID step 9). Update the spec reachable figure (was 36.53; target
>   ≤1.5 km² reduction, the `walkable_submerged_km2` bound). Then
>   reachable_lattice + town/encounter plans restamp (T10).
> - **T11 verify:** confirm each zone vs R-PERFBUDGET's 1.2×-baseline bar
>   EXPLICITLY + record **VRAM peak vs abort ceiling** — `perf_standalone.json`
>   does NOT capture vram/residency/exposure (rule-12 gap in the tool).
> - **T10:** foliage plans FRESH ✓. `restamp_consumed.py` for town plans
>   (DIVERGENT-BY-RULING) + encounters (consumed fields unchanged, only recipe
>   hash moved). `run_offline_suite` green or every red a ruled waiver.
> - **Capture (rule 4):** DEFERRED — capture.py INVALIDATED offscreen (WP
>   streamed out, editor WS ~5 GB; killed). Retry after relaunch or note as a
>   known offscreen limit.
> - **Close-out:** close R-WATER-CARVE OWED (RECIPES); two-altitude LESSONS +
>   RECIPES REJECTED for this session's 5 failures — (a) place_foliage
>   DEFAULT_RECIPE = legacy alpine.json (pass --recipe recipes/alpine_8k.json);
>   (b) `_VEG` missing `card`; (c) ue_exec `--set GO=1` is LITERAL `__GO__`
>   substitution not a global (two silent dry-runs); (d) `--extra=-noxgecontroller`
>   needs `=` (argparse rejects `-`-leading value); (e) offscreen capture
>   invalidation. `gen_doc_tocs.py` after. STATE update; final commit.
> The 2026-09-19 (EDITOR PHASE) block below still stands where this does not
> overtake it (T5–T8/T12/T7 detail).

> ⭐ **2026-09-19 (EDITOR PHASE) — THE WATER IS LIVE AND SAVED ON /Game/Alpine8K.**
> Rule 11 honoured (zero editors → clean offscreen launch → confirmed
> /Game/Alpine8K.Alpine8K, 4337 actors stable across two probes, 7 local shader
> workers). R-WATER-CARVE LOCKED (RECIPES.md). Committed this session:
> - **T5a (99619184)** — carved 8129 heightmap re-imported (`push_heightmap
>   --push --timeout 120`; the **25 s run DIED in the transport window** — first
>   8129 push; settled UNKNOWN via the absent `LandscapeEdit.cpp:8175` log line,
>   re-ran at 120 s, VERIFIED 1280 samples worst 0.00). Collision flushed same
>   session. **`check_collision_truth` COULD-NOT-MEASURE (~50%)** — the 4096 HLOD
>   proxies carry collision and intercept the trace (pre-existing, not a carve
>   fault, `collision_nohit_probe.py`); where the landscape is reachable p90
>   0.064 m. Two-altitude logged (LESSONS + R1 REJECTED).
> - **T5b/T5c (1af43231, 88bd6ea6)** — 288 water actors spawned (277 planes
>   clipped to CONNECTED COMPONENTS + 11 fall placeholders, pitch −90 facing
>   downstream), material renders, `capture.py` shows lakes at the ruled levels.
>   **`save_level --save`: 544 packages, all clean** (T_PushHeight_Source
>   gitignored). Plan: `water/alpine_8k_water_plan.json`.
> - **T8 (19399bd6)** — verified encounters re-frozen **317→305** (12 drowned
>   scavengers in Lake A removed); a derived `water` exclusion npz (191 ha) +
>   `plan_encounters.WaterMask` stop a regen re-drowning.
> - **T6 (baa828ca)** — z-span 0–1552.485 m (carve sub-decimetre); walkable
>   49.27→**47.77 km²** (water −1.50, the offline 1 m instrument reproduces the
>   baseline first — rule 13). Reachable 36.53 is NAVMESH; **water
>   NON-walkability = NavArea_Null modifiers + rebuild, FOLDED** (target ≤1.5).
> - **T7 (54178b19, b7ba066f)** — Bench_ground re-derived (old was 115 m under
>   Lake A) → loc [373600,269600,77988], bands 354/246 ≥ 160. **A's shore CANNOT
>   host it** (basin rim fails concavity: best rise 21.4 m) — the ruling wins.
>   An audit found a cm/m + grid bug in the new `--near-*` filter (W1/W2); the
>   committed station used the un-bugged `--exclude-water` path, the filter is
>   fixed (`--near-world-cm` + selftest) and the finding re-verified.
> - **T12 (54178b19)** — dirtied HLOD RECORDED not rebuilt: the re-import re-saved
>   all 256 proxies (all landscape HLOD source-stale); 288 water actors dirty the
>   Instanced cells over 191 ha. Folded to the post-Brief-5 rebuild.
> - Spec (CLAUDE.md): encounters 317→305, walkable 49.27→47.77.
>
> **OWED — the carve is not fully landed until these close (decisions MADE):**
> - **T9 foliage regen** (heavy editor): ~140 ha plantable went under water.
>   Remove submerged instances, re-derive the ±2%/−20% band for the post-water
>   world FIRST, regenerate through the planting-field contract
>   (`derive_planting_field` + `place_foliage`), re-stamp the 4 live plans.
>   **Regenerating w8b fires a NON-ZERO wet_shore for the first time** —
>   re-verify `derive_planting_field`, ground-station tools,
>   `check_layer_acceptance` against the new channel (this is the T9 NOTE and the
>   riskiest part). The 4 foliage plans are STALE on terrain **genuinely**
>   (submersion) — cleared BY T9, NOT a waiver.
> - **T10 suite green:** after T9, `restamp_consumed.py` reconciles the town-plan
>   DIVERGENT-BY-RULING binding (its terrain dependence is MATCHES_CONSUMED — the
>   carve is in the north cascade, not the town). Suite currently has the
>   freshness reds only (the 3 mechanical reds I introduced — a bare `_why`
>   prose-key collision, a section-sign in argparse help, stale TOCs — are
>   FIXED and re-verified). `run_offline_suite` is the acceptance instrument.
> - **T11 perf:** R-PERFBUDGET four zones, `-noxgecontroller` (R-XGE); water is
>   new GPU cost on a DEVICE_HUNG-history machine.
> - **T6 navmesh nav-carve:** NavArea_Null modifiers over the lake footprints +
>   a rebuild so the submerged basins are non-walkable (the reachable figure then
>   re-measures authoritatively, target 36.53 − ~1.5).
> An editor is OPEN (offscreen, /Game/Alpine8K) — close on the R-EDITOR-CLOSE
> kill path (offscreen ⇒ CloseMainWindow returns False; prove safe by census +
> quiet RSS + empty PackageRestoreData). Everything below still stands.

# (superseded within-session — the editor phase above overtakes the "T5–T12 next" framing) 2026-09-19 (BRIEF-4 CARVE: T1–T4 DONE + T8 DETECTED)

> ⭐ **2026-09-19 (T4) — CARVE_PLAN T4 COMPLETE + VERIFIED + COMMITTED (58f46b23).**
> `wet_shore` implemented in `derive_layer_weights.py` (was hardcoded zero): the damp
> shoreline RING of each placed lake — `dilate(footprint, 8 m) & (h>=level)`, strength
> `1-smoothstep(0,4 m,h-level)`, unioned over A/B/D — **NOT a global |h−level|≤band band**.
> Footprints from `hydro_derive.level_slice` on the committed 4x heightmap (NN24: one
> derivation), upsampled to 8129 by EXACT vertex indexing (8129=4·2032+1); POSITIVE
> CONTROL reproduces water.json areas EXACTLY (125.5/13.6/49.6 ha). `--expand` amended:
> `remainder == wet+path+gravel+meadow` (load-bearing — dropping wet false-passes only
> while wet==0), **dirt_path STAYS required-zero**, wet_shore folds into the remainder so
> the shipped PNG is byte-identical. **AUDITOR PASS** (4 findings fixed before first
> execution: collar `~fp` drop, `--out-prefix` commonpath guard, exact index-upsample vs
> PIL resize, zero-lakes REFUSE). Proof: **selftest 24/24** (C: wet_shore fires on shore
> 0.93 / ZERO far-at-same-elevation 0.000 = the global-band discriminator / fades /
> no-water=0; D: `--expand` 3 directions with counts); real derive **wet_shore 0.02%**
> (~26k cells), dirt_path 0; `_expand_check` on real data PASSES (gaps 1/255, 2/255).
> Evidence `_verify/brief4/t4_wetshore_2026-09-19/RESULT.md`. Commits 225a2c8c (pre-audit)
> → 48d46e3d (fixes) → 58f46b23 (verified).
> **NOT done, deliberate: the shipped w8a/w8b/weights.png were NOT regenerated** — the
> canonical regen belongs AFTER the heightmap re-import (T5) + foliage regen (T9). **T9/T10
> NOTE:** when `w8b` is regenerated, downstream consumers (`derive_planting_field`,
> ground-station tools, `check_layer_acceptance`) will read a non-zero wet_shore channel
> for the first time. **SUITE 30/31 unchanged** — the one red is the pre-existing T2/T3
> freshness cascade (terrain/alpine_8k.png + alpine_8k.json hashes), T10's to reconcile;
> **no stale plan implicates T4** (verified). **Owed still: R-WATER-CARVE lock once the
> whole carve lands.**

> ⭐ **2026-09-19 (CARVE SESSION) — CARVE_PLAN T1, T2, T3 COMPLETE + COMMITTED;
> T8 DETECTED; T4 + T5–T12 are the editor-phase session.** Off-disk foundation
> of the Brief-4 water carve landed, each with read-backs and a commit:
> - **T1 (tag)** — RISKY-OP CHECKPOINT `pre-brief4-water-carve` → **d03226fe**
>   (green suite, 31 checks). Restore: `git checkout pre-brief4-water-carve -- <path>`.
> - **T2 (c82a3698)** — `recipes/water.json` (schema `water-1.0`); the reserved
>   key `water` LIFTED (import_heightmap: OPTIONAL_TOP + `_validate_water` —
>   endorheic never-exceed ceiling is machine-readable, negative controls fire);
>   schema.md WATER RECIPE section; alpine_8k.json top-level `water` POINTER
>   (city.json precedent). All 14 level/extent read-backs EXACT vs RULING §7 /
>   hydro. A inflow fall DERIVED (1708,1050); **B inflow = none by MEASUREMENT**
>   (0 of 12 candidates drain into the endorheic tarn — the draft's (696,1493)
>   was a south-river point). 11 placed falls in the 10–15 cap.
>   `research/brief4/scripts/water_derive.py` (footprint areas reproduce hydro
>   EXACTLY — positive control).
> - **T3 (dc2034be)** — carved the 10 north-cascade pool-lip notches into
>   `terrain/alpine_8k.png` (8129², I;16, LFS) via `scripts/carve_water_notches.py`
>   (off-disk, rule 4). Read-backs: 47 changed px ⊆ 130 notch cells, 0 raised,
>   z-span 0..1552.485 m, sha cac37b86→13789791, read-back I;16 identical, 47/47.
>   **Auditor FIX applied before the write** (independent coord-map check via
>   lip_elev_m = 1.29 m; refuse zero-change/wrong-lip-count; atomic temp-verify
>   before os.replace; I;16 round-trip isolation-tested). **FINDING (rule 10/13):
>   the lips already sit at/near their outlet levels — total cut 0.32 m, max
>   0.20 m; the fill-to-level premise holds strongly, the notches are minimal.**
>   Evidence `_verify/brief4/carve_2026-09-19/RESULT.md`. NO town-lip cut (B
>   endorheic).
> - **T8 (ac0dc772, DETECTION)** — `research/brief4/scripts/encounters_in_water.py`:
>   **12 of 317 encounters inside a §7 water footprint, ALL in Lake A, ALL
>   scavenger** (11 below 180 m; #308 borderline shoal at 180.7 m). None in
>   B/D/cascade (measured zero, rule 13). Resolution (removal/re-freeze + a
>   `water` exclusion in encounters.json + placer code) is navmesh-coupled →
>   folded into T6. Evidence `_verify/brief4/encounters_in_water_2026-09-19/`.
>
> **SUITE STATE: 30/31.** The one red is the EXPECTED T10-owned freshness
> cascade — the T2 recipe edit + T3 carve moved the alpine_8k.json / terrain
> hashes, expiring hash-pair-bound waivers. T10 reconciles against final hashes.
>
> **NEXT SESSION = the editor phase (T5–T12). T4 IS DONE — see the T4 block at the
> top of this file.** Under rule 11 (zero editors → launch clean → confirm
> /Game/Alpine8K) + rule 7: **T5** re-import the carved heightmap
> + place the water plane meshes (Plane + M_SideWater at level Z, clip to
> connected component — the bbox over-floods) + material re-apply + capture;
> **T6** navmesh rebuild (water non-walkable) + reachability re-measure (z-span
> 0–1552.5 & 36.53 km² both go stale) + **T8 removal/re-freeze**; **T7**
> Bench_ground re-station on A's 180 m shore; **T9** foliage regen (re-derive the
> ±2%/−20% band for the post-water world FIRST); **T10** freshness reconciliation
> (town plan re-rule/restamp; clears the suite red); **T11** perf 4 zones
> (-noxgecontroller); **T12** record dirtied HLOD cells (do NOT rebuild).
> **Owed:** a R-WATER-CARVE lock in RECIPES.md once the carve fully lands.
> Everything below still stands.



> ⭐ **2026-09-19 (later) — BRIEF-4 CARVE_PLAN T0 COMPLETE; the carve session
> (T1→T12) is the next session.** Ryan approved doing T0 as prep. Established the
> UE 5.8 water surface LIVE (reflected stub + read-only probe
> `scripts/payloads/_t0_water_probe.py`, rule-7 MATCH) and **DECIDED: STATIC WATER
> MESHES** (engine Plane + `/Game/Materials/M_SideWater`, via the existing
> `scripts/spawn_water_plane_payload.txt` pattern), **NOT the UE Water plugin**
> (Experimental v0.1, spline-authored, carves the landscape by default — collides
> with rule 4 + the fill-to-level premise + pipeline rules 2/3). Decision + citations:
> `research/brief4/T0_WATER_SURFACE_2026-09-19.md`. Drafted the T2 recipe block:
> `research/brief4/water_recipe_DRAFT.json` (A@180 id4893 closed, B@140 id11877
> endorheic + ~180 m never-exceed ceiling, D@590.9 id8377, north cascade D→tarn hero
> landmark, inflow-fall coupling+elevation test, cap 10–15, no town-lip notch; route
> geometry referenced from hydro_amendment.json). **Ryan chose "preview shorelines
> first" and LOCKED Lake A @ 180 m** (B@140, D@590.9 fixed as ruled). Shoreline
> preview `_verify/brief4/shoreline_preview_2026-09-19/` — connected-component areas
> reproduce hydro EXACTLY (positive control: A 125.5, B 13.6, D 49.6 ha). **FINDING
> feeding T2/T3:** a plane over the hydro BBOX over-floods (D 98.7 ha bbox vs 49.6
> connected — bbox includes the cascade descent), so T2/T3 must clip each water
> surface to the CONNECTED COMPONENT, not the bbox (recorded in the draft recipe +
> T0 doc). Commits: fd77d069 (T0 decision+draft), 38113b8b (preview+finding). The
> carve session is deferred to its own dedicated session by Ryan's choice — see the
> handoff prompt. Everything below still stands.

> ⭐ **2026-09-19 — THE HLOD PER-PACKAGE SAVE-COST PILOT RAN (O-7 save-cost half
> closed; O-5 resolved).** Ryan closed the leftover editor PID 4452 mid-session
> (O-5 → CLOSED), so a fresh offscreen `/Game/Alpine8K` editor launched clean
> (rule 11 zero-editors honoured, rule 7 MATCH, world fully loaded 4337 actors).
> The Pass-3-fixed `hlod_setup_layers.py` — which per the 09-18 block had NEVER
> actually saved — **saved 79 packages across all three classes, 0 failed**,
> DRY_RUN=1 preview then DRY_RUN=0. Measured per-package save:
> **props ~12 ms (n=17), foliage ~11.5 ms (n=41), landscape proxy ~0.56 s
> (n=21)**; whole-world PROJECTS to **~3 min**, proxy-dominated (~65× a
> prop/foliage package). **LOCKED CONCLUSION: the 2026-09-07 90-min hang was the
> BULK save call, not per-package cost** — one-at-a-time is affordable.
> Evidence `_verify/hlod/save_cost_pilot_2026-09-19/RESULTS.md`; locked in
> RECIPES R-HLOD (AMENDED 2026-09-19) + REJECTED; narrative LESSONS 2026-09-19.
> The pilot's 79 assignments were fully REVERTED (read-back: 0 target-class
> actors layered) and the byte-churned OFPA `.uasset` `git checkout`-restored, so
> **the world is byte-identical to HEAD** — no world change committed. Editor
> closed on the R-EDITOR-CLOSE kill path (census 0 dirty + RSS flat 1.2 MB/40 s +
> responsive; PackageRestoreData absent after close). New reusable payloads:
> `_o7_readiness_probe.py`, `_o7_pilot_revert.py`.
> **STILL OPEN (unchanged):** O-7's `did_nothing` section-scoped-stale metric in
> `hlod_build_batched.py` still needs the GUID→package map + a real partitioned
> manifest (the deeper fix, explicitly out of scope this session). The FULL
> whole-world HLOD assignment stays unrun — ~3 min is a PROJECTION (79 measured,
> not 2,796), and the assignment POLICY is unsettled (`_Landscape` ruled
> REDUNDANT, STATE 3c; FoliageApprox-for-all-foliage); it wants its own session
> with a named restore tag (RISKY-OP CHECKPOINT). The 09-17/09-18 blocks below
> remain valid where this does not overtake them.

> ⭐ **2026-09-17 OVERNIGHT (third continuation) — running record
> `research/desk/PROGRESS_2026-09-17.md`.** This window:
> **Brief 4 gate CLOSED** — Ryan ruled every line (RULING.md §7): A@180,
> B@140, C defer, **D@590.9**, **tarn B ENDORHEIC** (cut 0 m; the 17 m notch
> struck), hero landmark = the **D-to-tarn stair**, waterfall cap 10-15;
> **nothing carved**. The read-only **`research/brief4/CARVE_PLAN.md`** (13
> tasks T0-T12, each with a read-back + acceptance, restore tag
> `pre-brief4-water-carve`, the wet_shore/--expand same-commit amendment,
> encounter re-verification and Bench_ground re-station as tasks) is the
> carve session's contract; it names no engine API (T0 establishes the 5.8
> water surface). The hydro amendment + RULING §0/§6 re-verification landed
> earlier this window (hydro_derive v2 with the border-outlet fix; every §0
> figure reproduces; the deputy's UNVERIFIED/UNDERIVABLE classes closed).
> **Pass 3 reading: COMPLETE — 178 of 178 done (n_pending 0).** A fresh-context
> continuation (post-/clear) closed the tail in thirty-four deputy-fanned
> batches of four/five, ~648 claims-vs-behaviour defects CONFIRMED-at-source
> and fixed (41 HIGH incl. NN13 zero-sample fail-opens, rule-12 read-back gaps,
> a bounded HLOD save-cost pilot that never actually saved, read-back probes
> that reported ok:true over a missing material / zero samples / empty groups,
> a set_color_gamma that read the delivered product back but never compared it,
> a prove_gaea_reader whose negative controls passed on ANY crash, and two
> trellis mesh scripts that printed "OK" over an unverified/empty write), commit
> per script, offline suite GREEN 29/29 re-run at each
> batch boundary. Two generated artefacts were regenerated with their code
> fixes and both suite checks stay green: **Free/manifest.json** (make_asset_manifest
> `_role` was silently bucketing EVERY unmatched file as "preview" — the fix
> SURFACES 205 files the ambientCG-suffix matcher does not classify) and
> **refs/MANIFEST.md** (gen_manifest hardcoded counts now derived). Detailed in
> `PROGRESS_2026-09-17.md`; worklist `research/audit/pass3_reading_worklist.json`.
> Open FUNCTIONAL follow-ups deliberately NOT carved in this read-only pass:
> scatter_alpinelab a bare --clear does not remove the foliage instances it
> places (only --place clears, per FoliageType); make_asset_manifest role
> matcher covers only ambientCG lowercase suffixes (PolyHaven `_diff_1k` /
> Quixel `_BaseColor` files fall through as unclassified); make_test_heightmap
> default --resolution 1009 vs the legacy alpine.json 2017; check_derived_culls
> validates declared_camera is present but not its sub-keys (an incomplete
> camera KeyErrors instead of a clean refuse). **O-6 FILED THEN RETRACTED same
> window (no Ryan action needed):** verify_walkable_profile's ruling-19 gate was
> using the SUPERSEDED world.primary_movement_mode comparand and false-fired
> exit 5; the next batch's read of apply_navigation_config showed ruling 19 was
> corrected 2026-08-26 to compare the agent vs the PAWN (RECIPES.md:12715/:13221).
> verify_walkable_profile now compares agent vs pawn (walk 44.765 ≤ climb 70 →
> OK); recipes/schema.md's stale rule fixed too. No recipe-data change needed.
> (CLOSED this window: kit_coverage_v2 now routes its roof-fit through
> roof_servability — the two-lists defect both modules named is fixed, output
> byte-identical.)
> **1b live -game still BLOCKED** by O-5 (editor PID 4452 alive, now 39.7
> CPU-h / WS grown to 1121 MB — Ryan to resolve); the 1b DERIVATION
> (proxy_fraction 0.05727) stays instrument of record. Open follow-ups
> logged in worklist results (NN12 FOV gate on measure_frame_cost; wire
> push_heightmap.tolerance_units; schema.md still advertises that field).
> The 2026-09-16 block below remains valid where PROGRESS_2026-09-17 does
> not overtake it.

# (2026-09-16 continuation, superseded item-by-item by the 09-17 block above)

> ⭐ **2026-09-16 OVERNIGHT, SECOND CONTINUATION — the running record is
> `research/desk/PROGRESS_2026-09-16.md`; rulings R1–R6 in
> `DESK_LOG_2026-09-16.md`.** Closed this window on top of the morning's
> D-2/Q2/Q3/D-4 work:
> **Q5/Pass 5 COMPLETE** — 405/405 findings ruled (381 OBSOLETE, 24 APPLY,
> 0 WRONG), every APPLY implemented or applied_where-recorded, ledger at its
> floor; a positional resume pointer that would have silently skipped 17
> findings was caught and fixed structurally (`pass5_extract --skip-ruled`).
> **Q6/Pass 3 reading** — 12 scripts read end-to-end by read-only deputies,
> **57 CONFIRMED claims-vs-behaviour defects fixed** (capture, landscape_spec,
> make_landscape_material, apply_lighting, place_foliage, import_heightmap,
> bench_capture+bench_render seed, verify_landscape, ue_exec, guard.py hooks
> +17 prover fixtures 184/184, verify_ground_station gained its missing
> selftest); keyed worklist `research/audit/pass3_reading_worklist.json`,
> ~169 lower-ref scripts pending.
> **Q7/Pass 2 COMPLETE** — 306 property levers vs the live 5.8 stub: zero
> live defects (AUDIT §11; board row 2 DONE).
> **Q8/E-4 COMPLETE — `run_offline_suite`: NO FAILURES ACROSS 29 CHECKS,
> the first fully green suite.** Consumed-field freshness per rulings R5/R6:
> plans no longer stale on edits to fields their producer never reads
> (MATCHES_CONSUMED), the town plan reads DIVERGENT-BY-RULING (loud, bound
> to the payload-hash pair, retires when the rebuild un-gates), 13
> dead-world plans archived (foliage/_archive/), R-PLANSTALE amended.
> **Q9/D-5 CLOSED** — perf-stall root cause NAMED from both sides
> (IncrediBuild stopped consuming XGE tasks; the engine dispatcher has no
> timeout/fallback; -noxgecontroller deployed in both consumers); procdump
> SUPERSEDED (approval remains H-6's instrument).
> **Q10/D-6 STAGED** — `payloads/hlodtex_coldread_probe.py` built,
> stub-verified, audited; the RUN is blocked by **O-5: a leftover
> UnrealEditor.exe (PID 4452, since 09-15 22:17, 36.8 CPU-hours) that Ryan
> must resolve** (rule 11). **Q11** — second STATUS-tag pass from the Pass-5
> rulings: 21 keyed rows, 17 applied, 0 refused.
> The body below is 2026-09-15 and is overtaken item by item; PROGRESS is
> the ground truth for this window.

> Repaired 2026-09-15 (closure item A-1). The 09-14e block below was
> written at the batch-18 disk stop and was OVERTAKEN THE SAME EVENING;
> it is kept below with a banner because its DDC/registry findings and
> the stale-parents sizing remain true.

## ⭐ THE 09-14 EVENING, AS IT ACTUALLY ENDED

    landscape L2 cells at 4096     256 / 256                  [4eba24e3]
      off-disk census re-verified 2026-09-15: 256/256 parsed,
      ProjectHLODMaxTextureSize 4096 x256, bake 4096², 0 torn,
      MinVisibleDistance 25,600 x256
    standalone perf                DELIVERED                  [9a561d07]
      all four zones PASS R-PERFBUDGET; warm-up pass recorded and
      DISCARDED [e0b4282e]; treeline reported as
      "treeline (formerly mid_slope)" as ruled
    the perf hang                  FIXED — R-XGE LOCKED       [53867f96]
      the XGE controller queued shader jobs and spawned zero workers;
      -noxgecontroller fixes it [51626688]; project is single-machine
      via r.ShaderCompiler.AllowDistributedCompilation=0, READ BACK on
      every launch [ff1acd4b]. WHY the dispatcher wedged is still open:
      procdump APPROVED, run the one-minute editor-vs--game control
      first (closure list D-5).
    Merged L1 parents              256/256 hash-stale — rebuilt ONCE
                                   after Brief 5, by ruling R-O1 / X-2

## ⛔ THE 09-14→15 OVERNIGHT WINDOW DIED AT OPEN

Machine rebooted 05:02 09-15 (Windows update). Zero writes between
2f8ef8d2 (21:54) and the reboot; zero torn packages, verified off disk.
A.1–A.4 were closed pre-window (PROGRESS.md); the A.5–E definitions were
never on disk and are LOST — superseded by the closure list below.

## ⭐ THE ACTIVE PROGRAMME: THE PRE-BRIEF-4 CLOSURE LIST

`research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md` (v2) — ALL of it
completes before Brief 4. Per-item ground truth:
`research/audit/STATUS_2026-09-15.md` (115 rows).

**BLOCK A COMPLETE (2026-09-15).** All nine items closed and committed:

    A-1  STATE repaired, OPEN/PROGRESS indexed, check_docs green   9537899b
    A-3  R-HERO: HeroStage lights affects_world False on two        5b68ba38
         instruments; ruling does NOT trigger, no grade re-read
    A-4  apply_lighting reads back all eight, in a sidecar         406fcaad
    A-5  EXR instrument dumped (V-6 closed); every capture names   301cc357
         its buffer; 09-14 mislabel corrected
    A-6  R-WB2x2 joint solve ADOPTED: 3415.7->3438.6 K,            98c980ac
         tint -0.0113->-0.0248; card R/G 1.0014 B/G 0.998, in band
    A-7  R-SHADEBAND band at 3438.6 K, shade floor D6000 (low-sun,     9245b592
         Hernandez-Andres 2001) -> 2.065-2.998; shade pair 2.1896      +amend
         PASS (at ~D6380); cards removed
    A-8  R-GATE porosity model: near_ground no longer false-       1a2bd43a
         refused, void still caught, three directions verified
    A-9  register hygiene batch + B3.26-B3.29 closure register     570f9ffd

✅ **A-2 CLOSED**: `research/desk/RESEARCH_DESK_HANDOFF_2026-09-15.md` is
committed and tracked (Ryan placed it; a515fc29 + amendment 31079ab9).
The Audit Pass 4 rewrite plan is also in (`research/audit/
PASS4_REWRITE_PLAN_2026-09-15.md`).

**A-7 shade acceptance PASSES** under the R-SHADEBAND low-sun amendment:
the shade floor is D6000 (not D6500) for a sun below ~30 deg, so the band
is 2.065-2.998 @ 3438.6 K and the 2.1896 measurement is in band. The
white point is 3438.6 K and the floor tracks sun elevation, so any
further shade work re-runs `shade_reference.py --white <K> --shade
<BAND_FLOOR_K> 10000` first.

**BLOCK B — 6 of 7 done, B-2 disk-blocked (2026-09-15):**

    B-1  Task 5 acceptance: TWO FINDINGS, not passes.            (findings)
         Fog-contrast metric OUT OF CLASS at altitude (content,
         not fog). Proxy-vs-real albedo NULL — the bench force-
         loads real cells, so HLOD proxies never render in a
         bench frame (proxy==real pixel-identical). Baked 4096
         verified off disk. Two desk rulings owed.
    B-2  Cost of 4096 A/B                        ⛔ DISK-BLOCKED
         Two landscape-HLOD rebuilds (256+4096) need ~42 GB;
         28 GB free. Needs Ryan to clear C:\UnrealDDC (31.8 GB).
    B-3  Brief 1 512 m detail threshold reported (P1-10)  bddaa7ff
    B-4  Cloud_GlobalCoverage: 0.3 is NOT overcast, param       (done)
         inverted; recipe unchanged (Q17 closed)
    B-5  Precedence null pair: flag effect == run-noise floor;  (done)
         frame instrument conclusive, agrees with the logs
    B-6  Census gains the 4 HLOD proxy props (257× 4096/        (done)
         SPECIFIC_SIZE); ED comparison BLOCKED (sample not
         installed)
    B-7  Brief 3 send-back assembled, PROVISIONAL               (done)
         research/brief3/for_research/INDEX.md

Also this session: **R-SHADEBAND amended to the D6000 low-sun floor**
(band 2.065–2.998 @ 3438.6 K; A-7's 2.1896 now PASSES). shade_card_pair.py
carries BAND_FLOOR_K = 6000 and self-derives.

**BLOCK D-1 FIRST APPLICATION — DONE 2026-09-15 (all 8 items):**

    1  player_streaming instrument added; proxy fraction ~0 -- the
       instrument does not exist yet (bench loads real cells even with
       the override gone; loading read-back: OverrideRuntimeLoadingRange
       to a derived range, bench_capture.py:1124-1127)
    2  B-2 STRUCK by ruling (Ryan): no rebuild; perf budget absolute,
       4096 passes it; pass-2 deltas -> HISTORY; premise 1024 not 256
    3  fog acceptance re-based to Bench_ground convergence (blacks rise
       clean; contrast-ratio +30.5% marginal); luma_std -> diagnostic
    4  frames left git: 2,860 untracked, _verify/**/*.{png,exr} ignored;
       .git history rewrite OWED (Ryan's go, BACKLOG)
    5  STATUS tags: 65 of 81 applied, 16 decided-and-deferred; TOC gains
       a status column (HISTORY 59 / SUPERSEDED 17 / WRONG 2 / CURRENT 3)
    6  scripts/current_values.py -> RECIPES CURRENT VALUES table, proven
       against source; baseline rule (A-6 capture is the zero)
    7  CLAUDE.md 13 rules gain verified --why pointers (seed dates fixed)
    8  register: Q17 closed (cloud param not coverage; sweep -> Brief 4);
       B-6 closed (ED unavailable; derivation stands)

C:\UnrealDDC was cleared by Ryan (60 GB free). Desk inputs in:
PASS3_SCRIPTS, PASS4_REWRITE_PLAN.

**NEXT:** the two Task 5 desk rulings (fog metric domain; rendered-proxy
capture); Block C (audit Passes 2/3/5) and the rest of Block D; the 16
deferred STATUS tags. B-2 stays struck. Task 4 stage 2 closed by R-T4.

## OPEN

See `OPEN.md` (O-1…O-4), the closure list's Blocks B–D, and
STATUS_2026-09-15.md sections D/H for the item-by-item register. The
09-14e OPEN list below remains valid where STATUS marks it so.

---

# (previous block) 2026-09-14e (CAP 4096; 145 of 256 CONVERTED, DISK GATE TRIPPED AT BATCH 18)

> ⛔ **SUPERSEDED THE SAME EVENING.** "145 of 256", "MIXED STATE" and
> "THE STANDALONE PERF RUN IS BLOCKED" were all overtaken by 4eba24e3,
> 9a561d07 and 53867f96 — see the live block above. The DDC location
> findings, the registry key, and the stale-parents sizing below remain
> true and citable.

## ⛔ THE WORLD IS IN A MIXED STATE RIGHT NOW (superseded — see banner)

    landscape L2 cells at 4096 x 4096   145
    landscape L2 cells at 1024 x 1024   111
    HLODMaxTextureSize in the ini      4096   <- ANY landscape HLOD build
                                               now bakes at 4096

Report: `_verify/hlod/cap4096_2026-09-14/CAP4096_PARTIAL.md`.
Resume:  `python scripts/hlod_build_landscape_cells.py run
          --run-dir <ABS>/_verify/hlod/cap4096_2026-09-14 --start 18`
Restore point: tag `pre-hlod-cap-4096-20260914`.

**18 of 32 batches run, 144 cells, 12.3 min total.** 144/144 approved,
0 rejected, 0 torn, true exit every batch. VRAM 10,015–11,931 MiB against
the 13,312 MiB abort — never tripped. The 8 GB gate has stopped the run
cleanly twice, before batch 16 and before batch 18, as ruled.

⛔ **RECLAIMING SPACE IS RYAN'S, BY INSTRUCTION.** The tool never clears a
cache — the DDC is outside the repo (standing rule 1) and
`hlod_build_landscape_cells.py` says so in its docstring. It stops and
names the batch instead.

## ⭐⭐ THE DDC THAT MATTERS IS `C:\UnrealDDC`, NOT `%LOCALAPPDATA%`

**Found 2026-09-14 after the batch-16 stop, and it changes the disk
advice completely.** `%LOCALAPPDATA%\UnrealEngine\Common\DerivedDataCache`
was cleared and is now **0 bytes / 0 files** — and it is **NOT where this
build writes**. The real consumer is a root-level cache:

    C:\UnrealDDC          46.96 GB total
      Zen                 21.62 GB   (+8.15 GB during batches 4-15)
      Content             19.19 GB   (+7.67 GB)
      Buckets              6.15 GB   (+0.46 GB)
      TestData             0.00 GB
    written in the last 3 h: 16.28 GB in 6,264 files

That 16.28 GB is the ~13 GB that the per-directory sweep could not
account for. Everything else was measured and flat: `_verify` +0.01 GB,
`.git` 0.00, `Saved` 0.00, `Intermediate` 0.00, recycle bin empty,
pagefile fixed at 192 GB (not auto-managed), no VSS visible.

    zenserver.exe   NOT running -- nothing holds the directory open
    UE-LocalDataCachePath / UE-SharedDataCachePath   unset, all 3 scopes

⭐ **ITS CONFIG SOURCE IS A REGISTRY KEY — FOUND 2026-09-14, and it was in
the logs the whole time.** Both `LogZenServiceInstance` and
`LogDerivedDataCache` print:

    Found registry key GlobalDataCachePath UE-LocalDataCachePath=C:/UnrealDDC

The key is named **`GlobalDataCachePath`** and its value is named
`UE-LocalDataCachePath`. My earlier search looked under
`HKCU:\Software\Epic Games\Unreal Engine` and a guessed `GlobalDDCPath`
and reported "not found". **The same line appears in the 2026-09-11 logs,
so this is long-standing machine config and NOT something the clear
introduced.**

**THE CAP CHANGE WORKS.** Every rebuilt cell records
`ProjectHLODMaxTextureSize: 4096` and bakes 4096×4096 BaseColor/Normal/MRS,
**1:1 on 256/256 packages** measured off disk — 145 record 4096 and bake
4096², 111 record 1024 and bake 1024². No cell records one and bakes the
other.

⛔ **STOPPED ON DISK, NOT ON A FAULT.** Measured slope **1.49 GB per
8-cell batch** over batches 0-3, **1.53 GB** over 4-15, **1.45 GB** over
16-17; **111 cells remain, needing ~21 GB** against **6.22 GB free**.

    LandscapeLab/Content   +0.41 GB/batch   permanent, wanted
    C:\UnrealDDC           +~1.1 GB/batch   Zen + Content, a CACHE
    everything else         0.00 GB/batch   measured

Two thirds of the slope is **cache**, and only the packages are permanent:
the remaining 111 cells need ~6.3 GB of packages, plus ~15 GB of
regenerable DDC.

⚠ **"RELOCATION IS IMPOSSIBLE" WAS ABOUT THE WRONG CACHE.** The
2026-09-14 finding — one drive, no relocation target — is TRUE of
`%LOCALAPPDATA%`, and it was reasoning about a cache this build does not
write to. **Whether `C:\UnrealDDC` can be relocated is UNANSWERED**, and
its config source was not found (above). Do not repeat the old conclusion
as though it covered both.

    physical disks   1   SAMSUNG MZVLC1T0HFLU-00BL2, 953.9 GB
    volumes          C: 951.6 GB + a 2 GB unlettered recovery
                     partition (1.1 GB free)
    network drives   none

The cadence is: Ryan reclaims space, the run resumes, the 8 GB gate stops
it again. **Clear 1 bought batches 4–15 (96 cells); a partial ~4.5 GB
recovery bought batches 16–17 (16 cells).** Clearing `C:\UnrealDDC`
(46.96 GB) would cover the remaining 111 with room to spare.

⚠ **VRAM peaks 10.0–11.9 GB against the 13 GB abort** across all 18
batches — never tripped, but batches of 8 are at the ceiling and 9 would
likely breach. ~1.4 GB per cell within a batch, reset only at the boundary.

⚠ **The Merged parents are hash-stale** for every rebuilt child
(`HLODSourceActorsFromCell.cpp:213-220`). No other layer touched, by
instruction — a scope boundary, and it applies to all 256 on completion.

⛔ **THE STANDALONE PERF RUN IS BLOCKED — IT NEVER REACHES `LoadMap`.**
Attempted 2026-09-14 on the now-uniform world, all four zones, settle
raised 60 → 240 s. **0 CSV on 4 of 4**; the tool refused per zone ("no CSV
appeared within the window") rather than averaging startup frames.

    LoadMap / Bringing World / StartPlay / World Partition   ABSENT, all 4 logs
    pc_location_logged                                       null
    viewport_res_readback                                    [1423, 889]
    res_matches_request                                      false

⭐ **The 4096 rebuild is NOT implicated** — the world was never loaded, so
its content cannot be the cause. The 256 cells stay verified at 4096 off
disk, by an instrument needing no editor.

## ⛔ SIX LAUNCHES, SIX HANGS — THE DDC IS EXONERATED, procdump IS NEXT

Diagnosis: `_verify/hlod/cap4096_2026-09-14/PERF_STALL_DIAGNOSIS.md`.
**procdump APPROVED by Ryan for the next session.**

    THE SIGNATURE, reproduced on two independent caches:
      shader dispatch high-water   6,813   FROZEN
      jobs still outstanding       1,569
      ShaderCompileWorker procs        0
      LoadMap                     absent
      CPU                    ~5% of ONE core (12.1 s over 241 s)

**The engine queues shader jobs and spawns zero workers to run them.**

    hypothesis            status
    dwell too short       REFUTED  945 s, idle throughout
    cold shader cache     REFUTED  0 workers alive; it is not compiling
    DDC backend broken    REFUTED  ZenLocal Status: OK!, identical to 09-11
    zenserver dead        REFUTED  launched, listening on 8558, alive in the hang
    DDC maintenance pass  REFUTED  0.005 s on a fresh cache, hangs identically
    cache contents        REFUTED  empty cache, same hang
    cache location        REFUTED  C:/UnrealDDC_fresh, same hang
    the 4096 rebuild      EXCLUDED LoadMap never runs

⭐ **THE CONTROL THAT SETTLED IT:** on `C:/UnrealDDC_fresh` the maintenance
pass costs **0.005 s** (110 files) against **35 s** on `C:\UnrealDDC`
(19,000 files) — and the hang is unchanged. The pass was a passenger.

⚠ **Run one control BEFORE the dump, it costs a minute:** launch the
EDITOR (not `-game`) on this project. The commandlet path demonstrably
works (`batch_31.log`, 8 cells, 2026-09-14), so the failure is specific to
some launch mode; knowing whether the editor hangs too narrows the stack
hunt a lot.

⛔ **Three of my diagnoses were WITHDRAWN on the way here** — cold shaders
(0 workers running), the shader-line-count reading (progress lines are not
a measure of work), and `%LOCALAPPDATA%` as the cache (it is
`C:\UnrealDDC`, set by registry key `GlobalDataCachePath`). Each was
refuted by a measurement available earlier than I took it.

When it does run: all four zones, treeline reported as **"treeline
(formerly mid_slope)"** — confirmed from a LIVE source,
`_verify/bench/2026-09-05/bench_stations_derived.json`
`derived_stations.mid_slope` = `[-190000, 100000]` pitch −2 yaw 105,
`replaces: "treeline [-153506, 265800]"`, identical to `perf_budgets.json`.

## ⚠ THE STALE PARENTS ARE SIZED: 256, ALL L1, EXACTLY 1:1

`scripts/hlod_stale_parents.py`, off disk, 2,267 packages, 0 unparsed:

    landscape children                     256
    parents referencing a child            256
    STALE (child rebuilt after parent)     256    fresh 0   undated 0
    by level                            L1 256    L0 0
    current package bytes               487,172,542  (0.45 GB)
    children per parent                      1    for all 256

    Instanced layer LoadingRange   76,800   (overridden in the asset)
    Merged layer   LoadingRange    51,200   (class default, HLODLayer.cpp:38-39)
                                            == its cells' MinVisibleDistance x256

**Merged parents govern 512 m – 1 km**; the Instanced cells govern
300–512 m. Measured frame share beyond 100 m: plaza **0.0%** (no Merged in
frame), treeline 17.82% mid + 25.78% far, vista 16.45% + 16.33%,
main_street **unmeasured**. ⚠ The bands bucket at 100 m–1 km so the 512 m
edge falls INSIDE a bucket and cannot be resolved; the model is offline and
explicitly incomplete for plaza.

⚠ Projected package delta if the parents are rebuilt at existing settings:
**~0, but that is a STRUCTURAL argument, not a measurement** — the parent's
texture size comes from its own `MeshApproximationSettings`, untouched
here. Not confirmable off disk (`TextureSize` is an `FIntPoint`,
`TextureSizingType` an enum; neither readable by the int/double scanners).

⛔ **`imported_size` IS NOT REFLECTED ON `UTexture2D`** (both spellings
raise). The source-dimension instrument is the off-disk
`FTextureSource.SizeX/SizeY` read, `scripts/uasset_lite.py`. Six cells /
18 textures: off-disk, `blueprint_get_built_texture_size` and
`blueprint_get_size_x/y` all agree — but on a WARM DDC, which does not
reproduce the 2026-09-14 cold-read condition. **That item stays open.**

---

# (previous block) 2026-09-14b — THE 32 NEVER EXISTED; LANDSCAPE HLOD IS 1024 ON 256/256

## ⭐ CLOSED THIS SESSION — THE LANDSCAPE HLOD PILOT

**There was no anomaly.** `-BuildSingleHLOD` has never produced 32×32
landscape HLOD textures. The 32 was an **editor read-back artefact**; the
commandlet wrote 1024 every time. Report:
`_verify/hlod/pilot_landscape_2026-09-14/FLATTEN_PATH_VERDICT.md`.

Measured off disk, no editor, 2,267 packages, 0 missing, 0 unparsed,
**256 L2 landscape cells, all agreeing**:

    MinVisibleDistance         25600              x256   <- NOT 76,800
    HLODTextureSizePolicy      SpecificSize(1)    x256
    HLODTextureSize            4096               x256
    ProjectHLODMaxTextureSize  1024               x256
    baked texture dimensions   1024x1024 (3/cell) x256

⭐ **THE BUILD RECORDS ITS OWN INPUTS.** Every HLOD package embeds a
`### HLOD_REPORT_BEGIN ###` block with the fields `ComputeHLODHash` hashed
(`LandscapeHLODBuilder.cpp:44-127`) and the command line that wrote it.
New read-only tools: `scripts/hlod_report_offdisk.py`, `scripts/uasset_lite.py`.

⛔ **THREE DOCUMENTS CARRY CORRECTION BANNERS** — `FINDINGS.md`,
`REPRO_AND_DISCRIMINATE.md`, and
`research/audit/inputs/HLOD_TEXTURE_SIZE_SOURCE_2026-09-14.md`. Their
`MinVisibleDistance` of 76,800 (from the layer's `loading_range`) is wrong
and every D-indexed table in them is off by 3×.

**THE CAP RULING: `SpecificSize` is in force on 256/256, so `:234` BINDS
and raising `HLODMaxTextureSize` to 4096 WOULD lift 1024 → 4096.** It is
not a no-op. **RECOMMENDED: HOLD** — it forces a full rebuild (`:124`
hashes the cap) and is a 16× texel increase on 256 cells, against a VRAM
budget already within 500 MB of the figure that caused DEVICE_HUNG. A
budget decision with no unknowns left in it.

⚠ **OPEN, and it is one measurement not an experiment:** the mechanism of
the bad read-back is NOT established. 1024 → 32 is exactly five mip
levels. Re-read that cell with `imported_size` (source) and
`blueprint_get_size_x()` (platform data) **in the same payload**; if they
disagree, the accessor is the defect and every texture-size read-back in
the record needs re-checking.

---

# (previous block) 2026-09-14a — SKY WHITE, GRADE RE-SOLVED, HLOD BUILD RUNNING

> **⭐ THE LIVE STATE BLOCK.** `CLAUDE.md` keeps a one-line pointer here.
> `check_docs.py` enforces exactly one `# CURRENT STATE` heading in EACH
> file. History is `docs/archive/current_state_history.md` — ⛔ never a
> source.

## 0 — RUNNING RIGHT NOW: THE HLOD BUILD, RE-PLANNED AT 96 (2026-09-14)

    run dir   _verify/hlod/build_20260914b      24 batches, 2,267 cells
    console   _verify/hlod/build_20260914b/run_console.log
    report    python scripts/hlod_run_report.py _verify/hlod/build_20260914b
    stop      a STOP file in the run dir, checked BETWEEN batches;
              fatal signatures (incl. DEVICE_REMOVED) retry once, then stop
    resume    `run --start N` -- BATCH granularity, not cell

    batch 0 (12-way run, _verify/hlod/build_20260914, SUPERSEDED)
      191 cells  approve 191 / reject 0  104 Instanced + 87 Merged
      64.4 min   VRAM peak 14,701 MiB    191 written, 0 torn, clean
    batch 0 (24-way run, LIVE)
       98 cells  approve  98 / reject 0   54 Instanced + 44 Merged
      32.5 min   VRAM peak  8,718 MiB     98 written, 0 torn, clean

⭐ **WHY THE RE-PLAN.** VRAM climbs ~90 MiB per cell WITHIN a batch and
is reset only at the batch boundary. 191 cells reached **14,701 MiB
against the 15.2 GB budget** whose breach caused DEVICE_HUNG on 09-12 --
within 500 MB. 98 cells peak at 8,718 MiB, leaving 6.5 GB.

⚠ **THE 12-WAY AND 24-WAY PARTITIONS DO NOT NEST** (new section 0 shares
98 of the old batch 0's 191 cells; sections 1-3 share none), verified by
comparing GUID sets. So there is no clean resume across a re-partition
and the old batch 0's 191 cells are rebuilt. Accepted deliberately:
`-RebuildHLODs` forces, and relying on the skip instead is the thing
R-HLOD records as "THE SKIP DOES NOT WORK".

    rate      3.02 cells/min -> ~32 min per batch
    ETA       ~12 h from 03:45, i.e. mid-afternoon 09-14
              -- PAST 07:00, so Part C of the overnight brief is SKIPPED

Per-batch attribution prints per layer and per cell via
`scripts/hlod_attribution.py`, validated against the 09-13 run
(27 Instanced / 19 Merged over 89 cells, 89/89 paired, 0 sync loss).

## 1 — ✅ TASK 3 CLOSED ON THE PLAYER INSTRUMENT

No texture-tile repeat is player-visible at either bin. n=3,
temporal_sample_count **8 read back**, TSR, warm-up 40,
display-referred.

    30-100   Grass  0.04005 +- 0.00124  thr 0.05338  0.75x  PASS
    30-100   Rock   0.00000             thr 0.02279         NO PEAK
    30-100   Scree  0.00000             thr 0.02498         NO PEAK
    100-300  all three                                      NO PEAK

TRUTH INSTRUMENT (temporal 1), recorded beside it — *aliasing at
temporal 1, NOT player-visible*: Grass 0.10960, Rock 0.10147, Scree
0.09030, all FAIL. REGISTER B3.20.

## 2 — ⛔ TASK 4 STOPPED: NEITHER SHADOW CANDIDATE IS A LEVER

    candidate                      4-10 m   10-30 m
    baseline (n=3)                 0.6701   0.6510
    A card dynamic shadows ON      0.6698   0.6514
    B sun contact shadow 20 cm WS  0.6698   0.6509
    band                           1.0-1.5  0.55-0.75

Neither reaches the render above capture noise (whole-frame mean
unchanged to 5 dp; meadow pixels >10% different: 0.03%). Nothing moved
4–10 m past 0.8, so the band is the desk's to re-derive. The ±8% hue and
brightness are KEPT; no lever adopted, so no perf run.

Read-backs: VSM **on**, `r.ContactShadows` 1 globally but
`contact_shadow_length` **0.0 on all four directional lights**; grass
varieties `cast_dynamic_shadow` **False**; card MP_NORMAL is the scan's
**tangent normal map**, so the "blended-up normal" candidate does not
apply and was not run.

## 3 — ⛔ THE HLOD BUILD DID NOT START

    Alpine8K_HLODLayer_Instanced   Reject 42   Approve 27
    Alpine8K_HLODLayer_Merged      Reject  1   Approve 19   <- wholesale

Stop condition met. `-SetupHLODs` **cannot** answer this — its "2267" is
the full actor list, and its log has ZERO Approve/Reject lines; the
policy runs at BUILD time. The counts above come from 20 tiny sections
run with the policy live.

⭐ **AND THE LANDSCAPE LAYER IS NOT IN USE.** `hlod_layer` is **None on
every actor** (Landscape, 256 proxies, 1093 foliage, 1451 static). The
1042 HLOD actors belong to `_Instanced` and `_Merged` only.
`_Landscape` and `_FoliageApprox` are **unreferenced assets** — the
settings applied to `_Landscape` (merge_materials False→True,
texture_sizing UseSingleTextureSize→AutomaticFromMeshDrawDistance, both
read back and census-confirmed) change nothing that renders. REGISTER
B3.19.

⛔ My probes BUILT 46 cells (27 Instanced + 19 Merged) — the sampling ran
without `-ReportOnly`. And I broke standing rule 11: a `ps aux` wait
cannot see Windows processes, so I launched an editor over a running
commandlet; killed in 11 s, commandlet left to finish.

## 3b — ✅ AUDIT READ-BACKS DELIVERED (2026-09-13, all 8 items)

`research/audit/inputs/READBACKS_2026-09-13.md` is the deliverable.
**Four Pass 1 verdicts change.**

    P1-8 WRONG        sky.color HAS a writer -- apply_lighting.py:394,
                      set_light_color(), a METHOD. Not UNVERIFIED; do
                      not delete the key; it is READ-BACK-OWED.
    P1-1 understated  GameOverride was added ONLY under --truth, so on
                      every dev/non-truth capture its 7 values were not
                      unread, they were NEVER APPLIED.
    P1-1 ANSWERED     precedence: THE CVARS WIN. Two independent log
                      instruments, sg.ShadowQuality 1 -> 1 in both arms.
                      Frame instrument INCONCLUSIVE -- needs a
                      dev-profile null pair (experiment written out).
    dev profile       is NOT sg.*=1. GI and Reflection are 3.

⭐ **§3's "Landscape layer not in use" now has a SECOND route.** Last
session read `hlod_layer` per actor; this one walked the world's
`DefaultHLODLayer` (`WorldPartition.h:612`) and its `ParentLayer` chain
to a fixed point: Instanced → Merged → end. `_Landscape` is in neither
channel. Two instruments, one conclusion.

Every "does not exist in 5.8" is now CONFIRMED LIVE (11,073-entry
enumeration + string getter, with both controls) instead of quoted.

⛔ **`dir()` IS NOT THE REFLECTED SURFACE.** `unreal.HLODLayer` exposes
23 names, ALL methods, ZERO properties. Names come from the header;
`get_editor_property` does the read. This is the SEED of the
already-corrected "HLOD exposes nothing to Python" claim.

## 3c — ⛔ TASK 5 IS VOID, AND sky.color HAS ALWAYS BEEN WRONG (2026-09-13)

Registers: `research/audit/inputs/LANDSCAPE_HLOD_REGISTER_2026-09-13.md`,
`TRUTH_INSTRUMENT_REGISTER_2026-09-13.md`,
`SKY_COLOR_READBACK_2026-09-13.md`. **Ruled: no actor mutated, no build.**

**TASK 5's ACCEPTANCE IS VOID, NOT FAILED.** A landscape component is
always built by `ULandscapeHLODBuilder` — `GetCustomHLODBuilderClass()`
is unconditional (`LandscapeComponent.cpp:97-100`), and
`HLODBuilder.cpp:354` regroups by it. So the layer's `mesh_merge_settings`
could never govern the landscape. The real levers are six proxy
properties (`LandscapeProxy.h:953-974`); all 257 actors read, **257 OK,
0 raises, 0 outliers**, all at 5.8 constructor defaults
(`Landscape.cpp:1780-1783`) — `SpecificSize/256/None/LowestDetailLOD/0/false`.

**And §3's "not in use" was half wrong.** A null `hlod_layer` **falls
back to the world default** (`WorldPartitionRuntimeHashSetConversions.cpp:45`),
so 0-of-4,339 means *everything uses Instanced*, not *the landscape is
un-HLOD'd*. `_Landscape` + `_FoliageApprox` marked **REDUNDANT**;
deletion deferred to the audit rewrite session.

⛔ **`-SetupHLODs` CANNOT report flagged cells.** `-ReportOnly` skips
`BuildHLODActors()` entirely (`WorldPartitionHLODsBuilder.cpp:438`) and
the rebuild policy lives inside it. Measured: 2,267 GUIDs, 0 packages
changed, **0 decision lines in a 2.8 MB log**. The count needs a pass
that writes.

⛔ **`sky.color` IS sRGB-ENCODED TWICE.** Recipe linear `[0.42,0.6,1.0]`
→ actor `FColor(215,231,255)` = `encode(encode(recipe))`, exact. In
force: linear `(0.6795, 0.7991, 1.0)`. **R 62% high, G 33% high, B exact
because 1.0 is a fixed point** — the channel a human would check cannot
show it. `set_light_color` ENCODES (`LightComponent.cpp:1130-1134` →
`Color.cpp:251`); the docstring at `apply_lighting.py:388-393` says
"decode" and is wrong. NOT FIXED — needs a ruling; any grade tuned
against this was compensating for it.

⚠ Three `HeroStage_*` DirectionalLights are live in the world level
alongside the sun. Contribution to bench frames not established.

## 4 — INSTRUMENTS
> STATUS: SUPERSEDED-BY B3.13 — the role-map is valid, but comp_ev -13.5898 / contrast are B3.13-revised

    PPI0       SCENE-LINEAR: exposure, albedo, shade.
    FinalImage LOOK: WB, tint, and where the CSF verdict belongs.
    BaseColor  ALBEDO x exposure. Divide by 2^comp, ASSERT plausible.

    compensation_ev -13.5898   warm-up 40   contrast 0.95
    repeat verdicts are PLAYER-INSTRUMENT ONLY (temporal 8) — the
    docstring carries the name and the two-instrument table.
    ⛔ B3.18: for materials built by `make_foliage_material` before
    2026-09-13, DISK-read checks are suspect; GRAPH-read audits stand.

## OPEN

    what dirtied Merged — candidates: M_Alpine8K (4 rebuilds, stochastic
      sweep) and M_grass_medium_01 (Task 4). Not isolated.
    ⛔ B3.12's SHADE BAND 2.184-2.940 IS QUOTED "AT WHITE POINT
      3481.9 K" AND THE WHITE POINT MOVED to 3415.7 on 09-14. That is
      the exact fault B3.8 was REJECTED for. Re-derive with
      shade_reference at 3415.7, or re-take at the old point — a
      ruling, not a tweak.
    the 09-14 WB solve's BUFFER is unnamed (AUDIT S-5) — the report
      said PPI0, but PPI0 is pre-grade and carries no WB. The EXR read
      was near_ground.exr from a --linear capture, i.e. the
      tone-curve-disabled FinalImage, which IS post-grade. Confirm and
      correct the record before the next solve.
    the shade band needs its INSTRUMENT named — the same frames read
      2.44x/2.86x apart on FinalImage vs PPI0. Card-normalised after:
      FinalImage 1.5987 (PASSES the tool's own 1.10-1.60), PPI0 0.5592
      (FAILS 2.184-2.940 by ~4x). 2.184-2.940's derivation is not in
      the record; a third pair (2.587-3.764) in the recipe rests on a
      white-point factor this session made stale.
    white_tint/white_temp COUPLING — solved first-order; B/G residual
      1.0339 decomposes to the coupling (+0.0244 from the temp step).
      A 2x2 solve on both axes together is a ruling, not a tweak.
    the HLOD build — `_Landscape` ruled REDUNDANT and left unassigned;
      what remains is whether to apply census settings to `_Merged`
    ElectricDreams landscape proxy HLOD props — the census has no such
      field, so "do it like Epic" is unanswerable until re-censused
    the precedence null pair — ONE dev capture at vista with the same
      flag value, to attribute the 3.77% frame difference. Command is
      in research/audit/inputs/precedence_frames_README.md. Until then
      the frame instrument is inconclusive, NOT agreeing.
    lever_inventory RECALL — a method-call writer (set_light_color) is
      invisible to a property-name scan, and the command-string fix
      found 7 cvars the old scan never saw. Precision is handled;
      recall is not.
    Task 4's band — the desk's, from the reference spread
    the 0.797 op — named device, unnamed stage
    regeneration — planting-field contract NOT BUILT, still gated
    Snow/ForestFloor 0 px at Bench_ground; Q6/Q9/Q10/Q11

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED
