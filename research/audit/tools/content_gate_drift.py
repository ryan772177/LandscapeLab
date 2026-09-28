"""content_gate_drift.py -- what the content gate predicts vs what it measures.

READ-ONLY. AUDIT S-11.

THE GATE. `bench_capture` compares each still's measured
`featureless_fraction` against a PREDICTED sky fraction and refuses when
the excess passes 0.20:

    sky   = derived_stations[st]["traced_occlusion"]["pct_sky"] / 100
    slack = featureless_fraction - sky
    if slack > 0.20: VOID

THE PREDICTION'S SOURCE is `_verify/bench/bench_stations_derived.json`,
produced by the station derivation, not per run -- `bench_capture` falls
back to the most recent file anywhere under `_verify/bench/` when the
current date has none.

⭐ THE ASSUMPTION, stated because the gate never does: **a featureless
pixel is a sky pixel.** `pct_sky` is a RAY-TRACED occlusion figure
against the heightfield -- how much of the station's frustum sees no
terrain. The gate then treats any measured flatness beyond that as
missing world. That holds only while every NON-sky surface carries
detail the featureless test can see. It is not a claim about streaming
at all, which is what it is used to police.

This tabulates the two numbers per station per date so the drift is
visible, and reports the ratio. It does NOT widen the threshold.
"""
import glob
import io
import json
import os
import sys


def _find_repo(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md above %s" % start)
        d = nd


REPO = _find_repo(__file__)


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(
            REPO, "_verify", "bench", "*", "bench_run_*.json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        date = str(d.get("date") or os.path.basename(os.path.dirname(f)))
        if date < "2026-09-05":
            continue
        for st, v in (d.get("stills") or {}).items():
            if not isinstance(v, dict) or not v.get("exists"):
                continue
            pred = v.get("predicted_sky_fraction")
            meas = v.get("featureless_fraction")
            sky = v.get("featureless_sky_fraction")
            nonsky = v.get("featureless_non_sky_fraction")
            if pred is None or meas is None:
                continue
            rows.append({
                "date": date, "tag": str(d.get("tag")), "station": st,
                "profile": d.get("profile"),
                "predicted_sky": pred, "featureless": meas,
                "featureless_sky": sky, "featureless_non_sky": nonsky,
                "over_prediction": v.get("featureless_over_prediction"),
                "ratio_measured_sky_to_predicted": (
                    round(sky / pred, 1) if (sky and pred) else None),
            })

    rows.sort(key=lambda r: (r["station"], r["date"], r["tag"]))

    print("%-12s %-22s %-12s %8s %8s %8s %8s %7s"
          % ("date", "tag", "station", "pred", "featurel", "f_sky",
             "f_nonsky", "ratio"))
    for r in rows:
        print("%-12s %-22s %-12s %8.4f %8.4f %8s %8s %7s"
              % (r["date"], r["tag"][:22], r["station"],
                 r["predicted_sky"], r["featureless"],
                 ("%.4f" % r["featureless_sky"]) if r["featureless_sky"]
                 is not None else "-",
                 ("%.4f" % r["featureless_non_sky"])
                 if r["featureless_non_sky"] is not None else "-",
                 r["ratio_measured_sky_to_predicted"] or "-"))

    # Per-station summary: the prediction is a per-station constant, so
    # any spread WITHIN a station is measurement, and the gap between the
    # constant and the measurements is the model error.
    print("")
    print("PER STATION")
    by = {}
    for r in rows:
        by.setdefault(r["station"], []).append(r)
    summary = {}
    for st, rs in sorted(by.items()):
        preds = sorted({r["predicted_sky"] for r in rs})
        skies = [r["featureless_sky"] for r in rs
                 if r["featureless_sky"] is not None]
        feats = [r["featureless"] for r in rs]
        s = {
            "n": len(rs),
            "predicted_sky_values": preds,
            "featureless_min": round(min(feats), 4),
            "featureless_max": round(max(feats), 4),
            "featureless_sky_min": round(min(skies), 4) if skies else None,
            "featureless_sky_max": round(max(skies), 4) if skies else None,
            "ratio_sky_to_pred_min": (round(min(skies) / preds[0], 1)
                                      if skies and preds and preds[0] else None),
            "ratio_sky_to_pred_max": (round(max(skies) / preds[0], 1)
                                      if skies and preds and preds[0] else None),
        }
        summary[st] = s
        print("  %-12s n=%-3d predicted %s   featureless %.4f-%.4f   "
              "f_sky %s-%s   sky/pred %sx-%sx"
              % (st, s["n"], preds, s["featureless_min"], s["featureless_max"],
                 s["featureless_sky_min"], s["featureless_sky_max"],
                 s["ratio_sky_to_pred_min"], s["ratio_sky_to_pred_max"]))

    out = os.path.join(REPO, "research", "audit", "inputs",
                       "content_gate_drift.json")
    json.dump({
        "_what": "content gate: predicted sky vs measured featureless, "
                 "per station per date since 2026-09-05",
        "_model": "predicted = derived_stations[st].traced_occlusion."
                  "pct_sky / 100, a RAY-TRACED occlusion figure against "
                  "the heightfield. Produced by the station derivation, "
                  "not per run; bench_capture falls back to the most "
                  "recent file under _verify/bench/ when the run's own "
                  "date has none.",
        "_assumption": "A FEATURELESS PIXEL IS A SKY PIXEL. The gate "
                       "treats measured flatness beyond the traced sky "
                       "as missing world. That holds only while every "
                       "non-sky surface carries detail the featureless "
                       "test can resolve -- it is not a claim about "
                       "streaming, which is what the gate is used to "
                       "police.",
        "_threshold": "slack > 0.20 -> VOID. NOT widened.",
        "rows": rows, "per_station": summary,
    }, io.open(out, "w", encoding="utf-8"), indent=1)
    print("")
    print("wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
