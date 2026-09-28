# Item 8 — HLOD proxy GPU share: the measurement, at last

**2026-09-21. One write editor pass (build scratch assets) + one read-only
editor pass (cleanup) + six `-game` MRQ renders. Fence held: census CLEAN —
world + every non-scratch asset byte-identical (14,153 files compared, umap
sha256 identical), no `/Game/Scratch/Item8/` remnant. Zero DEVICE_HUNG; VRAM
peaked 8,553 MiB of the 13,312 abort ceiling. NOT PUSHED.**

## The headline

The v3 GPU-share verdict was **INCONCLUSIVE** because no in-fence channel could
toggle `wp.Runtime.HLOD` after the far cells stream — startup `-ExecCmds` fired
once, pre-stream, and left every render counter byte-identical. **The MRQ
`StartConsoleCommands` channel fixes that.** `wp.Runtime.HLOD 0` delivered
through a `MoviePipelineConsoleVariableSetting` on a `-game` command-line render
fires when the shot begins, after the world has streamed, and it demonstrably
applies:

- **Positive control PASSED.** `GPUSceneInstanceCount` drops **1,406,348 →
  1,344,921 = −61,427 instances (4.37%)** in the HLOD-off arm, identical at both
  stations; `SceneCulling/NumStaticInstances` drops the same 61,427.
  `ActorCount/WorldPartitionHLOD` stays 422 (the HLOD actors remain resident —
  the command sets visibility, it does not unload — exactly as
  `HLODRuntimeSubsystem.cpp:149-187` says).

- **The number (I3).** GPU cost of the MRQ render frames, arm A (HLOD on) vs
  arm B (HLOD off), p90 over the steady render window, quoted × the A/A noise
  floor:

  | station | A p90 | B p90 | HLOD share | × A/A floor | verdict |
  |---|---|---|---|---|---|
  | treeline | 49.46 ms | 48.88 ms | **0.576 ms (1.2%)** | ×2.9 | **MEASURED** |
  | vista | 49.28 ms | 48.82 ms | 0.457 ms (0.9%) | ×0.7 | MEASURED-NEGLIGIBLE |

  The per-pass drop (treeline) is **NaniteVisBuffer +0.225, ShadowDepths +0.164,
  Basepass +0.080 ms** — the far-forest proxies' rasterization + shadow cost,
  exactly where an instanced-HLOD proxy band should show. vista's A/A floor is
  0.67 ms (a noisier station), so its 0.46 ms share sits under its own noise;
  treeline's floor is 0.20 ms, so its 0.58 ms share is a clean ×2.9 signal.

- **Pixel fraction (I3).** Hiding the proxies changes **0.20% of non-sky pixels**
  (vista 0.00203, treeline 0.00195), ~3× the A/A pixel noise floor — small, and
  far below the derived beyond-512 m ground fraction **0.05727**. That gap is the
  answer to "what is the far forest": most beyond-512 m ground is the
  MESH_APPROXIMATE merged landscape proxy + haze, NOT toggleable instanced tree
  proxies; the instanced proxies are a thin 0.2% of the frame. Cheap by
  construction — consistent with the v3 composition read.

**So: the HLOD proxy far-forest costs ≈0.5 ms (≈1% of frame) at the MRQ 4K
render, measured cleanly at treeline (×2.9 floor), and is a ~0.2% pixel / 4.37%
GPUScene-instance footprint. It is small.**

## The instrument trap, stated plainly (rule 10)

Two caveats bound the number:

1. **The ~49 ms/frame is MRQ's full-quality 4K render, heavier than the game
   runtime (~7-12 ms in the standalone perf runs).** The transferable figure is
   the SHARE FRACTION (~1%), not the absolute ms; at the 12.5 ms game budget ~1%
   is ~0.13 ms.
2. **A `-game` MRQ render renders OFF the main game-loop frame.** The
   CsvProfiler's per-row `GPUTime` is the near-idle offscreen pump (~0.07 ms);
   the real render appears only on the rows where `GPU/Basepass>0`. The first
   version of the analyser windowed on `GPUTime` and reported a nonsensical
   0.08 ms share — corrected to window on render rows (sum of `GPU/*` passes,
   last 30 render rows after the shader/Nanite/TSR warm-up spike). Logged in
   LESSONS 2026-09-21.

## Files

| file | what |
|---|---|
| `input/item8_share.json` | I5 synthesis: per-station verdict, share × floor, per-pass, pixel fraction, crops, combined positive control |
| `input/item8_perf.json` | I2 counter control + I3 number, per arm, per pass |
| `input/item8_pixels.json` | I3 pixel fraction + I4 crop manifest |
| `input/item8_build.json` | scratch-asset build read-backs (camera_ok, HLOD-command-on-B-only, no GameOverride) |
| `input/item8_capture_manifest.json` | driver manifest: 6 renders (VRAM, frames, ok), census verdict, device_hung_count 0 |
| `input/item8_cleanup.json` | scratch deletion (6 assets, C0House untouched) |
| `input/item8_levers.md` | every lever FILLed at header:line + runtime result |
| `derived/item8/frame_<station>_<arm>.png` | the six final 4K render frames (A1/A2/B × vista/treeline) |
| `derived/item8/crop_<station>_<label>.png` | 12 far-forest 512 px crops (5 distances + 1 boundary × 2 stations) — **for Ryan's visual tiling call** |
| `_verify/perf/item8/census_{before,after}.json` | the byte-identical fence brackets |

## For Ryan — the far-forest tiling verdict (I4): NO TILING

**The 12 distance-placed crops (`crop_<station>_<dist>.png`) FAILED to isolate
the forest** — the flat-ground distance placement saturates at each station's
horizon without a depth pass and landed on mid-field snow/road, and the auto
repetition-score is non-discriminating on self-similar canopy. So they do not
answer the question.

**The answer comes from the A-vs-B diff instead** (`diffcrop_<station>_A-B-diff
.png`, built by `item8_diffcrop.py`): the differing pixels ARE the toggled HLOD
proxies by construction, so the densest diff cluster is exactly the far proxy
band. At both stations that band sits at the upper-right ridge (~beyond 512 m),
and the diff panel shows it is a **natural, irregular conifer tree-line
silhouette — pointed crowns of varying height, NOT a grid of repeated square
billboard cards.** Arm A renders a coherent hazy distant forest; arm B drops it
entirely; the transition to the near real trees shows no hard pop line.

**So the SpruceSub / instanced-HLOD imposters do NOT tile at the rendered proxy
distances.** This is distinct from the 128-512 m near-band card-tiling that was
the Brief-5 REPAIR subject (the card drawn large/close, fixed by the LOD hold) —
beyond 512 m the octahedral imposters blend cleanly. The A|B|diff strips are the
load-bearing I4 evidence; the distance crops are kept but superseded.
