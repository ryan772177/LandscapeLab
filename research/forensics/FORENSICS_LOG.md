# Forensics — spiky landscape/rocks — orientation (read-only)

State as I understand it (2026-09-23, before any Task write):

1. HEAD dcc664f3, tree clean. Tags confirmed: pre-density-daylight 479501f3,
   pre-brief5-t3-hold a1711e19, pre-pcg-night b5ac5c55; commit dcc664f3 present.
2. research/DESK_HANDOFF.md is ABSENT on disk (rule 10 — stated, not assumed).
3. R-AESTHETIC-1 ruled: ms budgets suspended (perf recorded, not gated); visual
   gate = Ryan on stills. Hard stops remain: VRAM 13,312 MiB, DEVICE_HUNG
   protocol, persist protocol, tag-before-write, fence. T4 shadow probe + Task 3
   dry-run cancelled.
4. Committed world HEAD == pre-density-daylight: git diff tag..HEAD for
   LandscapeLab/Content/__ExternalActors__/Alpine8K = 0 files. The D4 revert
   holds at the COMMITTED level.
5. The D3 world commit (2372d8d0) touched ONLY __ExternalActors__ (1084 packages)
   + the 4 foliage/alpine_8k_*.json plans. NO .umap, NO landscape material, NO
   mesh, NO Config/ in that commit.
6. tag..01db49c0 (the D3-applied state, before the D4 revert 07ee6246) = 1084
   __ExternalActors__ changed. D4 reverted them -> HEAD == tag.
7. IMPLICATION: if the tag's landscape is clean, the committed HEAD landscape is
   clean too. So the spikes Ryan sees are candidates: (a) working-tree / LFS /
   editor state NOT in git; (b) the spikes predate the tag (already at the tag);
   (c) D3's __ExternalActors__ touch included LANDSCAPE proxies, not just foliage
   (Task 1 resolves this) -- reverted at HEAD, but a mechanism to characterise.
8. Fence: read-only; may write research/forensics/ + this log. No editor, no
   checkout into the tree, no branch switch, no LFS fetch/prune.
9. No contradiction with the files so far. Proceeding to Task 1.
