# Multi-view TRELLIS — the bakeoff's real result (2026-08-30)

**The blocker was the input, the spec fixed it, and the pipeline returns a
church.** `BAKEOFF.md` ended "Phase D is not blocked on a model. It is blocked
on an INPUT." That prediction is now confirmed from the other side.

## THE NUMBERS

| run | views | thin/long | vertices | faces | extent | VRAM peak |
|---|---|---|---|---|---|---|
| church, single view | 1 | **0.0114** | 74,904 | 149,610 | 0.5603 × 0.0114 × 1.0009 | 9,770 |
| castle control | 1 | **0.8491** | 570,703 | 1,141,334 | 0.8773 × 0.8509 × 1.0022 | 11,201 |
| **church, MULTI-VIEW** | **4** | **0.4317** | **190,498** | **381,228** | **0.7629 × 0.3949 × 0.9147** | **10,082** |

    load 21.3 s   inference 5.4 s   wall 27.8 s
    seed 20260830   model JeffreyXiang/TRELLIS-image-large
    [SPARSE] Backend: spconv, Attention: xformers   spconv algo: native

**0.4317 is 38× the flat sheet.** The intake verdict is **VOLUMETRIC**.

### Watertight — measured, with the method named

    edge use histogram   {2: 571842}      every edge used by exactly 2 faces
    boundary edges       0
    non-manifold edges   0
    V - E + F            190498 - 571842 + 381228  =  -116

**Closed and manifold: watertight TRUE.** But χ = −116 means **genus 59** —
fifty-nine handles of marching-cubes topological noise. Watertight is true and
is *not* the whole story; this wants a retopology pass before it is a
production mesh. Recorded rather than glossed.

### Why 0.4317 and not 0.85, and why that is CORRECT

The castle scores 0.849 because a castle is roughly as deep as it is wide. A
church is not: extent reads X 0.76 / Y 0.39 / Z 0.91 — **a building longer
than it is deep with a tall tower**, which is exactly what a nave plus spire
is. A church scoring 0.85 would be the suspicious result. The thin/long bar
separates *sheet from volume*; it was never a shape-quality score.

## AND IT WAS LOOKED AT, NOT ONLY MEASURED

`church_multi_views.png` — orthographic front / side / top, rendered from the
`.obj` by `render_mesh_views.py`, independent of TRELLIS's own report.

- **front** — nave with pitched roof, tower at one end carrying an **onion
  dome and finial**, belfry openings, porch annex
- **side** — nave gable, tower behind, entrance arch
- **top** — clean rectangular nave plan, tower a circular mass at one end

The concept records the church as *"pale tower, dark bulbous onion dome,
finial"*, and `CHURCH_VIEW_SPEC.md` §6 required the full vertical run — base,
nave, tower shaft, dome, finial. **All five are present and readable.**

This step is not ceremony. The same day, the concept loop reported
`deltas: []` over buildings whose roofs were visibly wrong, and ruling 4's
±20% bar passed a roof that visibly misfits. Numbers agreeing with each other
is what a picture is for.

## THE INPUT SET, MEASURED BEFORE THE GPU RAN

| view | frame | subject px | bbox | fill |
|---|---|---|---|---|
| az000 | 1024×1024 | 192,043 | 699×901 | 88% |
| az035 | 1024×1024 | 226,479 | 763×904 | 88% |
| az090 | 1024×1024 | 308,111 | 899×786 | 88% |
| az270 | 1024×1024 | 287,763 | 872×774 | 85% |

All four clear every floor in `CHURCH_VIEW_SPEC.md`, and the weakest is **52×**
the failed crop's ~3,700 subject pixels. `ai_input_guard.py --strict` cleared
all four, exit 0 each, **before the weights loaded** — per R-AIGATE, the only
moment that check can work.

**Two deviations from the spec, neither of which cost anything measurable:**

1. **JPEG, not PNG.** The spec asked for PNG because JPEG ringing on a
   high-contrast silhouette hurts background removal. Delivered as
   `.png.jpg`. The subject-pixel and fill numbers came through clean and the
   reconstruction is volumetric, so it did not bite here — but the preference
   stands for the next set.
2. **az035 in place of az180.** The spec asked 0/90/180/270; the set is
   0/35/90/270, and az035 is the 3/4 view the spec named as the best possible
   *single* choice. The back of the building is therefore unobserved, which is
   the most likely home for the genus-59 noise.

The operator noted roof material drifts between views (metal vs shingle) with
geometry consistent, and ruled the texture blend acceptable because the
material pipeline re-dresses it. **Geometry is the deliverable here** —
`formats=["mesh"]` — so the drift cannot reach the output.

## ⛔ THE RATIFICATION QUESTION FOR THE OPERATOR

`BAKEOFF.md` withheld a winner for **two independent reasons**. This run
settles one and **cannot settle the other**:

1. ~~*The subject is not servable yet.*~~ **RESOLVED.** The input is fixed,
   measured, and produces a volumetric watertight church.
2. **"One surviving candidate cannot be an unambiguous winner."** **STILL
   TRUE, AND NOW PERMANENT.** Hunyuan3D 2.1 was **DECLINED** under ruling 7 —
   recorded as declined, not deferred — and no other roster exists in this
   repo. There is no second candidate coming.

**So the brief's acceptance rule can never be met as written.** It says the
forge wrapper is built only if a winner is unambiguous *by comparison between
candidates*, and the field is permanently one.

**The question is therefore not "did TRELLIS win" — it is whether to change
the criterion from COMPARATIVE to ABSOLUTE:**

> Does TRELLIS become the ratified generation path on the strength of
> **absolute thresholds against its own controls** — volumetric vs its own
> flat-sheet failure, watertight, and a mesh that reads as the subject — given
> that a comparative winner is now impossible by your own ruling 7?

**This is the operator's call and I have not assumed it.** It is a change to a
brief's acceptance rule, which is escalation class 1.

If ratified, the next unit is the forge wrapper, and the second reason for
withholding it is also gone — a forge fed spec-conforming inputs industrialises
the production of *churches*, not of flat sheets. If not ratified, TRELLIS
stays a one-off tool and each landmark is hand-run.

## SCHEDULING CONSTRAINT, RE-MEASURED

    editor up, idle, this session      3,471 MiB (nvidia-smi, Windows)
    multi-view TRELLIS peak           10,082 MiB
    sum                               13,553 of 16,303

BAKEOFF.md recorded 16,064 of 16,303 for the single-view run plus a loaded
editor and concluded they "do not comfortably coexist". **The editor was closed
before this run anyway** — verified no dirty maps and no dirty content first,
then a graceful `CloseMainWindow`, VRAM back to 15,855 free. The two
instruments still disagree by ~5 GB (WSL CUDA view vs Windows allocator), so
the conservative one still governs the plan.
