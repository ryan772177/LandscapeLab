"""hlod_build_landscape_cells.py -- rebuild ONLY the landscape HLOD cells.

    python scripts/hlod_build_landscape_cells.py plan --run-dir <ABS> --per-batch 8
    python scripts/hlod_build_landscape_cells.py run  --run-dir <ABS> [--start N]

⭐ WHY THIS EXISTS, AND WHY IT IS NOT `hlod_build_batched`.
`hlod_build_batched` shards the WHOLE world: `-SetupHLODs -ReportOnly
-BuilderCount=N` hands the engine all 2,267 actors and it partitions every
one of them. There is no way to say "only these 256". For a change whose
hash reaches exactly one builder -- `ProjectHLODMaxTextureSize`, hashed at
`LandscapeHLODBuilder.cpp:124`, inside `ULandscapeHLODBuilder::ComputeHLODHash`
and nowhere else -- rebuilding 2,267 cells to refresh 256 is ~9x the work and
~9x the GPU exposure.

So this writes the manifest ITSELF, in the engine's own format, holding only
the landscape cells:

    WorldPartitionHLODsBuilder.cpp:68        section name HLODBuilder<Idx>
                                 :176-178    -BuildManifest / -BuilderIdx
                                 :1062-1095  actor list comes ONLY from the section
                                 :287-310    ValidateParams: refuses a missing
                                             manifest, a missing -BuilderIdx,
                                             and an EngineVersion mismatch
                                 :1325-1412  ValidateWorkload: every CHILD HLOD
                                             actor must appear EARLIER in the
                                             same batch

⛔ THE CHILD-BEFORE-PARENT RULE IS WHY THIS IS SAFE TO SHARD BY HAND HERE,
AND IT IS NOT A GENERAL LICENCE. The L2 landscape cells are built from
LANDSCAPE COMPONENTS, which are ordinary actors, not HLOD actors -- so
`GetChildHLODActors()` is empty for them and any grouping validates. Cells
from a layer that consumes other HLOD actors would NOT be safe to shard this
way, and the engine would refuse at :1325 rather than produce a wrong result.

⚠ THE PARENTS GO STALE WITH THE CHILDREN. The Merged layer consumes these
Instanced cells as sources (`HLODSourceActorsFromCell.cpp:213-220`), so
rebuilding the children leaves the parents mismatched.
SINCE 2026-10-01, `--parents` (with `--built-before`) rebuilds them. It is
safe to shard by hand for a DIFFERENT reason than the children are: it
passes `-BuildHLODLayer=`, which skips the child-before-parent check
(WorldPartitionHLODsBuilder.cpp:1378-1381) -- so the children MUST already be
finished, and plan and every batch refuse unless all landscape children are
baked at/after the cutoff. A parent built over an old child would count as
done and never be selected again.

WHY NOT `cmd_run` FROM THE OTHER SCRIPT: its success test is
`stale_delta` on `STALE_LAYER = "MeshMerge(1)"`, the 2026-09-09 layer
migration. This operation's artefact signal is different -- a cell is done
when its own report records `ProjectHLODMaxTextureSize: 4096`. Reusing a
success test written for another operation is how a batch that did nothing
reads as a pass.

TWO ABORTS, BOTH RULED BY RYAN 2026-09-14:
    VRAM peak  > 13 GB in any batch          -> stop
    free disk  < 8 GB between batches        -> stop and NAME THE BATCH
                                                (raised from 6 on 2026-09-14)
The disk gate exists because one cell at 4096 measured 60.9 MB on disk
against 4.2 MB at 1024 (14.5x), and the machine had 28.9 GB free.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hlod_build_batched as HB   # noqa: E402
import hlod_report_offdisk as HR  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VRAM_ABORT_MB = 13 * 1024
DEFAULT_FREE_DISK_ABORT_GB = 8      # RULED BY RYAN 2026-09-14, raised from 6
TARGET_CAP = "4096"

# ⛔ THIS TOOL NEVER CLEARS A CACHE. The run is disk-bound on the local
# shared DDC (%LOCALAPPDATA%\UnrealEngine\Common\DerivedDataCache), which is
# OUTSIDE the repo -- standing rule 1. When the floor is reached this STOPS
# and names the batch to resume at; reclaiming the space is Ryan's, by
# explicit instruction 2026-09-14. A build tool that quietly deletes a cache
# to keep itself running is exactly the kind of unasked-for side effect that
# rule exists to prevent.

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


def free_disk_bytes():
    return shutil.disk_usage(REPO_ROOT).free


def landscape_cells():
    """Every package whose own build report carries the landscape hash fields.

    Membership is by CONTENT SIGNATURE, not by path or by label pattern --
    the same rule `hlod_gitignore` uses, and for the same reason: nothing in
    a World Partition external-actor path distinguishes an HLOD from a real
    actor. A cell is a landscape cell because ITS OWN REPORT records
    `ProjectHLODMaxTextureSize`, which only `ULandscapeHLODBuilder` writes.
    """
    out = []
    for p in HR.gitignored_hlod_packages():
        if not os.path.exists(p):
            continue
        text = HR.extract_block(p)
        if text is None or "ProjectHLODMaxTextureSize" not in text:
            continue
        rec = HR.parse(text, p)
        if not rec.get("guid"):
            raise SystemExit(f"REFUSING: no GUID parsed for {p}")
        out.append(rec)
    return out


# The Merged layer every landscape PARENT belongs to. Passed as
# -BuildHLODLayer= in --parents mode: that is what turns off the
# child-before-parent workload check (WorldPartitionHLODsBuilder.cpp:1378-1381)
# so parents can be built after their children, in a separate run.
PARENT_LAYER = "Alpine8K_HLODLayer_Merged"


def parent_cells():
    """Every HLOD package that is NOT a landscape cell but whose own report
    names a landscape child's baked texture (hlod_stale_parents.CHILD_TEX):
    the parents that consume the landscape cells. Membership by content
    signature, like landscape_cells."""
    import hlod_stale_parents as SP
    out = []
    for p in HR.gitignored_hlod_packages():
        if not os.path.exists(p):
            continue
        text = HR.extract_block(p)
        if (text is None or "ProjectHLODMaxTextureSize" in text
                or not SP.CHILD_TEX.search(text)):
            continue
        rec = HR.parse(text, p)
        if not rec.get("guid"):
            raise SystemExit(f"REFUSING: no GUID parsed for {p}")
        out.append(rec)
    return out


def cells_for(parents):
    return parent_cells() if parents else landscape_cells()


def _children_finished_or_exit(built_before):
    """--parents precondition (audit 2026-10-01): EVERY landscape child must
    already be baked at/after the cutoff. A parent rebuilt while a child is
    still old gets a fresh date, counts as done, and is never selected again
    -- baked from the old child with nothing to flag it."""
    kids = cap_census(built_before, parents=False)
    if kids["stale"] != 0:
        raise SystemExit(
            f"REFUSING: {kids['stale']} of {kids['landscape_cells']} landscape "
            f"children are still baked before {built_before}. Finish the "
            f"landscape-cell run first; parents built now would bake the old "
            f"children in.")


_DT_FMT = "%Y-%m-%d %H:%M:%S"


def _built_before(cell, cutoff):
    """True if the cell's own report DateTimeUTC precedes `cutoff` (UTC,
    'YYYY-MM-DD HH:MM:SS'). An unparseable date REFUSES: counting it either
    way would be a silent guess."""
    import datetime as _dt
    raw = cell.get("DateTimeUTC")
    try:
        when = _dt.datetime.strptime((raw or "")[:19], _DT_FMT)
    except ValueError:
        raise SystemExit(f"REFUSING: unparseable DateTimeUTC {raw!r} in "
                         f"{cell.get('path')}")
    return when < _dt.datetime.strptime(cutoff, _DT_FMT)


def cmd_plan(args, run_dir):
    editors = HB.running_editors()
    if editors:
        raise SystemExit(f"REFUSING: {len(editors)} UnrealEditor process(es) "
                         f"alive: {editors}\nStanding rule 11: wait for ZERO.")

    if args.parents and not args.built_before:
        raise SystemExit("REFUSING: --parents needs --built-before. A parent "
                         "has no ProjectHLODMaxTextureSize, so the cap test "
                         "would call every parent stale forever.")
    if os.path.exists(HB.state_path(run_dir)):
        raise SystemExit(f"REFUSING: {HB.state_path(run_dir)} exists; plan "
                         f"would overwrite a run's state. Use a fresh --run-dir.")
    if args.parents:
        _children_finished_or_exit(args.built_before)
    cells = cells_for(args.parents)
    print(f"{'parent' if args.parents else 'landscape'} cells found      "
          f": {len(cells)}")
    if not cells:
        raise SystemExit("REFUSING: 0 landscape cells. Nothing to build, and "
                         "a zero here is a broken scan, not an empty world.")

    if args.built_before:
        # The cutoff is checked ON ITS OWN first (audit 2026-10-01): a
        # malformed one must refuse cleanly, and a FUTURE one (local time
        # typed as UTC) would leave freshly built cells "before" it, so
        # every batch would read as having done nothing.
        import datetime as _dt
        try:
            _cut = _dt.datetime.strptime(args.built_before, _DT_FMT)
        except ValueError:
            raise SystemExit(f"REFUSING: --built-before {args.built_before!r} "
                             f"is not 'YYYY-MM-DD HH:MM:SS' (UTC)")
        _now = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        if _cut > _now:
            raise SystemExit(f"REFUSING: --built-before {args.built_before} "
                             f"is in the future (UTC now "
                             f"{_now.strftime(_DT_FMT)}); was local time "
                             f"typed as UTC?")
        # MATERIAL-REFRESH MODE (2026-10-01, LESSONS 2026-10-01c). The
        # landscape HLOD hash covers the material OBJECT REFERENCE
        # (LandscapeHLODBuilder.cpp:84 `<< MaterialInstances`), not the
        # material's content, so a rebuilt-in-place M_Alpine8K leaves every
        # cell's hash equal and nothing marks it stale. Staleness is then by
        # construction: a cell whose own report DateTimeUTC precedes the
        # material change was baked from the old material.
        done = [c for c in cells if not _built_before(c, args.built_before)]
        todo = [c for c in cells if _built_before(c, args.built_before)]
        print(f"  baked at/after {args.built_before} : {len(done)}")
        print(f"  baked BEFORE it, to rebuild    : {len(todo)}")
    else:
        done = [c for c in cells if c["ProjectHLODMaxTextureSize"] == TARGET_CAP]
        todo = [c for c in cells if c["ProjectHLODMaxTextureSize"] != TARGET_CAP]
        print(f"  already at cap {TARGET_CAP}       : {len(done)}")
        print(f"  STALE, to rebuild        : {len(todo)}")
    if not todo:
        raise SystemExit("REFUSING: 0 cells to rebuild -- nothing to plan.")

    # Deterministic order so a resume covers the same cells in the same batches.
    todo.sort(key=lambda c: c["label"] or c["guid"])

    # Engine version must match the running engine or ValidateParams refuses
    # (:287-310). Take it from a manifest the ENGINE wrote, never typed.
    src = args.engine_version_from
    general, _sections = HB.parse_manifest(src)
    engine_version = general.get("EngineVersion")
    if not engine_version:
        raise SystemExit(f"REFUSING: no EngineVersion in {src}")
    print(f"engine version (from engine): {engine_version}")

    per = args.per_batch
    batches = [todo[i:i + per] for i in range(0, len(todo), per)]
    manifest = os.path.join(run_dir, "HLODBuildManifest_landscape.ini")
    with open(manifest, "w", encoding="utf-8") as fh:
        fh.write("[General]\n")
        fh.write(f"BuilderCount={len(batches)}\n")
        fh.write(f"EngineVersion={engine_version}\n")
        for i, b in enumerate(batches):
            fh.write(f"\n[HLODBuilder{i}]\n")
            for c in b:
                fh.write(f"+HLODActorGuid={c['guid']}\n")
    print(f"manifest written           : {manifest}")

    # Read it back through the SAME parser the other script uses, so the file
    # is proved by something other than the code that wrote it.
    g2, s2 = HB.parse_manifest(manifest)
    total = sum(len(v) for v in s2.values())
    print(f"manifest read-back         : sections={len(s2)} guids={total} "
          f"general={g2}")
    if total != len(todo):
        raise SystemExit(f"REFUSING: manifest holds {total} GUIDs, expected "
                         f"{len(todo)}")

    state = {
        "run_dir": run_dir,
        "manifest": manifest,
        "batches": len(batches),
        "per_batch": per,
        "engine_version": engine_version,
        "guids_total": total,
        "section_sizes": {k: len(v) for k, v in sorted(s2.items())},
        "cells_total": len(cells),
        "cells_stale_at_plan": len(todo),
        "built_before": args.built_before, "parents": bool(args.parents),
        "free_disk_at_plan": free_disk_bytes(),
        "records": [],
    }
    HB.write_state(run_dir, state)
    print(f"plan OK -> {HB.state_path(run_dir)}")
    print(f"free disk                  : {free_disk_bytes()/2**30:.2f} GB")
    return 0


def cap_census(built_before=None, parents=False):
    """How many landscape cells are DONE: at the target cap, or -- in
    material-refresh mode -- baked at/after the cutoff. The key keeps its
    name `at_target_cap` so the run loop and batches.json read one field."""
    cells = cells_for(parents)
    if built_before:
        at = sum(1 for c in cells if not _built_before(c, built_before))
    else:
        at = sum(1 for c in cells
                 if c["ProjectHLODMaxTextureSize"] == TARGET_CAP)
    return {"landscape_cells": len(cells), "at_target_cap": at,
            "stale": len(cells) - at,
            "bytes_total": sum(c["bytes"] for c in cells)}


def cmd_run(args, run_dir):
    state = HB.read_state(run_dir)
    if HB.running_editors():
        raise SystemExit(f"REFUSING: UnrealEditor already running: "
                         f"{HB.running_editors()}")
    if HB.stop_requested(run_dir):
        raise SystemExit(f"REFUSING: STOP file present in {run_dir}")

    # What "done" means, in the words every message below uses.
    done_what = ("baked at/after %s" % state["built_before"]
                 if state.get("built_before") else "at cap %s" % TARGET_CAP)
    indices = ([args.only] if args.only is not None
               else list(range(args.start, state["batches"])))

    for idx in indices:
        if HB.stop_requested(run_dir):
            print(f"\nSTOP file seen -- pausing cleanly before batch {idx}.\n"
                  f"Resume with: run --start {idx}")
            break

        free = free_disk_bytes()
        floor = args.free_disk_abort_gb * 2 ** 30
        if free < floor:
            done = cap_census(state.get("built_before"), state.get("parents", False))
            raise SystemExit(
                f"\n=== DISK GATE TRIPPED -- STOPPED CLEANLY ===\n"
                f"free disk        {free/2**30:.2f} GB  (floor "
                f"{args.free_disk_abort_gb} GB)\n"
                f"RESUME AT BATCH  {idx}   of {state['batches']}\n"
                f"batches unbuilt  {state['batches']-idx}\n"
                f"cells {done_what}  {done['at_target_cap']} of "
                f"{done['landscape_cells']}   still stale {done['stale']}\n"
                f"resume with      run --run-dir <ABS> --start {idx}\n"
                f"Nothing was written by this check. Reclaiming space is NOT "
                f"this tool's job -- see the module docstring.")

        if state.get("parents"):
            # Re-checked before EVERY batch: the children could have gone
            # stale again between plan and run (audit 2026-10-01).
            _children_finished_or_exit(state["built_before"])
        before = cap_census(state.get("built_before"), state.get("parents", False))
        rec = HB.run_batch(state, run_dir, idx, attempt=1, force=True, extra_args=(["-BuildHLODLayer=%s" % PARENT_LAYER] if state.get("parents") else None))
        after = cap_census(state.get("built_before"), state.get("parents", False))

        rec["cap_at_target_before"] = before["at_target_cap"]
        rec["cap_at_target_after"] = after["at_target_cap"]
        rec["cap_delta"] = after["at_target_cap"] - before["at_target_cap"]
        rec["bytes_total_after"] = after["bytes_total"]
        rec["free_disk_after"] = free_disk_bytes()
        state["records"].append(rec)
        HB.write_state(run_dir, state)
        HB.commit_batch(run_dir, rec)

        expect = state["section_sizes"].get(f"HLODBuilder{idx}", 0)
        print(f"    cells {done_what}: {before['at_target_cap']} -> "
              f"{after['at_target_cap']}  (+{rec['cap_delta']}, expected "
              f"+{expect})   free disk {rec['free_disk_after']/2**30:.2f} GB"
              f"   VRAM peak {rec['vram_peak_mb']} MiB")

        # --- the hard stops -------------------------------------------------
        if rec["torn_packages"]:
            raise SystemExit(f"STOP: torn package(s) after batch {idx}: "
                             f"{rec['torn_packages'][:3]}")
        if not rec["true_exit"]:
            raise SystemExit(f"STOP: batch {idx} did not truly exit; live: "
                             f"{rec['leftover_processes']}")
        if rec["vram_peak_mb"] and rec["vram_peak_mb"] > VRAM_ABORT_MB:
            raise SystemExit(
                f"STOP: batch {idx} VRAM peak {rec['vram_peak_mb']} MiB "
                f"exceeded the {VRAM_ABORT_MB} MiB abort. Resume with: "
                f"run --start {idx+1}")
        if rec["fatal"]:
            raise SystemExit(f"STOP: fatal in batch {idx}: "
                             f"{rec['fatal'][0]['signature']}")
        # THE ARTEFACT SIGNAL for THIS operation -- not the other script's
        # stale-layer delta. A batch that exits clean and moves no cell to the
        # new cap has done nothing.
        if rec["cap_delta"] < expect:
            raise SystemExit(
                f"STOP: batch {idx} moved {rec['cap_delta']} cells to "
                f"{done_what}, expected {expect}. Clean exit, wrong artefact.")

    final = cap_census(state.get("built_before"), state.get("parents", False))
    print(f"\nFINAL  landscape cells {final['landscape_cells']}  "
          f"{done_what}: {final['at_target_cap']}  "
          f"stale: {final['stale']}")
    print(f"FINAL  landscape package bytes: {final['bytes_total']:,} "
          f"({final['bytes_total']/2**30:.2f} GB)")
    print(f"FINAL  free disk: {free_disk_bytes()/2**30:.2f} GB")
    state["final"] = final
    HB.write_state(run_dir, state)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["plan", "run", "census"])
    ap.add_argument("--run-dir", required=True, help="ABSOLUTE path")
    ap.add_argument("--per-batch", type=int, default=8)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--only", type=int, default=None)
    ap.add_argument("--free-disk-abort-gb", type=float,
                    default=DEFAULT_FREE_DISK_ABORT_GB,
                    help="stop cleanly BEFORE a batch when free disk is under "
                         "this (default %d GB, ruled 2026-09-14)"
                         % DEFAULT_FREE_DISK_ABORT_GB)
    ap.add_argument("--parents", action="store_true", help="build the PARENTS that consume the landscape cells (Merged layer), with -BuildHLODLayer=%s; requires --built-before" % PARENT_LAYER)
    ap.add_argument("--built-before", default=None,
                    help="MATERIAL-REFRESH mode: plan every landscape cell "
                         "whose report DateTimeUTC precedes this UTC time "
                         "('YYYY-MM-DD HH:MM:SS'); a batch is done when its "
                         "cells' dates move past it. For a material changed "
                         "in place, which the HLOD hash cannot see.")
    ap.add_argument("--engine-version-from",
                    default=os.path.join(REPO_ROOT, "_verify", "hlod",
                                         "build_20260914b",
                                         "HLODBuildManifest.ini"))
    a = ap.parse_args(argv)

    run_dir = os.path.abspath(a.run_dir)
    os.makedirs(run_dir, exist_ok=True)
    if a.command == "plan":
        return cmd_plan(a, run_dir)
    if a.command == "run":
        return cmd_run(a, run_dir)
    if a.parents and not a.built_before:
        print("REFUSING: census --parents needs --built-before (parents carry "
              "no ProjectHLODMaxTextureSize)")
        return 2
    print(json.dumps(cap_census(a.built_before, a.parents), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
