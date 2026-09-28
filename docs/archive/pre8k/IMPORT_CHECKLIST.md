> # ⛔ SUPERSEDED — describes the pre-8K / pre-kit design. Do not apply.
>
> Quarantined 2026-08-29 by the doc-consolidation unit. **Nothing in this
> file may drive a decision.** It is kept verbatim because this project
> never deletes a record; the content below the banner is byte-identical to
> what it was before the move.
>
> **Why it is dead, and this is the dangerous one.** Its **opening claim is
> now false**: *"UE 5.8 Python cannot create a landscape."*
>
> **Superseded by R-CREATE, 2026-08-12.** The `LandscapeLabEditor` plugin
> exposes `create_landscape_from_heightmap`, and CLAUDE.md records the
> retraction verbatim: *"R-GAEA's 'UE 5.8 Python cannot create a landscape'
> is now FALSE."* A session following the click-list below would perform a
> manual dialog walk-through for something that is now one scripted call.
>
> It is also scoped to `AlpineLab_v1`, the Gaea **evaluation** terrain, not
> the shipped world.
>
> *Moved from its original path by `git mv`, so `git log --follow` still
> reaches its whole history.*

---

# IMPORT_CHECKLIST.md — creating the AlpineLab_v1 landscape by hand

**UE 5.8 Python cannot create a landscape.** The reflected surface has
no create/import-landscape function; the only two import entry points
are methods on an *existing* `LandscapeProxy` taking a
`TextureRenderTarget2D`, not a file
(`LandscapeLab/Intermediate/PythonStub/unreal.py:531939` and `:531954`).
So this dialog is a manual step, once, and everything either side of it
is scripted.

**This is the evaluation terrain.** It does not go in `/Game/Alpine` —
that world has 171,069 placed instances and a verified heightmap push
that a second landscape would sit on top of.

---

## THE FILE TO IMPORT

```
C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\002\UE5_Ready\AlpineLabHeight.png
```

**Not** `AlpineLab_v1_Height_normalized.png`, even though it is the same
bytes (sha256 `6e1f93bf…`, verified byte-identical). See FAILURE MODE 1.

---

## THE STEPS

1. **Open the project.**
   `C:\Users\ryanb\UE5LandscapePipeline\LandscapeLab\LandscapeLab.uproject`

2. **The level.** One already exists from the first attempt —
   `/Game/Game/GaeaLab/AlpineLab_v1`, on disk at
   `LandscapeLab/Content/Game/GaeaLab/AlpineLab_v1.umap` (45 KB, no
   landscape in it). Open that one; there is no reason to make another.

   *(The doubled `Game` in that path is a content-browser folder
   literally named `Game`, so the asset path is `/Game/Game/...`. Odd
   but harmless. Renaming it is a fixup for later, not now.)*

   If you would rather start clean: `File > New Level > Basic`, delete
   the `Floor` actor, save under `/Game/Maps/`.

3. **Landscape Mode.** `Ctrl+Shift+2`, or the mode dropdown in the
   top-left toolbar.

4. **Manage tab > New** (this is the default sub-mode) **> Import from
   File.**

5. **Heightmap File:** browse to `AlpineLabHeight.png` above.

   **If a dialog asks *"Use '…' Tiled Image?" — answer NO.** With the
   correct filename it should not appear at all; if it does, you have
   the wrong file selected.

6. **Set these, in this order** — the resolution readout is derived
   from the three above it, so it is the check, not an input:

   | Field | Value |
   |---|---|
   | Section Size | **63 × 63 Quads** |
   | Sections Per Component | **1 × 1 Section** |
   | Number of Components | **64 × 64** |
   | **Overall Resolution** | must read **4033 × 4033** — if it does not, STOP |
   | Location | 0, 0, 0 |
   | Rotation | 0, 0, 0 |
   | Scale X | **100** |
   | Scale Y | **100** |
   | **Scale Z** | **180.81** |

   Z 180.81 is measured, not chosen: Gaea declares a 2500 m project
   range, this build occupied 496–24763 of 65535 before the export was
   normalized, so the real span is 925.73 m and
   `925.73 / 512 × 100 = 180.81`. The obvious answer, 488.3, gives a
   landscape 2.7× too tall that looks entirely plausible. Full
   derivation: `RECIPES.md` → R-GAEA §6.

7. **Import.**

### SUCCESS CRITERION

**A `Landscape` actor appears in the World Outliner.** Nothing else
counts — not the dialog closing, not the absence of an error. If the
Outliner has no Landscape, the import failed, however quietly.

---

## THEN RUN THIS — the one post-import command

In the editor: **`Tools > Execute Python Script…`** and pick

```
C:\Users\ryanb\UE5LandscapePipeline\scripts\ue5_import_alpinelab.py
```

(or paste its contents into the Output Log's `Cmd:` box with the mode
set to **Python**).

It reads the ACTOR, not the dialog you typed into, and reports:

- landscape present, and exactly one — **it refuses and imports nothing
  if there is no landscape**, rather than half-succeeding
- component count vs the expected **4096** (64 × 64)
- world span vs the expected **403,200 UU** (4032 quads × 100) on both
  axes
- height span vs the **925.7 m** that Z 180.81 predicts for a
  full-range heightmap — a different representation of the Z scale than
  reading `scale.z` back, so it catches a value that landed without
  taking effect
- the five `T_AlpineLab_*` masks: **already imported, so it skips them**
  and reports what is there rather than re-importing over live assets

Expected verdict line: `VERDICT: PASS`.

### THEN SAVE — the masks are currently only in memory

The five `T_AlpineLab_*` textures from the first run are **not on disk**.
Nothing named `AlpineLab` exists under `LandscapeLab/Content/` except the
level itself, which means they live only in this editor session and die
with it. The import script sets `save=False` on purpose — it does not
write to your project without you asking.

After the verify script prints PASS: **`File > Save All`.**

---

## FAILURE MODES WE HAVE ACTUALLY HIT

### 1. The tiled-image prompt — this is what killed the first attempt

Selecting `AlpineLab_v1_Height_normalized.png` pops

> **Use 'AlpineLab_v<v>_Height_normalized.png' Tiled Image?**

**Answering YES creates no landscape.** Root cause, at source:

- `LandscapeTiledImage.cpp:14-19` — the tile tokens are `u`, `v`, `x`,
  `y`
- `:22-24` — each is matched as `<token>(-?[0-9]+)`, **anywhere in the
  base filename**. There is no underscore in the pattern; `v1` is
  enough.
- `LandscapeEditorUtils.cpp:80` — YES replaces the filename with the
  glob pattern
- `LandscapeTiledImage.cpp:86-104` — only a `u`/`x` token sets the tile
  **X** coordinate; a `v`-only name leaves `X = -1`
- `:105` — `if (X >= 0 && Y >= 0)` — so **no tile is added**
- `:149-155` — zero tiles → `"No files found"`, and the dialog gives you
  nothing useful

Answering **NO** is safe (`Filename = Filenames[0]`, same file). The
alias exists so the question is never asked.

### 2. Silent cancel — the dialog closes and nothing exists

The failure above presents as "I clicked Import and nothing happened".
There is no modal error. **This is why the success criterion is the
Outliner and not the dialog**, and why the verify script's first act is
to refuse when no Landscape actor exists.

### 3. Wrong Overall Resolution

If Section Size or component count is off, the dialog will happily
import a *valid* landscape at the wrong resolution — 1024 components at
127 quads is a perfectly good landscape of the wrong terrain. The
verify script catches it two ways (component count, and world span), but
the resolution readout in step 6 catches it before you spend the import.

### 4. Memory

A 4033² landscape at 4,096 components is not cheap to create. If free
RAM is tight, run `python scripts/resource_guard.py` first. This machine
has lost the GPU to a driver timeout once.
