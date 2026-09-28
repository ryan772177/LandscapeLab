"""Reproduce ELandscapeHLODTextureSizePolicy::AutomaticSize from source.

    ComputeRequiredTexelDensityFromDrawDistance   MaterialUtilities.cpp:2674-2691
        ScreenSizePercent = ComputeBoundsScreenSize(0, R, (0,0,D), Proj)
                          = max(M00, M11) * R / D
        ScreenSizePixel   = ScreenSizePercent * 1920
        TexelDensity/m    = ScreenSizePixel / (2R/100)
      -> R cancels: TexelDensity = max(M00,M11) * 1920 * 50 / D

    FPerspectiveMatrix(45deg, 1920, 1080, 0.01):
        M00 = 1/tan(45) = 1 ; M11 = (1920/1080)/tan(45) = 1.7778

    GetMeshTextureSizeFromTargetTexelDensity      LandscapeHLODBuilder.cpp:168-193
        TexelRatio  = sqrt(1/Mesh3DArea_cm2) * 100
        SizePerfect = ceil(TargetDensity / TexelRatio)
        SizeHi = RoundUpToPowerOfTwo(SizePerfect) ; SizeLo = SizeHi >> 1
        pick whichever of Lo/Hi has the smaller density error
"""
import math

M00, M11 = 1.0, 1920.0 / 1080.0
K = max(M00, M11) * 1920.0 * 50.0          # TexelDensity = K / D


def density(D_cm):
    return K / D_cm


def pick_size(target_density, area_cm2):
    texel_ratio = math.sqrt(1.0 / area_cm2) * 100.0
    perfect = math.ceil(target_density / texel_ratio)
    hi = 1 << max(0, (perfect - 1)).bit_length() if perfect > 1 else 1
    lo = hi >> 1
    d_lo, d_hi = lo * texel_ratio, hi * texel_ratio
    chosen = lo if (target_density - d_lo) < (d_hi - target_density) else hi
    return perfect, lo, hi, chosen, texel_ratio


PROXY_M = 8129.0 / 16.0            # 16x16 proxies over an 8129-vertex world
AREA = (PROXY_M * 100.0) ** 2      # cm^2

print("proxy edge %.1f m   area %.4g cm^2" % (PROXY_M, AREA))
print("K = %.1f  (TexelDensity = K / D_cm)" % K)
print("")
print("%-12s %-12s %-10s %-6s %-6s %s"
      % ("D (cm)", "target dens", "perfect", "lo", "hi", "CHOSEN"))
for D in (25600, 51200, 76800, 102400, 204800):
    t = density(D)
    p, lo, hi, ch, tr = pick_size(t, AREA)
    print("%-12d %-12.5f %-10d %-6d %-6d %d" % (D, t, p, lo, hi, ch))

print("")
print("Observed on 6 untouched L2 cells: 1024")
t = density(76800)
p, lo, hi, ch, tr = pick_size(t, AREA)
print("  D = 76800 cm (the Instanced layer's measured loading_range)")
print("  -> target %.5f, perfect %d, lo %d, hi %d, CHOSEN %d   %s"
      % (t, p, lo, hi, ch, "MATCH" if ch == 1024 else "no"))

print("")
print("What mesh area would yield the observed 32, holding D = 76800?")
for want in (32,):
    # chosen == want implies texel_ratio ~ target/perfect with perfect near want
    for edge_m in (10, 15, 20, 25, 30, 40, 60):
        a = (edge_m * 100.0) ** 2
        p, lo, hi, ch, tr = pick_size(density(76800), a)
        print("  mesh edge %-4d m -> perfect %-6d chosen %d" % (edge_m, p, ch))

print("")
print("And what draw distance would yield 32, holding the full 508 m area?")
for D in (1_000_000, 2_000_000, 4_000_000):
    p, lo, hi, ch, tr = pick_size(density(D), AREA)
    print("  D = %-10d cm (%.1f km) -> perfect %-5d chosen %d"
          % (D, D / 100000.0, p, ch))

print("")
print("SpecificSize branch, for comparison (LandscapeHLODBuilder.cpp:224):")
v = 4096
print("  :224 RequiredTextureSize = HLODTextureSize      = %d" % v)
v = max(v, 16)
print("  :230 Max(_, 16)                                 = %d" % v)
v = min(v, 1024)
print("  :234 Min(_, HLODMaxTextureSize=1024)            = %d" % v)
print("  :237 Min(_, GetMax2DTextureDimension())         = %d" % v)
print("  -> SpecificSize CANNOT produce 32 from 4096.")
