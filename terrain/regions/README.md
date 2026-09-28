# terrain/regions — RUNBOOK and VALIDATION RECORD

**Five candidate `.terrain` files, each a PARAMETER-ONLY variant of the
canonical AlpineLab graph. None has been opened in Gaea. None has been
built. Every landform claim in every `.md` beside them — and in this file
— is a PREDICTION FROM PARAMETERS, not a measurement.**

Written by the validator lane, 2026-08-15. Nothing here was executed
against Gaea or the editor.

---

## 0. WHAT THESE ARE, AND WHAT THEY ARE NOT

`WORLD_VISION.md:172-177` records **contiguous-vs-multi-region as an OPEN
DECISION** — *"Nothing may be built on either assumption until Ryan
rules."* So these are **EVALUATION TERRAINS**, exactly as
`AlpineLab_v1` is. They are not region two. Adopting one into the world
is a scope decision, not a build step.

They also do not satisfy the NEW-ELEMENT RULE: there is no
`recipes/<region>.json`, no `ASSETS.md` row and no `RECIPES.md` entry for
any of them. That is owed before any of them becomes content.

**Nothing in here goes near `/Game/Alpine` or `/Game/Alpine8K`.** Those
worlds carry 153,796 placed instances against a verified heightmap.

---

## 1. VALIDATION — RE-RUN INDEPENDENTLY, NOT TAKEN ON TRUST

Gates re-run by the validator on 2026-08-15 against every file present.
**The tool takes `--project <path>`; `--check-refs` and `--check-spec`
are bare flags.** The form `--check-refs <file>` exits 2 on argparse's
*"unrecognized arguments"*, which is not a graph verdict.

```
python scripts/read_gaea_graph.py --project terrain/regions/<name>.terrain --check-refs
python scripts/read_gaea_graph.py --project terrain/regions/<name>.terrain --check-spec
```

| file | `--check-refs` | `--check-spec` | sha256 (first 16) |
|---|---|---|---|
| `badlands.terrain`  | **0** | **0** | `95f89b930efbfbb3` |
| `coastal.terrain`   | **0** | **0** | `d8dc872d64255665` |
| `foothills.terrain` | **0** | **0** | `ea03912badc373c9` |
| `plateau.terrain`   | **0** | **0** | `b6073d02e4e26f0a` |
| `volcanic.terrain`  | **0** | **0** | `39487fb9c42e0572` |
| canonical `AlpineLabe_v1.terrain` | **0** | **0** | `459d5c2fc9d07b9c` |

Each reports `$id defined : 82 · $ref used : 23 · every $ref resolves to
a real $id` and *"the graph predicts exactly the SPEC's Gaea-sourced
files."*

**`--against-build` was NOT run on any of them and could not be** — no
build exists. That is *"I could not look"*, not a pass.

### The structural check the gates do NOT make

`--check-refs` proves references resolve; it would still pass a file
rewired between existing ids. So the validator walked both documents in
parallel and compared, independently of any agent's own claim:

* full key-path skeleton (every path, in document order) — **identical**
  on all five
* `$id` sequence (82) and `$ref` sequence (23), **in order** — identical
* leaf-path set (302 leaves) — identical; **no path added or removed**
* node ids `599 / 650 / 654 / 750 / 849 / 877`, their `$type`s, their
  `Ports`, and all three `SaveDefinition` bases (`Erosion2`, `Snow`,
  `SnowMask`) — **unchanged**

**Conclusion: all five differ from the canonical graph in leaf VALUES
only.** No node added, removed or rewired. The narrow safe-editing
envelope in `read_gaea_graph.py:44-51` was respected by every lane.

---

## 2. EXACTLY WHAT EACH FILE CHANGED

Canonical values on the left. Paths are under
`/Assets/$values[0]/Terrain/`.

### foothills.terrain — 8 leaves

| leaf | canonical | foothills |
|---|---|---|
| `Nodes/877/Height` (Mountain) | 2.032038 | **1.0** |
| `Nodes/654/Duration` (Erosion2) | 21.648195 | **28.0** |
| `Nodes/654/Downcutting` | 0.4531411 | **0.25** |
| `Nodes/599/SnowLine` (Snow) | 0.056395777 | **0.35** |
| four `Seed`s (877 / 650 / 654 / 599) | 22109 / 38804 / 15025 / 59434 | 30411 / 51862 / 27703 / 44190 |

### coastal.terrain — 10 leaves

| leaf | canonical | coastal |
|---|---|---|
| `Nodes/877/Height` | 2.032038 | **1.05** |
| `Nodes/877/Scale` | 0.74927175 | **0.42** |
| `Nodes/654/Duration` | 21.648195 | **14.0** |
| `Nodes/654/Downcutting` | 0.4531411 | **0.78** |
| `Nodes/654/ErosionScale` | 1413.2517 | **400.0** |
| `Nodes/599/SnowLine` | 0.056395777 | **0.62** |
| four `Seed`s | — | 41027 / 51163 / 30871 / 20514 |

### plateau.terrain — 12 leaves

| leaf | canonical | plateau |
|---|---|---|
| `Nodes/877/Height` | 2.032038 | **1.45** |
| `Nodes/877/Scale` | 0.74927175 | **0.38** |
| `Nodes/654/Duration` | 21.648195 | **31.0** |
| `Nodes/654/Downcutting` | 0.4531411 | **0.2** |
| `Nodes/654/ErosionScale` | 1413.2517 | **2297.4** |
| `Nodes/599/SnowLine` | 0.056395777 | **0.3** |
| four `Seed`s | — | 31427 / 14159 / 26535 / 48979 |
| `Metadata/Name` | *(empty)* | `PlateauLab_v1` |
| `Metadata/Description` | *(empty)* | *(authoring note)* |

### badlands.terrain — 18 leaves

| leaf | canonical | badlands |
|---|---|---|
| `Nodes/877/Height` | 2.032038 | **0.62** |
| `Nodes/877/Scale` | 0.74927175 | **1.34** |
| `Nodes/654/Duration` | 21.648195 | **30.5** |
| `Nodes/654/Downcutting` | 0.4531411 | **0.78** |
| `Nodes/654/ErosionScale` | 1413.2517 | **340.0** |
| `Nodes/599/SnowLine` | 0.056395777 | **0.88** |
| `Nodes/599/Duration` | 0.4066604 | **0.22** |
| `Nodes/599/Intensity` | 0.40226594 | **0.11** |
| `Nodes/599/SettleThaw` | 0.3619003 | **0.62** |
| `Nodes/599/Melt` | 0.450141 | **0.72** |
| **`Height`** (Terrain, project range) | **2500.0** | **1200.0** |
| **`Ratio`** | **0.5** | **0.24** |
| four `Seed`s | — | 41881 / 58207 / 70413 / 12960 |
| `Metadata/Name` + `Description` | *(empty)* | `Badlands` + note |

### volcanic.terrain — 18 leaves

| leaf | canonical | volcanic |
|---|---|---|
| `Nodes/877/Height` | 2.032038 | **2.75** |
| `Nodes/877/Scale` | 0.74927175 | **0.9** |
| `Nodes/654/Duration` | 21.648195 | **4.2** |
| `Nodes/654/Downcutting` | 0.4531411 | **0.68** |
| `Nodes/654/ErosionScale` | 1413.2517 | **2300.0** |
| `Nodes/599/SnowLine` | 0.056395777 | **0.02** |
| `Nodes/599/Duration` | 0.4066604 | **0.55** |
| `Nodes/599/Intensity` | 0.40226594 | **0.72** |
| `Nodes/599/SettleThaw` | 0.3619003 | **0.78** |
| `Nodes/599/Melt` | 0.450141 | **0.22** |
| four `Seed`s | — | 48213 / 26907 / 33641 / 51078 |
| **`/Id`** (document) | `816bb8b4` | **`c47a1f92`** |
| **`Assets/$values[0]/Id`** (GUID) | `9381bbdc-…` | **`5f2c8ae1-…`** |
| `Metadata/Name` + `Description` | *(empty)* | `Volcanic Ashlands` + note |

---

## 3. FLAGGED — read before building

### 3a. `plateau` typed a WORLD-METRE answer into a CANVAS-UNIT field

`plateau.md` justifies `ErosionScale 2297.4` as compensating the import
stretch: *"1413.2517/5000 = 0.28265 of `Terrain.Width`; ×(8128/5000 =
1.6256) = 2297.38."* **2297.38 m is alpine's erosion scale ALREADY
EXPRESSED IN WORLD METRES.** `Terrain.Width` is still 5000 in that file
(unchanged — I checked), so the parameter is still read against a 5000
canvas and the 1.6256 stretch applies on top:

```
                ErosionScale   / Width 5000   x 8128 m extent   vs alpine
alpine / foothills  1413.2517     0.28265        2297.4 m         1.00x
coastal              400.0        0.08000         650.2 m         0.28x
badlands             340.0        0.06800         552.7 m         0.24x
plateau             2297.4        0.45948        3734.7 m       **1.63x**
volcanic            2300.0        0.46000        3738.9 m       **1.63x**
```

The 1.63× is exactly the stretch factor it meant to cancel — the
signature of a units error, the same class as this project's own
metres-as-centimetres trap. The number may still be *wanted* for a broad
plateau, but it is **not** what its stated derivation computes, and it is
labelled `MEASURED` in that note. Read it as a hypothesis.

`volcanic.md` sets nearly the same value and states the consequence
correctly (*"3739 m world metres"*), so volcanic is honest about it. Both
files put erosion features at ~3.7 km across an 8.128 km region — **about
two drainage cells edge to edge.** Expect little or no visible drainage
network in either. That is the "erosion scale fights the extent" case.

### 3b. `badlands` moved `Terrain.Height`, and its own Z prediction contradicts its own Mountain edit

`badlands.terrain` is the only file that touches `Terrain/Height`
(2500 → 1200) and `Ratio` (0.5 → 0.24; 1200/5000 = 0.24, so the pair is
self-consistent).

This is **not** the 2.7× trap — that trap is typing `Terrain.Height`
straight into the import dialog. `rebuild_terrain.read_project_height_m`
(`:166-205`) reads this field and `derive_z_scale` (`:147-163`) multiplies
it by measured occupancy, so a lowered project range flows through
correctly. **But it is a second relief reduction stacked on the first,
and the two multiply**: Mountain.Height is also down to 0.62 (30.5% of
alpine).

`badlands.md` predicts span ≈ 444.4 m by borrowing alpine build 006's
occupancy 0.37035 — i.e. **by assuming `Mountain.Height` had no effect on
occupancy**, which is the opposite of the reason it was lowered. If
occupancy falls anywhere near proportionally, span lands closer to
~135 m over 8128 m. Treat 444 m as an upper bound, not an estimate.
`height_normalization.json` is the only value of record.

### 3c. Snow degeneracy — a refusal is likely on TWO files, in OPPOSITE directions

`verify_build.SPEC` (`verify_build.py:80-86`) **requires**
`Snow_Snow.png` and `SnowMask_Out.png`, and `MIN_UNIQUE = 16` (`:59`)
refuses a channel carrying fewer distinct values (exit 4). R-GAEA §2:
Gaea 2.3 exports a degenerate near-1-bit PNG **when the sim output is
uniform** — uniform in *either* direction.

`SnowLine` is INVERTED: **lower = more snow** (R-GAEA §2). Canonical is
`0.056395777`, i.e. near-maximum snow.

| file | `SnowLine` | direction vs alpine | degeneracy risk |
|---|---|---|---|
| `volcanic` | **0.02** | MORE snow than alpine, plus `Intensity` 0.40→0.72 | **SATURATED-uniform** |
| `badlands` | **0.88** | far less snow, plus `Intensity` 0.40→0.11 | **EMPTY-uniform** |
| `coastal` | 0.62 | less snow | moderate |
| `foothills` | 0.35 | less snow | low |
| `plateau` | 0.30 | less snow | low |

`badlands.md` names its own risk. **`volcanic.md` does not** — it frames
the Snow node as an ash mantle covering everything, which is precisely a
uniform sim. A mask that covers 100% is as degenerate as one that covers
0%. If either build refuses at exit 4, the fix is `SnowLine` alone: move
it toward the middle, rebuild, do not edit anything else.

### 3d. `volcanic` changed two IDENTITY leaves, not only parameters

`volcanic.md` states *"18 parameter leaves changed, 0 structural"*. The
count is right; the composition is not. Two of the eighteen are Gaea's
own asset identity (`/Id` and the asset GUID) and two are `Metadata`
strings. Neither is a `$id`/`$ref`, so **reference integrity is
unaffected** and every gate still passes — a distinct project arguably
*should* carry a distinct GUID. Recorded because the note's own summary
does not distinguish them.

### 3e. Every lane reports the same structural verdict, and they are right

All five notes conclude the region as briefed is **not fully reachable by
parameter variation**, and they converge on the same cause: the graph is
`Mountain + Ridge → Combine[Max] → Erosion2 → Snow` — peak generators, a
selector, a relief-*differentiating* simulation and a veneer. There is no
node with a concept of an absolute datum, a flat tread, a closed basin or
a direction. `Ridge` serialises **only `Seed`** (confirmed in the
canonical graph printout), so ridged noise has no amplitude control at
all.

The named additions (`Stratify`, `Lake`, `Sea`, `Canyon`, `Volcano`,
`LinearGradient`) are **not in these files and must not be hand-written.**
The correct route is the one the notes give: open the file in the Gaea
GUI, drop the node in, wire it, save — Gaea allocates the `$id`s — then
re-run `--check-refs`, which is exactly what that gate exists for.

### 3f. `RECIPES.md` R-GAEA §1 disagrees with the canonical file

R-GAEA §1 (`RECIPES.md:2963`) summarises the Snow node as
`Snow Line ~0.65`. The canonical file says **`0.056395777`** — opposite
ends of an inverted control, in a summary block a fresh session would
trust. **Reported, not fixed** (Ryan's file). First surfaced by the
coastal lane; independently confirmed here against
`read_gaea_graph.py --project <canonical>`.

---

## 4. RUNBOOK — GAEA

### 4a. The autosave trap — confirm the file before you trust it

```
CANONICAL   C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain
            sha256 459d5c2fc9d07b9cc19f4b08b2818d6c503119e95caf5c2cc57e6c7efc283346
AUTOSAVES   %APPDATA%\QuadSpinner\Gaea\2.0\Autosaves\      (121 entries)
```

Verified 2026-08-15: a recursive search of `C:\Dev\LandscapeLab` returns
**exactly one** `.terrain`, the canonical one. Every other
`AlpineLabe_v1*.terrain` on this machine is an autosave Gaea **rotates
and overwrites**. `rebuild_terrain.py` REFUSES to build the canonical
terrain from one (`:238-246`) and it is right to.

**The same trap now applies to these five.** The moment Gaea opens
`foothills.terrain` it starts autosaving into that same APPDATA folder.
`terrain/regions/<name>.terrain` in this repo is the canonical copy; an
autosave is a derived record. If you change something in the GUI, **save
back over the repo file deliberately** (`File > Save As`) — do not build
from an autosave.

### 4b. Open and inspect

1. Launch Gaea 2 (`C:\Program Files\QuadSpinner\Gaea 2`), `File > Open`,
   point at `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\<name>.terrain`.
2. You should see **six nodes**: `Mountain(877) + Ridge(650) →
   Combine(750)[Max] → Erosion2(654) → Snow(599)`, with `Snow.Depth →
   SnowMask(849)` (an Autolevel). If you see any other count, you are not
   looking at one of these files.
3. Three save nodes are enabled, with **bases** `Erosion2`, `Snow`,
   `SnowMask`, PNG16. Do not rename them — `--check-spec` refuses (exit 4)
   if a base moves, and `verify_build` then refuses the package.

### 4c. Resolution and export settings

* **Build at `8192`.** Gaea 2.3.0.1 **Indie** caps export at 8K, so 8192
  is exactly at the cap and is proven on this install (build `006`).
* **8129 is NOT a Gaea resolution.** It is the UE landscape vertex count
  produced *downstream* by `resize_gaea_build.py`. The arithmetic, from
  `rebuild_terrain.py:636-637`: `quads = 8192//64 - 1 = 127`, target
  `= 127*64 + 1 = 8129`. 8129 is also `254 × 32 + 1`, the 32-component
  layout the 1 m/vertex work uses.
* **Which maps.** Do not choose — the graph already declares them, and
  `--check-spec` has confirmed the declaration matches `verify_build.SPEC`.
  A build emits six PNG16 files:

  ```
  Snow_Out.png        the raw height   -> EXCLUDED, archived, never imported
  Erosion2_Flow.png   drainage mask
  Erosion2_Wear.png   wear mask        (low range, needs remap)
  Erosion2_Deposits.png                (very low range, needs strong remap)
  Snow_Snow.png       hard coverage    (degeneracy-checked)
  SnowMask_Out.png    graded depth
  ```

  `AlpineLab_v1_Height_normalized.png` and `AlpineLabHeight.png` are
  **derived downstream** by `rebuild_terrain.py`, not exported by Gaea.

### 4d. Headless — this is the supported path

`Gaea.BuildManager.exe` **does not work on the Indie licence** and
licensing did not fix it: it is an apphost with no
`Gaea.BuildManager.dll` behind it (R-GAEA §9). **`Gaea.Swarm.exe` is the
headless path.** Do not call it directly — `rebuild_terrain.py` wraps it,
and the wrapper carries three things a bare call does not:

* Gaea Swarm **dies 1.3 s in if its stdout is piped**
  (`System.IO.IOException: The handle is invalid`, exit `0xE0434352`).
  The wrapper launches it with `CREATE_NEW_CONSOLE`
  (`rebuild_terrain.py:388-392`). This is why the build is adjudicated
  from the artefact, not from a transcript.
* the normalization + `height_normalization.json` sidecar, **which is the
  only place the UE Z scale ever comes from**;
* a timeout that scales as `(resolution/4096)²`, so 8192 gets 4 hours.

---

## 5. RUNBOOK — GAEA BUILD TO UE LANDSCAPE

### THE TRAP THAT AFFECTS EVERY REGION — read this first

**`rebuild_terrain.py:89` `DEFAULT_ROOT` and `:96` `HEIGHT_OUTPUT` are
both keyed to alpine.**

* `DEFAULT_ROOT = C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1` — building
  without `--root` writes a region into **alpine's `NNN` sequence**. Same
  class as the talus cache that overwrote alpine's.
* `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"` and
  `HEIGHT_IMPORT_ALIAS = "AlpineLabHeight.png"` are **constants**, and
  `verify_build.SPEC` keys on the same names (`verify_build.py:66`,
  `ALIASES:109-111`). `--root` fixes the directory; **no flag fixes the
  filename.** A foothills build therefore emits its heightmap under an
  **alpine** name and `verify_build` passes.

Both are single declarations that must move together (non-negotiable 24).
Until they do: **`--root` is MANDATORY for every region build**, and the
directory is the only thing that tells you whose heightmap you are
holding. All five lanes found this independently; it blocks every region,
not one.

### The commands, in order

Substitute `<name>` = `foothills` | `coastal` | `plateau` | `badlands` |
`volcanic`. `<ROOT>` is a per-region directory **outside this repo** that
you create first, e.g. `C:\Dev\LandscapeLab\TerrainData\<Name>_v1`.
Builds land in `001`, `002`, … under it.

```
:: 0. DRY RUN FIRST. Bare invocation completes the whole preflight,
::    prints the exact Gaea command, and writes nothing.
python scripts/rebuild_terrain.py ^
    --project terrain\regions\<name>.terrain ^
    --root <ROOT> ^
    --resolution 8192

:: 1. BUILD. --ignore-cache on the first build of a new graph; the Gaea
::    cache is keyed on node state and a stale hit is silent.
::    ~4 h timeout is a backstop, not a schedule.
python scripts/rebuild_terrain.py ^
    --project terrain\regions\<name>.terrain ^
    --root <ROOT> ^
    --resolution 8192 ^
    --ignore-cache ^
    --go
```

`--go` runs the build, normalizes the height, writes
`height_normalization.json`, and then runs `verify_build.py` itself at
`8192x8192`. **If verify_build refuses, stop.** Do not resize and do not
import — read §3c first, it is the most likely refusal.

```
:: 2. RESIZE 8192 -> 8129, whole package in ONE operation.
python scripts/resize_gaea_build.py ^
    --build <ROOT>\001 ^
    --size 8129 ^
    --archive-excluded

:: 3. RE-GATE at the new size. Same gate, second size, deliberately.
python scripts/verify_build.py ^
    --build <ROOT>\001\UE5_Ready ^
    --expect-size 8129x8129
```

`--archive-excluded` moves `Snow_Out.png` into `_archive/`. **Keep it** —
it is the un-normalized height, and it is the only artefact from which
the Z scale could ever be re-derived if the sidecar is lost.

`resize_gaea_build.py` enforces R1-as-narrowed: the heightmap and all
five masks go through **one** resample at an identical factor, and
`verify_build` exits 4 if more than one distinct size is present in the
package. It also runs `check_registration()` — the brightest 1% of
`Erosion2_Flow` must sit **below** the median terrain rank against a
random control at ~50 (R-GAEA §8). Alpine measured 37.7 vs 50.1,
separation −12.4.

```
:: 4. CREATE THE LANDSCAPE. Bare invocation is a DRY RUN.
::    REQUIRES A FRESHLY LAUNCHED EDITOR (see below).
python scripts/create_landscape_from_build.py ^
    --build <ROOT>\001 ^
    --level /Game/GaeaLab/<Name>_8129 ^
    --actor Landscape_<Name> ^
    --sections 2 --quads 127 --scale-xy-cm 100 --grid-size 2 ^
    --go
```

Four things about step 4, all read from the script:

* **It reads the Z scale from `<ROOT>\001\height_normalization.json`
  (`:275-286`) and refuses if the sidecar is absent.** It then SHA-256
  matches the build-root heightmap against that sidecar (`:321-331`) —
  so `ue_z_scale` provably belongs to *this* terrain. Never type a Z
  scale by hand.
* **The editor's Python namespace must be FRESH.** The script probes it
  and exits **4** if any global roots a `UObject` — a map transition with
  one present is the fatal at `EditorServer.cpp:1951`. Relaunch the
  editor and run this as the first thing you do in it. (The docstring
  calls this `--require-fresh-editor`; it is not a flag, it is
  unconditional.)
* **The landscape is placed at Z = 0** (`:476`), centred, so the terrain
  spans ±span/2. That is deliberate for the Gaea path and it **differs
  from `/Game/Alpine8K`**, which sits at `location_cm` Z 128000 so that
  heightmap value 0 lands at world Z 0. If foliage is ever placed on a
  region landscape, `place_foliage.py:123`'s convention
  (`height_m = (arr / 65535.0) * (z_scale_cm / 100.0)`, which puts
  heightmap value 0 at world Z **zero**) assumes the alpine placement,
  not this one.
* `--material` defaults to empty, i.e. the engine default material. Mask
  import and a layered material are separate work (R-GAEA §5).

### 5a. The Z scale — the derivation, in one place

`rebuild_terrain.derive_z_scale` (`:147-163`) is the single definition:

```
occupancy = (vmax - vmin) / 65535          measured from Gaea's Snow_Out.png
span_m    = Terrain.Height * occupancy     Terrain.Height read from the .terrain
z_scale   = span_m / 512 * 100             512 m is UE's 16-bit span at Z=100
```

Alpine build 006, for calibration:
`occupancy 0.37035 × 2500 m = 925.88 m → Z 180.84`.

**The trap:** typing `Terrain.Height` straight in gives
`2500/512×100 = 488.28` — a landscape **2.7× too tall and entirely
plausible**, which no instrument downstream can catch. The normalization
stretch destroys `occupancy`, so it is recorded *before* the stretch, in
`height_normalization.json`, and read from there by
`create_landscape_from_build.py`.

**A new gate you should apply by hand, because none exists yet:** if a
region build reports **`occupancy` ≥ ~0.95**, the export very likely
CLIPPED rather than genuinely filling the range, and its span is a
saturation artefact. `volcanic` is the file at risk — it raises
`Mountain.Height` to 2.75 (135% of alpine) while cutting
`Erosion2.Duration` to 4.2 (19% of alpine, so far less material is
removed) and raising `Snow.Intensity` to 0.72 (so more is added). At
occupancy 1.0 the derived Z is exactly **488.28** — the trap's own
number, arrived at honestly. Do not accept it; re-check the height
histogram first.

**Every predicted span in every `.md` beside this file is UNVERIFIED.**
The only value of record is `height_normalization.json`, and it does not
exist for any of the five.

### 5b. The import alias, if you ever import by hand

Hand the dialog `UE5_Ready\AlpineLabHeight.png`, never
`..._Height_normalized.png`. The dialog scans the base filename for
`[uvxy]-?[0-9]+` (`LandscapeTiledImage.cpp:14-24`); `v1` matches, it
offers a tiled import, and answering YES creates **no landscape** with no
modal error. Full click-list: `docs/archive/pre8k/IMPORT_CHECKLIST.md`
**(ARCHIVED 2026-08-29 — its opening claim that UE 5.8 Python cannot create a
landscape is FALSE since R-CREATE; use `create_landscape_from_heightmap`.)**
`create_landscape_from_build.py` uses the alias already (`:288`).

---

## 6. UNVERIFIED — stated plainly

* **Nothing has been opened in Gaea. Nothing has been built. No landscape
  exists.** Every landform claim about all five regions is a PREDICTION
  from parameter values.
* **No `--against-build` control has run** on any region graph, because
  there is no build. The export-prediction rule is proven against alpine
  build 006 only.
* **Every Z span and `z_scale_cm` in every region note is a prediction**,
  most of them computed by borrowing alpine's occupancy — which the same
  notes' own `Mountain.Height` edits contradict. Report UNKNOWN until
  `height_normalization.json` exists.
* **The units of `ErosionScale` are inferred, not proven.** §3a's table
  reads it as a fraction of `Terrain.Width`, which is what CLAUDE.md's
  CURRENT STATE 2026-08-12 records (`ErosionScale 1413.25` tuned to
  `Width 5000`). No Gaea documentation was opened to confirm it; the
  ratio reading is consistent across all five lanes and is still a
  reading.
* **Whether `Terrain.Height` 2500 → 1200 changes what Gaea SIMULATES**
  (as opposed to only how the result is interpreted) is unknown. It
  affects `badlands` alone. `Snow.RealScale` is `False` in every file, so
  the Snow node at least is unaffected; `Erosion2` was not checked.
* **`--check-refs` and `--check-spec` are the only gates that ran.** They
  prove reference integrity and export-name agreement. They say nothing
  about whether a parameter value is sane, and by construction cannot.
* **No region has a `recipes/*.json`, an `ASSETS.md` row or a
  `RECIPES.md` entry.** The NEW-ELEMENT RULE is not satisfied for any of
  them.
* **`rebuild_terrain.py`'s `HEIGHT_OUTPUT` filename defect is reported,
  not fixed** — it is outside the validator's write scope.

---

## 7. SUGGESTED ORDER

1. **`foothills`** — 8 leaves, no `ErosionScale` change, no
   `Terrain.Height` change, lowest degeneracy risk, no self-contradiction
   found. It is the cleanest single-variable answer to *"does parameter
   variation change landform class at all?"*, and it produces the first
   non-alpine `occupancy` measurement, which every other region's Z
   prediction currently borrows from alpine.
2. **`coastal`** or **`badlands`** — the fine-`ErosionScale` pair (650 m
   and 553 m features). Between them, `coastal` carries less risk;
   `badlands` is the one that may refuse at `verify_build` on snow.
3. **`plateau`** and **`volcanic`** last — both sit at ~3.7 km erosion
   features across an 8.128 km region (§3a), and `volcanic` carries the
   occupancy-saturation risk (§5a).

Then, and only then, the structural question all five notes converge on:
add the missing node **in the Gaea GUI**, save, and re-run
`--check-refs`.
