# Audit Pass 3 — scripts against their own claims (2026-09-15, first cut)
Input: script_claims.json (973 scripts; 462 landscape pipeline, 428 packaged forge copy, 69 hero parked, 14 forge), desk_core sources.
Doc basis: the two constant sets checked here against Epic 5.8 (SkyAtmosphere defaults; landscape height encoding) are marked Doc; everything else is Project.

## 1. Test and control coverage (landscape pipeline, 462 scripts)
| class | count |
|---|---|
| selftest with positive AND negative control | 15 |
| selftest with one control only | 20 |
| selftest with no control at all | 17 |
| no test, but carries thresholds or ⭐/⛔ rules | 146 |
| no test, no thresholds (glue, CLI, one-offs) | 178 |
| KEEP (tested, called, named) | 45 |
Standard to apply (FP-4 generalised): an INSTRUMENT (anything that emits a verdict) has both controls; a TOOL (transforms, no verdict) has a selftest; GLUE needs neither. The 20 one-control instruments get their missing control first — they are the ones that pass tests and can still be fooled (tile_peak's 0.00000 null and the concavity gate were both in this class).
One-control instruments: temporal_stability (both copies), tiling_score (both copies), bench_capture, composite_stamps, derive_layer_weights, exr_card, heightmap_orientation_check, hillshade_snow_check, hlod_overnight, plan_encounters, reachability, surface_query, surface_report, surface_tables, task4_meadow_albedo, task4_reference_bins, town_exclusion, verify_ground_station.
Duplicate copies: temporal_stability.py and tiling_score.py exist both under scripts/ and under research/brief*/scripts/ — one is the tool of record, the other drifts. Ruling: the research/ copy is the desk's delivered artefact (read-only); scripts/ holds the working copy; a selftest asserts they are byte-identical or the scripts/ one states its divergence.

## 2. Thresholds without in-file provenance (priority by reach)
| script | refs | thresholds | provenance needed |
|---|---|---|---|
| capture.py | 161 | SCREENSHOT_TIMEOUT 900 s, SLOW_CAPTURE_NOTICE 90 s, SUSPEND_GAP 30 s, FRAME_FILL_WARN 0.45 | timeouts: state the wedge occurrences they were tuned on; FRAME_FILL_WARN: which capture set derived 0.45 |
| landscape_spec.py | 87 | MAX_PIVOT_OFFSET 1.0 m, MAX_BASE_OFFSET 0.25 m, MAX_UNCORRECTED_SINK_FRAC 0.25, LANDSCAPE_FULL_RANGE_UNITS 512 | 512 = 65536/128 — **Doc-consistent** with UE landscape height encoding (world_z = loc + (unit−32768)·ZScale/128; the 128000 cm cancellation on 09-14 is the same identity). The three offsets: cite the ruling |
| make_landscape_material.py | 65 | SLOPE_FEATHER_MAX 12°, HEIGHT_FEATHER_MAX_FRAC 0.06, OPEN 1e-3 | ~~Brief 3 Task 2 derivation~~ — MIS-ATTRIBUTED (ruling R3, 2026-09-16). Real source: LESSONS 2026-08-01 (R2 feather widths, "defensible aesthetic defaults, not physics") / recipes/schema.md v1.2 (normative formula) / commit 3570cb51. Cited in-file 2026-09-16. OPEN 1e-3 was already explained in-file (closed-cosine open band). |
| place_foliage.py | 64 | (ceiling gate only; no floor — F-1) | floor gate at −20% of ruled count (D-3) |
| import_heightmap.py | 47 | LEGAL_SECTION_SIZES (7,15,31,63,127,255), LEGAL_SPC (1,2) | **Doc-consistent**: UE landscape quads per section are 7/15/31/63/127/255 and sections per component 1 or 2 |
| atmosphere_solve.py | 14 | Earth radius 6360 km, atmosphere 60 km, Rayleigh (0.005802, 0.013558, 0.0331) scale height 8 km, Mie 0.003996 / absorption 0.000444 / 1.2 km / g 0.8, ozone (0.00065, 0.001881, 0.000085) tent 25 km ± 15 km | **Doc-consistent**: these are the 5.8 SkyAtmosphere component defaults (Rayleigh scattering scale 0.0331 × its colour, Mie scattering 0.003996, Mie absorption 0.000444, exponential distributions 8/1.2 km, ozone tent). Add the doc pointer; the solve uses the recipe's Mie 0.01 over these defaults — state that in the docstring |
| derive_layer_weights.py | 5 | SNOW_BASE 730 m, SNOW_ASPECT_HALF 125 m, SNOW_FEATHER 60 m, ROCK 29–35°, SCREE 20–32°, SCREE_SOURCE 40°, RUNOUT 60 m, CANOPY_COVER (0.15, 0.45), GRAVEL_MAX_SLOPE 20° | Brief 3 Task 2 register rows — cite each; scree 20–32° against angle of repose (30–38° talus) is derived, say from where |
| hlod_build_batched.py | 1 | STALE_LAYER "MeshMerge(1)", CURRENT_LAYER "MeshApproximate(3)", EXPECTED_PACKAGES 2267, STALE_BYTES 5 MB, REBUILT_BYTES 3 MB, MIN_PACKAGE 1 KB | **replace**: byte-size heuristics as staleness detectors are fragile; the off-disk hash census (58c4f1ad) is the instrument. Package count 2267 is a hard-coded world fact — read it from the manifest |
| perf_standalone.py | 1 | MIN_WINDOW 25 s, SETTLE 60 s, MARGIN 20 s, FRAMES 60000, EYE 175 cm | cite the warm-up-discard ruling (e0b4282e) and the settle derivation |
| greycard.py | 7 | DIST 300 cm, SCALE 0.3, HALF 50 cm, INNER_FRAC 0.6 | card subtends 1 m at 3 m at 90° = 16.7% of frame width; inner 60% read — state it |
| sweep_cameras.py | 2 | 24 thresholds | pre-8K camera sweep — likely ARCHIVE after Pass 5 reads it |

## 3. Archive proposal (R-O1 criteria: uncalled AND untested AND unnamed; string-reference check passed for all 86)
Ruling refinement: payloads are run by hand through ue_exec and are never "called" by scripts, so the criterion for them is **last git touch before 2026-09-08 → scripts/payloads/_archive/**; touched since → keep (active diagnostics). Claude Code applies the date test with `git log -1 --format=%cs -- <file>`.
### 3a. Separate products — move under their product folder, not the landscape archive (31)
  - scripts/blender/add_groom_gn_stack.py
  - scripts/blender/add_rest_geometry.py
  - scripts/blender/check_gn_bakes.py
  - scripts/blender/check_repoint_sockets.py
  - scripts/blender/church_profile.py
  - scripts/blender/church_split.py
  - scripts/blender/clear_gn_bake.py
  - scripts/blender/export_groom_source_head.py
  - scripts/blender/make_groom_authoring_blend.py
  - scripts/blender/make_test_groom.py
  - scripts/blender/mesh_spans.py
  - scripts/blender/probe_groom_exporter.py
  - scripts/blender/probe_modifier_api.py
  - scripts/blender/repoint_demo_groom.py
  - scripts/hair_stage.py
  - scripts/hair_variants.py
  - scripts/hero_face/capture_hero_pie.py
  - scripts/hero_face/likeness/axis_test.py
  - scripts/hero_face/likeness/contact_sheet.py
  - scripts/hero_face/likeness/env_check.py
  - scripts/hero_face/likeness/frame_signal_floor.py
  - scripts/hero_face/likeness/hair_color_measure.py
  - scripts/hero_face/likeness/hero_closeups.py
  - scripts/hero_face/likeness/shoot_sequence.py
  - scripts/hero_face/likeness/solo_shots.py
  - scripts/hero_face/likeness/three_panel.py
  - scripts/hero_face/likeness/verify_dna_edit.py
  - scripts/hero_face/plot_landmarks.py
  - scripts/hero_face/run_pie_probe.py
  - scripts/trellis/_forge_generate_body.py
  - scripts/trellis/render_mesh_views.py
### 3b. Landscape scripts, never referenced by another script, commit message or doc (13 + 3 one-offs) — ARCHIVE
  - _verify/20260831_coast_benchmark/render_preview.py
  - _verify/20260831_spike_photo2landscape/render_preview.py
  - _verify/20260901_overnight/make_comparison.py
  - scripts/census_rollup.py
  - scripts/ground_crop.py
  - scripts/ground_station_pick.py
  - scripts/kit_measure_v2.py
  - scripts/rebuild_sample_modules.py
  - scripts/rederive_shadow_band.py
  - scripts/rejudge_sky_depth.py
  - scripts/scan_tile_derive.py
  - scripts/void_differential.py
  - scripts/c0_run_stage.py
  - scripts/verify_doc_conservation.py
### 3c. Payloads — date test (41)
  - scripts/payloads/apply_landscape_hlod_settings.py
  - scripts/payloads/bench_dump_wp.py
  - scripts/payloads/bench_ground_place.py
  - scripts/payloads/bench_probe.py
  - scripts/payloads/console_api_probe.py
  - scripts/payloads/cvar_exists_probe.py
  - scripts/payloads/cvar_probe.py
  - scripts/payloads/dirty_actor_labels.py
  - scripts/payloads/exposure_cvar_probe.py
  - scripts/payloads/fog_state.py
  - scripts/payloads/foreign_light_probe.py
  - scripts/payloads/hlod_census_readback.py
  - scripts/payloads/hlod_clear_invalid.py
  - scripts/payloads/hlod_default_probe.py
  - scripts/payloads/hlod_pick_cell.py
  - scripts/payloads/hlod_runtimehash_probe.py
  - scripts/payloads/landscape_force_lod.py
  - scripts/payloads/landscape_material_probe.py
  - scripts/payloads/local_exposure_probe.py
  - scripts/payloads/make_depth_material.py
  - scripts/payloads/make_scenetexture_passthrough.py
  - scripts/payloads/message_log_probe.py
  - scripts/payloads/meter_warmup_probe.py
  - scripts/payloads/missing_ifa_distance.py
  - scripts/payloads/missing_ifa_probe.py
  - scripts/payloads/move_station_diagnostic.py
  - scripts/payloads/mrq_color_probe.py
  - scripts/payloads/read_grass_card.py
  - scripts/payloads/read_hlod_settings.py
  - scripts/payloads/read_rvt_and_mipbias.py
  - scripts/payloads/read_shadow_state.py
  - scripts/payloads/read_stochastic_binding.py
  - scripts/payloads/runtime_partition_probe.py
  - scripts/payloads/runtime_partition_surface.py
  - scripts/payloads/save_cost_probe.py
  - scripts/payloads/save_dirty_actors.py
  - scripts/payloads/set_color_gamma.py
  - scripts/payloads/set_preexposure.py
  - scripts/payloads/sky_ground_albedo.py
  - scripts/payloads/task4_shadow_lever.py
  - scripts/payloads/vista_hlod_boundary.py
Known exceptions to keep regardless of date: fog_state.py (Pass 1 read-back of the Sky-Atmosphere-affects-fog gate), read_shadow_state.py / task4_shadow_lever.py (Task 4 stage 2 record), read_rvt_and_mipbias.py (B3.20), make_scenetexture_passthrough.py + make_depth_material.py (the PPI0 and depth passes — instruments of record).

## 4. Instruments to retire or replace
- hlod_build_batched byte-size staleness → the hash census.
- task5_fog_contrast luma_std → diagnostic only (ruled 09-15); convergence instrument is the acceptance.
- Any script that still reads `--instrument truth` (retired S-12) — grep and remove.
- tile_peak nulls: fixed; keep the three-column contract as the template for every verdict emitter.

## 5. What Pass 3 still owes
Reading the 146 threshold-bearing untested scripts for claims vs behaviour (the make_foliage_material / __RESULT__ class of bug). Mechanical scan cannot find those; it is the desk's next round, prioritised by refs: capture.py, landscape_spec.py, make_landscape_material.py, place_foliage.py, import_heightmap.py, apply_lighting.py, bench_capture.py.

## 6. Reading-half results (Q6, 2026-09-16; deputy read-only, verified + fixed by main author)
Worklist: research/audit/pass3_reading_worklist.json (keyed, status per script). One row per script read.

| script | findings (class: verdict) | disposition |
|---|---|---|
| capture.py (1393 lines, read fully) | F1 sentinel survives an orderly setup-failure exit (claim-vs-code, CONFIRMED); F2 residency gate passes on zero landscape descs — rule-13 violation (verdict-integrity, CONFIRMED); F3 docstring+print misquote pipeline rule 4 with a dropped LESSONS clause, seeded into 3 more scripts (stale-claim, CONFIRMED); F4 "two dependencies CLAUDE.md permits" — CLAUDE.md names none; register is environment.md (stale-claim, CONFIRMED); F5 "% of its frame" is an angular bound, screen-area runs higher (threshold-semantics, CONFIRMED) | ALL FIXED same commit: F1 sentinel removed in the setup except-path; F2 zero-count refuses with a printed reason (exit 6 path); F3 seed + copies (place_foliage, save_level, delete_stray_landscape) reworded to the live rule; F4 comment cites environment.md; F5 message states the angular caveat. Clean areas and unre-opened engine citations recorded in the reading JSON (scratchpad). |
| landscape_spec.py (847 lines, read fully) | F1 recipe_mesh_paths docstring claims "every mesh path" but rocks are split out and discarded (claim-vs-code, CONFIRMED); F2 get_bounds citation drifted to a print/table line (stale-claim, CONFIRMED); F3 embed_frac provenance quotes a validator message that exists nowhere -- real text "above 0.5 buries more than half the rock" (stale-claim/rule-9-miniature, CONFIRMED); F4 exit-code classified by substring over a message interpolating the recipe PATH -- a path containing "parse"/"not found" flips exit 1 to 2 (dead-check, CONFIRMED); F5 bare float() on registry row fields -- a JSON null/list/string escapes every caller's (OSError, ValueError) net and crashes instead of the promised per-mesh REFUSE (verdict-integrity, CONFIRMED; latent, registries well-formed today) | ALL FIXED same commit: F1/F2/F3 doc fixes; F4 prefix classification with the prefixes documented load-bearing in load_recipe; F5 _num type-gate routing to the existing refusal, proven three directions. Auditor PASS, no findings. capture.py audit also PASS; its one FIX (delete_stray_landscape docstring still quoting the dropped LESSONS clause) fixed in the same follow-up. |
| make_landscape_material.py (3789 lines, read fully) | F1 two "skip loudly" grass skips printed nothing -- a species vanished with every instrument green (claim-vs-code, CONFIRMED); F2 layer_bands-lane recipe faults exited 1 against the documented exit-2 contract (claim-vs-code, CONFIRMED); F3 variant_map/macro_variation without weightmap planned samplers the graph never builds -- post-clear assertion death, the skill-recorded failure class (claim-vs-code, CONFIRMED); F4 payload quantises triplanar sharpness to integers while the CPU model computes real powers -- invariants certified a formula the graph does not implement at 4.5 (claim-vs-code, CONFIRMED); F5 _sample_typed hardcoded sampler SOURCE, the declaration column inert at 8 call sites (claim-vs-code, CONFIRMED); F6 stale 3-channel _chan copy of the 4-channel _CHAN contract (dead-check, CONFIRMED) | ALL FIXED same commit: WARNINGs on both skips; ValueError + main() wraps for exit 2; host-side cross-field REFUSE + weightmap in the sub/d predicates; host-side sharpness quantisation (shipping 2.0 unchanged); source from _row[4]; one _chan spelling. Proven offline (check script + import-time invariant suites + offline suite); auditor PASS clean, shipping plan bitwise unchanged. |
| apply_lighting.py (1583 lines, read fully) | F1 leftover unconditional real_time_capture=True AFTER the recipe write and read-back -- sidecar asserts a value the engine does not hold (read-back, CONFIRMED, latent); F3 sun_rotation_matches computed by the payload, never inspected by the host -- computed-and-discarded beside the very comment saying that pattern was killed (verdict-integrity, CONFIRMED); F5 fog_density (the 2026-08-01 whiteout field) + sun intensity/temperature written with NO read-back while neighbours had one (read-back, CONFIRMED); F4 fallback 0.2 vs justifying comment 0.4 (claim-vs-code, CONFIRMED); F2 _pkg_files docstring claims an external-actor filter that does not exist (claim-vs-code, CONFIRMED) | ALL FIXED same commit: re-set deleted; payload reads back all four fields; host COMPARES them + sun_rotation_matches in the verdict block (exit 4 on mismatch); default 0.4; docstring states the real mapping + non-OFPA caveat. Auditor FIX-1 applied: host fog comparison mirrors the payload predicate fog["enabled"], not the always-truthy key presence. Template re-verified to format. |
| place_foliage.py (1923 lines, read fully) | F2 --exclude-only FILTERED rock plans against three claims saying rocks were left alone, overwriting their waiver with tree narrative (claim-vs-code, CONFIRMED; live for the alpine biome); F3 the instance-REMOVING mode parsed --ruled-count and silently ignored it -- no floor protection where it matters most (dead-check, CONFIRMED); F1 exit-code table wrong on three counts (flow map, exit-3 breadth, missing exit 7) (claim-vs-code, CONFIRMED); F4 docstring overstates the pre-gate (900/ha refused only post-plan) (claim-vs-code, CONFIRMED, doc fix); F5 _is_count documented the wrong NaN hazard (claim-vs-code, CONFIRMED, doc fix); F6 no-op two-backslash replace (dead-check, CONFIRMED) | ALL FIXED same commit: ROCK-SKIP rows; floor gate wired into exclude_only with disk read-back (REFUSE=3, DEGRADE named); table corrected; docs corrected; os.sep normalisation. Auditor FIX applied (refusal 1->3 at the missing-declaration gate). Pre-existing cross-biome glob leak BACKLOGged. Selftest green. |
| import_heightmap.py (2899 lines, read fully) | F1 rock branch continue skipped the name+mesh checks -- duplicate/illegal rock names and missing meshes validated clean (dead-check, CONFIRMED); F2 rock height_m admitted, never validated -- KeyError crash or silent-empty placement (claim-vs-code, CONFIRMED); F3 rock mask slope_deg no bounds/ordering -- inverted pair = all-zero mask, species places nothing silently (threshold-semantics, CONFIRMED); F4 dot-py guard misses the two interpolated FIELDS (parent_material, actor_name) (claim-vs-code, CONFIRMED); F5 bare int() on registry lod_count crashes past the load-only net (claim-vs-code, CONFIRMED); F6 stale line citation (stale-claim, CONFIRMED) | ALL FIXED same commit: name/mesh moved above the branch (one spelling); height_m + slope_deg mirrored from the veg checks (9 shipping rock species verified in-bounds, nothing valid newly refused); field scan with PAT; lod_count type-gated; name citation. Auditor FIX applied: the field scan itself type-gated (or-{} does not save truthy non-dicts) + same idiom swept at layer_names/hm_src; adversarial probe exits 2 clean. Pre-existing: alpine_8k fails its own validator at HEAD (BACKLOG). |
| bench_capture.py (1940 lines, read fully; + payloads/bench_render.py seed) | F1 the declared sky band was NEVER read (BENCH/benchmark.json joined onto a path that IS the file; fallback always won, masked by matching values) (claim-vs-code, CONFIRMED); F2 --dolly-only judged an empty list -- zero-comparison residency PASS on a used path (verdict-integrity/rule 13, CONFIRMED); F3 --truth sidecar asserted "APPLIED" for a range the run printed it was NOT applying + expected sets at the wrong radius (read-back/rule 12, CONFIRMED); F4 --depth help claims raw-cm EXR, material emits log2 (claim-vs-code, CONFIRMED, seed in bench_render.py); F5 dead "--discover-grid" instruction (stale-claim, CONFIRMED); F6 unguarded sidecar rewrite could truncate the guarded write (dead-check, CONFIRMED) | ALL FIXED same commit: open(BENCH) + selftest band assertion; _judged = _resi_stations; range_applied_cm + honest provenance + rng from the applied range + not-a.truth cells guard; help + seed corrected; real grid-derivation route named; serialise-then-truncate with _jsonable. Selftest PASS. Deputy notes: selftest has NO control on the derived-judging path or content-gate arithmetic (missing-control lane); docstring sidecar name fixed. |
| verify_landscape.py (861 lines, read fully; 230 refs, the rule-7 gate) | F1 docstring claims a 63x2/126x1 blind spot "reported explicitly" -- the D3 ruling made spacing unique and no report exists (stale-claim, CONFIRMED); F2 "fails as a mismatch" -- fully-unloaded exits 6 INCOMPLETE (claim-vs-code, CONFIRMED); F3 --quiet "print only on failure" vs deliberate always-print DERIVED block (claim-vs-code, CONFIRMED); F4 "Neither caller" -- six callers today (stale-claim, CONFIRMED); F5 unreachable "matched but no data" branch presented as reachable (dead-check, CONFIRMED) | ALL DOC-ONLY, fixed same commit; no code change, py_compile OK. Clean: exit contract, fail-closed gates, zero-measurement refusals (rule 13). BACKLOGged: DEFAULT_RECIPE inherits pre-8K alpine.json (fail-safe but silently legacy). |
| ue_exec.py (311 lines, read fully; the transport, 138 refs) | F1 the local syntax check ran BEFORE __RENDER_PREAMBLE__ expansion -- the bare marker parses, so a preamble syntax fault (the exact motivating class) reached the editor while the comment claimed otherwise (claim-vs-code, CONFIRMED); F2 the mangle guard knew /Game/ only while claiming every parameter, and its hint was case-sensitively split against a case-insensitive match (claim-vs-code, CONFIRMED); F3 find() vs the last-act marker contract + AttributeError on non-object JSON where the COULD-NOT-LOOK refusal was promised (verdict-integrity, CONFIRMED) | ALL FIXED same commit: expansion precedes the check (comment states real coverage); (game|engine) regex + match-derived hint; rfind + isinstance refusal. Offline checks green. Deputy notes: stage_name default latent hazard; MODE_EXEC_FILE __file__ UNVERIFIED (engine-side, fails loudly if false). |
| .claude/hooks/guard.py (553 lines, read fully; THE ENFORCEMENT LAYER) | F1/F4 two drifted heredoc regexes -- the common redirect form failed OPEN on the escapes rule, <<- failed both ways (dead-check, CONFIRMED); F2 -m searched the whole command against a segment-scoped detection -- false deny on compliant compounds, observed live this session (claim-vs-code, CONFIRMED); F3 -am and attached -m"x" bypass (claim-vs-code, CONFIRMED); F5 --file= skipped the claims check (dead-check, CONFIRMED); F6 long options, rd /s, PS alias/abbreviation bypasses of the force-delete rule (claim-vs-code, CONFIRMED); F7 load_level allowed on MENTION of open_level.py, not invocation (claim-vs-code, CONFIRMED); F8 scratchpad sanction was a substring match, wider than its stated sanction (claim-vs-code, CONFIRMED); F9 the four path rules bind to file tools only -- shell writes bypass (claim-vs-code, CONFIRMED, recorded not built); F10 relative -F path opened against the hook cwd (UNVERIFIED divergence, handled) | 8 FIXED same commit with a shared HEREDOC_RE and 17 new prove_hooks fixtures, 183/183 green; F9 recorded in GOVERNANCE_MIGRATION + BACKLOG; F10 cwd-resolved + honest comment. |
| forge.py (625 lines, read fully; + run_forge.sh) | F1 BLOCKER: the 1e archival moved _forge_generate_body.py while run_forge.sh:45 still calls it -- the "unreferenced" grep read .py importers only, and every fresh forge would fail at stage 3 masked as a TRELLIS failure (stale-claim, CONFIRMED, SAME-WINDOW REGRESSION); F2 an AI-guard REFUSAL exited 3 as could-not-look instead of the documented exit-2 gate verdict (verdict-integrity, CONFIRMED); F3 refused/failed runs wrote NO cost line -- the exact uncosted GPU spend the register preamble forbids (claim-vs-code, CONFIRMED); F4 --skip-generate with a missing obj ran real generation but logged (REUSED) (claim-vs-code, CONFIRMED); F5 row-NOT-written still exited 0, re-opening the exit-0-no-register-row defect its own docstring narrates (verdict-integrity, CONFIRMED); F6 a recipe omitting views KeyError-ed at exit 1 past the designed exit-2 refusal (claim-vs-code, CONFIRMED) | ALL FIXED: file RESTORED by git mv + INDEX corrected + a sweep of all 45 archived entries against .sh/.txt/.json/.md referencers (2 prose hits repointed); __FORGE_GUARD_REFUSED__ marker -> exit 2; cost lines on the intake-refusal and stage-3-error paths + reused reflects the branch taken; NOT-written -> exit 3 after the report lands; .get() to the designed refusal; _write_report added to stage-3/4 failure paths (stale-report hazard). Auditor verdict pending. |
| plan_city.py (711 lines, read fully) | F2 the network verdict could PASS over ZERO street samples (three checks keyed off one falsy input; the backstop floor defaults to 0) (verdict-integrity/rule 13, CONFIRMED); F5 the landmark cut/fill recorded, gated against NOTHING (claim-vs-code, CONFIRMED); F7 roof_servable bool(None)=false read as measured-not-servable (verdict-integrity, CONFIRMED, latent); F9 the roofs print reported recipe pitch_deg the construction never reads (claim-vs-code/rule 12, CONFIRMED); F10 dead else-branch never printed (dead-check, CONFIRMED); F1 on_street counter never incremented -- 0 wearing a verdict (dead-check, CONFIRMED); F3 roof loc_cm z is the wall MID-height copy against a top-of-wall comment (claim-vs-code, CONFIRMED); F4 "long axis tangential" backwards ~65% of the time (claim-vs-code, CONFIRMED); F6 orphan distance is to segment MIDPOINTS, conservative (threshold-semantics, CONFIRMED); F8 the prune anchors on the innermost segment, not the plaza (claim-vs-code, CONFIRMED) | SPLIT by the reproduce-identity constraint: refusals/prints/comments landed (zero-street REFUSE, landmark gate, null-when-unmeasured, constructed 45, real if/else, five truth-comments); payload-shape changes MARKED IN-CODE and gated to the next ruled regeneration (on_street, roof loc_cm z, axis swap, emitted plaza text, the city.json stale ref inside the consumed buildings field). Ripple fix: R-PLANSTALE amendment 1e -- reproduce verdicts judge the PAYLOAD; metadata-only drift prints and reads REPRODUCES. Suite 29/29 re-verified. |
| resource_guard.py (218 lines, read fully; the heavy-op fence) + save_foliage_actors.py | F2 the lock was a NON-ATOMIC check-then-write -- two concurrent starts both see no live lock and both truncate, the exact case the lock exists for (claim-vs-code, CONFIRMED); F3 _pid_alive read GetLastError via a bare windll call ctypes can CLOBBER -- a live access-denied PID could read dead and have its lock STOLEN (claim-vs-code, CONFIRMED); F4 check_memory returned True on an unreadable RAM read -- could-not-look indistinguishable from comfortable (verdict-integrity, CONFIRMED, latent); F1 the headroom rationale quoted the retired 16 GB machine (15.4/1.8/6.5 GB) (claim-vs-code, CONFIRMED); F5 save_foliage_actors called a phantom resource_guard.free_gb behind an always-False hasattr, so the rule-5 RAM line never printed (dead-check, CONFIRMED) | ALL FIXED: atomic O_CREAT|O_EXCL acquire with a once-retry reclaim; WinDLL(use_last_error=True) + get_last_error(); check_memory returns None on unread (callers discard it, behaviour-neutral today); doc figures re-based to the MEASURED 10.6 GB-free current machine (recorded in environment.md); save_foliage_actors uses available_gb() with a could-not-read line. Proven 11 directions (clean acquire holds, live second REFUSES, dead/garbage lock reclaimed, None-vs-bool return, pid liveness). |
| rock_scatter.py (1493 lines, read fully) | F4 cull_distance_m=0 (DISABLED = unlimited draw in-engine) made triangles_in_view return 0.0 -- the MOST expensive config reported as the cheapest and passing the budget (verdict-integrity, CONFIRMED, latent); F3 rotation_gate yaw-uniformity only runs at n>=1000, so a pitch-into-yaw transposition passes for small species (CliffFace 84) and the selftest (n=5000) cannot see the gap (verdict-integrity/rule 13, CONFIRMED); F1 live_lods_and_materials RAISES on a missing registry, uncaught in the budget loop -> traceback exit 1 vs promised exit 2 (claim-vs-code, CONFIRMED); F2 missing recipe/heightmap/weightmap -> uncaught traceback exit 1 vs the exit-2 contract (claim-vs-code, CONFIRMED); F5 seven stale place_foliage line citations (place_foliage restructured 09-16) (stale-claim, CONFIRMED); F6 orphan-sweep blast radius quoted the archived 157,554 vs live ~217,102 (stale-claim, CONFIRMED); F7 embed "along the surface normal" is really the BLENDED up-axis (normal only at align=1) (claim-vs-code, CONFIRMED); F8 embed_depth_per_scale_m claims exact reconstruction verify_grounding shows is impossible (claim-vs-code, CONFIRMED) | ALL FIXED: cull (0,5000] refusal (9 live plans pass); rotation_gate returns (ok,reasons,NOTES) with the small-n skip printed loud (rule 13), gate still catches large-n; ValueError/OSError -> REFUSE exit 2 with a path; anchors for the stale cites; blast radius names the live plan set; embed comments corrected. Selftest PASS; F3/F4 behaviour proven. |
| terrain_erosion.py (468 lines, read fully; carries MOVEMENT_PROFILES) | F1 slope_degrees took a `resolution` parameter it NEVER read -- and it looked exactly like the resolution-vs-spacing guard this module exists for; a caller passing the recipe scale_xy_cm + a preview resolution would get slopes wrong by the ratio (the 2026-08-01 all-snow shape) with no error (dead-check, CONFIRMED); F2 the peaks comment said the caller "adds landscape.location_cm" -- x_m/y_m are METRES, location_cm is CM, a 100x world-position error of the 2026-08-02 camera class (claim-vs-code, CONFIRMED) | BOTH FIXED: the dead param removed from the signature and all 3 call sites (audit_step_height x2, make_alpine_terrain), docstring states the spacing must be corrected BEFORE the call; the comment corrected to "/ 100.0 (metres vs centimetres)". Callers already pre-correct via spacing_for, so removal is behaviour-neutral; all three compile, no stale-arg caller remains. |
| shoot.py (362 lines, read fully) | F1 a malformed --loc/--rot raised SystemExit("string") = exit 1, the code reserved for "payload ran / no frame" -- a series driver retrying exit 1 as transient loops forever on a typo the editor never saw (claim-vs-code, CONFIRMED); F2 exit 1 also covers could-not-look cases (no JSON/no marker, old payload) the table did not name (claim-vs-code, CONFIRMED); F3 stale ue_exec.py:174 cite (now the payload arg) (stale-claim, CONFIRMED) | ALL FIXED: _triple prints then SystemExit(2); exit table widened for the could-not-look cases and the bad-arg note; cite -> function names. Proven: both malformed-triple cases exit 2 with REFUSE text. |
| make_alpine_terrain.py (1231 lines, read fully; the compositor) | F4 a recipe that EXISTS but fails to parse was caught, downgraded to a WARNING with recipe=None, and the `if recipe:` world-gate block SKIPPED -> main fell to exit 0 "written and verified" with the gate never run, reproducing the 2026-08-02 ship-a-broken-world hole the gate exists to close (verdict-integrity, CONFIRMED); F1 docstring relief-default header frozen at 0.62, argparse default is 0.48 (claim-vs-code, CONFIRMED); F2 "writes exactly one file" -- a default run writes 4 (heightmap + flow/deposition/hillshade) (claim-vs-code, CONFIRMED); F3 exit table omits the return-3 written-but-world-missed state (claim-vs-code, CONFIRMED); F5 fold "^2" is really ^--ridge-sharpness (default 1.6) (claim-vs-code, CONFIRMED); F6 the run-print called ridge_width the corridor WIDTH -- it is a HALF-width (claim-vs-code, CONFIRMED) | ALL FIXED: an unparseable given recipe REFUSES exit 1 before the write (LIVE-PROVEN: broken recipe -> exit 1, no heightmap), a missing recipe prints a loud gate-skipped NOTE; docstring relief 0.48 with the 0.62->0.48 history, aux-file count, exit-3 row, ^sharpness fold; print says HALF-width + full footprint. |
