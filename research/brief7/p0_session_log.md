# Brief 7 — Phase 0b–0e session log

## State as I understand it (orient, 2026-09-23, fresh session)

1. Brief 7 = THE LOOK: Electric Dreams-grade alpine. Spec `BRIEF7_THE_LOOK.md`; rulings R-LOOK-1 (game gets its own `PPV_Look` + Look profile; bench PPV/profile/`benchmark.json` never touched), R-ROCKS-BACK (Aug rock species return), R-AESTHETIC-1 (ms budgets suspended, perf recorded not gated, visual gate = Ryan on stills).
2. Phase 1 material AUTHORED + REVIEWED + MERGED to main (schema v1.27 per-layer displacement, v1.28 height-weighted blend, GroundClutter restored). Offline-verified only; NOT run against the editor — the material rebuild is the gated world run, owed after Ryan's L0 grade.
3. F2 RESOLVED (Ryan MEASURE→MODEL): raw surface-lookup argmax flips 3.12% of walkable texels under the height reweight (>2% bar); `bake_surface_lookup.py` now models the reweight. OWED at Phase 1 world run: re-bake `textures/alpine_8k_surface.png` with `--write`.
4. Phase 0a DONE offline: D3 evidence tracked; D3 editor-peak VRAM 5,211 MiB recorded; min_detectable per-build in REGISTER.
5. World still m=1 (185,385 trees), pre-density-daylight. T4 found no cheap forest_floor lever (structural cost); density blocked pending Ryan on forest_floor path.
6. NEXT (this session) = Phase 0b–0e, a LIVE-EDITOR pass: read-backs → pre-exposure ini → PPV_Look + fog/cloud/sun → three still pairs → STOP at ASK L0.
7. Hard stops: rule 11 (zero editors — verified NONE now; verify LEVEL after launch), rule 7 (verify project = LandscapeLab), rule 12 (read-back every PPV param), VRAM 13,312 MiB, R-EDITOR-CLOSE, tag `pre-look` before first write, unreal-mcp 127.0.0.1:8001 (R-MCP).
8. Branch rule: Phase 0 runs on main. Phase 1 script changes already merged. Environment: UE 5.8, project LandscapeLab, RTX 5080 16303 MiB VRAM, ~10.6 GB free with editor open.

No contradiction between the files and the runbook. Proceeding: tag `pre-look`, then 0b read-backs.

---

## 0b read-backs — DONE

See `p0_readback.md` (tables) + `input/p0b_inventory.json`, `input/p0b_material.json`.
Headlines: bench PPV = `Lighting_alpine_8k_PostProcess` (manual, bias −14.2571, only PPV);
4 DirectionalLights (1 atmosphere sun 130000 lux/5200K + 3 HeroStage rig lights still
affecting the world — L0 flag); fog scattering 0.4 (ruled 0.2); cloud coverage 0.30
(ruled 0.1); material is the pre-Phase-1 build (no LandscapeLayerCoords/LayerBlend,
displacement magnitude 0.16, grass = Meadow+Blueberry only).

## 0c pre-exposure — DONE (applied + read-back; −game visual owed to L0)

- Confirmed the cvar in 5.8 source: `r.EyeAdaptation.CachedLightingPreExposure`
  (PostProcessEyeAdaptation.cpp:201). Warning fires when scene ExposureEV ∉
  [value−12, value+8] under Lumen (lines 250-268). Default 4 → [−8,12]; the sunlit 8K
  scene exposes ~14.3 EV → clips.
- Wrote `r.EyeAdaptation.CachedLightingPreExposure=8` to `LandscapeLab/Config/
  DefaultEngine.ini` [SystemSettings] → safe range [−4,16], covers 14–15.
- Runtime read-back in the live editor (`set_preexposure`, WANT=8): before **4.0**
  (the live defect the desk named), after **8.0**, landed True. Cvar valid, value applied
  to this editor session (so 0e stills render with the fix).
- **Warning-gone:** analytically cleared (14.3 ∈ [−4,16]); the −game on-screen debug
  message cannot be captured reliably from a headless -RenderOffScreen run, so the
  visual confirmation is deferred to Ryan at L0 (rule 10, stated not faked). The ini
  line applies at every future startup — PROVEN: the cold relaunch (below) read the
  cvar back at **8.0** in a fresh process (the defect 4.0 is gone).

## 0d PPV_Look + fog/cloud/sun — DONE (applied + saved + cold-verified)

Auditor gate on `brief7_p0d_write_payload.txt`: CLEAR-TO-EXECUTE after finding 1
(post-save dirty-package census) + 4 minor fixes, all applied. `input/p0d_write.json`.

- **PPV_Look** NEW actor (`A/YU/TFX5OZE9RR4THA2TVWQ9UZ` OFPA): unbound, priority 1.0
  (above bench PPV's 0.0), **enabled=False persisted** (the Look profile enables it, so
  no bench measurement is affected by default — R-LOOK-1). Grade: manual + bias
  −14.2571 (A-6 sun solve); local exposure 0.8/0.8; WB 6200 (sun 5200 K + 1000) tint 0;
  color_contrast w=0.90; FFT bloom 0.4 + dirt 0.1; grain 0.3; vignette 0.3.
- **Sun** shaft bloom + occlusion ON (occlusion was False). **Fog** volumetric ON,
  scattering 0.4→0.2. **Cloud** coverage 0.30→0.10 (`Cloud_GlobalCoverage`; global
  material param, so both profiles see it — noted; reversible, before=0.30 recorded).
- Persist: `save_current_level()` + `save_asset(MI)`; post-save dirty census **map 0 /
  content 0** (finding-1 verification). Bench PPV/profile/benchmark.json untouched.
- Fence-clean world diff: sun OFPA + fog OFPA modified, new PPV_Look OFPA, umap + cloud
  MI modified. Nothing else.

## 0d/0c COLD READ-BACK — persist proven cross-process (`input/p0_coldread.json`)

Closed the editor (R-EDITOR-CLOSE: census 0, quiet >120s, kill, 0 procs), relaunched
offscreen (fresh process reads the ini + cold-loads the saved OFPA/MI). All persisted:
pre-exposure **8.0**; PPV_Look found, enabled=False, manual/−14.2571, WB 6200/0,
contrast w=0.90, local 0.8, bloom 0.4, grain 0.3, vignette 0.3; sun occlusion True;
fog scatter 0.2; cloud coverage 0.1.

## 0e stills — DONE (`stills/p0/`, 6 × 4K)

Camera stations from `benchmark.json` (read-only): near_ground [-210800,278800] rot
(0,−2,−12.8); mid_slope [-190000,100000] rot (0,−2,105); vista [-216400,63600] rot
(0,−4,60); +175 cm eye, FOV 90, 3840×2160. Each shot bench-profile (PPV_Look off, sg
bench) vs Look-profile (PPV_Look on, sg Epic 3, TSR) via `brief7_p0e_setprofile_payload`
+ `shoot.py`. Camera read-backs exact (0 cm / 0°); no underground refusal; frames landed
offscreen in ~4 s each. The Look profile discards its runtime PPV_Look-enable toggle on
editor kill, so the persisted enabled=False is preserved.

**What the pair shows (CC's read; the visual gate is Ryan's):**
- near_ground: Look removes the tree-card LOD popping the bench shows (Epic sg → full
  geometry), warms to golden hour (WB 6200), sun rim-lights the grass/trunks, local
  exposure lifts shadow detail. Town = engine cube primitives in both (the known gap).
- vista: Look reads as a warm hazy alpine panorama — volumetric fog aerial perspective
  on the receding ridges, thin high cloud, snow terrain as mass. Possibly too warm.
- mid_slope: slope + treeline; Look warmer + cardless.

STOP → ASK L0.

## L0 (Ryan re-grade) — DONE, re-shot (`stills/p0_L0/`)

Ryan ruled (inline, not via the option tool): **rig-off**, **WB change**, **fix clouds**
(scattered cumulus ≥60% clear at vista, else disable+BACKLOG in 30 min); re-shoot 3 pairs.

- **Clouds** (`input/` cloud tries in `stills/p0_cloud/`): inspected — MI_AlpineClouds is a
  child of the engine `m_SimpleVolumetricCloud_Inst`; coverage IS bound (`Cloud_GlobalCoverage`).
  The lid was the values (`Layout_CloudGlobalScale` 256, low density). Swept coverage
  0.20→0.08→0.03 (+ density/scale): never opened past ~35–40% clear — the simple material
  renders a broken deck, not cumulus. **Ruled fallback taken: DISABLED the cloud actor for
  P1–P3** (`hidden_in_game` + component `visible=False`); open SkyAtmosphere. BACKLOG a
  WeatherMap cloud material. The vista now reads as clean open sky with a natural sunset horizon.
- **Rig-off:** the 3 HeroStage lights set `hidden_in_game=True` (persisted). **First attempt did
  NOT persist** — `set_actor_hidden_in_game` without `modify(True)` never dirtied the OFPA
  packages, so save skipped them and the cold read-back caught all three back at False. Fixed
  with `modify(True)` first (the 3 rig OFPA then appeared in the dirty set before save). LESSONS.
- **WB** 6200 → **5800** on PPV_Look (cooler; rig-off + open sky already cool the scene).
- **Cold read-back after the fix:** pre-exposure 8.0, WB 5800, rig all hidden_in_game True, cloud
  actor hidden + component invisible. Persist proven cross-process (`input/L0_write.json`).
- **Re-shoot** (`stills/p0_L0/`, 6×4K): vista Look = clean open sky, cooler, natural single-sun
  shadows. near_ground shows tree-card LODs (fresh-editor foliage-LOD settle gap — BACKLOG; the
  tonal grade is still judgeable). Contrast (0.90) + shafts (ON) unchanged (unruled → kept).

STOP → ASK L0-final: sign off the grade (WB 5800 / contrast 0.90 / shafts ON, rig-off, clouds-off)
or adjust, and green-light Phase 1 (material rebuild — the next gated world run on branch
`look-p1-material`, already merged; runs against the editor only on "merged, go").
