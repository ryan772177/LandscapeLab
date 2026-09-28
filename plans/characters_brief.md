# CHARACTERS — the domain brief, re-run

*`PHASE2_PLAN.md` unit 4. Written 2026-08-15. The first attempt returned one
sentence and three other briefs filled the vacuum incompatibly; §4 item 2 says
**do not proceed on the union of three partial guesses**, so nothing here is
inherited from them. Every asset claim below was measured on 2026-08-15 —
either by `scripts/probe_skeleton.py` against the running editor, or by
enumerating the engine install on disk.*

**Blocking:** units 5 and 12.

---

## 1. THE SKELETON RULING, CITED BY BONE PROBE

`scripts/probe_skeleton.py`, artefact `Free/_measured/skeletons.json`.
Controls `pelvis` and `hand_l` (present in both generations) pass on every
asset, so an absent UE5 marker is a real absence and not a broken probe.

| asset | class | bones | `spine_04` | `spine_05` | `clavicle_out_l` | `index_metacarpal_l` | verdict |
|---|---|---|---|---|---|---|---|
| `/Game/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton` | Skeleton | **68** | ✗ | ✗ | ✗ | ✗ | **UE4** |
| `/Game/Mannequin/Character/Mesh/SK_Mannequin` | SkeletalMesh | 68 | ✗ | ✗ | ✗ | ✗ | **UE4** |
| `/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SK_Mannequin` | Skeleton | **161** | ✓ | ✓ | ✓ | ✓ | **UE5** |
| `/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SKM_Manny` | SkeletalMesh | 161 | ✓ | ✓ | ✓ | ✓ | **UE5** |

**RULING: the character skeleton is the UE5 mannequin, 161 bones.** This
confirms `PHASE2_PLAN.md` ruling 15 by measurement, and confirms that
`ASSETS.md:78`, which calls the **UE4** asset the GASP retarget target, is
wrong. `/Game/Mannequin/` is UE4-era content in a folder whose name gives no
hint of it — which is why this was probed rather than read off a name.

### AND THE SOURCE IS THE ENGINE TEMPLATE, NOT THE IN-PROJECT COPY

There are two UE5 mannequins available. They are not interchangeable.

| | in-project (GV pack) | engine template |
|---|---|---|
| path | `/Game/GV_FreeShrubsPack/Demo/Mannequin/` | `UE_5.8/Templates/TemplateResources/High/Characters/Content/Mannequins/` |
| mesh | `SKM_Manny`, 27.44 MB | `SKM_Manny_Simple` 15.09 MB, `SKM_Quinn_Simple` 15.5 MB |
| **physics asset** | **NONE** | **`PA_Mannequin`** |
| control rigs | 1 (`CR_Mannequin_BasicFootIK`) | 3 (`Body`, `FootIK`, `Procedural`) |
| animations | 9 | **102** |
| licence | part of the ~3.5 GB Fab gap, **no `ASSETS.md` row**, gitignored | engine EULA, already on this disk |

**Migrate the engine template set.** Four independent grounds, any two of
which would be enough:

1. **It carries `PA_Mannequin`.** The in-project Manny has **no physics
   asset at all**, so ragdoll has nothing to build on. The only physics asset
   in the project is `SK_Mannequin_PhysicsAsset`, bound to the **UE4**
   skeleton — which is the asset the `physics` brief's P4 ragdoll design was
   built on, and it is the wrong skeleton by this probe.
2. **The 102 animations are authored against it.** Taking the mesh from one
   source and the animations from another is how a retarget becomes
   necessary; taking both from one source is how it stays unnecessary (§2).
3. **Licence.** Engine EULA content with a known origin, against a pack that
   is currently the project's only unmet `R-ASSET` requirement.
4. It is gitignored vendor content. A character rig is not something to build
   a game on top of when it vanishes on a re-download.

**REJECTED: the UE4 mannequin at `/Game/Mannequin/`.** 68 bones, no UE5
markers. Keep it on disk (it costs nothing) but nothing may target it.

---

## 2. THE RETARGET CHAIN: THERE ISN'T ONE, AND THAT IS THE FINDING

**Phase 2 needs no retarget.** The 102 template animations and
`SKM_Manny_Simple` share one skeleton asset; migrating them together brings
the animation set already bound. Retargeting becomes necessary only when
non-mannequin creatures arrive (`PHASE2_PLAN.md` §4 item 6), which is
explicitly *acquire later*.

**ONE TRAP, AND IT IS CREATED BY THE MIGRATION ITSELF.** After migrating,
the project will hold **two different UE5 mannequin skeletons** — the
template's and the GV pack's — both 161 bones and both plausibly named
`SK_Mannequin`. Animations bound to one **will not play** on a mesh bound to
the other, and the failure is a silent T-pose rather than an error.

- **Verify before assuming they are the same asset.** Identical bone counts
  are not identity. Re-run `probe_skeleton.py` against both after migration;
  it prints the resolved skeleton path per mesh, which is the discriminating
  field.
- If they differ and both must exist, the mechanism is
  `Skeleton.compatible_skeletons` (PythonStub 255051) — *"This skeleton will
  be able to use animation data originating from skeletons within this
  array"*. Set it deliberately; do not rely on it accidentally.
- **Preferred: do not keep both.** The GV pack's Manny is demo content for a
  shrub pack. Nothing should reference it.

---

## 3. ANIMATION BUDGET — 102 SHIPPED, 42 USABLE

Measured on disk: 102 assets, 42.6 MB.

| set | assets | MB | usable for this game |
|---|---|---|---|
| Rifle | 39 | 13.5 | **8 only** — the `HitReact` subfolder |
| Pistol | 29 | 12.2 | 0 |
| Unarmed | 28 | 15.2 | **28** |
| Death | 6 | 1.7 | **6** |

**68 of the 102 are weapon-specific animations for a shooter.** This is a
melee/mounted RPG, so the honest usable count is **42**, not 102 — and the
plan's "~110 animations" as a headline overstates what this project gets.

**AND THE 8 HIT REACTS ARE FILED UNDER `Anims/Rifle/HitReact/`.** They are
upper-body reactions and have nothing to do with rifles, but a session told
"take the Unarmed folder" will miss all eight. Named here because that is
exactly the shape of a step that gets ticked off.

**What the Unarmed set actually covers** (verified by listing):

    ABP_Unarmed, BS_Idle_Walk_Run, MM_Idle
    Attack/    MM_Attack_01, _02, _03, MM_ChargedAttack        4 melee attacks
    Walk/      8-way                                            8
    Jog/       8-way                                            8
    Jump/      MM_Jump, MM_Fall_Loop, MM_Land, MM_Dash, MM_WallJump

So melee locomotion and a three-hit combo plus a charged attack are **free**.

**GAPS, and none is blocking for Phase 2:** no mounted animations at all —
which matters because `WORLD_VISION.md` ruling 2b makes mounts first-class and
sizes POI spacing against mounted speed; no sheath/unsheath; no block or
parry; no gather/interact. All are authored or bought after Phase 2.

---

## 4. LOD BUDGET — AND A BROKEN CHAIN, MEASURED

`SKM_Manny` (in-project), via `SkeletalMeshEditorSubsystem`:

    LOD      0        1        2       3
    verts  48,779   48,779   14,962   7,525
    sections   2        2        2       2
    material slots 2

**LOD0 AND LOD1 ARE IDENTICAL AT 48,779 VERTICES.** A four-entry chain whose
first reduction step reduces nothing is a three-entry chain that costs a
fourth entry's memory — and the first step is normally the most valuable one,
because it is the one that fires soonest and covers the most screen area.

**This is measured on the GV pack's mesh, which we are not adopting.** It is
carried here as a REQUIRED CHECK, not as a finding about the mesh we will
ship: re-run against `SKM_Manny_Simple` immediately after migration. If it
repeats, the first reduction needs authoring; if it does not, the GV mesh was
simply imported without reduction and nothing is owed.

**Budget rule for Phase 2:** the player is one character at LOD0; enemies are
`N` characters mostly at LOD2/LOD3. Sizing the enemy cost off LOD0's 48,779
verts overstates it by ~3.3× at LOD2 and ~6.5× at LOD3, so any encounter
budget must state which LOD it assumed.

---

## 5. ROOT MOTION POLICY

**RECOMMENDED — root motion OFF for locomotion, ON for attacks and deaths.**
`UCharacterMovementComponent` drives movement (`PHASE2_PLAN.md` ruling 5), so
locomotion must be in-place and blended; attacks and deaths are montages
where the animation should own the displacement.

The folder naming is consistent with that split — locomotion is `MF_`
prefixed, attacks and deaths are `MM_` — **but this is an inference from a
naming convention and is explicitly NOT verified.** The template assets are
not mounted in this project, so nothing here could read them.

**The check, to run in the same session as the migration:** read
`enable_root_motion` on `MM_Attack_01`, `MM_Death_Front_01`,
`MF_Unarmed_Jog_Fwd` and `MM_Idle`. Four assets settle the whole policy. If
the convention does not hold, the policy stands and the assets are corrected
to match it, rather than the policy bending to the assets.

---

## 6. PER-CHARACTER COST — THE EXPERIMENT, NOT A GUESS

Unit 4's acceptance asks for a **proposed measurable** cost, and this
deliberately does not invent a millisecond figure. `PHASE2_PLAN.md` ruling 12
already records that every per-domain millisecond allocation in the original
briefs was PROPOSED and read like a ruling; adding another would repeat that.

**Why this is the number that matters.** Unit 1 measured the game thread at a
fixed ~7 ms with zero gameplay, against a 16.67 ms frame — and skeletal
animation evaluation is game-thread work. The plan's estimate of 8.0 ms for
AI perception and EQS would already consume the remainder. **Character cost is
therefore the term that decides encounter scale**, which is open question 6
("how many enemies is a fight — 3, 6, 12?"). No brief had a basis for that
number; this experiment is the basis.

**THE EXPERIMENT**

1. **Settle the premise first, in isolation** — exactly as `probe_pie`
   settled remote execution before `measure_pie_cost` was written. Python's
   spawn functions (`EditorActorSubsystem.spawn_actor_from_class`,
   PythonStub 641645) target the **editor** world, not the PIE world, and
   there is no reflected spawn into a running game world. So: **do transient
   editor-world actors get duplicated into the PIE world?** `spawn_actor_*`
   takes a `transient` flag, and transient objects are ordinarily skipped by
   duplication — if they are, this route does not work and the fallback is
   non-transient actors plus a guaranteed cleanup, which dirties packages and
   needs a restore point.
2. Add `--spawn-count N` to `measure_pie_cost.py`. Everything else — PIE
   lifecycle, station establishment, the view-point gate, the throttle gate,
   CSV reduction, the artefact — already exists and must not be duplicated
   into a second tool.
3. Measure at **N = 0, 1, 6, 12, 24**, at two stations: `forest_floor`
   (GPU-heavy, the control that reproduces) and `canopy_250m` (GPU headroom,
   so a game-thread effect is not masked).
4. Characters spawn with `ABP_Unarmed` bound and ticking. A skeletal mesh
   with no animation instance costs skinning and no evaluation, and would
   under-report the game-thread term by most of it.
5. **Report the marginal cost per character on `GameThreadTime` separately
   from `GPUTime`**, with the LOD each character was at recorded — §4 says a
   figure without its LOD is not reusable.

**Terms the result should be checked against**, so an implausible number is
caught: 161 bones evaluated per character per frame (game thread); 48,779
vertices skinned at LOD0 or 7,525 at LOD3 (GPU); 2 material slots → 2 draw
calls per character per pass, and with virtual shadow maps that is more than
one pass.

---

## 7. WHAT THIS BRIEF DOES NOT COVER

- **MetaHuman.** Cut by ruling 14; re-opens on one measured spawn-N A/B,
  which is §6's experiment.
- **Creature and non-human enemies.** Manny is the stand-in. The retarget
  work in §2 is deferred with them.
- **Facial animation, lipsync, dialogue.** No assets, no dependency in
  Phase 2.
- **Clothing and attachment sockets.** Needs an art direction pass that does
  not exist yet.
- **The `Free/_intake` GASP-shaped FBX set.** 1,374 files with
  `"licence_or_readme_files_present": 0`. Rejected in `PHASE2_PLAN.md` §4 and
  nothing here revisits it.
