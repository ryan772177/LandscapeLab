"""city_organic.py -- ORGANIC street network + street-fronted plots for plan_city (layout "organic", 2026-10-10).

Ryan 2026-10-10 (option a): the ring-and-spoke lattice reads as programmatic from a ridge
(_verify/lookdev/townkit_game01/ridge_town_e_crop.png). This replaces only the LAYOUT; plan_city keeps the building
gate, heights, roof fit, landmark, gates, stamping and output, so every consumer reads the plan unchanged.
Every tuning value is read from recipes/city.json plan.organic (pipeline rule 2); nothing below is a scene constant.

METHOD (offline, seeded, deterministic):
  1. COST FIELD: a grid of cell_m over the town extent, ground from the heightmap. A step steeper than the street
     grade bar (plan.max_street_slope_deg) on the 3x3-smoothed field is impassable; water (the Brief-4 water
     exclusion mask -- REQUIRED, refused if absent) and cells outside the extent are impassable. Step cost =
     length * (1 + slope_cost_k * (grade / bar)^2).
  2. MAIN ROADS: A* from the plaza to main_roads GATES on the rim (rim_radius_frac of the extent), one per angular
     sector, each at the gentlest of rim_samples candidates within rim_sector_span of its sector. Road cells cost
     road_reuse_discount x, so later roads MERGE into earlier ones -- trunks and branches instead of radii.
  3. LANES then ALLEYS from a point on the network (weighted exp(-d / branch_centre_bias_m) toward the plaza) to a
     reachable target lane_len_m / alley_len_m away; only the NEW cells of a path become street.
  4. SEGMENTS: each new polyline is cut into straight pieces <= segment_max_m, width by tier, kind main/lane/alley,
     carrying chain/seq (which polyline, which piece). Every piece must pass plan_city's street gate (grade + cut/fill
     on the REAL heightmap) AND stay off water along its whole length (physical tests only) -- tested as each run is
     ADDED, before it becomes road. A failing piece gets a local DETOUR between its own ends with its interior cells
     blocked (up to max_detours per run); with no detour the run is TRUNCATED at that piece's start, so a failing
     piece never becomes street and nothing else in the network moves. Final pieces are re-checked (REFUSE).
  5. PLOTS (after plan_city prunes the network to its plaza component): along every SURVIVING chain of straight
     pieces, both sides, lot after lot -- frontage = the footprint width along the piece, set back setback_m from
     the road edge, facing it (house local -Y toward the road; the plan records door_side 0). Gaps frontage_gap_m,
     sometimes an open lot. Each candidate passes plan_city's SAME building gate plus an ORIENTED clearance test:
     street_clearance_m from every street piece, buildings.gap_min_m from every house, outside every square.
  6. SQUARES: up to `squares` lane/alley junctions become open squares of square_radius_m, at least
     more than square_min_from_plaza_edge_m beyond the plaza edge and square_min_spacing_m apart.
"""
import heapq
import math
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATER_REL = "encounters/alpine_8k_water_exclusion.npz"
WATER = os.path.join(REPO, *WATER_REL.split("/"))


class Grid:
    def __init__(self, T, cx0, cy0, R_cm, cell_cm, bar_deg, k, discount):
        self.cx0, self.cy0, self.R, self.c = cx0, cy0, R_cm, cell_cm
        self.n = int(2 * R_cm / cell_cm) + 1
        ax = cx0 - R_cm + np.arange(self.n) * cell_cm
        ay = cy0 - R_cm + np.arange(self.n) * cell_cm
        X, Y = np.meshgrid(ax, ay)              # [j, i]: j = y index, i = x index
        self.X, self.Y = X, Y
        self.Z = np.asarray(T.z_cm(X, Y), dtype=np.float64)
        # Step grades are judged on a 3x3-cell box mean (12 m at 4 m cells): the street gate measures END-TO-END
        # grade over a ~15 m segment, and per-4 m raw relief failed 2 of 5 main roads on micro-relief alone
        # (2026-10-10 first run). The segment gates still run on the real heightmap afterwards.
        Zp = np.pad(self.Z, 1, mode="edge")
        self.Zs = sum(Zp[1 + dj:1 + dj + self.Z.shape[0], 1 + di:1 + di + self.Z.shape[1]]
                      for dj in (-1, 0, 1) for di in (-1, 0, 1)) / 9.0
        self.ok = np.hypot(X - cx0, Y - cy0) <= R_cm
        # the water mask is REQUIRED (audit 2026-10-10 F10): skipping it silently would route roads through lakes
        if not os.path.isfile(WATER):
            raise SystemExit("REFUSE: water exclusion mask %s missing -- organic roads would ignore water" % WATER)
        w = np.load(WATER)
        self.M, (self.wox, self.woy), self.wc = w["mask"], w["origin_cm"], float(w["cell_m"][0]) * 100.0
        self.ok &= ~self.wet(X, Y)
        self.tanbar = math.tan(math.radians(bar_deg))
        self.k, self.disc = k, discount
        self.road = np.zeros_like(self.ok)

    def wet(self, x, y):
        wi = np.clip(((np.asarray(x) - self.wox) // self.wc).astype(int), 0, self.M.shape[1] - 1)
        wj = np.clip(((np.asarray(y) - self.woy) // self.wc).astype(int), 0, self.M.shape[0] - 1)
        return self.M[wj, wi]

    def ij(self, x, y):
        return (int(round((y - (self.cy0 - self.R)) / self.c)), int(round((x - (self.cx0 - self.R)) / self.c)))

    def inside(self, c):
        return 0 <= c[0] < self.n and 0 <= c[1] < self.n

    def xy(self, j, i):
        return float(self.X[j, i]), float(self.Y[j, i])

    def path(self, start, goal):
        """A* over 8-neighbours on the smoothed field; None if unreachable. start/goal are (j, i)."""
        n, c, Z = self.n, self.c, self.Zs
        if not (self.ok[start] and self.ok[goal]):
            return None
        gi, gj = goal[1], goal[0]
        hmin = self.disc

        def h(j, i):
            return math.hypot(i - gi, j - gj) * c * hmin
        best = {start: 0.0}
        prev = {}
        pq = [(h(*start), 0.0, start)]
        nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        while pq:
            f, g, cur = heapq.heappop(pq)
            if cur == goal:
                out = [cur]
                while cur in prev:
                    cur = prev[cur]
                    out.append(cur)
                return out[::-1]
            if g > best.get(cur, 1e30):
                continue
            j, i = cur
            for dj, di in nb:
                jj, ii = j + dj, i + di
                if not (0 <= jj < n and 0 <= ii < n) or not self.ok[jj, ii]:
                    continue
                L = c * (1.4142135623730951 if dj and di else 1.0)
                grade = abs(Z[jj, ii] - Z[j, i]) / L
                if grade > self.tanbar:
                    continue
                step = L * (1.0 + self.k * (grade / self.tanbar) ** 2)
                if self.road[jj, ii]:
                    step *= self.disc
                ng = g + step
                if ng < best.get((jj, ii), 1e30):
                    best[(jj, ii)] = ng
                    prev[(jj, ii)] = cur
                    heapq.heappush(pq, (ng + h(jj, ii), ng, (jj, ii)))
        return None


def _new_runs(cells, road):
    """The parts of a cell path NOT already road, each extended one cell back onto the road it leaves from and
    one cell forward onto the road it joins, so new streets touch the network they branch from."""
    runs, cur = [], []
    for k, c in enumerate(cells):
        if road[c]:
            if cur:
                cur.append(c)
                runs.append(cur)
                cur = []
        else:
            if not cur and k > 0:
                cur.append(cells[k - 1])
            cur.append(c)
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) >= 2]


def _cut(points, i0, i1, seg_max):
    """Vertices i0..i1 of a polyline (world xy) -> straight pieces <= ~seg_max (cm), as vertex index pairs."""
    out = []
    s = i0
    for k in range(i0 + 1, i1 + 1):
        if math.hypot(points[k][0] - points[s][0], points[k][1] - points[s][1]) >= seg_max:
            out.append((s, k))
            s = k
    if s < i1:
        out.append((s, i1))
    return out


def obb(cx, cy, sx, sy, yaw_deg):
    a = math.radians(yaw_deg)
    return (cx, cy, sx * 0.5, sy * 0.5, math.cos(a), math.sin(a))


def obb_overlap(A, B, gap=0.0):
    """Separating-axis test for two oriented rectangles (centre, half-sizes, cos, sin), grown by gap/2 each."""
    ax, ay, ahx, ahy, ac, as_ = A
    bx, by, bhx, bhy, bc, bs = B
    ahx += gap * 0.5; ahy += gap * 0.5; bhx += gap * 0.5; bhy += gap * 0.5
    dx, dy = bx - ax, by - ay
    for ux, uy in ((ac, as_), (-as_, ac), (bc, bs), (-bs, bc)):
        ra = ahx * abs(ac * ux + as_ * uy) + ahy * abs(-as_ * ux + ac * uy)
        rb = bhx * abs(bc * ux + bs * uy) + bhy * abs(-bs * ux + bc * uy)
        if abs(dx * ux + dy * uy) > ra + rb:
            return False
    return True


def seg_ends(s):
    a = math.radians(s["yaw_deg"])
    h = s["len_cm"] * 0.5
    x, y = s["loc_cm"][0], s["loc_cm"][1]
    return (x - h * math.cos(a), y - h * math.sin(a)), (x + h * math.cos(a), y + h * math.sin(a))


def streets(T, pl, cx0, cy0, R_cm, rng, street_pass, street_seat, obstacles=()):
    """-> (segments in plan_city's street schema + chain/seq, junctions, stats). See the module docstring.
    obstacles: [(cx, cy, sx, sy, yaw_deg)] footprints no street may touch (the landmark; LESSONS 2026-10-10f) --
    their cells (grown by the widest half-street + clearance) are impassable to A*, and every straight piece's slab
    is tested against them as a physical test."""
    o = pl["organic"]
    G = Grid(T, cx0, cy0, R_cm, float(o["cell_m"]) * 100.0, float(pl.get("max_street_slope_deg", 8.0)),
             float(o["slope_cost_k"]), float(o["road_reuse_discount"]))
    widths = {k: float(v) * 100.0 for k, v in o["widths_m"].items()}
    seg_max = float(o["segment_max_m"]) * 100.0
    rim_frac = float(o["rim_radius_frac"])
    rim_samples = int(o["rim_samples"])
    span0, span1 = [float(v) for v in o["rim_sector_span"]]
    min_cells = int(o["min_branch_cells"])
    max_detours = int(o["max_detours"])
    rim_win = int(o["rim_roughness_halfwin_cells"])     # rim-gate roughness window: (2*rim_win + 1)^2 cells
    clearance = float(o["street_clearance_m"]) * 100.0
    obs = [obb(*ob) for ob in obstacles]
    grow = max(widths.values()) * 0.5 + clearance
    for ox, oy, ohx, ohy, oc, os_ in obs:
        lx = (G.X - ox) * oc + (G.Y - oy) * os_
        ly = -(G.X - ox) * os_ + (G.Y - oy) * oc
        G.ok &= ~((np.abs(lx) <= ohx + grow) & (np.abs(ly) <= ohy + grow))
    centre = G.ij(cx0, cy0)
    if not G.ok[centre]:
        raise SystemExit("REFUSE: the plaza centre is not on passable ground for the organic grid")
    G.road[centre] = True
    polylines, junctions = [], []
    st = {"pieces_failed": 0, "why": {}, "detours": 0, "runs_truncated": 0, "runs_dropped": 0, "cells_blocked": 0,
          "truncated_by_kind": {}}

    def piece_why(ax, ay, bx, by, w):
        """None if the straight piece (slab width w) passes, else why: 'water' / 'landmark' / 'gate'. PHYSICAL tests
        only: blocked cells are a routing device that steers A*, and testing chords against them made every detour
        cause the next failure (LESSONS 2026-10-10d: 27 of 37 failures, 3 of 5 main roads truncated)."""
        L = math.hypot(bx - ax, by - ay)
        if obs:
            slab = obb(0.5 * (ax + bx), 0.5 * (ay + by), L, w, math.degrees(math.atan2(by - ay, bx - ax)))
            if any(obb_overlap(slab, O, clearance) for O in obs):
                return "landmark"
        # the straight piece must ALSO stay off water along its length (audit F10):
        # a 15 m chord can cut the corner of a lake the cell path went round
        t = np.linspace(0, 1, max(3, int(L / G.c) + 2))
        xs, ys = ax + (bx - ax) * t, ay + (by - ay) * t
        if G.wet(xs, ys).any():
            return "water"
        if not street_pass(0.5 * (ax + bx), 0.5 * (ay + by), math.degrees(math.atan2(by - ay, bx - ax)), L):
            return "gate"
        return None

    def repair(run, w):
        """Gate a new run piece by piece BEFORE it becomes road -> (cells, [(i0, i1)] pieces), every piece passing.
        A failing piece gets a DETOUR between its own two ends with its interior cells blocked (local: nothing
        else moves). A piece with no interior, no detour, or past max_detours TRUNCATES the run at its start --
        the street ends there. LESSONS 2026-10-10c: regenerating the whole network per failure never converged
        (every branch depends on the whole road set), and re-cutting a failing piece down to one 4 m cell step
        turned the street gate into a roughness test (the 2026-08-25 lesson, one level down)."""
        run = list(run)
        done = []
        start = 0
        detours = 0
        # a run that leaves or joins the network does so at a road CELL, which can sit metres off the parent's
        # straight centreline; its end is SNAPPED onto the nearest placed centreline so the slabs really touch
        # (audit F9's per-pair join found 102 of 335 pieces stranded at such junctions once the 7 m tolerance
        # stopped hiding the gap)
        s0 = snap(run[0]) if G.road[run[0]] else None
        end_cell = run[-1] if G.road[run[-1]] else None
        s1 = snap(end_cell) if end_cell is not None else None
        while start < len(run) - 1:
            pts = [G.xy(*c) for c in run]
            if s0:
                pts[0] = s0
            if s1 and run[-1] == end_cell:
                pts[-1] = s1
            bad = None
            for i0, i1 in _cut(pts, start, len(run) - 1, seg_max):
                why = piece_why(pts[i0][0], pts[i0][1], pts[i1][0], pts[i1][1], w)
                if why is None:
                    done.append((i0, i1))
                    start = i1
                    continue
                bad = (i0, i1, why)
                break
            if bad is None:
                break
            i0, i1, why = bad
            st["pieces_failed"] += 1
            st["why"][why] = st["why"].get(why, 0) + 1
            path = None
            if i1 - i0 >= 2 and detours < max_detours:
                for c in run[i0 + 1:i1]:
                    if c != centre and not G.road[c] and G.ok[c]:
                        G.ok[c] = False
                        st["cells_blocked"] += 1
                path = G.path(run[i0], run[i1])
                detours += 1
                st["detours"] += 1
            if not path:
                run = run[:i0 + 1]
                st["runs_truncated"] += 1
                break
            run = run[:i0] + path + run[i1 + 1:]
        pts = [G.xy(*c) for c in run]
        if s0:
            pts[0] = s0
        if s1 and run[-1] == end_cell:
            pts[-1] = s1
        return run, pts, done

    placed = []     # (ax, ay, bx, by) of every accepted piece, for snapping

    def snap(cell):
        x, y = G.xy(*cell)
        best = None
        for ax, ay, bx, by in placed:
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / max(dx * dx + dy * dy, 1e-9)))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(x - px, y - py)
            if best is None or d < best[0]:
                best = (d, (px, py))
        return best[1] if best else None

    def add(kind, cells):
        added = False
        for run in _new_runs(cells, G.road):
            t0 = st["runs_truncated"]
            run, pts, done = repair(run, widths[kind])
            if st["runs_truncated"] > t0:
                st["truncated_by_kind"][kind] = st["truncated_by_kind"].get(kind, 0) + 1
            if not done:
                st["runs_dropped"] += 1
                continue
            polylines.append((kind, widths[kind], pts, done))
            junctions.append((kind, pts[0]))
            placed.extend((pts[a][0], pts[a][1], pts[b][0], pts[b][1]) for a, b in done)
            for c in run[:done[-1][1] + 1]:
                G.road[c] = True
            added = True
        return added

    nm = int(o["main_roads"])
    off = rng.uniform(0, 2 * math.pi)
    rim = []
    for sct in range(nm):
        best = None
        for t in np.linspace(0, 1, rim_samples, endpoint=False):
            th = off + 2 * math.pi * (sct + span0 + span1 * t) / nm
            x, y = cx0 + rim_frac * R_cm * math.cos(th), cy0 + rim_frac * R_cm * math.sin(th)
            j, i = G.ij(x, y)
            if not G.inside((j, i)) or not G.ok[j, i]:
                continue
            nbz = G.Z[max(0, j - rim_win):j + rim_win + 1, max(0, i - rim_win):i + rim_win + 1]
            rough = float(nbz.max() - nbz.min())
            if best is None or rough < best[0]:
                best = (rough, (j, i))
        if best:
            rim.append(best[1])
    n_main = 0
    for g in rim:
        p = G.path(centre, g)
        if p and add("main", p):
            n_main += 1

    def branch(kind, count, len_rng):
        made = 0
        tries = 0
        bias = float(o["branch_centre_bias_m"]) * 100.0
        while made < count and tries < count * int(o["branch_tries_per_target"]):
            tries += 1
            road_cells = np.argwhere(G.road)
            # branch from near the plaza more often (weight exp(-d / branch_centre_bias_m)): a uniform pick
            # strung the town out as a ribbon along one trunk with a thin core (2026-10-10 plan_organic4)
            dd = np.hypot(G.X[road_cells[:, 0], road_cells[:, 1]] - cx0,
                          G.Y[road_cells[:, 0], road_cells[:, 1]] - cy0)
            wts = np.exp(-dd / bias) if bias > 0 else np.ones(len(dd))
            j0, i0 = road_cells[int(rng.choice(len(road_cells), p=wts / wts.sum()))]
            ang = rng.uniform(0, 2 * math.pi)
            L = rng.uniform(*len_rng) * 100.0
            x0, y0 = G.xy(j0, i0)
            j1, i1 = G.ij(x0 + L * math.cos(ang), y0 + L * math.sin(ang))
            if not G.inside((j1, i1)) or not G.ok[j1, i1] or G.road[j1, i1]:
                continue
            p = G.path((int(j0), int(i0)), (j1, i1))
            if p and len(p) >= min_cells and add(kind, p):
                made += 1
        return made
    n_lane = branch("lane", int(o["lanes"]), [float(v) for v in o["lane_len_m"]])
    n_alley = branch("alley", int(o["alleys"]), [float(v) for v in o["alley_len_m"]])

    segs = []
    for chain, (kind, w, pts, done) in enumerate(polylines):
        for seq, (i0, i1) in enumerate(done):
            (ax, ay), (bx, by) = pts[i0], pts[i1]
            mx, my = 0.5 * (ax + bx), 0.5 * (ay + by)
            L = math.hypot(bx - ax, by - ay)
            yaw = math.degrees(math.atan2(by - ay, bx - ax))
            # every piece was gated in repair(); this re-asks the same physical questions on the final geometry
            if piece_why(ax, ay, bx, by, w) is not None:
                raise SystemExit("REFUSE: organic street piece chain %d seq %d fails its gate after repair" % (chain, seq))
            pitch, roll = street_seat(T, mx, my, yaw, L, w)
            segs.append({"kind": kind, "chain": chain, "seq": seq,
                         "loc_cm": [round(mx, 1), round(my, 1), round(float(T.z_cm(mx, my)), 1)],
                         "yaw_deg": round(yaw, 2), "pitch_deg": pitch, "roll_deg": roll,
                         "len_cm": round(L, 1), "width_cm": w})
    stats = dict({"main_roads": n_main, "gates": len(rim), "lanes": n_lane, "alleys": n_alley,
                  "polylines": len(polylines), "segments": len(segs)}, **st)
    return segs, junctions, stats


def chains(segs):
    """Pruned segments -> straight-piece chains: [(kind, width_cm, [(x, y), ...])], split where a piece is missing."""
    by = {}
    for s in segs:
        by.setdefault(s["chain"], []).append(s)
    out = []
    for k in sorted(by):
        run = []
        for s in sorted(by[k], key=lambda s: s["seq"]):
            a, b = seg_ends(s)
            if run and (s["seq"] != run[-1][0] + 1):
                out.append(run)
                run = []
            run.append((s["seq"], s["kind"], s["width_cm"], a, b))
        if run:
            out.append(run)
    res = []
    for run in out:
        pts = [run[0][3]] + [r[4] for r in run]
        res.append((run[0][1], run[0][2], pts))
    return res


def plots(pl, bd, segs, junctions, obstacles, cx0, cy0, plaza_cm, rng, draw_size, try_building):
    """Street-fronted lots along the SURVIVING (pruned) straight-piece chains, both sides. try_building(bx, by, sx,
    sy, yaw, d, extra, fields) runs plan_city's gate; extra(...) returns None or a rejection reason
    ('in_square' / 'on_landmark' / 'on_street' / 'overlap'). obstacles as in streets(), kept buildings.gap_min_m
    clear. -> (squares, stats)."""
    o = pl["organic"]
    sq_r = float(o["square_radius_m"]) * 100.0
    sq_plaza = plaza_cm + float(o["square_min_from_plaza_edge_m"]) * 100.0
    sq_space = float(o["square_min_spacing_m"]) * 100.0
    # only junctions that are still the start of a SURVIVING piece (the pruner may have removed the branch)
    starts = [seg_ends(s)[0] for s in segs if s["seq"] == 0]
    js = [j for j in junctions if j[0] in ("lane", "alley")
          and any(abs(j[1][0] - a[0]) < 5.0 and abs(j[1][1] - a[1]) < 5.0 for a in starts)]
    squares = []
    for k in range(min(int(o["squares"]), len(js))):
        kind, (x, y) = js[int(rng.integers(0, len(js)))]
        if math.hypot(x - cx0, y - cy0) > sq_plaza and all(math.hypot(x - s[0], y - s[1]) > sq_space
                                                            for s in squares):
            squares.append((round(x, 1), round(y, 1), sq_r))
    street_obbs = [obb(s["loc_cm"][0], s["loc_cm"][1], s["len_cm"], s["width_cm"], s["yaw_deg"]) for s in segs]
    house_obbs = []
    obs = [obb(*ob) for ob in obstacles]
    clearance = float(o["street_clearance_m"]) * 100.0
    gap_house = float(bd["gap_min_m"]) * 100.0              # ONE building spacing for both layouts (audit F11)
    min_len = float(o["min_frontage_chain_m"]) * 100.0
    sb0, sb1 = [float(v) * 100.0 for v in o["setback_m"]]
    g0, g1 = [float(v) * 100.0 for v in o["frontage_gap_m"]]
    ol0, ol1 = [float(v) * 100.0 for v in o["open_lot_m"]]
    p_open = float(o["open_lot_chance"])
    stats = {"candidates": 0, "accepted": 0}

    def extra(bx, by, sx, sy, yaw):
        if any(math.hypot(bx - s[0], by - s[1]) < s[2] + 0.5 * max(sx, sy) for s in squares):
            return "in_square"
        B = obb(bx, by, sx, sy, yaw)
        if any(obb_overlap(B, O, gap_house) for O in obs):
            return "on_landmark"
        if any(obb_overlap(B, S, clearance) for S in street_obbs):
            return "on_street"
        if any(obb_overlap(B, H, gap_house) for H in house_obbs):
            return "overlap"
        return None

    for kind, w, pts in chains(segs):
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        total = cum[-1]
        if total < min_len:
            continue

        def at(s):
            # position AND direction from the straight piece the house fronts (audit F5: the raw 4 m grid path
            # snapped house angles to 45 deg steps and up to ~22 deg off the drawn street)
            k = max(0, min(len(pts) - 2, int(np.searchsorted(cum, s) - 1)))
            seg = max(cum[k + 1] - cum[k], 1e-6)
            t = (s - cum[k]) / seg
            x = pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t
            y = pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t
            return x, y, math.degrees(math.atan2(pts[k + 1][1] - pts[k][1], pts[k + 1][0] - pts[k][0]))
        for side in (1, -1):
            s = rng.uniform(0, g1)
            while s < total:
                if rng.random() < p_open:
                    s += rng.uniform(ol0, ol1)
                    continue
                sx, sy = draw_size()          # sx along the road (frontage), sy depth
                if s + sx > total:
                    break
                x, y, yaw = at(s + sx * 0.5)
                nx, ny = -math.sin(math.radians(yaw)) * side, math.cos(math.radians(yaw)) * side
                off = w * 0.5 + rng.uniform(sb0, sb1) + sy * 0.5
                bx, by = x + nx * off, y + ny * off
                d = math.hypot(bx - cx0, by - cy0)
                stats["candidates"] += 1
                hyaw = yaw if side > 0 else yaw + 180.0      # local -Y faces the road either side
                if try_building(bx, by, sx, sy, hyaw, d, extra, {"door_side": 0, "fronts": kind}):
                    house_obbs.append(obb(bx, by, sx, sy, hyaw))
                    stats["accepted"] += 1
                s += sx + rng.uniform(g0, g1)
    return squares, stats
