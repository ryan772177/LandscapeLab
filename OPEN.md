# OPEN — parked items, overnight window 2026-09-14

Items parked with their evidence, for Ryan or a later session. Nothing here
is blocked on idling; each says what would unblock it.

---

## O-1 ⛔ THE DESK IS NOT AN INDEPENDENT AUTHORITY, AND THREE ACTIONS ARE HELD BACK

**The brief defines THE DESK as a subagent I spawn, and says "treat its
ruling exactly as Ryan's".** I am using it as instructed for analysis,
research and recommendations — it is genuinely useful for that, especially
for reading large corpora and consulting Epic's 5.8 docs in parallel.

**But a subagent I spawn is the same model, with the same blind spots and
no independent stake.** By this project's own law that is ONE instrument,
not two: non-negotiable 0 — "instruments sharing a source are ONE
measurement" — and non-negotiable 8 — "verify with a different instrument
than the one that made the claim". A ruling I generate and then obey is
not a second opinion; it is my own reasoning wearing a different hat.

That is fine for reversible work. It is not a substitute for an owner on
actions that cannot be undone from inside the repo. **Three are therefore
prepared but NOT executed, each with the decision reduced to one step:**

| action | why held | what unblocks it |
|---|---|---|
| **Uninstall IncrediBuild** | Outside the repo (standing rule 1), system-wide, affects every project on this machine — and **unnecessary**: `r.ShaderCompiler.AllowDistributedCompilation=0` was read back on 5 launches and the project is already immune. Removing software to fix a problem that is already fixed is a net risk. | Ryan's say-so. The engineering recommendation is **do not uninstall**; disable the Agent service instead if the wedge ever recurs. |
| **Wholesale archive of 620 uncalled / 899 untested scripts** | A move is reversible, but a 620-file sweep decided by criteria I also authored is a single point of failure across most of the toolbox. | Ryan ruling the criteria, or a staged move (10 files, observe, continue). |
| **Merge brief4-water to main** | Terrain carving is upstream of foliage, navmesh, encounters and HLOD; a wrong merge invalidates all of them. | Ryan's acceptance of the branch. |

**Everything else in the brief I am executing under the delegated
authority**, including archiving *within* the repo, branch work, captures,
rebuilds, and LESSONS/RECIPES curation. This entry exists so the boundary
is visible rather than silently assumed.

---

## O-2 THE COST OF 4096 IS UNMEASURED — ⛔ STRUCK BY RULING 2026-09-15 (B-2 CANCELLED)

**RYAN RULED 2026-09-15: do not run the A/B. The perf budget is ABSOLUTE
and 4096 PASSES it** (all four zones PASS R-PERFBUDGET, `9a561d07`), so the
isolated cost of 4096 does not need a number to clear the gate. B-2 (the
256↔4096 rebuild A/B) is cancelled — no rebuild.

⛔ **THE PASS-2 DELTAS BELOW ARE HISTORY** (confounded, never a measurement
of the cap): Pass 2 − 09-10 GPU p90 −0.317 / −0.320 / −0.388 / −0.506 ms,
mean −0.383. Negative in every zone (wrong sign for a texel increase)
because the 2,267-cell HLOD rebuild and the grade/white-point re-solve
moved in the same window. Not to be quoted as the cost of 4096.

⚠ **PREMISE CORRECTED (Ryan, 2026-09-15): the old bake was 1024 texels
(≈2 m/texel on 2 km cells), NOT 256 (8 m/texel).** So 4096 is a **4×**
texel refinement (2000/4096 ≈ 0.49 m/texel), not 16×. The "16× texel
increase" reasoning above rested on the wrong baseline. Correction lands
in AUDIT/register and the CURRENT VALUES table (closure item 6).

---

## O-3 PRE-EXISTING SUITE FAILURE — "every plan against its inputs"

`run_offline_suite.py` reports 1 failure: *"A plan its producer will not
reproduce is a plan nothing should consume."* **Verified to fail at the
pre-session commit `bef19a51` as well**, so it predates this window and
none of tonight's work caused it. Not investigated yet — it is a real
finding about plan reproducibility and deserves its own pass.

---

## O-4 WHAT BROKE XGE BETWEEN 09-11 AND 09-14 IS NOT ESTABLISHED

The flag was absent on both dates; XGE was the dispatcher on both; it
returned jobs on 09-11 and did not on 09-14. IncrediBuild ran
`CheckForUpdates` at 09-14 19:04, but **no install file carries a
post-09-10 write date** evidencing an applied update. The project is immune
either way via the ini cvar, so this is curiosity, not risk.

## O-5 (2026-09-16, Q9/D-5): leftover UnrealEditor.exe burning ~1.4 cores for a day — Ryan to resolve

PID 4452, started 2026-09-15 22:17:12, CPU 132,440 s (~36.8 CPU-hours)
by the 09-16 late-window check, working set flat ~386 MB, window title =
the bare exe path (Epic UE_5.8 UnrealEditor.exe). NOT the perf-stall
idle-wedge signature (those consumed ~0 CPU with 4.5 GB resident); this
one is BUSY at low memory. Possibly a leftover from the 09-15 window's
editor work that never honoured R-EDITOR-CLOSE, or a process of Ryan's
own. Ownership and level are unverifiable without touching it (rules
7/11), so nothing was done. It BLOCKS editor launches (rule 11
zero-editors) until closed. Resolution: Ryan identifies and closes it
(or rules it killable); then rule 11 clears. Recorded during the D-5
closure (PROGRESS 2026-09-16).

**UPDATE 2026-09-17 (overnight, re-checked before the queued 1b -game
still):** PID 4452 is STILL alive — CPU now **39.7 CPU-hours** (still
climbing ~1.4 cores) and the working set has **grown 386 MB → 1121 MB**,
so the "flat ~386 MB" above no longer holds; it is busy AND accreting
memory (a possible leak), not idle. Nothing touched (rules 7/11). This
keeps **Brief-4 queue item 2 (the live -game proxy_fraction diff) BLOCKED**
— the 1b DERIVATION (proxy_fraction 0.05727, PROGRESS D-2 1b) remains the
instrument of record until the live still can run. Unblock is unchanged:
Ryan closes 4452 (or rules it killable).

**✅ RESOLVED 2026-09-19 — Ryan closed 4452.** Re-checked at session start:
PID 4452 still alive after ~4 days (CPU **44.95 CPU-hours**, WS 839 MB); its
command line read non-invasively (CIM) CONFIRMED the identity — THIS project
and THIS level, headless
(`UnrealEditor.exe …\LandscapeLab\LandscapeLab.uproject /Game/Alpine8K -log
-RenderOffScreen`), a leftover automation editor that never honoured
R-EDITOR-CLOSE. It was reported as still-blocking (rule 11 forbids launching a
fresh editor while one is alive; connecting to a wedged editor would violate the
"nothing touched" posture and give a worthless cost read). **Ryan then closed
it mid-session**, the process check went to ZERO editors, and the O-7 pilot ran
to completion on a fresh clean editor. O-5 is closed; the leftover-editor
class remains a standing R-EDITOR-CLOSE hazard, not an open item.

## O-6 ✅ RETRACTED/CLOSED 2026-09-18 — it was a verifier bug, not a recipe-data decision

**Filed then RETRACTED the same window.** The next Pass-3 batch read
`apply_navigation_config.py`, whose ruling-19 gate was CORRECTED 2026-08-26 to
compare the navmesh agent against the PAWN's `movement.profile`, NOT
`world.primary_movement_mode` — the world-primary comparand being a MEASURED
defect (LESSONS.md 2026-08-26; RECIPES.md:12715, :13221 state the pawn comparand
as the locked ruling). `verify_walkable_profile.py` had simply LAGGED that
correction and still used the superseded comparand, so it false-fired exit 5 on
a correct config. **Fixed:** verify_walkable_profile now compares agent vs pawn
(walk 44.765 ≤ climb 70 → OK, exit 0). There is NO recipe-data decision for
Ryan here; `world.primary_movement_mode` "mount" in alpine_8k.json is correct as
a world-scale POI-spacing declaration (RECIPES.md:12711 marks it UNUSED by the
gate). Remaining tail: `recipes/schema.md` §ruling-19 still stated the old
comparand — corrected in the same window.

--- (original mistaken escalation, kept for the record) ---
## O-6 (2026-09-18, Pass-3 reading): RULING-19 gate fires on the shipped recipes — nav agent (walk) exceeds the world's primary mode (mount)

`scripts/verify_walkable_profile.py` run offline **exits 5 (RULING 19
VIOLATED)** against the committed recipes: the navmesh `agent_profile` is
`"walk"` (44.765 deg) but `world.primary_movement_mode` in
`recipes/alpine_8k.json` is still `"mount"` (35 deg), and ruling 19 requires
nav agent ≤ world primary. **This is a recipe-DATA question, not a tool bug —
the gate is doing exactly its job** (it caught a real inconsistency), which is
why nothing in the recipe was changed.

The likely cause: `character.json`'s `_agent_profile_changed_20260826` note
records the navmesh agent being moved mount→walk (44.765) so the town's outer
third became reachable, but `alpine_8k.json`'s `world.primary_movement_mode`
was left at `"mount"`. Two resolutions, Ryan's call:
- update `alpine_8k.json` `primary_movement_mode` to `"walk"` (or `"climb"`)
  to match the navmesh the town actually needs, **or**
- rule that ruling 19 no longer holds / needs revisiting given the mount agent
  was retired (nothing mounted exists in the project — see the character.json
  note).

Adjacent to the town-reachability navmesh work; not blocked on idling. Found
during the Pass-3 reading of verify_walkable_profile (worklist entry has the
detail); the tool's own fixes (exit-code doc, fail-direction, honest verdict)
landed this window.

---

## O-7 (2026-09-18, Pass-3 reading): hlod_build_batched per-batch "did nothing" test uses a WHOLE-WORLD metric — can HALT a clean batch

`scripts/hlod_build_batched.py` decides whether each batch did anything from
`did_nothing = (not --no-force and stale_before > 0 and stale_delta <= 0)`,
where `stale_before`/`stale_delta` come from `layer_census()` — which counts the
**whole world** (all ~2267 packages), not the batch's own ~189-cell section.

**Consequence:** a batch whose section held ZERO stale cells (all already
current) leaves the whole-world stale count unchanged, while OTHER batches keep
it `> 0`, so `stale_delta <= 0` and `did_nothing` fires. The batch is marked
failed, retried once, fails identically, and the ruled build HALTS
(`cmd_run` `raise SystemExit`) — even though the batch built cleanly. Nothing
guarantees the engine's hierarchy-grouped partition puts a stale cell in every
section, so this can stop a legitimately-successful run.

**Why not fixed this pass:** the correct test scopes stale to the section's own
GUIDs (`sections["HLODBuilder%d" % idx]` from `parse_manifest`), which needs a
GUID→package map and a live editor to verify; rewriting the ruled build's
pass/fail blind (the tool is not in the offline suite and cannot be run here) is
the exact "author over a graph they can't check" risk the constitution warns
about. The limitation is documented in-code at the `did_nothing` computation.

**What would unblock it:** a session with the editor available, to build the
GUID→package mapping and confirm a section-scoped `stale_before`/`stale_delta`
against a real partitioned manifest. The safe verdict/exit-code findings from
the same read (WORLD UNIFORM positive-confirmation, NOT-DONE exit code,
plan GUID-count refuse + --allow-partial, git-commit read-back, plan zero-sample
floor) DID land this window.

**UPDATE 2026-09-19 — the SAVE-COST half is now MEASURED and de-risked (the
did_nothing metric fix itself is unchanged/open).** The session goal was the
per-package save-cost pilot (`hlod_setup_layers.py`, Pass-3-fixed so it actually
saves), and it ran on a fresh `/Game/Alpine8K` editor: per-package save is cheap
— props ~12 ms (n=17), foliage ~11.5 ms (n=41), landscape proxy ~0.56 s (n=21);
whole-world PROJECTS to ~3 min, proxy-dominated. So the 2026-09-07 90-min hang
was the BULK save call, not per-package cost, and a wider assignment/build's SAVE
is affordable. Evidence `_verify/hlod/save_cost_pilot_2026-09-19/RESULTS.md`;
locked in R-HLOD (AMENDED 2026-09-19). This does NOT fix the `did_nothing`
section-scoped-stale metric — that still needs the GUID→package map + a real
partitioned manifest (unchanged above) — but it removes the save-cost fear that
gated any wider HLOD work, and it proves the assignment save path works end to
end. The full whole-world assignment stays deliberately unrun (projection, not
measurement; and the `_Landscape`-redundant / FoliageApprox-for-all policy is
unsettled — it wants its own session with a named restore tag).
