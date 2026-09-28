"""wb_joint_solve.py -- R-WB2x2 (closure A-6): joint white_temp/white_tint solve.

    python scripts/wb_joint_solve.py --wb-r <R/G> --wb-b <B/G> \
        --temp <current K> --tint <current> [--out <json>]
    python scripts/wb_joint_solve.py --selftest

The 2x2 uses THE MEASURED SLOPES of 2026-09-14 (grade_resolve run, all
four numbers from one session's rows -- base, +500 K step, +0.06 tint
step, artefact _verify/bench/grade_resolve_2026-09-14.json):

    d(R/G)/dK    = (1.1966 - 1.0230) / 500  = +3.4720e-4
    d(B/G)/dK    = (0.8113 - 0.9952) / 500  = -3.6780e-4   <- the coupling
    d(R/G)/dtint = (1.0583 - 1.0230) / 0.06 = +0.58833     <- the coupling
    d(B/G)/dtint = (1.1050 - 0.9952) / 0.06 = +1.83000

The 09-14 FIRST-ORDER solve used only the diagonal (R by temp, B by
tint) and left a B/G residual of ~1.03 -- exactly the off-diagonal terms
it dropped. The joint solve inverts the full matrix from the CURRENT
measured card, so the residual is solved rather than inherited.

Both solutions are reported side by side; adoption is the caller's, per
the ruling: adopt joint if the confirm card lands 0.97-1.03 on BOTH axes.
"""
from __future__ import annotations

import argparse
import json

# The 2026-09-14 measured matrix (see docstring for derivation).
M_RR_K = (1.1966 - 1.0230) / 500.0     # d(wb_R)/dK
M_BR_K = (0.8113 - 0.9952) / 500.0     # d(wb_B)/dK
M_RT = (1.0583 - 1.0230) / 0.06        # d(wb_R)/dtint
M_BT = (1.1050 - 0.9952) / 0.06        # d(wb_B)/dtint


def solve(wb_r, wb_b, temp_k, tint):
    er, eb = 1.0 - wb_r, 1.0 - wb_b
    det = M_RR_K * M_BT - M_RT * M_BR_K
    if abs(det) < 1e-12:
        raise SystemExit("singular slope matrix -- cannot solve")
    dk_joint = (er * M_BT - M_RT * eb) / det
    dt_joint = (M_RR_K * eb - er * M_BR_K) / det
    # First-order, as 09-14 did it: R/G by temperature alone, B/G by tint
    # alone -- the diagonal, ignoring the coupling.
    dk_first = er / M_RR_K
    dt_first = eb / M_BT
    pred_first = {
        "wb_R": wb_r + M_RR_K * dk_first + M_RT * dt_first,
        "wb_B": wb_b + M_BR_K * dk_first + M_BT * dt_first,
    }
    return {
        "measured": {"wb_R": wb_r, "wb_B": wb_b,
                     "white_temp_k": temp_k, "white_tint": tint},
        "matrix": {"dR_dK": M_RR_K, "dB_dK": M_BR_K,
                   "dR_dtint": M_RT, "dB_dtint": M_BT,
                   "source": "grade_resolve_2026-09-14.json rows"},
        "first_order": {"white_temp_k": round(temp_k + dk_first, 1),
                        "white_tint": round(tint + dt_first, 6),
                        "predicted_after": {k: round(v, 5)
                                            for k, v in pred_first.items()},
                        "_note": "diagonal only; the coupling lands in the"
                                 " residual, which is what 09-14 measured"},
        "joint": {"white_temp_k": round(temp_k + dk_joint, 1),
                  "white_tint": round(tint + dt_joint, 6),
                  "predicted_after": {"wb_R": 1.0, "wb_B": 1.0},
                  "_note": "full 2x2; exact to first order by construction"},
    }


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-52s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond

    # From the 09-14 base point the joint solve must null both ratios
    # exactly under its own linear model.
    r = solve(1.0230, 0.9952, 3481.9, -0.0139)
    j = r["joint"]
    wr = (1.0230 + M_RR_K * (j["white_temp_k"] - 3481.9)
          + M_RT * (j["white_tint"] + 0.0139))
    wb = (0.9952 + M_BR_K * (j["white_temp_k"] - 3481.9)
          + M_BT * (j["white_tint"] + 0.0139))
    check("joint nulls both ratios under the model",
          abs(wr - 1.0) < 5e-4 and abs(wb - 1.0) < 5e-4)
    # The first-order branch must reproduce the 09-14 adoption from the
    # same base -- that run solved temp 3481.9->3415.7 (dk = -66.2).
    f = r["first_order"]
    check("first-order reproduces the 09-14 temp step (3415.7)",
          abs(f["white_temp_k"] - 3415.7) < 0.5)
    # ...and must PREDICT the coupled B/G residual the run then measured
    # (~1.024 predicted vs 1.0339 measured -- sign and size, not exact).
    check("first-order model predicts a positive B/G residual",
          f["predicted_after"]["wb_B"] > 1.015)
    # A card already neutral must move nothing.
    r0 = solve(1.0, 1.0, 3400.0, -0.02)
    check("a neutral card solves to zero movement",
          abs(r0["joint"]["white_temp_k"] - 3400.0) < 0.05
          and abs(r0["joint"]["white_tint"] + 0.02) < 1e-6)
    print("selftest %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wb-r", type=float)
    ap.add_argument("--wb-b", type=float)
    ap.add_argument("--temp", type=float)
    ap.add_argument("--tint", type=float)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if None in (a.wb_r, a.wb_b, a.temp, a.tint):
        ap.error("--wb-r --wb-b --temp --tint all required (or --selftest)")
    r = solve(a.wb_r, a.wb_b, a.temp, a.tint)
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
