"""
build_narkomfin.py  --  Dom Narkomfin (Ginzburg & Milinis, 1928-30) element model generator
=============================================================================================
Builds a Blender scene with real (thick) slabs, columns, walls, stairs, single-pane windows and
doors, on the SAME coordinate frame as the abstract Topologic grammar model
("3d_Topologic_Model_Dom_Narkomfin__Full_Grammar_development.blend"):

    residential block  x 13.28 -> 93.80  (22 bays of 3.66 m),  y 7.52 -> 17.42 (9.90 m deep)
    condenser          x  6.07 -> 16.72,  y -16.04 -> -5.48 ; stair core y -5.48 -> -2.08
    bridge             x 13.28 -> 15.62,  y  -2.08 ->  9.82
    levels (top of slab) L0 0.00 | L1 2.50 | L2 5.30 | L3 8.10 | L4 10.90 | L5 13.70 | L6 16.50 | L7 21.00

Run inside Blender (Text editor > Run Script) or headless:
    blender --background --python build_narkomfin.py -- --out /path/DomNarkomfin_Elements.blend
or with the pip "bpy" module:  python build_narkomfin.py --out ...

Every object gets:  a unique name  <Class>_<Block>_L<level>_<descriptor>
                    custom properties  IfcClass, Block, Level, LevelName, Bay, Unit, Role, Material
                    a material         Concrete / Glass / Timber / Ground
All solids are closed, genus-0 meshes with no mutual overlaps (walls are split at columns,
door and stair openings are notches, never holes) so they can be turned into Topologic Cells.
"""
import bpy, bmesh, math, sys, os, argparse
from mathutils import Vector

# --------------------------------------------------------------------------------------- CONSTANTS
X0, BAY, NBAY = 13.28, 3.66, 22
XL = [round(X0 + BAY * i, 2) for i in range(NBAY + 1)]        # 23 column lines
YS, YN = 7.52, 17.42                                          # south / north faces of the block
Y_RS, Y_RC, Y_RN = 8.72, 12.41, 16.20                         # the three column rows
Y_BAL1 = 9.82                                                 # L1: balcony edge / corridor glazing
Y_COR4 = 10.46                                                # L4: F-corridor north wall
LEVELS = {0: 0.0, 1: 2.5, 2: 5.3, 3: 8.1, 4: 10.9, 5: 13.7, 6: 16.5, 7: 21.0}
LEVEL_NAMES = {0: "Ground (pilotis)", 1: "First (K lower / corridor 1)", 2: "Second (K upper)",
               3: "Third (F lower)", 4: "Fourth (F corridor)", 5: "Fifth (F upper)",
               6: "Roof / penthouse", 7: "Penthouse roof"}
TS = 0.30            # slab thickness
TE = 0.30            # exterior wall thickness (spandrel)
TP = 0.30            # party / core wall thickness
TC = 0.20            # corridor / hall wall thickness
TT = 0.10            # light partition thickness
TG = 0.05            # glass pane / door pane thickness
HS = 1.00            # spandrel (parapet-height solid band under the ribbon window)
COL_X, COL_Y = 0.30, 0.40   # rectangular column (x across party wall, y along it)
PIL_R = 0.25                # pilotis radius
DW, DH = 0.90, 2.10         # door leaf
WCW = 0.70                  # WC door
FT = 0.25                   # stair flight thickness (vertical)
CIRC_SEG = 24

# condenser
CX0, CX1, CY0, CY1 = 6.07, 16.72, -16.04, -5.48
KX1, KY1 = 15.62, -2.08                                   # condenser stair core x1, y1 (core y: CY1..KY1)
CB_LEVELS = [0.0, 2.5, 5.3, 8.4, 10.9]                    # condenser: ground, first, hall, gallery, roof
CB_CORE_TOP = 13.5
# bridge
BX0, BX1 = 13.28, 15.62
# penthouse
PX0, PX1, PY0, PY1 = 16.94, 46.22, 9.82, 17.42
# west balconies (L2-L5)
WB_CY, WB_R = 11.40, 2.40

COLX = {i: XL[i] for i in range(NBAY + 1)}                    # column centres per line (end lines pulled inside the end walls)
COLX[0] = round(XL[0] + TE + COL_X / 2, 3)
COLX[NBAY] = round(XL[NBAY] - TE - COL_X / 2, 3)

MATS = {}
COLLS = {}
STATS = {}


# --------------------------------------------------------------------------------------- HELPERS
def clear_scene():
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def make_materials():
    def mat(name, rgba, alpha=1.0):
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*rgba, alpha)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*rgba, 1.0)
            bsdf.inputs["Alpha"].default_value = alpha
            if alpha < 1:
                bsdf.inputs["Roughness"].default_value = 0.05
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
    mat("Ground", (0.35, 0.40, 0.30))


def coll(name, parent=None):
    if name in COLLS:
        return COLLS[name]
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    COLLS[name] = c
    return c


def new_object(name, verts, faces, collection, props, material):
    """Closed mesh from explicit verts/faces; normals recalculated outward."""
    if name in bpy.data.objects:
        raise ValueError("duplicate object name: " + name)
    bm = bmesh.new()
    bverts = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        try:
            bm.faces.new([bverts[i] for i in f])
        except ValueError:
            pass
    bm.faces.ensure_lookup_table()
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[material])
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    for k, v in props.items():
        ob[k] = v
    ob["Material"] = material
    STATS[props.get("IfcClass", "?")] = STATS.get(props.get("IfcClass", "?"), 0) + 1
    return ob


def extrude(name, profile, axis, a0, a1, collection, props, material):
    """Extrude a simple closed 2D polygon (u,v) along `axis` from a0 to a1.
       axis 'z': (u,v)=(x,y)   axis 'y': (u,v)=(x,z)   axis 'x': (u,v)=(y,z)"""
    if a1 < a0:
        a0, a1 = a1, a0
    def P(u, v, a):
        return {"z": (u, v, a), "y": (u, a, v), "x": (a, u, v)}[axis]
    n = len(profile)
    verts = [P(u, v, a0) for u, v in profile] + [P(u, v, a1) for u, v in profile]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n, i + n])
    return new_object(name, verts, faces, collection, props, material)


def box(name, x0, x1, y0, y1, z0, z1, collection, props, material):
    if x1 < x0: x0, x1 = x1, x0
    if y1 < y0: y0, y1 = y1, y0
    return extrude(name, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "z", z0, z1, collection, props, material)


def cylinder(name, cx, cy, r, z0, z1, collection, props, material, seg=CIRC_SEG):
    prof = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    return extrude(name, prof, "z", z0, z1, collection, props, material)


def arc_ring(name, cx, cy, r_in, r_out, ang0, ang1, z0, z1, collection, props, material, seg=CIRC_SEG):
    """Curved wall / parapet: annular sector between angles ang0..ang1 (degrees)."""
    a0, a1 = math.radians(ang0), math.radians(ang1)
    outer = [(cx + r_out * math.cos(a0 + (a1 - a0) * i / seg), cy + r_out * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg + 1)]
    inner = [(cx + r_in * math.cos(a0 + (a1 - a0) * i / seg), cy + r_in * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg, -1, -1)]
    return extrude(name, outer + inner, "z", z0, z1, collection, props, material)


def half_disc(name, cx, cy, r, ang0, ang1, z0, z1, collection, props, material, seg=CIRC_SEG):
    a0, a1 = math.radians(ang0), math.radians(ang1)
    prof = [(cx + r * math.cos(a0 + (a1 - a0) * i / seg), cy + r * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg + 1)]
    return extrude(name, prof, "z", z0, z1, collection, props, material)


def notched_profile(u0, u1, v0, v1, notches):
    """Rectangle [u0,u1]x[v0,v1] with notches [(nu0,nu1,nh),...] cut upward from the bottom edge v0.
       Stays a simple (genus-0) polygon."""
    pts = [(u0, v0)]
    for nu0, nu1, nh in sorted(notches):
        nu0, nu1 = max(nu0, u0), min(nu1, u1)
        if nu1 - nu0 < 0.05:
            continue
        pts += [(nu0, v0), (nu0, v0 + nh), (nu1, v0 + nh), (nu1, v0)]
    pts += [(u1, v0), (u1, v1), (u0, v1)]
    return pts


def split_intervals(u0, u1, cuts, min_len=0.12):
    """[u0,u1] minus the (c0,c1) intervals -> list of remaining intervals."""
    segs = [(u0, u1)]
    for c0, c1 in sorted(cuts):
        out = []
        for s0, s1 in segs:
            if c1 <= s0 or c0 >= s1:
                out.append((s0, s1))
            else:
                if c0 - s0 >= min_len: out.append((s0, c0))
                if s1 - c1 >= min_len: out.append((c1, s1))
        segs = out
    return segs


# ---- composite element builders ------------------------------------------------------------------
def wall(name, along, pos, u0, u1, z0, z1, thick, collection, props, doors=(), cuts=(), material="Concrete",
         door_h=DH):
    """Solid wall. along='x': runs along x at y=pos ; along='y': runs along y at x=pos.
       doors: [(du0,du1)] notches of height door_h from z0 ; cuts: [(c0,c1)] column exclusions.
       Returns list of wall pieces (door leaves are NOT created here)."""
    pieces = []
    full = [(d0, d1) for d0, d1 in doors if door_h >= (z1 - z0) - 1e-6]
    doors = [d for d in doors if d not in full]
    segs = split_intervals(u0, u1, list(cuts) + full)
    for k, (s0, s1) in enumerate(segs):
        seg_doors = [(d0, d1, door_h) for d0, d1 in doors if d0 >= s0 - 1e-6 and d1 <= s1 + 1e-6]
        prof = notched_profile(s0, s1, z0, z1, seg_doors)
        nm = name if len(segs) == 1 else f"{name}_s{k}"
        p = dict(props)
        p["Role"] = props.get("Role", "Wall")
        p["IfcClass"] = props.get("IfcClass") or "IfcWall"
        pieces.append(extrude(nm, prof, "y" if along == "x" else "x", pos - thick / 2, pos + thick / 2,
                              collection, p, material))
    return pieces


def door(name, along, pos, u0, u1, z0, collection, props, h=DH, material="Timber"):
    p = dict(props); p["IfcClass"] = "IfcDoor"
    if along == "x":
        return box(name, u0, u1, pos - TG / 2, pos + TG / 2, z0, z0 + h, collection, p, material)
    return box(name, pos - TG / 2, pos + TG / 2, u0, u1, z0, z0 + h, collection, p, material)


def facade(name, along, pos, u0, u1, z0, z1, collection, props, spandrel=HS, doors=(), glass=True, cuts=()):
    """Exterior wall = spandrel (solid) + ribbon window (single glass pane) up to the slab soffit.
       Doors notch both the spandrel and the pane. Returns (wall_pieces, pane_pieces, door_objs)."""
    wprops = dict(props); wprops["IfcClass"] = "IfcWall"; wprops["Role"] = props.get("Role", "Exterior")
    gprops = dict(props); gprops["IfcClass"] = "IfcWindow"; gprops["Role"] = "RibbonWindow"
    walls, panes, doors_o = [], [], []
    ztop_sp = min(z0 + spandrel, z1)
    if ztop_sp > z0 + 0.01:
        walls += wall(f"Wall_{name}", along, pos, u0, u1, z0, ztop_sp, TE, collection, wprops, doors=doors, cuts=cuts,
                      door_h=min(DH, ztop_sp - z0))
    if glass and z1 > ztop_sp + 0.05:
        segs = split_intervals(u0, u1, cuts)
        for k, (s0, s1) in enumerate(segs):
            notches = [(d0, d1, DH - spandrel) for d0, d1 in doors if d0 >= s0 - 1e-6 and d1 <= s1 + 1e-6 and DH > spandrel]
            prof = notched_profile(s0, s1, ztop_sp, z1, notches)
            nm = f"Window_{name}" + ("" if len(segs) == 1 else f"_s{k}")
            panes.append(extrude(nm, prof, "y" if along == "x" else "x", pos - TG / 2, pos + TG / 2, collection, gprops, "Glass"))
    for k, (d0, d1) in enumerate(doors):
        dp = dict(props); dp["Role"] = "ExteriorDoor"
        doors_o.append(door(f"Door_{name}" + ("" if len(doors) == 1 else f"_{k}"), along, pos, d0, d1, z0, collection, dp))
    return walls, panes, doors_o


def flight(name, along, w0, w1, s, e, z0, z1, collection, props, t=FT):
    """Straight stair flight as a solid: runs along `along` from s (level z0) to e (level z1),
       width across = [w0,w1]. Underside is truncated at z0 so it never dips into the slab below."""
    d = t * (e - s) / (z1 - z0)
    prof = [(s, z0), (e, z1), (e, z1 - t), (s + d, z0)]
    p = dict(props); p["IfcClass"] = "IfcStair"
    return extrude(name, prof, "x" if along == "y" else "y", w0, w1, collection, p, "Concrete_Structure")


def column(name, cx, cy, z0, z1, collection, props, round_=False):
    p = dict(props); p["IfcClass"] = "IfcColumn"
    if round_:
        p["Profile"] = "Circular D0.50"
        return cylinder(name, cx, cy, PIL_R, z0, z1, collection, p, "Concrete_Structure")
    p["Profile"] = "Rect 0.30x0.40"
    return box(name, cx - COL_X / 2, cx + COL_X / 2, cy - COL_Y / 2, cy + COL_Y / 2, z0, z1, collection, p, "Concrete_Structure")


def slab(name, poly, z0, z1, collection, props, material="Concrete", role="Slab"):
    p = dict(props); p["IfcClass"] = props.get("IfcClass") or "IfcSlab"; p["Role"] = role
    return extrude(name, poly, "z", z0, z1, collection, p, material)


def rect(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rect_minus_east_notch(x0, x1, y0, y1, ny0, ny1, nx0):
    """Rectangle with a notch cut from its east edge (x1) between ny0..ny1, back to nx0. Genus 0."""
    return [(x0, y0), (x1, y0), (x1, ny0), (nx0, ny0), (nx0, ny1), (x1, ny1), (x1, y1), (x0, y1)]


def rect_minus_west_notch(x0, x1, y0, y1, ny0, ny1, nx1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, ny1), (nx1, ny1), (nx1, ny0), (x0, ny0)]


# --------------------------------------------------------------------------------------- UNIT LAYOUT
def K_units():
    """8 K-type (2-bay) units, bays 3..18.  Pairs mirror about their shared party wall."""
    out = []
    for k in range(8):
        xl = round(24.26 + 7.32 * k, 2); xr = round(xl + 7.32, 2)
        side = "E" if k % 2 == 0 else "W"          # stair + entrance side
        out.append(dict(id=f"K{k+1:02d}", xl=xl, xr=xr, side=side, bays=(3 + 2 * k, 4 + 2 * k)))
    return out


def F_units():
    """16 F-type single-bay duplex units, bays 3..18. Stair against the east party wall."""
    return [dict(id=f"F{j+1:02d}", xl=XL[3 + j], xr=XL[4 + j], bay=3 + j) for j in range(16)]


UNITS_END_W = dict(id="EndW", xl=XL[0], xr=XL[2])
UNITS_END_E = dict(id="EndE", xl=XL[20], xr=XL[22])
CORE_W = dict(id="CoreW", xl=XL[2], xr=XL[3], bay=2)
CORE_E = dict(id="CoreE", xl=XL[19], xr=XL[20], bay=19)


def col_cuts_rows(rows=(Y_RS, Y_RC, Y_RN)):
    return [(r - COL_Y / 2, r + COL_Y / 2) for r in rows]


def col_cuts_lines(lines):
    return [(COLX[i] - COL_X / 2, COLX[i] + COL_X / 2) for i in lines]


def pil_cuts(centres, r=PIL_R + 0.05):
    return [(c - r, c + r) for c in centres]


# --------------------------------------------------------------------------------------- BUILD: RB
def build_residential():
    RB = coll("RB_ResidentialBlock", coll("DomNarkomfin"))
    L = LEVELS
    lc = {k: coll(f"RB_L{k}_{['Pilotis','First','Second','Third','Fourth','Fifth','Roof','PenthouseRoof'][k]}", RB) for k in range(8)}

    def P(level, bay=-1, unit="", role="", **kw):
        d = dict(IfcClass="", Block="RB", Level=level, LevelName=LEVEL_NAMES[level], Bay=bay, Unit=unit, Role=role)
        d.update(kw); return d

    Ks, Fs = K_units(), F_units()
    z_end = {k: L[k + 1] - TS for k in range(7)}       # top of walls / columns per level

    # ---------------- columns (all levels) ----------------
    for lvl in range(6):
        for i in range(23):
            for rname, ry in (("S", Y_RS), ("C", Y_RC), ("N", Y_RN)):
                cx = COLX[i]
                rnd = (lvl == 0) or (lvl == 1 and rname == "S" and 0 < i < 22)      # pilotis, and balcony columns
                column(f"Column_RB_L{lvl}_{rname}{i:02d}", cx, ry, L[lvl], z_end[lvl], lc[lvl],
                       P(lvl, bay=i, role="Pilotis" if lvl == 0 else "Column", Row=rname, Line=i), round_=rnd)

    # ---------------- slabs ----------------
    def bay_slab(lvl, i, poly, suffix="", unit="", role="Slab"):
        return slab(f"Slab_RB_L{lvl}_b{i:02d}{suffix}", poly, L[lvl] - TS, L[lvl], lc[lvl], P(lvl, bay=i, unit=unit, role=role))

    # core voids: stair core occupies y 13.7..17.42 in bays 2 and 19 (landing 12.41..13.7 stays)
    def core_bay_slab(lvl, i, y0):
        return bay_slab(lvl, i, rect(XL[i], XL[i + 1], y0, 13.70), unit="CoreW" if i == 2 else "CoreE", role="Slab+StairLanding")

    for i in range(22):
        x0, x1 = XL[i], XL[i + 1]
        # L1 : units/corridor slab + separate balcony strip (bay 0 south strip belongs to the bridge)
        if i in (2, 19):
            core_bay_slab(1, i, Y_BAL1)
        else:
            bay_slab(1, i, rect(x0, x1, Y_BAL1, YN))
        bx0 = max(x0, BX1)
        if x1 > BX1:
            slab(f"Balcony_RB_L1_b{i:02d}", rect(bx0, x1, YS, Y_BAL1), L[1] - TS, L[1], lc[1], P(1, bay=i, role="Balcony"))
        # L2 : full depth, K stair notches, core voids
        if i in (2, 19):
            core_bay_slab(2, i, YS)
        else:
            poly = rect(x0, x1, YS, YN)
            for K in Ks:
                if K["side"] == "E" and abs(K["xr"] - x1) < 1e-6:
                    poly = rect_minus_east_notch(x0, x1, YS, YN, 12.61, 15.20, x1 - 1.50)
                if K["side"] == "W" and abs(K["xl"] - x0) < 1e-6:
                    poly = rect_minus_west_notch(x0, x1, YS, YN, 12.61, 15.20, x0 + 1.50)
            bay_slab(2, i, poly)
        # L3 : full depth
        if i in (2, 19):
            core_bay_slab(3, i, YS)
        else:
            bay_slab(3, i, rect(x0, x1, YS, YN))
        # L4 : corridor+hall strip for F bays (living rooms are double height), full elsewhere
        if i in (2, 19):
            core_bay_slab(4, i, YS)
        elif 3 <= i <= 18:
            poly = [(x0, YS), (x1, YS), (x1, 12.90), (x1 - 1.35, 12.90), (x1 - 1.35, Y_RC), (x0, Y_RC)]
            bay_slab(4, i, poly, role="Slab (corridor+hall, void over living room)")
        else:
            bay_slab(4, i, rect(x0, x1, YS, YN))
        # L5 : full depth, F stair notches
        if i in (2, 19):
            core_bay_slab(5, i, YS)
        elif 3 <= i <= 18:
            bay_slab(5, i, rect_minus_east_notch(x0, x1, YS, YN, 12.90, 15.40, x1 - 1.35))
        else:
            bay_slab(5, i, rect(x0, x1, YS, YN))
        # L6 roof
        if i in (2, 19):
            core_bay_slab(6, i, YS)
        else:
            rp = P(6, bay=i, role="Roof"); rp["IfcClass"] = "IfcRoof"
            slab(f"Roof_RB_L6_b{i:02d}", rect(x0, x1, YS, YN), L[6] - TS, L[6], lc[6], rp, role="Roof")

    # west semicircular balconies L2-L5
    for lvl in range(2, 6):
        half_disc(f"Balcony_RB_L{lvl}_West", X0, WB_CY, WB_R, 90, 270, L[lvl] - TS, L[lvl], lc[lvl], P(lvl, bay=0, unit="EndW", role="Balcony", IfcClass="IfcSlab"), "Concrete")
        arc_ring(f"Parapet_RB_L{lvl}_West", X0, WB_CY, WB_R - 0.15, WB_R, 90, 270, L[lvl], L[lvl] + 1.10, lc[lvl], P(lvl, bay=0, unit="EndW", role="Parapet", IfcClass="IfcWall"), "Concrete")

    # ---------------- L1 balcony parapet + bridge passage partition ----------------
    for i in range(22):
        x0, x1 = max(XL[i], BX1), XL[i + 1]
        if x1 <= BX1: continue
        box(f"Parapet_RB_L1_b{i:02d}", x0, x1, YS, YS + 0.20, L[1], L[1] + 1.20, lc[1], P(1, bay=i, role="Parapet", IfcClass="IfcWall"), "Concrete")
    box("Parapet_RB_L1_EastEnd", XL[22] - 0.20, XL[22], YS + 0.20, Y_BAL1, L[1], L[1] + 1.20, lc[1], P(1, bay=21, role="Parapet", IfcClass="IfcWall"), "Concrete")

    # ---------------- exterior facades ----------------
    def face_segments(lvl, gapless=False):
        """[(u0,u1,unit,bay)] along x between party walls for the given level.
           gapless=True: no party walls cross this line (corridor glazing) -> contiguous pieces."""
        g = 0.0 if gapless else TP / 2
        segs = [(XL[0] + TE, XL[2] - g, "EndW", 0), (XL[2] + g, XL[3] - g, "CoreW", 2)]
        if lvl in (1, 2):
            segs += [(K["xl"] + g, K["xr"] - g, K["id"], K["bays"][0]) for K in Ks]
        else:
            segs += [(F["xl"] + g, F["xr"] - g, F["id"], F["bay"]) for F in Fs]
        segs += [(XL[19] + g, XL[20] - g, "CoreE", 19), (XL[20] + g, XL[22] - TE, "EndE", 20)]
        return segs

    for lvl in range(1, 6):
        z0, z1 = L[lvl], z_end[lvl]
        # north face
        for (u0, u1, unit, bay) in face_segments(lvl):
            facade(f"RB_L{lvl}_N_{unit}", "x", YN - TE / 2, u0, u1, z0, z1, lc[lvl], P(lvl, bay=bay, unit=unit, role="Exterior_N"))
        # south face
        if lvl == 1:
            # corridor glazing line at y=9.82 (balcony in front). Bay 0 west of the bridge passage stays open.
            for (u0, u1, unit, bay) in face_segments(1, gapless=True):
                u0 = max(u0, BX1)
                if u1 <= u0: continue
                if unit == "EndE":
                    facade(f"RB_L1_S_{unit}", "x", Y_BAL1 + TE / 2, u0, u1, z0, z1, lc[1], P(1, bay=bay, unit=unit, role="Exterior_S_corridorLine"))
                elif unit == "EndW":
                    # west end: passage partition + corridor glazing
                    facade(f"RB_L1_S_{unit}", "x", Y_BAL1 + TE / 2, u0, u1, z0, z1, lc[1], P(1, bay=bay, unit="Corridor1", role="Exterior_S_corridorLine"))
                else:
                    facade(f"RB_L1_S_{unit}", "x", Y_BAL1 + TE / 2, u0, u1, z0, z1, lc[1], P(1, bay=bay, unit="Corridor1", role="Exterior_S_corridorLine"))
        else:
            for (u0, u1, unit, bay) in face_segments(lvl, gapless=(lvl == 4)):
                if lvl == 4:   # corridor level: only the x=20.60 and x=86.48 core walls cross the corridor line
                    if bay in (0, 2): u1 = u1 - (TP / 2 if bay == 0 else 0.0)
                    if bay == 2: u0 = u0 + TP / 2
                    if bay == 19: u1 = u1 - TP / 2
                    if bay == 20: u0 = u0 + TP / 2
                facade(f"RB_L{lvl}_S_{unit}", "x", YS + TE / 2, u0, u1, z0, z1, lc[lvl], P(lvl, bay=bay, unit=unit if lvl != 4 else ("Corridor4" if 3 <= bay <= 18 else unit), role="Exterior_S"))
        # end faces
        wdoors = [(WB_CY - DW / 2, WB_CY + DW / 2)] if lvl >= 2 else []
        facade(f"RB_L{lvl}_W_EndW", "y", XL[0] + TE / 2, YS, YN, z0, z1, lc[lvl], P(lvl, bay=0, unit="EndW" if lvl != 1 else "Corridor1/EndW", role="Exterior_W"), doors=wdoors)
        ey0 = Y_BAL1 if lvl == 1 else YS
        facade(f"RB_L{lvl}_E_EndE", "y", XL[22] - TE / 2, ey0, YN, z0, z1, lc[lvl], P(lvl, bay=21, unit="EndE", role="Exterior_E"))

    # ---------------- party / core walls ----------------
    def party(lvl, x, y0, y1, unit, role="Party", doors=(), suffix=""):
        line = XL.index(round(x, 2)) if round(x, 2) in XL else -1
        cuts = [(max(c0, y0), min(c1, y1)) for c0, c1 in col_cuts_rows() if c1 > y0 + 1e-6 and c0 < y1 - 1e-6]
        return wall(f"Wall_RB_L{lvl}_{role}_x{x:05.2f}{suffix}", "y", x, y0, y1, L[lvl], z_end[lvl], TP, lc[lvl],
                    P(lvl, bay=line, unit=unit, role=role, Line=line), doors=doors, cuts=cuts)

    # L1: K party walls + core walls, y 12.41..17.42 ; east core / EndE wall down to the corridor line
    for K in Ks:
        party(1, K["xl"], Y_RC + TC / 2, YN, K["id"])
    party(1, XL[19], Y_RC + TC / 2, YN, "K08/CoreE")
    party(1, XL[2], Y_RC + TC / 2, YN, "EndW/CoreW", role="Core")
    party(1, XL[20], Y_BAL1 + TE, YN, "CoreE/EndE", role="Core", doors=[(10.5, 10.5 + DW)])
    # L2: full-depth K party walls, core walls
    for K in Ks:
        party(2, K["xl"], YS, YN, K["id"])
    party(2, XL[19], YS, YN, "K08/CoreE")
    party(2, XL[2], YS, YN, "EndW/LobbyW", role="Core", doors=[(10.5, 10.5 + DW)])
    party(2, XL[20], YS, YN, "LobbyE/EndE", role="Core", doors=[(10.5, 10.5 + DW)])
    # L3 & L5: every F party wall full depth
    for lvl in (3, 5):
        for i in range(3, 20):
            party(lvl, XL[i], YS, YN, f"F{i-2:02d}" if i < 19 else "F16/CoreE")
        party(lvl, XL[2], YS, YN, "EndW/LobbyW", role="Core", doors=[(10.5, 10.5 + DW)])
        party(lvl, XL[20], YS, YN, "LobbyE/EndE", role="Core", doors=[(10.5, 10.5 + DW)])
    # L4: party walls only north of the corridor (corridor is continuous); lobby openings at bays 2/19
    for i in range(3, 20):
        party(4, XL[i], Y_COR4 + TC / 2, YN, f"F{i-2:02d}" if i < 19 else "F16/CoreE")
    party(4, XL[2], YS, YN, "EndW/LobbyW", role="Core", doors=[(10.5, 10.5 + DW)])
    party(4, XL[20], YS, YN, "LobbyE/EndE", role="Core", doors=[(10.5, 10.5 + DW)])

    # ---------------- corridors & interior ----------------
    # L1 corridor north wall y=12.41 with all entrance doors
    doors1 = {1: [(18.5, 18.5 + DW)], 2: [(21.9, 21.9 + DW)], 19: [(84.2, 84.2 + DW)]}
    for K in Ks:
        if K["side"] == "E":
            d = (K["xr"] - 2.6, K["xr"] - 2.6 + DW)
        else:
            d = (K["xl"] + 1.7, K["xl"] + 1.7 + DW)
        b = int((d[0] - X0) // BAY)
        doors1.setdefault(b, []).append(d)
    for i in range(0, 20):
        x0, x1 = XL[i] + (TE if i == 0 else 0), XL[i + 1]
        unit = "EndW" if i < 2 else "CoreW" if i == 2 else "CoreE" if i == 19 else next(K["id"] for K in Ks if K["bays"][0] <= i <= K["bays"][1])
        w = wall(f"Wall_RB_L1_Corridor_b{i:02d}", "x", Y_RC, x0, x1, L[1], z_end[1], TC, lc[1],
                 P(1, bay=i, unit=unit, role="CorridorWall"), doors=doors1.get(i, []), cuts=col_cuts_lines([i, i + 1]))
        for k, d in enumerate(doors1.get(i, [])):
            door(f"Door_RB_L1_{unit}" + (f"_{k}" if len(doors1.get(i, [])) > 1 else ""), "x", Y_RC, d[0], d[1], L[1], lc[1], P(1, bay=i, unit=unit, role="EntranceDoor"))
    # L1 end-unit / core doors that sit in walls along y
    door("Door_RB_L1_EndE", "y", XL[20], 10.5, 10.5 + DW, L[1], lc[1], P(1, bay=20, unit="EndE", role="EntranceDoor"))
    # K stairs L1->L2 (+ partition and bathroom on L2)
    for K in Ks:
        if K["side"] == "E":
            w0, w1 = K["xr"] - 1.50, K["xr"] - TP / 2
            bx0, bx1 = K["xr"] - 2.0 - TP / 2, K["xr"] - TP / 2
        else:
            w0, w1 = K["xl"] + TP / 2, K["xl"] + 1.50
            bx0, bx1 = K["xl"] + TP / 2, K["xl"] + 2.0 + TP / 2
        flight(f"Stair_RB_{K['id']}_L1-L2", "y", w0, w1, 12.61, 15.20, L[1], L[2], lc[1], P(1, bay=K["bays"][0], unit=K["id"], role="UnitStair"))
        # L2: bedroom partition on the intermediate column line (south half); bathroom on the north face
        # beside the stair arrival (stair corner stays free), with its door on the south side
        xm = round(K["xl"] + BAY, 2)
        wall(f"Wall_RB_L2_{K['id']}_Bedroom", "y", xm, YS + TE, Y_RC - COL_Y / 2, L[2], z_end[2], TT, lc[2],
             P(2, bay=K["bays"][0], unit=K["id"], role="Partition"), cuts=col_cuts_rows((Y_RS,)))
        if K["side"] == "E":
            bx0, bx1 = xm + 0.20, K["xr"] - 1.55
        else:
            bx0, bx1 = K["xl"] + 1.55, xm - 0.20
        by0 = YN - TE - 2.2
        bd = (bx0 + 0.4, bx0 + 0.4 + WCW)
        wall(f"Wall_RB_L2_{K['id']}_BathS", "x", by0, bx0 - TT / 2, bx1 + TT / 2, L[2], z_end[2], TT, lc[2], P(2, bay=K["bays"][0], unit=K["id"], role="Partition"), doors=[bd])
        door(f"Door_RB_L2_{K['id']}_Bath", "x", by0, bd[0], bd[1], L[2], lc[2], P(2, bay=K["bays"][0], unit=K["id"], role="InteriorDoor"))
        for tag, bx in (("W", bx0), ("E", bx1)):
            wall(f"Wall_RB_L2_{K['id']}_Bath{tag}", "y", bx, by0 + TT / 2, YN - TE, L[2], z_end[2], TT, lc[2], P(2, bay=K["bays"][0], unit=K["id"], role="Partition"))

    # L2-L5 stair-lobby -> core doors (y=12.41 walls of both cores), core south walls
    for lvl in range(1, 7):
        for core, dx in ((CORE_W, 21.9), (CORE_E, 84.2)):
            if lvl == 1:
                continue   # at L1 this is the corridor wall (door already there)
            zt = z_end[lvl] if lvl < 6 else L[7] - TS
            wall(f"Wall_RB_L{lvl}_{core['id']}_S", "x", Y_RC, core["xl"] + TP / 2, core["xr"] - TP / 2, L[lvl], zt, TC, lc[lvl],
                 P(lvl, bay=core["bay"], unit=core["id"], role="CoreWall"), doors=[(dx, dx + DW)])
            door(f"Door_RB_L{lvl}_{core['id']}", "x", Y_RC, dx, dx + DW, L[lvl], lc[lvl], P(lvl, bay=core["bay"], unit=core["id"], role="StairDoor"))
    # doors in the y-walls between lobby and end units (L2-L5) and east core->EndE at L1 already done
    for lvl in range(2, 6):
        door(f"Door_RB_L{lvl}_EndW", "y", XL[2], 10.5, 10.5 + DW, L[lvl], lc[lvl], P(lvl, bay=2, unit="EndW", role="EntranceDoor"))
        door(f"Door_RB_L{lvl}_EndE", "y", XL[20], 10.5, 10.5 + DW, L[lvl], lc[lvl], P(lvl, bay=20, unit="EndE", role="EntranceDoor"))

    # main stair cores: dogleg per storey (flight A east side up to mid landing at north end, flight B back)
    for core in (CORE_W, CORE_E):
        xl_, xr_ = core["xl"] + 0.30, core["xr"] - 0.30      # clear of the pilotis at L0 too
        for lvl in range(6):
            z0, z1 = L[lvl], L[lvl + 1]
            zm = (z0 + z1) / 2
            flight(f"Stair_RB_{core['id']}_L{lvl}-L{lvl+1}_A", "y", xr_ - 1.50, xr_, 13.70, 16.00, z0, zm, lc[lvl], P(lvl, bay=core["bay"], unit=core["id"], role="CoreStair"))
            box(f"Stair_RB_{core['id']}_L{lvl}-L{lvl+1}_Landing", xl_, xr_, 16.00, YN - TE, zm - TS, zm, lc[lvl], P(lvl, bay=core["bay"], unit=core["id"], role="CoreStairLanding", IfcClass="IfcStair"), "Concrete_Structure")
            flight(f"Stair_RB_{core['id']}_L{lvl}-L{lvl+1}_B", "y", xl_, xl_ + 1.50, 16.00, 13.70, zm, z1, lc[lvl], P(lvl, bay=core["bay"], unit=core["id"], role="CoreStair"))

    # F units: L3/L5 partitions, L4 corridor wall, halls, WCs, stubs, stairs
    for F in Fs:
        xl, xr, b = F["xl"], F["xr"], F["bay"]
        for lvl in (3, 5):
            wall(f"Wall_RB_L{lvl}_{F['id']}_Kitchen", "x", Y_RC, xl + TP / 2, xr - 1.50, L[lvl], z_end[lvl], TT, lc[lvl], P(lvl, bay=b, unit=F["id"], role="Partition"))
        # L4
        wall(f"Wall_RB_L4_Corridor_b{b:02d}", "x", Y_COR4, xl + TP / 2, xr - TP / 2, L[4], z_end[4], TC, lc[4], P(4, bay=b, unit=F["id"], role="CorridorWall"), doors=[(xl + 0.5, xl + 0.5 + DW)])
        door(f"Door_RB_L4_{F['id']}", "x", Y_COR4, xl + 0.5, xl + 0.5 + DW, L[4], lc[4], P(4, bay=b, unit=F["id"], role="EntranceDoor"))
        wall(f"Wall_RB_L4_{F['id']}_Hall", "x", Y_RC, xl + TP / 2, xr - 1.35, L[4], z_end[4], TC, lc[4], P(4, bay=b, unit=F["id"], role="HallWall"))
        wx = xr - 1.65
        wall(f"Wall_RB_L4_{F['id']}_WC", "y", wx, Y_COR4 + TC / 2, Y_RC - TC / 2, L[4], z_end[4], TT, lc[4], P(4, bay=b, unit=F["id"], role="Partition"),
             doors=[(10.66, 10.66 + WCW), (11.50, 11.50 + WCW)])
        door(f"Door_RB_L4_{F['id']}_WC1", "y", wx, 10.66, 10.66 + WCW, L[4], lc[4], P(4, bay=b, unit=F["id"], role="InteriorDoor"))
        door(f"Door_RB_L4_{F['id']}_WC2", "y", wx, 11.50, 11.50 + WCW, L[4], lc[4], P(4, bay=b, unit=F["id"], role="InteriorDoor"))
        wall(f"Wall_RB_L4_{F['id']}_WCmid", "x", 11.40, wx + TT / 2, xr - TP / 2, L[4], z_end[4], TT, lc[4], P(4, bay=b, unit=F["id"], role="Partition"))
        flight(f"Stair_RB_{F['id']}_L3-L4", "y", xr - 1.35, xr - TP / 2, 15.40, 12.90, L[3], L[4], lc[3], P(3, bay=b, unit=F["id"], role="UnitStair"))
        flight(f"Stair_RB_{F['id']}_L4-L5", "y", xr - 1.35, xr - TP / 2, 12.90, 15.40, L[4], L[5], lc[4], P(4, bay=b, unit=F["id"], role="UnitStair"))

    # ---------------- ground floor enclosure (L0) ----------------
    z0, z1 = L[0], z_end[0]
    pil_x = lambda lines: pil_cuts([XL[i] for i in lines])
    pil_y = pil_cuts([Y_RS, Y_RC, Y_RN])
    G = lambda unit, role, bay=-1, **kw: P(0, bay=bay, unit=unit, role=role, **kw)
    # caretaker flat  x 16.94..20.60, y 9.88..16.20
    facade("RB_L0_W_Caretaker", "y", XL[1] + TE / 2, 9.88, Y_RN, z0, z1, lc[0], G("Caretaker", "Exterior_W", 1), cuts=pil_y)
    facade("RB_L0_S_Caretaker", "x", 9.88 + TE / 2, XL[1] + TE, XL[2] - TP / 2, z0, z1, lc[0], G("Caretaker", "Exterior_S", 1))
    facade("RB_L0_N_Caretaker", "x", Y_RN, XL[1] + TE, XL[2] - TP / 2, z0, z1, lc[0], G("Caretaker", "Exterior_N", 1), cuts=pil_x([1, 2]))
    # line 2: caretaker | vestibule + core
    wall("Wall_RB_L0_Core_x20.60", "y", XL[2], 9.88, YN - TE, z0, z1, TP, lc[0], G("Caretaker/Vestibule/CoreW", "Core", 2, Line=2), doors=[(10.5, 10.5 + DW)], cuts=pil_y)
    door("Door_RB_L0_Caretaker", "y", XL[2], 10.5, 10.5 + DW, z0, lc[0], G("Caretaker", "EntranceDoor", 2))
    # vestibule (bay 2, y 9.88..12.41): entrance in its south wall
    facade("RB_L0_S_Vestibule", "x", 9.88 + TE / 2, XL[2] + TP / 2, XL[3] - TP / 2, z0, z1, lc[0], G("Vestibule", "Exterior_S", 2), doors=[(21.9, 21.9 + DW)])
    wall("Wall_RB_L0_CoreW_S", "x", Y_RC, XL[2] + TP / 2, XL[3] - TP / 2, z0, z1, TC, lc[0], G("CoreW", "CoreWall", 2), doors=[(21.9, 21.9 + DW)], cuts=pil_x([2, 3]))
    door("Door_RB_L0_CoreW", "x", Y_RC, 21.9, 21.9 + DW, z0, lc[0], G("CoreW", "StairDoor", 2))
    facade("RB_L0_N_CoreW", "x", YN - TE / 2, XL[2] + TP / 2, XL[3] - TP / 2, z0, z1, lc[0], G("CoreW", "Exterior_N", 2))
    # line 3: vestibule | lobby  and core | lobby(toilets side)
    wall("Wall_RB_L0_Core_x24.26", "y", XL[3], 9.88, YN - TE, z0, z1, TP, lc[0], G("Vestibule/Lobby/CoreW", "Core", 3, Line=3), doors=[(10.5, 10.5 + DW)], cuts=pil_y)
    door("Door_RB_L0_Vestibule-Lobby", "y", XL[3], 10.5, 10.5 + DW, z0, lc[0], G("Lobby", "InteriorDoor", 3))
    # lobby  x 24.26..40.20 + semicircle (r 3.16) ; y 9.88..16.20
    LCX, LCY, LR = 40.20, 13.04, 3.16
    facade("RB_L0_S_Lobby", "x", 9.88 + TE / 2, XL[3] + TP / 2, LCX, z0, z1, lc[0], G("Lobby", "Exterior_S", 3), doors=[(25.5, 25.5 + DW)])
    facade("RB_L0_N_Lobby", "x", Y_RN, XL[3] + TP / 2, LCX, z0, z1, lc[0], G("Lobby", "Exterior_N", 3), cuts=pil_x([3, 4, 5, 6, 7]))
    arc_ring("Window_RB_L0_Lobby_Curved", LCX, LCY, LR - TG / 2, LR + TG / 2, -90, 90, z0, z1, lc[0], G("Lobby", "CurvedGlazing", 7, IfcClass="IfcWindow"), "Glass", seg=32)
    wall("Wall_RB_L0_Lobby_MidRow", "x", Y_RC, XL[4] - PIL_R, XL[7] - PIL_R, z0, z1, TC, lc[0], G("Lobby", "Partition", 4),
         doors=[(28.4, 28.4 + WCW), (30.2, 30.2 + WCW), (36.0, 36.0 + DW)], cuts=pil_x([4, 5, 6, 7]))
    door("Door_RB_L0_LobbyWC1", "x", Y_RC, 28.4, 28.4 + WCW, z0, lc[0], G("LobbyWC1", "InteriorDoor", 4))
    door("Door_RB_L0_LobbyWC2", "x", Y_RC, 30.2, 30.2 + WCW, z0, lc[0], G("LobbyWC2", "InteriorDoor", 4))
    door("Door_RB_L0_LobbyService", "x", Y_RC, 36.0, 36.0 + DW, z0, lc[0], G("LobbyService", "InteriorDoor", 6))
    wall("Wall_RB_L0_LobbyWC_W", "y", XL[4], Y_RC + PIL_R + 0.05, Y_RN - PIL_R - 0.05, z0, z1, TT, lc[0], G("LobbyWC", "Partition", 4))
    wall("Wall_RB_L0_LobbyWC_mid", "y", 29.75, Y_RC + TC / 2, Y_RN - PIL_R - 0.05, z0, z1, TT, lc[0], G("LobbyWC", "Partition", 4))
    wall("Wall_RB_L0_LobbyWC_E", "y", XL[5], Y_RC + PIL_R + 0.05, Y_RN - PIL_R - 0.05, z0, z1, TT, lc[0], G("LobbyWC/LobbyService", "Partition", 5))
    wall("Wall_RB_L0_LobbyService_E", "y", XL[7], Y_RC + PIL_R + 0.05, Y_RN - PIL_R - 0.05, z0, z1, TT, lc[0], G("LobbyService", "Partition", 7))
    # east core + curved vestibule (bay 19)
    ECX, ECY, ER = 84.65, 11.63, 1.83
    for ang in ((180, 256), (284, 360)):
        arc_ring(f"Window_RB_L0_VestibuleE_Curved_{ang[0]}", ECX, ECY, ER - TG / 2, ER + TG / 2, ang[0], ang[1], z0, z1, lc[0], G("VestibuleE", "CurvedGlazing", 19, IfcClass="IfcWindow"), "Glass", seg=16)
    door("Door_RB_L0_VestibuleE_Entrance", "x", ECY - ER * math.sin(math.radians(76)), ECX - ER * math.cos(math.radians(76)) - 0.0, ECX + ER * math.cos(math.radians(76)), z0, lc[0], G("VestibuleE", "ExteriorDoor", 19))
    wall("Wall_RB_L0_Core_x82.82", "y", XL[19], ECY, YN - TE, z0, z1, TP, lc[0], G("VestibuleE/CoreE", "Core", 19, Line=19), cuts=pil_y)
    wall("Wall_RB_L0_Core_x86.48", "y", XL[20], ECY, YN - TE, z0, z1, TP, lc[0], G("VestibuleE/CoreE", "Core", 20, Line=20), cuts=pil_y)
    wall("Wall_RB_L0_CoreE_S", "x", Y_RC, XL[19] + TP / 2, XL[20] - TP / 2, z0, z1, TC, lc[0], G("CoreE", "CoreWall", 19), doors=[(84.2, 84.2 + DW)], cuts=pil_x([19, 20]))
    door("Door_RB_L0_CoreE", "x", Y_RC, 84.2, 84.2 + DW, z0, lc[0], G("CoreE", "StairDoor", 19))
    facade("RB_L0_N_CoreE", "x", YN - TE / 2, XL[19] + TP / 2, XL[20] - TP / 2, z0, z1, lc[0], G("CoreE", "Exterior_N", 19))

    # ---------------- roof level: parapets, penthouse, east stair tower ----------------
    R6 = lc[6]
    par = lambda n, x0, x1, y0, y1: box(n, x0, x1, y0, y1, L[6], L[6] + 0.60, R6, P(6, role="Parapet", IfcClass="IfcWall"), "Concrete")
    par("Parapet_RB_L6_S", XL[0], XL[22], YS, YS + 0.20)
    par("Parapet_RB_L6_W", XL[0], XL[0] + 0.20, YS + 0.20, YN)
    par("Parapet_RB_L6_E", XL[22] - 0.20, XL[22], YS + 0.20, YN)
    par("Parapet_RB_L6_N_a", XL[0] + 0.20, PX0, YN - 0.20, YN)
    par("Parapet_RB_L6_N_b", PX1, XL[19] - TP / 2, YN - 0.20, YN)
    par("Parapet_RB_L6_N_c", XL[20] + TP / 2, XL[22] - 0.20, YN - 0.20, YN)
    # penthouse
    def PH(role, **kw):
        d = dict(IfcClass="", Block="PH", Level=6, LevelName=LEVEL_NAMES[6], Bay=-1, Unit="Penthouse", Role=role); d.update(kw); return d
    z0, z1 = L[6], L[7] - TS
    facade("PH_L6_W", "y", PX0 + TE / 2, PY0, PY1, z0, z1, R6, PH("Exterior_W"))
    facade("PH_L6_E", "y", PX1 - TE / 2, PY0, PY1, z0, z1, R6, PH("Exterior_E"))
    facade("PH_L6_S", "x", PY0 + TE / 2, PX0 + TE, PX1 - TE, z0, z1, R6, PH("Exterior_S"), doors=[(30.0, 30.0 + DW)])
    facade("PH_L6_N", "x", PY1 - TE / 2, PX0 + TE, PX1 - TE, z0, z1, R6, PH("Exterior_N"))
    rp = PH("Roof"); rp["IfcClass"] = "IfcRoof"; rp["Level"] = 7
    slab("Roof_PH_L7", rect(PX0, PX1, PY0, PY1), L[7] - TS, L[7], lc[7], rp, role="Roof")
    # west core inside the penthouse (walls only; the L6 landing sits on the roof slab)
    for x in (XL[2], XL[3]):
        wall(f"Wall_PH_L6_CoreW_x{x:05.2f}", "y", x, Y_RC + TC / 2, PY1 - TE, z0, z1, TP, R6, PH("Core", Unit="CoreW"))
    # east stair tower
    def TW(role, **kw):
        d = dict(IfcClass="", Block="RB", Level=6, LevelName=LEVEL_NAMES[6], Bay=19, Unit="CoreE", Role=role); d.update(kw); return d
    wall("Wall_RB_L6_CoreE_x82.82", "y", XL[19], Y_RC - TC / 2, YN, z0, z1, TP, R6, TW("Core"))
    wall("Wall_RB_L6_CoreE_x86.48", "y", XL[20], Y_RC - TC / 2, YN, z0, z1, TP, R6, TW("Core"))
    facade("RB_L6_N_CoreE", "x", YN - TE / 2, XL[19] + TP / 2, XL[20] - TP / 2, z0, z1, R6, TW("Exterior_N"))
    rp = TW("Roof"); rp["IfcClass"] = "IfcRoof"; rp["Level"] = 7
    slab("Roof_RB_L7_CoreE", rect(XL[19] - TP / 2, XL[20] + TP / 2, Y_RC - TC / 2, YN), L[7] - TS, L[7], lc[7], rp, role="Roof")


# --------------------------------------------------------------------------------------- BUILD: CB
def build_condenser():
    CB = coll("CB_Condenser", coll("DomNarkomfin"))
    lc = {0: coll("CB_L0_Ground", CB), 1: coll("CB_L1_First", CB), 2: coll("CB_L2_Hall", CB), 3: coll("CB_L3_Gallery", CB), 4: coll("CB_Roof", CB)}
    names = {0: "Ground", 1: "First", 2: "Hall (double height)", 3: "Gallery", 4: "Roof"}
    def P(lvl, unit, role, **kw):
        d = dict(IfcClass="", Block="CB", Level=lvl, LevelName=names[lvl], Bay=-1, Unit=unit, Role=role); d.update(kw); return d
    Z = CB_LEVELS
    storeys = [(0, Z[0], Z[1] - TS), (1, Z[1], Z[2] - TS), (2, Z[2], Z[3] - TS), (3, Z[3], Z[4] - TS)]
    # slabs
    slab("Slab_CB_L1", rect(CX0, CX1, CY0, CY1), Z[1] - TS, Z[1], lc[1], P(1, "Hall", "Slab"))
    slab("Slab_CB_L2", rect(CX0, CX1, CY0, CY1), Z[2] - TS, Z[2], lc[2], P(2, "Hall", "Slab"))
    # gallery slab with the curved edge (from the grammar model's Condenser_Slab)
    gal = [(CX0, CY0), (CX1, CY0), (CX1, -8.52)]
    seg = 20
    for i in range(1, seg):
        t = i / seg
        x = CX1 - t * (CX1 - 9.98)
        # elliptical bite: apex at (13.35,-9.49)
        cxm, a = (CX1 + 9.98) / 2, (CX1 - 9.98) / 2
        y = -8.52 - 0.97 * math.sqrt(max(0.0, 1 - ((x - cxm) / a) ** 2))
        gal.append((x, y))
    gal += [(9.98, -8.52), (CX0, -8.52)]
    slab("Slab_CB_L3_Gallery", gal, Z[3] - TS, Z[3], lc[3], P(3, "Gallery", "Slab (gallery over hall)"))
    rp = P(4, "Hall", "Roof"); rp["IfcClass"] = "IfcRoof"
    slab("Roof_CB", rect(CX0, CX1, CY0, CY1), Z[4] - TS, Z[4], lc[4], rp, role="Roof")
    rp = P(4, "CoreCB", "Roof"); rp["IfcClass"] = "IfcRoof"
    slab("Roof_CB_Core", rect(CX0, KX1, CY1, KY1), CB_CORE_TOP - TS, CB_CORE_TOP, lc[4], rp, role="Roof")
    # core landings (east end) per level + mid landings (west end)
    core_levels = [(0, Z[0]), (1, Z[1]), (2, Z[2]), (3, Z[3]), (4, Z[4])]
    for k, (lvl, z) in enumerate(core_levels):
        if k > 0:
            box(f"Stair_CB_Core_L{lvl}_Landing", 12.5, KX1 - TE, CY1 + TC / 2, KY1 - TE, z - TS, z, lc[min(lvl, 4)], P(lvl, "CoreCB", "CoreStairLanding", IfcClass="IfcStair"), "Concrete_Structure")
        if k < len(core_levels) - 1:
            z1 = core_levels[k + 1][1]; zm = (z + z1) / 2
            flight(f"Stair_CB_Core_L{lvl}-L{lvl+1}_A", "x", CY1 + TC / 2, CY1 + TC / 2 + 1.40, 12.5, 8.5, z, zm, lc[lvl], P(lvl, "CoreCB", "CoreStair"))
            box(f"Stair_CB_Core_L{lvl}-L{lvl+1}_MidLanding", CX0 + TE, 8.5, CY1 + TC / 2, KY1 - TE, zm - TS, zm, lc[lvl], P(lvl, "CoreCB", "CoreStairLanding", IfcClass="IfcStair"), "Concrete_Structure")
            flight(f"Stair_CB_Core_L{lvl}-L{lvl+1}_B", "x", KY1 - TE - 1.40, KY1 - TE, 8.5, 12.5, zm, z1, lc[lvl], P(lvl, "CoreCB", "CoreStair"))
    # exterior walls per storey
    for lvl, z0, z1 in storeys:
        facade(f"CB_L{lvl}_W_Hall", "y", CX0 + TE / 2, CY0, CY1, z0, z1, lc[lvl], P(lvl, "Hall", "Exterior_W"))
        facade(f"CB_L{lvl}_S_Hall", "x", CY0 + TE / 2, CX0 + TE, CX1 - TE, z0, z1, lc[lvl], P(lvl, "Hall", "Exterior_S"))
        facade(f"CB_L{lvl}_N_HallE", "x", CY1 - TE / 2, KX1, CX1 - TE, z0, z1, lc[lvl], P(lvl, "Hall", "Exterior_N"))
        # fully glazed east face (single pane per storey), entrance door at ground
        gp = P(lvl, "Hall", "CurtainWall", IfcClass="IfcWindow")
        prof = notched_profile(CY0, CY1, z0, z1, [(-11.2, -11.2 + DW, DH)] if lvl == 0 else [])
        extrude(f"Window_CB_L{lvl}_E_Glazing", prof, "x", CX1 - TE / 2 - TG / 2, CX1 - TE / 2 + TG / 2, lc[lvl], gp, "Glass")
        if lvl == 0:
            door("Door_CB_L0_Entrance", "y", CX1 - TE / 2, -11.2, -11.2 + DW, z0, lc[0], P(0, "Hall", "ExteriorDoor"))
        # hall | core wall with door
        wall(f"Wall_CB_L{lvl}_Core_S", "x", CY1, CX0 + TE, KX1 - TE, z0, z1, TC, lc[lvl], P(lvl, "Hall/CoreCB", "CoreWall"), doors=[(12.6, 12.6 + DW)] if lvl != 2 else [])
        if lvl != 2:
            door(f"Door_CB_L{lvl}_Core", "x", CY1, 12.6, 12.6 + DW, z0, lc[lvl], P(lvl, "CoreCB", "StairDoor"))
    # core exterior walls (5 storeys, up to 12.6)
    core_storeys = storeys + [(4, Z[4], CB_CORE_TOP - TS)]
    for lvl, z0, z1 in core_storeys:
        facade(f"CB_L{lvl}_W_Core", "y", CX0 + TE / 2, CY1, KY1, z0, z1, lc[lvl], P(lvl, "CoreCB", "Exterior_W"))
        facade(f"CB_L{lvl}_E_Core", "y", KX1 - TE / 2, CY1 - TE, KY1 - TE, z0, z1, lc[lvl], P(lvl, "CoreCB", "Exterior_E"))
        facade(f"CB_L{lvl}_N_Core", "x", KY1 - TE / 2, CX0 + TE, KX1, z0, z1, lc[lvl], P(lvl, "CoreCB", "Exterior_N"),
               doors=[(13.9, 13.9 + DW)] if lvl == 1 else [])
    # roof-terrace door in the top storey of the core (south wall, above the hall roof)
    wall("Wall_CB_L4_Core_S", "x", CY1, CX0 + TE, KX1 - TE, Z[4], CB_CORE_TOP - TS, TC, lc[4], P(4, "CoreCB", "CoreWall"), doors=[(11.0, 11.0 + DW)])
    door("Door_CB_L4_RoofTerrace", "x", CY1, 11.0, 11.0 + DW, Z[4], lc[4], P(4, "CoreCB", "ExteriorDoor"))
    # ground floor toilets (x 6.07..8.77, three rooms)
    z0, z1 = Z[0], Z[1] - TS
    wall("Wall_CB_L0_WC_E", "y", 8.77, CY0 + TE, CY1 - TC / 2, z0, z1, TT, lc[0], P(0, "WC", "Partition"),
         doors=[(-14.7, -14.7 + WCW), (-11.2, -11.2 + WCW), (-7.7, -7.7 + WCW)])
    for k, y in enumerate((-14.7, -11.2, -7.7)):
        door(f"Door_CB_L0_WC{k+1}", "y", 8.77, y, y + WCW, z0, lc[0], P(0, f"WC{k+1}", "InteriorDoor"))
    for k, y in enumerate((-12.52, -9.00)):
        wall(f"Wall_CB_L0_WC_mid{k+1}", "x", y, CX0 + TE, 8.77 - TT / 2, z0, z1, TT, lc[0], P(0, "WC", "Partition"))
    # interior round columns near the glazed face
    for lvl, z0, z1 in ((0, Z[0], Z[1] - TS), (1, Z[1], Z[2] - TS)):
        for k, y in enumerate((-8.94, -12.23)):
            column(f"Column_CB_L{lvl}_{k+1}", 15.40, y, z0, z1, lc[lvl], P(lvl, "Hall", "Column"), round_=True)
    column("Column_CB_L2_1", 15.40, -8.94, Z[2], Z[4] - TS, lc[2], P(2, "Hall", "Column (full height of hall)"), round_=True)
    column("Column_CB_L2_2", 15.40, -12.23, Z[2], Z[3] - TS, lc[2], P(2, "Hall", "Column"), round_=True)
    column("Column_CB_L3_2", 15.40, -12.23, Z[3], Z[4] - TS, lc[3], P(3, "Gallery", "Column"), round_=True)
    # roof parapets
    par = lambda n, x0, x1, y0, y1, zb, lvl: box(n, x0, x1, y0, y1, zb, zb + 0.60, lc[4], P(lvl, "Hall" if lvl == 4 else "CoreCB", "Parapet", IfcClass="IfcWall"), "Concrete")
    par("Parapet_CB_Roof_W", CX0, CX0 + 0.2, CY0, CY1, Z[4], 4)
    par("Parapet_CB_Roof_S", CX0 + 0.2, CX1, CY0, CY0 + 0.2, Z[4], 4)
    par("Parapet_CB_Roof_E", CX1 - 0.2, CX1, CY0 + 0.2, CY1, Z[4], 4)
    par("Parapet_CB_Roof_N", KX1, CX1 - 0.2, CY1 - 0.2, CY1, Z[4], 4)
    par("Parapet_CB_CoreRoof_W", CX0, CX0 + 0.2, CY1, KY1, CB_CORE_TOP, 4)
    par("Parapet_CB_CoreRoof_N", CX0 + 0.2, KX1, KY1 - 0.2, KY1, CB_CORE_TOP, 4)
    par("Parapet_CB_CoreRoof_E", KX1 - 0.2, KX1, CY1, KY1 - 0.2, CB_CORE_TOP, 4)
    par("Parapet_CB_CoreRoof_S", CX0 + 0.2, KX1 - 0.2, CY1, CY1 + 0.2, CB_CORE_TOP, 4)


# --------------------------------------------------------------------------------------- BUILD: bridge
def build_bridge():
    BR = coll("BR_Bridge", coll("DomNarkomfin"))
    def P(role, **kw):
        d = dict(IfcClass="", Block="BR", Level=1, LevelName=LEVEL_NAMES[1], Bay=0, Unit="Bridge", Role=role); d.update(kw); return d
    z0, z1 = LEVELS[1], LEVELS[2] - TS
    slab("Slab_BR_L1", rect(BX0, BX1, KY1, Y_BAL1), z0 - TS, z0, BR, P("Slab"))
    rp = P("Roof"); rp["IfcClass"] = "IfcRoof"
    slab("Roof_BR_L2", rect(BX0, BX1, KY1, YS), z1, z1 + TS, BR, rp, role="Roof")
    facade("BR_L1_W", "y", BX0 + TE / 2, KY1, YS, z0, z1, BR, P("Exterior_W"))
    facade("BR_L1_E", "y", BX1 - TE / 2, KY1, YS, z0, z1, BR, P("Exterior_E"))
    # passage partition inside the block (to the balcony), with door
    wall("Wall_BR_L1_PassageE", "y", BX1 - TE / 2, YS, Y_BAL1, z0, z1, TE, BR, P("Partition"), doors=[(YS + 0.4, YS + 0.4 + DW)])
    door("Door_BR_L1_Balcony", "y", BX1 - TE / 2, YS + 0.4, YS + 0.4 + DW, z0, BR, P("BalconyDoor"))
    # (the bridge door into the condenser core is Door_CB_L1_N_Core, built with the core's north facade)


# --------------------------------------------------------------------------------------- SITE
def build_site():
    S = coll("Site", coll("DomNarkomfin"))
    p = dict(IfcClass="IfcSlab", Block="SITE", Level=0, LevelName="Ground", Bay=-1, Unit="Site", Role="GroundSlab")
    slab("Slab_SITE_Ground", rect(-2.0, 102.0, -24.0, 26.0), -TS, 0.0, S, p, material="Ground")


# --------------------------------------------------------------------------------------- SPACES
def import_abstract_spaces(src_blend):
    """Append the abstract grammar cells (only the copy sitting on the main coordinate frame)."""
    if not (src_blend and os.path.exists(src_blend)):
        return 0
    with bpy.data.libraries.load(src_blend, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    SP = coll("Spaces_AbstractGrammar", coll("DomNarkomfin"))
    n = 0
    for ob in data_to.objects:
        if ob is None or ob.type != "MESH":
            continue
        pts = [ob.matrix_basis @ v.co for v in ob.data.vertices]
        if not pts:
            bpy.data.objects.remove(ob); continue
        ymin, ymax = min(p.y for p in pts), max(p.y for p in pts)
        base = ob.name.split(".")[0]
        keep = (-20 < ymin and ymax < 40) and base not in ("COLUMNS_mesh_", "Plane", "Text")
        if keep:
            ob.name = "Space_" + ob.name
            ob["IfcClass"] = "IfcSpace"; ob["Block"] = "RB" if ymin > 5 else ("CB" if ymax < 0 else "BR"); ob["Role"] = "AbstractGrammarCell"
            ob["Source"] = "3d_Topologic_Model_Dom_Narkomfin__Full_Grammar_development.blend"
            SP.objects.link(ob); n += 1
        else:
            bpy.data.objects.remove(ob)
    SP.hide_viewport = True; SP.hide_render = True
    return n


# --------------------------------------------------------------------------------------- MAIN
def build(out_path=None, spaces_from=None):
    clear_scene()
    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"; scn.unit_settings.length_unit = "METERS"
    make_materials()
    build_site()
    build_residential()
    build_condenser()
    build_bridge()
    n_sp = import_abstract_spaces(spaces_from)
    print("Element counts:", dict(sorted(STATS.items())), "| abstract spaces:", n_sp, "| objects:", len(bpy.data.objects))
    if out_path:
        bpy.ops.wm.save_as_mainfile(filepath=out_path)
        print("saved", out_path)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.abspath("DomNarkomfin_Elements.blend"))
    ap.add_argument("--spaces-from", default=None, help="original grammar .blend to append the abstract space cells from")
    a, _ = ap.parse_known_args(argv)
    build(a.out, a.spaces_from)
