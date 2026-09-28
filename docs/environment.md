> # ✅ LIVE DOCTRINE — THIS IS LAW, NOT HISTORY.
>
> Extracted verbatim from `CLAUDE.md` on 2026-08-29 by the doc-consolidation
> unit, purely so `CLAUDE.md` could fit under its size ceiling. **Nothing here
> was weakened, superseded or retired.** It is one index hop away, not
> archived — `docs/archive/` is the archive, and this file is not in it.
>
> **LOAD THIS** before launching the editor, using unreal-mcp, or running anything resource-heavy. Hardware, paths, ports, and the roots quoted in every audit request.

---

# ENVIRONMENT

- Windows 11 Home 10.0.26200, Lenovo Legion Pro 7i — **NVIDIA GeForce
  RTX 5080 Laptop GPU, 16303 MiB VRAM, driver 610.88**; Intel Core
  Ultra 9 275HX, **24 logical cores, 31.4 GB RAM**; display 2560x1600
  (reported 1707x1067 at 150% scaling). Migrated here 2026-08-10.
  **RAM IS 31.4 GB, NOT THE 64 GB THE BACKLOG ANTICIPATED** — measured,
  not assumed, and every RAM-derived budget re-derives from 31.4.
  **With an editor open, ~10.6 GB is free** (measured 2026-09-16 via
  resource_guard.available_gb with the alpine editor resident) — the
  number resource_guard's WARN_FREE_GB=4.0 is calibrated against;
  the retired 16 GB machine's "~1.8 GB free" figure is history.
  *Superseded, and kept because every GPU number on the board is
  calibrated to it:* HP OmniBook, Intel Core Ultra 5 225U integrated
  GPU, 15.4 GB RAM, 14 logical cores. **Every frame-cost figure in
  RECIPES R13 belongs to that machine and is now HISTORICAL, not
  wrong** — R13's CALIBRATION CLASS labelled them correctly.
- **UE 5.8** at `C:\Program Files\Epic Games\UE_5.8`. All API calls
  target 5.8.
- Python Editor Scripting Plugin on; Remote Execution on
  (239.0.0.1:6766). **Use `--timeout 25`** — the 6 s default is
  unreliable on this machine.
- unreal-mcp at **127.0.0.1:8001** (`~~8000~~` — corrected 2026-08-14; the
  engine default 8000 is held by IncrediBuild's `Manager.exe` on this machine
  and UE cannot bind it). 52 toolsets, reached through the three meta-tools
  `list_toolsets` / `describe_toolset` / `call_tool`; read/write/mutate
  cleared. **The server lives INSIDE the editor and does not survive it** —
  start it with `python scripts/start_mcp_server.py --port 8001`, recipe
  **R-MCP**. Read UI state via `SlateInspectorToolset` before driving it.
  MCP-authored scene state does not satisfy pipeline rule 2 — anything that
  should survive a rebuild gets written back into `recipes/`.
  *Struck rather than deleted because the old number never described a
  working connection: a bind failure on 8000 logs "Starting MCP server on
  port 8000" and then "All listeners started" under a different log
  category, so three recorded attempts all read as successes.*

### Roots — quoted verbatim in every audit request
- `REPO_ROOT`: `C:\Users\Admin\UE5LandscapePipeline`
- `UE_PROJECT_ROOT`: `C:\Users\Admin\UE5LandscapePipeline\LandscapeLab`

*Changed 2026-08-10 by the migration; the user account is `Admin`, not
`ryanb`. The old roots were `C:\Users\ryanb\UE5LandscapePipeline[\LandscapeLab]`
and appear in RECIPES.md, LESSONS.md, PROJECT_STATE.json and
`scripts/migrate_to_drive.ps1` — historical there, and NOT swept, because
rewriting a path inside a narrative record would falsify what was true
when it was written.* **The CODE never needed the sweep:**
`bootstrap.py:54-55` derives `REPO_ROOT` from its own file location and
defines `UE_PROJECT_ROOT = REPO_ROOT/"LandscapeLab"`, so the two cannot
drift and no script carries a machine-specific path.
**This also settles which project directory is canonical** — see the
untracked `LandscapeLab 5.8` duplicate flagged in CURRENT STATE.

### Hardware profile
Low-spec config is locked in `RECIPES.md` R7 and lives in
`LandscapeLab/Config/`. Lumen is **off for editing** and goes back on for
final renders. This machine has already lost the GPU to a driver timeout
once; treat frame cost as a correctness concern, not a polish concern.

### Python dependencies — STANDING RULE 5's register

**This section did not exist until 2026-09-11.** Standing rule 5 says
"record any dependency added to the project's Python environment", and
there was nowhere to record one — so the rule had no landing site and the
existing dependencies had never been written down at all. Measured on the
host interpreter, not recalled:

    numpy        2.5.2    everywhere
    Pillow       12.3.0   every PNG read/write
    opencv (cv2) 5.0.0    ⛔ CANNOT read or write EXR in this wheel --
                          imread returns None, imwrite raises "could not
                          find a writer". OpenCV 5's pip build ships
                          without the OpenEXR codec; OPENCV_IO_ENABLE_OPENEXR
                          does not bring it back. Verified 2026-09-11.
    OpenEXR      3.3.2    ADDED 2026-09-11 for scene-linear card
                          measurement (R-GREYCARD). Self-contained
                          (bundles Imath); reads straight to numpy via
                          `OpenEXR.File(p).parts[0].channels[name].pixels`.

    scipy          1.18.0  was ALREADY INSTALLED and had never been
                           recorded -- found 2026-09-13 while checking
                           hydro_derive.py's imports. `ndimage` label /
                           gradient work.
    scikit-image   0.26.0  ADDED 2026-09-13 for the desk's
                           `research/brief4/scripts/hydro_derive.py`,
                           which fills terrain depressions with
                           `skimage.morphology.reconstruction` (grayscale
                           reconstruction by erosion = priority-flood).
                           Pulls in imageio 2.37.4, tifffile 2026.9.9,
                           networkx 3.6.1, lazy-loader 0.5.

    python -m pip install "OpenEXR==3.3.2"
    python -m pip install scikit-image

**Why a dependency at all, given cv2 was already installed:** it was
checked first and cannot do the job — see the ⛔ line above. The cheaper
option was tested and rejected on a measurement, not assumed.

**What the reader must not do is CLAMP.** A scene-linear pass is
unbounded, and a reader that silently clips to [0,1] returns a card
reading that looks plausible and is wrong. The probe that qualified this
one read a live MRQ EXR and reported per-channel min/max.

### External assets
Vendor sources in `Free/`. **~~Gaea is blocked at both ends by
licensing~~ — RESOLVED 2026-08-09, AND THIS LINE WAS STALE FOR TWO
DAYS.** Gaea **2.3.0.1 Indie** is activated: $99 perpetual, 2 machines,
**8K export cap**, with 4096² exports verified against a real build
(`AlpineLab_v1/002`). The Community 1024² cap and the paid-feature
headless CLI are HISTORY — retired in `RECIPES.md` → "Gaea headless
export — RESOLVED 2026-08-09 BY LICENSING". The old diagnosis was right;
the cause is gone.
*Struck rather than deleted because of HOW it was found: it says "do not
re-diagnose it", and a stale line in a do-not-re-derive position is
strictly more dangerous than one anywhere else — the same shape as the
talus-threshold entry struck on 2026-08-08. On 2026-08-11 it was one
sentence from being reported as the blocker on the 1 vertex/metre
re-terrain. It is not: 8129² is inside the 8K cap.*

---

