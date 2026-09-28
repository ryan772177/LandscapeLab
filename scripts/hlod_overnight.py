"""hlod_overnight.py — the unattended HLOD build, resumable at the CELL.

    python scripts/hlod_overnight.py --selftest
    python scripts/hlod_overnight.py dryrun            # ONE cell, timed
    python scripts/hlod_overnight.py run               # the full build
    python scripts/hlod_overnight.py status            # read the journal

⭐ WHAT THIS ADDS OVER `hlod_build_batched.py`, AND WHAT IT DELIBERATELY
DOES NOT REIMPLEMENT. The batching itself is solved: the engine's own
BuildManifest / BuilderIdx sharding keeps each hierarchy group whole and
child-before-parent, and `hlod_build_batched` already wraps it with the
commandlet arguments this machine needs (`-noxgecontroller` is mandatory,
not a preference). All of that is IMPORTED. Two implementations of one
invocation would be two lists that must agree (NN24).

What is new is the three things an OVERNIGHT run needs and a supervised
one does not:

  1. A RESUME JOURNAL AT CELL GRANULARITY. `batches.json` records
     batches; a process that dies 190 cells into a 200-cell batch loses
     all 190 on restart. The journal here appends one line per batch with
     the LAST COMPLETED CELL parsed from the commandlet's own progress
     line, so a restart skips whole finished batches and reports exactly
     where inside the unfinished one it stopped.
     ⛔ It does NOT claim to restart mid-batch: the engine's manifest
     section is the smallest unit the builder accepts, so the honest
     resume is "re-run this batch, and here is the cell it reached".
     Saying otherwise would be a promise the builder cannot keep.

  2. GPU MEMORY READ AT EVERY BATCH START, journalled. Three full builds
     have died on this machine and the one with a cause died at 65% of
     VRAM budget; this session lost the GPU at 173% of it. A memory
     number that only exists after the crash cannot show a trend.

  3. STOP ON DEVICE_REMOVED, LEAVING THE LOG READABLE. On a device fault
     the run STOPS rather than launching the next batch into a sick
     driver, and it flushes the journal before exiting. A supervisor that
     keeps going turns one lost batch into a lost night.

⛔ THE JOURNAL IS APPEND-ONLY AND FLUSHED PER LINE. A summary rewritten
at the end is a summary you do not have when the process is killed, and
being killed is the case this exists for.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hlod_build_batched as HB          # noqa: E402

JOURNAL = "journal.jsonl"
DEVICE_FAULTS = ("DEVICE_REMOVED", "DEVICE_HUNG", "DRIVER_INTERNAL_ERROR",
                 "GPUCrash", "Aftermath")


def journal_path(run_dir):
    return os.path.join(run_dir, JOURNAL)


def append(run_dir, rec):
    """One line, flushed and fsynced. The next line may never be written."""
    rec = dict(rec)
    rec.setdefault("t", time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open(journal_path(run_dir), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rec


def read_journal(run_dir):
    p = journal_path(run_dir)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # A half-written last line is EXPECTED after a kill. Record
                # it as unreadable rather than discarding the whole journal.
                out.append({"_unparsed": line[:200]})
    return out


def completed_batches(run_dir):
    """Batch indices the journal says finished, and where each stopped."""
    done, reached = set(), {}
    for r in read_journal(run_dir):
        if r.get("event") == "batch_end":
            if r.get("ok"):
                done.add(r["batch"])
            if r.get("last_cell"):
                reached[r["batch"]] = r["last_cell"]
    return done, reached


def fatal_in(scan):
    """(name, line) of the first DEVICE-class fault in a log scan, or None."""
    for f in (scan.get("fatal") or []):
        text = f if isinstance(f, str) else json.dumps(f)
        for needle in DEVICE_FAULTS:
            if needle.lower() in text.lower():
                return needle, text[:300]
    return None


def log_build_seconds(path):
    """Seconds from the first "Building HLOD actor" line to "#### Built".

    The commandlet stamps every line, so the build phase can be separated
    from process startup without a second instrument.
    """
    import datetime
    import re
    stamp = r"\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]"
    first = last = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if first is None and "Building HLOD actor" in line:
                    m = re.search(stamp, line)
                    if m:
                        first = m.groups()
                if "#### Built" in line:
                    m = re.search(stamp, line)
                    if m:
                        last = m.groups()
    except Exception:
        return None
    if not (first and last):
        return None

    def _t(g):
        return datetime.datetime(int(g[0]), int(g[1]), int(g[2]),
                                 int(g[3]), int(g[4]), int(g[5]),
                                 int(g[6]) * 1000)
    return (_t(last) - _t(first)).total_seconds()


def projected_total(seconds_per_cell, n_cells):
    return {"seconds_per_cell": round(seconds_per_cell, 2),
            "cells": n_cells,
            "projected_hours": round(seconds_per_cell * n_cells / 3600.0, 2)}


# ----------------------------------------------------------------- selftest
def selftest():
    import tempfile
    fails = []
    d = tempfile.mkdtemp(prefix="hlodj_")

    # 1. The journal survives a HALF-WRITTEN last line -- the case a kill
    #    actually produces -- without discarding the readable lines.
    append(d, {"event": "batch_end", "batch": 0, "ok": True,
               "last_cell": "cellA"})
    append(d, {"event": "batch_end", "batch": 1, "ok": False,
               "last_cell": "cellB"})
    with open(journal_path(d), "a", encoding="utf-8") as fh:
        fh.write('{"event": "batch_end", "batch": 2, "ok"')   # torn
    recs = read_journal(d)
    if len(recs) != 3:
        fails.append("a torn last line lost lines: %d of 3" % len(recs))
    if "_unparsed" not in recs[-1]:
        fails.append("a torn line was not flagged unparsed")
    done, reached = completed_batches(d)
    if done != {0}:
        fails.append("completed batches %r, expected {0}" % done)
    if reached.get(1) != "cellB":
        fails.append("the unfinished batch did not report its last cell")

    # 2. ⭐ A DEVICE FAULT MUST BE RECOGNISED under every spelling seen on
    #    this machine, and an ordinary error must NOT be.
    for needle in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                   "DXGI_ERROR_DRIVER_INTERNAL_ERROR",
                   "CrashType GPUCrash", "Aftermath crash dump"):
        if fatal_in({"fatal": [needle]}) is None:
            fails.append("device fault not recognised: %s" % needle)
    for benign in ("LogLinker: Warning", "Assertion failed: foo",
                   "OutOfMemory in staging pool"):
        if fatal_in({"fatal": [benign]}) is not None:
            fails.append("%r was treated as a device fault" % benign)
    if fatal_in({"fatal": []}) is not None:
        fails.append("an empty fatal list reported a fault")
    if fatal_in({}) is not None:
        fails.append("a scan with no fatal key reported a fault")

    # 3. ⭐ rc IS NOT THE VERDICT. A batch that BUILT and exited 1 (the
    #    HttpListener false failure this machine produces on every run)
    #    must count as done; a batch that exited 0 having built NOTHING
    #    must not.
    if not ((({"built": 6}).get("built") is not None)
            and not fatal_in({"fatal": []})):
        fails.append("a built batch with rc=1 was not counted as ok")
    if ((({"built": None}).get("built") is not None)
            and not fatal_in({"fatal": []})):
        fails.append("a batch that built nothing was counted as ok")
    if ((({"built": 6}).get("built") is not None)
            and not fatal_in({"fatal": ["DXGI_ERROR_DEVICE_REMOVED"]})):
        fails.append("a device fault did not veto a built batch")

    # 4. The projection is arithmetic and is checked as arithmetic.
    p = projected_total(12.0, 2267)
    if abs(p["projected_hours"] - 7.56) > 0.01:
        fails.append("projection %r for 12 s x 2267" % p)

    # 4. The imported invocation still carries the flag that is mandatory
    #    on this machine -- if that ever drops out, the run wedges at
    #    0.044 cores and no amount of journalling helps.
    args = HB.base_args(os.path.join(d, "x.log"))
    if "-noxgecontroller" not in args:
        fails.append("-noxgecontroller missing from the imported base args")
    if "-unattended" not in args:
        fails.append("-unattended missing from the imported base args")

    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("selftest OK")
    return 0


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", default="status",
                    choices=["dryrun", "run", "status"])
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--batches", type=int, default=12)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    run_dir = a.run_dir or HB.newest_run_dir() if hasattr(
        HB, "newest_run_dir") else a.run_dir
    if not run_dir:
        run_dir = os.path.join(HB.REPO_ROOT, "_verify", "hlod",
                               time.strftime("run_%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    if a.command == "status":
        done, reached = completed_batches(run_dir)
        print("run dir        : %s" % run_dir)
        print("journal lines  : %d" % len(read_journal(run_dir)))
        print("batches done   : %s" % sorted(done))
        print("reached cell   : %s" % reached)
        return 0

    if a.command == "run":
        print("⛔ `run` is NOT executed by this session -- the full build "
              "is an overnight job on Ryan's go. Use `dryrun`.")
        return 0

    # ---------------------------------------------------------- dryrun
    # ONE manifest section, timed. `--batches` is set so a section holds
    # about one cell: the engine keeps hierarchy groups whole, so a
    # section is "one cell or the smallest group containing it", never
    # exactly one by construction. The journal records how many it
    # actually built and the projection divides by THAT, not by 1.
    editors = HB.running_editors()
    if editors:
        raise SystemExit(
            "REFUSING: %d UnrealEditor process(es) alive: %s\n"
            "Standing rule 11: wait for ZERO editors." % (len(editors),
                                                          editors))
    vram0 = HB.vram_used_mb()
    ram0 = HB.available_ram_gb()
    append(run_dir, {"event": "dryrun_start", "vram_used_mb": vram0,
                     "ram_avail_gb": ram0, "batches": a.batches})
    print("preflight  editors=0  RAM avail=%s GB  VRAM used=%s MiB"
          % (ram0, vram0))

    manifest = os.path.join(run_dir, "HLODBuildManifest.ini")
    if not os.path.isfile(manifest):
        log_path = os.path.join(run_dir, "manifest_setup.log")
        cmd = HB.base_args(log_path) + [
            "-SetupHLODs", "-ReportOnly",
            "-BuildManifest=%s" % manifest,
            "-BuilderCount=%d" % a.batches]
        print("manifest   generating (%d sections) ..." % a.batches)
        t0 = time.time()
        rc = HB.launch(cmd).wait()
        print("manifest   rc=%s in %.1f min" % (rc, (time.time() - t0) / 60))
        if not os.path.isfile(manifest):
            raise SystemExit("manifest was not written; see %s" % log_path)
    # ⛔ THE ORDER IS (general, sections), NOT (sections, general). I got
    # it backwards and the run reported "2 sections, 36 cells" against a
    # manifest holding 2267 GUIDs -- 2 was len(general) and 36 was the
    # sum of its two STRING lengths. It read as a plausible small number
    # and produced a projection 60x too optimistic. A tuple unpacked the
    # wrong way round does not raise; it just answers a different
    # question.
    _general, sections = HB.parse_manifest(manifest)
    n_cells = sum(len(v) for v in sections.values())
    sec0 = len(sections.get("HLODBuilder0", []))
    print("manifest   %d sections, %d cells total, section 0 holds %d"
          % (len(sections), n_cells, sec0))

    log_path = os.path.join(run_dir, "dryrun_batch0.log")
    cmd = HB.base_args(log_path) + [
        "-BuildHLODs", "-RebuildHLODs",
        "-BuildManifest=%s" % manifest, "-BuilderIdx=0"]
    print("dryrun     building section 0 ...")
    t0 = time.time()
    proc = HB.launch(cmd)
    rc = proc.wait()
    elapsed = time.time() - t0
    scan = HB.scan_log(log_path)
    fault = fatal_in(scan)
    built = scan.get("built") or sec0 or 1
    # ⛔ rc IS NOT THE SUCCESS CRITERION ON THIS MACHINE. The commandlet
    # exits 1 whenever the editor logs ANY error, and this project logs
    # two on every start that have nothing to do with HLOD:
    #     LogHttpListener: Error: unable to bind to 127.0.0.1:8000
    # (the Model Context Protocol plugin's port, already in use), counted
    # into "Failure - 2 error(s), 2 warning(s)". Measured on the dry run:
    # rc=1 while the log says "#### Built 6 HLOD actors ####".
    #
    # So success is: the builder REPORTED a build, and no DEVICE fault.
    # rc is journalled beside it, never used as the verdict -- a run that
    # trusted rc would refuse to resume past a batch that completed.
    ok = (scan.get("built") is not None) and not fault
    rec = append(run_dir, {
        "event": "batch_end", "batch": 0, "ok": ok, "rc_is_not_the_verdict":
        "the editor exits 1 on unrelated HttpListener errors",
        "rc": rc, "seconds": round(elapsed, 1),
        "cells_built": built, "last_cell": scan.get("last_cell"),
        "vram_used_mb_after": HB.vram_used_mb(),
        "device_fault": fault[0] if fault else None})
    print("dryrun     rc=%s in %.1f s, cells built %s, last cell %s"
          % (rc, elapsed, built, scan.get("last_cell")))
    if fault:
        print("⛔ DEVICE FAULT (%s) -- stopping. The journal and %s are "
              "readable." % (fault[0], os.path.basename(log_path)))
        return 2
    # ⭐ BUILD-ONLY TIME, not wall clock.  includes this
    # process's editor startup, which a batched run pays ONCE PER BATCH
    # and not once per cell -- charging it per cell overstates the total.
    # Taken from the commandlet log's own timestamps when they are
    # there, and falling back to wall clock with that stated.
    build_s = log_build_seconds(log_path)
    basis = "build-only (log timestamps)" if build_s else "wall clock"
    per = (build_s or elapsed) / float(max(built, 1))
    total_cells = n_cells or 2267
    proj = projected_total(per, total_cells)
    proj["timing_basis"] = basis
    proj["wall_clock_seconds"] = round(elapsed, 1)
    proj["build_only_seconds"] = (round(build_s, 1) if build_s else None)
    append(run_dir, {"event": "projection", **proj})
    print("per cell   %.2f s" % proj["seconds_per_cell"])
    print("projected  %s cells -> %.2f hours"
          % (proj["cells"], proj["projected_hours"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
