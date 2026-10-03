"""
probe_occt8.py -- the M0 probe (brief, section 1)
=================================================
Records what the installed pythonocc-core / TopologicPy actually expose, and writes the findings to
docs/occt8_probe.md. It reports; it does not work around anything that is missing.

    TOPOLOGICPY_CORE_BACKEND=pythonocc python scripts/probe_occt8.py
"""
import importlib
import os
import pkgutil
import platform
import sys
import traceback
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "occt8_probe.md"

# the identity / history API Wassim describes; matched case-insensitively against binding names
WANTED = ("UID", "RefUID", "ItemUID", "AddWithHistory", "LayerHistory", "ShapesView",
          "Modified", "Generated", "Deleted", "Replaced")
IMPORTS = ("brepgraph", "BRepGraph_NodeId", "BRepGraph_ChildExplorer")


def attempt(fn):
    try:
        return True, fn()
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"


def versions():
    out = {"python": sys.version.split()[0], "platform": f"{platform.system()} {platform.machine()}",
           "TOPOLOGICPY_CORE_BACKEND": os.environ.get("TOPOLOGICPY_CORE_BACKEND", "(unset)")}
    for mod, attr in (("OCC", "VERSION"), ("topologicpy", "__version__"), ("igraph", "__version__")):
        ok, val = attempt(lambda: getattr(importlib.import_module(mod), attr))
        out[mod] = val if ok else f"unavailable ({val})"
    ok, val = attempt(lambda: importlib.import_module("OCC.Core.Standard").Standard_Version.Number())
    if not ok:
        ok, val = attempt(lambda: importlib.import_module("OCC.Core").__dict__.get("OCC_VERSION_COMPLETE"))
    out["OCCT"] = val if ok and val else "not reported by the bindings"
    return out


def brepgraph_imports():
    ok, mod = attempt(lambda: importlib.import_module("OCC.Core.BRepGraph"))
    if not ok:
        return [("OCC.Core.BRepGraph", False, mod)], None
    rows = [("OCC.Core.BRepGraph", True, "")]
    for name in IMPORTS:
        rows.append((name, hasattr(mod, name), ""))
    return rows, mod


def brepgraph_modules():
    """Every OCC.Core module whose name starts with BRepGraph."""
    ok, core = attempt(lambda: importlib.import_module("OCC.Core"))
    if not ok:
        return []
    return sorted(m.name for m in pkgutil.iter_modules(core.__path__) if m.name.startswith("BRepGraph")
                  and not m.name.startswith("_"))


def scan(module_names):
    """Exact public names per module, plus the members of every class that looks like identity/history."""
    names, members = {}, {}
    for mn in module_names:
        ok, mod = attempt(lambda: importlib.import_module(f"OCC.Core.{mn}"))
        if not ok:
            names[mn] = mod
            continue
        public = sorted(n for n in dir(mod) if not n.startswith("_") and not n.endswith("_swigregister"))
        names[mn] = public
        for n in public:
            if any(w.lower() in n.lower() for w in WANTED):
                obj = getattr(mod, n)
                if isinstance(obj, type):
                    members[f"{mn}.{n}"] = sorted(m for m in dir(obj) if not m.startswith("_")
                                                  and m not in ("thisown", "this"))
    return names, members


def wanted_hits(names, members):
    rows = []
    for w in WANTED:
        hits = []
        for mn, public in names.items():
            if isinstance(public, list):
                hits += [f"{mn}.{n}" for n in public if w.lower() in n.lower()]
        for cls, ms in members.items():
            hits += [f"{cls}.{m}" for m in ms if w.lower() in m.lower()]
        rows.append((w, sorted(set(hits))))
    return rows


def backend():
    def run():
        from topologicpy.Core import Core
        return type(Core.Backend()).__name__
    return attempt(run)


def shape_grammar_smoke():
    """One Divide rule on a box; read History, GeneratedBy, ModifiedBy, LineageGraph."""
    from topologicpy.Cell import Cell
    from topologicpy.ShapeGrammar import ShapeGrammar
    from topologicpy.Topology import Topology

    box = Cell.Prism(width=2.0, length=1.0, height=1.0)
    sg = ShapeGrammar(title="M0 probe")
    rid = sg.AddRule(input=box, operation="Divide", uSides=2, vSides=1, wSides=1, title="split in two")
    matches = sg.ApplicableRules(box)
    result = sg.ApplyRule(box, rid)
    history = sg.History()
    out = {"rule id": rid,
           "applicable rules": len(matches or []),
           "result type": Topology.TypeAsString(result) if result is not None else None,
           "result cells": len(Topology.Cells(result) or []) if result is not None else 0,
           "History() records": len(history),
           "relations in History()": sorted({str(r.get("relation")) for r in history}),
           "result types in History()": sorted({str(r.get("resultType")) for r in history}),
           "record keys": sorted(history[0].keys()) if history else []}
    for name in ("GeneratedBy", "ModifiedBy", "UnchangedBy", "DeletedBy"):
        ok, val = attempt(lambda: len(getattr(sg, name)()))
        out[f"{name}()"] = val
    for name in ("LineageGraph", "DerivationGraph"):
        ok, val = attempt(lambda: getattr(sg, name)())
        out[f"{name}()"] = type(val).__name__ if ok else val
    ok, val = attempt(lambda: sorted({(str(r.get("relation")), str(r.get("sourceType")), str(r.get("resultType")))
                                      for r in history}))
    out["relation / source type / result type"] = val
    return out


def cut_face_probe():
    """The party-wall case: how does History() report the face created by dividing a cell, and what
    dictionary does it carry? Identity only (ShapeGrammar's own comparison), no geometric matching."""
    import time
    from collections import Counter
    from topologicpy.Cell import Cell
    from topologicpy.CellComplex import CellComplex
    from topologicpy.Dictionary import Dictionary
    from topologicpy.ShapeGrammar import ShapeGrammar
    from topologicpy.Topology import Topology

    def pydict(t):
        d = Topology.Dictionary(t)
        return d if isinstance(d, dict) else Dictionary.PythonDictionary(d)

    box = Cell.Prism(width=2.0, length=1.0, height=1.0)
    box = Topology.SetDictionary(box, Dictionary.ByKeysValues(["type", "level"], ["storey", 3]))
    sg = ShapeGrammar(title="M0 cut face")
    rid = sg.AddRule(input=box, operation="Divide", uSides=2, vSides=1, wSides=1)
    res = sg.ApplyRule(box, rid)
    hist = sg.History()
    same = ShapeGrammar._same_topology
    faces = Topology.Faces(res)
    face_recs = [r for r in hist if r.get("resultType") == "Face" and r.get("result") is not None]
    silent = [f for f in faces if not any(same(r["result"], f) for r in face_recs)]
    internal = CellComplex.InternalFaces(res)
    cut = []
    for f in internal:
        cut += [(r["relation"], r.get("sourceRole"), r["sourceType"], r.get("operation"))
                for r in face_recs if same(r["result"], f)]
    table = Counter((r["relation"], str(r.get("sourceRole")), str(r["sourceType"]), str(r["resultType"]))
                    for r in hist)

    sg2 = ShapeGrammar(title="M0 22 bays")
    r2 = sg2.AddRule(input=box, operation="Divide", uSides=22, vSides=1, wSides=1)
    t0 = time.perf_counter()
    out = sg2.ApplyRule(box, r2)
    ms = (time.perf_counter() - t0) * 1000
    return {"summary": {"faces in result": len(faces),
                        "faces with no history record": len(silent),
                        "internal (cut) faces": len(internal),
                        "cut face records (relation, sourceRole, sourceType, operation)": cut,
                        "cut face dictionary": [pydict(f) for f in internal],
                        "cell dictionaries after the divide": [pydict(c) for c in Topology.Cells(res)],
                        "22-way divide": f"{len(Topology.Cells(out))} cells, {len(sg2.History())} history "
                                         f"records, {ms:.0f} ms"},
            "table": sorted(table.items())}


def render(v, imports, modules, names, members, hits, be, smoke, cut):
    L = ["# OCCT 8 probe (M0)", "",
         f"Generated by `scripts/probe_occt8.py` on {date.today().isoformat()}. "
         "This file records what exists; nothing here is worked around.", "",
         "## Versions", "", "| item | value |", "|---|---|"]
    L += [f"| {k} | `{val}` |" for k, val in v.items()]

    L += ["", "## 1. BRepGraph imports named in the brief", "", "| name | present | note |", "|---|---|---|"]
    L += [f"| `{n}` | {'yes' if ok else '**no**'} | {note} |" for n, ok, note in imports]

    L += ["", "## 2. Active TopologicPy backend", "",
          f"`{be[1]}`" if be[0] else f"**Failed:** `{be[1]}`"]

    L += ["", "## 3. Identity and history bindings", "", "BRepGraph modules found under `OCC.Core`: "
          + (", ".join(f"`{m}`" for m in modules) if modules else "**none**"), "",
          "| wanted | exact Python names found |", "|---|---|"]
    for w, found in hits:
        L.append(f"| `{w}` | " + ("<br>".join(f"`{h}`" for h in found) if found else "**not found**") + " |")
    if members:
        L += ["", "### Members of the matching classes", ""]
        for cls, ms in members.items():
            L += [f"**`{cls}`**", "", ", ".join(f"`{m}`" for m in ms) or "(none)", ""]
    L += ["", "## 4. `ShapeGrammar` smoke test", ""]
    if smoke[0]:
        L += ["One `Divide` rule (2 x 1 x 1) on a 2 x 1 x 1 box.", "", "| item | value |", "|---|---|"]
        L += [f"| {k} | `{val}` |" for k, val in smoke[1].items()]
    else:
        L += ["**Failed:**", "", "```", smoke[1], "```"]

    L += ["", "## 5. The cut face (the party-wall case)", ""]
    if cut[0]:
        L += ["The same divide on a cell carrying `{type: storey, level: 3}`. Faces are compared by "
              "identity, not by geometry.", "", "| item | value |", "|---|---|"]
        L += [f"| {k} | `{val}` |" for k, val in cut[1]["summary"].items()]
        L += ["", "| relation | sourceRole | sourceType | resultType | records |", "|---|---|---|---|---|"]
        L += [f"| {a} | {b} | {c} | {d} | {n} |" for (a, b, c, d), n in cut[1]["table"]]
    else:
        L += ["**Failed:**", "", "```", cut[1], "```"]

    L += ["", "## Appendix: all public names per module", ""]
    for mn, public in names.items():
        L += [f"**`OCC.Core.{mn}`**", ""]
        L += [", ".join(f"`{n}`" for n in public) if isinstance(public, list) else f"import failed: `{public}`", ""]
    return "\n".join(L) + "\n"


def main():
    v = versions()
    imports, _ = brepgraph_imports()
    modules = brepgraph_modules()
    names, members = scan(modules)
    hits = wanted_hits(names, members)
    be = backend()
    try:
        smoke = (True, shape_grammar_smoke())
    except Exception:
        smoke = (False, traceback.format_exc())
    try:
        cut = (True, cut_face_probe())
    except Exception:
        cut = (False, traceback.format_exc())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(v, imports, modules, names, members, hits, be, smoke, cut))
    print("wrote", OUT)
    print("backend:", be[1])
    print("smoke test:", "ok" if smoke[0] else "FAILED")
    print("cut face probe:", "ok" if cut[0] else "FAILED")
    for w, found in hits:
        print(f"  {w:16s} {len(found)} name(s)")


if __name__ == "__main__":
    main()
