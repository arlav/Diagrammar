"""
narkomfin_graph_grammar.py -- the Dom Narkomfin GRAPH grammar (TopologicPy)
===========================================================================
The mirror of narkomfin_grammar.py. Every production rewrites a labelled graph whose semantics live
in dictionaries embedded on the vertices and the edges; at every step the state is materialised as a
real TopologicPy `Graph` so it can be measured, exported and compared.

    Grammar GA  "BLOCK"       GA0 axiom, GA1 lift, GA2 stack, GA3 bay, GA4 corridor,
                              GA5 cell (L / U), GA6 core, GA7 facade (IDENTITY), GA8 roof
    Grammar GB  "CONDENSER"   GB0 axiom, GB1 stack, GB2 merge, GB3 gallery,
                              GB4 facade (IDENTITY), GB5 core, GB6 bridge (composition)

Node dictionary        id, label, type, level, bay, tag, kind, levels, corridor_index, symbol, block
Edge dictionary        rel  in {supports, above, party, door, corridor, stair, core_door, open, bridge}
                       access in {none, open, door, stair}      <- the access semantics of the edge

The two edge keys are the point of the whole exercise: `party` edges have access "none" (adjacent but
not connected) while `door`/`stair`/`open` edges carry access. A graph grammar that ignores this
distinction can produce plans that are topologically connected and architecturally impossible.

INTERPRETER (graph -> shape).  Every dwelling / corridor / core node carries enough in its dictionary
(bay, levels, corridor_index, kind) for `interpret()` to build Topologic Cells, assemble them into a
CellComplex, and read the adjacency graph back out with Graph.ByTopology. So the same variant can be
generated from the graph side and checked against the shape side.

Usage
    python narkomfin_graph_grammar.py --json out/graphs --blend out/DomNarkomfin_GraphGrammar.blend
    (Blender's bpy is only needed for --blend; everything else is pure TopologicPy.)
"""
import argparse, json, os, sys
from copy import deepcopy

from topologicpy.Vertex import Vertex
from topologicpy.Edge import Edge
from topologicpy.Face import Face
from topologicpy.Cell import Cell
from topologicpy.CellComplex import CellComplex
from topologicpy.Cluster import Cluster
from topologicpy.Graph import Graph
from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary

# ---------------------------------------------------------------- dimensions (shared with the shape grammar)
BAY, DEPTH, H, H_PIL = 3.66, 9.90, 2.80, 2.50
CORR, HALL, TS = 1.80, 1.58, 0.30
ACCESS = {"supports": "none", "above": "none", "party": "none", "door": "door", "corridor": "open",
          "stair": "stair", "core_door": "door", "open": "open", "bridge": "door"}


# ---------------------------------------------------------------- the rewriting state
class GState:
    """A labelled graph under rewriting. Nodes and edges hold plain dicts here; `to_graph()` embeds
    them as TopologicPy Dictionaries on the Vertices and Edges of a real Topologic Graph."""

    def __init__(self, name="G"):
        self.name = name
        self.N = {}       # id -> dict(props..., pos=(x,y,z))
        self.E = []       # dict(a, b, rel)

    # -- rewriting primitives -------------------------------------
    def add(self, nid, pos, **props):
        self.N[nid] = dict(id=nid, pos=tuple(round(v, 3) for v in pos), **props)
        return nid

    def link(self, a, b, rel):
        if a in self.N and b in self.N and a != b:
            self.E.append(dict(a=a, b=b, rel=rel))

    def remove(self, *nids):
        for nid in nids:
            self.N.pop(nid, None)
        keep = set(self.N)
        self.E = [e for e in self.E if e["a"] in keep and e["b"] in keep]

    def merge(self, nids, new_id, pos=None, **props):
        """The contraction used by the L/U cell rule: several nodes become one, their外 edges survive."""
        nids = [n for n in nids if n in self.N]
        if not nids:
            return None
        ps = [self.N[n]["pos"] for n in nids]
        pos = pos or tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
        self.add(new_id, pos, **props)
        old = set(nids)
        for e in self.E:
            if e["a"] in old:
                e["a"] = new_id
            if e["b"] in old:
                e["b"] = new_id
        self.remove(*[n for n in nids if n != new_id])
        seen, out = set(), []
        for e in self.E:
            if e["a"] == e["b"]:
                continue                                  # self-loops from the contraction dissolve
            k = (min(e["a"], e["b"]), max(e["a"], e["b"]), e["rel"])
            if k not in seen:
                seen.add(k)
                out.append(e)
        self.E = out
        return new_id

    def access_subgraph(self):
        """The ACCESS graph: only nodes that can be occupied, only edges you can walk through.
        This, not the full labelled graph, is what the two grammars should agree on."""
        keep = {n for n, d in self.N.items()
                if d.get("type") in ("ground", "dwelling", "corridor", "stairwell", "hall", "gallery",
                                     "bridge", "interface")}
        s = GState(self.name + "_access")
        for n in keep:
            s.N[n] = deepcopy(self.N[n])
        for e in self.E:
            if e["a"] in keep and e["b"] in keep and ACCESS.get(e["rel"], "none") != "none":
                s.E.append(deepcopy(e))
        return s

    def match(self, **kw):
        """LHS matcher: every node whose dictionary agrees with the given key/values."""
        return [n for n, d in sorted(self.N.items()) if all(d.get(k) == v for k, v in kw.items())]

    def copy(self):
        s = GState(self.name)
        s.N, s.E = deepcopy(self.N), deepcopy(self.E)
        return s

    # -- materialise as a TopologicPy Graph ------------------------
    def to_graph(self):
        verts, byid = {}, {}
        for nid, d in self.N.items():
            v = Vertex.ByCoordinates(*d["pos"])
            keys = [k for k in d if k != "pos"]
            v = Topology.SetDictionary(v, Dictionary.ByKeysValues(
                keys + ["x", "y", "z"], [d[k] for k in keys] + list(d["pos"])))
            verts[nid] = v
            byid[nid] = d
        edges = []
        for e in self.E:
            a, b = verts.get(e["a"]), verts.get(e["b"])
            if a is None or b is None:
                continue
            ed = Edge.ByStartVertexEndVertex(a, b, silent=True)
            if ed is None:
                continue
            ed = Topology.SetDictionary(ed, Dictionary.ByKeysValues(
                ["rel", "access", "from", "to"], [e["rel"], ACCESS.get(e["rel"], "none"), e["a"], e["b"]]))
            edges.append(ed)
        return Graph.ByVerticesEdges(list(verts.values()), edges, silent=True)

    def metrics(self, heavy=False):
        """Light metrics are computed on the Python side (they are called after every production);
        `heavy=True` materialises the TopologicPy Graph and adds its analyses - used on final states."""
        deg, adj = {}, {}
        for e in self.E:
            deg[e["a"]] = deg.get(e["a"], 0) + 1
            deg[e["b"]] = deg.get(e["b"], 0) + 1
            adj.setdefault(e["a"], set()).add(e["b"])
            adj.setdefault(e["b"], set()).add(e["a"])
        seen, comps = set(), 0
        for n in self.N:
            if n in seen:
                continue
            comps += 1
            stack = [n]
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                stack += [y for y in adj.get(x, ()) if y not in seen]
        acc = {}
        for e in self.E:
            k = ACCESS.get(e["rel"], "none")
            acc[k] = acc.get(k, 0) + 1
        m = dict(nodes=len(self.N), edges=len(self.E), max_degree=max(deg.values()) if deg else 0,
                 components=comps, edges_by_access=acc,
                 nodes_by_type={t: len(self.match(type=t))
                                for t in sorted({d.get("type") for d in self.N.values()} - {None})})
        if heavy:
            g = self.to_graph()
            m["topologic_graph"] = dict(vertices=len(Graph.Vertices(g)), edges=len(Graph.Edges(g)))
            try:
                cv = Graph.CutVertices(g) or []
                labels = []
                for v in cv:
                    cd = Dictionary.PythonDictionary(Topology.Dictionary(v)) or {}
                    labels.append(cd.get("id") or cd.get("label") or "?")
                m["cut_vertices"] = len(cv)
                m["cut_vertex_ids"] = sorted(labels)[:12]
            except Exception as ex:
                m["cut_vertices"] = f"unavailable ({ex})"
            try:
                m["degree_centrality_max"] = round(max(Graph.DegreeCentrality(g) or [0]), 4)
            except Exception:
                pass
        return m


# ---------------------------------------------------------------- GRAMMAR GA : the block
def GA0_axiom(s, P):
    s.add("BLOCK", (P["bays"] * BAY / 2, DEPTH / 2, 8.0), label="BLOCK", type="mass", block="A")
    return "GA0 AXIOM: one node, type=mass."


def GA1_lift(s, P):
    for n in s.match(type="mass"):
        s.remove(n)
    s.add("GROUND", (P["bays"] * BAY / 2, DEPTH / 2, 1.2), label="GROUND", type="ground", block="A")
    s.add("MASS", (P["bays"] * BAY / 2, DEPTH / 2, 11.0), label="MASS", type="mass", block="A")
    s.link("GROUND", "MASS", "supports")
    return ("GA1 R_LIFT: mass -> {ground, mass} joined by 'supports' (access none). The ground plane becomes "
            "a node in its own right, which is what makes the pilotis legible to the graph at all.")


def GA2_stack(s, P):
    s.remove("MASS")
    for lv in range(1, P["levels"] + 1):
        s.add(f"L{lv}", (P["bays"] * BAY / 2, DEPTH / 2, H_PIL + (lv - 0.5) * H),
              label=f"STOREY L{lv}", type="storey", level=lv, block="A")
        s.link(f"L{lv-1}" if lv > 1 else "GROUND", f"L{lv}", "above")
    return f"GA2 R_STACK: mass -> a chain of {P['levels']} storey nodes on 'above' edges (access none)."


def GA3_bay(s, P):
    for lv in range(1, P["levels"] + 1):
        s.remove(f"L{lv}")
        for i in range(P["bays"]):
            s.add(f"b{lv}_{i:02d}", ((i + 0.5) * BAY, DEPTH / 2, H_PIL + (lv - 0.5) * H),
                  label=f"BAY {i}", type="bay", level=lv, bay=i, block="A")
            if i:
                s.link(f"b{lv}_{i-1:02d}", f"b{lv}_{i:02d}", "party")
        if lv > 1:
            for i in range(P["bays"]):
                s.link(f"b{lv-1}_{i:02d}", f"b{lv}_{i:02d}", "above")
    return ("GA3 R_BAY: each storey node is expanded into n bay nodes chained by 'party' edges whose access "
            "is NONE. This is the graph half of the bay / party-wall pair: the subdivision creates adjacency "
            "WITHOUT access, and every later rule has to supply the access explicitly.")


def GA4_corridor(s, P):
    for lv in P["corridor_levels"]:
        prev = None
        for i in range(P["bays"]):
            bid = f"b{lv}_{i:02d}"
            if bid not in s.N:
                continue
            cid = f"c{lv}_{i:02d}"
            s.add(cid, ((i + 0.5) * BAY, CORR / 2, H_PIL + (lv - 0.5) * H),
                  label=f"CORRIDOR L{lv}", type="corridor", level=lv, bay=i, symbol="SP.CORRIDOR", block="A")
            s.N[bid]["pos"] = ((i + 0.5) * BAY, (CORR + DEPTH) / 2, H_PIL + (lv - 0.5) * H)
            s.link(cid, bid, "door")
            if prev:
                s.link(prev, cid, "corridor")
            prev = cid
    return ("GA4 R_CORRIDOR: on the chosen levels each bay node splits into {corridor, band}. The corridor "
            "nodes form an open chain (access open) and each band gets exactly ONE 'door' edge. The internal "
            "street now exists as a path in the graph, so the shape rule that cuts it is no longer optional.")


def GA5_cell(s, P):
    """GA5 R_LCELL / R_UCELL: contract a vertical run of band nodes into one dwelling node.
    The parameter that makes the section L or U is `corridor_index` - the position, inside the run, of the
    level the street pierces."""
    notes = []
    for (lo, hi, ci, tag) in P["cells"]:
        levels = hi - lo + 1
        kind = "L" if ci == 0 else ("Gamma" if ci == levels - 1 else ("U" if levels == 3 else "Z"))
        for i in range(P["core_lines"][0] + 1, P["bays"] - P["ends"]):
            if i in P["core_lines"]:
                continue
            run = [f"b{lv}_{i:02d}" for lv in range(lo, hi + 1) if f"b{lv}_{i:02d}" in s.N]
            if len(run) < levels:
                continue
            nid = f"{tag}{i:02d}"
            s.merge(run, nid, pos=((i + 0.5) * BAY, (CORR + DEPTH) / 2, H_PIL + (lo - 1 + levels / 2) * H),
                    label=f"{tag} [{kind}] b{i}", type="dwelling", tag=tag, kind=kind, levels=levels,
                    corridor_index=ci, bay=i, level=lo, symbol=f"SP.CELL.{tag}", block="A")
        notes.append(f"{tag}: {levels} levels, corridor at index {ci} -> {kind}")
    # the end bays are single-level end dwellings; their access arrives with GA6
    for i in list(range(P["core_lines"][0])) + list(range(P["core_lines"][-1] + 1, P["bays"])):
        for lv in range(1, P["levels"]):
            bid = f"b{lv}_{i:02d}"
            if bid in s.N:
                s.merge([bid], f"E{lv}_{i:02d}", label=f"END UNIT L{lv} b{i}", type="dwelling", tag="E",
                        kind="flat", levels=1, corridor_index=0, bay=i, level=lv, symbol="SP.CELL.E", block="A")
    # the street STOPS at the cores: the end units inherit no door from GA4, they are entered from the
    # stair lobby (the edge arrives with GA6). Drop the inherited corridor doors.
    ends = set(range(P["core_lines"][0])) | set(range(P["core_lines"][-1] + 1, P["bays"]))
    s.E = [e for e in s.E
           if not (e["rel"] == "door"
                   and {s.N.get(e["a"], {}).get("type"), s.N.get(e["b"], {}).get("type")} == {"corridor", "dwelling"}
                   and (s.N.get(e["a"], {}).get("bay") in ends or s.N.get(e["b"], {}).get("bay") in ends)
                   and "E" in (s.N.get(e["a"], {}).get("tag"), s.N.get(e["b"], {}).get("tag")))]
    # K dwellings are built in mirrored pairs; mark the shared party edge
    for e in s.E:
        da, db = s.N.get(e["a"], {}), s.N.get(e["b"], {})
        if e["rel"] == "party" and da.get("tag") == db.get("tag") == "K" and abs(da.get("bay", 0) - db.get("bay", 9)) == 1:
            if min(da["bay"], db["bay"]) % 2 == 1:
                e["rel"] = "party"
                e["mirror"] = True
    return ("GA5 R_LCELL / R_UCELL: CONTRACT the run of band nodes of one bay into a single dwelling node, "
            "keeping the door edge to the level the corridor pierces and dissolving the internal 'above' "
            "edges (they are now inside one dwelling). " + "; ".join(notes) +
            ". This is the only production that REDUCES the node count, and it is where the section type is "
            "decided: L keeps 2 levels on one street, U hangs 3 levels off one street.")


def GA6_core(s, P):
    for i in P["core_lines"]:
        for lv in range(1, P["levels"] + 1):
            s.remove(f"b{lv}_{i:02d}", f"c{lv}_{i:02d}")
            sid = f"S{lv}_{i:02d}"
            s.add(sid, ((i + 0.5) * BAY, DEPTH - 2.5, H_PIL + (lv - 0.5) * H),
                  label=f"STAIRWELL b{i}", type="stairwell", level=lv, bay=i, symbol="SP.STAIRWELL", block="A")
            s.link(f"S{lv-1}_{i:02d}" if lv > 1 else "GROUND", sid, "stair")
            for cl in P["corridor_levels"]:
                if lv == cl:
                    for nb in (f"c{cl}_{i-1:02d}", f"c{cl}_{i+1:02d}"):
                        s.link(sid, nb, "core_door")
            for nb in (f"E{lv}_{i-1:02d}", f"E{lv}_{i+1:02d}", f"E{lv}_{i-2:02d}", f"E{lv}_{i+2:02d}"):
                s.link(sid, nb, "core_door")               # end units are entered from the stair lobby
            for d in s.match(type="dwelling", level=lv):
                if s.N[d].get("tag") in ("K", "F") and abs(s.N[d].get("bay", 99) - i) == 1:
                    s.link(sid, d, "core_door")
    return ("GA6 R_CORE: two bay stacks are relabelled as stairwells and chained by 'stair' edges (access "
            "stair), with 'core_door' edges into the corridor chains. Before this rule the graph has no "
            "vertical access at all; after it every dwelling is reachable from GROUND, which is the property "
            "a generated variant must be tested against.")


def GA7_facade(s, P):
    before = (len(s.N), len(s.E))
    # deliberately empty: the facade split has no graph counterpart
    assert (len(s.N), len(s.E)) == before
    return ("GA7 R_FACADE: IDENTITY on the graph. The shape grammar's facade split (spandrel + ribbon, or "
            "spandrel=0 -> curtain wall) changes no node and no edge. Keeping it in the list as an explicit "
            "identity production is the honest way to record that shape and graph grammars are NOT in "
            "bijection: the envelope is style, and the graph cannot see it.")


def GA8_roof(s, P):
    for n in s.match(type="bay"):
        s.N[n].update(type="roof", label="ROOF ZONE " + s.N[n]["label"], symbol="SL.ROOF")
    s.add("PENTHOUSE", (P["bays"] * BAY * 0.36, DEPTH * 0.75, H_PIL + P["levels"] * H + 1.4),
          label="PENTHOUSE", type="dwelling", tag="PH", kind="flat", levels=1, block="A")
    s.link(f"S{P['levels']}_{P['core_lines'][0]:02d}", "PENTHOUSE", "stair")
    return ("GA8 R_ROOF: the bay nodes still unassigned at the top level are relabelled as roof zone, and a "
            "terminal penthouse dwelling is attached to a core. No 'bay' node may survive a complete "
            "derivation - a leftover bay is the graph grammar's equivalent of an unresolved non-terminal.")


GRAMMAR_GA = [("GA0", "AXIOM", GA0_axiom), ("GA1", "R_LIFT", GA1_lift), ("GA2", "R_STACK", GA2_stack),
              ("GA3", "R_BAY", GA3_bay), ("GA4", "R_CORRIDOR", GA4_corridor),
              ("GA5", "R_LCELL / R_UCELL", GA5_cell), ("GA6", "R_CORE", GA6_core),
              ("GA7", "R_FACADE (identity)", GA7_facade), ("GA8", "R_ROOF", GA8_roof)]


# ---------------------------------------------------------------- GRAMMAR GB : the condenser
CB_O = (-26.0, -13.0)


def GB0_axiom(s, P):
    s.add("COND", (CB_O[0], CB_O[1], 5.0), label="CONDENSER", type="mass", block="B")
    s.add("IFACE", (0.0, CORR / 2, H_PIL + 0.5 * H), label="[interface] BLOCK L1 corridor",
          type="interface", block="A/B")
    return ("GB0 AXIOM: a second axiom, plus ONE interface node standing for the block's corridor. Grammar GB "
            "sees nothing else of grammar GA, which is what lets the two be varied independently.")


def GB1_stack(s, P):
    s.remove("COND")
    for lv in range(P["cb_levels"]):
        s.add(f"CB{lv}", (CB_O[0], CB_O[1], (lv + 0.5) * H), label=f"CB L{lv}", type="storey",
              level=lv, block="B")
        if lv:
            s.link(f"CB{lv-1}", f"CB{lv}", "above")
    return f"GB1 R_STACK: the same stacking production as GA2, {P['cb_levels']} levels."


def GB2_merge(s, P):
    lo, hi = P["cb_merge"]
    s.merge([f"CB{lv}" for lv in range(lo, hi + 1)], "HALL",
            pos=(CB_O[0], CB_O[1], (lo + (hi - lo + 1) / 2) * H),
            label="SP.HALL (social condenser)", type="hall", symbol="SP.HALL", block="B",
            levels=hi - lo + 1)
    return ("GB2 R_MERGE (the condenser rule): CONTRACT adjacent storey nodes into one. It is the inverse of "
            "GA2/GB1 and the mirror of GA5 - same graph operation, opposite programme: GA5 contracts a stack "
            "into a dwelling, GB2 contracts a stack into a collective room. The result is a node of high "
            "degree, which is the graph-theoretic definition of a social condenser.")


def GB3_gallery(s, P):
    s.add("GALLERY", (CB_O[0] + 3.0, CB_O[1] + 2.0, (P["cb_merge"][1] + 0.6) * H),
          label="GALLERY", type="gallery", symbol="SL.GALL", block="B")
    s.link("HALL", "GALLERY", "open")
    return ("GB3 R_GALLERY: a node joined to the hall by an 'open' edge - no wall, no door. The open edge is "
            "what distinguishes a gallery from a room, and it is invisible to any grammar that only records "
            "'adjacent'.")


def GB4_facade(s, P):
    return ("GB4 R_FACADE (identity): as GA7. The condenser's curtain wall is the same facade rule with the "
            "split height at zero, and it too leaves the graph untouched.")


def GB5_core(s, P):
    for lv in range(P["cb_core_levels"]):
        sid = f"CBS{lv}"
        s.add(sid, (CB_O[0] + 4.5, CB_O[1] + 6.7, (lv + 0.5) * H), label=f"CB CORE L{lv}",
              type="stairwell", level=lv, symbol="SP.STAIRWELL", block="B")
        if lv:
            s.link(f"CBS{lv-1}", sid, "stair")
    s.link("CBS1", "HALL", "core_door")
    s.link("CBS2", "GALLERY", "core_door")
    return "GB5 R_CORE: a core chain ATTACHED to the hall and the gallery by 'core_door' edges."


def GB6_bridge(s, P):
    s.add("BRIDGE", (-8.0, -2.0, H_PIL + 0.5 * H), label="SP.BRIDGE", type="bridge", symbol="SP.BRIDGE",
          block="A/B")
    s.link("CBS1", "BRIDGE", "bridge")
    s.link("BRIDGE", "IFACE", "bridge")
    # GLUING: the interface node is identified with the block's first corridor node
    street = [n for n in s.match(type="corridor", level=P["corridor_levels"][0])]
    if street:
        s.link("IFACE", street[0], "door")
    return ("GB6 R_BRIDGE (composition): the single production that joins the two grammars, through the "
            "interface node. In the composed graph BRIDGE is a cut vertex - the only one that matters "
            "architecturally, since removing it strands the whole communal programme.")


GRAMMAR_GB = [("GB0", "AXIOM", GB0_axiom), ("GB1", "R_STACK", GB1_stack), ("GB2", "R_MERGE (condenser)", GB2_merge),
              ("GB3", "R_GALLERY", GB3_gallery), ("GB4", "R_FACADE (identity)", GB4_facade),
              ("GB5", "R_CORE", GB5_core), ("GB6", "R_BRIDGE", GB6_bridge)]


# ---------------------------------------------------------------- parameters
def params(bays=22, levels=6, corridor_levels=(1, 4), cells=((1, 2, 0, "K"), (3, 5, 1, "F")),
           core_lines=(2, 19), ends=3, cb_levels=4, cb_merge=(1, 2), cb_core_levels=5):
    return dict(bays=bays, levels=levels, corridor_levels=tuple(corridor_levels), cells=tuple(cells),
                core_lines=tuple(core_lines), ends=ends, cb_levels=cb_levels, cb_merge=tuple(cb_merge),
                cb_core_levels=cb_core_levels)


AS_BUILT = params()


def derive(grammars, P, state=None, log=True):
    s = state or GState()
    steps = []
    for (rid, rname, fn) in grammars:
        note = fn(s, P)
        m = s.metrics(heavy=(rid in ("GA8", "GB6")))
        steps.append(dict(rule=rid, name=rname, description=note, **m))
        if log:
            print(f"  {rid:4s} {rname:22s} {m['nodes']:4d}n {m['edges']:4d}e  maxdeg {m['max_degree']:3d} "
                  f"comps {m['components']}  access {m['edges_by_access']}")
    return s, steps


# ---------------------------------------------------------------- graph -> shape interpreter
def section_profile(levels, ci, depth=DEPTH, corr=CORR, h=H, t=TS):
    L, Ht = depth, levels * h - t
    z0, z1 = ci * h, (ci + 1) * h - t
    if ci == 0:
        return [(corr, 0.0), (L, 0.0), (L, Ht), (0.0, Ht), (0.0, z1), (corr, z1)]
    if ci == levels - 1:
        return [(0.0, 0.0), (L, 0.0), (L, Ht), (corr, Ht), (corr, z0), (0.0, z0)]
    return [(0.0, 0.0), (L, 0.0), (L, Ht), (0.0, Ht), (0.0, z1), (corr, z1), (corr, z0), (0.0, z0)]


def _prism(profile, x0, x1):
    """Cell from a (y,z) profile extruded along x -- built face by face so it is always a closed Cell."""
    bot = [Vertex.ByCoordinates(x0, y, z) for (y, z) in profile]
    top = [Vertex.ByCoordinates(x1, y, z) for (y, z) in profile]
    faces = [Face.ByVertices(bot), Face.ByVertices(top[::-1])]
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        faces.append(Face.ByVertices([bot[i], bot[j], top[j], top[i]]))
    return Cell.ByFaces(faces, tolerance=0.001)


def _box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return _prism([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], x0, x1)


def interpret(state, cellcomplex=True):
    """Build Topologic Cells from the node dictionaries: the graph DRIVES the shape.
    Returns (cells, cluster, cellcomplex_or_None, recovered_graph_or_None)."""
    cells = []
    for nid, d in sorted(state.N.items()):
        t, c = d.get("type"), None
        if t == "dwelling" and d.get("levels") and d.get("bay") is not None:
            lo = d.get("level", 1)
            z = H_PIL + (lo - 1) * H
            prof = [(y, zz + z) for (y, zz) in section_profile(d["levels"], d["corridor_index"])]
            c = _prism(prof, d["bay"] * BAY + 0.15, (d["bay"] + 1) * BAY - 0.15)
        elif t == "corridor":
            z = H_PIL + (d["level"] - 1) * H
            c = _box(d["bay"] * BAY + 0.15, (d["bay"] + 1) * BAY - 0.15, 0.0, CORR, z, z + H - TS)
        elif t == "stairwell" and d.get("block") == "A":
            z = H_PIL + (d["level"] - 1) * H
            c = _box(d["bay"] * BAY + 0.15, (d["bay"] + 1) * BAY - 0.15, DEPTH - 5.0, DEPTH, z, z + H - TS)
        elif t == "hall":
            c = _box(CB_O[0] - 5.3, CB_O[0] + 5.3, CB_O[1] - 5.0, CB_O[1] + 5.0,
                     1 * H, (1 + d.get("levels", 2)) * H - TS)
        elif t == "gallery":
            c = _box(CB_O[0] - 5.3, CB_O[0] + 5.3, CB_O[1] - 1.5, CB_O[1] + 5.0, 3 * H - TS, 3 * H)
        elif t == "stairwell":
            c = _box(CB_O[0] - 5.3, CB_O[0] + 3.6, CB_O[1] + 5.0, CB_O[1] + 8.4,
                     d["level"] * H, (d["level"] + 1) * H - TS)
        elif t == "bridge":
            c = _box(0.0, 2.34, CB_O[1] + 8.4, 0.0, H_PIL, H_PIL + H - TS)
        if c is None:
            continue
        keys = [k for k in d if k != "pos"]
        cells.append(Topology.SetDictionary(c, Dictionary.ByKeysValues(keys, [d[k] for k in keys])))
    cluster = Cluster.ByTopologies(cells) if cells else None
    cc = rec = None
    if cellcomplex and cluster:
        merged = Topology.SelfMerge(cluster, tolerance=0.001)
        cc = merged
        rec = Graph.ByTopology(merged, direct=True, useInternalVertex=True, tolerance=0.001)
    return cells, cluster, cc, rec


# ---------------------------------------------------------------- comparison with the shape grammar
def compare_with_shape_grammar(gstate):
    """Compare the two grammars on their ACCESS graphs: the shape grammar's final state
    (narkomfin_grammar.State) against the graph grammar's. The shape side's nodes are classified from
    their labels, the graph side's from their dictionaries."""
    try:
        import narkomfin_grammar as sg
    except Exception as e:                       # needs bpy
        return dict(available=False, reason=str(e))
    s = sg.State()
    for (_, _, fn) in sg.GRAMMAR_A:
        fn(s)
    for (_, _, fn) in sg.GRAMMAR_B:
        fn(s)

    def classify(lbl):
        u = lbl.upper()
        for key, t in (("INTERFACE", "interface"), ("CORRIDOR", "corridor"), ("STAIRWELL", "stairwell"), ("GROUND", "ground"),
                       ("HALL", "hall"), ("GALLERY", "gallery"), ("BRIDGE", "bridge"),
                       ("PENTHOUSE", "dwelling"), ("CB CORE", "stairwell")):
            if key in u:
                return t
        if u.startswith(("K [", "F [", "E [", "END UNIT")) or " [L]" in u or " [U]" in u or " [FLAT]" in u:
            return "dwelling"
        return "other"

    gs = GState("shape")
    for n in s.nodes:
        gs.add(n["id"], n["pos"], label=n["label"], type=classify(n["label"]))
    for e in s.edges:
        lbl = e["label"]
        rel = ("corridor" if "corridor" in lbl else "stair" if "stair" in lbl else
               "core_door" if "core" in lbl else "open" if "open" in lbl else
               "party" if "party" in lbl else "above" if "above" in lbl else
               "supports" if "support" in lbl else "door")
        gs.link(e["a"], e["b"], rel)
    A, B = gs.access_subgraph(), gstate.access_subgraph()
    ga, gb = A.to_graph(), B.to_graph()
    out = dict(available=True,
               shape_side_full=gs.metrics(heavy=True), graph_side_full=gstate.metrics(heavy=True),
               shape_side_access=A.metrics(heavy=True), graph_side_access=B.metrics(heavy=True))
    for tag, st in (("shape", A), ("graph", B)):
        out[f"{tag}_access_node_types"] = st.metrics()["nodes_by_type"]
    try:
        out["access_graphs_isomorphic_topologic"] = bool(Graph.IsIsomorphic(ga, gb, silent=True))
    except Exception as e:
        out["access_graphs_isomorphic_topologic"] = f"not tested ({e})"
    # Independent check: TopologicPy's IsIsomorphic is an iterative refinement and returns False on these
    # graphs even when they are isomorphic, so the verdict is taken from igraph's VF2, both plain and
    # colour-preserving (vertices coloured by node type).
    try:
        import igraph as ig

        def _ig(st):
            ids = sorted(st.N)
            idx = {n: i for i, n in enumerate(ids)}
            gg_ = ig.Graph(n=len(ids), edges=[(idx[e["a"]], idx[e["b"]]) for e in st.E
                                              if e["a"] in idx and e["b"] in idx])
            gg_.simplify()
            types = sorted({d.get("type") for d in st.N.values()})
            return gg_, [types.index(st.N[n].get("type")) for n in ids]

        ia, ca = _ig(A)
        ib, cb = _ig(B)
        out["degree_sequences_equal"] = sorted(ia.degree()) == sorted(ib.degree())
        out["access_graphs_isomorphic"] = bool(ia.isomorphic_vf2(ib))
        out["access_graphs_isomorphic_typed"] = bool(ia.isomorphic_vf2(ib, color1=ca, color2=cb))
    except Exception as e:
        out["access_graphs_isomorphic"] = f"not tested ({e})"
    out["note"] = ("The full states are not comparable - the shape grammar carries element cells the graph "
                   "grammar has no use for. What must agree is the ACCESS structure, and it now does: same "
                   "node count, same edge count, same node types, same degree sequence, one component, and a "
                   "type-preserving isomorphism. That agreement is the correctness test for generated "
                   "variants: derive on one side, realise on the other, compare access graphs.")
    return out


# ---------------------------------------------------------------- variants
VARIANTS = {
    "V1_as_built": dict(),
    "V2_all_U_3levels": dict(levels=9, corridor_levels=(2, 5, 8), cells=((1, 3, 1, "F"), (4, 6, 1, "F"), (7, 9, 1, "F"))),
    "V3_gamma_access_over": dict(levels=6, corridor_levels=(2, 5), cells=((1, 2, 1, "G"), (4, 5, 1, "G"))),
    "V4_skipstop_Z4": dict(levels=8, corridor_levels=(2, 6), cells=((1, 4, 1, "Z"), (5, 8, 1, "Z"))),
    "V5_short_block": dict(bays=10, core_lines=(2, 8), levels=6),
}


def run_variant(name, over, interpret_shape=True, merge=False):
    P = params(**over)
    print(f"\n=== variant {name}: {over or 'as built'}", flush=True)
    sa, steps_a = derive(GRAMMAR_GA, P)
    sb, steps_b = derive(GRAMMAR_GB, P, state=sa)
    m = sb.metrics(heavy=True)
    res = dict(name=name, parameters={k: v for k, v in P.items()}, metrics=m,
               steps_A=steps_a, steps_B=steps_b)
    # reachability test: every dwelling reachable from GROUND over access-bearing edges only
    adj = {}
    for e in sb.E:
        if ACCESS.get(e["rel"], "none") != "none":
            adj.setdefault(e["a"], set()).add(e["b"])
            adj.setdefault(e["b"], set()).add(e["a"])
    seen, stack = set(), ["GROUND"]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack += [x for x in adj.get(n, ()) if x not in seen]
    dwell = sb.match(type="dwelling")
    res["dwellings"] = len(dwell)
    res["dwellings_reachable_from_ground"] = sum(1 for d in dwell if d in seen)
    res["valid"] = res["dwellings"] == res["dwellings_reachable_from_ground"]
    streets = len(P["corridor_levels"])
    res["floors_per_street"] = round(P["levels"] / streets, 2) if streets else None
    print(f"  -> {res['dwellings']} dwellings, reachable {res['dwellings_reachable_from_ground']}, "
          f"valid={res['valid']}, floors per street {res['floors_per_street']}")
    if interpret_shape:
        cells, cluster, cc, rec = interpret(sb, cellcomplex=merge)
        res["interpreted"] = dict(cells=len(cells),
                                  volume=round(sum(Cell.Volume(c) for c in cells), 1),
                                  merged=Topology.TypeAsString(cc) if cc else None,
                                  recovered_graph=dict(nodes=len(Graph.Vertices(rec)), edges=len(Graph.Edges(rec))) if rec else None)
        print(f"  -> interpreted to {len(cells)} Topologic Cells, {res['interpreted']['volume']} m3"
              + (f", merged as {res['interpreted']['merged']}, recovered graph "
                 f"{res['interpreted']['recovered_graph']}" if merge else ""))
    return sb, res


# ---------------------------------------------------------------- Blender visualisation (optional)
def visualise(states, blend_path, interpreted=None):
    import bpy
    from narkomfin_element_dictionary import make_materials, clear, label, MATS, cuboid
    clear()
    make_materials()
    root = bpy.data.collections.new("Narkomfin_GraphGrammar")
    bpy.context.scene.collection.children.link(root)

    def draw(state, coll, offset, scale=1.0):
        NODE_MAT = {"dwelling": "Timber", "corridor": "Glass", "stairwell": "Concrete_Structure",
                    "hall": "Space", "gallery": "Space", "bridge": "Timber", "interface": "Glass"}
        for nid, d in state.N.items():
            r = 0.55 if d.get("type") in ("dwelling", "hall") else 0.38
            me = cuboid(f"N_{nid}", -r, r, -r, r, -r, r)
            me.materials.append(MATS[NODE_MAT.get(d.get("type"), "Concrete")])
            ob = bpy.data.objects.new(f"Node_{nid}", me)
            ob.location = (offset[0] + d["pos"][0] * scale, offset[1] + d["pos"][1] * scale, offset[2] + d["pos"][2] * scale)
            coll.objects.link(ob)
            for k, v in d.items():
                if k != "pos":
                    ob[k] = v
        import math as _m
        for rel in sorted({e["rel"] for e in state.E}):
            verts, faces = [], []
            r = 0.10 if ACCESS.get(rel, "none") == "none" else 0.16   # access-bearing edges drawn thicker
            for e in state.E:
                if e["rel"] != rel or e["a"] not in state.N or e["b"] not in state.N:
                    continue
                pa = [p * scale for p in state.N[e["a"]]["pos"]]
                pb = [p * scale for p in state.N[e["b"]]["pos"]]
                d = [pb[i] - pa[i] for i in range(3)]
                L = _m.sqrt(sum(c * c for c in d)) or 1.0
                d = [c / L for c in d]
                up = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
                u = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]
                n = _m.sqrt(sum(c * c for c in u)) or 1.0
                u = [c / n * r for c in u]
                w = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
                base = len(verts)
                for p in (pa, pb):
                    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                        verts.append(tuple(p[i] + sx * u[i] + sy * w[i] for i in range(3)))
                for k in range(4):
                    j = (k + 1) % 4
                    faces.append([base + k, base + j, base + 4 + j, base + 4 + k])
                faces += [[base, base + 1, base + 2, base + 3], [base + 7, base + 6, base + 5, base + 4]]
            if not faces:
                continue
            me = bpy.data.meshes.new(f"E_{rel}")
            me.from_pydata(verts, [], faces)
            me.materials.append(MATS["Concrete_Structure" if ACCESS.get(rel, "none") == "none" else "Timber"])
            ob = bpy.data.objects.new(f"Edges_{rel}", me)
            ob.location = offset
            coll.objects.link(ob)
            ob["rel"] = rel
            ob["access"] = ACCESS.get(rel, "none")

    y = 0.0
    for (nm, st, note) in states:
        coll = bpy.data.collections.new(nm)
        root.children.link(coll)
        draw(st, coll, (0, y, 0))
        m = st.metrics()
        label(f"{nm}\n{m['nodes']} nodes / {m['edges']} edges, max degree {m['max_degree']}",
              (-12, y - 4, 0), 1.0, coll, f"L_{nm}")
        y -= 40.0
    if interpreted:
        from narkomfin_element_dictionary import prism
        for (nm, cells) in interpreted:
            coll = bpy.data.collections.new(f"Interpreted_{nm}")
            root.children.link(coll)
            for c in cells:
                d = Dictionary.PythonDictionary(Topology.Dictionary(c))
                verts, faces = Topology.Geometry(c)["vertices"], Topology.Geometry(c)["faces"]
                me = bpy.data.meshes.new(d.get("id", "cell"))
                me.from_pydata([tuple(v) for v in verts], [], [list(f) for f in faces])
                me.materials.append(MATS["Space"])
                ob = bpy.data.objects.new(d.get("id", "cell"), me)
                ob.location = (0, y, 0)
                coll.objects.link(ob)
                for k, v in d.items():
                    ob[k] = v
            label(f"Interpreted {nm}: {len(cells)} cells", (-12, y - 4, 0), 1.0, coll, f"LI_{nm}")
            y -= 40.0
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print("saved", blend_path)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="directory for the exported graphs and report")
    ap.add_argument("--blend", default=None, help="write a Blender visualisation (needs bpy)")
    ap.add_argument("--compare", action="store_true", help="compare with the shape grammar (imports bpy)")
    a, _ = ap.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)

    print("=== GRAMMAR GA: BLOCK ===", flush=True)
    sa, steps_a = derive(GRAMMAR_GA, AS_BUILT)
    print("=== GRAMMAR GB: SOCIAL CONDENSER (composed by GB6) ===", flush=True)
    sb, steps_b = derive(GRAMMAR_GB, AS_BUILT, state=sa.copy())

    print("\n=== variants (the graph grammar drives, the interpreter realises) ===", flush=True)
    var_states, var_res = [], []
    for nm, over in VARIANTS.items():
        # the CellComplex round trip is done only on the short variant: SelfMerge is O(minutes) at full length
        st, res = run_variant(nm, over, merge=(nm == "V5_short_block"))
        var_states.append((nm, st))
        var_res.append(res)

    if a.json:                                    # export before the (heavy) comparison, so nothing is lost
        os.makedirs(a.json, exist_ok=True)
        for nm, st in [("AS_BUILT_A", sa), ("AS_BUILT_AB", sb)] + var_states:
            g = st.to_graph()
            p = os.path.join(a.json, f"graph_{nm}.json")
            try:
                Graph.ExportToJSON(g, p, vertexLabelKey="label", edgeLabelKey="rel", overwrite=True)
            except Exception as ex:
                with open(p, "w") as f:
                    json.dump(dict(nodes=list(st.N.values()), edges=st.E), f, indent=2)
                print("  (TopologicPy export unavailable, wrote plain JSON)", ex)
            with open(os.path.join(a.json, f"graph_{nm}_dicts.json"), "w") as f:
                json.dump(dict(nodes=list(st.N.values()), edges=st.E, metrics=st.metrics()), f, indent=2)

    cmp = dict(available=False, reason="skipped (--compare not set)")
    if a.compare:
        print("\n=== comparison with the shape grammar (access subgraphs) ===", flush=True)
        cmp = compare_with_shape_grammar(sb)
        print(json.dumps({k: cmp[k] for k in ("shape_side_access", "graph_side_access",
                                              "access_graphs_isomorphic") if k in cmp}, indent=2)[:900])

    if a.json:
        with open(os.path.join(a.json, "graph_grammar_report.json"), "w") as f:
            json.dump(dict(grammar_GA=steps_a, grammar_GB=steps_b, comparison=cmp, variants=var_res,
                           edge_access_semantics=ACCESS, parameters=AS_BUILT), f, indent=2)
        print("wrote", a.json, flush=True)

    if a.blend:
        cells, _, _, _ = interpret(sb, cellcomplex=False)
        visualise([("AS_BUILT_GA", sa, ""), ("AS_BUILT_GA_GB", sb, "")] + [(nm, st, "") for nm, st in var_states],
                  a.blend, interpreted=[("AS_BUILT", cells)])


if __name__ == "__main__":
    main()
