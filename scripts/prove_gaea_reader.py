"""Positive AND negative controls for read_gaea_graph's gates. Scratch copies
only -- the real .terrain is never touched.

Each negative control asserts the tool refuses with the SPECIFIC exit code of
the gate under test (2 = unreadable, 3 = --check-refs, 4 = --check-spec,
6 = --against-build mismatch), NOT merely a non-zero exit -- otherwise any
unrelated crash (import error, drifted fixture, bad path) would exit non-zero
and read as "the gate works". The codes are read from read_gaea_graph.main().
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = r"C:\Users\Admin\UE5LandscapePipeline"
SRC = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain"
BUILD_006 = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\006"
TOOL = os.path.join(REPO, "scripts", "read_gaea_graph.py")

# This proof needs the local Gaea project; if it is absent, say so cleanly
# rather than crash with a FileNotFoundError traceback on the first open().
if not os.path.isfile(SRC):
    print("COULD NOT LOOK: source .terrain not found: %s" % SRC)
    print("This proof harness needs the local AlpineLab_v1 Gaea project.")
    sys.exit(2)
if not os.path.isfile(TOOL):
    print("COULD NOT LOOK: read_gaea_graph.py not found: %s" % TOOL)
    sys.exit(2)

tmp = tempfile.mkdtemp(prefix="gaea_probe_")
fails = []


def run(path, *extra):
    return subprocess.run(
        [sys.executable, TOOL, "--project", path] + list(extra),
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=REPO)


def mutate(label, fn):
    with open(SRC, encoding="utf-8") as fh:
        d = json.load(fh)
    before = json.dumps(d, sort_keys=True)
    try:
        fn(d)
    except (KeyError, IndexError, TypeError) as exc:
        # The fixture drifted from the node ids / ports these faults target;
        # that is a BROKEN control, not a passed one.
        print("  FIXTURE DRIFT  %-48s %s: %s"
              % (label, type(exc).__name__, exc))
        fails.append("%s (fixture drift)" % label)
        return None
    if json.dumps(d, sort_keys=True) == before:
        # A fault that changed nothing leaves the graph valid, the gate would
        # (correctly) ACCEPT it, and the control would prove nothing.
        print("  NO-OP FAULT    %-48s (injected fault changed nothing)" % label)
        fails.append("%s (no-op fault)" % label)
        return None
    p = os.path.join(tmp, "m.terrain")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    return p


def expect(label, path, args, want_code):
    if path is None:
        return          # mutate() already recorded the failure
    r = run(path, *args)
    ok = (r.returncode == want_code)
    print("  rc=%d want=%d  %-6s %s"
          % (r.returncode, want_code, "OK" if ok else "FAIL", label))
    if not ok:
        # Show the tool's own tail so a wrong-reason refusal is diagnosable.
        fails.append("%s (rc=%d want=%d)" % (label, r.returncode, want_code))
        tail = (r.stdout or "").strip()[-300:]
        if tail:
            print("      " + tail.replace("\n", "\n      "))


print("POSITIVE CONTROL — the shipped graph must be ACCEPTED (rc 0)")
expect("shipped graph, all gates", SRC,
       ["--check-refs", "--check-spec", "--against-build", BUILD_006], 0)

print()
print("NEGATIVE CONTROLS — each must be REFUSED with its gate's exit code")

# 1. A save node disabled in the GUI -> --check-spec disagreement (rc 4).
def disable_erosion(d):
    t = d["Assets"]["$values"][0]["Terrain"]
    t["Nodes"]["654"]["SaveDefinition"]["IsEnabled"] = False
expect("a save node DISABLED (a map would be omitted)",
       mutate("disable save node", disable_erosion), ["--check-spec"], 4)

# 2. A save node removed entirely -> --check-spec disagreement (rc 4).
def drop_snowmask(d):
    t = d["Assets"]["$values"][0]["Terrain"]
    del t["Nodes"]["849"]["SaveDefinition"]
expect("a save definition REMOVED",
       mutate("remove save def", drop_snowmask), ["--check-spec"], 4)

# 3. An output port stops exporting -> --check-spec disagreement (rc 4).
def unexport_flow(d):
    t = d["Assets"]["$values"][0]["Terrain"]
    for p in t["Nodes"]["654"]["Ports"]["$values"]:
        if p.get("Name") == "Flow":
            p["IsExporting"] = None
expect("an output port stops EXPORTING",
       mutate("unexport flow", unexport_flow), ["--check-spec"], 4)

# 4. A dangling $ref -> --check-refs failure (rc 3).
def break_ref(d):
    t = d["Assets"]["$values"][0]["Terrain"]
    t["Nodes"]["654"]["Ports"]["$values"][0]["Parent"]["$ref"] = "99999"
expect("a DANGLING $ref (careless structural edit)",
       mutate("break $ref", break_ref), ["--check-refs"], 3)

# 5. The prediction rule vs a build directory that does not match -> rc 6.
expect("prediction vs a build MISSING files", SRC,
       ["--against-build", tmp], 6)

shutil.rmtree(tmp, ignore_errors=True)
print()
print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
