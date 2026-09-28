# Desk audit — running record
Repo: UE5LandscapePipeline (Alpine8K). Engine: UE 5.8. Started 2026-09-14. Owner: the research desk.
This file is the ongoing audit. Each pass appends; verdicts are never edited in place — a superseded verdict gets a
dated line under it. Verdict vocabulary: CONFIRMED / WRONG-FIX / DEAD-REMOVE / STALE-REWRITE / READ-BACK-OWED /
UNAPPLIED-APPLY / UNVERIFIED. "Doc" = checked against Epic 5.8 documentation by the desk. "Project" = measured in the corpus.

## Status board
| pass | scope | state |
|---|---|---|
| 1 | levers in force vs 5.8 docs | DONE 2026-09-14 — detail in AUDIT_PASS1_levers_2026-09-14.md; amended 09-15 (§8) |
| 2 | 307 editor properties vs Python API; copy/nested-struct read-back trap | DONE 2026-09-16 — trap hunt (§2), inputs (§9), API-name pass (§11): zero live defects |
| 3 | scripts vs their own claims; tests; callers; archive proposal | NOT STARTED |
| 4 | LESSONS / RECIPES / CLAUDE / STATE / registers rewrite to traceable lines | NOT STARTED — evidence coverage measured (§3) |
| 5 | findings ledger: 405 UNAPPLIED ruled APPLY / OBSOLETE / WRONG | STARTED — 2 ruled (§4) |

## Inputs received
desk_core.zip (1,254 files), lever_inventory, api_inventory, findings_ledger, script_claims, tools_of_record, report_groups,
CONTRADICTIONS_AND_DEAD_WEIGHT.md, README.md, corpus_tree.txt, claims_ledger (35,376 rows).
Received 09-15 (Claude Code session): benchmark.json; mrq_config_dump.json; cvars_5.8_live.txt (11,073 entries: 9,817 Var / 884 Cmd / 372 Exec); hlod_landscape_layer.json; lever_inventory v2; sidecars.zip (549); history_diffs.txt (544 commits) — files to be uploaded to the desk.

---
## 1. Pass 1 — levers in force (summary; full tables in the Pass 1 file)
### 1.1 Corrections to the ledgers themselves
- `lever_inventory.json` marks every cvar mention as a WRITE and 0 READS for all 98. Re-scanned with context: current scripts
  directly write ~6 cvars; the bench's cvars flow benchmark.json → MoviePipelineConsoleVariableSetting and ARE read back
  from the engine log; probes are reads. The "170 written, never read back" figure holds for editor properties, not cvars.
  FIX: `scan_levers_and_api.py` classifies by call context (execute_console_command / add_or_update_console_variable vs get_console_variable_*).
- Non-levers captured by the regex: a.png, a.txt, a.ini, a.uasset, t.png, r.ScreenPercentage100, *_overridden_by_this_capture, *_applied. DROP.
- The claims ledger's mechanical `contradicted_by` links on CLAUDE.md (9) and STATE.md (5) are all shared-word noise on
  inspection (e.g. "cutting"/"modify"/"others"). The finder is not usable for the governing docs; Pass 4 is by reading.

### 1.2 Verdicts that change something
| # | finding | verdict | action |
|---|---|---|---|
| P1-1 | MRQ GameOverride: `cinematic_quality_settings` sets Cinematic scalability at render start (Doc); bench dev profile sets sg.*=1 by cvar at the same moment. Precedence unknown → the bench's real scalability is unknown. Same setting carries disable_hlods, use_lod_zero, override_view_distance_scale, use_high_quality_shadows, flush_grass_streaming, flush_streaming_managers — none read back anywhere. | READ-BACK-OWED (7) + precedence test | one capture per flag state, sg.ShadowQuality from the engine log |
| P1-2 | Sky Light real-time capture is time-sliced across frames (Doc). Pre-09-13 captures had 0 rendered warm-up frames → sky lighting unsettled, a second mechanism behind the +0.27 EV. | STALE-REWRITE (register line) | name both mechanisms on the pre-09-13 caveat |
| P1-3 | Fog model: both inscattering colours black → Sky Atmosphere colours the fog, gated by Support Sky Atmosphere Affecting Height Fog (Doc). Brief 2 built exactly this; fog_state.py reads the gate. | CONFIRMED | none |
| P1-4 | `r.LandscapeLODBias` — 6 write sites, does not exist in 5.8 (live enumeration). Honoured lever is Landscape.max_lod_level. | DEAD-REMOVE | delete writes; landscape_force_lod uses max_lod_level |
| P1-5 | Absent cvars still probed as if they might exist: r.TonemapperFilm, r.ExpandGamut, r.LocalExposure.* (6), r.Shadow.Virtual.Nanite.Enable. | DEAD-REMOVE | keep ONE negative control (r.ThisCVarCannotPossiblyExist_zzz) and ONE positive (r.ScreenPercentage) |
| P1-6 | `r.Shadow.Virtual.ResolutionLodBiasDirectional` −1.5 (target profile) vs −0.5 (verify_cold_boot). Two values in force. | WRONG-FIX | one value, in the profile, read back |
| P1-7 | PPV auto_exposure_min/max_brightness written at Manual metering — inert. | STALE-REWRITE | comment or remove the writes |
| P1-8 | recipe `sky.color` — no write site found in apply_lighting. | UNVERIFIED | find the writer or delete the key |
| P1-9 | `clouds.coverage` 0.3 → near-total overcast; parameter semantics unknown; 0.1 read-back capture owed since Brief 2. | WRONG-FIX pending | the owed capture |
| P1-10 | Brief 1 detail threshold at 512 m — re-derivation ruled 09-12 hygiene (d), never reported. | READ-BACK-OWED | angular_budget at 512 m |
| P1-11 | Recipe → apply_lighting writes with no read: sun rotation, enable_light_shaft_bloom, sky_atmosphere_ambient_contribution_color_scale, enable_volumetric_fog, cast_shadows, atmosphere_sun_light, unbound, is_spatially_loaded. | READ-BACK-OWED (8) | add to apply_lighting's read list |

### 1.3 Confirmed clean against 5.8 docs
white balance mode + tint axis; Manual exposure semantics; sun intensity in lux + use_temperature; Sky Light lower-hemisphere-black and real-time capture (needs Sky Atmosphere — present); Mie scattering scale / anisotropy and Rayleigh scattering scale on the Sky Atmosphere component; fog half-height→falloff model (1000/half_height_cm reproduces 0.0193); Volumetric Cloud layer_bottom_altitude / layer_height; HLOD layer Loading Range; MRQ temporal_sample_count handled as a setting, not a cvar; MRQ Disable Tone Curve outputs post-process-pipeline linear (explains PPI0 vs FinalImage); render vs engine warm-up split.

---
## 2. Pass 2 — editor properties (partial)
### 2.1 Struct-copy write trap, hunted mechanically
Pattern: `x = obj.get_editor_property("S")` then `x.set_editor_property(...)` with no `obj.set_editor_property("S", x)` within 40 lines.
Six candidates; on reading, all six are safe: nanite_settings (written via StaticMeshEditorSubsystem.set_nanite_settings), static_mesh_import_data / body_setup / world_partition / hlod_builder_settings are UObject sub-objects (references, not copies), and both HLOD payloads write the struct back up the chain and re-read from a freshly loaded asset. The one real instance (grass_varieties handing out copies) was found and fixed on 09-12. VERDICT: CONFIRMED — no open struct-copy trap in current scripts. The 40-line window is a limit; a helper that reads back from a re-loaded asset (as the HLOD payloads do) is the standard to adopt everywhere (see §6, ll_must).
### 2.2 Pending
Group the 307 properties by class (PostProcessVolume, DirectionalLight, SkyLight, SkyAtmosphere, ExponentialHeightFog, VolumetricCloud, Landscape*, FoliageType, HLODLayer, MoviePipeline*) and check names/enums against the 5.8 Python API reference. Note: set_editor_property on a non-existent name RAISES, so any property written by a script that has run successfully exists; the API pass is therefore about semantics, deprecations (e.g. disable_hlo_ds → disable_hlods) and defaults, not existence.

---
## 3. Evidence coverage of the governing documents (from claims_ledger, mechanical)
| document | rules | rules with an evidence pointer | verdict claims | with evidence |
|---|---|---|---|---|
| CLAUDE.md | 27 | 4 (3 doc, 1 recipe) | — | — |
| STATE.md | 3 | 0 | — | — |
| research/brief3/REGISTER_ADDENDUM.md | 7 | 0 | — | — |
| .claude/ (skills, hooks) | 81 | 1 | — | — |
| LESSONS.md | — | — | 237 | 25 |
| RECIPES.md | — | — | 461 | 5 |
Reading: the rules are mostly right (Pass 1 found them consistent with the docs) but almost none say WHY in a way a reader can check.
Pass 4 standard: every surviving rule carries a pointer (doc URL, script:line, sidecar path, or ruling id); every surviving
verdict claim carries the sidecar or script that produced it; a line that cannot be pointed at is moved to an archive file,
not deleted, with the date it lost its trace.

---
## 4. Pass 5 — findings ledger (405 UNAPPLIED), rulings so far
| # | finding | file | verdict |
|---|---|---|---|
| F-1 | Ceiling gate at place_foliage.py:520 fires only when a plan is too LARGE; a plan half the intended size passes silently. The 152-instance regeneration passed it. | plans/RECIPES_draft_closure.md:141 | UNAPPLIED-APPLY: floor gate, refuse below −20% of the ruled count |
| F-2 | 219,659 placed "never replayed cold". | plans/RECIPES_draft_closure.md:25 | UNAPPLIED-APPLY: cold replay is a Brief 5 acceptance |
| F-3 | Foliage override lists are POSITIONAL and the two PN meshes order slots differently. | plans/RECIPES_draft_pn_trees.md:156 | UNVERIFIED — check whether the current recipe keys overrides by slot NAME; if positional, APPLY |
| F-4 | "Blueberry_01 LOD0 tris ?" recorded where the source file held 195. | plans/RECIPES_draft_understory.md:8 | STALE-REWRITE: fix the artefact |
Remaining 401: line-fragment heavy (236 of 405 per the report); reviewed by reading the source paragraphs in Pass 5 proper.

---
## 5. Ledger quality notes (so the numbers are read correctly)
- Contradiction finder recall ~40% on known cases; precision on governing docs ~0% on inspection. Use as a hint, never a verdict.
- `applied_where` is a text search: a finding implemented under another name reads UNAPPLIED.
- api_inventory's 1,617 silent-failure sites: 94 read as verdict-consuming, but 54 are under dist/ (packaged forge) and 32 of the 40 live ones already handle the failure. Real scope was 4 bare save_asset sites (ruled 6f65e7ba). CORRECTED 09-15.

---
## 6. Standing fix patterns (four; the two §7 items are Ryan's rulings, not patterns)
1. `ll_must.py`: must_exist / must_save / must_connect / cvar_must. must_save APPLIED at the 4 bare sites (bake_hero_face_textures:133, make_alpinelab_material:475, make_layer_debug_material:464, make_landscape_material:3254). The other three functions have zero production call sites by ruling — adopt at new code, not retrofitted. (CORRECTED 09-15; the earlier '94 sites' line was wrong.)
2. Read-back standard: re-load the asset from disk and read the nested member (the HLOD payload pattern), never the object you wrote to.
3. Lever standard: any cvar the bench relies on is in benchmark.json and read back from the engine log; scripts do not execute_console_command for bench state.
4. Probe standard: one positive and one negative control per batch read; no probing of names already known absent.

## 7. Open questions for Ryan
- Archive proposal for uncalled + untested scripts (620 uncalled, 899 untested): the desk will list them in Pass 3; the ruling on whether they move to scripts/_archive/ is yours.
- Whether LESSONS.md and RECIPES.md remain append-only after Pass 4, or become curated with an archive — the desk recommends curated + archive.

---
## 8. Amendments from the 09-15 read-back session
| # | item | result | verdict |
|---|---|---|---|
| P1-1 | sg.* vs GameOverride precedence | The bench cvars win: MRQ's own apply log shows PreviousValue 1 → 1 for sg.ShadowQuality in both arms; scalability echoed from inside the render identical at both hooks. A third instrument (frame diff 3.77% of pixels) is inconclusive pending a dev-profile null pair (precedence_frames_README.md). | CONFIRMED (two instruments, sample counts reported) |
| P1-1b | GameOverride presence | NEW. The dev config has five setting classes and GameOverride is NOT among them; it is added only under `--truth`. Under truth, all 20 properties read back: disable_hlods True, use_lod_zero True, view_distance_scale 50, texture streaming disabled, … So the TRUTH instrument is not only "all regions force-loaded": it is also LOD0 everywhere, HLOD off, draw distance ×50, streaming off. The player instrument never had these. | STALE-REWRITE: the two-instrument ruling's definition of "truth" must state these seven values; every acceptance ever taken on --truth is to be listed and checked for LOD/HLOD/cull contamination (Brief 1 LOD audit and cull verification first). |
| P1-4/5 | absent cvars | All Pass 1 "does not exist in 5.8" verdicts now confirmed against the live enumeration (two instruments, both controls passed). | CONFIRMED |
| P1-8 | recipe sky.color | WRONG in Pass 1: apply_lighting.py:394 writes it via set_light_color(), a METHOD, invisible to the property-name grep. Do not delete the key. | READ-BACK-OWED. General finding: any lever set through a named setter is invisible to the lever scan → scan v3 must include set_*( method calls on engine objects. |
| L-v2 | lever inventory regenerated | 412 levers (97 cvar / 307 property / 8 ini); cvar 131 writes / 2 reads / 276 declared; property 992 writes / 1,202 reads; 28 non-levers dropped; +7 cvars the old scan never saw. | CONFIRMED — Pass 1's classification correction stood and understated the gap. |
| H-1 | Landscape HLOD layer | NEW, WRONG-FIX. The 09-13 census-value write reads back correctly, but 0 of 4,339 actors name any HLOD layer and the world's default chain is Instanced → Merged; the Landscape layer is in neither. The layer is inert: Task 5's settings changed nothing the builder uses, and any Landscape-only build would have built the default chain. | WRONG-FIX: assign the Landscape layer to the landscape streaming proxies (or add it to the world default chain as the census structure has it), then -SetupHLODs and count flagged actors per layer BEFORE any build. |
| R-1 | practice rule (from the session's own failure) | A bare sg.X console query prints nothing; a comparison that reported "two instruments agree" had zero samples on one side. | Rule adopted: every comparison reports its sample count beside its verdict. Add to CLAUDE.md standing rules with this pointer. |

---
## 9. Inputs verified against the live engine (09-15 files: cvars_5_8_live.txt, benchmark.json, mrq_config_dump.json, sidecars.zip, lever_inventory v2)
| # | check | result | verdict |
|---|---|---|---|
| V-1 | every cvar in benchmark.json dev/target (24 keys) against the live 5.8 enumeration | all 24 are type Var | CONFIRMED |
| V-2 | every cvar the scripts write (inventory v2, 33 with writes) | only r.LandscapeLODBias is ABSENT (12 write sites). wp.Runtime.DumpStreamingSources / DumpWorldPartitions / OverrideRuntimeLoadingRange are type Cmd and are used as commands — correct | P1-4 CONFIRMED; no other dead writes |
| V-3 | probe-only absent names (14) | r.TonemapperFilm, r.ExpandGamut, r.LocalExposure.* ×6, r.Shadow.Virtual.Nanite.Enable, landscape.ForcedLOD, foliage.WindEnabled, r.Wind.Enable, r.HairStrands.DebugMode, r.ThisCVarCannotPossiblyExist_zzz | P1-5 CONFIRMED (keep the last as the negative control) |
| V-4 | benchmark.json vs what the engine holds | dev 11/11, target 13/13 cvars present and matching; cvars_match true on every job; temporal 1/8; warm-up 300 engine + 40 render, render_warm_up_frames True; resolutions 2560×1440 / 3840×2160 | CONFIRMED |
| V-5 | AA setting | anti_aliasing_method AAM_NONE but override_anti_aliasing False → inert; the project's TSR applies (matches the 09-13 read-back). The AAM_NONE value is misleading prose in the config | STALE-REWRITE: either set override False explicitly with a comment or remove the method value |
| V-6 | output classes in the standard construction | PNG only; no EXR output class, both additional post-process passes (WorldDepth, MotionVectors) disabled; no PPI0 pass | READ-BACK-OWED: the EXR / PPI0 / depth constructions used by every Brief 3 acceptance are added by flags not in this dump — dump the config under each acceptance flag set (--exr, PPI0 pass, depth) so the acceptance instrument is on record |
| V-7 | GameOverride under --truth, from the sidecars | truth captures: 6 of 111 bench sidecars (09-06 dev diag/truth; 09-09 target mrqtruth ×2, truth_task5; 09-10 truth_t5r). Recorded GO: view_distance_scale 100, override_view_distance_scale, flush_streaming_managers, disable_hlods. Plus a separate editor HighResShot truth on 09-07 (non-MRQ). | The sidecars DID record the requested overrides; the ruling text never did. Definition to write: truth = all regions force-loaded + GO {VDS 100, override VDS, flush_streaming_managers, disable_hlods} + the class DEFAULTS that also apply and were never recorded (cinematic_quality_settings, use_lod_zero, use_high_quality_shadows, texture streaming) — all 20 read back per truth capture from now on |
| V-8 | P1-1b contamination check | Brief 1's LOD audit (E2, lod_silhouette.json) is a mesh-side audit, not a capture; the dolly (E4) and every cull/LOD/perf capture ran on dev/target with GO=none. The six truth captures were residency/void/fog work that INTENDED truth. | CLEAN — no LOD, HLOD, cull or draw-distance acceptance was taken on the truth instrument. P1-1b closes as a definition fix, not a re-measurement |
| V-9 | truth instrument drift | VDS 100 in the 09-06→09-10 sidecars; the 09-15 forced dump shows the class default 50 when only cinematic_quality_settings is requested | the --truth construction sets 100 explicitly; record it in the definition; the default-50 dump was a diagnostic, not a truth capture |
| V-10 | r.Shadow.Virtual.ResolutionLodBiasDirectional | −1.5 in the target config as held by the engine (P1-6 second value −0.5 lives in verify_cold_boot only) | WRONG-FIX stands: verify_cold_boot must check the profile value, not carry its own |

---
## 10. 09-14 evening session (R-SKYCOLOR applied, R-HLODTEX applied, build running)
| # | item | result | verdict |
|---|---|---|---|
| S-1 | sky light colour path | double encode confirmed from source (LightComponent.cpp:1130 → Color.cpp:251); host now passes linear once; _linear_to_srgb deleted. Proof on a discriminating colour ([0.42,0.6,1.0] → FColor(173,203,255) new vs (215,231,255) old) since white is a fixed point. | CONFIRMED FIXED |
| S-2 | sky light value | white (1,1,1); census: all four Epic sample sky lights are white, real-time capture. | CONFIRMED (R-SKYCOLOR) |
| S-3 | grade re-solve | white_temp 3481.9 → 3415.7 (−66 K), tint −0.0139 → −0.0113, compensation −13.5898 → −14.2571, PPI0 card 0.1805 PASS. | CONFIRMED, but see S-4/S-5 |
| S-4 | FinalImage card is 8-bit | card codes 145/144/144 from PNG; one code = 1.5% of the card; WB signal < 1 code. The look instrument has been quantised to 8 bits — the EXR output class is not in the standard construction (V-6). | WRONG-FIX: FinalImage acceptances read from a 16-bit-float EXR; PNG is for viewing only. Add the EXR output to the acceptance construction and dump it (V-6) |
| S-5 | which buffer solved WB | Report says "solved on scene-linear" with PPI0 card R/G 1.000 after — but PPI0 is pre-grade and carries no WB (09-13: R/G 1.814). Either the tap moved, or the numbers were WB-applied numerically. | READ-BACK-OWED: name the buffer and whether WB is inside it; the solve is only valid on a buffer that contains the WB stage |
| S-6 | shade band instrument | Same frames read 2.44×/2.86× apart between FinalImage and PPI0; report could not find the band's derivation. The band 2.184–2.940 is from shade_reference.py (research/brief3/scripts): card-pair ratio of B/luma (Rec.709), each card first divided channel-wise by the lit card (numerical WB), on SCENE-LINEAR data — i.e. PPI0 card-normalised, exactly the 09-13 measurement (2.5166 PASS). Tonight's PPI0 0.5592 is not that metric (a shade/lit ratio of B/luma cannot be < 1 with a bluer shade; 0.56 is a brightness ratio). The 1.10–1.60 row is the struck band and must not be reported as a PASS. | STALE-REWRITE + READ-BACK-OWED: re-run the 09-13 instrument on tonight's frames; docstring names PPI0 card-normalised as the band's domain |
| S-7 | exposure slope 0.7598 "corroborates 0.731" | That slope is post-grade (FinalImage); PPI0 delivers 1.000. It must not enter the PPI0 solve. | STALE-REWRITE (note in the sidecar) |
| S-8 | R-HLODTEX | 257/257 at 4096 (inheritance pushed parent → proxies); build running, every cell approving (hash change), ~10 h projected. | CONFIRMED |
| S-8b | R-HLODTEX PREMISE CORRECTED 2026-09-15 (Ryan) | The pre-cap landscape HLOD **baked at 1024 texels** (≈2 m/texel on the 2 km cells), NOT 256 (8 m/texel) as the handoff §3 and "256-texel bakes" summary stated. So 4096 (0.49 m/texel) is a **4× texel refinement over 1024, not 16× over 256**. The "256" was the pre-R-HLODTEX HLODTextureSize property value; the BAKE that shipped was 1024 (clamped by ProjectHLODMaxTextureSize, "the 32 never existed" finding 41dcfb6a: 1024 on 256/256 cells). The 16×-texel reasoning in O-2 rested on the wrong baseline. | STALE-REWRITE |
| S-9 | VRAM growth | +64 MiB/cell within a batch; 191-cell batches → ~14 GB vs 15.2 budget that hung on 09-12; reset at batch boundary; resume is batch-granular. | WRONG-FIX: batch size ≤ 96 from batch 1 |
| S-10 | census landscape HLOD proxy properties | never collected (sample_census.py:504-518 reads landscape_material only). | READ-BACK-OWED: re-census with the four proxy properties |
| S-11 | content gate | refuses near_ground at 23.3% featureless; bench has read 12.8–36.8% since 09-13; predicted_sky_fraction 0.0075 vs measured featureless_sky 0.15 — the gate's prediction is ~20× off. | Pass 3 item: the gate's prediction model is stale; re-derive from the current world, don't widen the threshold |
| S-12 | truth flags | one instrument, --truth, 20 properties recorded, refuses on fewer; --instrument truth exits 2. | CONFIRMED |

---
## 11. Pass 2 — the 306 editor-property levers vs the LIVE 5.8 Python stub (2026-09-16, Q7)

Instrument: `scripts/pass2_properties.py` (selftest PASS) against
`LandscapeLab/Intermediate/PythonStub/unreal.py` (engine-generated live
enumeration, 21,567 property names parsed; a zero-parse REFUSES).
Result file: `research/audit/pass2_properties.json`.

| verdict | n | disposition |
|---|---|---|
| PRESENT | 290 | exact stub spelling; no action |
| PRESENT_AS_SNAKE | 2 | `CellSize`/`LoadingRange` in apply_streaming_range use the FName spelling; valid at runtime (get_editor_property resolves the FName); recorded, no change |
| ABSENT | 14 | ALL verified at their call sites: 2 DOCUMENTED-CASUALTY (hit_actor, persistent_level — both already carry in-file documentation of the failure and the reflected route; hit_actor is on the ue58-api-protocol casualty list), 7 PROBE-GUARDED (the WP runtime-hash internals probes, every access try/except with the error recorded; the probe docstring documents the bare-UPROPERTY pattern), 4 GUARDED-ABSENT (landscape_guid, landscape_components, imported_size, expression_collection — NN6-style self-reporting reads, two on legacy alpinelab scripts), 1 SCAN-ARTEFACT ("override_" is a dynamically built prefix, not a property) |
| deprecated-flagged | 5 | CLASS-BLIND weak signal (generic names: default_value, is_enabled, name, reduction_settings, settings — the flagged class is not necessarily the accessed class); recorded, not actioned; per-class pass is the named follow-up |

**ZERO live defects: every ABSENT site already fails toward
refusal/report, and the two casualties are documented at the site and in
the protocol doc.** The copy/nested-struct read-back trap hunt (§2) plus
this name pass close C-1's property lane; the AUDIT board row for Pass 2
moves to DONE.

---
## 12. AUDIT CLOSED — 2026-09-19 (D-8)

Passes 1–5 DONE (levers; 306 properties vs live 5.8, zero live defects; 178/178 scripts read, ~648 defects fixed, 41 HIGH; rewrite with STATUS tags, CURRENT VALUES, rule pointers, archive, frames out of git; 405/405 findings ruled). Suite green, 31 checks. Deputy R1–R8 confirmed by the desk 09-17. Carried, not blockers: HLOD proxy collision on ground traces (R-NAVGRID step 9); perf_standalone exposure read-back; REPLAY_BURNDOWN cold replay = Brief 5 acceptance; .git rewrite awaits Ryan; 1b live -game observation. Brief 4 landed 09-19 on the desk's amendment.

_Practice: the repo copy `research/audit/AUDIT.md` is canonical; the desk supplies sections that are APPENDED here, never a whole-file replacement (a whole-file supply on 2026-09-19 silently reverted §11 / the Pass 2 DONE row and was discarded from the working tree)._
