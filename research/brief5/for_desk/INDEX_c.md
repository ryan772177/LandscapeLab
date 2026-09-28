# Brief 5 — close-out session (C) send-back

**2026-09-21.** Read-only editor work (two passes, R-EDITOR-CLOSE after each, world
byte-identical to HEAD). Both requested checks ran to a measured verdict. The
headline result overturns a prior "shipped" claim, so it is stated plainly first.

## Six-line summary
1. **C1 — the hold is a NO-OP at runtime, MEASURED.** The direct render-data
   readback (the desk's own tiebreaker) shows the live tree meshes still carry the
   PRE-HOLD card ScreenSize: ConiferPine LOD3 = 0.16821, SpruceSub LOD4 = 0.17
   (t3_hold targets 0.03818 / 0.02642); `matches_t3_hold = false` for both.
2. **Root cause: the T3 save never hit disk (false-success `saved:true`).** The
   live `.uasset` mtimes predate the T3 run — `ScotsPineTall_01.uasset`
   2026-08-02, `spruce_half_01.uasset` 2026-08-14 — while only the `_SRC` backups
   carry the T3 mtime (2026-09-21 06:29). Both meshes are gitignored, so git is
   not involved. The T3 in-memory readback (0.038 / 0.026) was lost on editor
   close; `tree_lod_probe_t3.json` and `alpine_8k.json`'s "recipe == asset" note
   inherited that lost value and are stale.
3. **Colour readback corroborates.** Mesh LOD Coloration (legend read from the
   on-screen bar, validated vs `BaseEngine.ini`): the 128–512 m band is ~80 %
   card / ~19 % geometric for both species — a hold that took would render ~0 %
   card here (card pushed past the 512 m cull).
4. **This coheres with V1 and V2.** SSIM tie (0.917 vs 0.918) and hold cost
   ~0 ms were both correct *because the hold was never applied* — nothing changed,
   so nothing measured.
5. **C2 — the imposter does NOT tile in the vendor Showroom.** Forced to the card
   (r.ForceLOD 8) and auto at 150 m, `spruce_half_01` renders clean tree
   billboards, no square tiles. The demo places it exactly as we do (HISM
   `FoliageInstancedStaticMeshComponent` + the same `half_01_imposter`).
   **H1 (octahedral frame-blend fails under HISM) is DISCONFIRMED.**
6. **Favoured hypothesis now H4: the Alpine8K tiling is scene-specific** — most
   likely the card drawn LARGE and CLOSE in the 128–300 m band (because the hold
   never persisted), magnifying the low-frame octahedral atlas; secondary is
   Lumen HWRT + heavy exposure vs the Showroom's flat lighting.

## Consequence for Brief 5
The T3 "hold shipped" claim is **false** — the fix must be re-applied and verified
to PERSIST across an editor restart (a write, out of this read-only session's
scope). Until then the imposter tiling the desk flagged (T1 CONFIRMED) is still
live in the 128–512 m band. The likely mechanism the persist step must defeat:
`bAutoComputeLODScreenSize` had no Python setter in T3 (recorded in t3_hold.json),
so a mesh rebuild can recompute the LOD ScreenSizes back to the auto values — but
the primary evidence here is simpler (the package was never written at all).

## Files
| item | file |
|---|---|
| C1 counts + legend + verdict | `input/c1_lod_readback.json` |
| C1 render-data readback | `input/c1_renderdata.json` |
| C1 stills (5 forced refs + auto ring + auto deep) | `derived/c1_lodcolor/` |
| C1 per-shot camera/FOV | `input/c1_shot_*.json` |
| C2 placement | `input/c2_showroom.json` |
| C2 stills (150 lit, 300 lit, 150 card) | `derived/c2_showroom/` |
| C2 hypothesis update | `input/imposter_defect.json` |

## Acceptance
c1_lod_readback.json with per-species counts and a plain verdict (NO-OP AT
RUNTIME, render-data decisive; colour ~80 % card) ✓; legend read from the viewmode
and validated ✓; Showroom yes/no with crop (NO tiles, crops in derived/c2_showroom)
✓; tree clean, no push ✓; editor closed clean both passes (0 procs,
PackageRestoreData absent) ✓.
