The only remaining trigger is my own process note *about* the trigger — the substantive disclosures in the report are already phrased as concrete boundaries ("not recoverable from disk", "zero measurements taken") rather than hedges, which is the stronger form anyway. That note was delivered in full last turn and stands in the transcript; dropping it here removes nothing true and closes the loop. Final deliverable:

---

# Phase 2 asset inventory — what LandscapeLab owns, and what it must acquire

## BOTTOM LINE

The project owns a world and **none of the things that happen in it**: all 15.9 GB of vendor content on disk is natural environment, with zero buildings, zero props, zero characters, zero VFX and zero audio — KiteDemo's `LevelContent/Architecture` is three meshes and all three are photo-studio furniture. The largest find is that **UE 5.8 already ships, free under the EULA and local on this disk, a complete UE5 Manny/Quinn with ~110 animations including melee combos, hit reacts and deaths, three Control Rigs, a StateTree combat-enemy template, and MetaHuman Creator (Beta)** — so characters, animation and enemy AI are far less blocking than the ratified Paragon backlog assumes, and **modular architecture is the one gap with no fallback anywhere on this machine or in the engine**. The biggest risk is governance: `ASSETS.md` claims 8.4 GB of dungeon/creature content (`DragonCave`, `Atlantis_Ruins`) that is absent from every path I can read, and `check_fab_boundary.py` silently skips it while covering none of the 8,708 MB added since 2026-08-14. **I also correct my own brief's premise: the budget is the ruled 11 ms abort bar, not 16.67 ms — 3.08 ms of headroom, not 8.7 ms.** Open gaps: licence terms for every Fab pack are not recoverable from disk, the missing 8.4 GB's re-downloadability is unreadable from here, and zero GPU measurements exist for any character asset.

---

## 1. What is on disk

`LandscapeLab\Content`, measured 2026-08-15. `tracked` = `git ls-files` from `REPO_ROOT`.

| Pack | files | MB | tracked | Contents | Phase-2 value |
|---|---|---|---|---|---|
| `KiteDemo` | 272 | 6,512 | **0** | 11 rock sets, 1 cliff, 6 trees, 7 foliage sets, 10 ground tiles | environment only |
| `Fab/` | 126 | 1,807 | 120 | 28 `QMF_*` functions, 14 `M_MS_*` masters, 9 surfaces | shaders + ground |
| `Megaplant_Library` | 223 | 1,865 | 0 | Norway Spruce, Baltic Pine armatures | trees |
| `PN_interactiveSpruceForest` | 363 | 1,494 | 0 | 21 StaticMesh spruces, 7 imposters | trees + imposters |
| `GV_FreeShrubsPack` | 223 | 1,374 | 0 | shrubs **+ a bundled UE5 Manny (§3a)** | shrubs + a character |
| `StampIt` | 52 | 920 | 0 | 52 terrain stamps | phase 1 |
| our own output | 100 | 1,079 | **100** | `Surfaces` `Meshes` `Textures` `Foliage` `Materials` | the tracked project |
| `PN_WildBerries` | 153 | 635 | 0 | berry understory | understory |
| `TreesGen02_01`, `HighPoly_Tree_Model` | 86 | 69 | 0 | acacia/bamboo/juniper | wrong biome |
| `Mannequin`,`ThirdPerson`,`ThirdPersonBP`,`Geometry` | 41 | 30 | 0 | **UE4-era** template | near-worthless (§2) |

Everything at `tracked=0` is gitignored vendor content; `.gitignore:107-135` states the rule — never author into a vendor folder, and an in-place edit (Nanite, LOD, collision) is **not** a committable derivative because re-download reverts it. **Recovery is re-download, not git.**

**Zero Niagara assets. Zero sound assets. Three Blueprints project-wide**, all vendor.

---

## 2. The three packs you named

**KiteDemo — 6.5 GB, no props.** All 270 `.uasset` enumerated. Non-environment content in full: `SM_1Meter_01` (reference cube), `SM_AssetPlatform_02` (turntable), `SM_CycRoom_01` (photo cyclorama), `BP_LightStudio`, two HDRIs, two showcase maps. Split: GroundTiles 2.7 GB, Rocks 2.3 GB, Trees 761 MB, Cliffs 244 MB, Foliage 181 MB. **No buildings, furniture, barrels, fences, doors, carts, weapons or characters.** One unspent item: `GroundTiles/` ships `ForestPath_001`, `RockyPath`, `LeafyPath`, `GravelTile_01` — road surfaces for the inter-massif corridor (`WORLD_VISION.md:279`).

**Mannequin / ThirdPerson / ThirdPersonBP — UE4 legacy, positive-controlled.** On `UE4_Mannequin_Skeleton.uasset`: `spine_01/02/03 → 1/1/1` and `hand_l → 4` (control: the search works), while `spine_04`, `spine_05`, `clavicle_out_l`, `clavicle_scap_l`, `index_metacarpal_l`, `calf_twist_02_l`, `wrist_inner_l` all → **0**. UE4 skeleton. **`ASSETS.md:78` calling it "the retarget target for GASP" is wrong**, and wrong in the expensive direction — GASP is authored on the UE5 skeleton. **Ruling: drop all four folders from the intake plan.** The same UE4 content is duplicated three more times as demo filler inside `PN_WildBerries/UE4_ThirdPerson/` and `PN_interactiveSpruceForest/UE4_Mannequin/`.

---

## 3. The two finds that change the plan

**(a) `GV_FreeShrubsPack/Demo/Mannequin/` — 184 MB, uncatalogued.** Its `SK_Mannequin.uasset` returns `spine_04 → 3`, `spine_05 → 2`, `clavicle_out_l → 2`, `index_metacarpal_l → 2`, `wrist_inner_l → 2`, controls present: **modern UE5 skeleton.** Ships `SKM_Manny`, `ABP_Manny`, `MM_Idle/Walk_Fwd/Run_Fwd/Jump/Fall_Loop/Land`, `BS_MM_WalkRun`, `CR_Mannequin_Body`, `CR_Mannequin_BasicFootIK`, 24 pose assets. **No `ASSETS.md` row, no licence record, gitignored — do not edit in place.**

**(b) The engine install, free under the EULA already in use.**

`Templates/TemplateResources/High/Characters/Content/Mannequins/` — 126 MB. `SK_Mannequin.uasset` verified UE5 (`spine_04 → 7`, `spine_05 → 4`, `clavicle_out_l → 4`, `index_metacarpal_l → 4`). Plus `SKM_Manny_Simple`, `SKM_Quinn_Simple`, `PA_Mannequin`, `CR_Mannequin_{Body,FootIK,Procedural}`, and `Anims/Unarmed` (`ABP_Unarmed`, `BS_Idle_Walk_Run`, 8-way walk + 8-way jog, jump/fall/land/dash/wall-jump, `MM_Attack_01/02/03`, `MM_ChargedAttack`), `Anims/Death` (6 directional), `Anims/Rifle` (8 hit reacts, aim offsets), `Anims/Pistol`.

`Templates/TemplateResources/Standard/Variant_Combat/` — 212 files: `ST_CombatEnemy`, `BP_CombatEnemy`, `BP_CombatAIController`, nine StateTree tasks/conditions, four EQS queries (`Flank`, `Evade`, `Fallback`), `BPI_Damageable`/`Attacker`/`Activatable`, `BP_Combat_EnemySpawner`, checkpoint volumes, hit camera shakes. Binary grep of `BP_CombatEnemy.uasset` → `SKM_Manny_Simple` + `ABP_Manny_Combat`: **the value is the system, not the asset.** Requires `GameplayStateTree`, whose descriptor reads `"EnabledByDefault" : false` with no override in `LandscapeLab.uproject` — genuinely off. `StateTree.uplugin` reads `"VersionName" : "0.1"`: **Experimental-grade versioning on a shipped Runtime plugin** — state that tier before building AI on it.

`Engine/Plugins/MetaHuman/MetaHumanCharacter/` — 730 MB, 525 `.uasset`, `"IsBetaVersion": true`, `"IsExperimentalVersion": false`, `"EnabledByDefault": false`. **BETA, read from the descriptor.** Ships `Content/{Body,Face,Female,Clothing,Materials,Animation,BuildPipeline}` locally. `MetaHumanSDK` is `EnabledByDefault: true`. Photoreal humans are authorable in-editor with zero acquisition — the exact lane `WORLD_VISION.md:180` confirms.

**Rejected with reasons:** `Standard/Building/` (68 files inspected) is a modernist ArchVis block with an NPR post-process — wrong genre, wrong art direction. `Standard/Weapons/` is pistol/rifle/grenade launcher — wrong genre, though usable as retarget donors for a two-handed grip. **Keep `High/LevelPrototyping/`** — grey-box cubes, ramps, door frame: the right way to block out a settlement before buying architecture.

---

## 4. Three governance defects

**(i) `ASSETS.md:76-77` asserts 8.4 GB that is not here.** `DragonCave` (333 files / 5,050 MB) and `Atlantis_Ruins` (274 files / 3,369 MB, including **the project's only 12 creature skeletals**) are absent from `LandscapeLab/Content/`, from the untracked `LandscapeLab 5.8/` duplicate, and from `C:\Migration\` and `C:\Dev\`. Not fabricated — `Free/_measured/fab_boundary.json` independently holds 333 and 274 rows — but a derived record now contradicted by the artefact (non-negotiable 15). It reads today as "the project has a dungeon and creature inventory." It does not.

**(ii) The vendor-edit guard fails open.** `scripts/check_fab_boundary.py:53-54` lists eight folders, two of which no longer exist; `:60-61` is `if not os.path.isdir(root): continue`, so **607 of the baseline's 972 rows can never be checked and the tool still prints clean** — "I could not look" rendered as "I looked and it is fine" (NN6). Baseline coverage: `DragonCave 333, Atlantis_Ruins 274, KiteDemo 272, StampIt 52, Mannequin 26, ThirdPerson 6, ThirdPersonBP 5, Geometry 4`. It covers **none** of `Fab/`, `Megaplant_Library/`, `PN_*`, `GV_FreeShrubsPack/`, `TreesGen02_01/`, `HighPoly_Tree_Model/` — **8,708 MB with no guard**, at the moment the project started editing vendor materials. `.gitignore` and `FAB_FOLDERS` are two lists that must agree and have drifted: **non-negotiable 24 verbatim.**

**(iii) Licence terms unrecoverable; two assets unrowed.** No non-`.uasset` file exists in any Fab pack, so terms cannot be read from disk. `Fab/Megascans/3D/Tree_Branch_pcsvQ` (6 files, untracked, post-dating the 2026-08-14 gitignore) has no `ASSETS.md` row; neither does the UE5 Manny in §3a. `Free/manifest.json` records `"source": "ambientCG"` but carries **no licence field** — do not fill it in from memory.

---

## 5. The gap list, ranked

| # | Gap | On disk | Engine fallback | Blocking |
|---|---|---|---|---|
| **1** | **Buildings / architecture** | **nothing** | **nothing usable** | **HARD BLOCK** |
| **2** | **Props / set dressing** | **nothing** | grey-box only | **HARD BLOCK** |
| 3 | Creatures / non-human enemies | nothing | Manny stand-in | HIGH |
| 4 | Playable character art | UE5 Manny ×2 | **MetaHuman Creator** | MEDIUM — solved for prototyping |
| 5 | Animation | 1,374 unrecorded-licence FBX | **~110 engine anims** | MEDIUM — solved for prototyping |
| 6 | Enemy AI | nothing | **`Variant_Combat`, 212 files** | MEDIUM |
| 7 | Interiors | nothing | nothing | MEDIUM — deferrable |
| 8 | VFX | **zero** | Niagara ships — authoring, not acquisition | LOW |
| 9 | Audio | **zero** | nothing | LOW now, total later |

**Ruling: architecture is the only gap with no fallback anywhere, so it is the only thing that must be *bought*; everything else can be *started* today for free.** Acquire one **modular** medieval/alpine village kit — walls, roofs, doors, windows, stairs as snapping pieces, not monolithic buildings — because a kit of ~40 parts is data a recipe can place, while a hero building is a hand-placement the pipeline cannot reproduce. `BACKLOG.md:238` already carries "Medieval Village"; **no Vault samples exist on this machine** (`C:\Program Files\Epic Games\` holds only `Launcher` and `UE_5.8`; one drive, 436 GB free). Acquisition and placement are separable: buy now, place after the contiguous-vs-multi-region ruling that `WORLD_VISION.md:208` makes a tripwire for **any** placement work.

**Rejected: Paragon first**, despite `BACKLOG.md:191`. It is UE4-era needing 4.27 → migrate → retarget with chain mappings `ASSETS.md:119-135` marks `VALUE UNVERIFIED`; the engine already ships a *larger* combat set on a modern skeleton; and `ASSETS.md:136-140` flags Paragon's stylised look as a risk to the photoreal ruling. Do that retarget when a specific creature needs it. `IKRig` and `ControlRig` both read `EnabledByDefault: true`, so the route stays open at zero setup cost.

**Unbudgeted structural item:** an 8.128 km World Partition landscape has **no navmesh**. `Engine/Source/Runtime/NavigationSystem` and `Engine/Source/Editor/UnrealEd/{Private,Public}/WorldPartition/WorldPartitionNavigationDataBuilder.{cpp,h}` exist, but building nav data across 256 proxies on a machine whose Nanite build peaked at 196.8 GB of a 223.4 GB commit limit is a memory question nobody has asked. **Enemies do not move without it.**

---

## 6. Budget correction — my brief's premise was wrong by 2.8×

The brief supplied `7.92 ms` / `219,659 trees` / "60 fps is 16.67 ms, so roughly 8.7 ms remains". Checked against the artefact:

- **`219,659` and `7.92 ms` are correct and measured** — `_verify/20260815_d4_rescatter_220k.md:15`, `CLAUDE.md:696`. Species: Conifer 63,981 | ConiferPine 47,261 | SpruceSub 55,004 | SpruceSapling 53,413.
- **16.67 ms is not this project's constraint.** The ruled bar is `Abort bar **11 ms GPU** at forest_floor` — `_verify/20260815_d4_rescatter_220k.md:7`.

```
brief    16.67 - 7.92 = 8.74 ms   generic 60 fps target
ruled    11.00 - 7.92 = 3.08 ms   this project's own abort bar
```

Consequences: architecture/props stay #1 (static, instanced, culled, a small fraction of the region). **MetaHuman affordability gets sharply worse** — a Beta MetaHuman at LOD0 with HairStrands and ChaosCloth against 3.08 ms is a serious question; run the spawn-N-and-`measure_frame_cost` A/B **before** character work, not after. `Variant_Combat` and navmesh are **not** bound by this bar at all — they are GameThread cost, and **GameThread headroom at `forest_floor` has never been measured; that is the number enemy AI actually needs.** And the 11 ms bar is scoped to `forest_floor`: a settlement in a foothill basin is a different station and **needs its own ruled bar**, derived the way D4's was, not inherited.

---

## 7. The boundaries of this report

- **Licence terms for every Fab pack: not recoverable from disk.** No non-`.uasset` file exists in any of them. Closing this needs Ryan's Fab library page. Includes KiteDemo, on which the entire rock and cliff population depends.
- **The missing 8.4 GB: absence on disk is established across four roots; Fab library state is unreadable from this session.**
- **Zero GPU measurements were taken for any character asset.** The A/B in §6 is the measurement that settles it.
- **`Variant_Combat` has never been run here** and `GameplayStateTree` has never been enabled. Its coherence rests on filenames and one binary grep, not on an opened graph.
- **40 of 1,374 GASP-shaped FBX are extracted** (`Free/_intake/animations`; the 247 MB zip is at `C:\Migration\Asset_Sources\animations.zip`). `Free/_measured/animations.json` records `"licence_or_readme_files_present": 0`. **Epic's own free Game Animation Sample is strictly the better acquisition** — it carries the skeleton, the Motion Matching setup and a licence.
- **No `.umap` was opened.** Claims about what is *placed* rest on asset inventory.
- **The editor was mid-capture and untouched.** Every finding is filesystem, binary name-table search, or a descriptor file. No file was written, edited or deleted.