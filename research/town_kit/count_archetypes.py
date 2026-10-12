"""Offline: how many archetypes do the 303 town buildings collapse to?

Key = (W, D snapped to SNAP_M, sorted so W >= D; courses = height / 2.0 m). Rotation by 90 deg multiples is free
at placement, so W x D and D x W are one archetype. Reports counts under several snaps so the snap is chosen
on numbers. Run from the repo root.
"""
import collections, io, json

plan = json.load(io.open('city/alpine_basin_town_plan.json', encoding='utf-8'))
bl = [r for r in plan.get('buildings', plan.get('volumes', [])) if r.get('kind') == 'building'] \
    if isinstance(plan.get('buildings'), list) else None
if bl is None:
    rows = next(v for v in plan.values() if isinstance(v, list) and v and isinstance(v[0], dict) and 'kind' in v[0])
    bl = [r for r in rows if r['kind'] == 'building']
print('buildings', len(bl))
for snap in (0.5, 1.0, 1.5, 2.0):
    keys = collections.Counter()
    err = []
    for r in bl:
        x, y, h = r['size_cm']
        w, d = sorted((x / 100.0, y / 100.0), reverse=True)
        ws, ds = round(w / snap) * snap, round(d / snap) * snap
        err.append(max(abs(ws - w), abs(ds - d)))
        keys[(ws, ds, int(round(h / 200.0)))] += 1
    single = sum(1 for k, v in keys.items() if v == 1)
    print('snap %.1f m: %3d archetypes (%d used once); max footprint change %.2f m; top: %s'
          % (snap, len(keys), single, max(err), keys.most_common(4)))
