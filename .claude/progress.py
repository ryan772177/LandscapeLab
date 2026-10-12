"""Task progress bar for the Claude Code status line.

Two roles, one file:

  WRITER (Claude calls this as a task advances):
      python .claude/progress.py start "Hero round 6" 5   # task, total steps
      python .claude/progress.py step "build material"    # one step done
      python .claude/progress.py done                     # task finished
      python .claude/progress.py clear                    # hide the bar

  STATUS LINE (Claude Code calls this; settings statusLine.command):
      python .claude/progress.py statusline

State lives in .claude/progress.json (gitignored). The ETA is the mean
time per completed step times the steps left -- a plain extrapolation,
shown as "ETA ?" until one step has finished, because a guess from zero
data reads like a measurement.
"""
import io
import json
import os
import sys
import time

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "progress.json")
WIDTH = 20


def _load():
    try:
        with io.open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(s):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f)
    os.replace(tmp, STATE)


def _fmt(sec):
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%dh%02dm" % (h, m)
    if m:
        return "%dm%02ds" % (m, s)
    return "%ds" % s


def render(s, now=None):
    now = time.time() if now is None else now
    total = max(1, int(s["total"]))
    done = min(total, int(s["done"]))
    frac = done / float(total)
    fill = int(round(frac * WIDTH))
    bar = "█" * fill + "░" * (WIDTH - fill)
    elapsed = now - s["started"]
    if s.get("finished"):
        tail = "done in " + _fmt(s["finished"] - s["started"])
    elif done == 0:
        tail = "elapsed %s · ETA ?" % _fmt(elapsed)
    else:
        eta = elapsed / done * (total - done)
        tail = "elapsed %s · ETA %s" % (_fmt(elapsed), _fmt(eta))
    label = s.get("label") or ""
    if label:
        label = " · " + label
    return "%s %s %d/%d %3d%%%s · %s" % (
        s["task"], bar, done, total, int(frac * 100), label, tail)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "statusline":
        try:
            sys.stdin.read()          # Claude Code session JSON; unused
        except Exception:
            pass
        s = _load()
        print(render(s) if s else "")
        return 0
    if cmd == "start":
        if len(argv) != 3 or int(argv[2]) < 1:
            print("usage: start <task> <total_steps>=1+")
            return 2
        _save({"task": argv[1], "total": int(argv[2]), "done": 0,
               "label": "", "started": time.time(), "finished": None})
    elif cmd in ("step", "done", "total"):
        s = _load()
        if s is None:
            print("no task started")
            return 2
        if cmd == "step":
            s["done"] = min(int(s["total"]), int(s["done"]) + 1)
            s["label"] = argv[1] if len(argv) > 1 else ""
        elif cmd == "total":          # re-scope mid-task
            s["total"] = max(int(s["done"]), int(argv[1]))
        else:
            s["done"] = int(s["total"])
            s["label"] = ""
            s["finished"] = time.time()
        _save(s)
    elif cmd == "clear":
        if os.path.exists(STATE):
            os.replace(STATE, STATE + ".last")
        return 0
    else:
        print("unknown command: " + cmd)
        return 2
    print(render(_load()))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
