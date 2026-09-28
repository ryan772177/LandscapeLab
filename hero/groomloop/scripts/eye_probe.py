"""eye_probe.py -- WHERE IS THE EYE BAND, actually?

    blender --background <hero_base.blend> --python eye_probe.py -- <out.json>

WHY THIS RUNS BEFORE THE SURVEYOR PUBLISHES A BROW LINE. Two tools in this
project report the eye band and they AGREE -- preview_hair.py gives
z_lo + 0.62..0.80 * height, and author_hero_hair.py gates the face zone at
face_zone_z_frac 0.80 of the same bounds. That is the SAME ARITHMETIC IN TWO
FILES, so their agreement is one measurement, not two (non-negotiable 0), and
the eye band has never been measured from the head at all. Every "no hair over
his eyes" claim rests on it.

My first detector was also wrong, in the informative way: it took the frontmost
vertex per height band and looked for a dip, and the frontmost vertex at eye
height is the BROW RIDGE, not the socket. It returned 176.1 -- 2.3 cm below the
crown, up on the forehead.

THE SOCKET IS OFF THE MIDLINE. So this samples a COLUMN at the eye's own
lateral offset and looks for the recess there, and reports the profile so the
answer can be read rather than trusted.
"""

import json
import os
import sys

import bpy
import numpy as np

UP = np.array([0.0, 0.0, 1.0])
FWD = np.array([0.0, -1.0, 0.0])
SIDE = np.cross(UP, FWD)


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out = tail[0]

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    mw = head.matrix_world
    V = np.array([list(mw @ v.co) for v in head.data.vertices])
    z, y, x = V @ UP, V @ FWD, V @ SIDE
    z_lo, z_hi = float(z.min()), float(z.max())
    height = z_hi - z_lo

    rep = {"producer": "eye_probe.py", "head": head.name,
           "mesh_bounds_up": [round(z_lo, 3), round(z_hi, 3)],
           "fraction_based_claim": {
               "preview_hair.py eye_z": [round(z_lo + 0.62 * height, 2),
                                         round(z_lo + 0.80 * height, 2)],
               "_note": "both existing tools use this same arithmetic"}}

    # THE COLUMN. Eyes sit ~3-4 cm off the midline on a human head; the sockets
    # are the recess there. Take the frontmost surface in that column per band.
    prof = []
    for lo, hi in ((2.0, 3.2), (3.2, 4.4), (4.4, 5.6)):
        col = (np.abs(x) >= lo) & (np.abs(x) < hi)
        bands = np.linspace(z_lo + 0.45 * height, z_hi, 45)
        row = []
        for i in range(len(bands) - 1):
            m = col & (z >= bands[i]) & (z < bands[i + 1])
            row.append(None if m.sum() < 4 else round(float(y[m].max()), 3))
        prof.append({"column_cm": [lo, hi],
                     "band_mid_up": [round(float(0.5 * (bands[i] + bands[i + 1])), 2)
                                     for i in range(len(bands) - 1)],
                     "front_extent": row})
    rep["columns"] = prof

    # The socket as a LOCAL minimum in the 3.2-4.4 column, searched only
    # between the nose tip and the crown so the receding forehead cannot win.
    col = (np.abs(x) >= 3.2) & (np.abs(x) < 4.4)
    bands = np.linspace(z_lo + 0.45 * height, z_hi, 60)
    mids, ext = [], []
    for i in range(len(bands) - 1):
        m = col & (z >= bands[i]) & (z < bands[i + 1])
        if m.sum() >= 4:
            mids.append(0.5 * (bands[i] + bands[i + 1]))
            ext.append(float(y[m].max()))
    mids, ext = np.array(mids), np.array(ext)
    # nose tip = global max forward extent near the midline
    nose_m = (np.abs(x) < 1.5)
    nose_z = float(z[nose_m][np.argmax(y[nose_m])])
    rep["nose_tip_up"] = round(nose_z, 3)
    above = mids > nose_z
    if above.sum() > 4:
        sub_m, sub_e = mids[above], ext[above]
        # local minima only
        loc = [i for i in range(1, len(sub_e) - 1)
               if sub_e[i] <= sub_e[i - 1] and sub_e[i] <= sub_e[i + 1]]
        rep["local_minima_up"] = [round(float(sub_m[i]), 3) for i in loc]
        if loc:
            rep["socket_up"] = round(float(sub_m[loc[0]]), 3)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
    print("__EYE__" + json.dumps({k: rep[k] for k in rep
                                  if k not in ("columns",)}))


if __name__ == "__main__":
    main()
