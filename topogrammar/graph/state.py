"""
state.py -- the labelled graph under rewriting
==============================================
The state of the graph grammar is a topologicpy `TGraph`. `GraphState` adds the two things a grammar
needs on top of it: semantic ids (the brief's axis A3: nodes are addressed by grammar-assigned ids, never
by raw index) and the rewriting primitives `add`, `link`, `remove`, `contract`.

Semantics live in dictionaries on the vertices and the edges. Every edge carries

    rel     the relation (party, door, stair, ...)
    access  what that relation means for movement: none | open | door | stair

`party` edges have access "none": adjacent but not connected.
"""
from topologicpy.TGraph import TGraph

# keys TGraph writes into the dictionaries it stores; they are bookkeeping, not semantics
_TGRAPH_KEYS = ("index", "active", "src", "dst", "directed")
_POS_KEYS = ("x", "y", "z")


def _clean(d):
    return {k: v for k, v in d.items() if k not in _TGRAPH_KEYS}


class GraphState:
    """A labelled graph addressed by semantic id, stored in a TGraph."""

    def __init__(self, name="G", access=None):
        self.name = name
        self.access = dict(access or {})      # rel -> access
        self.graph = TGraph(directed=False, allowSelfLoops=False, allowParallelEdges=False)
        self.flags = set()                    # productions that leave no trace in the graph (axioms, identities)
        self.conflicts = []                   # contractions that met two relations on one pair
        self._ix = {}                         # semantic id -> TGraph index

    # -- reading ----------------------------------------------------------
    def __contains__(self, nid):
        return nid in self._ix

    def __len__(self):
        return len(self._ix)

    def ids(self):
        return sorted(self._ix)

    def node(self, nid):
        d = _clean(self.graph.VertexDictionary(self._ix[nid], copy=True))
        d["pos"] = tuple(d.pop(k) for k in _POS_KEYS)
        return d

    def nodes(self):
        return {nid: self.node(nid) for nid in self.ids()}

    def get(self, nid, key, default=None):
        if nid not in self._ix:
            return default
        return self.graph.VertexDictionary(self._ix[nid], copy=False).get(key, default)

    def edges(self):
        by_index = {i: nid for nid, i in self._ix.items()}
        out = []
        for e in TGraph.Edges(self.graph):
            d = _clean(e["dictionary"])
            out.append(dict(a=by_index[e["src"]], b=by_index[e["dst"]], **d))
        return out

    def edge(self, a, b):
        """The edge between two nodes, or None."""
        if a not in self._ix or b not in self._ix:
            return None
        e = TGraph.Edge(self.graph, vertexA=self._ix[a], vertexB=self._ix[b], silent=True)
        return None if e is None else dict(a=a, b=b, **_clean(e["dictionary"]))

    def neighbours(self, nid):
        by_index = {i: n for n, i in self._ix.items()}
        i = self._ix[nid]
        out = []
        for e in TGraph.IncidentEdges(self.graph, i):
            other = e["dst"] if e["src"] == i else e["src"]
            out.append((by_index[other], _clean(e["dictionary"])))
        return out

    def match(self, **kw):
        """LHS matcher: every node whose dictionary agrees with the given key/values, sorted by id."""
        out = []
        for nid in self.ids():
            d = self.graph.VertexDictionary(self._ix[nid], copy=False)
            if all(d.get(k) == v for k, v in kw.items()):
                out.append(nid)
        return out

    # -- rewriting primitives ---------------------------------------------
    def add(self, nid, pos, **props):
        if nid in self._ix:
            raise ValueError(f"node '{nid}' already exists")
        x, y, z = (round(float(v), 3) for v in pos)
        self._ix[nid] = self.graph.AddVertex(dict(id=nid, x=x, y=y, z=z, **props))
        return nid

    def link(self, a, b, rel, **props):
        """Add an edge. Returns False when an end is missing: a rule may offer a link to a neighbour
        that a variant does not have."""
        if a not in self._ix or b not in self._ix or a == b:
            return False
        if self.edge(a, b) is not None:
            return False
        self.graph.AddEdge(self._ix[a], self._ix[b],
                           dictionary=dict(rel=rel, access=self.access.get(rel, "none"), **props), silent=True)
        return True

    def unlink(self, a, b):
        if a not in self._ix or b not in self._ix:
            return False
        e = TGraph.Edge(self.graph, vertexA=self._ix[a], vertexB=self._ix[b], silent=True)
        if e is None:
            return False
        self.graph.RemoveEdge(e["index"], silent=True)
        return True

    def remove(self, *nids):
        for nid in nids:
            i = self._ix.pop(nid, None)
            if i is not None:
                self.graph.RemoveVertex(i, silent=True)

    def update(self, nid, **props):
        for k, v in props.items():
            if k == "pos":
                for kk, vv in zip(_POS_KEYS, v):
                    self.graph.SetVertexValue(self._ix[nid], kk, round(float(vv), 3), silent=True)
            else:
                self.graph.SetVertexValue(self._ix[nid], k, v, silent=True)

    def update_edge(self, a, b, **props):
        e = TGraph.Edge(self.graph, vertexA=self._ix[a], vertexB=self._ix[b], silent=True)
        if e is None:
            return False
        for k, v in props.items():
            self.graph.SetEdgeValue(e["index"], k, v, silent=True)
        return True

    def contract(self, nids, new_id, pos=None, **props):
        """Vertex contraction: several nodes become one. Edges to the outside survive, edges between the
        contracted nodes dissolve. The new node takes its dictionary from the rule, not from its sources.

        If two contracted nodes reach the same outside node by different relations, the pair keeps one
        edge and the clash is recorded in `conflicts` rather than resolved silently."""
        nids = [n for n in nids if n in self._ix]
        if not nids:
            return None
        if new_id in self._ix and new_id not in nids:
            raise ValueError(f"node '{new_id}' already exists")
        run = set(nids)
        reached = {}
        for n in nids:
            for other, d in self.neighbours(n):
                if other not in run:
                    reached.setdefault(other, []).append(d.get("rel"))
        for other, rels in reached.items():
            if len(set(rels)) > 1:
                self.conflicts.append(dict(node=new_id, neighbour=other, relations=sorted(set(rels)),
                                           kept=rels[0]))
        if pos is None:
            ps = [self.node(n)["pos"] for n in nids]
            pos = tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
        target = self._ix[nids[0]]
        TGraph.MergeVertices(self.graph, [self._ix[n] for n in nids], targetVertex=target,
                             transferDictionaries=False, silent=True)
        for n in nids:
            del self._ix[n]
        self._ix[new_id] = target
        x, y, z = (round(float(v), 3) for v in pos)
        self.graph.SetVertexDictionary(target, dict(id=new_id, x=x, y=y, z=z, **props))
        return new_id

    # -- copies -----------------------------------------------------------
    def copy(self):
        s = GraphState.__new__(GraphState)
        s.name = self.name
        s.access = self.access
        s.graph = TGraph.Copy(self.graph)
        s.flags = set(self.flags)
        s.conflicts = [dict(c) for c in self.conflicts]
        s._ix = dict(self._ix)
        return s

    def subgraph(self, keep_node, keep_edge, name=None):
        """A new state holding the nodes and edges the two predicates accept."""
        s = GraphState(name or self.name, self.access)
        for nid, d in self.nodes().items():
            if keep_node(d):
                pos = d.pop("pos")
                d.pop("id")
                s.add(nid, pos, **d)
        for e in self.edges():
            if e["a"] in s and e["b"] in s and keep_edge(e):
                props = {k: v for k, v in e.items() if k not in ("a", "b", "rel", "access")}
                s.link(e["a"], e["b"], e["rel"], **props)
        return s
