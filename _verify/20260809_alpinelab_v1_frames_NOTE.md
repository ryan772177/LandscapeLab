# CORRECTION — how these two frames were actually produced

Commit `7db2d79f`'s message claims a controlled comparison proving that
**window focus** is what makes a HighResShot land, with this row as the
discriminator:

> `21:09  multiplier 2   SUCCEEDED   1.6 GB free, editor forced foreground`

**That row is false.** The 2x run reported **NO NEW OR REWRITTEN FILE**.
No run that night reported writing `HighresScreenshot00003.png`, which
is the file `20260809_alpinelab_v1_peak.png` was copied from.

## What is actually known

| time | request | what the run REPORTED | file on disk |
|---|---|---|---|
| 20:50:21 | `HighResShot 1` | **WROTE 00002.png, 340,894 B** | 00002.png |
| 20:52 | `HighResShot 2` | no new file | — |
| 20:58 | `HighResShot 1920x1080` | no new file | — |
| 21:02 | `HighResShot 1` | no new file | — |
| 21:09 | `HighResShot 2` (focused) | no new file | **00003.png appeared 21:09:40** |

`00003.png` is **856 x 561** — the viewport's own size, i.e. the
dimensions a `HighResShot 1` produces. `HighResShot 2` would be
1712 x 1122. So the most likely origin is the **21:02 `HighResShot 1`
request completing late**, after focus let a backlog drain.

**Which request produced it is UNKNOWN.** That is the honest answer, and
it is not "the 2x shot worked".

## What the frames still are

Valid. Both the 21:02 and 21:05 requests were issued against the same
parked camera (parked ~20:55, position and aim read back to 0.00 cm /
0.000 deg), so either one renders the view in `..._peak.png`. The
terrain, the framing and the lighting in these images are exactly what
they appear to be. Nothing about the LANDSCAPE evidence is affected.

## Root cause of the wrong claim, and it is mine

I ran every background capture as `python scripts/highres_shot.py ... |
tail -4`. `highres_shot.py` prints its verdict as a **banner followed by
a long diagnostic**, so `tail` kept the diagnostic and discarded the
verdict. The task output files are 196-319 bytes each: I was reading
outcomes off the last four lines of a message whose first line said the
opposite.

**Non-negotiable 14, verbatim: never truncate the output of an operation
you cannot repeat.** A capture on a throttled editor at 1.6 GB free is
exactly that kind of operation — each attempt cost minutes, and I
truncated all five.

The one run I could read in full (581 bytes, the 20:50 success) is the
only capture outcome that night that rests on evidence rather than on
inference from a file's mtime.

## What to do differently

- Capture runs pipe to a **file**, or are read in full. Never `tail`.
- A file appearing in `Saved/Screenshots/` is **not** attributable to the
  request you just made. The engine reuses the filenames, requests queue,
  and a throttled editor delivers late. `highres_shot.py` already
  compares `{path: mtime}` for exactly this reason — trust its verdict,
  not the directory listing.
- Focus remains a **plausible** contributor to the stall, and is worth
  doing before a capture. It is not demonstrated by this run.
