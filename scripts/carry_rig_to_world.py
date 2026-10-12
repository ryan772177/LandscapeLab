"""carry_rig_to_world.py -- carry the kept rig look (rounds 6-27 + RVT) into recipes/alpine_8k.json.

    python scripts/carry_rig_to_world.py [--write]

One explicit list of carried fields, not a blind copy: the rig recipe holds
rig-only decisions (hero-camera sun azimuth, no forest, rig heightmap paths)
that must NOT reach the world. Without --write it prints the change list.
Every value is copied FROM recipes/lookdev.json at run time, so a later rig
retune is carried by re-running, not by editing numbers here.

NOT carried, deliberately (2026-10-04):
  sun.azimuth_deg       chosen to rake the rig's hero camera (r10a)
  ForestFloor tint      the rig has no forest; the world's 0.42 was tuned on it
  heightmap/weightmap edits (cliff relief, midground terrace, scree shaping)
                        a separate, checked step: they move ground under placed trees
  map/asset paths       re-derived for the world (biome alpine_8k)
"""
import argparse
import copy
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIG = os.path.join(REPO, "recipes", "lookdev.json")
WORLD = os.path.join(REPO, "recipes", "alpine_8k.json")


def _layer(r, name):
    return next(l for l in r["material"]["layers"] if l["name"] == name)


def _species(r, name):
    return next((s for s in r["foliage"]["species"] if s.get("name") == name), None)


def carry(rig, w, log):
    m, mr = w["material"], rig["material"]
    # --- material ---------------------------------------------------------
    cv = copy.deepcopy(mr["cavity"])
    cv["map"] = "textures/alpine_8k_cavity.png"
    # World-only: the raw 8K heightmap's 1 m micro-relief made ~43% of rock read
    # as cliff-foot; 4 m slope smoothing matches the rig's 4% (2026-10-04).
    if cv.get("damp"):
        cv["damp"]["slope_smooth_m"] = 4.0
    m["cavity"] = cv
    log.append("material.cavity <- rig (map -> textures/alpine_8k_cavity.png)")
    for k in ("triplanar",):
        m[k] = copy.deepcopy(mr[k]); log.append("material.%s <- rig %s" % (k, mr[k]))
    old = m["macro_variation"]["chroma_ratio"]
    m["macro_variation"]["chroma_ratio"] = mr["macro_variation"]["chroma_ratio"]
    log.append("material.macro_variation.chroma_ratio %s -> %s" % (old, m["macro_variation"]["chroma_ratio"]))
    m["rvt_output"] = "recipes/rvt_alpine8k.json"
    log.append("material.rvt_output -> recipes/rvt_alpine8k.json")
    rr, rw = _layer(rig, "Rock"), _layer(w, "Rock")
    for k in ("near_surface", "macro_normal_strength"):
        rw[k] = copy.deepcopy(rr[k]); log.append("Rock.%s <- rig" % k)
    sr, sw = _layer(rig, "Scree"), _layer(w, "Scree")
    for k in ("base_color", "tiling_m"):
        log.append("Scree.%s %s -> %s" % (k, sw[k], sr[k])); sw[k] = copy.deepcopy(sr[k])
    # --- foliage (grass system) -------------------------------------------
    sp = w["foliage"]["species"]
    for name in ("Meadow", "MeadowFar"):
        src, dst = _species(rig, name), _species(w, name)
        for k in ("card", "density_per_10m2", "scale_range", "varieties"):
            if k in src:
                dst[k] = copy.deepcopy(src[k])
        log.append("%s <- rig card/density/scale/varieties" % name)
    new = ("MeadowNear", "MeadowMid", "MeadowMid2", "MeadowFar200", "ScreeTufts", "MeadowBoulders")
    # Remove every carried species BEFORE taking the anchor, so a re-run
    # reproduces the same order (pipeline rule 3; the first version anchored
    # first and moved the block past MeadowFar on the second run).
    for name in new:
        if _species(w, name) is not None:
            sp.remove(_species(w, name))
    anchor = sp.index(_species(w, "MeadowFar"))
    for name in new:
        sp.insert(anchor, copy.deepcopy(_species(rig, name)))
        anchor += 1
        log.append("+%s <- rig" % name)
    # The rig's RVT-blend instances sample the rig's RVTs; the world has its own
    # (recipes/rvt_blend_boulders_alpine8k.json). Re-point by the two recipes'
    # declared names, never by string surgery on paths.
    rb = json.load(io.open(os.path.join(REPO, "recipes", "rvt_blend_boulders.json"), encoding="utf-8"))
    wb = json.load(io.open(os.path.join(REPO, "recipes", "rvt_blend_boulders_alpine8k.json"),
                           encoding="utf-8"))
    # Index pairing is only sound when both recipes list the same sources in
    # the same order (audit 2026-10-04, finding 1).
    if rb["source_instances"] != wb["source_instances"]:
        raise SystemExit("rig and world RVT-blend recipes list different source_instances")
    remap = dict(("%s/%s" % (rb["target_dir"], a), "%s/%s" % (wb["target_dir"], b))
                 for a, b in zip(rb["target_instance_names"], wb["target_instance_names"]))
    n = 0
    for v in _species(w, "MeadowBoulders").get("varieties", []):
        om = v.get("override_materials") or []
        for i, p in enumerate(om):
            if p not in remap:
                raise SystemExit("MeadowBoulders override %r is not a rig RVT-blend instance" % p)
            om[i] = remap[p]; n += 1
    _species(w, "MeadowBoulders")["_rvt_blend"] = (
        "World copy (carry 2026-10-04): varieties use the M_Photoscan_RVTBlend8K instances "
        "(recipes/rvt_blend_boulders_alpine8k.json), which sample the world RVTs.")
    log.append("MeadowBoulders override_materials -> world RVT-blend instances (%d)" % n)
    # --- lighting (NOT azimuth) ------------------------------------------
    L, Lr = w["lighting"], rig["lighting"]
    # exposure.compensation_ev is NOT carried (2026-10-05): the world's value is
    # solved on its own grey card (R-METER, PPI0), never copied from the rig.
    # grade.white_temp_k is NOT carried either (2026-10-05): the world's 3438.6 is
    # a grey-card solve (R-GRADE); carrying the rig's 5200 put the card at R/G 1.19.
    for path in (("sun", "elevation_deg"), ("sky", "intensity"), ("clouds", "coverage"), ("clouds", "wind_param"),
                 ("clouds", "wind")):
        a, b = path
        old = L[a].get(b, "<absent>")
        L[a][b] = copy.deepcopy(Lr[a][b])
        log.append("lighting.%s.%s %s -> %s" % (a, b, old, L[a][b]))
    _layer(w, "Rock").setdefault("_carry_2026_10_04", (
        "Rig rounds 6-27 + RVT carried by scripts/carry_rig_to_world.py (Ryan: 'carry into alpine8k'). "
        "NOT carried: sun azimuth (rig hero camera), ForestFloor tint (world-tuned), heightmap/weightmap "
        "edits (cliff relief, terrace, scree shaping), rig map paths."))
    return w


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    rig = json.load(io.open(RIG, encoding="utf-8"))
    w = json.load(io.open(WORLD, encoding="utf-8"))
    log = []
    carry(rig, w, log)
    print("\n".join(log))
    if a.write:
        io.open(WORLD, "w", encoding="utf-8").write(json.dumps(w, indent=1, ensure_ascii=False))
        out = os.path.join(REPO, "_verify", "carry_alpine8k")
        os.makedirs(out, exist_ok=True)
        io.open(os.path.join(out, "carry_log.txt"), "w", encoding="utf-8").write("\n".join(log) + "\n")
        print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
