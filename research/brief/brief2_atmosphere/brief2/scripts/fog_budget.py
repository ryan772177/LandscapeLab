"""fog_budget.py — derive ExponentialHeightFog density and height falloff
from what the EYE should see at distance, instead of typing 0.0015 or 0.02.

THE MODEL (UE ExponentialHeightFog, single layer; VERIFY constants in
Engine/Shaders/Private/HeightFogCommon.ush and
Engine/Source/Runtime/Engine/Private/Components/ExponentialHeightFogComponent.cpp):

    density(z)   = D * 2^( -F * (z - z0) / 1000 )        z, z0 in cm
    transmittance along a ray of length L (cm) from height z_cam with
    vertical slope dz/ds = s:
        T = 2^( - D/1000 * integral_0^L 2^(-F*(z_cam + s*t - z0)/1000) dt )
    horizontal ray (s = 0):  T = 2^( -D * 2^(-F*(z_cam-z0)/1000) * L/1000 )

  D = FogDensity      (the component's "Fog Density")
  F = FogHeightFalloff (the component's "Fog Height Falloff")
  z0 = fog actor Z    (the component's height datum)
  The /1000 on both D and F is the engine's cm scaling: with D=0.02 at the
  datum, T(1 km) = 2^-2 = 0.25 -- which matches how the default fog looks.
  If VERIFY finds a different constant, change UNIT below and nothing else.

WHY THESE TARGETS. Aerial perspective is a primary depth cue: contrast falls
with distance. A distant ridge should still be *legible* -- 25-40% of its
contrast left -- at the far edge of the shape band, and the horizon band
(the last 10% of the world) should be nearly absorbed into the sky. Fog
that is opaque at 500 m from an elevated station (the 2026-09-07 mid_slope
and vista frames: T ~ 0 beyond ~600 m) is not haze; it is a wall.

Inputs (metres, converted internally):
  --world-z-min / --world-z-max  the terrain's height range
  --valley-z    height where fog should be densest (the datum)
  --targets     "distance_m:transmittance" pairs for a camera at --cam-z,
                e.g. 1000:0.75 4000:0.30 8000:0.10 -- D is SOLVED from the
                first target; the rest are reported so the choice is
                visible. F comes from --halving-m (density halves every N m
                of altitude; default world height / 3), a stated rule.

Usage
  python fog_budget.py --world-z-min 0 --world-z-max 1552 --valley-z 120 \
      --cam-z 130 --targets 1000:0.75 4000:0.30 8000:0.10 [--out fog.json]
  python fog_budget.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import sys

UNIT = 1000.0  # cm per density/falloff unit (VERIFY)


def transmittance(D, F, z0_cm, cam_z_cm, L_cm, slope=0.0, steps=200):
    """Numeric line integral; slope = dz/ds along the ray (0 = level)."""
    if L_cm <= 0:
        return 1.0
    dt = L_cm / steps
    acc = 0.0
    for i in range(steps):
        t = (i + 0.5) * dt
        z = cam_z_cm + slope * t
        acc += 2.0 ** (-F * (z - z0_cm) / UNIT) * dt
    return 2.0 ** (-(D / UNIT) * acc)


def solve(world_min_m, world_max_m, valley_m, cam_m, targets, halving_m=None, slope=0.0):
    """D is solved from the FIRST target (bisection; T is monotone in D).
    F comes from a stated halving height, not from a fit: fog density
    halves every `halving_m` metres of altitude above the datum. Default
    halving = one third of the world's height span, so the ridge sees
    about 4x farther than the valley floor -- a rule to state in the
    recipe, not a number to discover. Remaining targets are REPORTED."""
    z0 = valley_m * 100.0
    cam = cam_m * 100.0
    if halving_m is None:
        halving_m = max(50.0, (world_max_m - world_min_m) / 3.0)
    F = UNIT / (halving_m * 100.0)
    d1, t1 = targets[0]
    lo, hi = 1e-6, 10.0
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if transmittance(mid, F, z0, cam, d1 * 100.0, slope) > t1:
            lo = mid
        else:
            hi = mid
    D = math.sqrt(lo * hi)
    rep = {"fog_density": round(D, 6), "fog_height_falloff": round(F, 6),
           "datum_z_m": valley_m, "density_halves_every_m": round(halving_m, 1),
           "camera_z_m": cam_m,
           "targets": [{"distance_m": d, "target_T": t,
                        "achieved_T": round(transmittance(D, F, z0, cam, d * 100.0, slope), 4)}
                       for d, t in targets]}
    rep["table_level_ray_T"] = {}
    for label, zc in (("valley", valley_m + 10), ("mid", (valley_m + world_max_m) / 2), ("ridge", world_max_m - 50)):
        rep["table_level_ray_T"][label + "_%dm" % zc] = {
            "%dm" % d: round(transmittance(D, F, z0, zc * 100.0, d * 100.0), 3)
            for d in (250, 500, 1000, 2000, 4000, 8000)}
    zr = world_max_m - 50
    rep["ridge_looking_down_20deg_T"] = {
        "%dm" % d: round(transmittance(D, F, z0, zr * 100.0, d * 100.0, slope=-math.tan(math.radians(20))), 3)
        for d in (500, 1000, 2000, 4000)}
    rep["_note"] = ("VERIFY UNIT against HeightFogCommon.ush before writing to a recipe. "
                    "Fog colour comes from the sky atmosphere (r.SupportSkyAtmosphereAffectsHeightFog=1, "
                    "inscattering luminance black), never a typed tint.")
    return rep


def selftest():
    # sanity: default-ish fog D=0.02, F=0.2 at the datum, level: T(1km)=0.25
    T = transmittance(0.02, 0.2, 0.0, 0.0, 100000.0)
    ok1 = abs(T - 0.25) < 0.01
    # solver recovers a known pair
    rep = solve(0, 1500, 100, 110, [(1000, 0.75), (4000, 0.30)])
    ok2 = abs(rep["targets"][0]["achieved_T"] - 0.75) < 0.02
    print("selftest:", "PASS" if (ok1 and ok2) else "FAIL", round(T, 4), rep["fog_density"], rep["fog_height_falloff"])
    return 0 if (ok1 and ok2) else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--world-z-min", type=float, default=0.0)
    ap.add_argument("--world-z-max", type=float, default=1552.0)
    ap.add_argument("--valley-z", type=float, default=100.0)
    ap.add_argument("--cam-z", type=float, default=110.0)
    ap.add_argument("--targets", nargs="+", default=["1000:0.75", "4000:0.30", "8000:0.10"])
    ap.add_argument("--halving-m", type=float, default=None, help="altitude over which fog density halves (default: world height / 3)")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    targets = [(float(x.split(":")[0]), float(x.split(":")[1])) for x in a.targets]
    rep = solve(a.world_z_min, a.world_z_max, a.valley_z, a.cam_z, targets, a.halving_m)
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
