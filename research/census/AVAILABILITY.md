# Sample project availability — checked 2026-09-09, before any editor launch

**Two of the four projects are not installed on this machine.** Checked first
because each census costs an editor launch on a large project, and "record why
and move to the next" is cheaper before the launch than after.

| # | Project | Stated path | Reality |
|---|---|---|---|
| 1 | Electric Dreams | `C:\Users\Admin\Samples\ElectricDreams` | **NOT INSTALLED** |
| 2 | City Sample | `VaultCache\CitySample_5.8\data` | **REAL** — 147,931 `.uasset` |
| 3 | Valley of the Ancient | `VaultCache\AncientGame_5.7\data` | **REAL** — uproject + Content |
| 4 | Dark Ruins | `C:\Users\Admin\Samples\DarkRuins` | **NOT INSTALLED** |

## `C:\Users\Admin\Samples` does not exist

It holds one entry, `CitySample`, and that has no `.uproject`. The name in the
brief is close to `C:\Users\Admin\samples_text\`, which does contain
directories named exactly `ElectricDreams` and `DarkRuins` — so the paths look
right at a glance.

**`samples_text` is a TEXT EXTRACT, not a set of projects.** Each holds only
`Config/` and a `.uproject`:

    ElectricDreams        66 KB    0 .uasset   0 .umap
    DarkRuins             74 KB    0 .uasset   0 .umap
    ValleyOfTheAncient   210 KB    0 .uasset   0 .umap

Opening one would load an empty world, and the census would return a
structurally valid JSON full of empty sections — **a plausible artefact from a
project with no content**. That is the failure this check exists to prevent;
it is the same shape as rendering the wrong level and passing every tonal
check.

## 1. Electric Dreams — partially staged, never extracted

    VaultCache\ElectricDreamsSample_5.8\
      data\     EMPTY
      stage\    c\ f\ m\   — 808 MB of launcher chunk format

The vault entry exists and has bulk, which is why a size check alone would
have said "present". There is no `.uproject` anywhere under it and no
`.uasset`. This is an interrupted or un-finalised download: the launcher
stages chunks under `stage\` and only materialises `data\` on completion.

**To census it, install/finish it from the Epic launcher first.**

## 4. Dark Ruins — no real copy anywhere

A bounded search of `C:\Users\Admin`, `C:\ProgramData\Epic` and `D:\` for
`*darkruin*` found only the `samples_text` extract. Not in VaultCache.

**To census it, install it first.**

## 3. Valley of the Ancient — BLOCKED: C++ modules built for 5.7

The project opens, converts, and then **exits before loading anything**,
because it is a C++ project whose compiled modules are 5.7 binaries. From the
log, one bounded attempt (90 s):

    LogInit: Warning: Still incompatible or missing module: AncientGame
    LogInit: Warning: Still incompatible or missing module: InstanceLevelCollision
    LogInit: Warning: Still incompatible or missing module: Crossfader
    LogInit: Warning: Still incompatible or missing module: Uproar
    LogInit: Warning: Still incompatible or missing module: Underscore
    LogInit: Warning: Still incompatible or missing module: HoverDrone
    LogCore: Engine exit requested (reason: EngineExit() was called)

Interactively the editor offers to rebuild; non-interactively it just exits.
The operator hit the same wall by hand — *"says i need to rebuild manually it
was missing things"* — so this is confirmed from two directions.

**It is rebuildable, and that is a real build, not a flag.** Source is present
for the game module and for all six plugin modules:

    AncientGame              Source/AncientGame        prebuilt: 5.7 DLL only
    Crossfader               source yes                5 binaries (5.7)
    Uproar                   source yes                5 binaries (5.7)
    Underscore               source yes                5 binaries (5.7)
    HoverDrone               source yes                3 binaries (5.7)
    InstanceLevelCollision   source yes                3 binaries (5.7)
    ModularGameplayActors    source yes                3 binaries (5.7)

To census it: generate project files against 5.8 and build the editor target
in Visual Studio, then re-run. That is a compile of seven modules, needs a
working C++ toolchain, and is well outside "one bounded attempt per project" —
the brief's own instruction is to record why and move on, which is what this
is.

**No assets were saved and nothing was written into the project** beyond
whatever the engine touched while attempting to open it.

## What proceeded

Only **City Sample**. Of the four projects in the brief, one censused, one is
blocked on a C++ rebuild, and two are not installed.
