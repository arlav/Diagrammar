"""
narkomfin_to_topologic.py -- load DomNarkomfin_Elements.blend into TopologicPy
==============================================================================
Every Blender object becomes a Topologic Cell (closed solid) carrying a Dictionary with the
object's custom properties (IfcClass, Block, Level, LevelName, Bay, Unit, Role, Material, name).

    python narkomfin_to_topologic.py --blend DomNarkomfin_Elements.blend [--filter "Block=RB,Level=3"]
                                     [--cellcomplex] [--graph] [--spaces]

Needs: bpy (pip install bpy, or run inside Blender's Python) and topologicpy.
Inside Blender you can also just `import narkomfin_to_topologic as n2t; cells = n2t.cells_from_scene()`.
"""
import argparse, sys, time

import bpy
from topologicpy.Vertex import Vertex
from topologicpy.Face import Face
from topologicpy.Cell import Cell
from topologicpy.Cluster import Cluster
from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary

PROP_KEYS = ("IfcClass", "Block", "Level", "LevelName", "Bay", "Unit", "Role", "Material", "Line", "Row", "Profile",
             "Symbol", "ElementName", "Category", "GrammarRole", "Ports")   # the last five are on the element dictionary objects


def object_to_cell(ob, tolerance=0.0001):
    """Blender mesh object -> Topologic Cell with a dictionary of its custom properties."""
    mw = ob.matrix_world
    verts = [tuple(mw @ v.co) for v in ob.data.vertices]
    faces = [list(p.vertices) for p in ob.data.polygons]
    topo = Topology.ByGeometry(vertices=verts, faces=faces, tolerance=tolerance)
    cell = None
    if topo is not None and Topology.IsInstance(topo, "Cell"):
        cell = topo
    else:
        # fall back: rebuild from faces (handles n-gon caps of the extruded profiles)
        tfaces = []
        for f in faces:
            tfaces.append(Face.ByVertices([Vertex.ByCoordinates(*verts[i]) for i in f]))
        cell = Cell.ByFaces(tfaces, tolerance=tolerance)
    if cell is None:
        return None
    keys = ["name"] + [k for k in PROP_KEYS if k in ob.keys()]
    vals = [ob.name] + [ob[k] for k in PROP_KEYS if k in ob.keys()]
    d = Dictionary.ByKeysValues(keys, vals)
    return Topology.SetDictionary(cell, d)


def cells_from_scene(flt=None, include_spaces=False):
    """All element objects (optionally the abstract Space_* cells) as Topologic Cells."""
    out, skipped = [], []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if ob.name.startswith("Space_") and not include_spaces:
            continue
        if ob.name == "Slab_SITE_Ground":
            continue
        if flt and any(str(ob.get(k, "")) != v for k, v in flt.items()):
            continue
        c = object_to_cell(ob)
        (out if c else skipped).append(c or ob.name)
    if skipped:
        print("could not convert:", skipped)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--filter", default="", help='e.g. "Block=RB,Level=3" (property=value pairs)')
    ap.add_argument("--cellcomplex", action="store_true", help="self-merge the cells into a CellComplex (slow for the whole model)")
    ap.add_argument("--graph", action="store_true", help="also build the adjacency graph")
    ap.add_argument("--spaces", action="store_true", help="include the abstract grammar Space_* cells")
    ap.add_argument("--brep", default="", help="write the cluster as BREP to this path")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    flt = dict(kv.split("=") for kv in a.filter.split(",")) if a.filter else None

    bpy.ops.wm.open_mainfile(filepath=a.blend)
    t = time.time()
    cells = cells_from_scene(flt, a.spaces)
    print(f"{len(cells)} cells in {time.time()-t:.1f}s")
    vols = [Cell.Volume(c) for c in cells]
    print("volume total %.1f m3, min %.4f" % (sum(vols), min(vols)))
    cluster = Cluster.ByTopologies(cells)
    if a.brep:
        Topology.ExportToBREP(cluster, a.brep, overwrite=True)
        print("wrote", a.brep)
    merged = None
    if a.cellcomplex or a.graph:
        # Self-merge fuses coincident faces so adjacency becomes explicit. The result is a CellComplex
        # when everything is face-connected, otherwise a Cluster of CellComplexes/Cells - both are fine.
        t = time.time()
        merged = Topology.SelfMerge(cluster, tolerance=0.001)
        kind = Topology.TypeAsString(merged)
        print("SelfMerge ->", kind, f"({time.time()-t:.1f}s)", "cells:", len(Topology.Cells(merged)),
              "| cellcomplexes:", len(Topology.CellComplexes(merged)) if kind == "Cluster" else 1)
    if a.graph and merged:
        from topologicpy.Graph import Graph
        t = time.time()
        g = Graph.ByTopology(merged, direct=True, viaSharedTopologies=False, useInternalVertex=True, tolerance=0.001)
        print("Graph (direct cell adjacency): vertices", len(Graph.Vertices(g)), "edges", len(Graph.Edges(g)), f"({time.time()-t:.1f}s)")
        v0 = Graph.Vertices(g)[0]
        print("example vertex dictionary:", Dictionary.PythonDictionary(Topology.Dictionary(v0)))
    return cells, cluster, merged


if __name__ == "__main__":
    main()
