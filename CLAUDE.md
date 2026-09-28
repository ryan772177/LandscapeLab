# CLAUDE.md â€” the constitution

# â­ CONTEXT-LOADING PROTOCOL â€” READ THIS FIRST, IT GOVERNS WHAT YOU READ NEXT

**This file used to be 492,079 characters and 30 stacked `CURRENT STATE` blocks,
and sessions were reasoning from superseded design notes as though they were
live.** It is now an INDEX.

**At session start read ONLY:**

1. **THE OPERATING LOOP and THE STANDING RULES** in this file â€” they are law.
2. **THE LIVE `# CURRENT STATE` BLOCK** in this file. **There is exactly one**,
   and a checker enforces that. If you find a second, something is broken.
3. **THE INDEX** at the bottom of this file.

**Then pull what the work needs via the index, and nothing else.** Its "load
when" column exists so you do not guess: encounters â†’ the encounters row;
writing a gate â†’ `docs/non-negotiables.md`; before a render â†’ grep `RECIPES.md`
for `R-CITYSHOT`.

**NEVER read `docs/archive/` unless investigating history** â€” why a decision was
taken, what a number used to be, when a defect appeared. **Nothing in there may
drive a decision**, and every file carries a â›” banner saying so. If an archived
doc seems to answer your question, that answer is stale by construction; find
the live source in the index.

**`docs/` itself is NOT the archive.** `non-negotiables.md`, `environment.md`
and `ue58-api-protocol.md` are LIVE LAW that did not fit here. Only
`docs/archive/**` is dead.

---

# THE MISSION, AND THE WORLD AS IT STANDS

**This project is phase one of an open-world RPG in Unreal Engine 5.8.** Terrain
came first because everything else is placed relative to it. Read
`WORLD_VISION.md` for the trajectory; terrain is a subsystem, not the product.

**Separate exploration from the Unity/AnyRPGCore project â€” do not cross-reference
that repo.**

## THE CURRENT SPEC â€” one screen

**Every row re-verified against the recipe or a plan on disk 2026-08-29**, not
copied from a prior block. Sources: `recipes/alpine_8k.json`,
`city/alpine_basin_town_plan.json`, `encounters/alpine_8k_verified.json`,
4 Ã— `foliage/alpine_8k_*.json`.

    level        /Game/Alpine8K          heightmap terrain/alpine_8k.png png16
    landscape    8129 x 8129 vertices    32 comp x 2 sect x 127 quads + 1
    sampling     scale_xy_cm 100.0       = 1 METRE per vertex
    z_scale_cm   256000.0                loc [-406400, -406400, 128000]
    material     M_Alpine8K              displacement 0.4 m, triplanar Rock
    foliage      219,659 instances       navmesh 72 bounds volumes
    town         303 buildings, 838 streets, 303 roofs, 1 landmark, 1 spire
                 -- ENGINE PRIMITIVES, this is the biggest gap
    encounters   305 verified
    architecture MULTI-REGION, 2x2 atlas  RULED BY RYAN 2026-08-15
                 [WORLD_VISION.md:174, :191]

**Two figures are MEASUREMENTS** â€” terrain Z span **0â€“1552.5 m**,
**35.32 kmÂ² reachable** (navmesh, post-water; was 36.53) of **47.77
walkable** (was 49.27).

**The biggest gap: the town is 762 engine Cubes and a Cylinder.** The Medieval
Village kit is on disk (22.6 GB, vault cache) and **is a COMPONENT KIT** â€”
2.00 m wall courses, no whole-house meshes.

**The pre-8K world (`/Game/Alpine`, 2017Â², 4 m/vertex) is HISTORY** â€” its docs
are in `docs/archive/pre8k/`. Reading about `alpine_heightmap_v2.png`, Pass 0â€“7,
or a manual landscape-import click-list means you are in the archive: stop.

---

# THE OPERATING LOOP

This is the whole method. Everything below it is detail.

### a. Check `RECIPES.md` first
Before attempting anything, look for a locked procedure. **If one exists,
follow it exactly.** No freelancing on solved problems. The recipes exist
because someone already paid for the mistakes.

**STEP (a) IS A SEARCH, NOT A RECALL.** *"I don't remember a tool for
this"* is not evidence of absence. **`scripts/` gets LISTED before any
ad-hoc payload touches the editor**, and `RECIPES.md` gets grepped
before any procedure is invented.
*Motivating case, 2026-08-05:* I hand-rolled a `load_level` payload,
crashed the editor at `EditorServer.cpp:1951`, root-caused it correctly
from the log, wrote it up at two altitudes, and got the rule ratified â€”
and `scripts/open_level.py` had been sitting there the whole time,
having already root-caused that same crash **twice**, with the fix. A
two-second `ls scripts/ | grep level` would have prevented the crash,
the wrong rule, and its ratification.
This is non-negotiable 17's shape again: **memory of the toolbox is a
DERIVED RECORD; the directory is ground truth.**

### b. No recipe? Experiment freely â€” but log the moment it fails
You may try anything. **The moment something fails, log it in
`LESSONS.md` with root cause before retrying.** Not after the session,
not once it's fixed â€” before the retry. A failure you retry without
understanding is a failure you will have again.

Root cause means a source line, a schema, or a measured number. "It
didn't work" is not a root cause.

### c. Succeeded and verified? Lock it into `RECIPES.md`
Verified means: the editor launches clean, the output validates, and
nothing regressed. Note which `LESSONS.md` entries informed the recipe.

A recipe locked on the strength of one lucky run is worse than no recipe.

### d. Refine deliberately
A locked recipe can be improved. **Test the improvement in isolation
first.** Only replace the recipe once the new version is verified. Log the
old version in `LESSONS.md` as superseded, with the reasoning â€” never
delete it.

### e. Rework trends toward zero
That is the success metric across sessions. **The same mistake twice is a
process failure, not an accident.** When it happens, the lesson is not
"be more careful" â€” log *why the existing lesson did not prevent it* and
fix that gap. A lesson that exists and doesn't fire is a defect in the
lesson.

### f. Full autonomy, two escalations
Decide anything within the RPG vision without asking. Escalate only:

1. **Scope changes** â€” adding or cutting a major system.
2. **Anything destructive to `LESSONS.md` or `RECIPES.md`.**

---


# STANDING RULES

These are not approval gates. Not one requires Ryan. They exist to catch
**my** errors, and every one was written after a real defect.

1. **Never operate outside this repo or the UE project directory.** No
   writes, deletes, or config changes elsewhere on the machine. Reading
   elsewhere is fine and expected â€” engine source especially.
   *â€” why: LESSONS 2026-08-01 (a machine-global EditorSettings.ini write; a disclosed exception, not a defect).*
2. **Never use recursive or forced deletes** (`rm -rf`, `del /s`). To
   remove files, move them to `_trash/` inside the repo. Git is the undo
   button; `_trash/` is the second one.
   *â€” why: LESSONS 2026-08-03 (rm -f used under the rule that forbids forced deletes).*
3. **Commit before and after anything where a restore point matters.**
   **Commit messages go through a FILE (`git commit -F <path>`),
   unconditionally.** Not "when the message looks risky" â€” always.
   Promoted 2026-08-03 after the FOURTH message in one session was
   mangled by shell quoting: heredocs eaten by apostrophes, then
   backticks expanding as command substitution and silently deleting
   words from a commit that still succeeded. A rule that depends on
   remembering which characters the shell eats is the weakest kind of
   rule; the file path has no failure mode.
   Small, frequent commits. This matters MORE under full autonomy, not
   less â€” git is the only thing between a wrong idea and a lost day.
   *â€” why: LESSONS 2026-09-10 (crash reverted Brief-2 Tasks 1-5) + 2026-08-05 (commit mangling); the "08-03" above is the promotion date.*
4. **Never modify `.uproject`, `.uasset` or `.umap` directly on disk.**
   Editor-side changes go through the UE Python API. (`.ini` files are
   normal project config and are edited directly.)
   *â€” why: LESSONS 2026-07-28 (overwriting a .uasset on disk desyncs it from editor memory).*
5. **Record any dependency added** to the project's Python environment.
   A dependency nobody wrote down is a rebuild that fails on a fresh
   machine.
   *â€” why: NO motivating LESSONS entry â€” a-priori (founded on the fresh-machine rebuild it prevents). Stated per rule 10.*
6. **If a script errors twice in a row, stop and diagnose.** Do not
   brute-force variations against a live editor.
   *â€” why: LESSONS 2026-08-01 §12.10 (.py-in-payload read as a path, brute-forced twice against the live editor).*
7. **Verify the connected editor matches `UE_PROJECT_ROOT` before any
   remote execution.** The port serves whichever editor holds it. Autonomy
   over this project is not authority over somebody else's.
   *â€” why: LESSONS 2026-07-27 (gate founded; port serves whichever editor); confirmed 2026-09-13b.*
8. **Dry-run anything destructive**, and identify by property signature
   rather than by name wherever the operation is irreversible. Actor
   labels collide â€” this project has two landscapes whose proxies carried
   identical labels.
   *â€” why: LESSONS 2026-09-08f (no-force-delete guard disabled 4 min) + 2026-07-28 (two landscapes, identical proxy labels).*
9. **Cite full text or a path.** **AND THIS APPLIES TO OUR OWN
   ARTEFACTS.** A claim inherited from our own docstrings, comments or
   prior recipes into a new document, without opening the underlying
   source, is the same unverified-derivation class as trusting an
   external record.
   *Motivating case, 2026-08-03:* two builder docstrings asserted that a
   normal-map sampler mismatch "compiles clean and is silently wrong". I
   repeated it into a RECIPES REJECTED entry without checking. Engine
   source says the opposite â€” `VerifySamplerType` errors on EVERY
   mismatch and applies an EXTRA sRGB check that fires only for Normal
   and Masks. **An unverified claim in our own code contaminated the
   knowledge base**, which is the one place that is supposed to be
   checkable. Containment is to fix the SEED as well as the copy.
   "As reported above" and "(F2)" are indexes, not content. Ryan's
   terminal has repeatedly received truncated context.
   *â€” why: LESSONS 2026-08-27b (licence asserted from memory) + the 08-03 normal-map case above.*
10. **State plainly when something was not done, not verified, or turned
    out wrong.** Under the old process a gate would have caught it.
    Nothing does now except this.
    *â€” why: LESSONS 2026-08-03 ("I couldn't look" reported as "it's absent", twice).*
11. **Wait for ZERO editors before launching one, then ASK WHICH LEVEL is
    loaded before any shot or mutation.** 2026-08-30: `CloseMainWindow()`
    went unhonoured for 20 s, a second editor was launched over the first,
    and discovery answers from whichever holds the port. The failure mode
    is a **plausible artefact from the wrong level** â€” it renders clean,
    passes every tonal check, and nothing downstream can detect it. Rule 7
    checks the PROJECT; this checks the LEVEL.
    *â€” why: LESSONS 2026-08-30 (second editor over the first) + 2026-09-10d (0-dirty close deadlock, 4th occurrence).*
12. **A PROFILE PARAMETER THAT IS NOT READ BACK IS PROSE.** A declared
    value must be APPLIED and READ BACK FROM THE ENGINE â€” all three, or
    the field is a comment that answers "is this controlled?" with a false
    yes. Promoted 2026-09-07 on the third instance in three days: perf
    stations declared no FOV; residency was gated in `measure_frame_cost`
    and absent from the capture tool; `benchmark.json` said `"exposure
    manual"` while auto-exposure ran, drifting luma 0.349 -> 0.275 across
    a dolly and burying the pop signal the capture existed to measure.
    The read-back comes from a log line, a property re-read or the
    artefact â€” never the structure just written, which proves only that
    the setter ran.
    *â€” why: LESSONS 2026-09-06 (exposure "manual" declared, never applied); the "09-07" above is the promotion date.*
13. **EVERY COMPARISON REPORTS ITS SAMPLE COUNT BESIDE ITS VERDICT, AND
    A ZERO COUNT REFUSES.** "No differences found" from an instrument
    that found nothing to compare is not agreement — it is silence
    wearing agreement's clothes, and in a report the two read
    identically. Promoted 2026-09-13 from the GameOverride precedence
    test: two instruments were declared to agree and the second had
    parsed **0 of 22** values, because a bare `sg.X` console query
    prints nothing at all. The verdict was right on instrument one; the
    report would have claimed two. This is rule 12's sibling — 12
    catches a value that was never read back, this catches **a read
    that returned nothing and was counted as confirmation**.
    *â€” why: LESSONS 2026-09-13 (GameOverride precedence echo parsed 0 of 22, counted as agreement).*

---


# PIPELINE RULES

1. Logic in Python/C++. Blueprints only as thin wrappers.
2. **Every scene parameter comes from recipe JSON**, never hardcoded.
3. **Scripts are idempotent** â€” re-running a recipe rebuilds
   deterministically.
4. **After any scene change: run `scripts/capture.py`.** Editor-touching
   runs that are not scene changes need no capture.
5. **Heavy operations run one at a time** and log available RAM first
   (`scripts/resource_guard.py`, `RECIPES.md` R10).

---


# SESSION PROTOCOL

**No session ends with uncommitted work or a stale CURRENT STATE.**

**At session start, in this order:**
1. Read `CURRENT STATE` at the bottom of this file.
2. Read `BACKLOG.md`. **This is the only moment work may be pulled from
   the backlog** â€” pulling mid-session is the scope creep the backlog
   exists to prevent.
3. **State the session goal in one line, out loud, before touching
   anything.** A goal you did not write down is a goal you will drift
   from.

**CONTEXT EXHAUSTION IS A LIVENESS CONDITION.** When working context
nears its limit, **commit the groundwork and hand off cleanly rather than
start a unit that cannot be finished verifiably.** A large authored
artefact begun on a degraded context is the project's most expensive
failure mode in its purest form: a builder that reports success over a
graph that is wrong, produced by an author who no longer holds enough of
the system to notice.

The handoff must carry: what is committed, what is proven, what is
decided-but-unbuilt, and the named open items with their decisions
already made. "I ran out of room" is not a handoff; the next session
needs the DECISIONS, not the fatigue.

This is the same instrument-distrust the gates get, turned on the author.
A session that recognises its own degradation is applying non-negotiable
8 to itself â€” verify with a different instrument than the one that made
the claim, and right now the instrument IS the claim.

**At session end:**
1. Descriptive commit â€” what changed and *why*, not just what.
2. Update `CURRENT STATE`: open defects, active frontier, next step.
3. Confirm two-altitude logging happened for every failure this session.


# THE TWO-ALTITUDE LOGGING RULE

**Every failure gets logged twice, in the same commit:**

| Altitude | Where | What |
|---|---|---|
| Narrative | `LESSONS.md` | What was attempted, what happened, root cause at a source line or schema, the general rule it implies |
| Specification | `RECIPES.md`, the relevant recipe's REJECTED section | The exact wrong value/approach â†’ the symptom you will see â†’ the correct value â†’ the reference |

**A recipe with an empty REJECTED section, after a session that hit
failures, is an incomplete commit.** The narrative alone does not stop
recurrence â€” a fresh session follows the recipe, not the story. The
completeness test: *could a fresh session repeat this mistake without
opening LESSONS.md?* If yes, it is not yet captured.


# THE NEW-ELEMENT RULE

**No new element without its recipe.** Any session that adds a new
element TYPE to the world â€” a new asset kind, material, scatter type, or
import path â€” must produce a template-conforming recipe before the
session ends: exact import settings, compression, LODs, collision,
placement parameters.

**Tuning an existing element updates its recipe's values in the same
commit.** A recipe that describes last week's values is worse than no
recipe, because it will be trusted.


# THE RISKY-OP CHECKPOINT

**Before any operation touching many assets, or not cleanly undoable:**
create a git branch or tagged commit first, **named for the operation**.

Applies to, at minimum: bulk reimport, landscape resize, mass foliage
regeneration, engine or plugin version change, batch retarget.

This is not the same as rule 3's ordinary commit discipline. Rule 3 says
commit before anything where a restore point matters; this says the
restore point must be *findable by name* six weeks later, when nobody
remembers which of forty commits preceded the bad reimport.

---


---

# THE INDEX â€” how a session finds context instead of inheriting it

**This table replaces a 492K constitution AND the old "six files" table.** Every
doc in the repo is listed here or under a declared prefix. Load by the **"load
when"** trigger; do not read ahead.

## LAW â€” the operating loop and standing rules are above; these are the rest

| Path | What | Load when |
|---|---|---|
| `CLAUDE.md` | This file: protocol, spec, operating loop, standing rules, the one live CURRENT STATE, and this index. | **Always, first.** |
| `docs/non-negotiables.md` | 28 rules, each bought with a real defect. Rule 0: instruments sharing a source are ONE measurement. | **Writing any gate, check, tolerance or measurement**, or trusting an instrument that agrees with your hope. |
| `docs/ue58-api-protocol.md` | 5.8 resolution order; the reflected surface is the contract; names that meant something else. | **Before writing or calling ANY Unreal API, property, enum or MCP tool.** |
| `docs/environment.md` | Hardware, UE path, ports, remote-exec, MCP, the two ROOTS quoted in every audit request. | **Before the editor, unreal-mcp, or any heavy op.** |
| `REFERENCES.md` | Docs are intent, source is ground truth, RECIPES outranks both once proven. | Citing anything; how hard to check a claim. |

## THE WORKING SET

| Path | What | Load when |
|---|---|---|
| `RECIPES.md` | **The executable SPEC and ANTI-SPEC.** Values that work and that failed. **Never delete a locked recipe.** | **Step (a) of every task â€” grep before inventing a procedure.** TOC at top. |
| `LESSONS.md` | Append-only NARRATIVE of what was learned the hard way. **Never delete from it.** | Diagnosing a failure; why a recipe says what it says. TOC at top. |
| `WORLD_VISION.md` | Where this is going: difficulty gradient, region ruling, POI tripwire. | Scope, direction, or whether something needs Ryan. |
| `BACKLOG.md` | The scope-creep valve. Add freely. | **Session start only** â€” the one moment work may be pulled. |
| `PROGRESS.md` | One line per closed item of the active autonomy window. | Session start; closing a window item. |
| `OPEN.md` | Items parked with evidence during a window (O-1..O-4). | Session start; before ruling on a parked item. |
| `ASSETS.md` | Intake register. No asset without a row. | Importing, evaluating or cataloguing any asset. |
| `FORGE_LOG.md` | One costed line per generation run. | Any forge run. |
| `CREDITS.md` | Shipping licence obligations (Blenderust CC BY 4.0 and others). | Third-party content; anything that ships. |
| `research/` | Research-desk briefs: BRIEF, FOR_CLAUDE_CODE, REGISTER. **Inputs, not law** — open every number before use (rule 9); append results. | Working a brief. |

## CODE THAT IS NOT PROSE

| Path | What | Load when |
|---|---|---|
| `recipes/schema.md` | Normative contract for recipe JSON; twelve files reference it. | Adding or changing ANY recipe field. |
| `recipes/scene_grammar.md`, `recipes/concepts/` | Contract for CONCEPT recipes (v1.0-concept) â€” site vs camera, provenance per entity â€” and the recipes read from the art refs. | **Concept-pipeline work.** |
| `refs/` | Concept art â€” never an engine asset â€” plus `MANIFEST.md`, the unserved-entity frontier. | Judging output against intent; choosing what to forge next. |
| `recipes/alpine_8k.json` | **The shipped world** â€” terrain, material, foliage, navmesh, cameras. | Any world-level change. |
| `recipes/city.json` | The town: rings, spokes, footprints, `storey_m`, roofs, landmark. | **City planner or kit work.** |
| `recipes/ai_restrictions.json` | â›” Assets a generation model may NEVER be fed. `ai_input_guard.py` refuses; violation is undetectable after the fact. | **Before ANY generation or forge run.** |
| `recipes/encounters.json` | Density, separation, settlement exclusion. | **Touching encounters.** |
| `recipes/character.json` | Capsule, speeds, walkable angle, spawn. | Pawn or movement work. |
| `recipes/` rest | `alpine.json` + `alpinelab_*` are the pre-8K and Gaea EVALUATION worlds â€” they load, nothing current reads them. | Only for those legacy terrains. |
| `PROJECT_STATE.json` | Machine-recovered editor state (`recover_state.py`). | Recovering state â€” never over the live editor. |
| `scripts/` | All tooling. **LIST IT before inventing an ad-hoc payload** â€” step (a) is a SEARCH, not a recall. | Every task touching the editor or a plan. |

## PROGRAMME AND DESIGN â€” live

| Path | What | Load when |
|---|---|---|
| `PHASE2_PLAN.md` | Playable-world programme, units 1â€“12. **âš  Four rulings overtaken â€” banner at top.** | Working any numbered unit. Banner first. |
| `WORLD_ARCHITECTURE.md` | Multi-region 2Ã—2 atlas. **RATIFIED** 2026-08-15 despite its own status line. | Region work, streaming budgets, travel. |
| `terrain/regions/` | Five `.terrain` region files, authoring notes, runbook README. | Building or editing a Gaea region. |
| `plans/RECIPES_draft_*.md` | Three drafts staged, never merged. Found 5 numeric errors in our own artefacts. | Closure / PN trees / understory. |
| `plans/characters_brief.md` | Unit 4 brief. **âš  Skeleton ruling partly superseded by MetaHuman; its 102-animation inventory is current.** | Character or animation work. |
| `plans/trellis_setup.md` | TRELLIS/WSL env for hero face reconstruction. | Rebuilding it. |
| `REPLAY_BURNDOWN.md` | The 13 UNPROVEN recipes. **OPEN: cold replay is a Brief 5 acceptance.** | Recipe replay work. |
| `GOVERNANCE_MIGRATION.md` | Which rules became hooks, and which did not. | Adding a `.claude/hooks/` guard. |
| `docs/_consolidation_inventory.md` | Why each doc is live or archived, with evidence. | Where a doc went; disputing a verdict. |

## HERO â€” PARKED, not superseded

Ryan: *"I'll revisit this later since we have a working prototype."* Post-8K
work, so **not** pre-8K archive material.

| Path | What | Load when |
|---|---|---|
| `hero/` | Groom pipeline, DNA, references, the overnight loop and logs. | Resuming hero work. |
| `hero/BLENDER_HANDOFF.md`, `hero/ADVISOR_LOG.md`, `docs/archive/MORNING_REPORT*.md` | The Blenderâ†’Alembic groom round trip and advisor consults (hero, parked); the MORNING_REPORTs are archived session reports. | Same â€” newest first. |

## EVIDENCE AND HISTORY â€” cite, never obey

| Path | What | Load when |
|---|---|---|
| `_verify/` | Dated measurement artefacts and renders. **Cited, never obeyed.** | Checking what was measured, and what it read. |
| `Free/_measured/` | Measurement JSON (kit modules, pivots, palettes, the kit closure manifest). | Needing a measured dimension, not a remembered one. |
| `.claude/` | Skills, subagent definitions, enforcement hooks. | Invoking a skill; adding a guard. |
| `docs/archive/current_state_history.md` | **â›” 31 superseded CURRENT STATE blocks.** | **History only. Never to decide.** |
| `docs/archive/pre8k/` | **â›” Six pre-8K docs**, each marked with what superseded it. | **History only. Never to decide.** |
| `plans/phase2_lanes/`, `plans/region_lanes/`, `plans/region_authoring/` | Lane outputs, 2026-08-15 â€” the INPUTS behind `PHASE2_PLAN.md`, `WORLD_ARCHITECTURE.md`, `terrain/regions/`. | Auditing how one reached its conclusion. |
| `_trash/` | Removals. Git is the first undo; this is the second. | Recovering something removed. |

## REPO LAYOUT

    docs/ live doctrine + docs/archive/ (DEAD)   recipes/ biome JSON (CODE)
    scripts/ UE Python + blender/                terrain/ textures/ heightmaps
    foliage/ city/ encounters/ planner JSON      captures/ _verify/ evidence
    Free/ vendor + _measured/                    hero/ PARKED   plans/ briefs
    _trash/ removals -- never `rm -rf`

**`scripts/check_docs.py` enforces this index** and runs in
`scripts/run_offline_suite.py`.

---

# CURRENT STATE — moved to `STATE.md`

> **⭐ THE LIVE STATE BLOCK IS `STATE.md`.** Moved out of this file
> 2026-09-13: CLAUDE.md had FOUR characters of headroom under its
> 25,000 ceiling, so the state could not grow without displacing law.
> Read `STATE.md` at session start, immediately after this file.
> History is `docs/archive/current_state_history.md` — ⛔ never a
> source.
