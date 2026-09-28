# Pre-Brief-4 closure list — 2026-09-15 (v2, supersedes v1 of the same date)

Scope, restated from Ryan: the audit's purpose is to CLEAN THE PIPELINE — verify every lever against UE 5.8, harvest
historical work that speeds things up, and remove historical work that misleads Claude Code. **All of it completes
before Brief 4. Nothing is "alongside".** The only items that stay deferred are ones a later brief will physically
undo (foliage regeneration, the Merged/Instanced HLOD rebuild) or that a standing ruling already parks.

Every Claude Code prompt in this list is checked against the 5.8 documentation (or the live cvar enumeration) BEFORE
it is sent, and each item carries its doc basis in the `basis` column: **Doc** (Epic 5.8 documentation, cited in
AUDIT.md), **Live** (research/audit/inputs/cvars_5_8_live.txt), **Project** (measured in the corpus), **Ruling**.

## 0. Rulings that unblock the BLOCKED rows (issued here)

| ruling | resolves | text |
|---|---|---|
| **R-SHADEBAND** | S-6, D-6, F-R2, H-11 | The band belongs to the CURRENT white point by construction. `python research/brief3/scripts/shade_reference.py --white 3415.7` → **2.254–3.029**. Derived by the desk 09-15; it is "nowhere in the repo" because the handoff never reached the repo (H-21). shade_card_pair.py BAND := (2.254, 3.029) @ 3415.7. The recipe's third pair 2.587–3.764 is STRUCK (FinalImage is not the band's domain). Whenever white_temp_k moves, this command runs first. |
| **R-GATE** | S-11, D-7 | Apply the porosity model (canopy alpha-tested, ~21% ray pass) — it predicted mid_slope and vista inside their spread on stations it was not derived from. Threshold unchanged. |
| **R-WB2x2** | H-10 | Solve white_temp and white_tint jointly (2×2 from the measured slopes), once, on the tone-curve-off FinalImage EXR; record first-order and joint side by side; adopt joint if the card is inside 0.97–1.03 on both axes. |
| **R-O1** | H-20, H-8, H-4 | IncrediBuild: do NOT uninstall. Script archive: staged move to scripts/_archive/ for scripts that are uncalled AND untested AND not named as a CLI entry anywhere; index file; no deletions. brief4-water merge row struck (no branch). Merged/Instanced L1 parents: not rebuilt now — once after Brief 5 (recorded). |
| **R-T4** | C-T4 | Task 4 closes at stage 1 + finding (lighting structure; shadow candidates do not reach the render). The 4–10 m band moves to Brief 5 understory. |
| **R-HERO** | H-18 | Three HeroStage_* DirectionalLights live in the world level: read back per light `intensity`, `affects_world`/visibility, `atmosphere_sun_light`, `atmosphere_sun_light_index`, `lighting_channels`, `cast_shadows`. **Doc:** a DirectionalLight with `atmosphere_sun_light` True competes for one of the two supported atmosphere-light slots; any enabled directional light lights the scene unless channels exclude it. One PPI0 capture with all three disabled vs baseline; ≥0.5% luma difference anywhere → they are disabled for the bench by ruling and every grade number since 09-13 is re-read. |
| **R-AUDIT-COMPLETE** | scope | Audit Passes 2–5 and the Pass 4 rewrite are MUST. Brief 4 does not open until every governing document line traces to a script, a recipe value, a sidecar, a doc, or a ruling in force; every misleading historical line is archived with the date it lost its trace; every historical finding is ruled APPLY / OBSOLETE / WRONG. |

## 1. MUST — in execution order

### Block A: make the repo safe to work in (CC session 1)
| # | item | owner | acceptance | basis | from |
|---|---|---|---|---|---|
| A-1 | Repair STATE.md (header still claims disk gate tripped / perf blocked); index OPEN.md + PROGRESS.md; offline doc checks green | CC | check_docs green; STATE.md matches 4eba24e3 / 9a561d07 / 53867f96 | Project | H-1, H-3 |
| A-2 | Place RESEARCH_DESK_HANDOFF_2026-09-15.md → research/desk/, AUDIT.md + this file → research/audit/ | RYAN | present, indexed | — | H-21 |
| A-3 | R-HERO read-backs + discriminator capture | CC | table per light; luma delta; ruling applied if triggered | Doc | H-18 |
| A-4 | apply_lighting: the 7 remaining no-read properties read back | CC | 8/8 | Doc (DirectionalLight/SkyLight/Fog property names — Python API) | P1-11, D-3 |
| A-5 | EXR look instrument run once; config dumped under --linear / PPI0 / depth; sidecar `instrument` field {ppi0, finalimage_linear, finalimage_look, truth}; 09-14 grade_resolve label corrected | CC | V-6 closed; sidecar field present from now on | Doc (MoviePipelineImageSequenceOutput_EXR; pass high_precision_output) | S-4, S-5, V-6, D-4, D-5 |
| A-6 | Joint WB solve (R-WB2x2) on EXR FinalImage | CC | card 0.97–1.03 both axes | Doc (white balance mode, tint axis) + Project | H-10 |
| A-7 | Shade pair on the 09-13 instrument vs 2.254–3.029 | CC | verdict with white point beside it | Ruling + Project | S-6, D-6 |
| A-8 | Content gate porosity model (R-GATE) applied; predictions re-derived; read back vs last ten captures | CC | near_ground not refused without cause | Project | S-11, D-7 |
| A-9 | Register hygiene batch: pre-09-13 caveat naming both mechanisms (eye adaptation + sky-light time-slicing — Doc); S-7 slope note; F-4 "?"→195; V-5 AA prose; older probe sets to the two-control standard; AUDIT §6 line (done desk-side) | CC | each line present; probes conform | Doc/Project | P1-2, F-R4, S-7, F-4, V-5, P1-5, FP-4, H-19 |

### Block B: close Brief 3 on verified instruments (CC session 2)
| # | item | owner | acceptance | basis | from |
|---|---|---|---|---|---|
| B-1 | Task 5 acceptance on uniform-4096: vista + mid_slope on PPI0, 300 m–1 km contrast vs fog_budget ±30%; proxy-vs-real albedo ±15% per layer | CC | both tables; FAIL is a finding | Project (fog model Doc-confirmed) | C-T5c, C-T5d |
| B-2 | ⛔ STRUCK BY RULING 2026-09-15: no A/B, no rebuild. The perf budget is ABSOLUTE and 4096 PASSES it (9a561d07); the isolated cost stays unmeasured and does not need to be measured. Pass-2 deltas tagged HISTORY (confounded). Premise corrected: old bake 1024 (2 m/texel), not 256. | RYAN | — | Ruling | H-5 |
| B-3 | Brief 1 detail threshold at 512 m reported + register row | CC | angular_budget_512 reported | Project | P1-10, D-1 |
| B-4 | Cloud_GlobalCoverage 0.1 capture with parameter read-back (Q17) | CC | sky fraction vs parameter recorded | Project (MI parameter) | P1-9, D-2 |
| B-5 | Precedence null pair (one dev capture) | CC | frame instrument conclusive or retired | Project | D-10 |
| B-6 | Re-census with the four landscape HLOD proxy properties | CC | ED values beside 4096/SPECIFIC_SIZE | Project | S-10, D-8 |
| B-7 | Brief 3 send-back complete | CC → DESK | folder complete; desk marks CLOSED | — | C-SB |

### Block C: the audit proper (DESK, interleaved with A/B; needs history_diffs.txt from Ryan NOW)
| # | item | owner | acceptance | from |
|---|---|---|---|---|
| C-1 | Pass 2 — 307 properties by class vs 5.8 Python API: semantics, deprecations, enum values | DESK | verdict per property class in AUDIT §11 | AUDIT board |
| C-2 | Pass 3 — 973 scripts vs their own claims: every threshold's provenance; every instrument's positive+negative control; the 899 untested / 620 uncalled classified KEEP / ARCHIVE / RETIRE per R-O1 | DESK | script_verdicts.json + archive index | AUDIT board, H-13 |
| C-3 | Pass 5 — the 401 remaining UNAPPLIED findings read in their source paragraphs; each ruled APPLY / OBSOLETE / WRONG; APPLY rows become tasks in Block D | DESK | findings_rulings.json | AUDIT §4 |
| C-4 | Pass 4 — rewrite: CLAUDE.md, STATE.md, LESSONS.md, RECIPES.md, both REGISTER_ADDENDA, skills. Every surviving line traces (doc URL / script:line / sidecar / ruling id); untraceable lines → docs/archive/<file>_<date>.md with the date they lost their trace; contradictions resolved by reading (finder recall 40%); the 23 stale plans handled by keying waivers to consumed fields | DESK drafts, CC applies | traced set + archive list + diff | AUDIT §3/§7, E-4 |
| C-5 | Lever inventory recall: Pass 3's reading names any writer shape the scanner misses; scan v4 if any found | DESK → CC | inventory regenerated | H-13 |

### Block D: apply the audit (CC session 3–4)
| # | item | owner | acceptance | from |
|---|---|---|---|---|
| D-1 | Apply Pass 4 rewrite; archive moves; plan waivers re-keyed; check_docs green | CC | suite green incl. plan freshness | C-4 |
| D-2 | Script archive per R-O1 + Pass 3 verdicts | CC | index committed; nothing deleted | C-2 |
| D-3 | Apply every Pass 5 APPLY finding (known so far: floor gate F-1/E-2; cold replay scheduled F-2/E-3 as a Brief 5 acceptance; slot-count check F-3) | CC | each with a read-back | C-3 |
| D-4 | Planting-field contract: spec + schema + script (regeneration itself stays gated until the water carve) | CC spec, DESK review | contract file + selftest | E-1 |
| D-5 | Perf-stall root cause (procdump approved; editor-vs--game control first) | CC | cause named or retired | H-7 |
| D-6 | 1024→32 read-back mechanism: cold-load re-read, source + platform in one payload | CC | mechanism named | H-9 |
| D-7 | Temporal tool (tile-wise motion compensation) delivered | DESK | selftest + run on dolly frames | tools list |
| D-8 | Desk marks the audit CLOSED in AUDIT.md; Brief 4 opens on Ryan's M-12 ruling | DESK/RYAN | — | — |

### Ryan
| # | item |
|---|---|
| R-1 | A-2 file placement (now) |
| R-2 | history_diffs.txt to the desk (now — Block C-4 needs it) |
| R-3 | Brief 4 ruling: lakes A/B/C, south river, carve vs chain-of-pools (any time before D-8) |

## 2. DEFERRED by ruling (will be physically undone or is parked by a standing ruling)
| # | item | to | from |
|---|---|---|---|
| X-1 | Foliage regeneration; cold replay acceptance | after the Brief 4 carve / Brief 5 | F-2, E-3 |
| X-2 | Merged + Instanced HLOD rebuild (256 stale L1 parents) | once, after Brief 5 | H-8 |
| X-3 | Delete the two inert HLOD layers | in D-1 (archive session) — moved from deferred to MUST | H-1 |
| X-4 | What dirtied Merged 09-13 | moot after X-2 | H-12 |
| X-5 | The 0.797 stage | cancelled at the card; logged | H-14 |
| X-6 | Snow/ForestFloor 0 px at Bench_ground; Q6/Q9/Q10/Q11 | Bench_ground re-stations in Brief 4 (lake A) | H-15 |
| X-7 | Q16 range vs SetupHLODs; 768 m memory | Brief 5 | H-16 |
| X-8 | Brief 2c Lumen far-field | standing ruling | H-17 |
| X-9 | What broke XGE | curiosity; immune via ini | H-6 |
| X-10 | Task 4 near-bin band | Brief 5 understory (R-T4) | C-T4 |

## 3. Lost overnight items bound (closes B-4…B-13)
B-4 ll_must → 4 sites (done) · B-5 LODBias/probes (done; older probes → A-9) · B-6 verify_cold_boot (done) · B-7 content gate model (found → A-8) · B-8 register (done) · B-9 EXR flag (done → A-5) · B-10 buffer/instrument field → A-5 · B-11 EXR run → A-5 · B-12 shade pair → A-7 · B-13 re-census → B-6.

## 4. Counts
MUST 9 + 7 + 5 + 8 = 29 (CC 20, DESK 7, joint 2) · Ryan 3 · DEFERRED 10 · rulings 7 · STATUS rows 115/115 accounted.
Estimated: CC 4 sessions; DESK 4–5 rounds; Brief 4 opens after D-8.
