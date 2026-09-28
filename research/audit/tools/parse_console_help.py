"""parse_console_help.py -- ConsoleHelp.html -> cvars_5.8_live.txt.

READ-ONLY. Audit item 4's second half: turn the engine's own dump into
a flat, greppable list the desk can check a name against.

The dump is a JS array literal inside the page, one record per line:

    {name: "r.ScreenPercentage", help:"...", type:"Var"},

`type` is Var / Cmd / Exec. Only Var entries are console VARIABLES; the
other two are commands, and conflating them is how a "cvar" that is
really an exec command gets written into a profile and silently does
nothing.

⛔ THE HELP TEXT IS NOT PARSED. It is JS-escaped prose containing
newlines, quotes and apostrophes, and a regex that tried to span it
would swallow the next record. Only the NAME and the TYPE are taken,
from the start of each record, which is the part with no ambiguity.
"""
import io
import os
import re
import sys

RE_ENTRY = re.compile(r'^\{name:\s*"([^"]+)",.*?type:"(Var|Cmd|Exec)"\},?\s*$')
# A record whose help text carries a literal newline spills onto later
# lines; those continuation lines never start with `{name:`, so anchoring
# at the start of the line is what makes name extraction unambiguous.
RE_NAME_ONLY = re.compile(r'^\{name:\s*"([^"]+)"')
RE_TYPE_TAIL = re.compile(r'type:"(Var|Cmd|Exec)"\},?\s*$')


def main(src, dst):
    rows, pending, n_lines = [], None, 0
    with io.open(src, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            n_lines += 1
            m = RE_ENTRY.match(line)
            if m:
                rows.append((m.group(1), m.group(2)))
                pending = None
                continue
            m = RE_NAME_ONLY.match(line)
            if m:
                # Opened a record whose help text wraps. Hold the name
                # until its type tail turns up.
                pending = m.group(1)
                t = RE_TYPE_TAIL.search(line)
                if t:
                    rows.append((pending, t.group(1)))
                    pending = None
                continue
            if pending is not None:
                t = RE_TYPE_TAIL.search(line)
                if t:
                    rows.append((pending, t.group(1)))
                    pending = None

    by_type = {}
    for _n, t in rows:
        by_type[t] = by_type.get(t, 0) + 1
    seen, uniq = set(), []
    for n, t in rows:
        if (n, t) in seen:
            continue
        seen.add((n, t))
        uniq.append((n, t))
    uniq.sort(key=lambda r: (r[1], r[0].lower()))

    with io.open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Live console enumeration -- UE 5.8.1-56057345+++UE5+"
                 "Release-5.8\n")
        fh.write("# Source: the engine's own `Help` dump, %s\n" % src)
        fh.write("# Parsed by research/audit/tools/parse_console_help.py\n")
        fh.write("#\n")
        fh.write("# type Var  = console VARIABLE (settable, readable)\n")
        fh.write("# type Cmd  = console command  -- NOT a variable\n")
        fh.write("# type Exec = exec command     -- NOT a variable\n")
        fh.write("# Writing a Cmd/Exec name into a profile as if it were a\n"
                 "# variable sets nothing and reports nothing.\n")
        fh.write("#\n")
        fh.write("# lines scanned %d   records %d   unique %d\n"
                 % (n_lines, len(rows), len(uniq)))
        for t in sorted(by_type):
            fh.write("# %-5s %d\n" % (t, by_type[t]))
        fh.write("#\n")
        for n, t in uniq:
            fh.write("%-5s %s\n" % (t, n))

    print("records %d   unique %d   %s"
          % (len(rows), len(uniq),
             "  ".join("%s=%d" % kv for kv in sorted(by_type.items()))))
    print("%s  %d bytes" % (dst, os.path.getsize(dst)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
