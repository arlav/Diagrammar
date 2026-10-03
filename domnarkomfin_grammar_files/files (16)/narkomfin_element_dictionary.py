"""
narkomfin_element_dictionary.py -- the ELEMENT DICTIONARY of the Dom Narkomfin
==============================================================================
The alphabet of the Topologic shape grammar: one canonical instance of every element type that
the building is made of, each in its OWN local coordinate frame (so LHS/RHS matching and
Topology.IsSimilar work without worrying about where it sits in the building), each carrying
its parameters and its labelled ports (attachment points) for rule writing.

Frames are canonical and consistent:
    slabs / plates   x 0..len,  y 0..depth,  z -t..0        (z=0 is the FINISHED FLOOR)
    walls            x 0..len,  y -t/2..t/2, z 0..h         (x = the run, y = the thickness)
    columns          centred on x=y=0,       z 0..h
    panes            x 0..w,    y -t/2..t/2, z 0..h
    spaces (voids)   x 0..len,  y 0..depth,  z 0..h

Output:
    DomNarkomfin_ElementDictionary.blend   catalogue, laid out in rows by category, with labels
                                           and port empties; every object named + tagged
    narkomfin_elements.json                the machine-readable dictionary
    narkomfin_elements.md                  the human-readable dictionary
Run:
    blender --background --python narkomfin_element_dictionary.py -- --out DICT.blend
    (or with the pip bpy module: python narkomfin_element_dictionary.py --out DICT.blend)
"""
import argparse, json, math, os, sys

import bpy
import bmesh

# ---------------------------------------------------------------- building constants (as built model)
BAY = 3.66          # structural bay
DEPTH = 9.90        # depth of the residential block
H_TYP = 2.80        # typical storey
H_PIL = 2.50        # pilotis storey
TS = 0.30           # slab
TE = 0.30           # exterior / party / core wall
TC = 0.20           # corridor wall
TT = 0.10           # partition
TG = 0.05           # single pane (glass or door leaf)
HS = 1.00           # spandrel height
DW, DH = 0.90, 2.10
WCW = 0.70
COL_X, COL_Y = 0.30, 0.40
PIL_R = 0.25
STAIR_W = 1.50
FT = 0.25

CAT_ORDER = ["Structure", "Envelope", "Division", "Circulation", "Opening", "Space"]
MAT_OF_CAT = {"Structure": "Concrete_Structure", "Envelope": "Concrete", "Division": "Concrete",
              "Circulation": "Concrete_Structure", "Opening": "Timber", "Space": "Space"}

MATS = {}


# ---------------------------------------------------------------- primitives (local frames)
def _mesh(name, verts, faces):
    bm = bmesh.new()
    bv = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        try:
            bm.faces.new([bv[i] for i in f])
        except ValueError:
            pass
    bm.faces.ensure_lookup_table()
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def prism(name, profile, axis, a0, a1):
    """Extrude a closed 2D polygon along an axis. axis 'z': (u,v)=(x,y); 'y': (x,z); 'x': (y,z)."""
    if a1 < a0:
        a0, a1 = a1, a0
    P = {"z": lambda u, v, a: (u, v, a), "y": lambda u, v, a: (u, a, v), "x": lambda u, v, a: (a, u, v)}[axis]
    n = len(profile)
    verts = [P(u, v, a0) for u, v in profile] + [P(u, v, a1) for u, v in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n, i + n])
    return _mesh(name, verts, faces)


def cuboid(name, x0, x1, y0, y1, z0, z1):
    return prism(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "z", z0, z1)


def cyl(name, r, z0, z1, seg=24):
    return prism(name, [(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg)) for i in range(seg)], "z", z0, z1)


def notched(u0, u1, v0, v1, notches):
    """Rectangle with notches cut up from the bottom edge - stays a simple polygon (genus 0)."""
    pts = [(u0, v0)]
    for nu0, nu1, nh in sorted(notches):
        pts += [(nu0, v0), (nu0, v0 + nh), (nu1, v0 + nh), (nu1, v0)]
    return pts + [(u1, v0), (u1, v1), (u0, v1)]


def arc(name, r_in, r_out, a0, a1, z0, z1, seg=24):
    a0, a1 = math.radians(a0), math.radians(a1)
    out = [(r_out * math.cos(a0 + (a1 - a0) * i / seg), r_out * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg + 1)]
    inn = [(r_in * math.cos(a0 + (a1 - a0) * i / seg), r_in * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg, -1, -1)]
    return prism(name, out + inn, "z", z0, z1)


def disc(name, r, a0, a1, z0, z1, seg=24):
    a0, a1 = math.radians(a0), math.radians(a1)
    return prism(name, [(r * math.cos(a0 + (a1 - a0) * i / seg), r * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg + 1)], "z", z0, z1)


def flight_mesh(name, w, run, rise, t=FT, axis="x"):
    """Solid straight flight: rises over `run` along `axis`, width w across, underside truncated."""
    d = t * run / rise
    prof = [(0.0, 0.0), (run, rise), (run, rise - t), (d, 0.0)]
    return prism(name, prof, "y" if axis == "x" else "x", 0.0, w)


# ---------------------------------------------------------------- the DICTIONARY
# ports: (name, (x, y, z), (dx, dy, dz)) -- an attachment point and the direction it faces.
def E(sym, name, cat, ifc, mesh_fn, params, ports, count, where, grammar):
    return dict(symbol=sym, name=name, category=cat, ifc=ifc, mesh=mesh_fn, params=params,
                ports=ports, count=count, where=where, grammar=grammar)


def dictionary():
    D = []

    # ---------------- STRUCTURE ----------------
    D.append(E("SL.BAY", "Bay floor slab", "Structure", "IfcSlab",
               lambda: cuboid("m", 0, BAY, 0, DEPTH, -TS, 0),
               dict(length=BAY, depth=DEPTH, thickness=TS),
               [("top", (BAY / 2, DEPTH / 2, 0), (0, 0, 1)), ("soffit", (BAY / 2, DEPTH / 2, -TS), (0, 0, -1)),
                ("edge_W", (0, DEPTH / 2, -TS / 2), (-1, 0, 0)), ("edge_E", (BAY, DEPTH / 2, -TS / 2), (1, 0, 0)),
                ("edge_S", (BAY / 2, 0, -TS / 2), (0, -1, 0)), ("edge_N", (BAY / 2, DEPTH, -TS / 2), (0, 1, 0))],
               110, "every bay of every level of the residential block",
               "the unit of horizontal subdivision; SPLIT-X of a slab band generates the bay rhythm"))

    D.append(E("SL.STRIP", "Partial slab strip (corridor / hall band)", "Structure", "IfcSlab",
               lambda: cuboid("m", 0, BAY, 0, 3.38, -TS, 0),
               dict(length=BAY, depth=3.38, thickness=TS),
               [("top", (BAY / 2, 1.69, 0), (0, 0, 1)), ("edge_N", (BAY / 2, 3.38, -TS / 2), (0, 1, 0))],
               16, "L4 of the F bays: the corridor + entrance-hall band, leaving the living room double height",
               "produced by SUBTRACT of a void volume from SL.BAY; the rule that makes the F duplex"))

    D.append(E("SL.BALC", "Balcony slab strip", "Structure", "IfcSlab",
               lambda: cuboid("m", 0, BAY, 0, 2.30, -TS, 0),
               dict(length=BAY, depth=2.30, thickness=TS),
               [("top", (BAY / 2, 1.15, 0), (0, 0, 1)), ("edge_N", (BAY / 2, 2.30, -TS / 2), (0, 1, 0)),
                ("parapet_seat", (BAY / 2, 0.10, 0), (0, 0, 1))],
               21, "L1 south side, the full length of the block",
               "OFFSET-Y of SL.BAY beyond the facade line; carries EN.PARAPET"))

    D.append(E("SL.BALC.SEMI", "Semicircular balcony", "Structure", "IfcSlab",
               lambda: disc("m", 2.40, 90, 270, -TS, 0),
               dict(radius=2.40, thickness=TS),
               [("top", (-1.2, 0, 0), (0, 0, 1)), ("wall_face", (0, 0, -TS / 2), (1, 0, 0))],
               4, "west gable, L2-L5",
               "a curved terminal: rotational rule applied to the end wall, not derivable by orthogonal splits"))

    D.append(E("SL.GALL", "Gallery slab with curved edge", "Structure", "IfcSlab",
               lambda: prism("m", [(0, 0), (10.65, 0), (10.65, 7.52)] +
                             [(10.65 - t * 6.74 / 20 * 20 / 20, 0) for t in []] +
                             [(10.65 - i * (10.65 - 3.91) / 20,
                               7.52 - 0.97 * math.sqrt(max(0.0, 1 - ((10.65 - i * (10.65 - 3.91) / 20 - (10.65 + 3.91) / 2) / ((10.65 - 3.91) / 2)) ** 2)))
                              for i in range(1, 20)] +
                             [(3.91, 7.52), (0, 7.52)], "z", -TS, 0),
               dict(length=10.65, depth=7.52, thickness=TS, bite="elliptical, 0.97 deep"),
               [("top", (5.3, 3.5, 0), (0, 0, 1)), ("curved_edge", (7.3, 7.52 - 0.97, -TS / 2), (0, 1, 0))],
               1, "condenser: the gallery over the double-height hall",
               "SUBTRACT of a curved void from a full slab; the only non-orthogonal horizontal element"))

    D.append(E("SL.ROOF", "Roof slab (bay)", "Structure", "IfcRoof",
               lambda: cuboid("m", 0, BAY, 0, DEPTH, -TS, 0),
               dict(length=BAY, depth=DEPTH, thickness=TS),
               [("top", (BAY / 2, DEPTH / 2, 0), (0, 0, 1))],
               25, "top of both blocks",
               "terminal: the last slab of a vertical repetition stops the STACK-Z rule"))

    D.append(E("CO.PIL", "Pilotis (round column)", "Structure", "IfcColumn",
               lambda: cyl("m", PIL_R, 0, H_PIL - TS),
               dict(diameter=2 * PIL_R, height=H_PIL - TS, profile="circular"),
               [("base", (0, 0, 0), (0, 0, -1)), ("head", (0, 0, H_PIL - TS), (0, 0, 1))],
               69, "ground floor, three rows at y = 8.72 / 12.41 / 16.20",
               "the free-standing terminal that lets the ground plane stay open; marks the pilotis storey"))

    D.append(E("CO.RECT", "Column (rectangular, in the party wall)", "Structure", "IfcColumn",
               lambda: cuboid("m", -COL_X / 2, COL_X / 2, -COL_Y / 2, COL_Y / 2, 0, H_TYP - TS),
               dict(width=COL_X, depth=COL_Y, height=H_TYP - TS, profile="rectangular"),
               [("base", (0, 0, 0), (0, 0, -1)), ("head", (0, 0, H_TYP - TS), (0, 0, 1)),
                ("wall_W", (-COL_X / 2, 0, (H_TYP - TS) / 2), (-1, 0, 0)), ("wall_E", (COL_X / 2, 0, (H_TYP - TS) / 2), (1, 0, 0))],
               352, "all upper levels, flush with the party walls on the same three rows",
               "the column absorbed into the division; walls are SPLIT by it (hence the _s0/_s1 pieces)"))

    D.append(E("CO.RND.INT", "Interior round column", "Structure", "IfcColumn",
               lambda: cyl("m", PIL_R, 0, H_TYP - TS),
               dict(diameter=2 * PIL_R, height=H_TYP - TS, profile="circular"),
               [("base", (0, 0, 0), (0, 0, -1)), ("head", (0, 0, H_TYP - TS), (0, 0, 1))],
               6, "condenser hall, in front of the glazed east face",
               "free column inside a space: does not divide it, so the graph keeps one node"))

    # ---------------- ENVELOPE ----------------
    D.append(E("EN.SPAND", "Spandrel band", "Envelope", "IfcWall",
               lambda: cuboid("m", 0, BAY, -TE / 2, TE / 2, 0, HS),
               dict(length=BAY, thickness=TE, height=HS),
               [("base", (BAY / 2, 0, 0), (0, 0, -1)), ("head", (BAY / 2, 0, HS), (0, 0, 1)),
                ("out", (BAY / 2, -TE / 2, HS / 2), (0, -1, 0)), ("in", (BAY / 2, TE / 2, HS / 2), (0, 1, 0))],
               "≈180 pieces", "both long facades of both blocks, every level",
               "lower half of the SPLIT-Z of a facade panel; pairs with EN.WIN.RIBBON"))

    D.append(E("EN.WIN.RIBBON", "Ribbon window (single pane)", "Envelope", "IfcWindow",
               lambda: cuboid("m", 0, BAY, -TG / 2, TG / 2, 0, H_TYP - TS - HS),
               dict(length=BAY, thickness=TG, height=H_TYP - TS - HS, glazing="single pane, full bay"),
               [("base", (BAY / 2, 0, 0), (0, 0, -1)), ("head", (BAY / 2, 0, H_TYP - TS - HS), (0, 0, 1)),
                ("out", (BAY / 2, -TG / 2, (H_TYP - TS - HS) / 2), (0, -1, 0))],
               "≈200 panes", "both long facades, continuous from party wall to party wall",
               "upper half of the facade SPLIT-Z; the rule keeps it CONTINUOUS across bays, which is the "
               "signature of the style - a bay-wise pane would be the wrong grammar"))

    D.append(E("EN.WIN.CURT", "Curtain wall (storey-high pane)", "Envelope", "IfcWindow",
               lambda: cuboid("m", 0, 10.56, -TG / 2, TG / 2, 0, H_TYP - TS),
               dict(length=10.56, thickness=TG, height=H_TYP - TS),
               [("base", (5.28, 0, 0), (0, 0, -1)), ("out", (5.28, -TG / 2, (H_TYP - TS) / 2), (0, -1, 0))],
               5, "condenser east face, one pane per storey (fully glazed)",
               "degenerate case of the facade SPLIT-Z with spandrel = 0; the 'social condenser' reading"))

    D.append(E("EN.WIN.CURVED", "Curved glazing", "Envelope", "IfcWindow",
               lambda: arc("m", 3.16 - TG / 2, 3.16 + TG / 2, -90, 90, 0, H_PIL - TS),
               dict(radius=3.16, thickness=TG, height=H_PIL - TS, sweep=180),
               [("base", (0, 0, 0), (0, 0, -1)), ("chord", (0, 0, (H_PIL - TS) / 2), (-1, 0, 0))],
               3, "ground-floor lobby (apse) and the east entrance vestibule",
               "rotational terminal; the LHS is an orthogonal room corner, the RHS its curved replacement"))

    D.append(E("EN.WALL.END", "Blank end wall (gable)", "Envelope", "IfcWall",
               lambda: cuboid("m", 0, DEPTH, -TE / 2, TE / 2, 0, H_TYP - TS),
               dict(length=DEPTH, thickness=TE, height=H_TYP - TS),
               [("base", (DEPTH / 2, 0, 0), (0, 0, -1)), ("out", (DEPTH / 2, -TE / 2, (H_TYP - TS) / 2), (0, -1, 0)),
                ("corner_S", (0, 0, (H_TYP - TS) / 2), (0, 0, 0)), ("corner_N", (DEPTH, 0, (H_TYP - TS) / 2), (0, 0, 0))],
               12, "east and west gables of the block, all levels",
               "the boundary terminal: stops the repetition along x; may carry a door to SL.BALC.SEMI"))

    D.append(E("EN.PARAPET", "Parapet", "Envelope", "IfcWall",
               lambda: cuboid("m", 0, BAY, -0.10, 0.10, 0, 0.60),
               dict(length=BAY, thickness=0.20, height=0.60),
               [("base", (BAY / 2, 0, 0), (0, 0, -1))],
               "≈40 pieces", "roof edges of both blocks (1.20 m version on the L1 balcony)",
               "attaches to a slab edge port; the guard rule for any accessible horizontal surface"))

    D.append(E("EN.PARAPET.CURVED", "Curved parapet", "Envelope", "IfcWall",
               lambda: arc("m", 2.25, 2.40, 90, 270, 0, 1.10),
               dict(radius=2.40, thickness=0.15, height=1.10, sweep=180),
               [("base", (0, 0, 0), (0, 0, -1))],
               4, "the semicircular west balconies",
               "the same guard rule following a curved edge - shows the rule is edge-driven, not axis-driven"))

    # ---------------- DIVISION ----------------
    D.append(E("DV.WALL.PARTY", "Party wall", "Division", "IfcWall",
               lambda: cuboid("m", 0, DEPTH, -TE / 2, TE / 2, 0, H_TYP - TS),
               dict(length=DEPTH, thickness=TE, height=H_TYP - TS),
               [("base", (DEPTH / 2, 0, 0), (0, 0, -1)), ("head", (DEPTH / 2, 0, H_TYP - TS), (0, 0, 1)),
                ("face_W", (DEPTH / 2, -TE / 2, (H_TYP - TS) / 2), (0, -1, 0)), ("face_E", (DEPTH / 2, TE / 2, (H_TYP - TS) / 2), (0, 1, 0))],
               "≈150 pieces", "between dwellings, on the bay lines; blind (no openings)",
               "the DIVIDE-X operator made material: one party wall = one new node pair in the graph"))

    D.append(E("DV.WALL.CORE", "Core wall (with door)", "Division", "IfcWall",
               lambda: prism("m", notched(0, DEPTH, 0, H_TYP - TS, [(3.5, 3.5 + DW, DH)]), "x", -TE / 2, TE / 2),
               dict(length=DEPTH, thickness=TE, height=H_TYP - TS, opening=f"{DW} x {DH}"),
               [("base", (DEPTH / 2, 0, 0), (0, 0, -1)), ("door", (3.5 + DW / 2, 0, 0), (0, 1, 0))],
               "≈40 pieces", "around both stair cores, all levels",
               "same as DV.WALL.PARTY but with a door notch: the wall that a graph EDGE passes through"))

    D.append(E("DV.WALL.CORR", "Corridor wall (with entrance door)", "Division", "IfcWall",
               lambda: prism("m", notched(0, BAY, 0, H_TYP - TS, [(1.2, 1.2 + DW, DH)]), "y", -TC / 2, TC / 2),
               dict(length=BAY, thickness=TC, height=H_TYP - TS, opening=f"{DW} x {DH}"),
               [("base", (BAY / 2, 0, 0), (0, 0, -1)), ("door", (1.2 + DW / 2, 0, 0), (0, 1, 0)),
                ("face_corr", (BAY / 2, -TC / 2, (H_TYP - TS) / 2), (0, -1, 0)), ("face_unit", (BAY / 2, TC / 2, (H_TYP - TS) / 2), (0, 1, 0))],
               "≈40 pieces", "the internal street at L1 (y=12.41) and L4 (y=10.46)",
               "the SPLIT-Y that produces the corridor; one door per dwelling = one edge corridor->unit"))

    D.append(E("DV.WALL.PART", "Partition", "Division", "IfcWall",
               lambda: cuboid("m", 0, 3.00, -TT / 2, TT / 2, 0, H_TYP - TS),
               dict(length=3.00, thickness=TT, height=H_TYP - TS),
               [("base", (1.5, 0, 0), (0, 0, -1)), ("start", (0, 0, (H_TYP - TS) / 2), (-1, 0, 0)), ("end", (3.00, 0, (H_TYP - TS) / 2), (1, 0, 0))],
               "≈90 pieces", "inside the dwellings: bedroom, kitchen and bathroom divisions",
               "the light, non-structural DIVIDE inside a cell - free of the column grid, so it is the "
               "level where unit variants are generated"))

    D.append(E("DV.WALL.WC", "WC partition (paired doors)", "Division", "IfcWall",
               lambda: prism("m", notched(0, 2.00, 0, H_TYP - TS, [(0.20, 0.20 + WCW, DH), (1.10, 1.10 + WCW, DH)]), "x", -TT / 2, TT / 2),
               dict(length=2.00, thickness=TT, height=H_TYP - TS, openings=f"2 x {WCW} x {DH}"),
               [("base", (1.0, 0, 0), (0, 0, -1)), ("door_1", (0.20 + WCW / 2, 0, 0), (0, 1, 0)), ("door_2", (1.10 + WCW / 2, 0, 0), (0, 1, 0))],
               16, "the F dwellings' paired WC/shower off the entrance hall, L4",
               "a repeated micro-rule: the same partition serves two cells - a shared-service motif"))

    # ---------------- CIRCULATION ----------------
    D.append(E("CI.FLIGHT", "Stair flight (half storey)", "Circulation", "IfcStair",
               lambda: flight_mesh("m", STAIR_W, 2.30, H_TYP / 2),
               dict(width=STAIR_W, run=2.30, rise=H_TYP / 2, thickness=FT),
               [("foot", (0, STAIR_W / 2, 0), (-1, 0, 0)), ("head", (2.30, STAIR_W / 2, H_TYP / 2), (1, 0, 0))],
               "≈60", "both main cores, one pair per storey",
               "the vertical CONNECT operator; its two ports are what make a graph edge between levels"))

    D.append(E("CI.LANDING", "Stair landing", "Circulation", "IfcStair",
               lambda: cuboid("m", 0, 3.06, 0, 1.22, -TS, 0),
               dict(length=3.06, depth=1.22, thickness=TS),
               [("top", (1.53, 0.61, 0), (0, 0, 1)), ("arrive", (0, 0.61, -TS / 2), (-1, 0, 0)), ("depart", (3.06, 0.61, -TS / 2), (1, 0, 0))],
               "≈30", "half-landing of each dogleg",
               "the turn: two CI.FLIGHT plus one CI.LANDING = the dogleg composite"))

    D.append(E("CI.STAIR.K", "K-unit stair (one storey, straight)", "Circulation", "IfcStair",
               lambda: flight_mesh("m", 1.20, 2.59, H_TYP),
               dict(width=1.20, run=2.59, rise=H_TYP, thickness=FT),
               [("foot", (0, 0.60, 0), (-1, 0, 0)), ("head", (2.59, 0.60, H_TYP), (1, 0, 0))],
               8, "inside each K dwelling, L1 to L2, against the party wall",
               "the element that turns two stacked cells into ONE dwelling node: the K duplex rule"))

    D.append(E("CI.STAIR.F", "F-unit stair (one storey, straight)", "Circulation", "IfcStair",
               lambda: flight_mesh("m", 1.05, 2.50, H_TYP),
               dict(width=1.05, run=2.50, rise=H_TYP, thickness=FT),
               [("foot", (0, 0.52, 0), (-1, 0, 0)), ("head", (2.50, 0.52, H_TYP), (1, 0, 0))],
               32, "inside each F dwelling, L3->L4 and L4->L5",
               "applied twice per dwelling: the split-level F duplex that spans the corridor level"))

    # ---------------- OPENING ----------------
    D.append(E("OP.DOOR", "Door (single pane)", "Opening", "IfcDoor",
               lambda: cuboid("m", 0, DW, -TG / 2, TG / 2, 0, DH),
               dict(width=DW, height=DH, thickness=TG),
               [("hinge", (0, 0, DH / 2), (0, 0, 0)), ("axis", (DW / 2, 0, DH / 2), (0, 1, 0))],
               "≈95", "dwelling entrances, core doors, interior doors, balcony doors",
               "the OPENING terminal: it does not divide, it CONNECTS - every door is a graph edge"))

    D.append(E("OP.DOOR.WC", "WC door (single pane)", "Opening", "IfcDoor",
               lambda: cuboid("m", 0, WCW, -TG / 2, TG / 2, 0, DH),
               dict(width=WCW, height=DH, thickness=TG),
               [("hinge", (0, 0, DH / 2), (0, 0, 0)), ("axis", (WCW / 2, 0, DH / 2), (0, 1, 0))],
               "≈40", "WC / shower / bathroom",
               "narrow variant; the width is the only parameter that distinguishes service from habitable"))

    # ---------------- SPACE (the graph-side terminals) ----------------
    D.append(E("SP.CELL.K", "K dwelling volume (2 bays, 2 levels)", "Space", "IfcSpace",
               lambda: cuboid("m", 0, 2 * BAY, 0, DEPTH, 0, 2 * H_TYP - TS),
               dict(length=2 * BAY, depth=DEPTH, height=2 * H_TYP - TS, type="K: compact kitchen, no dining"),
               [("entrance", (0.8 * BAY, DEPTH / 2 - 1.2, 0), (0, -1, 0)), ("facade_S", (BAY, 0, 1.4), (0, -1, 0)), ("facade_N", (BAY, DEPTH, 1.4), (0, 1, 0))],
               8, "L1-L2, bays 3-18, in mirrored pairs",
               "the 2-bay x 2-level cell; MIRROR-X of this cell is the rule that makes the pair"))

    D.append(E("SP.CELL.F", "F dwelling volume (1 bay, 3 levels)", "Space", "IfcSpace",
               lambda: cuboid("m", 0, BAY, 0, DEPTH, 0, 3 * H_TYP - TS),
               dict(length=BAY, depth=DEPTH, height=3 * H_TYP - TS, type="F: duplex, no kitchen (communal dining)"),
               [("entrance", (0.5, DEPTH / 2 - 0.44, H_TYP), (0, -1, 0)), ("facade_S", (BAY / 2, 0, 1.4), (0, -1, 0)), ("facade_N", (BAY / 2, DEPTH, 1.4), (0, 1, 0))],
               16, "L3-L5, bays 3-18",
               "the 1-bay x 3-level cell entered from its MIDDLE level: the section that lets one corridor "
               "serve three floors - the key move of the whole building"))

    D.append(E("SP.CORRIDOR", "Corridor segment", "Space", "IfcSpace",
               lambda: cuboid("m", 0, BAY, 0, 1.29, 0, H_TYP - TS),
               dict(length=BAY, depth=1.29, height=H_TYP - TS),
               [("west", (0, 0.65, 1.2), (-1, 0, 0)), ("east", (BAY, 0.65, 1.2), (1, 0, 0)), ("unit", (BAY / 2, 1.29, 1.2), (0, 1, 0))],
               "2 streets", "L1 (K level) and L4 (F level), running the full 80 m",
               "the linear connector: a chain of segments whose end nodes attach to SP.STAIRWELL"))

    D.append(E("SP.STAIRWELL", "Stair core volume", "Space", "IfcSpace",
               lambda: cuboid("m", 0, BAY, 0, 5.01, 0, H_TYP - TS),
               dict(length=BAY, depth=5.01, height=H_TYP - TS),
               [("corridor", (BAY / 2, 0, 1.2), (0, -1, 0)), ("down", (BAY / 2, 3.0, 0), (0, 0, -1)), ("up", (BAY / 2, 3.0, H_TYP - TS), (0, 0, 1))],
               "2 cores x 7 levels", "bays 2 and 19, from the ground to the roof",
               "the only terminal with vertical ports: STACK-Z of stairwells is what makes the graph 3D"))

    D.append(E("SP.HALL", "Condenser hall (double height)", "Space", "IfcSpace",
               lambda: cuboid("m", 0, 10.05, 0, 9.96, 0, 2 * H_TYP - TS),
               dict(length=10.05, depth=9.96, height=2 * H_TYP - TS, programme="gymnasium / dining / library"),
               [("core", (5.0, 9.96, 1.2), (0, 1, 0)), ("entrance", (10.05, 5.0, 1.2), (1, 0, 0)), ("gallery", (5.0, 5.0, H_TYP), (0, 0, 1))],
               2, "condenser block: the collective volume, with a gallery on one side",
               "the social condenser: a single node of HIGH degree - the graph-level definition of 'collective'"))

    D.append(E("SP.BRIDGE", "Bridge / passage volume", "Space", "IfcSpace",
               lambda: cuboid("m", 0, 2.34, 0, 11.90, 0, H_TYP - TS),
               dict(length=2.34, depth=11.90, height=H_TYP - TS),
               [("block", (1.17, 11.90, 1.2), (0, 1, 0)), ("condenser", (1.17, 0, 1.2), (0, -1, 0))],
               1, "L1, from the corridor of the block to the condenser core",
               "the bridging edge: removing this one terminal disconnects the graph into two components"))

    return D


# ---------------------------------------------------------------- catalogue
def make_materials():
    def mat(name, rgba, alpha=1.0):
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*rgba, alpha)
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = (*rgba, 1.0)
            b.inputs["Alpha"].default_value = alpha
        if alpha < 1:
            for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
                try:
                    setattr(m, attr, val)
                except Exception:
                    pass
        MATS[name] = m
    mat("Concrete", (0.78, 0.77, 0.74))
    mat("Concrete_Structure", (0.55, 0.55, 0.57))
    mat("Glass", (0.55, 0.80, 0.95), alpha=0.35)
    mat("Timber", (0.55, 0.35, 0.18))
    mat("Space", (0.95, 0.72, 0.25), alpha=0.25)


def clear():
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    for f in list(bpy.data.curves):
        bpy.data.curves.remove(f)


def label(text, loc, size, coll, name):
    cu = bpy.data.curves.new(name, type="FONT")
    cu.body = text
    cu.size = size
    cu.align_x = "LEFT"
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def build_catalogue(out_path=None, json_path=None, md_path=None):
    clear()
    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    scn.unit_settings.length_unit = "METERS"
    make_materials()
    root = bpy.data.collections.new("Narkomfin_ElementDictionary")
    scn.collection.children.link(root)

    D = dictionary()
    by_cat = {c: [e for e in D if e["category"] == c] for c in CAT_ORDER}
    export = []
    rows = {}
    y_cursor = 0.0
    for cat in CAT_ORDER:
        items = by_cat[cat]
        if not items:
            continue
        ccol = bpy.data.collections.new(f"{CAT_ORDER.index(cat)+1:02d}_{cat}")
        root.children.link(ccol)
        # build the meshes first so the row can be packed by their real footprints
        built = []
        for e in items:
            me = e["mesh"]()
            mat = "Glass" if e["ifc"] == "IfcWindow" else MAT_OF_CAT[e["category"]]
            me.materials.append(MATS[mat])
            nm = f"{e['symbol']}_{e['name'].split('(')[0].strip().replace(' ', '')}"
            me.name = nm
            xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]
            built.append((e, me, nm, mat, min(xs), max(xs), min(ys), max(ys)))
        depth = max(b[7] - b[6] for b in built)
        row_y = y_cursor - depth / 2
        label(cat.upper(), (-9.0, row_y, 0), 1.4, ccol, f"CatLabel_{cat}")
        x_cursor = 0.0
        for idx, (e, me, nm, mat, x0, x1, y0, y1) in enumerate(built):
            ob = bpy.data.objects.new(nm, me)
            ob.location = (x_cursor - x0, row_y - (y0 + y1) / 2, 0)   # row-centred, packed left to right
            ccol.objects.link(ob)
            ob["Symbol"] = e["symbol"]; ob["ElementName"] = e["name"]; ob["Category"] = e["category"]
            ob["IfcClass"] = e["ifc"]; ob["Material"] = mat
            ob["Occurrences"] = str(e["count"]); ob["Where"] = e["where"]; ob["GrammarRole"] = e["grammar"]
            for k, v in e["params"].items():
                ob["p_" + k] = v
            ob["Ports"] = ", ".join(p[0] for p in e["ports"])
            for pname, loc, d in e["ports"]:
                em = bpy.data.objects.new(f"Port_{e['symbol']}_{pname}", None)
                em.empty_display_type = "SINGLE_ARROW" if any(d) else "PLAIN_AXES"
                em.empty_display_size = 0.5
                em.location = loc
                if any(d):
                    from mathutils import Vector
                    em.rotation_euler = Vector(d).to_track_quat("Z", "Y").to_euler()
                em.parent = ob
                em.matrix_parent_inverse = ob.matrix_world.inverted()
                em["Symbol"] = e["symbol"]; em["Port"] = pname; em["Direction"] = list(d)
                ccol.objects.link(em)
            label(f"{e['symbol']}\n{e['name']}", (x_cursor, row_y - depth / 2 - (0.9 if idx % 2 == 0 else 2.3), 0),
                  0.5, ccol, f"Label_{e['symbol']}")
            export.append(dict(symbol=e["symbol"], name=e["name"], category=e["category"], ifc=e["ifc"],
                               object=nm, params=e["params"],
                               ports=[dict(name=p[0], at=list(p[1]), faces=list(p[2])) for p in e["ports"]],
                               occurrences=e["count"], where=e["where"], grammar_role=e["grammar"],
                               catalogue_location=[round(v, 3) for v in ob.location]))
            x_cursor += (x1 - x0) + 2.2
        rows[cat] = (row_y, x_cursor, depth)
        y_cursor -= depth + 5.0
    with open("/home/claude/out2/rows.json", "w") as f:
        json.dump(rows, f)

    print(f"{len(D)} element types in {len([c for c in CAT_ORDER if by_cat[c]])} categories; objects: {len(bpy.data.objects)}")
    if json_path:
        with open(json_path, "w") as f:
            json.dump(dict(model="Dom Narkomfin (Ginzburg & Milinis, 1928-30)",
                           note="Element dictionary / alphabet of terminals for the Topologic shape+graph grammar. "
                                "Each element is in its own canonical local frame; see the module docstring.",
                           constants=dict(bay=BAY, depth=DEPTH, storey=H_TYP, pilotis_storey=H_PIL, slab=TS,
                                          wall_ext=TE, wall_corridor=TC, partition=TT, pane=TG, spandrel=HS),
                           elements=export), f, indent=2)
        print("wrote", json_path)
    if md_path:
        with open(md_path, "w") as f:
            f.write("# Dom Narkomfin - element dictionary\n\nThe alphabet of terminals for the shape + graph grammar. "
                    "Each element sits in its own canonical local frame in `DomNarkomfin_ElementDictionary.blend`, "
                    "tagged with its parameters and its ports.\n\n")
            f.write(f"Constants: bay {BAY} m, block depth {DEPTH} m, storey {H_TYP} m (pilotis {H_PIL} m), "
                    f"slab {TS}, exterior/party wall {TE}, corridor wall {TC}, partition {TT}, pane {TG}, spandrel {HS}.\n")
            for cat in CAT_ORDER:
                if not by_cat[cat]:
                    continue
                f.write(f"\n## {cat}\n\n| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |\n|---|---|---|---|---|---|---|\n")
                for e in by_cat[cat]:
                    par = ", ".join(f"{k} {v}" for k, v in e["params"].items())
                    f.write(f"| `{e['symbol']}` | {e['name']} | {e['ifc']} | {par} | {', '.join(p[0] for p in e['ports'])} | {e['count']} | {e['grammar']} |\n")
        print("wrote", md_path)
    if out_path:
        bpy.ops.wm.save_as_mainfile(filepath=out_path)
        print("saved", out_path)
    return D


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.abspath("DomNarkomfin_ElementDictionary.blend"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    a, _ = ap.parse_known_args(argv)
    build_catalogue(a.out, a.json, a.md)
