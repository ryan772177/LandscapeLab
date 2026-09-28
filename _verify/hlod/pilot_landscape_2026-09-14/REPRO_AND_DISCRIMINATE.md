> # ⛔ SUPERSEDED IN PART — 2026-09-14 by `FLATTEN_PATH_VERDICT.md`
>
> **"32 reproduced exactly" IS WRONG.** The build produced 1024×1024, as it
> did every other time; the 32 came from the editor read-back, not the
> commandlet. Re-run on 2026-09-14: three texture sources, all 1024×1024,
> read off disk with no editor.
>
> **The finding that survives — and it was the right one — is "NEITHER
> POLICY BRANCH PREDICTS 32".** That is correct, and the explanation is the
> one this file could not reach: **no branch predicts 32 because 32 was
> never an output.** `SpecificSize` ran, and it produced 1024.
>
> ⚠ `MinVisibleDistance` is **25,600 cm**, not 76,800. Every arithmetic
> table below uses the wrong D.
>
> The "unintended write" section stands as a process lesson, but its net
> effect was neither corrective nor harmful: there was no deviation to repair.

# 32 reproduced and attributed — and task 3 is blocked by the Python surface

**32 reproduced exactly. The mesh input is NOT degenerate, and NEITHER
policy branch predicts 32 with it.** So the earlier elimination argument
is wrong too, and the cause is outside `ComputeRequiredTextureSize`.

**Task 3 could not be run: `set_min_visible_distance`,
`get_min_visible_distance` and `get_hlod_hash` do not exist in the
Python binding.**

⚠ **And one unintended write, reported in full below: the editor's
in-memory 1024 was saved over the commandlet's 32. Net effect is
benign — it repaired last session's deviation — but it was not
intended.**

---

## 1. The fixup, verbatim, and whether it is in force

`Landscape.cpp:5044-5049`, at the end of `ALandscapeProxy::PostLoad()`
(`:4686`–`:5051`), inside `#if WITH_EDITOR`:

```cpp
5044| // Keep previous behavior of landscape HLODs if created before the settings were added
5045| if (GetLinkerCustomVersion(FFortniteMainBranchObjectVersion::GUID) < FFortniteMainBranchObjectVersion::LandscapeAddedHLODSettings)
5046| {
5047| 	HLODTextureSizePolicy   = ELandscapeHLODTextureSizePolicy::AutomaticSize;
5048| 	HLODMeshSourceLODPolicy = ELandscapeHLODMeshSourceLODPolicy::AutomaticLOD;
5049| }
5050| #endif // WITH_EDITOR
```

**The condition is the package's LINKER custom version** — the version
recorded in the file as it was loaded, not a runtime flag.

**It runs in BOTH processes.** The commandlet is `UnrealEditor-Cmd`, an
editor build, so `WITH_EDITOR` is defined and `PostLoad` is the same
code path. There is no commandlet-only branch here.

**Therefore the editor read was NOT wrong, and the fixup does not
explain the divergence.** If the packages were old enough to trip the
condition, the editor would have reported `AutomaticSize` too — it
reported `SPECIFIC_SIZE` on 256/256 with 0 raised. R-HLODTEX saved all
257 proxy packages on 2026-09-13, which updates their linker version, so
by both the full build and this pilot the condition is false and
**`SpecificSize` is in force in both processes.**

That is the opposite of what I predicted last session, and it matters:
the "legacy fixup" candidate is now **REJECTED**, by the same line that
was supposed to support it.

## 2. Reproduction — 32 again, with the term named

`-BuildSingleHLOD` on the same cell, D unchanged. 0.34 min, VRAM peak
2,937 MiB, 1 cell, 1 approval.

Read back from the built asset:

| `:218-219` term | value |
|---|---|
| triangles (LOD0) | 72 |
| box extent | 38 100 × 38 100 × 44 643 cm (**762 m footprint**) |
| sphere radius | 69 689.4 cm |
| footprint area | 5.806e9 cm² |
| `TexelRatio = 100/√area` | 0.00131234 |
| **baked textures** | **32 × 32** (BaseColor, Normal, MRS) |

**Acceptance met: 32 reproduced.** But the term that was supposed to
explain it does not:

| branch | prediction with THIS mesh at D = 76 800 | observed |
|---|---|---|
| AutomaticSize | density 2.22222 → perfect 1694 → lo 1024 / hi 2048 → **2048** | 32 |
| SpecificSize | 4096 → `Max(_,16)` → `Min(_,1024)` → **1024** | 32 |

**The mesh is not degenerate** — 762 m across, larger than the 508 m
proxy, which is right for a 1024 m L2 cell. So the "degraded mesh input"
hypothesis from the previous report is **REJECTED by measurement**.

⛔ **Neither branch produces 32 from these inputs.** Something outside
`ComputeRequiredTextureSize` is setting the final size. The remaining
place it can happen is between `:247-251` (where `InTextureSize` is
applied to five flatten properties) and the texture creation — most
likely inside `FMaterialUtilities::ExportLandscapeMaterial` (`:252`),
which was not read this session. **That is the next file to open, and I
am not guessing at it.**

## 3. Discriminator — BLOCKED, not skipped

All three accessors the task names raise `AttributeError` on the Python
object:

    set_min_visible_distance   'WorldPartitionHLOD' object has no attribute
    get_min_visible_distance   'WorldPartitionHLOD' object has no attribute
    get_hlod_hash              'WorldPartitionHLOD' object has no attribute

This is the same wall as before: `AWorldPartitionHLOD` exposes almost
nothing to Python. The 5.8 documentation page lists these as C++ API;
they are not in the reflected Python surface, and the doc page does not
distinguish the two.

**The accessible route instead** — not taken, because this session
forbids layer changes: `MinVisibleDistance` is written onto the HLOD
actors at `-SetupHLODs` time from the layer's creation params
(`WorldPartitionHLODUtilities.cpp:421-424`), and the HLOD **layer's**
`loading_range` IS reflected and readable (76 800 on Instanced, read
2026-09-13). So the discriminator is reachable as:

    set Instanced layer loading_range 76 800 -> 51 200
    -SetupHLODs        (rewrites MinVisibleDistance on the actors)
    -BuildSingleHLOD   (rebuild the one cell)
    read dimensions

That is a layer change and needs a ruling.

## ⚠ The unintended write

Sequence, stated plainly:

1. Commandlet build wrote the cell at **32** to disk.
2. Editor launched; first read returned **32** (correct, from disk).
3. My payload attempted `set_min_visible_distance`, which raised — and
   then **still executed its save step**, calling
   `EditorLoadingAndSavingUtils.save_packages([cell_package])`.
4. That wrote the editor's in-memory copy — **1024** — over the file.
5. Subsequent reads return 1024, and the package mtime is the save.

**The fault is mine and it is a design fault in the payload**: the save
was not made conditional on the write succeeding. A write that raises
should abort the save, not fall through to it.

**Blast radius, measured:** exactly **1** package written since the
build (`find -newermt`), the pilot cell only; dirty census 0; no
collateral.

**Net effect is benign and actually corrective:** the cell is now 1024,
matching its 255 siblings, so last session's reported deviation is
repaired. But it was not intended, and the 32 no longer exists on disk —
only in this report and in `repro_D76800.log`.

Where the in-memory 1024 came from is itself unexplained: the editor
read 32 from disk at step 2 and held 1024 by step 3. Either the actor
was reloaded/regenerated in between, or the editor's HLOD path produced
1024 where the commandlet produced 32 — **which would be the same
discrepancy, seen from the other side.** Worth pursuing; not pursued
here.

## Recommendation

**Neither "raise the cap" nor "change policy handling" is supported
yet.** Both rested on the branch question, and the measurement has now
ruled out the mechanism both arguments assumed:

* `SpecificSize` is in force (fixup rejected at `:5045`).
* `SpecificSize` predicts 1024, and 1024 is what 256 of 257 cells carry.
* The single-cell path produces 32 from inputs that predict 1024 —
  so the divergence is **not** in the policy branch at all.

**Do not raise the cap yet.** The cap only binds under `SpecificSize`,
which is in force, so raising it to 4096 *would* lift 1024 → 4096 for a
normal full build — but the single-cell path is doing something else
entirely, and shipping a cap change while one build path produces 32×32
would bake that anomaly into whichever cells it touches.

**Next step is one file, not one experiment:** read
`FMaterialUtilities::ExportLandscapeMaterial` and the flatten-material
path between `LandscapeHLODBuilder.cpp:247` and `:270` to find what
overrides `InTextureSize`.
