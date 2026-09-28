# Mannequin to Groom

**UE 5.8 · MetaHuman · Blender 5.2**

The full chain as this project actually built it — skeleton, DNA, face, textures,
assemble, groom authoring, Alembic, binding, colour, gates. Every value here was
measured on this machine. Written to give a research effort the exact ground
truth around one open defect: a groom that imports, binds, sits in the right
place, and renders zero pixels.

> Read stages 8–11 and 14 if you only care about the open defect. Stages 1–7 are
> the ground it stands on, and several of the traps in them recur later in
> different clothes.

**Status vocabulary.** **PROVEN** means it was executed and verified by a render
or a second instrument. **REFUTED** means it was tried and measured not to work —
those rows are the expensive ones and are recorded so nobody re-derives them.

---

## 01 · Skeleton, and which mannequin

Two 161-bone UE5 mannequin skeletons can coexist in one project and animations
bound to one play as a *silent T-pose* on the other. Equal bone counts are not
identity — compare the resolved skeleton *path*.

| Skeleton | Bones | UE5 markers | Verdict |
|---|---|---|---|
| `UE4_Mannequin_Skeleton` | 68 | 0 of 4 | UE4 — wrong |
| in-project GV pack `SK_Mannequin` | 161 | 4 of 4 | UE5, but no physics asset; LOD0 and LOD1 both 48,779 verts |
| engine template `SKM_Manny` | 161 | 4 of 4 | **CHOSEN** — carries `PA_Mannequin`, 3 control rigs, 102 anims |

Recipe `R-SKEL` is the identification procedure; `R-CHARACTER` declares movement.
The mannequin matters for the *body* and animation; the MetaHuman face rides a
separate `Face_Archetype_Skeleton` (875 bones).

---

## 02 · The MetaHuman character asset

Everything about the hero's identity lives in one asset:
`/Game/Hero/MHC_AlpineHero`. A duplicate, `MHC_AlpineHero_Master`, is never
imported into and never written — it is the restore point of last resort.

### Enabling the plugin — the trap that cost four attempts

> **A plugin descriptor is a derived record.**
> `MetaHumanCharacter.uplugin` declares **20** plugin dependencies and
> `MetaHumanCoreTech` is *not one of them* — and it does not start without it.
> Every scripted route faithfully reproduced an incomplete declaration. Enable a
> plugin the way the editor enables it, at least once, before encoding it
> anywhere.

Also: enabling a Beta plugin raises a confirmation modal. Through the UI a human
answers it; raised at startup from a descriptor it blocks the game thread — the
same thread that services Python remote execution, so the editor cannot report
why it is stuck.

---

## 03 · DNA and the face

The face is driven by a MetaHuman DNA file. Canonical copy:
`hero/dna/MHC_AlpineHero_Head.dna`, never edited in place.

### The DNA's own coordinate system

```
format 2.5;  axes X=Left  Y=Up  Z=Front;  cm

head_lod0_mesh   X ±19.034   Y 140.878..178.439   Z −11.616..14.988
teeth_lod0_mesh              Y 156.5..162.1
eyes_lod0_mesh               Y 165.6..168.5
```

**The DNA is Y-up and UE is Z-up.** Nothing converts. The jaw is *low Y*. Work in
the declared space, and use `--flag=value` so argparse does not eat a negative
coordinate.

### The round trip that works

1. `edit_dna_geometry.py` — feathered region edit in the DNA's own space,
   self-verifying selected and untouched vertices (`R-HEROGEOM`).
2. `sanctioned_import.py` — `import_from_face_dna`, with an `--identity` arm and
   a `--restore` path (`R-HEROIMPORT`).
3. `use_preview_mesh.py` — re-point the transient preview face mesh after every
   assemble.
4. `capture_shot.py` against the locked camera from `build_capture_stage.py`
   (`R-HEROCAP`).

> **An Epic docstring is wrong, and believing it costs a permanent decision.**
> `ImportFromDNAParams.import_whole_rig` documents that when unchecked "the head
> DNA file will only be used for neck alignment". False.
> `MetaHumanCharacterEditorSubsystem.cpp:6647-6656` — the false branch calls the
> same `FitToFaceDna` and then `CommitFaceState`. What `import_whole_rig` adds is
> `CommitFaceDNA`, which makes the body type **fixed and non-editable,
> permanently, per asset**.

### Refuted routes — do not re-derive

| Route | What happened |
|---|---|
| `UpdateJoints` neutral-joint writes | **REFUTED** — Y/Z coordinate mismatch; identity round trip failed by 164 cm on all three readers |
| neutral joints via the sanctioned path | **REFUTED** — the fitter never reads them; 1.26× against an unedited DNA's 1.13× |
| parametric fit as *author* | **REFUTED** — 10× command amplification, 4× reproducibility loss at edited states. Retained as *verifier* only (0.07 cm) |
| `request_auto_rigging(blocking=True)` | **REFUTED** — fatals the editor, `Assertion failed: IsValid() [SharedPointer.h:1133]`. `blocking=False` runs clean in ~25 s |
| `reload_packages` as undo | **REFUTED** — fatals the editor at address 0x470. The undo is a **closed-editor disk restore**, proven 0.1668 → 1.2531 → 0.1661 cm |

---

## 04 · The body

`Masculine/Feminine` on the body slider, range −2…+2. Two facts that are easy to
get wrong:

- **Body drives the parametric face.** −1.0 → −2.0 moves the jaw +0.468 cm
  (10.6× the noise floor). The same comparison on the *imported* face sits inside
  1.2× floor. So body work before the lock changes the face; after, it does not.
- **UE struct arrays iterate as copies.** A body-parameter write looked exactly
  like the advertised body lock until a positive control was put in the same run.
  The advertised permanent body-type lock *does not exist* — a scratch character
  edits its body identically after three whole-rig imports.

Instrument: `scripts/hero_body/body_silhouette.py` — orthographic at
0.253906 cm/px, difference-mask silhouette, bone-anchored heights, settle-gated.

---

## 05 · Textures and materials

Skin textures cannot be extracted by script. The door is a UI command:
**MetaHuman Character → Save Face Textures**, which writes the maps as PNGs.
Order is load-bearing: *Create Full Rig* **before** *Download Texture Sources* —
the other way round errors telling you to autorig.

> **A setter that returns False on names it just listed.**
> `MaterialEditingLibrary.set_material_instance_texture_parameter_value` returns
> **False** for `Basecolor`/`Normal`/`Cavity` — names
> `get_texture_parameter_names` lists on the same instance. Write the
> `texture_parameter_values` array directly. A re-run also made an instance *its
> own parent*, because the tool took the slot's current material as the parent;
> walk up instead.

The editor exports the **face atlas only**. Body maps go transient after the rig
and cannot be recovered — the body ships on stock MetaHuman maps. That is a
trade, not an accident.

---

## 06 · Assemble

`build_meta_human` is reflected and works from Python; the *unpack* is not
reflected anywhere in the 5.8 stub. Assemble writes `/Game/MetaHumans/`, not
`/Game/Hero/Generated/`.

> **Assemble leaves every package dirty and unsaved.** It logs "MetaHuman
> Character assembly succeeded" and writes nothing. On 2026-08-16 that read as
> "Assemble did nothing" until `get_dirty_content_packages()` returned **252**.

- **The assemble and its save are one payload.** The editor stopped answering
  remote execution immediately after `build_meta_human` twice; the first time it
  took 91 unsaved packages with it.
- **`duplicate_asset` cannot carry transient MetaHuman meshes.** Duplicated
  meshes have a degenerate reference pose — every bone within 6 mm of one point.
  Assembled: head 160.6 cm above root. Duplicated: 0.5 cm. 320× separation, with
  the known-bad meshes as the control.

---

## 07 · Vendor grooms — the working baseline

Four slots: **Hair, Beard, Mustache, Eyebrows**. Adding an item makes it
*available*; it is not worn until the instance selects it.

```python
col = subsystem.get_preview_collection(character)
col.try_add_item_from_wardrobe_item(slot, wardrobe_item)   # available
col.default_instance.set_single_slot_selection(slot, key)  # worn
subsystem.on_edit_preview_collection(character)            # REQUIRED
EditorAssetLibrary.save_asset(...)
```

`on_edit_preview_collection` is not optional — the engine's own docstring says
any code modifying the preview collection must call it to propagate edits back to
the Character asset.

> **The pack ships 38 grooms and 36 bindings.** `Hair_M_TwistedBraids` and
> `Hair_S_BrushCut` have no `<name>_Binding` sibling and are unreachable by the
> duplicate-a-binding route. Names come from the *asset*, not from the wardrobe
> item.

---

## 08 · Authoring a groom in Blender

Blender 5.2. A UE round trip costs ~4 minutes plus an editor; Blender answers the
same shape question in ~40 seconds. **Decide the shape in Blender; the UE trip
proves the groom, not the haircut.**

### The scripts

| Script | Role |
|---|---|
| `author_hero_hair.py` | places roots on his own face mesh, writes `groom_root_uv` and radius; every PARAMS key overridable via `HAIR_<KEY>` env |
| `head_frame.py` | the ONE measurement of head anatomy — brow, socket, crown, neck cut |
| `build_guide_stack.py` | the demo's non-baked Geometry Nodes stack |
| `preview_hair.py` | front/side/back + bare-head control, ~40 s |
| `validate_groom_export.py` | the four properties UE consumes — run BEFORE importing |
| `snap_curves_to_surface.py` | root relocation onto the target surface |

### The measured frame

```
hero authoring blend   Z-up, CENTIMETRES, face points −Y
skull sphere fit       centre (0.0038, −3.0978, 168.995)  radius 9.2274 cm
crown 178.44   brow 167.24   eye socket 165.46   neck cut 157.47
```

> **The brow was wrong by 3.68 cm for the whole project.** Two tools reported the
> eye band and *agreed* — `preview_hair.py` used `z_lo + 0.62…0.80 × height` and
> `author_hero_hair.py` gated the face zone at `face_zone_z_frac 0.80` of the
> same bounds. Same arithmetic in two files, so their agreement was one
> measurement, not two. It put the brow at 170.93; measured from the socket
> recess it is 167.24. Every guard "keeping hair out of his eyes" was defending
> his forehead, which is why four attempts at a fringe produced nothing.

### Traps in the authoring loop

- **A rebuild via `hair_curves.new` + `add_curves` on an existing groom crashes
  Blender** (`EXCEPTION_ACCESS_VIOLATION`) — 5.2 exposes no add/remove on
  `Curves`. Building fresh is fine; `bpy.ops.curves.delete` is the supported
  removal path.
- **Rotate strands about their own root; do not translate their tips.**
  Translation drags hair off the skull and uncovers scalp (left exposure
  22.9 → 34.4%). A rigid rotation preserves every point's distance from its root.
  Rotation and translation *fight*: running both scored worse than rotation alone.
- **Every picker takes the largest Curves object** and none consults visibility.
  A blend carrying a previous groom will have every downstream stage silently
  measure the wrong one.

---

## 09 · The Alembic contract

Export through the GroomExporter add-on, *not* `bpy.ops.wm.alembic_export`:

```python
bpy.ops.groom.buttonexport(
    filepath=out_abc, check_existing=False,
    groom_scale=1.0,                 # the hero blend is already in cm
    groom_width_scale=True,
    groom_radius_to_diameter=True,
    groom_animation=False, node_execution=False)
```

| Property | Why UE cares |
|---|---|
| points per curve ≥ 2 | `GroomBuilder.cpp:2403` asserts `CurveNumVertices >= 2` — a hard crash that killed an editor |
| `groom_root_uv` | without it a binding can only project each root onto the nearest triangle — from a groom authored on another head, that is the **jaw** |
| radius > 0 | zero width draws zero pixels |
| finite positions | one NaN can take out a whole group |

> **Two scale traps, both measured in UE not predicted.**
> An export at `global_scale` 1.0 from a *metres* blend lands in UE at 1/100 and
> at the origin. And `global_scale` multiplies `radius` too — a constant 0.436611
> became 43.7 UE units and the groom rendered as giant blocky ribbons. The width
> attribute is not stripped; it is present and wrong.

> **The generic Alembic importer is not a valid read path for a groom .abc.**
> Pointed at a groom that renders correctly in UE, `bpy.ops.wm.alembic_import`
> reports no `groom_root_uv` (the attribute *is* in the file), positions in the
> emitter's local space, and 5 points per curve where the file has 28. A verifier
> built on it refuses correct files. Verify on the **blend** before export, and on
> the **UE import report** after — UE is the consumer.

---

## 10 · Ingest into UE

The factory is `HairStrandsFactory` — not `GroomFactory`, not
`AlembicImportFactory` (which produces static/skeletal meshes: it imports
successfully and produces the wrong asset type).

**Scale is verified, never corrected.** A groom at the wrong scale still binds,
still renders, and is silently wrong; auto-fixing hides an exporter mismatch the
next groom inherits.

```
ue_exec.py <payload> --timeout 25       # 25, not 200
```

`--timeout` is a *discovery window spent in full*. A 220 s value wasted four
minutes per call while the import ran fine at 25.

---

## 11 · Binding

Three generations of this, and the history matters because the first two are
still findable.

| Approach | Outcome |
|---|---|
| `create_new_groom_binding_asset_with_path` | **STRUCK** — the build never completes; `Waiting for groom bindings to be ready 0/1`, no error, no later line |
| `GroomBindingAsset.build()` from Python | **REFUTED** — reflected, and fatals the editor: `Assertion failed: IsUnlocked() [BulkData.cpp:596]` |
| `LandscapeLabTools.build_groom_binding_for_mesh` | **PROVEN** — a C++ `UFUNCTION` doing the pipeline's own four steps, ~15 s |

```python
unreal.LandscapeLabTools.build_groom_binding_for_mesh(
    source_binding,     # an ALREADY-BUILT binding (a vendor one)
    target_mesh,        # the character's face mesh, READ off the actor
    dest_binding_path,
    dest_groom_path)
 -> (out_binding_path, out_groom_path, b_out_success, out_error)
```

**Assign both returned assets.** The deformation is baked into the groom *copy*,
not only into the binding; assigning the original groom with the new binding is
half the fix and renders like a total failure.

All four internal steps are load-bearing, each measured by omission. The one that
looks like housekeeping — stripping decimation around the RBF bake — is the one
that put hair in the right place.

### For a groom authored on its own target

Identity binding, source mesh empty. The RBF bake *fatals* on an identity binding
— `GroomRBFDeformer.cpp:740`, `check()` on
`RootDatas[GroupIndex].MeshPositions.IsValidIndex` — so it is guarded on
`EffectiveSource != TargetMesh`. For a groom authored on the target's own head the
transfer *is* the identity and the step was a no-op anyway (`R-GROOMBIND4`).

> **The stale-component trap, and its one-line fix.**
> The bind payload writes a groom **copy** each run. Rebuilding an asset that a
> live component already points at leaves the component holding a dead object
> behind a path that still reads back correctly — every property check passes and
> nothing draws. Sequence that works:
> **bind → respawn the actor → bind again → colour → render.**

### Guide correspondence — a cliff, not a gradient

```
guide_every 20   2,400 guides   BALD
guide_every  4  12,000 guides   BALD
guide_every  1  48,000 guides   FULL HAIR
```

A gradient would mean density. A cliff at "every curve is its own guide" means
**correspondence** — the only configuration in which each strand's nearest guide
is itself and *Merge Guide and Weight it* cannot get the weights wrong. It is a
workaround, not a repair.

---

## 12 · Colour

Ruled values: **melanin 0.92, redness 0.28**. The durable surface is the
assembled material instance, not the component and not the preview.

> **Writing `override_materials` NULLS the component's `binding_asset`.** An
> unbound groom draws nothing, so the render goes bald while the colour tool
> reports success and every read-back is correct — the material looks guilty.
> Re-assert the binding *after* the material and check it; the payload refuses
> otherwise.

- `groom_color.py` writes character *instance* parameters — a component-assigned
  groom never passes through the wardrobe, so it cannot be coloured that way.
- Enumerate the material variants: `MI_WI_Eyebrows_M_Dense_Hair` is a *stale*
  instance carrying no colour; the live one is the `None_1` variant.
- There is no `hairWhiteness` on this master — the family is `WhiteAmount` /
  `WhiteMelinin*`.

---

## 13 · Gates that actually discriminate

`groom_presence.py` (`R-HEROGROOM`) hides each groom in turn and requires the
picture to change. Three fail-closed properties, all measured:

- **Positive control** — the face mesh, hidden through the same call in the same
  payload: ~1,471,000 px, 1,266× floor. Without it a null is "I could not look",
  not "absent".
- **Stability map** — two captures of an *unchanged* subject differ over 11.3% of
  frame because the *forest* re-renders. Excluding those pixels took the floor
  472,199 → ~1,100 px.
- **Reproduce** — measured twice; >30% drift is a refusal.

> **A verdict belongs to its framing.** At 0.9 m all four grooms pass; at 6.2 m
> the entire face is ten thousand pixels. A landscape framing cannot carry a
> groom claim. The old checklist gate returned DELIVERABLE at every distance,
> because component properties are identical at all of them.

> **A groom converges over frames after its assets first become resident**, once
> per editor session, not per spawn. Hair reads 33,743 px on the first capture
> and 96,246 on the second with nothing changed but the frames spent. Every
> "bald" render before that was measured too early.

---

## 14 · The open defect

A DiffLocks-generated groom imports clean, binds, sits in the right place at the
right size — and renders zero pixels. This is the research target.

### What is being compared

| Property | DiffLocks (BALD) | Procedural (DRAWS) |
|---|---|---|
| curves | 100,943 | 48,000 |
| points | 2,826,404 | 576,000 |
| points per curve | 28 | 12 |
| Blender radius | 0.018 uniform | 0.012–0.035 taper |
| UE `hair_width` | 0.01 | 0.01 |
| bounds z (cm) | 153.4 – 180.8 | 154.3 – 184.2 |
| guides | 10,094 | 4,800 |
| root UV unique | 1,758 (1.74%) | 1,223 (2.55%) |
| material slots | empty | empty |
| `data.surface` | set | set |
| `curve_type` | absent / poly | absent / poly |
| **draws unbound** | **no — luma 50.23** | **yes — 34.60** |
| **draws bound** | **no — luma 50.21** | **yes — 34.94** |

### Constraints any explanation must satisfy

1. **It draws nothing with no binding at all.** Standalone `GroomActor`, no
   binding asset. So it is not binding, skinning, guide correspondence, or the
   MetaHuman component — it is the GroomAsset in isolation.
2. **UE knows exactly where it is.** Component bounds are correct, so the position
   data reached UE and parsed. Not empty, not at the origin, not at 1/100.
3. **The import reports full success** — `GroomAsset`, 100,943 curves, delta
   0.0000, 10,094 guides, no error, no warning.
4. **Count is not the lever** — 33,648 curves is equally bald.
5. **Not width, material, `curve_type`, `data.surface`, or interpolation.**
   Material was tested by *write* as well as read: the vendor's proven `MI_Hair`
   placed in the slot, read back, saved — still bald.

### What remains

Two things differ and neither has a cheap probe: the **strand point data** itself
(naturally varied generated geometry vs procedurally authored — segments ~0.3 cm
after resampling from 0.32 mm, total strand length 8.20 cm mean against the
working groom's ~20 cm), and the **root UVs**, sampled here by nearest-vertex
rather than by the authoring tool's own placement.

The hypothesis that fits every observation at once is that **UE's groom builder
produced empty render resources while still populating bounds and group info** —
the strand data passing validation but the strand-rendering buffer building
empty. That is where I would point the search.

### Source data

```
DiffLocks payload   positions (100943, 256, 3) float32, Y-up REAL METRES
                    sha256 97db0462…f96d2c, 100,943 strands, 29.6 s
                    strand length mean 0.0815 m, max 0.1497 m
registration        scalp.ply → hero scalp, similarity only
                    scale 100.600 cm per metre   ← the metre-to-centimetre
                    unit conversion, recovered from geometry
                    crown lands within 0.03 cm; 0.00% roots on his face
```

---

Every number here was measured on this machine — RTX 5080 Laptop, UE 5.8.1,
Blender 5.2 LTS. Recipes referenced by ID live in `RECIPES.md`; the narrative
behind each failure is in `LESSONS.md`. Where a claim could not be verified it is
marked as such rather than rounded up.
