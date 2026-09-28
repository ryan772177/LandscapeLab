# THE DNA→MESH IDENTITY ROUND TRIP FAILS ON ALL THREE READERS

2026-08-17. Recipe **R-HERODNA**; narrative in LESSONS 2026-08-17 (later).
Instrument: `LandscapeLabTools.apply_dna_to_skeletal_mesh(..., reader_source)`.
Subject: `/Game/MetaHumans/MHC_AlpineHero/Face/SKM_MHC_AlpineHero_FaceMesh`,
875 bones. DNA: `hero/dna/MHC_AlpineHero_Head.dna`, the canonical export.

## THE TEST

Apply the **UNEDITED** canonical DNA with `UpdateJoints` and require every
probe bone to come back to its original component-space translation. Nothing
is edited, so a correct reader must be the identity. The mesh is reloaded
from disk between arms, so no arm inherits the previous one's damage.

## WHAT THE DNA DECLARES ABOUT ITSELF

Read, not inferred — `IDNAReader::GetCoordinateSystem()`, `FCoordinateSystem`
of `EDirection` (`DNACommon.h:47,268`):

    format 2.5   axes X=Left  Y=Up  Z=Front   translation cm   rotation deg
    870 joints

**Y-up.** The mesh is Z-up. That is the whole disagreement, stated by the
file itself.

## RESULT

    reader   legacy-wrapped   worst probe delta   identity
    file           no            164.42 cm          NO
    legacy         YES           205.44 cm          NO
    mesh           no            164.42 cm          NO

    spine_04 (the DNA root, parent to itself — the clean comparison,
              because UpdateJoints assigns it directly as a component
              transform rather than composing it through parents)

      mesh has      (0,   4.3415, 120.0077)
      file  gives   (0, 120.0077,   4.3415)     Y/Z swapped
      legacy gives  (0,-120.0077,   4.3415)     swapped AND negated
      mesh   gives  (0, 120.0077,   4.3415)     same as file

**`mesh` is byte-for-byte the same answer as `file`**, so the DNA the mesh
CARRIES is in the same Y-up space as the exported file. The hypothesis that
`export_dna` writes DCC space while the mesh keeps UE space is REFUTED.

**`legacy` is worse, not better**, and its own source says why: it applies
`(x, -y, z)` to joint translations (`LegacyDNAReaderAdapter`), which is a Y
negation, not the Y/Z swap the data needs.

## WHAT THIS MEANS

`USkelMeshDNAUtils::UpdateJoints` cannot reproduce this mesh's reference
skeleton from this DNA under any reader available in 5.8. The mesh's
reference skeleton was **not** produced by `UpdateJoints`; it came through
the MetaHuman assemble/Interchange path, which applies a conversion the
RigLogic utilities do not.

**So the `USkelMeshDNAUtils` route is a dead end for editing this assembled
hero unless the conversion is supplied by us.**

## THE CONVERSION, DERIVED AND CORROBORATED — NOT YET APPLIED

From the declared axes and the spine_04 numbers:

    UE.x = -DNA.x       (DNA X=Left, UE Y=Right)
    UE.y =  DNA.z       (DNA Z=Front)
    UE.z =  DNA.y       (DNA Y=Up)

    check   DNA (0, 120.0077, 4.3415)  ->  (0, 4.3415, 120.0077)   EXACT

**Corroborated by a different representation:** the capture stage found the
hero's face pointing along **+Y** in world (azimuth 90 is frontal, 270 is the
back of the head), which is what `DNA Z=Front -> UE Y` predicts. Two
independent facts, one mapping.

**STATED PLAINLY, THIS IS NOT PROVEN.** The X sign is UNTESTED — spine_04's
X is zero, so nothing here constrains it. And `UpdateJoints` reads
`GetNeutralJointRotation` as well as the translation, so a converted DNA
needs its ROTATIONS converted too or every child bone composes through a
wrong parent. The acceptance test is the identity round trip above, and it
is fail-closed: a converted DNA that does not reproduce the mesh exactly is
not the conversion.

## SAFETY

`dirty_at_end` is EMPTY. The probe path no longer dirties the package, and
the final reload left the mesh in its on-disk state — bounds
`[18.724, 10.859, 26.277]`, the assembled hero. Nothing was ever saved at any
point in this test, and `reload_packages(..., ASSUME_POSITIVE)` is what
undoes an arm.
