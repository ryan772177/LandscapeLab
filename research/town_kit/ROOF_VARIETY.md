# ROOF VARIETY — design (2026-10-11)

Ryan: "go ahead with the roof variety next". STATE 2026-10-11 evening named the whole roofs as the town's
dominant sameness after arm C + soffit.

## What was measured before designing

- **Mesh mix was already at random.** Shipped manifest: 4 usable whole roofs (House02 76, House03C 82,
  House07_02 92, House08 99). Neighbour sameness, i.e. the share of each house's nearest 4 neighbours that use
  the same roof mesh, is 0.24. A random draw over 4 roofs gives 0.25. Swapping meshes alone therefore buys
  little.
- **Alternatives exist but stretch more.** 242 of 349 houses have 2–3 roofs within `roof_tol` 0.2 on their
  (jetty) footprint. Shipped best fits: stretch p50 0.067, max 0.153. Alternatives: p50 0.13–0.17, up to 0.199.
- **All 7 roof meshes have ONE material slot, all Nanite.** Their MIs are siblings under
  `/Game/Materials/Masters/M_RoofMaster`, and every MI carries the same albedo controls:
  - `ALBEDO_Intensity` 1.2;
  - `ALBEDO_Desaturation` -0.3;
  - `ALBEDO_Contrast` 1.0;
  - `ALBEDO_Overlay_Strength` 0.0;
  - vector `ALBEDO_Color_Overlay` (1,1,1,1).

  Source: probe `scripts/payloads/roof_material_probe.py`, artefact `_verify/roof_variety/material_probe.json`.

  So every thatch in town has the same grade. That is the sameness a still shows.

## Two levers, one placement

**A. Mesh + ridge direction (pure Python, done offline).**
- `town_kit_plan.roof_candidates` returns every (roof, yaw 0/90) with stretch <= `max_stretch`, plus the best fit.
- `pick_roof` scores each candidate as: neighbours with the same mesh + neighbours whose WORLD ridge lies within
  `ridge_tol_deg`. The neighbours are the 6 nearest already-planned houses within 40 m. The lowest score wins;
  ties go to a per-house RNG that is separate from the walls' RNG.
- Measured (dry run):
  - mesh sameness 0.24 → 0.19;
  - ridge sameness 0.58 → 0.46;
  - 171 houses change roof;
  - walls, foundations and soffits are byte-identical (0 houses differ outside roof/gable pieces).
- Cost: stretch p90 0.189; 96 roofs exceed the 0.153 seen so far. The 0.153–0.2 band is judged by still. If it
  reads badly, lower `max_stretch` (0.15 still gives 148 houses 2 options).

**B. Weathering grades (new assets + one payload addition).**
- New assets: for each USED roof MI × each non-base grade in recipe `style.roof_variety.grades`, one
  MaterialInstanceConstant `/Game/Materials/TownKit/RoofGrades/<roof MI asset name>_<grade>` (e.g. `MI_Roof_aged`; `town_kit_plan.grade_mic_path`, the one naming rule).
  - Parent = the roof's own MI, so textures, switches and normals are inherited untouched.
  - Overrides only the grade's `ALBEDO_*` keys.
  - Idempotent: find-or-create, set, save, reload, READ BACK every set value (rule 12).
  - Refuses if a recipe key is not a parameter of the parent (`get_scalar/vector_parameter_names`).
  - Vendor bytes are never written: the new assets sit outside `/Game/Meshes` and `/Game/Megascans`.
- Grade per house: uniform over the grades, with neighbour balancing (same-grade count among the same 6
  neighbours), its own RNG.
  - Grade "base" = no override; the piece carries no `material`.
- Manifest: the roof piece gets `"material": <MIC path>` when the grade is not base.
- Payload `town_kit_build_house.py`: after `set_kit_instances`, for each group:
  - if its pieces carry a `material`, all pieces in the group must agree, or the house is refused;
  - set `override_materials` on that ISM to `[mic]` when a material is given, else to `[]`. Explicit both ways,
    because `SetKitInstances` REUSES a same-named ISM (`LandscapeLabTools.cpp:2069-2082`), so a stale override
    would survive an update-in-place;
  - READ BACK `get_material(0)` path == the wanted MIC, or == the mesh's slot-0 material when none is given;
  - the per-house `ok` includes it.
- Registry: `/Game/Materials/TownKit/RoofGrades` is ADDED to `quixel_medieval_village_sample.packages` (derived
  from kit textures).
- Initial grades are starting values, not tuned. Tuning is a re-run of the MI builder with no re-placement: the
  houses reference the MIC by path.

  | grade | changes |
  |---|---|
  | `base` | — |
  | `aged` | Intensity 0.85, Desaturation 0.15 |
  | `grey` | Overlay (0.60, 0.62, 0.64), Overlay_Strength 0.35, Desaturation 0.25, Intensity 1.0 |
  | `fresh` | Overlay (1.0, 0.86, 0.58), Overlay_Strength 0.25, Intensity 1.3 |

## Application

- Roof MESHES change on 171 houses.
- `--update-in-place` is add-only for dropped meshes: a house whose roof changes keeps the old roof ISM with its
  instances (R-TOWNKIT AMENDED 10-11), and its gable ISMs may go to zero.
- Therefore: tagged restore point, then a full clear + place of 349, as arm C did. Verify EXACT instance counts.
  Then save, navmesh (the boxes are unchanged, so nav should be identical; rebuild is the check), the
  streets/doors/lattice/encounters gates, the street mask re-stamp check, then the HLOD rebuild DETACHED with the
  RAM sampler, then stills.

## Not done / out of scope

- The 3 awning roofs (House05/06/07_Roof01) stay unusable; a per-roof body box needs mesh-body measurement.
- Shingles: the Megascans Shingles surface is tileable. The roof meshes are UV'd to their own atlases, so a
  surface swap is not a parameter change. Deferred.
- Per-instance custom data (continuous tint): needs a master edit of a vendor material. Rejected: grades are
  discrete MICs, which leave every vendor byte untouched.
