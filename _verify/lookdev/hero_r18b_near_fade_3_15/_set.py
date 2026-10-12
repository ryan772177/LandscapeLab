import io, json, re, sys
p = "recipes/lookdev.json"
r = json.load(io.open(p, encoding="utf-8"))
log = []
for item in sys.argv[2:]:
    path, _, raw = item.partition("=")
    # REFUSE a path whose ROOT is not already a recipe key. Two -Set values
    # passed through `pwsh -File` arrive as ONE string ("a=1','b=2"), and
    # this setter used to create the junk key "'material" from it (hero
    # rounds 1 and 11, LESSONS 2026-10-03f). Pass several values as
    # separate -Set flags in one in-process call, or one value per run.
    if path.split(".")[0].split(":")[0] not in r or "'" in item:
        raise SystemExit("REFUSED -Set item %r: unknown recipe root or a "
                         "quote in it -- two values collapsed into one "
                         "string? Pass one value per -Set." % item)
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    node = r
    parts = path.split(".")
    for i, part in enumerate(parts):
        m = re.match(r"^(\w+):(\w+)$", part)
        last = i == len(parts) - 1
        if m:
            lst = node[m.group(1)]
            node = next(x for x in lst if x.get("name") == m.group(2))
            if last:
                raise SystemExit("path ends on a list selector: " + path)
            continue
        if last:
            old = node.get(part, "<absent>")
            if val == "__DELETE__":
                node.pop(part, None)
            else:
                node[part] = val
            log.append("%s: %r -> %r" % (path, old, val))
        else:
            node = node.setdefault(part, {})
json.dump(r, io.open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
io.open(sys.argv[1], "w", encoding="utf-8").write("\n".join(log) + "\n")
print("\n".join(log))
