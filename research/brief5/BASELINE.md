# Brief 5 — density & cost baseline (v3)

**2026-09-20. Read-only against the world except standalone `-game` perf runs
(process-local cvars, restored by exit) and one read-only offscreen editor pass
(closed per R-EDITOR-CLOSE: 0 dirty, 0 processes, world byte-identical to HEAD).**
World `/Game/Alpine8K` at 512 m streaming. Machine-readable:
`research/brief5/input/density_baseline.json`. This v3 re-measures the two
conclusions the desk audit (`BRIEF5_BASELINE_AUDIT.md`) did not accept in v2:
the HLOD GPU share and the density/forest cost. Every delta carries its
`× min_detectable` multiple; anything under 1× is reported "not distinguishable".

Verdict vocabulary: **MEASURED** (delta ≥ 1× min_detectable, control passed) /
**MEASURED-NEGLIGIBLE** (control passed, delta < 1×) / **INCONCLUSIVE** (control
not passed). "Resolved" is not a verdict.

---

## MEASURED

### The noise floor (Task 1) — the gate every delta is quoted against
Five as-is `-game` runs per zone (4K, settle 60 s / window 25 s). GPU p90
`min_detectable_ms = 2 × sd`: **treeline 0.060, plaza 0.040, forest_floor 0.016**.
GPUSceneInstanceCount is **deterministic** across as-is runs (sd 0; treeline
57876, plaza 196553, forest 103162) — which **refutes** the v2 "instance-count
wobble is streaming variance" (audit A5): as-is residency does not wobble; the
v2 −21 % swing was the D2/D4 `grass.DensityScale` lever regenerating grass.

### Forest foliage cost, where the forest is (Task 3) — the number that replaces the withdrawn one
The v2 foliage deltas were measured where almost no trees are on screen (audit
A4: treeline 0 / plaza 903 visible live trees of 185,385). v3 measures at a
**derived `forest_floor` station** (the densest tree cluster, heading swept for
the most in-frustum trees): **1844 in-frustum-in-cull trees** — the *maximum*
achievable at the declared 90° hFOV / 512 m cull. **5000 is not reachable on this
forest** (~0.005 trees/m²); 1844 is reported as the honest max, not padded.

3 as-is + 3 foliage-hidden runs, `--csv-gpu-stats`:
- **Foliage GPU cost = 0.185 ms p90 (11.4× min_detectable — distinguishable).**
  as-is 11.048 (sd 0.008) vs hidden 10.863 (sd 0.026). Control: GPUScene
  103162 → 61714 (41,448 instances removed, deterministic).
- **Where the trees cost (per-pass delta, as-is − hidden):**

  | pass | Δ ms | as-is | hidden |
  |---|---|---|---|
  | LumenReflections | **+0.324** | 1.067 | 0.743 |
  | ShadowProjection | +0.105 | 0.891 | 0.785 |
  | Basepass | +0.086 | 0.309 | 0.223 |
  | Prepass | +0.046 | 0.069 | 0.023 |
  | NaniteBasePass | −0.047 | 0.450 | 0.496 |
  | RenderDeferredLighting | −0.158 | 0.279 | 0.436 |

  The foliage cost is **Lumen reflections + shadows + base/pre pass** — *not*
  NaniteVisBuffer (the Nanite spruce raster is cheap). Some passes go slightly
  negative as Lumen rebalances when foliage is removed.
- **ms per 1000 in-frustum-in-cull trees = 0.100** (upper bound — the delta also
  removed grass and off-frustum in-cull trees; attributing all of it to the 1844
  visible trees). This replaces the withdrawn off-frustum `ms/10k`, and is ~10×
  larger because it counts only trees that actually draw.
- Per-species (Nanite spruce vs card species): **not measurable in `-game`** — no
  process-local per-FoliageType lever; the hide is all-foliage. Not invented.

### Per-pass frame attribution (Task 1 carried from v2 — holds as *pass* attribution)
treeline top passes: VolumetricCloud 11.9 %, NaniteVisBuffer 11.7 %, ShadowDepths
9.5 %, TSR 8.4 %, Post 7.4 %. plaza: NaniteVisBuffer 19.2 % (buildings) + shadows
18.6 %. This splits by render pass, never by content, so it cannot say "this is
(not) the forest" — but the fixed frame cost is atmosphere + Nanite raster +
shadows + TSR/post.

### The census (Task 1/3) — 185,385 trees, per-station visible
Conifer 54,599 / ConiferPine 40,326 / SpruceSub 46,841 / SpruceSapling 43,619.
In-frustum-in-cull (base-point) at the declared 90° camera: **treeline 0, vista
34, plaza 903, main_street 919, forest_floor 1844**. (The census now also reports
a base→top *segment* count — a tree whose base is below frame but crown is on
screen; treeline recovers only 2 that way.) Occlusion out of scope (upper bound).

### What each species is rendered as, by distance (Task 4a/4c)
- **LOD/billboard/imposter switch distances** (header-verified
  `D = 1.778·R/ScreenSize`, all LOD/view scales = 1.0). **Every switch is ABOVE
  the 40 px detail floor** (audit A8, quantified):

  | species | R (cm) | H (m) | billboard/imposter LOD | engages at | px tall there |
  |---|---|---|---|---|---|
  | ConiferPine | 1210 | 22.1 | LOD3 ss 0.168, 32 tris (billboard) | **127.8 m** | 332 |
  | SpruceSub | 837 | 16.7 | LOD4 ss 0.17, 6 tris (imposter) | **87.5 m** | 367 |
  | SpruceSapling | 276 | 4.5 | LOD3 ss 0.10, 326 tris | 49.1 m | 177 |
  | Conifer | 1547 | 29.3 | Nanite, 1 LOD (fallback 2335 tris) | n/a | — |

  So "seen only at DETAIL" (a *pixel* band) hides that the *mesh* drops to cards
  at 88–128 m while the tree is still hundreds of px tall.
- **HLOD proxies (Task 4c, audit A7 answered).** The two layers are
  `Alpine8K_HLODLayer_Instanced` = **INSTANCING** (ISMs at the source meshes'
  *lowest* LOD) and `Alpine8K_HLODLayer_Merged` = **MESH_APPROXIMATE** (one
  approximate mesh per cell) — **not** "merged Nanite proxies" as v2 said.
  **Between 512 m and ~2 km each species renders as its lowest-LOD instance**
  (ScotsPine 32-tri billboard, spruce_half 6-tri imposter, sapling 326-tri, and
  the Norway Spruce as its **2335-tri Nanite fallback — not the full Nanite
  mesh**), then as a single merged approximate proxy per cell beyond.

### HLOD cell distances (Task 2d — audit A1 fixed)
Derived from the grid index in each actor label (`centre = (idx+0.5)·cellsize`,
cellsize(L) = 256 m·2^L), **not** `get_actor_location` (which is degenerate for
Instanced HLOD — the source of v2's identical-distance artefact). Distances now
vary per cell and station: nearest cell centre treeline 105.9 / plaza 120.9 /
vista 192.4 / forest_floor 0.0 m; treeline Merged_L0 p10/p50/p90 = 1327/3450/5928
m. The v2 "same three distances for every actor" is refuted.

---

## MEASURED-NEGLIGIBLE / lever inert

**The density lever cannot move — or even test — this forest.** `foliage.DensityScale`
read back at 2/4 but GPUScene did not rise (placed HISM is capped at the authored
count), and — the definitive read-back (Task 4d) — **all four FoliageTypes have
`enable_density_scaling = False`**, so `foliage.DensityScale` (a scalability
*down*-lever, opt-in per type) has **no effect** on these trees at all (audit B3).
No zone approaches budget at any scale; the lever cannot test a denser forest.

---

## INCONCLUSIVE

### HLOD proxy GPU *share* — the millisecond number (Task 2)
**Not measurable inside the fence; verdict INCONCLUSIVE (was v2 "RESOLVED —
negligible", reverted by audit A1/A2).**
- **`-game` positive control FAILED.** as-is vs `wp.Runtime.HLOD 0` runs are
  byte-identical on every render-side counter (GPUSceneInstanceCount,
  SceneCulling/NumStaticInstances, ActorCount/WorldPartitionHLOD, GPUTime). The
  command is an `FAutoConsoleCommand` (HLODRuntimeSubsystem.cpp:149) delivered via
  startup `-ExecCmds` (→ `GEngine->DeferredCommands`, one-shot, fires before the
  far cells stream); it cannot re-fire post-settle without an ini/asset/Python
  change (outside the fence). The commands *do* run (BugItGo executed; each
  echoed as `LogEngine: Warning: <cmd>` — so the v2 "deferred/never applied" was a
  misread of the normal echo). Detail: `hlod_task2_gamepath.md`.
- **Editor control also fails.** At full editor residency the proxies are not
  drawn (real cells render), so the v2 actor-hide's 0.015 ms delta is the control
  *failing* (audit A2), not a measured zero. Forcing proxy render needs
  region-unloading and still gives editor ≠ `-game`.
- **What this leaves:** the composition and geometry are measured (above), so the
  far forest is cards + a 2335-tri fallback + approximate meshes covering few
  pixels beyond 512 m — cheap *by construction* — but the exact GPU share/pixel
  fraction is still open (item-8 `-game` MRQ territory).

---

## Carried deputy outputs (unchanged, honest about limits)
- **Coverage** (`reference_coverage.json`): alpine target ≈ grass 0.40 (lower
  bound), 2 concept refs only, no photos on disk.
- **Dolly** (`dolly_manifest.json`): 360 E4 frames, 356 consecutive pairs; **267
  usable** excluding the FAILED 2026-09-07 actor-heading set (89 pairs).
- **PCG** (`PCG_NOTES.md`, revised v3): evaluate-don't-migrate holds; injection
  kinds are **two** (exclusions = Local, custom biome data = Global); Biome
  runtime radii 48/96 m; the water mask maps to a **Filter**, not injected data.
- **Replay** (`replay_inventory.json`): 13 recipes, all inputs present, 1
  selftest pass / 12 none.

---

## Levers table — header:line filled in (was doc-URL-only)

| lever | verified at | value/finding |
|---|---|---|
| `wp.Runtime.HLOD` | HLODRuntimeSubsystem.cpp:149-187 | `FAutoConsoleCommand` (a command, no echo); acts only on game worlds; sets static `WorldPartitionHLODEnabled` (:147). |
| `-ExecCmds` dispatch | UnrealEngine.cpp:2552 (+:2548 `-EXEC=`) | → `GEngine->DeferredCommands`, first post-init tick; runs post-PlayerController but one-shot (pre-stream). |
| LOD ScreenSize → distance | SceneManagement.cpp:966 (fwd) / :980 (inverse) | `D = 1.778·R/ScreenSize` at 4K 90° hFOV (P11 dominates). |
| `foliage.LODDistanceScale` | HierarchicalInstancedStaticMesh.cpp:96 | default **1.0**. |
| `r.StaticMeshLODDistanceScale` | SceneVisibility.cpp:173 | default **1.0** (higher = LODs earlier). |
| `r.ViewDistanceScale` | ConsoleManager.cpp:4435 + DefaultEngine.ini:207 | **1.0** (compiled default AND ini-pinned). |
| `enable_density_scaling` (per FoliageType) | FoliageType.h:591 (read back) | **False** on all four species → `foliage.DensityScale` inert. |
| HLOD `layer_type` | HLODLayer.h:112 (read back) | Instanced = INSTANCING, Merged = MESH_APPROXIMATE. |
| Nanite Foliage (project) | RendererSettings.h:1550 + DefaultEngine.ini:63 | **enabled** (`r.Nanite.Foliage=True`). |

---

## Closing summary for the desk

- **Noise floor**: min_detectable treeline 0.060 / plaza 0.040 / forest 0.016 ms.
- **Forest foliage cost** (the on-screen number): **0.185 ms (11.4×)**, in Lumen
  reflections + shadows + base pass, not Nanite raster; **0.100 ms / 1000 visible
  trees** (upper bound). The withdrawn off-frustum ms/10k is retired.
- **Density lever**: inert — `enable_density_scaling=False` on every type.
- **HLOD share**: **INCONCLUSIVE** (both controls fail inside the fence); but the
  proxies are lowest-LOD ISM (Instancing) + approximate merged meshes, rendering
  beyond 512 m — cheap by construction.
- **Representation-by-distance**: cards engage at 88–128 m, all above the 40 px
  detail floor; recipe LODs ≠ built asset LODs for ConiferPine.

**What the desk may now derive Brief 5 from:** the on-frustum forest foliage cost
(0.185 ms / 0.100 ms per 1000 visible trees, with its noise floor and per-pass
split), the per-species representation ladder and switch distances, the HLOD
proxy *composition* (Instancing lowest-LOD + MESH_APPROXIMATE), and that the
density lever is inert on this world.

**What it still may not:** treat the HLOD proxy GPU *share* / live pixel fraction
as measured — it is INCONCLUSIVE and needs a `-game` MRQ HLOD-toggle pass (item
8). And do not read the forest number as a per-*visible-tree* cost precisely (it
is an upper bound; the delta also removed grass and off-frustum trees), nor
extrapolate density past the authored count (the lever cannot test it).
