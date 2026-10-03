"""
narkomfin_grammar.py -- the Dom Narkomfin Topologic grammar, in two parts
=========================================================================
Grammar A  "BLOCK"      the residential slab: ground, stack, bay/party-wall pair, corridor,
                        the L- and U-section dwelling cells, cores, facade split, ends, roof
Grammar B  "CONDENSER"  the social condenser: stack, double-height merge, gallery, curtain wall,
                        core, and the BRIDGE rule that joins the two grammars

Both grammars rewrite the SAME state: a list of labelled cells (volumes and elements) plus a
labelled directed graph. Every rule declares what it does to the geometry AND to the graph, which is
the point of the exercise: the shape rule advances, the graph follows, so variants can later be driven
from either side.

The two apartment types are one rule with one parameter:

        section(levels, corridor_level)     the dwelling's section, extruded along the bay

        levels=2, corridor at the BOTTOM   ->  L        (K-type, corridor at L1)
        levels=3, corridor in the MIDDLE   ->  U        (F-type, corridor at L4)
        levels=2, corridor at the TOP      ->  Gamma    (mirror of L: unbuilt variant)
        levels=4, corridor at level 1 or 2 ->  L/Z      (skip-stop family: unbuilt variants)

The corridor is subtracted from ONE level of an n-level stack; which level it pierces is what makes
the section L or U. That single parameter is the variant engine.

Usage
-----
    blender --background --python narkomfin_grammar.py -- --out GRAMMAR.blend --json rules.json
    python narkomfin_grammar.py --out GRAMMAR.blend --json rules.json       (pip bpy module)

Collections produced:
    Rules/                 one card per rule: LHS | arrow | RHS, with labels
    Derivation_A_Block/    Step_01 .. Step_10, each with its graph drawn beside it
    Derivation_B_Condenser/Step_01 .. Step_07
    Variants/              the same rules with different parameters (V1..V4)
"""
import argparse, json, math, os, sys
from copy import deepcopy

import bpy
from mathutils import Vector

from narkomfin_element_dictionary import (prism, cuboid, cyl, arc, disc, notched, flight_mesh,
                                          make_materials, clear, label, MATS,
                                          BAY, DEPTH, H_TYP, H_PIL, TS, TE, TC, TT, TG, HS,
                                          DW, DH, COL_X, COL_Y, PIL_R, STAIR_W)

NBAY = 22
CORE_LINES = (2, 19)       # the two stair cores; A5 leaves these bays alone, A6 consumes them
CORR = 1.80          # depth of the common corridor, measured from the south face
HALL = 1.58          # depth of the dwelling's own band beside the corridor at that level
LEN = NBAY * BAY

# ---------------------------------------------------------------------------- state
class State:
    """The design: cells (each a labelled solid) + a labelled graph."""

    def __init__(self):
        self.cells = []      # dicts: id, label, cat, geom=('box',x0,x1,y0,y1,z0,z1) | ('sect',x0,x1,profile)
        self.nodes = []      # dicts: id, label, pos
        self.dwelling_base = {}   # dwelling node -> the level it is entered on
        self.edges = []      # dicts: a, b, label
        self._n = 0

    # -- geometry ---------------------------------------------------------
    def box(self, label, cat, x0, x1, y0, y1, z0, z1, **kw):
        self._n += 1
        c = dict(id=f"c{self._n}", label=label, cat=cat, geom=("box", x0, x1, y0, y1, z0, z1))
        c.update(kw)
        self.cells.append(c)
        return c

    def sect(self, label, cat, x0, x1, profile, **kw):
        """A cell defined by a (y,z) section profile extruded along x - this is how L and U cells live."""
        self._n += 1
        c = dict(id=f"c{self._n}", label=label, cat=cat, geom=("sect", x0, x1, profile))
        c.update(kw)
        self.cells.append(c)
        return c

    def drop(self, pred):
        self.cells = [c for c in self.cells if not pred(c)]

    def find(self, **kw):
        return [c for c in self.cells if all(c.get(k) == v for k, v in kw.items())]

    # -- graph ------------------------------------------------------------
    def node(self, nid, label, pos):
        self.nodes.append(dict(id=nid, label=label, pos=[round(v, 2) for v in pos]))

    def edge(self, a, b, label):
        self.edges.append(dict(a=a, b=b, label=label))

    def drop_nodes(self, pred):
        gone = {n["id"] for n in self.nodes if pred(n)}
        self.nodes = [n for n in self.nodes if n["id"] not in gone]
        self.edges = [e for e in self.edges if e["a"] not in gone and e["b"] not in gone]

    def centroid(self, c):
        g = c["geom"]
        if g[0] == "box":
            return ((g[1] + g[2]) / 2, (g[3] + g[4]) / 2, (g[5] + g[6]) / 2)
        ys = [p[0] for p in g[3]]
        zs = [p[1] for p in g[3]]
        return ((g[1] + g[2]) / 2, sum(ys) / len(ys), sum(zs) / len(zs))

    def copy(self):
        s = State()
        s.cells = deepcopy(self.cells)
        s.nodes = deepcopy(self.nodes)
        s.edges = deepcopy(self.edges)
        s._n = self._n
        return s


# ---------------------------------------------------------------------------- the section rule
def section(levels, corridor_level, depth=DEPTH, corr=CORR, hall=HALL, h=H_TYP, t=TS):
    """(y, z) profile of a dwelling of `levels` storeys whose level `corridor_level` (0-based from the
    bottom) is pierced by the common corridor. Returns a simple closed polygon:

        corridor at bottom -> L        in the middle -> U        at the top -> Gamma

    The pierced level keeps only a band of depth `hall` on the far side of the corridor, which is where
    the dwelling's entrance hall (and, at Narkomfin, its WCs) sit."""
    y_c = corr                       # north edge of the corridor
    y_h = corr + hall                # north edge of the dwelling's own band on the pierced level
    pts = [(0.0, 0.0)]
    # walk up the SOUTH side, stepping in and out around the corridor
    z = 0.0
    for lv in range(levels):
        z0, z1 = lv * h, (lv + 1) * h - (t if lv == levels - 1 else 0.0)
        if lv == corridor_level:
            pts += [(0.0, z0), (y_c, z0), (y_c, z1), (0.0, z1)]
    pts += [(0.0, levels * h - t)]
    # north side back down
    pts += [(depth, levels * h - t), (depth, 0.0)]
    # rebuild cleanly: the profile is the rectangle minus the corridor notch (and minus the slot
    # above/below the hall band on the pierced level)
    L, H = depth, levels * h - t
    if not (0 <= corridor_level < levels):        # no street pierces this cell: the plain rectangle
        return [(0.0, 0.0), (L, 0.0), (L, H), (0.0, H)]
    z0, z1 = corridor_level * h, (corridor_level + 1) * h - t
    poly = [(0.0, 0.0), (L, 0.0), (L, H), (0.0, H)]
    if corridor_level == 0:                       # L : notch out of the bottom-south corner
        poly = [(y_c, 0.0), (L, 0.0), (L, H), (0.0, H), (0.0, z1), (y_c, z1)]
    elif corridor_level == levels - 1:            # Gamma : notch out of the top-south corner
        poly = [(0.0, 0.0), (L, 0.0), (L, H), (y_c, H), (y_c, z0), (0.0, z0)]
    else:                                          # U : notch bitten out of the middle of the south side
        poly = [(0.0, 0.0), (L, 0.0), (L, H), (0.0, H), (0.0, z1), (y_c, z1), (y_c, z0), (0.0, z0)]
    return poly


def section_kind(levels, corridor_level):
    if levels < 2:
        return "flat"
    if corridor_level == 0:
        return "L"
    if corridor_level == levels - 1:
        return "Gamma"
    if levels == 3:
        return "U"
    return "Z"


# ---------------------------------------------------------------------------- GRAMMAR A: the block
def A_axiom(s, levels=6):
    s.box("BLOCK mass", "Mass", 0, LEN, 0, DEPTH, 0, H_PIL + levels * H_TYP, role="axiom")
    s.node("BLOCK", "BLOCK", (LEN / 2, DEPTH / 2, 8))
    return "A0 AXIOM: a single prism, 80.5 x 9.9 x 19.3 m, labelled BLOCK"


def A_lift(s, levels=6):
    """R_LIFT  BLOCK -> open ground plane (pilotis) + MASS above."""
    s.drop(lambda c: c.get("role") == "axiom")
    s.box("GROUND open", "Space", 0, LEN, 0, DEPTH, 0, H_PIL - TS, role="ground")
    s.box("MASS", "Mass", 0, LEN, 0, DEPTH, H_PIL, H_PIL + levels * H_TYP, role="mass")
    for i in range(NBAY + 1):
        for y in (2.0, DEPTH / 2, DEPTH - 2.0):
            cyl_c = s.box(f"CO.PIL {i}", "Structure", i * BAY - PIL_R, i * BAY + PIL_R,
                          y - PIL_R, y + PIL_R, 0, H_PIL - TS, role="pilotis", symbol="CO.PIL")
    s.drop_nodes(lambda n: n["id"] == "BLOCK")
    s.node("GROUND", "GROUND", (LEN / 2, DEPTH / 2, 1.1))
    s.node("MASS", "MASS", (LEN / 2, DEPTH / 2, 11))
    s.edge("GROUND", "MASS", "supports")
    return ("A1 R_LIFT: SPLIT-Z at 2.50 m. The lower part is emptied to a colonnade of CO.PIL (3 rows x 23 "
            "lines) and the upper part relabelled MASS: the ground plane is given away, which is the first "
            "political act of the building. Graph: one node becomes two, joined by a 'supports' edge.")


def A_stack(s, levels=6):
    """R_STACK  MASS -> n storey bands, each a slab + a volume."""
    s.drop(lambda c: c.get("role") == "mass")
    s.drop_nodes(lambda n: n["id"] == "MASS")
    for lv in range(levels):
        z0 = H_PIL + lv * H_TYP
        s.box(f"SL band L{lv+1}", "Structure", 0, LEN, 0, DEPTH, z0 - TS, z0, role="slab", level=lv + 1, symbol="SL.BAY")
        s.box(f"STOREY L{lv+1}", "Space", 0, LEN, 0, DEPTH, z0, z0 + H_TYP - TS, role="storey", level=lv + 1)
        s.node(f"L{lv+1}", f"STOREY L{lv+1}", (LEN / 2, DEPTH / 2, z0 + 1.2))
        if lv:
            s.edge(f"L{lv}", f"L{lv+1}", "above")
        else:
            s.edge("GROUND", "L1", "above")
    s.box("SL roof", "Structure", 0, LEN, 0, DEPTH, H_PIL + levels * H_TYP - TS, H_PIL + levels * H_TYP,
          role="roof", symbol="SL.ROOF")
    return (f"A2 R_STACK: repeated SPLIT-Z of MASS into {levels} storey bands of 2.80 m, each a slab band + a "
            "storey volume, closed by SL.ROOF. Graph: a vertical chain of 'above' edges - stacking is the only "
            "rule so far that makes the graph three-dimensional, and R_LCELL/R_UCELL will later exploit it.")


def A_bay_party(s, levels=6):
    """R_BAY  the bay / party-wall PAIR.  One storey band -> 22 bay slabs + 23 party lines,
    each party line = DV.WALL.PARTY with CO.RECT inside it (which is why the wall arrives in pieces)."""
    for band in list(s.find(role="slab")):
        s.cells.remove(band)
        lv = band["level"]
        z0, z1 = band["geom"][5], band["geom"][6]
        for i in range(NBAY):
            s.box(f"SL.BAY L{lv} b{i:02d}", "Structure", i * BAY, (i + 1) * BAY, 0, DEPTH, z0, z1,
                  role="bayslab", level=lv, bay=i, symbol="SL.BAY")
    for st in list(s.find(role="storey")):
        s.cells.remove(st)
        lv = st["level"]
        z0, z1 = st["geom"][5], st["geom"][6]
        s.drop_nodes(lambda n, lv=lv: n["id"] == f"L{lv}")
        for i in range(NBAY):
            s.box(f"BAY L{lv} b{i:02d}", "Space", i * BAY + TE / 2, (i + 1) * BAY - TE / 2, 0, DEPTH, z0, z1,
                  role="bay", level=lv, bay=i)
            s.node(f"L{lv}b{i:02d}", f"BAY {i}", ((i + 0.5) * BAY, DEPTH / 2, z0 + 1.2))
            if i:
                s.edge(f"L{lv}b{i-1:02d}", f"L{lv}b{i:02d}", "party wall (blind)")
        for i in range(NBAY + 1):
            # the PAIR: a party wall on the line, split by the column that sits inside it
            for (y0, y1) in ((0, DEPTH / 2 - COL_Y / 2), (DEPTH / 2 + COL_Y / 2, DEPTH)):
                s.box(f"DV.WALL.PARTY L{lv} x{i:02d}", "Division", i * BAY - TE / 2, i * BAY + TE / 2,
                      y0, y1, z0, z1, role="party", level=lv, line=i, symbol="DV.WALL.PARTY")
            s.box(f"CO.RECT L{lv} x{i:02d}", "Structure", i * BAY - COL_X / 2, i * BAY + COL_X / 2,
                  DEPTH / 2 - COL_Y / 2, DEPTH / 2 + COL_Y / 2, z0, z1, role="column", level=lv, line=i, symbol="CO.RECT")
    return ("A3 R_BAY (the bay / party-wall pair): SPLIT-X of a storey band on a 3.66 m rhythm. The rule is a "
            "PAIR because neither half is meaningful alone: each cut produces a bay slab AND the party wall on "
            "the cut line, and the column CO.RECT is absorbed into that wall, splitting it into pieces. "
            "Graph: 22 bay nodes per level, chained by blind 'party wall' edges - adjacency without access, "
            "which is exactly what a party wall means.")


def A_corridor(s, corridor_levels=(1, 4)):
    """R_CORRIDOR  insert the common corridor: SPLIT-Y of the chosen levels into corridor + dwelling band."""
    for lv in corridor_levels:
        prev = None
        for c in list(s.find(role="bay", level=lv)):
            s.cells.remove(c)
            x0, x1, _, _, z0, z1 = c["geom"][1:]
            i = c["bay"]
            s.box(f"SP.CORRIDOR L{lv} b{i:02d}", "Space", x0, x1, 0, CORR, z0, z1,
                  role="corridor", level=lv, bay=i, symbol="SP.CORRIDOR")
            s.box(f"BAY L{lv} b{i:02d} (north of corridor)", "Space", x0, x1, CORR, DEPTH, z0, z1,
                  role="bay", level=lv, bay=i)
            s.box(f"DV.WALL.CORR L{lv} b{i:02d}", "Division", x0, x1, CORR - TC / 2, CORR + TC / 2, z0, z1,
                  role="corrwall", level=lv, bay=i, symbol="DV.WALL.CORR")
            s.drop_nodes(lambda n, lv=lv, i=i: n["id"] == f"L{lv}b{i:02d}")
            nid = f"C{lv}b{i:02d}"
            s.node(nid, f"CORRIDOR L{lv}", ((i + 0.5) * BAY, CORR / 2, z0 + 1.2))
            if prev:
                s.edge(prev, nid, "corridor (open)")
            prev = nid
    return ("A4 R_CORRIDOR: SPLIT-Y of levels " + ", ".join(f"L{l}" for l in corridor_levels) +
            " into a 1.80 m common corridor on the south and the dwelling band on the north, with "
            "DV.WALL.CORR (door notch per bay) on the cut. Graph: the corridor nodes form an open chain - "
            "the 'internal street'. This is the level at which the whole social programme is decided.")


def A_cells(s, groups=((1, 2, 0, "K"), (3, 5, 1, "F"))):
    """R_LCELL / R_UCELL  merge a vertical run of bays into ONE dwelling whose section is L or U,
    according to which level the corridor pierces.  groups: (level_lo, level_hi, corridor_index, tag)."""
    notes = []
    for (lo, hi, ci, tag) in groups:
        levels = hi - lo + 1
        kind = section_kind(levels, ci)
        prof = section(levels, ci)
        for i in range(3, NBAY - 3):
            # consume the stacked bay volumes
            for lv in range(lo, hi + 1):
                for c in s.find(role="bay", level=lv, bay=i):
                    s.cells.remove(c)
                s.drop_nodes(lambda n, lv=lv, i=i: n["id"] == f"L{lv}b{i:02d}")
            # one dwelling cell, its section extruded along the bay
            z_base = H_PIL + (lo - 1) * H_TYP
            pr = [(y, z + z_base) for (y, z) in prof]
            s.sect(f"SP.CELL.{tag} b{i:02d} [{kind}]", "Space", i * BAY + TE / 2, (i + 1) * BAY - TE / 2, pr,
                   role="dwelling", tag=tag, kind=kind, bay=i, level=lo, levels=levels, corridor_index=ci,
                   symbol=f"SP.CELL.{tag}")
            nid = f"{tag}b{i:02d}"
            s.node(nid, f"{tag} [{kind}] b{i}", ((i + 0.5) * BAY, DEPTH / 2 + 1.0, z_base + levels * H_TYP / 2))
            s.dwelling_base[nid] = lo
            s.edge(f"C{lo+ci}b{i:02d}", nid, "entrance door")
            if i > 3:
                s.edge(f"{tag}b{i-1:02d}", nid, "party wall (blind)")
        notes.append(f"{tag}: {levels} levels, corridor at index {ci} -> section {kind}")
    # END UNITS: the bays beyond the cores are single-level flats, entered from the stair lobby.
    # They are the degenerate case of the same rule - one level, no corridor notch, so the section is
    # the plain bay rectangle. Their access edge is supplied by A6, with the core that serves them.
    for i in list(range(CORE_LINES[0])) + list(range(CORE_LINES[-1] + 1, NBAY)):
        for lv in range(1, 6):
            gone = False
            for c in s.find(role="bay", level=lv, bay=i):
                s.cells.remove(c)
                gone = True
            if not gone:
                continue
            s.drop_nodes(lambda n, lv=lv, i=i: n["id"] == f"L{lv}b{i:02d}")
            z_base = H_PIL + (lv - 1) * H_TYP
            s.sect(f"SP.CELL.E L{lv} b{i:02d} [flat]", "Space", i * BAY + TE / 2, (i + 1) * BAY - TE / 2,
                   [(y, z + z_base) for (y, z) in section(1, -1)],
                   role="dwelling", tag="E", kind="flat", bay=i, level=lv, levels=1, corridor_index=-1,
                   symbol="SP.CELL.E")
            nid = f"Eb{i:02d}L{lv}"
            s.node(nid, f"E [flat] b{i} L{lv}", ((i + 0.5) * BAY, DEPTH / 2 + 1.0, z_base + H_TYP / 2))
            for nb in (f"Eb{i-1:02d}L{lv}", f"Eb{i+1:02d}L{lv}"):
                s.edge(nb, nid, "party wall (blind)")
    notes.append("E: 1 level, no corridor notch -> flat (the end units beyond the cores)")
    # K units come in mirrored pairs: MIRROR-X about the shared party wall
    for i in range(3, NBAY - 3, 2):
        a, b = f"Kb{i:02d}", f"Kb{i+1:02d}"
        if any(n["id"] == a for n in s.nodes) and any(n["id"] == b for n in s.nodes):
            for e in s.edges:
                if {e["a"], e["b"]} == {a, b}:
                    e["label"] = "party wall (mirror pair)"
    return ("A5 R_LCELL / R_UCELL (one rule, one parameter): a run of stacked bays is merged into a single "
            "dwelling whose SECTION is the bay rectangle minus the corridor notch. " + "; ".join(notes) +
            ". The K cell is an L: two levels, corridor at the bottom, so the upper level runs the full 9.90 m "
            "depth over the corridor. The F cell is a U: three levels, corridor through the MIDDLE, so the "
            "dwelling has a full-depth level below AND above the street and only a narrow hall band beside it. "
            "One corridor therefore serves three floors. Graph: the stacked bay nodes COLLAPSE into one "
            "dwelling node with a single 'entrance door' edge to the corridor - the section rule is visible "
            "in the graph as a change of node count, which is what we want to drive variants from. The END "
            "UNITS are the degenerate case of the same production - levels = 1, no notch - which is the "
            "cheapest possible proof that L, U and flat are one rule and not three.")


def A_cores(s, lines=CORE_LINES, levels=6):
    """R_CORE  two bays become vertical cores: stairwell volumes + flights, with up/down edges."""
    for i in lines:
        for lv in range(1, levels + 1):
            for c in s.find(role="bay", level=lv, bay=i):
                s.cells.remove(c)
            for c in s.find(role="corridor", level=lv, bay=i):
                s.cells.remove(c)
            s.drop_nodes(lambda n, lv=lv, i=i: n["id"] in (f"L{lv}b{i:02d}", f"C{lv}b{i:02d}"))
            z0 = H_PIL + (lv - 1) * H_TYP
            s.box(f"SP.STAIRWELL L{lv} b{i:02d}", "Space", i * BAY + TE / 2, (i + 1) * BAY - TE / 2,
                  DEPTH - 5.01, DEPTH, z0, z0 + H_TYP - TS, role="stairwell", level=lv, bay=i, symbol="SP.STAIRWELL")
            for k, (run0, up) in enumerate(((0.0, True), (2.30, False))):
                s.box(f"CI.FLIGHT L{lv} b{i:02d} {k}", "Circulation", i * BAY + 0.3 + k * 1.6, i * BAY + 0.3 + k * 1.6 + STAIR_W,
                      DEPTH - 4.6, DEPTH - 2.3, z0 + k * H_TYP / 2, z0 + (k + 1) * H_TYP / 2,
                      role="flight", level=lv, bay=i, symbol="CI.FLIGHT")
            nid = f"S{lv}b{i:02d}"
            s.node(nid, f"STAIRWELL b{i}", ((i + 0.5) * BAY, DEPTH - 2.5, z0 + 1.2))
            if lv > 1:
                s.edge(f"S{lv-1}b{i:02d}", nid, "stair flight")
            else:
                s.edge("GROUND", nid, "stair flight")
            # the core INTERRUPTS the corridor chain, so it must carry it: a door on each side re-links
            # the street through the stairwell instead of leaving two dangling chains
            for cl in (1, 4):
                if lv == cl:
                    for nb in (f"C{cl}b{i-1:02d}", f"C{cl}b{i+1:02d}"):
                        if any(n["id"] == nb for n in s.nodes):
                            s.edge(nid, nb, "core door")
            # the end units on this level are entered from the stair lobby
            for nb in [f"Eb{j:02d}L{lv}" for j in (i - 1, i + 1, i - 2, i + 2)]:
                if any(n["id"] == nb for n in s.nodes):
                    s.edge(nid, nb, "core door")
            # so is the dwelling immediately beside the core - once, on the level it is entered from
            for d in s.nodes:
                if d["id"].endswith((f"b{i-1:02d}", f"b{i+1:02d}")) and s.dwelling_base.get(d["id"]) == lv:
                    s.edge(nid, d["id"], "core door")
    return ("A6 R_CORE: two bays (lines 2 and 19) are relabelled as vertical cores - CI.FLIGHT pairs + "
            "SP.STAIRWELL. Graph: the only nodes carrying VERTICAL edges. Until this rule the graph is a set "
            "of horizontal chains; after it the graph is genuinely three-dimensional. The core also CARRIES "
            "THE STREET: because it interrupts the corridor, it takes a door on each side, so the chain runs "
            "corridor - stairwell - corridor rather than breaking into two dangling halves. The end units and "
            "the dwellings beside the core are entered from the same lobby.")


def A_facade(s, levels=6, spandrel=HS):
    """R_FACADE  the facade SPLIT-Z: each envelope panel -> EN.SPAND (below) + EN.WIN.RIBBON (above).
    The pane is produced CONTINUOUS along the whole facade, not per bay - that is the style rule."""
    for lv in range(1, levels + 1):
        z0 = H_PIL + (lv - 1) * H_TYP
        z1 = z0 + H_TYP - TS
        for (y, tag) in ((0.0, "S"), (DEPTH, "N")):
            yy = y + (TE / 2 if y == 0 else -TE / 2)
            if spandrel > 0.01:
                s.box(f"EN.SPAND L{lv} {tag}", "Envelope", 0, LEN, yy - TE / 2, yy + TE / 2, z0, z0 + spandrel,
                      role="spandrel", level=lv, face=tag, symbol="EN.SPAND")
            if z1 - (z0 + spandrel) > 0.05:
                s.box(f"EN.WIN.RIBBON L{lv} {tag}", "Envelope", 0, LEN, yy - TG / 2, yy + TG / 2,
                      z0 + spandrel, z1, role="ribbon", level=lv, face=tag,
                      symbol="EN.WIN.RIBBON" if spandrel > 0.01 else "EN.WIN.CURT")
    return ("A7 R_FACADE (facade split): every envelope panel is SPLIT-Z at 1.00 m into EN.SPAND below and "
            "EN.WIN.RIBBON above, the pane running from end to end of the block. Two things matter "
            "grammatically: (i) the split height is a parameter - at spandrel = 0 the same rule yields the "
            "condenser's EN.WIN.CURT, so ribbon and curtain wall are ONE rule, not two; (ii) the pane is NOT "
            "subdivided by the bay rule, so the facade is deliberately out of step with the structure. A "
            "per-bay window would generate a different architecture with the same plan. The graph is unchanged: "
            "the facade split adds no nodes, only exterior faces - envelope is style, not topology.")


def A_ends_roof(s, levels=6):
    """R_END + R_ROOF  gables, semicircular balconies, parapets, penthouse."""
    for lv in range(1, levels + 1):
        z0 = H_PIL + (lv - 1) * H_TYP
        for x, tag in ((TE / 2, "W"), (LEN - TE / 2, "E")):
            s.box(f"EN.WALL.END L{lv} {tag}", "Envelope", x - TE / 2, x + TE / 2, 0, DEPTH, z0, z0 + H_TYP - TS,
                  role="gable", level=lv, symbol="EN.WALL.END")
        if 2 <= lv <= 5:
            s.box(f"SL.BALC.SEMI L{lv}", "Structure", -2.4, 0, DEPTH / 2 - 2.4, DEPTH / 2 + 2.4, z0 - TS, z0,
                  role="balcony", level=lv, symbol="SL.BALC.SEMI")
    ztop = H_PIL + levels * H_TYP
    s.box("EN.PARAPET roof", "Envelope", 0, LEN, 0, 0.2, ztop, ztop + 0.6, role="parapet", symbol="EN.PARAPET")
    s.box("PENTHOUSE", "Mass", 0.18 * LEN, 0.55 * LEN, DEPTH / 2, DEPTH, ztop, ztop + H_TYP, role="penthouse")
    for n in s.nodes:
        if n["label"].startswith("BAY "):
            n["label"] = "ROOF ZONE " + n["label"]
    s.node("PENTHOUSE", "PENTHOUSE", (0.36 * LEN, DEPTH * 0.75, ztop + 1.4))
    s.edge(f"S{levels}b02", "PENTHOUSE", "stair flight")
    return ("A8 R_END + R_ROOF: EN.WALL.END terminates the repetition along x (a blind gable - the rule that "
            "says 'stop'), with SL.BALC.SEMI attached to its outer face on L2-L5, and the stack is closed by "
            "parapet and penthouse. Graph: one terminal node on top of a core.")


GRAMMAR_A = [("A0", "AXIOM", A_axiom), ("A1", "R_LIFT", A_lift), ("A2", "R_STACK", A_stack),
             ("A3", "R_BAY (bay / party-wall pair)", A_bay_party), ("A4", "R_CORRIDOR", A_corridor),
             ("A5", "R_LCELL / R_UCELL", A_cells), ("A6", "R_CORE", A_cores),
             ("A7", "R_FACADE (facade split)", A_facade), ("A8", "R_END + R_ROOF", A_ends_roof)]


# ---------------------------------------------------------------------------- GRAMMAR B: condenser
CX, CY, CZ = 10.65, 9.96, 2.80
COND_ORIGIN = (-26.0, -18.0, 0.0)


def _o(x, y, z):
    return (x + COND_ORIGIN[0], y + COND_ORIGIN[1], z + COND_ORIGIN[2])


def B_axiom(s, **kw):
    ox, oy, _ = COND_ORIGIN
    s.box("CONDENSER mass", "Mass", ox, ox + CX, oy, oy + CY, 0, 4 * CZ, role="Baxiom")
    s.node("COND", "CONDENSER", (ox + CX / 2, oy + CY / 2, 5))
    # the INTERFACE node: grammar B knows nothing of grammar A except this one gluing point,
    # the block's L1 corridor. R_BRIDGE is the only production that touches it.
    s.node("IFACE.BLOCK_L1_CORRIDOR", "[interface] BLOCK L1 corridor", (0.0, CORR / 2, H_PIL + 1.2))
    return ("B0 AXIOM: a second, separate prism - the social condenser. It is a SEPARATE GRAMMAR because its "
            "rules are different in kind: the block subdivides a repetitive frame, the condenser merges levels "
            "into a single collective volume. Same operations, opposite direction.")


def B_stack(s, levels=4, **kw):
    ox, oy, _ = COND_ORIGIN
    s.drop(lambda c: c.get("role") == "Baxiom")
    s.drop_nodes(lambda n: n["id"] == "COND")
    for lv in range(levels):
        z0 = lv * CZ
        s.box(f"CB SL L{lv}", "Structure", ox, ox + CX, oy, oy + CY, z0 - TS, z0, role="Bslab", level=lv)
        s.box(f"CB STOREY L{lv}", "Space", ox, ox + CX, oy, oy + CY, z0, z0 + CZ - TS, role="Bstorey", level=lv)
        s.node(f"CB{lv}", f"CB L{lv}", (ox + CX / 2, oy + CY / 2, z0 + 1.2))
        if lv:
            s.edge(f"CB{lv-1}", f"CB{lv}", "above")
    s.box("CB roof", "Structure", ox, ox + CX, oy, oy + CY, levels * CZ - TS, levels * CZ, role="Broof")
    return f"B1 R_STACK: the same SPLIT-Z as A2, {levels} storeys."


def B_merge(s, merge=(1, 2), **kw):
    """R_MERGE  the social condenser rule: remove an intermediate slab and UNION two storeys into one
    double-height collective volume. The inverse of A2."""
    ox, oy, _ = COND_ORIGIN
    for lv in merge[1:]:
        s.drop(lambda c, lv=lv: c.get("role") == "Bslab" and c.get("level") == lv)
    for lv in merge:
        s.drop(lambda c, lv=lv: c.get("role") == "Bstorey" and c.get("level") == lv)
        s.drop_nodes(lambda n, lv=lv: n["id"] == f"CB{lv}")
    z0 = merge[0] * CZ
    s.box("SP.HALL (double height)", "Space", ox, ox + CX, oy, oy + CY, z0, z0 + len(merge) * CZ - TS,
          role="hall", symbol="SP.HALL")
    s.node("HALL", "SP.HALL", (ox + CX / 2, oy + CY / 2, z0 + 2.5))
    s.edge("CB0", "HALL", "above")
    if any(n["id"] == f"CB{merge[-1]+1}" for n in s.nodes):
        s.edge("HALL", f"CB{merge[-1]+1}", "above")
    return ("B2 R_MERGE (the social condenser rule): delete an intermediate slab and UNION the two storeys "
            "into one double-height volume - gymnasium / dining / library. Graph: two nodes collapse into one "
            "of HIGH degree. That is the graph-theoretic definition of a 'social condenser': not a room type "
            "but a node whose degree is out of proportion to the rest of the graph.")


def B_gallery(s, **kw):
    ox, oy, _ = COND_ORIGIN
    seg, x_a, x_b = 18, 3.91, 10.65
    pr = [(ox, oy), (ox + CX, oy), (ox + CX, oy + 7.52)]
    for i in range(1, seg):
        x = x_b - i * (x_b - x_a) / seg
        cxm, a = (x_b + x_a) / 2, (x_b - x_a) / 2
        y = 7.52 - 0.97 * math.sqrt(max(0.0, 1 - ((x - cxm) / a) ** 2))
        pr.append((ox + x, oy + y))
    pr += [(ox + x_a, oy + 7.52), (ox, oy + 7.52)]
    z = 3 * CZ - CZ * 0.0 - 0.4
    s.sect("SL.GALL gallery", "Structure", 0, 0, [], role="gallery")   # placeholder replaced below
    s.cells[-1]["geom"] = ("poly", pr, 2 * CZ + 0.6 - TS, 2 * CZ + 0.6)
    s.node("GALLERY", "GALLERY", (ox + CX / 2, oy + 3.5, 2 * CZ + 1.8))
    s.edge("HALL", "GALLERY", "open (double height)")
    return ("B3 R_GALLERY: SUBTRACT a curved void from a slab inside the hall, giving SL.GALL. Graph: a node "
            "adjacent to the hall by an OPEN edge (no wall, no door) - the relation that makes a gallery a "
            "gallery rather than a room.")


def B_curtain(s, levels=4, **kw):
    """R_FACADE with spandrel = 0 : the same split rule as A7, degenerate."""
    ox, oy, _ = COND_ORIGIN
    for lv in range(levels):
        z0 = lv * CZ
        s.box(f"EN.WIN.CURT L{lv}", "Envelope", ox + CX - TG, ox + CX, oy, oy + CY, z0, z0 + CZ - TS,
              role="curtain", level=lv, symbol="EN.WIN.CURT")
        s.box(f"EN.SPAND CB L{lv} W", "Envelope", ox, ox + TE, oy, oy + CY, z0, z0 + CZ - TS,
              role="Bwall", level=lv)
    return ("B4 R_FACADE (spandrel = 0): the SAME facade split as A7 with the split height driven to zero, so "
            "the whole east face becomes one storey-high pane per level. Ribbon and curtain wall are one rule "
            "with one parameter - this is the strongest evidence that the two grammars share an alphabet.")


def B_core(s, levels=5, **kw):
    ox, oy, _ = COND_ORIGIN
    for lv in range(levels):
        z0 = lv * CZ
        s.box(f"CB CORE L{lv}", "Space", ox, ox + 8.9, oy + CY, oy + CY + 3.4, z0, z0 + CZ - TS,
              role="Bcore", level=lv, symbol="SP.STAIRWELL")
        s.box(f"CI.FLIGHT CB L{lv}", "Circulation", ox + 2.0, ox + 2.0 + 2.3, oy + CY + 0.3, oy + CY + 0.3 + STAIR_W,
              z0, z0 + H_TYP / 2, role="Bflight", level=lv, symbol="CI.FLIGHT")
        s.node(f"CBS{lv}", f"CB CORE L{lv}", (ox + 4.5, oy + CY + 1.7, z0 + 1.2))
        if lv:
            s.edge(f"CBS{lv-1}", f"CBS{lv}", "stair flight")
    s.edge("CBS1", "HALL", "core door")
    s.edge("CBS2", "GALLERY", "core door")
    return ("B5 R_CORE: a core strip is attached to the north face (ATTACH on a face port, not a split). "
            "It overshoots the roof by one level, which is what gives the condenser its roof terrace.")


def B_bridge(s, **kw):
    """R_BRIDGE  the one rule that belongs to BOTH grammars: it joins their graphs."""
    ox, oy, _ = COND_ORIGIN
    x0 = 0.0
    s.box("SP.BRIDGE", "Space", x0, x0 + 2.34, oy + CY + 3.4, 0.0, H_PIL, H_PIL + H_TYP - TS,
          role="bridge", symbol="SP.BRIDGE")
    s.node("BRIDGE", "SP.BRIDGE", (x0 + 1.2, (oy + CY + 3.4) / 2, H_PIL + 1.2))
    s.edge("CBS1", "BRIDGE", "door")
    s.edge("BRIDGE", "IFACE.BLOCK_L1_CORRIDOR", "door")
    # GLUING: the interface node is identified with the block's own street, so the two grammars'
    # graphs become one component (the same gluing GB6 performs on the graph side)
    street = sorted(n["id"] for n in s.nodes if n["label"].startswith("CORRIDOR L1"))
    if street:
        s.edge("IFACE.BLOCK_L1_CORRIDOR", street[0], "door")
    return ("B6 R_BRIDGE (the composition rule): a single volume at L1 linking the condenser core to the "
            "block's corridor. In the graph it is a CUT VERTEX - delete it and the design falls into two "
            "components. The two grammars are therefore composed by exactly one production, which is why they "
            "can be developed, and varied, independently.")


GRAMMAR_B = [("B0", "AXIOM", B_axiom), ("B1", "R_STACK", B_stack), ("B2", "R_MERGE (condenser)", B_merge),
             ("B3", "R_GALLERY", B_gallery), ("B4", "R_FACADE (curtain)", B_curtain),
             ("B5", "R_CORE", B_core), ("B6", "R_BRIDGE", B_bridge)]


# ---------------------------------------------------------------------------- Blender output
CAT_MAT = {"Mass": "Space", "Space": "Space", "Structure": "Concrete_Structure", "Division": "Concrete",
           "Envelope": "Concrete", "Circulation": "Concrete_Structure", "Opening": "Timber"}


def emit_cell(c, coll, offset=(0, 0, 0), name=None):
    g = c["geom"]
    nm = name or c["label"]
    if g[0] == "box":
        me = cuboid(nm, g[1], g[2], g[3], g[4], g[5], g[6])
    elif g[0] == "sect":
        me = prism(nm, g[3], "x", g[1], g[2])
    else:                                     # poly: (points, z0, z1)
        me = prism(nm, g[1], "z", g[2], g[3])
    mat = "Glass" if "WIN" in c.get("symbol", "") else CAT_MAT.get(c["cat"], "Concrete")
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(nm, me)
    ob.location = offset
    coll.objects.link(ob)
    ob["Category"] = c["cat"]
    ob["Role"] = c.get("role", "")
    if c.get("symbol"):
        ob["Symbol"] = c["symbol"]
    for k in ("level", "bay", "tag", "kind", "levels", "corridor_index", "line", "face"):
        if c.get(k) is not None:
            ob[k] = c[k]
    return ob


def emit_graph(state, coll, offset, scale=1.0, tag=""):
    """Nodes as small cubes, edges as a single line mesh - the paper's Figure 6/8 idiom."""
    pos = {n["id"]: Vector(n["pos"]) for n in state.nodes}
    for n in state.nodes:
        me = cuboid(f"N_{tag}{n['id']}", -0.22, 0.22, -0.22, 0.22, -0.22, 0.22)
        me.materials.append(MATS["Timber"])
        ob = bpy.data.objects.new(f"Node_{tag}{n['id']}", me)
        ob.location = Vector(offset) + pos[n["id"]] * scale
        coll.objects.link(ob)
        ob["GraphNode"] = n["label"]
    verts, edges = [], []
    for e in state.edges:
        if e["a"] in pos and e["b"] in pos:
            verts += [pos[e["a"]] * scale, pos[e["b"]] * scale]
            edges.append((len(verts) - 2, len(verts) - 1))
    me = bpy.data.meshes.new(f"Edges_{tag}")
    me.from_pydata([tuple(v) for v in verts], edges, [])
    ob = bpy.data.objects.new(f"Edges_{tag}", me)
    ob.location = offset
    coll.objects.link(ob)
    return len(state.nodes), len(state.edges)


def run_derivation(name, rules, parent, state=None, offset_step=(0, -34.0, 0), graph_offset=(0, 0, 24.0),
                   params=None, log=None):
    s = state or State()
    steps = []
    for k, (rid, rname, fn) in enumerate(rules):
        note = fn(s, **(params or {})) if params else fn(s)
        coll = bpy.data.collections.new(f"{name}_Step{k:02d}_{rid.replace(' ', '')}")
        parent.children.link(coll)
        off = Vector(offset_step) * k
        for c in s.cells:
            emit_cell(c, coll, off)
        nn, ne = emit_graph(s, coll, Vector(off) + Vector(graph_offset), tag=f"{name}{k}_")
        label(f"{rid}  {rname}\n{nn} nodes / {ne} edges", Vector(off) + Vector((-10, -6, 0)), 1.1, coll,
              f"Label_{name}_{k}")
        steps.append(dict(step=k, rule=rid, name=rname, cells=len(s.cells), nodes=nn, edges=ne,
                          description=note if isinstance(note, str) else ""))
        if log is not None:
            log.append(f"{rid:3s} {rname:34s} cells {len(s.cells):5d}  graph {nn:4d}n/{ne:4d}e")
    return s, steps


# ---------------------------------------------------------------------------- rule cards
def rule_cards(parent):
    """Small LHS -> RHS demonstrations of the four rules the user asked to foreground."""
    cards = []
    y = 0.0
    W = 26.0

    def card(cid, title, lhs, rhs, note):
        nonlocal y
        coll = bpy.data.collections.new(f"Rule_{cid}")
        parent.children.link(coll)
        for side, cells, ox in (("LHS", lhs, 0.0), ("RHS", rhs, W * 0.55)):
            for (nm, me, mat) in cells:
                me.materials.append(MATS[mat])
                ob = bpy.data.objects.new(f"{cid}_{side}_{nm}", me)
                ob.location = (ox, y, 0)
                coll.objects.link(ob)
                ob["Rule"] = cid
                ob["Side"] = side
        label(f"{cid}   {title}", (0, y + 12.0, 0), 1.0, coll, f"RuleTitle_{cid}")
        label("LHS", (0, y - 2.2, 0), 0.7, coll, f"RuleLHS_{cid}")
        label("RHS", (W * 0.55, y - 2.2, 0), 0.7, coll, f"RuleRHS_{cid}")
        label(note, (0, y - 4.0, 0), 0.45, coll, f"RuleNote_{cid}")
        cards.append(dict(id=cid, title=title, note=note))
        y -= 20.0

    # R_FACADE : panel -> spandrel + ribbon
    h = H_TYP - TS
    card("R_FACADE", "facade split  panel -> EN.SPAND + EN.WIN.RIBBON (continuous)",
         [("panel", cuboid("m", 0, 2 * BAY, -TE / 2, TE / 2, 0, h), "Concrete")],
         [("spandrel", cuboid("m", 0, 2 * BAY, -TE / 2, TE / 2, 0, HS), "Concrete"),
          ("ribbon", cuboid("m", 0, 2 * BAY, -TG / 2, TG / 2, HS, h), "Glass")],
         "SPLIT-Z at h=1.00. The pane is NOT cut by the bay rule: one pane spans the whole facade.\n"
         "h is a parameter: h=0 gives EN.WIN.CURT (the condenser). Graph: unchanged.")

    # R_BAY : the pair
    card("R_BAY", "bay / party-wall PAIR  band -> 2 bays + party wall + column",
         [("band", cuboid("m", 0, 2 * BAY, 0, DEPTH, 0, h), "Space"),
          ("slab", cuboid("m", 0, 2 * BAY, 0, DEPTH, -TS, 0), "Concrete_Structure")],
         [("bay_W", cuboid("m", TE / 2, BAY - TE / 2, 0, DEPTH, 0, h), "Space"),
          ("bay_E", cuboid("m", BAY + TE / 2, 2 * BAY - TE / 2, 0, DEPTH, 0, h), "Space"),
          ("party_S", cuboid("m", BAY - TE / 2, BAY + TE / 2, 0, DEPTH / 2 - COL_Y / 2, 0, h), "Concrete"),
          ("party_N", cuboid("m", BAY - TE / 2, BAY + TE / 2, DEPTH / 2 + COL_Y / 2, DEPTH, 0, h), "Concrete"),
          ("column", cuboid("m", BAY - COL_X / 2, BAY + COL_X / 2, DEPTH / 2 - COL_Y / 2, DEPTH / 2 + COL_Y / 2, 0, h), "Concrete_Structure"),
          ("slab_W", cuboid("m", 0, BAY, 0, DEPTH, -TS, 0), "Concrete_Structure"),
          ("slab_E", cuboid("m", BAY, 2 * BAY, 0, DEPTH, -TS, 0), "Concrete_Structure")],
         "SPLIT-X at 3.66. Inseparable pair: the cut yields two bay slabs AND the party wall on the\n"
         "cut line, with CO.RECT absorbed into it (so the wall arrives in pieces). Graph: 1 node -> 2,\n"
         "joined by a BLIND edge - adjacent, not connected.")

    # R_CORRIDOR
    card("R_CORRIDOR", "corridor insertion  bay -> SP.CORRIDOR + dwelling band",
         [("bay", cuboid("m", 0, BAY, 0, DEPTH, 0, h), "Space")],
         [("corridor", cuboid("m", 0, BAY, 0, CORR, 0, h), "Space"),
          ("band", cuboid("m", 0, BAY, CORR + TC, DEPTH, 0, h), "Space"),
          ("corr_wall", prism("m", notched(0, BAY, 0, h, [(1.2, 1.2 + DW, DH)]), "y", CORR, CORR + TC), "Concrete")],
         "SPLIT-Y at 1.80 with DV.WALL.CORR on the cut. Graph: corridor nodes form an OPEN chain\n"
         "(the internal street); each dwelling gets exactly one 'entrance door' edge to it.")

    # R_LCELL / R_UCELL : the section family
    for (lv, ci, cid, ttl) in ((2, 0, "R_LCELL", "L-section cell (K-type): 2 levels, corridor at the BOTTOM"),
                               (3, 1, "R_UCELL", "U-section cell (F-type): 3 levels, corridor in the MIDDLE")):
        lhs = []
        for k in range(lv):
            lhs.append((f"bay_L{k}", cuboid("m", 0, BAY, 0, DEPTH, k * H_TYP, (k + 1) * H_TYP - TS), "Space"))
        lhs.append(("corridor", cuboid("m", 0, BAY, 0, CORR, ci * H_TYP, (ci + 1) * H_TYP - TS), "Concrete"))
        rhs = [("cell", prism("m", section(lv, ci), "x", 0, BAY), "Space"),
               ("corridor", cuboid("m", 0, BAY, 0, CORR, ci * H_TYP, (ci + 1) * H_TYP - TS), "Concrete"),
               ("stair", flight_mesh("m", 1.05, 2.5, H_TYP), "Concrete_Structure")]
        card(cid, ttl, lhs, rhs,
             f"{lv} stacked bays + the corridor at level {ci} MERGE into ONE dwelling. The section is the\n"
             f"bay rectangle minus the corridor notch -> {section_kind(lv, ci)}. The pierced level keeps only a\n"
             "1.58 m hall band beside the street. Graph: the stacked bay nodes COLLAPSE into one dwelling\n"
             "node; one corridor serves " + ("two" if lv == 2 else "three") + " floors.")

    # R_MERGE (condenser)
    card("R_MERGE", "social condenser  two storeys -> one double-height SP.HALL",
         [("L0", cuboid("m", 0, CX, 0, CY, 0, CZ - TS), "Space"),
          ("slab", cuboid("m", 0, CX, 0, CY, CZ - TS, CZ), "Concrete_Structure"),
          ("L1", cuboid("m", 0, CX, 0, CY, CZ, 2 * CZ - TS), "Space")],
         [("hall", cuboid("m", 0, CX, 0, CY, 0, 2 * CZ - TS), "Space")],
         "The INVERSE of R_STACK: delete the intermediate slab and UNION the storeys. Graph: two nodes\n"
         "collapse into one of high degree - the graph definition of a social condenser.")

    return cards


# ---------------------------------------------------------------------------- variants
def variants(parent):
    """The same rules, different parameters: the section family the graph grammar will later search."""
    out = []
    specs = [("V1", 2, 0, "L", "as built: K-type, 2 levels, corridor at the bottom"),
             ("V2", 3, 1, "U", "as built: F-type, 3 levels, corridor through the middle"),
             ("V3", 2, 1, "Gamma", "unbuilt: corridor at the TOP - the L flipped, access over the dwelling"),
             ("V4", 4, 1, "Z", "unbuilt: 4 levels, corridor at level 1 - a skip-stop section, one street per four floors")]
    x = 0.0
    coll = bpy.data.collections.new("Variants_SectionFamily")
    parent.children.link(coll)
    for (vid, lv, ci, kind, note) in specs:
        for b in range(3):
            me = prism(f"{vid}_cell{b}", section(lv, ci), "x", 0, BAY - TE)
            me.materials.append(MATS["Space"])
            ob = bpy.data.objects.new(f"{vid}_{kind}_cell{b}", me)
            ob.location = (x + b * BAY, 0, 0)
            coll.objects.link(ob)
            ob["Variant"] = vid
            ob["levels"] = lv
            ob["corridor_index"] = ci
            ob["kind"] = kind
        me = cuboid(f"{vid}_corr", 0, 3 * BAY, 0, CORR, ci * H_TYP, (ci + 1) * H_TYP - TS)
        me.materials.append(MATS["Timber"])
        ob = bpy.data.objects.new(f"{vid}_corridor", me)
        ob.location = (x, 0, 0)
        coll.objects.link(ob)
        label(f"{vid}  {kind}-section\nlevels={lv}, corridor level={ci}\n{note}", (x, -3.0, 0), 0.5, coll, f"VLabel_{vid}")
        out.append(dict(id=vid, levels=lv, corridor_index=ci, kind=kind, note=note,
                        dwellings_per_street=f"1 street serves {lv} floors"))
        x += 3 * BAY + 6.0
    return out


# ---------------------------------------------------------------------------- main
def build(out_path=None, json_path=None, md_path=None):
    clear()
    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    make_materials()
    root = bpy.data.collections.new("Narkomfin_Grammar")
    scn.collection.children.link(root)

    rc = bpy.data.collections.new("Rules")
    root.children.link(rc)
    cards = rule_cards(rc)

    ca = bpy.data.collections.new("Derivation_A_Block")  # steps march along -y
    root.children.link(ca)
    log_a = []
    sa, steps_a = run_derivation("A", GRAMMAR_A, ca, log=log_a)

    cb = bpy.data.collections.new("Derivation_B_Condenser")
    root.children.link(cb)
    log_b = []
    # Grammar B is derived INDEPENDENTLY (its own axiom, its own graph) and composed with A by R_BRIDGE
    # alone, through the interface node. That independence is the whole reason for splitting the grammar.
    sb, steps_b = run_derivation("B", GRAMMAR_B, cb, offset_step=(0, -26.0, 0),
                                 graph_offset=(0, 0, 16.0), log=log_b)

    cv = bpy.data.collections.new("Variants")
    root.children.link(cv)
    vars_ = variants(cv)

    print("\n--- GRAMMAR A: BLOCK ---")
    print("\n".join(log_a))
    print("\n--- GRAMMAR B: SOCIAL CONDENSER (continues on the final state of A) ---")
    print("\n".join(log_b))
    print(f"\nobjects: {len(bpy.data.objects)}")

    if json_path:
        with open(json_path, "w") as f:
            json.dump(dict(model="Dom Narkomfin", grammars=dict(
                A=dict(name="BLOCK", scope="the residential slab", steps=steps_a),
                B=dict(name="SOCIAL CONDENSER", scope="the communal block + the bridge that composes the two",
                       steps=steps_b)),
                rule_cards=cards, variants=vars_,
                parameters=dict(bay=BAY, depth=DEPTH, storey=H_TYP, pilotis=H_PIL, corridor_depth=CORR,
                                hall_band=HALL, spandrel=HS, bays=NBAY)), f, indent=2)
        print("wrote", json_path)
    if md_path:
        with open(md_path, "w") as f:
            f.write("# Dom Narkomfin — the grammar, in two parts\n\n")
            for tag, nm, steps in (("A", "BLOCK", steps_a), ("B", "SOCIAL CONDENSER", steps_b)):
                f.write(f"\n## Grammar {tag}: {nm}\n\n")
                for st in steps:
                    f.write(f"### {st['rule']} {st['name']}\n\n"
                            f"*{st['cells']} cells · graph {st['nodes']} nodes / {st['edges']} edges*\n\n{st['description']}\n\n")
            f.write("\n## Section family (the variant engine)\n\n| id | levels | corridor level | section | note |\n|---|---|---|---|---|\n")
            for v in vars_:
                f.write(f"| {v['id']} | {v['levels']} | {v['corridor_index']} | {v['kind']} | {v['note']} |\n")
        print("wrote", md_path)
    if out_path:
        bpy.ops.wm.save_as_mainfile(filepath=out_path)
        print("saved", out_path)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.abspath("DomNarkomfin_Grammar.blend"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    a, _ = ap.parse_known_args(argv)
    build(a.out, a.json, a.md)
