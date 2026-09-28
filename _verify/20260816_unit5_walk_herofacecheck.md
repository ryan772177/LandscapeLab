# Unit 5 — the 1 km walk, tag `herofacecheck`

**Class: PLAY IN EDITOR.** The character is driven by a per-tick
`AddMovementInput`, so CharacterMovementComponent does real floor
checks and real step-ups. This is a STRAIGHT LINE on heading
135.0 deg, **not** the inter-massif corridor — that corridor has no
spatial definition in this repo (`WORLD_VISION.md:304` is prose).

| | |
|---|---|
| distance | 28.6 m of 30 requested |
| samples | 20 over 4.9 s |
| spawn Z | 31109.6 cm |
| lowest Z | 31014.3 cm (95.3 below spawn) |
| descent beyond what 70.0 deg allows | worst 0.0 cm in a sample, longest run 0.00 s |
| is_falling | 0.0% of 20 readable samples |
| longest stop | 0.02 s |
| **fell through** | **no** |
| **stalled** | **no** |

## Trace log

`t_s, x_cm, y_cm, z_cm, speed_cm_s, is_falling, cumulative_cm`

```
0.017, 354600.0, -321400.0, 31109.6, 0.0, False, 0.0
0.278, 354551.7, -321351.7, 31104.2, 512.0, False, 68.3
0.544, 354439.5, -321239.5, 31097.9, 600.0, False, 227.0
0.811, 354326.3, -321126.3, 31094.0, 600.0, False, 387.0
1.078, 354213.2, -321013.2, 31090.2, 600.0, False, 547.0
1.344, 354100.0, -320900.0, 31082.6, 600.0, False, 707.0
1.595, 353994.0, -320794.0, 31074.1, 600.0, False, 857.0
1.861, 353880.8, -320680.8, 31061.6, 600.0, False, 1017.0
2.111, 353774.8, -320574.8, 31053.4, 600.0, False, 1167.1
2.361, 353668.7, -320468.7, 31045.1, 600.0, False, 1317.1
2.628, 353555.6, -320355.6, 31040.0, 600.0, False, 1477.1
2.894, 353442.4, -320242.4, 31037.8, 600.0, False, 1637.1
3.144, 353336.4, -320136.4, 31041.9, 600.0, False, 1787.1
3.411, 353223.2, -320023.2, 31046.2, 600.0, False, 1947.1
3.661, 353117.2, -319917.2, 31049.6, 600.0, False, 2097.1
3.928, 353004.0, -319804.0, 31046.9, 600.0, False, 2257.1
4.178, 352898.0, -319698.0, 31047.3, 600.0, False, 2407.1
4.428, 352791.9, -319591.9, 31042.4, 600.0, False, 2557.1
4.678, 352685.8, -319485.8, 31032.6, 600.0, False, 2707.1
4.928, 352579.7, -319379.7, 31014.3, 600.0, False, 2857.1
```

