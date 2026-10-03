"""
interpret.py -- graph -> shape, for the Unité
=============================================
The Narkomfin interpreter is kept for everything it knows. What the Unité adds: half bands beside a
central street, and the two interlocked cells, `up` and `down`.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("narkomfin_interpret", Path(__file__).resolve().parents[2] / "narkomfin" / "graph" / "interpret.py")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)


def _profiles(d, kind):
    """(y, z) profile of a two-level cell beside a central street of width w: the half of the street
    level on its side, and the whole depth on the other level."""
    depth, w, h, t = d["depth"], d["corridor"], d["storey"], d["slab"]
    ys, yn = depth / 2 - w / 2, depth / 2 + w / 2
    if kind == "up":                        # street level below, full level above
        return [(0.0, 0.0), (ys, 0.0), (ys, h), (depth, h), (depth, 2 * h - t), (0.0, 2 * h - t)]
    return [(0.0, 0.0), (depth, 0.0), (depth, 2 * h - t), (yn, 2 * h - t), (yn, h), (0.0, h)]


def cells(state, P):
    d = P["dim"]
    bay, depth, h, pil, t, w = d["bay"], d["depth"], d["storey"], d["pilotis"], d["slab"], d["corridor"]
    ys, yn = depth / 2 - w / 2, depth / 2 + w / 2
    out = {c["id"]: c for c in _base.cells(state, P)}
    for nid, n in state.nodes().items():
        kind, lv, i = n.get("type"), n.get("level"), n.get("bay")
        z0 = pil + (lv - 1) * h if lv is not None else 0.0
        if kind == "bay" and n.get("half") == "S":
            out[nid] = dict(id=nid, category="Mass", **_base.box(i * bay, (i + 1) * bay, 0, ys, z0, z0 + h - t))
        elif kind == "bay" and n.get("half") == "N":
            out[nid] = dict(id=nid, category="Mass", **_base.box(i * bay, (i + 1) * bay, yn, depth, z0, z0 + h - t))
        elif kind == "corridor":
            out[nid] = dict(id=nid, category="Space", **_base.box(i * bay, (i + 1) * bay, ys, yn, z0, z0 + h - t))
        elif kind == "dwelling" and n.get("kind") in ("up", "down"):
            prof = [(y, z + z0) for (y, z) in _profiles(d, n["kind"])]
            out[nid] = dict(id=nid, category="Space", axis="x", profile=prof, a0=i * bay, a1=(i + 1) * bay)
    return list(out.values())
