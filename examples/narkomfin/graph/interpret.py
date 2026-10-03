"""
interpret.py -- graph -> shape, for the Dom Narkomfin pack
==========================================================
Every node carries enough in its dictionary (type, bay, level, levels, corridor_index) to say what
volume it stands for. `cells()` reads the nodes and returns one prism per node: the graph DRIVES the
shape. Non-terminals are interpreted too, so a derivation can be watched from the axiom prism onwards.

A prism is a closed profile and the axis it is extruded along:

    axis "x"   profile in (y, z), extruded from x = a0 to x = a1     sections
    axis "z"   profile in (x, y), extruded from z = a0 to z = a1     plans

This is the P1 stand-in for the shape grammar. From P2 the cells come from topologicpy.ShapeGrammar and
this module becomes the oracle they are checked against.
"""
import math


def section(levels, ci, d, pierced=True):
    """(y, z) profile of a dwelling of `levels` storeys whose level `ci` (0-based from the bottom) is
    pierced by the street: the bay rectangle minus the corridor notch.

        street at the bottom -> L      in the middle -> U / Z      at the top -> Gamma"""
    depth, corr, h, t = d["depth"], d["corridor"], d["storey"], d["slab"]
    top = levels * h - t
    if not pierced or not (0 <= ci < levels):
        return [(0.0, 0.0), (depth, 0.0), (depth, top), (0.0, top)]
    z0, z1 = ci * h, (ci + 1) * h - t
    if levels == 1:                                    # a flat beside the street
        return [(corr, 0.0), (depth, 0.0), (depth, top), (corr, top)]
    if ci == 0:
        return [(corr, 0.0), (depth, 0.0), (depth, top), (0.0, top), (0.0, z1), (corr, z1)]
    if ci == levels - 1:
        return [(0.0, 0.0), (depth, 0.0), (depth, top), (corr, top), (corr, z0), (0.0, z0)]
    return [(0.0, 0.0), (depth, 0.0), (depth, top), (0.0, top), (0.0, z1), (corr, z1), (corr, z0), (0.0, z0)]


def rect(u0, u1, v0, v1):
    u0, u1 = sorted((u0, u1))
    v0, v1 = sorted((v0, v1))
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def box(x0, x1, y0, y1, z0, z1):
    z0, z1 = sorted((z0, z1))
    return dict(axis="z", profile=rect(x0, x1, y0, y1), a0=z0, a1=z1)


def gallery_plan(ox, oy, d):
    """SL.GALL: the hall's plan with an elliptical bite out of its inner edge."""
    length, edge, bite, x_a, seg = d["cb_length"], 7.52, 0.97, 3.91, 18
    pts = [(ox, oy), (ox + length, oy), (ox + length, oy + edge)]
    mid, half = (length + x_a) / 2, (length - x_a) / 2
    for i in range(1, seg):
        x = length - i * (length - x_a) / seg
        pts.append((ox + x, oy + edge - bite * math.sqrt(max(0.0, 1 - ((x - mid) / half) ** 2))))
    return pts + [(ox + x_a, oy + edge), (ox, oy + edge)]


def cells(state, P):
    d = P["dim"]
    bay, depth, h, pil, t, corr = d["bay"], d["depth"], d["storey"], d["pilotis"], d["slab"], d["corridor"]
    length = P["bays"] * bay
    ox, oy = d["cb_origin"]
    cb_x1, cb_y1 = ox + d["cb_length"], oy + d["cb_depth"]
    streets = {(n["level"], n["bay"]) for n in state.nodes().values() if n.get("type") == "corridor"}

    def floor(lv):                                       # finished floor of storey lv of the block
        return pil + (lv - 1) * h

    out = []
    for nid, n in state.nodes().items():
        kind, block, lv, i = n.get("type"), n.get("block"), n.get("level"), n.get("bay")
        g, category = None, "Space"
        if kind == "mass" and block == "A":
            z0 = 0.0 if nid == "BLOCK" else pil
            g, category = box(0, length, 0, depth, z0, pil + P["levels"] * h), "Mass"
        elif kind == "mass":
            g, category = box(ox, cb_x1, oy, cb_y1, 0, P["cb_levels"] * h), "Mass"
        elif kind == "ground":
            g = box(0, length, 0, depth, 0, pil - t)
        elif kind == "storey" and block == "A":
            g, category = box(0, length, 0, depth, floor(lv), floor(lv) + h - t), "Mass"
        elif kind == "storey":
            g = box(ox, cb_x1, oy, cb_y1, lv * h, (lv + 1) * h - t)
            category = "Mass" if "HALL" not in state else "Space"
        elif kind in ("bay", "roof"):
            y0 = corr if (lv, i) in streets else 0.0
            g = box(i * bay, (i + 1) * bay, y0, depth, floor(lv), floor(lv) + h - t)
            category = "Mass" if kind == "bay" else "Roof"
        elif kind == "corridor":
            g = box(i * bay, (i + 1) * bay, 0, corr, floor(lv), floor(lv) + h - t)
        elif kind == "dwelling" and i is not None:
            ci = n["corridor_index"]
            pierced = (lv + ci, i) in streets
            prof = [(y, z + floor(lv)) for (y, z) in section(n["levels"], ci, d, pierced)]
            g = dict(axis="x", profile=prof, a0=i * bay, a1=(i + 1) * bay)
        elif kind == "dwelling":                          # the penthouse
            top = pil + P["levels"] * h
            g = box(0.18 * length, 0.55 * length, depth / 2, depth, top, top + h - t)
        elif kind == "stairwell" and block == "A":
            g = box(i * bay, (i + 1) * bay, depth - d["stairwell_depth"], depth, floor(lv), floor(lv) + h - t)
        elif kind == "stairwell":
            g = box(ox, ox + d["cb_core_length"], cb_y1, cb_y1 + d["cb_core_depth"], lv * h, (lv + 1) * h - t)
        elif kind == "hall":
            g = box(ox, cb_x1, oy, cb_y1, lv * h, (lv + n.get("levels", 2)) * h - t)
        elif kind == "gallery":
            z = lv * h + 0.6
            g, category = dict(axis="z", profile=gallery_plan(ox, oy, d), a0=z - t, a1=z), "Structure"
        elif kind == "bridge":
            g = box(0, d["bridge_width"], cb_y1 + d["cb_core_depth"], 0, floor(1), floor(1) + h - t)
        if g is None:                                     # the interface node stands for a cell of the block
            continue
        out.append(dict(id=nid, category=category, **g))
    return out
