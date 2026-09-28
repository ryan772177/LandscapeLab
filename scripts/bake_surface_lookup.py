"""Bake a CPU-queryable SURFACE TYPE lookup from the layer weightmap.

    python scripts/bake_surface_lookup.py
    python scripts/bake_surface_lookup.py --write

PHASE2_PLAN unit 11. "What am I standing on?" -- for footstep audio, movement
modifiers, VFX, and anything else that needs the surface without asking the
renderer.

** IT READS THE SAME DECLARATION THE MATERIAL READS. ** `textures/<biome>_weights.png`
is baked once by `make_layer_weightmap.py` and sampled by the landscape
material; this samples that same file. Non-negotiable 19: a second definition of
"where the rock is" would drift from the first silently, and the two would
disagree in a way no single check could see.

** DO NOT GET THIS BY PAINTING LANDSCAPE LAYERS. ** That forks the surface
definition -- the painted layers and the baked weightmap become two sources for
one physical fact, which is the same rule from the other direction.

WHAT IT PRODUCES
----------------
Two arrays at the weightmap's own resolution, written as one PNG:

    R  DOMINANT LAYER INDEX  (0..N-1, the recipe's layer order)
    G  DOMINANCE             (0..255) how far the winner leads the runner-up
    B  0, DECLARED INERT     -- non-negotiable 21: a channel nobody assigned
                                carries whatever was there and reads like data

** DOMINANCE IS NOT CONFIDENCE IN THE BAKE, IT IS BLEND DEPTH IN THE WORLD. **
The material BLENDS layers; it does not choose one. A cell at dominance 4 is
genuinely half rock and half grass, and a consumer that wants a single answer
there is asking a question the world does not have. Consumers should treat low
dominance as "on a boundary" rather than as "the lookup is unsure".

WHAT THIS CANNOT DO, from PHASE2_PLAN unit 11 verbatim
------------------------------------------------------
Per-surface WALKABILITY is not achievable this way. `IsWalkable` reads
`HitComponent->GetWalkableSlopeOverride()`, which is a PER-COMPONENT override,
and one landscape component here is 254 m square. "Scree is unwalkable" must be
gameplay logic on top of this query, never a landscape setting.
"""
import argparse
import hashlib
import io
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _manifest_disp_path(repo, surface_id):
    """Resolve a surface id -> its Displacement source PNG via Free/manifest.json
    (role 'displacement'). Returns an absolute path or None."""
    mp = os.path.join(repo, "Free", "manifest.json")
    man = json.loads(io.open(mp, encoding="utf-8").read())
    for a in man.get("assets", []):
        if a.get("id") != surface_id:
            continue
        for f in a.get("files", []):
            if f.get("role") == "displacement":
                return os.path.join(repo, "Free", f["path"].replace("/", os.sep))
    return None


def _load_disp01(path):
    im = Image.open(path)
    a = np.asarray(im)
    if a.ndim == 3:
        # The shader wires the sample's R pin into the blend
        # (make_landscape_material displacement path), so read R -- NOT the
        # channel mean, which would diverge on an RGB displacement whose
        # channels differ. The four shipped maps are single-channel grey, so
        # this is identical for them and correct for a future RGB one.
        a = a[:, :, 0]
    a = a.astype(np.float32)
    return a / (65535.0 if a.max() > 255.0 else 255.0)


def _tiled_sample(dmap, wx_cm, wy_cm, tile_cm):
    """Bilinear-sample dmap at world (wx_cm, wy_cm) under a `tile_cm` period,
    wrapped -- the shader's WorldPosition.xy / divisor tiling."""
    H, Wd = dmap.shape
    u = (wx_cm / tile_cm) % 1.0
    v = (wy_cm / tile_cm) % 1.0
    fx = u * Wd - 0.5
    fy = v * H - 0.5
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    dx = (fx - x0).astype(np.float32)
    dy = (fy - y0).astype(np.float32)
    x0m = x0 % Wd
    x1m = (x0 + 1) % Wd
    y0m = y0 % H
    y1m = (y0 + 1) % H
    c00 = dmap[y0m, x0m]
    c10 = dmap[y0m, x1m]
    c01 = dmap[y1m, x0m]
    c11 = dmap[y1m, x1m]
    return (c00 * (1 - dx) * (1 - dy) + c10 * dx * (1 - dy)
            + c01 * (1 - dx) * dy + c11 * dx * dy)


def _build_hbctx(hb, rec, layers, direct, has_remainder, repo, mlm):
    """Resolve + load everything the reweight needs, once. REFUSES (exits) if
    a stored layer has no displacement source -- the reweight cannot be
    modelled without it, and a silent skip would re-open the very divergence
    this exists to close."""
    # The shader only reweights a band when d_active is true (surface AND
    # (sub_active OR displacement on OR stochastic)); an inactive stored
    # band ships an IDENTITY reweight (factor 1). Gate this bake on the SAME
    # predicate, or a height_blend-on/displacement-off recipe would get the
    # full reweight here and an identity in the shader -- the exact
    # divergence F2 closes, re-opened for another recipe shape. REFUSE
    # rather than model factor-1, which would fork _cpu_height_blend's one
    # declaration (NN24). d_active is coincident with surface presence on
    # the shipped alpine_8k (displacement on, all stored surfaced).
    bands = mlm.layer_bands(rec)          # pure reducer; ValueError on faults
    ls = rec["landscape"]
    loc = ls["location_cm"]
    sxy = float(ls["scale_xy_cm"])
    dmaps, tiles = [], []
    for i in range(direct):
        L = layers[i]
        if not bands[i].get("d_active"):
            sys.exit("REFUSE: material.height_blend is on but stored layer "
                     "%r is not d_active -- the shader applies an IDENTITY "
                     "reweight to it (displacement off / no height path), so "
                     "modelling the full reweight here would drift from the "
                     "painted surface. Turn height_blend off or make the "
                     "layer d_active (displacement on)." % L["name"])
        sid = L.get("surface")
        p = _manifest_disp_path(repo, sid) if sid else None
        if not p or not os.path.isfile(p):
            sys.exit("REFUSE: material.height_blend is on but stored layer "
                     "%r (surface %r) has no Displacement source in "
                     "Free/manifest.json -- the reweight the shader applies "
                     "cannot be modelled, so the surface lookup would drift "
                     "from the painted surface. Path: %r" % (L["name"], sid, p))
        dmaps.append(_load_disp01(p))
        tiles.append(float(L["tiling_m"]) * 100.0)
    return {"k": float(hb["k"]), "eps": float(hb["eps"]),
            "dmaps": dmaps, "tiles": tiles, "direct": direct,
            "has_remainder": has_remainder,
            "loc": loc, "sxy": sxy, "mlm": mlm}


def _reweight_block(stored01, heights, ctx):
    """The shader model over arrays: _cpu_height_blend is elementwise, so a
    list of same-shape arrays returns the reweighted stored channels. One
    declaration of the formula (NN24) -- the material builder's."""
    return ctx["mlm"]._cpu_height_blend(
        [stored01[i] for i in range(ctx["direct"])],
        heights, ctx["k"], ctx["eps"])


def _dominant_dominance(W, hbctx):
    """(dominant uint8, dominance uint8, note). Raw argmax over W when hbctx
    is None; otherwise the height-reweighted argmax, row-blocked for memory."""
    h, w, nch = W.shape
    if hbctx is None:
        # argmax (first-max on ties), NOT argsort[...,-1] (unstable sort,
        # arbitrary winner on exact 8-bit ties) -- so this matches the
        # point-control's _point_dominant tie-break and a tied texel cannot
        # spuriously fail the positive control.
        dominant = np.argmax(W, axis=2).astype(np.uint8)
        srt = np.sort(W, axis=2)
        dominance = np.clip(srt[:, :, -1] - srt[:, :, -2], 0, 255).astype(
            np.uint8)
        return dominant, dominance, "DOMINANT: raw weightmap argmax " \
            "(no height_blend)."
    direct = hbctx["direct"]
    loc, sxy = hbctx["loc"], hbctx["sxy"]
    wx = (loc[0] + np.arange(w) * sxy).astype(np.float32)          # (w,)
    dominant = np.zeros((h, w), dtype=np.uint8)
    dominance = np.zeros((h, w), dtype=np.uint8)
    flipped = 0
    BLK = 1024
    for y0 in range(0, h, BLK):
        y1 = min(y0 + BLK, h)
        rows = np.arange(y0, y1)
        wy = (loc[1] + rows * sxy).astype(np.float32)             # (nb,)
        WX = np.broadcast_to(wx, (y1 - y0, w))
        WY = wy[:, None].astype(np.float32)
        stored01 = [W[y0:y1, :, i].astype(np.float32) / 255.0
                    for i in range(direct)]
        heights = [_tiled_sample(hbctx["dmaps"][i], WX, WY, hbctx["tiles"][i])
                   for i in range(direct)]
        rew = _reweight_block(stored01, heights, hbctx)
        chans = list(rew)
        if hbctx["has_remainder"]:
            chans.append(W[y0:y1, :, -1].astype(np.float32) / 255.0)
        stack = np.stack(chans, axis=2)                            # (nb,w,nch)
        dblk = np.argmax(stack, axis=2).astype(np.uint8)
        dominant[y0:y1] = dblk
        srt = np.sort(stack, axis=2)
        dom01 = srt[:, :, -1] - srt[:, :, -2]
        dominance[y0:y1] = np.clip(dom01 * 255.0, 0, 255).astype(np.uint8)
        # positive control that the model is NOT a no-op: how much it moved
        # the answer off the raw argmax.
        raw = np.argmax(W[y0:y1, :, :], axis=2).astype(np.uint8)
        flipped += int((dblk != raw).sum())
    note = ("DOMINANT: height-reweighted argmax (schema v1.28). The reweight "
            "moved the winner off the raw argmax on %d of %d texels (%.4f%%) "
            "-- the divergence now modelled instead of shipped."
            % (flipped, h * w, 100.0 * flipped / (h * w)))
    return dominant, dominance, note


def _point_dominant(W, hbctx, ys, xs):
    """The modelled (or raw) dominant at scattered points -- an independent
    re-derivation for the positive control."""
    if hbctx is None:
        return np.argmax(W[ys, xs, :], axis=1).astype(np.uint8)
    direct = hbctx["direct"]
    loc, sxy = hbctx["loc"], hbctx["sxy"]
    wx = (loc[0] + xs * sxy).astype(np.float32)
    wy = (loc[1] + ys * sxy).astype(np.float32)
    stored01 = [W[ys, xs, i].astype(np.float32) / 255.0 for i in range(direct)]
    heights = [_tiled_sample(hbctx["dmaps"][i], wx, wy, hbctx["tiles"][i])
               for i in range(direct)]
    rew = _reweight_block(stored01, heights, hbctx)
    chans = list(rew)
    if hbctx["has_remainder"]:
        chans.append(W[ys, xs, -1].astype(np.float32) / 255.0)
    return np.argmax(np.stack(chans, axis=1), axis=1).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--samples", type=int, default=20000,
                    help="points for the positive control")
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rp = os.path.join(REPO_ROOT, args.recipe)
    rec = json.loads(io.open(rp, encoding="utf-8").read())
    layers = rec["material"]["layers"]
    biome = rec["biome_id"]

    wpath = os.path.join(REPO_ROOT, "textures", "%s_weights.png" % biome)
    if not os.path.exists(wpath):
        sys.exit("REFUSE: no weightmap at %s. It is baked by "
                 "make_layer_weightmap and is the material's own source; "
                 "this must not invent one." % wpath)

    # v1.26 (2026-09-12): FOUR stored channels plus a shader REMAINDER.
    # `mask_plan` is IMPORTED from the material builder, not restated --
    # this file and the shader must agree about which channel is which
    # layer, and two copies of that mapping would disagree silently: the
    # shader would paint scree where the footstep audio played grass,
    # with nothing to compare them against (NN24, and NN19 again).
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import make_landscape_material as _mlm      # noqa: E402

    W = np.asarray(Image.open(wpath).convert("RGBA")).astype(np.int16)
    h, w, _ = W.shape
    try:
        direct, has_remainder = _mlm.mask_plan(len(layers))
    except _mlm.TexturePlanError as e:
        sys.exit("REFUSE: %s" % e)

    W = W[:, :, :direct]
    if has_remainder:
        # DERIVED EXACTLY AS THE SHADER DERIVES IT: 1 - sum(stored),
        # clamped at 0. Storing it instead would be a fifth number
        # obliged to agree with four others.
        rem = np.clip(255 - W.sum(axis=2), 0, 255).astype(np.int16)
        W = np.concatenate([W, rem[:, :, None]], axis=2)
    if W.shape[2] != len(layers):
        sys.exit("REFUSE: built %d mask channels for %d layers"
                 % (W.shape[2], len(layers)))

    print("recipe       %s   biome %s" % (args.recipe, biome))
    print("weightmap    %s   %d x %d" % (os.path.relpath(wpath, REPO_ROOT),
                                         w, h))
    print("layers       %s" % ", ".join(
        "%d=%s(%s)" % (i, l["name"], l.get("surface"))
        for i, l in enumerate(layers)))
    print()

    # HEIGHT-WEIGHTED BLEND MODELLED HERE (schema v1.28, Brief 7 Phase 1
    # addendum; Ryan ruling 2026-09-23). The landscape material reweights
    # each STORED channel by w_i*(h_i+eps)^k and renormalises (preserving
    # sum(stored), so the remainder is unchanged). bake_surface_lookup's
    # argmax MUST model the same reweight or the footstep/VFX/movement
    # answer disagrees with the painted surface at feathered overlaps -- the
    # two-consumers-of-one-contract case (NN19/NN24). MEASURED offline on
    # the real weightmap (research/brief7/input/f2_argmax_flip.json): the
    # raw argmax flips on 3.12% of WALKABLE texels (> the 2% accept bar),
    # margins p50 0.35 -- not near-ties -- so it is MODELLED, not accepted.
    # The reweight uses the SAME _cpu_height_blend and the SAME k/eps the
    # shader reads (one declaration), and samples each layer's height at the
    # texel's WORLD position under that layer's tiling, exactly as the shader
    # samples it via WorldPosition.
    hb = _mlm.height_blend_spec(rec)
    hbctx = _build_hbctx(hb, rec, layers, direct, has_remainder,
                         REPO_ROOT, _mlm) if hb else None
    dominant, dominance, model_note = _dominant_dominance(W, hbctx)
    print(model_note)
    print()

    print("DOMINANT LAYER, share of the map:")
    for i, l in enumerate(layers):
        frac = float((dominant == i).mean())
        print("  %d %-8s %8.4f%%   (%s)" % (i, l["name"], 100.0 * frac,
                                            l.get("surface")))
    print()
    print("DOMINANCE -- how far the winner leads the runner-up:")
    for q in (10, 50, 90):
        print("  p%-3d %6.1f" % (q, float(np.percentile(dominance, q))))
    boundary = float((dominance < 16).mean())
    print("  under 16 (a genuine blend, not an unsure lookup): %.2f%%"
          % (100.0 * boundary))
    print()

    # ---- POSITIVE CONTROL -------------------------------------------------
    # Re-derive the answer at N random points by code that did not build the
    # arrays. A bake that agrees with itself proves nothing; this proves the
    # arrays say what the source says. When height_blend is on, the source is
    # weightmap + heights + reweight, so the re-derivation applies the SAME
    # reweight POINT-WISE (a different code path from the row-blocked array
    # build, so an indexing/block bug still shows).
    rng = np.random.default_rng(args.seed)
    ys = rng.integers(0, h, size=args.samples)
    xs = rng.integers(0, w, size=args.samples)
    ref = _point_dominant(W, hbctx, ys, xs)
    baked = dominant[ys, xs]
    agree = int((ref == baked).sum())
    print("POSITIVE CONTROL  %d random points, re-derived %s"
          % (args.samples,
             "with the reweight applied point-wise" if hb
             else "straight from the weightmap"))
    print("  agree           %d of %d  (%.4f%%)"
          % (agree, args.samples, 100.0 * agree / args.samples))

    # ---- NEGATIVE CONTROL -------------------------------------------------
    # Shift the lookup by one row and it must STOP agreeing. Without this,
    # 100% agreement is also what a comparison against itself returns.
    shifted = np.roll(dominant, 1, axis=0)[ys, xs]
    dis = int((ref != shifted).sum())
    print("NEGATIVE CONTROL  the same lookup shifted one row")
    print("  disagree        %d of %d  (%.2f%%)  -- must be well above 0"
          % (dis, args.samples, 100.0 * dis / args.samples))
    print()

    ok = (agree == args.samples) and (dis > args.samples * 0.01)
    if not ok:
        print("REFUSE: controls did not behave. agree must be 100%% and the "
              "shifted lookup must disagree materially.")
        return 3

    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[:, :, 0] = dominant
    out[:, :, 1] = dominance
    # B is DECLARED INERT and written zero, and this line is the declaration
    # (non-negotiable 21). A channel nobody assigns carries whatever the
    # allocator left, reads like data, and is sampled by something eventually.
    out[:, :, 2] = 0

    dst = os.path.join(REPO_ROOT, "textures", "%s_surface.png" % biome)
    if not args.write:
        print("REPORT ONLY -- nothing written. Re-run with --write to bake "
              "%s" % os.path.relpath(dst, REPO_ROOT))
        return 0

    Image.fromarray(out, mode="RGB").save(dst)
    back = np.asarray(Image.open(dst).convert("RGB"))
    if not np.array_equal(back[:, :, 0], dominant):
        sys.exit("REFUSE: wrote the lookup and read back a different R "
                 "channel. PNG is lossless, so this is a real defect.")
    if back[:, :, 2].any():
        sys.exit("REFUSE: the inert B channel read back non-zero.")

    sha = hashlib.sha256(io.open(dst, "rb").read()).hexdigest()
    side = os.path.join(REPO_ROOT, "textures",
                        "%s_surface.json" % biome)
    io.open(side, "w", encoding="utf-8", newline="\n").write(json.dumps({
        "_what": "CPU surface-type lookup baked from the layer weightmap the "
                 "landscape material samples. R = dominant layer index in "
                 "recipe order, G = dominance (winner minus runner-up), "
                 "B = DECLARED INERT, written zero.",
        "_height_blend_modelled": bool(hbctx is not None),
        "_height_blend_note": (
            "schema v1.28: the dominant models the material's height-weighted "
            "reweight (w_i*(h_i+eps)^k, renormalised) so it matches the "
            "painted surface at feathered overlaps (F2, Ryan 2026-09-23). "
            "k/eps from recipe.material.height_blend."
            if hbctx is not None else
            "no material.height_blend -- raw weightmap argmax."),
        "_produced_by": "scripts/bake_surface_lookup.py",
        "_recipe": args.recipe,
        "_source_weightmap": os.path.relpath(wpath, REPO_ROOT).replace(
            "\\", "/"),
        "_walkability_is_NOT_available_here": (
            "IsWalkable reads HitComponent->GetWalkableSlopeOverride(), a "
            "PER-COMPONENT override, and one landscape component here is 254 m "
            "square. 'Scree is unwalkable' must be gameplay logic on top of "
            "this query, never a landscape setting."),
        "layers": [{"index": i, "name": l["name"],
                    "surface": l.get("surface")} for i, l in enumerate(layers)],
        "size": [w, h],
        "sha256": sha,
        "dominant_share": {l["name"]: round(float((dominant == i).mean()), 6)
                           for i, l in enumerate(layers)},
        "blend_boundary_fraction": round(boundary, 6),
    }, indent=1) + "\n")

    print("wrote %s  (%.1f MB)" % (os.path.relpath(dst, REPO_ROOT),
                                   os.path.getsize(dst) / 1048576.0))
    print("wrote %s  sha %s" % (os.path.relpath(side, REPO_ROOT), sha[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
