# scripts/_archive — the record that these are archived, not lost

D-2 item 1e, executed 2026-09-15 per `research/audit/PASS3_SCRIPTS_2026-09-15.md`
§3. Archiving here means `git mv` to an `_archive/` folder — nothing was
deleted. Restore any row with `git mv <destination> <origin>`.

Destinations follow the ruling recorded in the D-2 task:
- §3a "separate products" move UNDER THEIR OWN PRODUCT's `_archive/` (blender,
  hero_face, trellis) or `scripts/_archive_products/` for the root-level `hair_*`.
- §3b "landscape scripts never referenced" move to `scripts/_archive/`; the
  three `_verify/**` one-offs move to an `_archive_scripts/` folder beside them.
- §3c payloads move to `scripts/payloads/_archive/` only if their last commit
  predates 2026-09-08 (the date test); named exceptions and later payloads stay.

Reference check: no `.py` in the repo imports or invokes any moved file by path
(only the files' own docstrings and the audit's JSON catalogs name them). The
offline suite was green (baseline: one allowed pre-existing failure, "every plan
against its inputs" / E-4) after each group's commit.

## §3a — separate products (31) — reason: belongs to another product, not the landscape pipeline

| origin | destination |
|---|---|
| scripts/blender/add_groom_gn_stack.py | scripts/blender/_archive/add_groom_gn_stack.py |
| scripts/blender/add_rest_geometry.py | scripts/blender/_archive/add_rest_geometry.py |
| scripts/blender/check_gn_bakes.py | scripts/blender/_archive/check_gn_bakes.py |
| scripts/blender/check_repoint_sockets.py | scripts/blender/_archive/check_repoint_sockets.py |
| scripts/blender/church_profile.py | scripts/blender/_archive/church_profile.py |
| scripts/blender/church_split.py | scripts/blender/_archive/church_split.py |
| scripts/blender/clear_gn_bake.py | scripts/blender/_archive/clear_gn_bake.py |
| scripts/blender/export_groom_source_head.py | scripts/blender/_archive/export_groom_source_head.py |
| scripts/blender/make_groom_authoring_blend.py | scripts/blender/_archive/make_groom_authoring_blend.py |
| scripts/blender/make_test_groom.py | scripts/blender/_archive/make_test_groom.py |
| scripts/blender/mesh_spans.py | scripts/blender/_archive/mesh_spans.py |
| scripts/blender/probe_groom_exporter.py | scripts/blender/_archive/probe_groom_exporter.py |
| scripts/blender/probe_modifier_api.py | scripts/blender/_archive/probe_modifier_api.py |
| scripts/blender/repoint_demo_groom.py | scripts/blender/_archive/repoint_demo_groom.py |
| scripts/hair_stage.py | scripts/_archive_products/hair_stage.py |
| scripts/hair_variants.py | scripts/_archive_products/hair_variants.py |
| scripts/hero_face/capture_hero_pie.py | scripts/hero_face/_archive/capture_hero_pie.py |
| scripts/hero_face/plot_landmarks.py | scripts/hero_face/_archive/plot_landmarks.py |
| scripts/hero_face/run_pie_probe.py | scripts/hero_face/_archive/run_pie_probe.py |
| scripts/hero_face/likeness/axis_test.py | scripts/hero_face/likeness/_archive/axis_test.py |
| scripts/hero_face/likeness/contact_sheet.py | scripts/hero_face/likeness/_archive/contact_sheet.py |
| scripts/hero_face/likeness/env_check.py | scripts/hero_face/likeness/_archive/env_check.py |
| scripts/hero_face/likeness/frame_signal_floor.py | scripts/hero_face/likeness/_archive/frame_signal_floor.py |
| scripts/hero_face/likeness/hair_color_measure.py | scripts/hero_face/likeness/_archive/hair_color_measure.py |
| scripts/hero_face/likeness/hero_closeups.py | scripts/hero_face/likeness/_archive/hero_closeups.py |
| scripts/hero_face/likeness/shoot_sequence.py | scripts/hero_face/likeness/_archive/shoot_sequence.py |
| scripts/hero_face/likeness/solo_shots.py | scripts/hero_face/likeness/_archive/solo_shots.py |
| scripts/hero_face/likeness/three_panel.py | scripts/hero_face/likeness/_archive/three_panel.py |
| scripts/hero_face/likeness/verify_dna_edit.py | scripts/hero_face/likeness/_archive/verify_dna_edit.py |
| scripts/trellis/_forge_generate_body.py | **RESTORED 2026-09-16** — the "unreferenced" verdict was WRONG: `scripts/trellis/run_forge.sh` calls it (the guard-marker edit in the same change set moved the call from :45 to :51 — cited by name, not line, for exactly that reason) (the reference check greped .py importers only, never shell scripts). A sweep of all 45 archived entries against .sh/.txt/.json/.md referencers found only two other hits, both prose, both repointed (recipes/church_materials.json, recipes/character.json). Lesson: a reference check that only reads one language's call sites is not a reference check. |
| scripts/trellis/render_mesh_views.py | scripts/trellis/_archive/render_mesh_views.py |

## §3b — landscape scripts never referenced (14) — reason: uncalled, untested, unreferenced

Note on count: the audit doc's §3b header reads "13 + 3 one-offs" but the doc
enumerates only 11 `scripts/` files + 3 `_verify` one-offs = 14. Only the
explicitly named files were moved (moving un-enumerated files would defeat the
per-file reference check). The "13" is a miscount in the audit doc's header.

| origin | destination |
|---|---|
| scripts/census_rollup.py | scripts/_archive/census_rollup.py |
| scripts/ground_crop.py | scripts/_archive/ground_crop.py |
| scripts/ground_station_pick.py | scripts/_archive/ground_station_pick.py |
| scripts/kit_measure_v2.py | scripts/_archive/kit_measure_v2.py |
| scripts/rebuild_sample_modules.py | scripts/_archive/rebuild_sample_modules.py |
| scripts/rederive_shadow_band.py | scripts/_archive/rederive_shadow_band.py |
| scripts/rejudge_sky_depth.py | scripts/_archive/rejudge_sky_depth.py |
| scripts/scan_tile_derive.py | scripts/_archive/scan_tile_derive.py |
| scripts/void_differential.py | scripts/_archive/void_differential.py |
| scripts/c0_run_stage.py | scripts/_archive/c0_run_stage.py |
| scripts/verify_doc_conservation.py | scripts/_archive/verify_doc_conservation.py |
| _verify/20260831_coast_benchmark/render_preview.py | _verify/20260831_coast_benchmark/_archive_scripts/render_preview.py |
| _verify/20260831_spike_photo2landscape/render_preview.py | _verify/20260831_spike_photo2landscape/_archive_scripts/render_preview.py |
| _verify/20260901_overnight/make_comparison.py | _verify/20260901_overnight/_archive_scripts/make_comparison.py |

## §3c — payloads failing the date test (7 of 41) — reason: last commit before 2026-09-08

Date test (`git log -1 --format=%cs`): last-touch BEFORE 2026-09-08 -> archive;
2026-09-08 or later -> keep. Named exceptions kept regardless of date. Of the 41
listed payloads, these 7 predate the cutoff and are not exceptions; the other 34
stay in place. Full table in the D-2 report.

| origin | last commit | destination |
|---|---|---|
| scripts/payloads/bench_dump_wp.py | 2026-09-05 | scripts/payloads/_archive/bench_dump_wp.py |
| scripts/payloads/bench_probe.py | 2026-09-05 | scripts/payloads/_archive/bench_probe.py |
| scripts/payloads/hlod_clear_invalid.py | 2026-09-05 | scripts/payloads/_archive/hlod_clear_invalid.py |
| scripts/payloads/hlod_default_probe.py | 2026-09-05 | scripts/payloads/_archive/hlod_default_probe.py |
| scripts/payloads/hlod_pick_cell.py | 2026-09-05 | scripts/payloads/_archive/hlod_pick_cell.py |
| scripts/payloads/hlod_runtimehash_probe.py | 2026-09-05 | scripts/payloads/_archive/hlod_runtimehash_probe.py |
| scripts/payloads/save_cost_probe.py | 2026-09-05 | scripts/payloads/_archive/save_cost_probe.py |

## Kept because still imported

None. No moved file was imported or invoked by any other file; no move had to be
restored. (Recorded per the D-2 import-safety requirement — this section exists
so its emptiness is itself the evidence.)
