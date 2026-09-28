"""reachability.py -- THE ONE answer to "can you get there".

    python scripts/reachability.py --selftest
    python scripts/reachability.py --report

WHY THIS EXISTS (class-level promotion, non-negotiable 4a, ruled 2026-08-26).

"Per-element gates do not compose into whole-traversability" reached its SECOND
tool in one week:

  1. plan_city gated each STREET SEGMENT on its own slope. Every segment passed
     and the network came out as 155 disconnected pieces with the town centre
     stranded in a 22-segment fragment.
  2. plan_city's TOWN EXTENT was drawn by per-structure cut/fill and pad-slope
     gates. Every building passed and 185 of 838 streets and 50 of 303
     buildings are unreachable from the town's own plaza.

And a third was already forming: plan_encounters had grown its OWN private
`near_reachable` reading the sidecar directly. Non-negotiable 4a promotes on the
second, without waiting for the third. **Individually-patched reachability
checks in a planner are a REJECTED pattern from here forward.**

=====================================================================
WHAT REACHABILITY IS, AND WHAT IT IS NOT
=====================================================================
There are TWO different questions and conflating them is the defect this module
exists to prevent:

  PROJECTION   "is there navmesh underfoot at B?"      -> a polygon exists
  REACHABILITY "can an agent walk from A to B?"        -> a PATH exists

The town's streets project 838/838 and reach 653/838. Only the path query
separates them, and every tool that has confused them has produced a plausible
wrong number.

=====================================================================
THE AUTHORED REGION IS DATA, AND IT IS BOUND
=====================================================================
Reachability is measured IN THE EDITOR against the BUILT navmesh (collision-
derived) and written to a sidecar. That sidecar is true for exactly ONE navmesh
build, so it records what it was measured against -- agent, resident chunk
count, anchor, query extent -- and this module REFUSES a sidecar whose binding
does not match the caller's declared agent.

A live pointer would make "what is reachable" answerable only by re-measuring;
a bound artefact is a fact on disk (non-negotiable 20).

=====================================================================
THE OFFLINE MODEL IS A PREFILTER, NEVER A GATE
=====================================================================
`offline_component_mask` builds a walkable mask from the HEIGHTMAP and labels
8-connected components. It is OPTIMISTIC -- it passed five encounters the built
navmesh then refused, at two different agents, because an 8 m gradient smooths a
1 m step and it models no agent radius, height or step.

It is kept because it is free and it prunes obvious rubbish. It is labelled a
PREFILTER in every report it appears in. It was deliberately NOT tuned to agree
with the navmesh: tuning a model until it matches the authority is fitting a
model to an answer.

Exit codes: 0 ok  2 bad args  3 refuse (stale/missing binding)  4 selftest failed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import terrain_erosion as te  # noqa: E402


class StaleRegion(Exception):
    """The sidecar was measured against a different navmesh than the caller
    declares. Refusing is the point: a reachability claim is true for one
    build."""


class ReachableRegion:
    """The authored reachable region, loaded from its bound sidecar."""

    def __init__(self, path, expect_agent_profile=None,
                 expect_nav_chunks=None, lattice_path=None):
        self.path = path
        if not os.path.isfile(path):
            raise StaleRegion(
                "no reachable-region sidecar at %r. It is produced in the "
                "editor by scripts/city_reachable_region_payload.txt against "
                "the BUILT navmesh; there is no offline substitute." % path)
        with open(path, "r", encoding="utf-8") as fh:
            self.doc = json.load(fh)

        self.bound = self.doc.get("_bound_to") or {}
        self.agent = self.bound.get("navmesh_agent") or {}
        self.anchor = self.bound.get("player_start_cm")

        # ---- the binding check, and it FAILS CLOSED ----------------------
        if expect_agent_profile is not None:
            want = float(te.MOVEMENT_PROFILES[expect_agent_profile]
                         ["max_slope_deg"])
            got = self.agent.get("agent_max_slope")
            if got is None:
                raise StaleRegion(
                    "the sidecar records no agent_max_slope, so it cannot be "
                    "matched to an agent. Re-measure it.")
            if abs(float(got) - want) > 0.01:
                raise StaleRegion(
                    "sidecar was measured at agent_max_slope %.5f but the "
                    "caller declares profile %r = %.5f. A reachability claim "
                    "is true for ONE navmesh build; re-measure rather than "
                    "reconcile." % (float(got), expect_agent_profile, want))

        # ---- the NAVMESH-BUILD half of the binding -----------------------
        # The sidecar has always RECORDED nav_chunk_actors_resident and nothing
        # ENFORCED it, which is a claim in a docstring that nothing re-checks
        # (non-negotiable 25). It was live: the east extension took the world
        # from 8 chunks to 10 and the sidecar went on declaring 8.
        #
        # !! AN OFFLINE CALLER CANNOT SUPPLY THIS. The live chunk count is an
        # editor query, so `expect_nav_chunks=None` means UNCHECKED, not
        # verified -- stated here rather than left to be assumed. Offline
        # consumers get the agent half of the binding and no more; an
        # in-editor caller that counts NavigationDataChunkActors should pass
        # the number and get a refusal instead of a stale answer.
        self.nav_chunks = self.bound.get("nav_chunk_actors_resident")
        self.nav_chunks_checked = expect_nav_chunks is not None
        if expect_nav_chunks is not None:
            if self.nav_chunks is None:
                raise StaleRegion(
                    "the sidecar records no nav_chunk_actors_resident, so it "
                    "cannot be matched to a navmesh build. Re-measure it.")
            if int(self.nav_chunks) != int(expect_nav_chunks):
                raise StaleRegion(
                    "sidecar was measured against %d navmesh chunk actors, "
                    "the caller reports %d in the world. The navmesh has been "
                    "rebuilt or extended since; re-measure rather than "
                    "reconcile." % (int(self.nav_chunks),
                                    int(expect_nav_chunks)))

        rows = [r for r in self.doc.get("street_rows", [])
                if r.get("reachable") is True]
        pts = [r["loc_cm"] for r in rows]
        self.n_reachable_streets = len(rows)

        # ---- THE LATTICE, and why it is not optional in practice ----------
        # The town sidecar samples street midpoints and building doorsteps --
        # every one of them INSIDE the settlement. A consumer asking "is this
        # point near ground the player can reach" therefore gets True only
        # inside the town, so a rule of the form "OUTSIDE the settlement AND
        # near reachable ground" is unsatisfiable BY CONSTRUCTION. That is
        # exactly what made the encounter planner compute zero available area
        # and report that the basin could not hold an encounter.
        #
        # The lattice covers the whole built navmesh, so the question can be
        # asked about ground the town does not occupy. It is a separate
        # artefact because it is measured differently (grid BFS) and can be
        # re-measured on its own.
        self.lattice_path = lattice_path
        self.n_lattice = 0
        if lattice_path is None:
            lattice_path = os.path.join(os.path.dirname(path),
                                        "alpine_basin_reachable_lattice.json")
        if os.path.isfile(lattice_path):
            with open(lattice_path, "r", encoding="utf-8") as fh:
                lat = json.load(fh)
            lb = (lat.get("_bound_to") or {}).get("navmesh_agent") or {}
            mine = self.agent.get("agent_max_slope")
            theirs = lb.get("agent_max_slope")
            # BOTH artefacts must describe the SAME navmesh build, or merging
            # them silently mixes two different worlds.
            if mine is not None and theirs is not None and \
                    abs(float(mine) - float(theirs)) > 0.01:
                raise StaleRegion(
                    "the lattice was measured at agent_max_slope %.5f and the "
                    "town sidecar at %.5f. Merging them would mix two navmesh "
                    "builds; re-measure rather than reconcile."
                    % (float(theirs), float(mine)))
            lc = (lat.get("_bound_to") or {}).get("nav_chunk_actors_resident")
            mc = self.bound.get("nav_chunk_actors_resident")
            if lc is not None and mc is not None and int(lc) != int(mc):
                raise StaleRegion(
                    "the lattice was measured against %d navmesh chunk actors "
                    "and the town sidecar against %d -- different builds."
                    % (int(lc), int(mc)))
            lat_pts = [[r[0], r[1]] for r in lat.get("rows", [])]
            self.n_lattice = len(lat_pts)
            self.lattice_step_cm = (lat.get("_bound_to") or {}).get(
                "lattice_step_cm")
            pts.extend(lat_pts)

        self.anchors = np.asarray(pts, dtype=np.float64) if pts else None

    # ---- the query every placement tool should use -------------------
    def near_reachable(self, x, y, max_cm):
        """Is (x,y) within max_cm of ground MEASURED reachable from the anchor?

        This is a PROXIMITY test to measured ground, not a claim that (x,y)
        itself is reachable -- only an editor path query can say that, and the
        caller is expected to run one. Named so the distinction survives.
        """
        if self.anchors is None or len(self.anchors) == 0:
            raise StaleRegion("the sidecar holds no reachable street rows")
        d = np.hypot(self.anchors[:, 0] - x, self.anchors[:, 1] - y)
        return bool(d.min() <= max_cm)

    def summary(self):
        s = self.doc.get("streets", {})
        b = self.doc.get("buildings", {})
        return {
            "sidecar": os.path.relpath(self.path, REPO),
            "agent_max_slope": self.agent.get("agent_max_slope"),
            "anchor_cm": self.anchor,
            "query_extent_cm": self.bound.get("query_extent_cm"),
            "nav_chunks_resident": self.bound.get("nav_chunk_actors_resident"),
            "anchors": (0 if self.anchors is None else len(self.anchors)),
            "lattice_rows": self.n_lattice,
            "streets": s, "buildings": b,
        }


def offline_component_mask(T, x0, y0, x1, y1, cell_cm, max_slope_deg,
                           anchor_xy):
    """PREFILTER ONLY. Heightmap walkable mask, 8-connected, anchor's component.

    ⚠ OPTIMISTIC BY CONSTRUCTION. It smooths a step it cannot see and models no
    agent radius, height or step height. It has passed rows the built navmesh
    refused. Use it to prune, never to accept.
    """
    from scipy import ndimage

    nx = int((x1 - x0) // cell_cm) + 1
    ny = int((y1 - y0) // cell_cm) + 1
    gx, gy = np.meshgrid(x0 + np.arange(nx) * cell_cm,
                         y0 + np.arange(ny) * cell_cm, indexing="ij")
    hz = np.asarray(T.z_cm(gx.ravel(), gy.ravel())).reshape(nx, ny)
    dzx = np.abs(np.gradient(hz, cell_cm, axis=0))
    dzy = np.abs(np.gradient(hz, cell_cm, axis=1))
    slope = np.degrees(np.arctan(np.maximum(dzx, dzy)))
    walkable = slope <= max_slope_deg
    lab, nlab = ndimage.label(walkable, structure=np.ones((3, 3), dtype=int))
    i = min(max(int(round((anchor_xy[0] - x0) / cell_cm)), 0), nx - 1)
    j = min(max(int(round((anchor_xy[1] - y0) / cell_cm)), 0), ny - 1)
    home = int(lab[i, j])
    mask = (lab == home) if home else np.zeros_like(walkable, dtype=bool)
    return {"mask": mask, "nx": nx, "ny": ny, "cell_cm": cell_cm,
            "x0": x0, "y0": y0, "components": int(nlab),
            "anchor_component": home,
            "_role": "PREFILTER -- optimistic, never a gate"}


def selftest():
    """Prove the binding check REFUSES. It has only ever seen a good sidecar."""
    ok = True
    side = os.path.join(REPO, "city", "alpine_basin_town_reachable.json")

    # (a) the shipping agent must LOAD
    try:
        r = ReachableRegion(side, expect_agent_profile="walk")
        print("  walk sidecar loads                       OK  (%d reachable "
              "street rows)" % r.n_reachable_streets)
    except StaleRegion as e:
        print("  walk sidecar loads                       FAIL  %s" % e)
        ok = False

    # (b) a DIFFERENT agent must REFUSE -- this is the whole point
    try:
        ReachableRegion(side, expect_agent_profile="mount")
        print("  mount against a walk-measured sidecar    FAIL (accepted it)")
        ok = False
    except StaleRegion:
        print("  mount against a walk-measured sidecar    OK  (refused)")

    # (c) a missing sidecar must REFUSE, not return empty
    try:
        ReachableRegion(os.path.join(REPO, "city", "does_not_exist.json"))
        print("  missing sidecar                          FAIL (accepted it)")
        ok = False
    except StaleRegion:
        print("  missing sidecar                          OK  (refused)")

    # (c2) the NAVMESH-BUILD half of the binding, both directions.
    # It was recorded and unenforced until 2026-08-26, and it was live: the
    # east extension took the world from 8 chunks to 10 while the sidecar went
    # on declaring 8.
    try:
        rr = ReachableRegion(side, expect_agent_profile="walk")
        live = rr.nav_chunks
        ReachableRegion(side, expect_agent_profile="walk",
                        expect_nav_chunks=live)
        print("  matching nav chunk count (%s)             OK  (accepted)"
              % live)
    except StaleRegion as e:
        print("  matching nav chunk count                 FAIL  %s" % e)
        ok = False
    try:
        ReachableRegion(side, expect_agent_profile="walk",
                        expect_nav_chunks=999)
        print("  a DIFFERENT nav chunk count              FAIL (accepted it)")
        ok = False
    except StaleRegion:
        print("  a DIFFERENT nav chunk count              OK  (refused)")

    # (d) proximity discriminates
    try:
        r = ReachableRegion(side, expect_agent_profile="walk")
        a = r.anchors[0]
        near = r.near_reachable(float(a[0]), float(a[1]), 100.0)
        far = r.near_reachable(float(a[0]) + 5000000.0, float(a[1]), 100.0)
        good = near and not far
        print("  proximity: on a reachable row=%s, 50 km away=%s   %s"
              % (near, far, "OK" if good else "FAIL"))
        ok &= good
    except StaleRegion as e:
        print("  proximity                                FAIL  %s" % e)
        ok = False

    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar",
                    default="city/alpine_basin_town_reachable.json")
    ap.add_argument("--agent", default="walk")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        print("SELFTEST")
        good = selftest()
        print("SELFTEST %s" % ("PASSED" if good else "FAILED"))
        return 0 if good else 4

    try:
        r = ReachableRegion(os.path.join(REPO, a.sidecar),
                            expect_agent_profile=a.agent)
    except StaleRegion as e:
        print("REFUSE: %s" % e)
        return 3

    s = r.summary()
    print("sidecar          %s" % s["sidecar"])
    print("agent_max_slope  %s   (declared profile %r)"
          % (s["agent_max_slope"], a.agent))
    print("anchor_cm        %s" % s["anchor_cm"])
    print("query_extent_cm  %s" % s["query_extent_cm"])
    print("nav chunks       %s" % s["nav_chunks_resident"])
    st, bd = s["streets"], s["buildings"]
    print("streets          %s of %s reachable" % (st.get("reachable"),
                                                   st.get("total")))
    print("buildings        %s of %s reachable at the doorstep"
          % (bd.get("reachable"), bd.get("total")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
