#!/usr/bin/env python3
"""shade_reference.py — derive the expected shade/lit blue ratio at a stated white point.

Model: the grade neutralises a Planckian white W (the ruled white_temp_k). A lit grey
card under W reads (1,1,1). A shaded grey card sees skylight only, modelled as a CIE
D-series illuminant at CCT T_shade. Both are Bradford-adapted so W is neutral, converted
to linear sRGB, and reported as B/luma with luma = Rec.709 (0.2126, 0.7152, 0.0722).

Output is the reference band for a CARD-PAIR instrument (shade card / lit card), which is
albedo-free by construction. It is NOT a band for terrain pixels.

    python shade_reference.py --white 3481.9 --shade 6500 10000
    python shade_reference.py --white 5200   --shade 6500 8500      # reproduces the old 1.10-1.60 premise

Self-test: python shade_reference.py --selftest
"""
import argparse, sys
import numpy as np

def planck_xy(T):  # Kim et al. 2002, 1667-25000 K
    t = float(T)
    if t <= 4000: x = -0.2661239e9/t**3 - 0.2343589e6/t**2 + 0.8776956e3/t + 0.179910
    else:         x = -3.0258469e9/t**3 + 2.1070379e6/t**2 + 0.2226347e3/t + 0.240390
    if t <= 2222:   y = -1.1063814*x**3 - 1.34811020*x**2 + 2.18555832*x - 0.20219683
    elif t <= 4000: y = -0.9549476*x**3 - 1.37418593*x**2 + 2.09137015*x - 0.16748867
    else:           y =  3.0817580*x**3 - 5.87338670*x**2 + 3.75112997*x - 0.37001483
    return x, y

def daylight_xy(T):  # CIE daylight locus, 4000-25000 K
    T = float(T)
    if T < 4000 or T > 25000: raise ValueError("daylight locus valid 4000-25000 K")
    if T <= 7000: x = -4.6070e9/T**3 + 2.9678e6/T**2 + 0.09911e3/T + 0.244063
    else:         x = -2.0064e9/T**3 + 1.9018e6/T**2 + 0.24748e3/T + 0.237040
    return x, -3.0*x*x + 2.870*x - 0.275

def XYZ(xy): x, y = xy; return np.array([x/y, 1.0, (1-x-y)/y])

_B = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
_M = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
_D65 = XYZ((0.3127, 0.3290))

def rgb_under_white(illum_xyz, white_xyz):
    s, d = _B @ white_xyz, _B @ _D65
    A = np.linalg.inv(_B) @ np.diag(d / s) @ _B
    return _M @ (A @ illum_xyz)

def bluma(rgb): return rgb[2] / (0.2126*rgb[0] + 0.7152*rgb[1] + 0.0722*rgb[2])

def band(white_k, shade_lo, shade_hi, white_locus="planck"):
    W = XYZ(planck_xy(white_k) if white_locus == "planck" else daylight_xy(white_k))
    lit = bluma(rgb_under_white(W, W))
    lo = bluma(rgb_under_white(XYZ(daylight_xy(shade_lo)), W)) / lit
    hi = bluma(rgb_under_white(XYZ(daylight_xy(shade_hi)), W)) / lit
    return lit, lo, hi

def selftest():
    lit, lo, hi = band(3481.9, 6500, 10000)
    assert abs(lit - 1.0) < 1e-3, "lit card must read neutral at its own white"
    assert 2.1 < lo < 2.3 and 2.85 < hi < 3.0, (lo, hi)
    _, lo5, hi5 = band(5200, 6500, 8500, "daylight")
    assert 1.25 < lo5 < 1.35 and 1.55 < hi5 < 1.7, (lo5, hi5)   # the old 1.10-1.60 premise
    print("selftest OK")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--white", type=float, default=3481.9)
    ap.add_argument("--white-locus", choices=["planck", "daylight"], default="planck")
    ap.add_argument("--shade", type=float, nargs=2, default=(6500, 10000), metavar=("LO_K", "HI_K"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: selftest(); sys.exit(0)
    lit, lo, hi = band(a.white, *a.shade, a.white_locus)
    print(f"white {a.white:.1f} K ({a.white_locus})  lit-card B/luma {lit:.4f}")
    print(f"shade D{a.shade[0]:.0f}-D{a.shade[1]:.0f}  card-pair shade/lit B/luma band  {lo:.3f} - {hi:.3f}")
    for T in (6500, 7000, 7500, 8000, 8500, 9000, 10000):
        if a.shade[0] <= T <= a.shade[1]:
            _, v, _ = band(a.white, T, T, a.white_locus)
            print(f"   D{T}: {v:.3f}")
