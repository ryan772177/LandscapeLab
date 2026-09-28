# FOR_CLAUDE_CODE — Brief 3 tasks

Read CLAUDE.md, then BRIEF.md §0, §3, §4, §5. Tools: `scripts/texel_budget.py`, `scripts/tiling_score.py` (both self-tested; copy into `scripts/`, run each once on a known frame). The depth pass and grey card from Brief 2 are instruments here. One variable per capture set; commit each; every value read back into the sidecar.

Session goal line: **"Brief 3: loading range, card WB, derived layer weights."**

## Task 0 — Loading range (precondition; RISKY-OP CHECKPOINT, branch first)
1. Read back the runtime grid loading range (256 m). Set 768 m (basis: City HLOD0 range; Brief 1 4K detail threshold ~700 m). VERIFY where it lives for UWorldPartitionRuntimeHashSet in 5.8 and whether SetupHLODs must re-run (no BuildHLODs).
2. HLOD0 Instancing layer range → 2 km; approximate layer unchanged.
3. Read back; derived-residency at near_ground and vista must show real landscape/foliage to ≥ 700 m by bounds-centre.
4. Standalone perf (E3 instrument) all four zones; must hold R-PERFBUDGET. If it fails at any zone: 512 m, record, and note that Brief 1's detail threshold moves with it.
5. Recapture vista + near_ground (target class). Report the proxy hand-off distance from residency sets. Lock as R-RANGE with both perf tables.

## Task 1 — Grey-card white balance
1. From the card's R/G and B/G at near_ground, step white_temp (and white_tint for the green axis) at most twice; each step through the recipe, apply_lighting (saves), read back, recapture near_ground.
2. Acceptance: card R/G and B/G within 0.97–1.03. Record `grade.warmth_bias_k = 0` for the bench; a look value is a later ruling.

## Task 2 — Layer set and derived weights (offline first)
1. Schema: eight layers, two weightmaps (meadow, forest_floor, rock, scree, wet_shore, snow, dirt_path, gravel). VERIFY the second-weightmap route for this landscape (layer-info assets / `make_layer_weightmap` extension).
2. `derive_layer_weights.py` over the adopted heightmap + Gaea masks (import_alpinelab_masks outputs) + foliage placement JSON: precedence and formulas from BRIEF §3.4–3.6; snow with the aspect term; forest_floor from crown-blurred instance density; scree from the flow proxy. Every weight's derivation into a sidecar. Selftest on a synthetic heightmap (north/south slope, a cliff, a tree cluster).
3. Import; `LandscapeLayerBlend` height-blend on for every layer (VERIFY LB_HEIGHT_BLEND and per-layer height inputs in make_landscape_material). Recapture all three.
4. Acceptance: forest_floor > 0.8 under the near_ground trees, < 0.1 open; vista snow north-minus-south octant fraction ≥ 0.2 at the same height band (depth+normal pass); meadow/rock edge gradient histogram sharper than the linear baseline.

## Task 3 — Scanned surfaces at derived tiles
1. `texel_budget.py --fov-h 90 --res 3840 2160 --near-m 3 --tex <res>` per layer → tiling_m written from the rule; macro tile 20–50×.
2. Six Megascans/Fab surfaces (mainline may use Fab): meadow, forest floor (needle litter), rock cliff, scree, wet pebbles, snow — hash-pinned in vendor_manifest; imported sRGB albedo / linear normal-rough-height; displacement re-centred.
3. Stochastic/hex tiling on (VERIFY engine material function in 5.8; else the existing macro-variation path at derived strength).
4. Recapture; `tiling_score.py` per depth bin (30–100, 100–300 m) with `--period-px` from the tile's on-screen period at the bin distance and `--threshold` from texel_budget; albedo variation 0.10–0.20.

## Task 4 — Grass appearance
PerInstanceRandom hue/brightness ±8%; card base colour from the underlying layer albedo; taller cards only where meadow > 0.7. Recapture near_ground + dolly (frames kept, unscored). Acceptance: meadow albedo-variation metric rises into band; card mask unchanged.

## Task 5 — Proxy rebuild with sourced settings
HLOD approximate layer: texture sizing automatic-from-draw-distance, geometric-tolerance 0.25 m, capture 2048, roughness 1 / specular 0 on the generated material. Batched rebuild. Recapture vista; depth-bin contrast (300 m–1 km) within ±30% of fog_budget's predicted T.

## Send-back
`research/brief3/for_research/`: near_ground, mid_slope, vista (target, 1920-wide) after Task 3 and after Task 5; weightmap sidecars; tiling and albedo tables; card readings; perf tables from Task 0; REGISTER diff.

Do not touch tree density, culls, budgets, water, or the town. Do not do Brief 2c.
