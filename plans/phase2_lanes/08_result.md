# COMPLETENESS CRITIQUE — Phase 2 domain briefs
*Final. Two corrections from self-audit folded in: §3's confidence is stated rather than implied, and §4's scope is narrowed to what is genuinely unnamed.*

## BOTTOM LINE

**One of eight briefs (`characters`) returned no content, and a second (`quests-data`) returned a schema autopsy instead of the save architecture its domain title names — so the two domains with the largest Phase-2 blast radius are unreviewed.** Of what was delivered, eleven shipping subsystems are named by nobody: audio, UI/HUD, input bindings, **the gameplay camera**, localisation, save/load, cinematics, cook/packaging, in-engine testing, time-of-day lighting, and region-transition loading — the camera omission being the expensive one, since every performance figure this project owns was taken from a parked capture station. The largest under-named risk is that **the whole measurement corpus is editor-viewport-class and four variables change at once the moment a player exists**, with the net sign unknown; `budget` named the missing PIE reading but nobody named the compound effect or made it a gate. The brief whose central premise and central mechanism are both unverified — and the cheapest to settle — is `towns`. I checked 14 engine and repo citations directly; two briefs contain absence-findings drawn from **searching only part of the codebase**, repeating this project's own logged `LandscapeNanite.cpp` near-miss.

---

## 1. WHAT IS MISSING

I grepped `BACKLOG.md` (1,982 lines) for each item. Unless noted, **zero hits** — these are absent from the project's scope valve, not merely unmentioned in the briefs.

### Blocking Phase 2 execution

**1. Input bindings — P0-blocking, and the brief that needs them did not name them.**
`LandscapeLab/Config/DefaultInput.ini` is the stock legacy `[/Script/Engine.InputSettings]` block: 40+ `AxisConfig` lines for Vive and MixedReality hardware, **zero action mappings, zero Enhanced Input mapping contexts**. `EnhancedInput` is `EnabledByDefault: true` in the engine. The `physics` brief's P0 is *"a player exists… walk 1 km along the inter-massif corridor"*. **Walking requires an `UInputMappingContext` and `UInputAction` set; no brief specifies one, names its path, or rules whether it is recipe-generated or authored.** P0 as written cannot execute.

**2. The gameplay camera — HIGH, and it silently undermines the budget.**
No brief mentions a camera system; `Engine/Plugins/Runtime/Cameras` exists here and nobody opened it. Every GPU figure — 7.89 p50, the 5.86 ms terrain floor, the 11 ms abort bar, the D4 219,659-instance ruling — was measured from a static `Capture_*` station at fixed FOV with **the viewport resolution unrecorded** (`budget` flags this itself, at `measure_frame_cost.py:38`). A third-person spring arm with a collision probe, player yaw and raised pivot yields a different frustum, a different Nanite cluster set and a different VSM page load than any station ever measured. `budget` got adjacent to this via its elevated-station test but framed it as aerial readability, not as *the camera the game is played through does not exist and has never been costed*.

**3. The player-to-world contract.** `DefaultEngine.ini` sets **only** `GameDefaultMap=/Engine/Maps/Templates/OpenWorld`. No `GlobalDefaultGameMode`, no default pawn, no `GameInstance`. `physics` alone noticed. Two consequences nobody drew: **`/Game/Alpine8K` is not the default map**, so a cook today ships Epic's template world; and encounters, towns, AI and quests all presuppose a possessed pawn on nobody's critical path but `physics`'s.

**4. Save / load — a named domain requirement, not delivered.**
The domain is *"Quest, dialogue, progression **and save architecture**"*. The return contains one clause: *"the save enumeration and its exclusion of landscape and foliage."* CLAUDE.md: *"'As reported above' and '(F2)' are indexes, not content."* For World Partition with One File Per Actor, save is the hardest Phase-2 data problem: actor identity across streaming, `FActorInstanceGuid` stability, a killed enemy in an unloaded cell, and `ai-enemies`'s director that explicitly *"persists a small per-marker state record"* — against a format nobody specified. **Blocking everything with persistent state.**

**5. UI / HUD — and the project already carries UI config nobody ruled on.**
`DefaultGame.ini` opens with `[/Script/CommonUI.CommonUISettings]` plus three `CommonUI.*` console variables, inherited from a template, in a project that has never shown a widget. The `quests-data` schema rests entirely on `title_key`, `summary_key`, `text_key`, `progress_bar` — **every one a UI contract with no consumer designed.**

### Blocking later, cheap to scope now

**6. Audio — total absence, with a hard dependency on an open physics item.**
`assets` confirms **zero sound assets on disk**; `BACKLOG.md` has no audio, sound, music, MetaSound or Wwise entry. The engine ships `AudioGameplay`, `AudioGameplayVolume`, `AudioInsights`, `AudioModulation`, `AudioSynesthesia`, `SubtitlesAndClosedCaptions` — none evaluated or tiered. The coupling nobody drew: **footstep audio needs the per-surface query `physics` marks `[INFERENCE]` in §3f**, whose own conclusion is that this project probably cannot use landscape physical materials as built. Audio does not block Phase-2 engineering; it blocks nothing while the *surface-representation decision is being made without it in the room*.

**7. Localisation — zero, and one brief silently depends on it.** No `LandscapeLab/Content/Localization` directory (verified absent). `quests-data` is key-based, which is right, and names no mechanism: not `FText`, not `UStringTable`, not the gather commandlet, not the Localization Dashboard.

**8. Cinematics — and the world vision requires one.** `MovieRenderPipeline` is enabled in the `.uproject`. `physics` quotes WORLD_VISION correctly: *"the airship is a scripted travel sequence between regions… a region transition behind a sky sequence."* **A cutscene requirement, ruled by Ryan, load-bearing on the multi-region option, owned by no brief.**

**9. Build / cook / packaging — zero coverage, and a live landmine.** `LandscapeLab.uproject` enables with `"Enabled": true`:

| Plugin | Descriptor |
|---|---|
| `AllToolsets` | `IsExperimentalVersion: true`, **`NoRedist: true`**, `EditorOnly: true`, `EnabledByDefault: false` |
| `MCPClientToolset` | Experimental, NoRedist |
| `ModelContextProtocol`, `RemoteControl`, `RemoteControlWebInterface` | a remote-control **web server** in the shipping plugin array |

Nobody has cooked this project; no brief proposed it; `BACKLOG.md` has no cook entry. `pipeline` touched `AllToolsets` for its dependency graph, not its shippability.

**10. In-engine automated testing.** The 114-script offline suite covers none of the runtime. `AutomationTestToolset` is pulled in by `AllToolsets`; `Engine/Source/Developer/AutomationController` exists. No brief proposed a functional test that enters PIE and asserts anything — a doctrinal contradiction in a project whose rule is *a gate that has only seen good input has not been tested*.

**11. Time-of-day / gameplay lighting.** The whole lighting record is **one** 12° sun and **one** exposure solve (`-1.923 EV`); the VSM page-pool sizing, Lumen cost, shadow-depth draws and the 11 ms bar are all pinned to it. Exploration implies multiple lighting states. **Any day/night work re-opens the budget, the exposure solve and the shadow instrumentation together.**

**12. Region-transition loading.** `towns` owns WP grids inside a region; nobody owns crossing between them, which Option A makes the primary traversal mechanic.

---

## 2. UNCITED OR RECALLED CLAIMS

Ordered by blast radius, per rule 27.

**2a. `characters` returned nothing.** Full text: *"Done. Brief is in my first response; audit is settled…"* Skeleton selection — where `assets` and `physics` **disagree** on UE4 vs UE5 mannequin and neither is authoritative — retarget chains, root motion, per-character anim budget and LOD policy are all unaddressed. In that vacuum `assets` asserts **~110 free engine animations**, a count with no enumeration method, and calls `ASSETS.md:78` wrong on the strength of a name-table byte search. Nobody with the animation domain reviewed either.

**2b. `pipeline` — an absence finding from a partial search. Highest-confidence defect here.**
Claim: *"The `"EditorOnly": true` those carry is **inert**: no descriptor parser in `Engine/Source` reads the key."* In C++ that holds — `Runtime/Projects/Private/PluginDescriptor.cpp` and `Public/PluginDescriptor.h` have zero hits for `EditorOnly` **or** `NoRedist`. But build/cook/stage filtering is C#, and the file exists:

- `Engine/Source/Programs/UnrealBuildTool/Configuration/Descriptors/PluginDescriptor.cs` — **unread by anyone**
- `AutomationTool/AutomationUtils/DeploymentContext.cs:580` — *"restricted folder names such as NoRedist, NotForLicensees"*
- `AutomationTool/Scripts/CopyBuildToStagingDirectory.Automation.cs:2444-2445`
- `UnrealBuildTool/Configuration/Rules/TargetRules.cs:804`, `ModuleRules.cs:1118`

**A C++-only search returned zero and was reported as engine-wide inertness** — the `LandscapeNanite.cpp` failure verbatim: a zero from the wrong path is *"I could not look"* (non-negotiable 6). The conclusion then justifies leaving the plugin situation alone.

**2c. `ai-enemies` §9 step 1 is wrong on both halves and violates a standing rule.**
Step: *"Add **only** `StateTree` and `GameplayStateTree` to `LandscapeLab.uproject`."* Traced:

```
LandscapeLab.uproject  ->  "AllToolsets", Enabled: true
AllToolsets.uplugin    ->  "StateTreeToolset", Enabled: true  (+ GASToolsets, ConversationToolset, …)
StateTreeToolset       ->  "StateTree"                         <- already pulled in
GASToolsets            ->  "GameplayAbilities"
ConversationToolset    ->  "CommonConversation"
GameplayStateTree      ->  pulled in by NOTHING
```

`StateTree` is already enabled transitively (`pipeline` is right; `ai-enemies` did not check); `GameplayStateTree` — the half carrying `StateTreeAIComponent`, `FStateTreeMoveToTask`, `FStateTreeRunEnvQueryTask` — is the one genuinely missing. Both briefs read descriptors only, which is a derived record; whether the modules load in the running process is a live query nobody made. Worse: **standing rule 4 forbids modifying `.uproject` directly on disk**, and CURRENT STATE 2026-08-12 records the guard refusing exactly this once, producing a better design. **The AI brief's first action item is the one `pipeline` already ruled out** (a `LandscapeLabGameplay` project plugin with `EnabledByDefault: true`, citing `PluginManager.cpp:420-433`).

**2d. `towns` — the load-bearing magnitude is composed across two landscapes.**
*"Rendered, collided and planned ground disagree by up to ~0.8 m."* Components: 0.4 m Nanite displacement (correct, `/Game/Alpine8K`) **plus** *"collision quantization here already measures 0.431 m max"* — but **0.431 m was measured on `/Game/Alpine`**, a 2017², 4 m/vertex landscape, in the 2026-08-06 grounding work. `/Game/Alpine8K` is 1 m/vertex, and quantization is a function of collision mip and vertex spacing. **Carrying it across a 4× resample and adding it to a displacement amplitude is arithmetic on two worlds, not a measurement** — and the entire foundation-seating design is sized to it. Also uncited where every sibling cites `unreal.py:NNNNN`: *"`PCGGraph.add_node_of_type`, `add_edge`, `PCGNode.set_node_position` are all reflected."*

**2e. `budget` — two numbers with no derivation set everything else.** The most disciplined brief, and it marks most of its soft spots. Unmarked: **"a 2.00 ms hold + 1.67 ms margin"** appears with zero justification and produces the 5.08 ms every other domain spends. `"15,235 MB (measured RHI budget)"` is cited to nothing. `~1,633 MB` of VRAM unattributed — 26% of use — is disclosed but not treated as a risk to the 6,270 MB allocatable figure.

**2f. `physics` — one `[INFERENCE]` need not be one.** §3e Trap 1 (a Python write to `collision_profile_name` bypassing `LoadProfileData`) is correctly labelled and given a disproof — but it is settleable offline in one grep of `LandscapeLab/Intermediate/PythonStub/unreal.py`, which states whether the property has a setter. The brief was read-only, not blocked; the stub is a file. *"I could not look"* was claimed where looking cost nothing.

**2g. `quests-data` — the engine content is an index.** *"The design's engine findings are unmoved across five passes"*, then three named — `FActorInstanceGuid::GetActorGuids`, the `CommonConversation` UncookedOnly rejection, the save enumeration — **with no file, no line, no restatement.** Not a citation a reviewer can open. The six-defect authoring autopsy that *is* fully delivered is the best epistemics in the set, and is not the deliverable requested.

---

## 3. THE BRIEF MOST LIKELY TO BE WRONG

**`towns`** — with the confidence stated plainly, because the field forced a single answer: `characters` returned nothing so it cannot be wrong, and among the remaining seven the margin over `ai-enemies` §3.4 is thin. The honest form of the answer is: **`towns` is the brief whose central magnitude and central mechanism are both unverified, and it is the cheapest to settle.**

Two independent failure modes, either fatal to the approach:

1. **The ~0.8 m disagreement may not exist on this landscape** (§2d — the 0.431 m term is imported from `/Game/Alpine`). If the real figure on `/Game/Alpine8K` is 0.1 m, the flat-pad + zero-displacement + two-distance-gate design costs town sites their terrain detail to protect against nothing.
2. **The mechanism may have no surface to write to.** `LandscapeTexturePatch` on a dedicated edit layer is the seating method — and the brief's own open list concedes the "one edit layer" record belongs to `/Game/Alpine`, a different landscape. If `Landscape_Alpine8K` has none, the primary mechanism does not apply, and the C++ it requests (`ALandscape::CreateLayer`, `Landscape.h:431`, no `UFUNCTION`) is scoped before anyone confirmed the target supports it.

### The single check that settles it

One editor session, one prospective town site, ~10 minutes, nothing authored, nothing saved:

1. Read `Landscape_Alpine8K`'s edit-layer array. **Non-zero → mechanism valid; zero → the towns design needs re-basing before any C++ is written.**
2. At the same XY: sample the heightmap PNG (plan), take an engine line trace (collision), read the rendered surface — at **two camera distances**, inside and outside the per-cluster displacement-disable range (`r.Landscape.AllowNanitePerClusterDisplacementDisable`, `LandscapeRender.cpp:223-231`). Report the max spread.

Three representations of one physical fact on **one** landscape — what non-negotiable 0 asks for, and what the brief substituted arithmetic for. Both unknowns close in a single run.

---

## 4. THE LARGEST UNDER-NAMED RISK

**The measurement corpus describes a configuration the game will never run in, and four variables change together the moment a player exists.**

Every number Phase 2 is planned against — GPU 7.92 ms, the **11 ms abort bar**, the 219,659-instance density ruling, the 730 m conifer cull, `-1.923` EV, the VSM 2048-page pool, 6,241 MB VRAM — was taken under **all four** of these at once:

| Measured under | Phase 2 reality | Direction |
|---|---|---|
| Editor viewport, Slate running (6.03 of 8.88 ms GameThread) | PIE / packaged | **cheaper**, then re-spent |
| **Parked** station, fixed FOV, **unrecorded resolution** | player-driven third-person camera | **unknown** |
| **All 256 proxies force-resident** (219,659 trees) | WP streaming — `physics` §3d derives **≈1,360** resident at the 256 m default | **far cheaper** |
| **No** AI, animation, physics, audio or gameplay tick | all of it | **more expensive** |

Three make the frame cheaper; one makes it dearer; **nobody knows the sum, and every brief allocated milliseconds against a fixed baseline.**

**Scope of the "unnamed" claim, corrected:** `budget` *did* name the missing PIE reading, citing `RECIPES.md:5889` calling it a calibration class that does not exist. What no brief named is the **compound** effect above and the ruling that it must **gate** allocation rather than sit as an open item.

This is the project's signature failure mode, not a hypothetical. R13's frame-cost table was invalidated by a hardware migration and survived only because it was labelled a calibration class **in advance**; the editor-viewport corpus carries no such label. And three grounding checks once agreed for three days while the world rendered v2 and collided v1 — **eight briefs agreeing that ~8.7 ms remains is one measurement, not eight.** They all read the same CSV.

**Mitigation, as a gate rather than a backlog item:** before any domain is allocated GPU or game-thread budget, take **one PIE capture** at a matched camera and a **recorded** resolution on `/Game/Alpine8K`, with streaming live rather than force-resident, and stamp every existing frame-cost artefact with its calibration class. The delta from 7.92 ms is the real Phase 2 budget; until it exists, every abort bar in these briefs — 11 ms, +2.5, +1.5, +1.0 — is a number in the wrong units.

### Second, and visible in the returns themselves

**Half the briefs were degraded by tooling, and nothing measured brief completeness.** `characters` returned one sentence; `quests-data` returned an autopsy instead of its domain; `ai-enemies`, `towns`, `budget` and `pipeline` each spend paragraphs on a validation matcher, four independently diagnosing the same cause. **At least 25% of requested coverage was never produced, and the plan does not know it.** Scope the matcher to unhedged first-person assertion and exempt quoted spans — as two briefs independently proposed — then **re-run `characters` and the save half of `quests-data` before sequencing anything.**

---

## 5. DEFECT IN THE OUTPUT CONTRACT I WAS GIVEN

Two fields asserted their subject exists, unconditionally: *"which brief is most likely to be WRONG"* and *"the biggest RISK that no brief named."* Had every brief been sound, or every material risk already been named, the shape of the request would push toward manufacturing one — which is why §3 states its confidence explicitly and §4 narrows its own scope. Both should be nullable: **null on the first meaning *no brief is clearly wrong on the evidence returned*; null on the second meaning *every material risk was already named by a brief*.** `pipeline` identified the same defect in its own contract (`blocked_by_ruling` absent, unproven-claims not nullable). Two contracts, one trap class — under non-negotiable 4a that is a promotion trigger, not a pair of one-offs.