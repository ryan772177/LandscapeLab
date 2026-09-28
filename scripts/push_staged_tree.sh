#!/bin/bash
# push_staged_tree.sh -- push a branch whose FIRST commit carries more than
# GitHub's ~2 GB per-push pack limit, by re-rooting it on a chain of commits
# whose trees grow one large directory at a time.
#
# Why (LESSONS 2026-09-27, "GITHUB PACK LIMIT"): after the LFS phase GitHub
# answers `RPC failed; HTTP 500` to a git pack over ~2 GB. The 2026-09-20
# convention (scripts/push_chunked.py, halve the commit span) cannot help when
# ONE commit holds 3.8 GB of plain blobs, and orphan "seed" branches do not
# help either: pack-objects only omits objects reachable from ANCESTORS of the
# commit being pushed, not from unrelated remote refs.
#
# Usage:
#   bash scripts/push_staged_tree.sh <branch> <remote> <dir1> [dir2 ...]
#   e.g. bash scripts/push_staged_tree.sh github-main origin research hero _verify
#
# What it does:
#   1. T_full = tree of the branch's root commit; T_k = T_full minus dirs k..N.
#   2. Commits C1(T_1) .. CN(T_full) chained; then every commit of <branch>
#      replayed (same tree, same message) on top of CN.
#   3. Pushes C1, C2, ..., CN, tip to <remote> main in turn; each pack holds one
#      directory's blobs. Stops on the first push whose sha does not come back
#      from `git ls-remote`.
#   4. Re-points <branch> at the replayed tip (its old commits stay in reflog).
# The trees are identical at every replayed commit; only the history gains the
# staged-upload chain at the root. Remote main must be empty or already an
# ancestor of C1 (i.e. run this once, on a fresh remote).
set -e
BRANCH="$1"; REMOTE="$2"; shift 2
DIRS=("$@")
if [ -z "$BRANCH" ] || [ -z "$REMOTE" ] || [ ${#DIRS[@]} -eq 0 ]; then
  echo "usage: $0 <branch> <remote> <dir> [dir ...]"; exit 2
fi
REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
SCRATCH="${SCRATCH:-$REPO/.git}"
FIRST=$(git rev-list --max-parents=0 "$BRANCH")
FULL=$(git rev-parse "$FIRST^{tree}")
echo "root commit $FIRST tree $FULL"

export GIT_INDEX_FILE="$SCRATCH/stage-index"
mk() { git read-tree "$FULL"; if [ $# -gt 0 ]; then git rm -r -q --cached "$@" >/dev/null; fi; git write-tree; }
CHAIN=()
PARENT=""
N=${#DIRS[@]}
for ((k=0; k<=N; k++)); do
  REST=("${DIRS[@]:k}")
  T=$(mk "${REST[@]}")
  if [ $k -eq 0 ]; then MSG="staged upload 1/$((N+1)): lite tree minus ${DIRS[*]} (GitHub 2 GB pack limit)";
  else MSG="staged upload $((k+1))/$((N+1)): + ${DIRS[k-1]}"; fi
  if [ -n "$PARENT" ]; then C=$(echo "$MSG" | git commit-tree "$T" -p "$PARENT"); else C=$(echo "$MSG" | git commit-tree "$T"); fi
  CHAIN+=("$C"); PARENT=$C
  echo "step $((k+1)) tree $T commit $C"
done
unset GIT_INDEX_FILE
if [ "$(git rev-parse "${CHAIN[N]}^{tree}")" != "$FULL" ]; then echo "last staged tree != root tree"; exit 1; fi

MSGF="$SCRATCH/stage-msg.txt"
for s in $(git rev-list --reverse "$BRANCH"); do
  git log -1 --format=%B "$s" > "$MSGF"
  PARENT=$(git commit-tree "$s^{tree}" -p "$PARENT" -F "$MSGF")
done
TIP=$PARENT
if [ "$(git rev-parse "$TIP^{tree}")" != "$(git rev-parse "$BRANCH^{tree}")" ]; then echo "replayed tip tree != $BRANCH tree"; exit 1; fi
echo "replayed tip $TIP"

for c in "${CHAIN[@]}" "$TIP"; do
  echo "$(date +%H:%M:%S) push $c -> $REMOTE main"
  git push "$REMOTE" "$c:refs/heads/main" 2>&1 | grep -vE '^\s*$' | grep -vi 'GH001\|git-lfs.github.com' | tail -3
  if ! git ls-remote --heads "$REMOTE" main | grep -q "^$c"; then echo "PUSH FAILED at $c"; exit 1; fi
done
git branch -f "$BRANCH" "$TIP"
echo "$(date +%H:%M:%S) DONE: $BRANCH -> $TIP, $REMOTE main = $TIP"
