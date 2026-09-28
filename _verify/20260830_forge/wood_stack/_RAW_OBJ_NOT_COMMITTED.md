# ⛔ `SM_WoodStack_Forge_raw.obj` IS ON DISK AND **NOT IN GIT**

**Stated plainly because its absence from the commit is deliberate, not an
oversight** (standing rule 10).

    file      SM_WoodStack_Forge_raw.obj
    size      108,976,605 bytes = 103.9 MiB
    status    on disk, gitignored via `_verify/**/*_raw.obj`

## WHY

**103.9 MiB is over GitHub's hard 100 MiB per-file limit.** Committing it does
not merely bloat the repo — it makes that commit and every commit after it
**unpushable** to `origin`, and the only cure is a history rewrite. `.git` is
already 39 GB.

`R-FORGE` names **the `.fbx` as the artefact of record**, and that file IS
committed (700,652 bytes). The raw `.obj` is a stage-3 intermediate.

## WHAT THIS COSTS, AND IT IS NOT NOTHING

**The forge is not bit-reproducible** — same seed, same inputs, different
mesh. So this `.obj` cannot be recovered by re-running stage 3; a rerun
produces an equivalent asset, never this one.

Concretely, what is lost if this file is deleted: the ability to **re-run
stage 4 at a different triangle budget** against *this* mesh. The committed
`.fbx` is already decimated to 15,000 tris. Re-deriving a 30,000-tri version
of the same asset is impossible without it.

**Do not delete this file** on the assumption git has it. Git does not.

## DIVERGENCE FROM THE CHURCH, RECORDED

`_verify/20260830_forge/church/SM_Church_Forge_raw.obj` **is** tracked — it is
13.3 MiB, comfortably under the limit, and predates this rule. It stays
tracked; untracking it would not shrink history. The two assets are therefore
handled differently, on a size threshold, and this file is why.
