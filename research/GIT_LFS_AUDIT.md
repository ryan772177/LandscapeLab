# Git LFS / pack-size audit — 2026-09-20

**READ-ONLY audit. Proposes; applies nothing.** Tool:
`scripts/git_blob_audit.py 364716f5..HEAD 200 30`. Motivated by the `git push`
of `364716f5..HEAD` (1500+ commits) repeatedly failing with
`RPC failed; HTTP 500 curl 22` mid-pack — the LFS objects (27 GB, 22806) upload
to S3 fine, but the **non-LFS git pack** is too big for the server in one shot.

## Finding: 27.9 GB of non-LFS content in the pushed range

4434 non-LFS blobs ≥ 200 KB, summing **27,890 MB**. (An LFS-tracked file is a
~130-byte pointer in git, so every blob ≥ 200 KB is real content, not a pointer.)

By extension (count, total):

| ext | blobs | total | notes |
|---|---|---|---|
| **.png** | 3229 | **19,386 MB** | the dominant bloat — committed render PNGs outside the 3 narrow LFS patterns |
| **.exr** | 98 | **5,332 MB** | `_verify/bench/**` HDR captures, ~100–133 MB each |
| .csv | 29 | 663 MB | perf CSVs (mostly since gitignored) |
| .blend | 32 | 562 MB | `hero/blender/**` |
| .zip | 6 | 376 MB | `research/audit/pipeline_full_2026-09-14_part{1..4}.zip` |
| .json | 179 | 344 MB | mostly text history-churn (dolly manifests, plans) — NOT an LFS candidate |
| .blend1 | 10 | 229 MB | Blender autosaves |
| .md | 624 | 613 MB | LESSONS/RECIPES history-churn — NOT an LFS candidate (text, diffable) |
| .log | 150 | 106 MB | committed logs |
| .npy/.npz/.obj/.abc/.fbx | 25 | 233 MB | mesh/mask data |

Top blobs are all `_verify/bench/**/*.exr` (123–133 MB each) and
`research/audit/pipeline_full_*.zip` (80–108 MB).

## What escapes `.gitattributes`

Current LFS patterns (`.gitattributes`): `*.uasset`, `*.umap`,
`terrain/*_8k*.png`, `textures/*_8k*.png`, `hero/generated/Textures/*.png`,
`*.dna`, `characters/*/grooms/difflocks_raw/*.npz`. So the 19.4 GB of `.png`
(mostly `_verify/**`, `refs/**`, `captures/**`) and all `.exr`, `.blend`,
`.blend1`, `.zip`, `.fbx`, `.obj`, `.abc`, `.npy` blobs are stored raw in git.

## PROPOSAL (for Ryan to rule — apply nothing tonight)

1. **Forward-looking `.gitattributes` additions** (affect only NEW commits):
   ```
   *.exr   filter=lfs diff=lfs merge=lfs -text
   *.blend filter=lfs diff=lfs merge=lfs -text
   *.blend1 filter=lfs diff=lfs merge=lfs -text
   *.fbx   filter=lfs diff=lfs merge=lfs -text
   *.obj   filter=lfs diff=lfs merge=lfs -text
   *.abc   filter=lfs diff=lfs merge=lfs -text
   *.npy   filter=lfs diff=lfs merge=lfs -text
   *.npz   filter=lfs diff=lfs merge=lfs -text
   ```
   And broaden PNG: either `*.png filter=lfs` (simplest) or, to keep tiny UI
   sprites in git, LFS-track `_verify/**/*.png`, `captures/**/*.png`,
   `refs/**/*.png`.
2. **Stop committing `_verify/bench/**/*.exr`** — they are large derived
   captures; gitignore them like the perf CSVs, or route to LFS. Same for
   `research/audit/pipeline_full_*.zip` (108 MB archives).
3. **The 27.9 GB is ALREADY in history.** LFS additions do not retroactively
   move it; only `git lfs migrate` / a history rewrite would — **out of scope**
   (standing rules forbid rewrite/force tonight, and it needs Ryan). Until then,
   the push must chunk around the oversized pack: use
   **`scripts/push_chunked.py`** (halve-on-failure, resumable, real exit code),
   which is what carried the current push past the 200-commit 500s.
4. If Ryan wants the history slimmed later: `git lfs migrate import
   --include="*.exr,*.png,..." --everything` on a coordinated rewrite (all
   clones re-pulled). A big decision — flagged, not taken.

## Instruments
- `scripts/git_blob_audit.py` — this audit (LFS-pointer size shortcut; no
  per-blob cat-file).
- `scripts/push_chunked.py` — the chunked pusher this finding justifies.

## PROPOSED (V0, 2026-09-21) — stop committing _verify/bench/** captures

Proposed, NOT applied. The `.exr` (123-133 MB) that forced the LFS migrate all
live under `_verify/bench/**`; they are large derived HDR captures, not source.
Either gitignore them or route the whole tree to LFS going forward:

Option A (gitignore -- simplest; they are regenerable evidence):
```
# .gitignore
_verify/bench/**/*.exr
_verify/bench/**/*.png
```
Option B (LFS, if the captures must stay tracked):
```
# .gitattributes
_verify/bench/**/*.exr filter=lfs diff=lfs merge=lfs -text
_verify/bench/**/*.png filter=lfs diff=lfs merge=lfs -text
```
Neither retroactively slims history (already migrated for >100 MB; the sub-100 MB
`.png` under `_verify/bench` remain non-LFS git blobs). A later `git lfs migrate
import --include="_verify/bench/**"` on a coordinated rewrite would move the rest
— Ryan's call, not taken.
