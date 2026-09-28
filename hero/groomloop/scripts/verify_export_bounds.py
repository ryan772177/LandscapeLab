"""verify_export_bounds.py -- RETIRED. This check cannot be done this way.

It REFUSES to run rather than being deleted, because the idea is an obvious one
and the next person to have it should find the measurement instead of repeating
it.

WHAT IT TRIED TO DO. Read the shipped .abc back and verify the roots land in the
hero's scalp band. The motivation was real: on 2026-08-22 an export at
global_scale 1.0 landed in UE at 1/100 scale and at the origin, and every check
upstream of the file had passed. A groom at the wrong scale still binds, still
renders, and is silently wrong.

WHY IT CANNOT. `bpy.ops.wm.alembic_import` is not a valid read path for a
MetaHuman groom .abc. Run against `cr_g75_ue.abc` -- a groom that imported,
bound and RENDERED CORRECTLY on the hero's head in Unreal the same day -- it
reported:

    no groom_root_uv                     (the attribute IS in the file; the
                                          generic importer does not restore it)
    0.00% of roots in his scalp band     (positions come back in the emitter's
                                          local space, root Z -7.48 .. 11.99)
    100.00% of roots on his face
    points 240,000 for 48,000 curves     (resampled to 5 per curve, from 28)

A gate that refuses a known-good input is not a strict gate, it is a broken one,
and ONLY THE POSITIVE CONTROL showed it. Without that control this would have
blocked the correct file and sent a session hunting a defect in the export.

WHAT TO USE INSTEAD, in order:
  scripts/blender/validate_groom_export.py   on the BLEND, before exporting --
      the properties UE actually consumes: points per curve, root UVs, radius,
      finite positions. Forty seconds.
  the UE import payload's own report        on the FILE, at ingest -- it reads
      through UE's HairStrandsFactory, which is the consumer, and reports curve
      count and group info. That is the only representation that can answer a
      question about what UE will draw.
"""

import sys

raise SystemExit(__doc__ + "\nREFUSED: retired instrument, see above.\n")
