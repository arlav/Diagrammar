"""
metrics.py -- what is measured on a graph state
===============================================
Light metrics run after every production, so they stay on the TGraph and in Python. Isomorphism is
igraph's VF2, plain and colour-preserving by node type; `TGraph.IsIsomorphic` and `Graph.IsIsomorphic`
are refinements and are never used for a verdict.
"""
from collections import Counter

from topologicpy.TGraph import TGraph


def metrics(state):
    g = state.graph
    edges = state.edges()
    degrees = [TGraph.Degree(g, i) for i in state._ix.values()]
    types = Counter(d.get("type") for d in state.nodes().values() if d.get("type") is not None)
    return dict(nodes=len(state), edges=len(edges), max_degree=max(degrees) if degrees else 0,
                components=len(TGraph.ConnectedComponents(g)) if len(state) else 0,
                edges_by_access=dict(sorted(Counter(e["access"] for e in edges).items())),
                edges_by_rel=dict(sorted(Counter(e["rel"] for e in edges).items())),
                nodes_by_type=dict(sorted(types.items())))


def access_subgraph(state, occupiable):
    """Only nodes that can be occupied, only edges that can be walked through. This, not the full
    labelled graph, is what the shape side and the graph side must agree on."""
    occupiable = set(occupiable)
    return state.subgraph(lambda d: d.get("type") in occupiable,
                          lambda e: e.get("access", "none") != "none",
                          name=state.name + "_access")


def reachable(state, source):
    """Node ids reachable from `source` over access-bearing edges."""
    if source not in state:
        return set()
    adj = {}
    for e in state.edges():
        if e.get("access", "none") != "none":
            adj.setdefault(e["a"], set()).add(e["b"])
            adj.setdefault(e["b"], set()).add(e["a"])
    seen, stack = set(), [source]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack += [x for x in adj.get(n, ()) if x not in seen]
    return seen


def reachability(state, source, node_type):
    """How many nodes of `node_type` can be reached from `source` on foot."""
    targets = state.match(type=node_type)
    seen = reachable(state, source)
    missing = [t for t in targets if t not in seen]
    return dict(total=len(targets), reachable=len(targets) - len(missing), unreachable=missing,
                valid=bool(targets) and not missing)


def unresolved(state, nonterminals):
    """Nodes still carrying a non-terminal type: the graph grammar's unfinished business."""
    out = {}
    for nid, d in state.nodes().items():
        if d.get("type") in nonterminals:
            out.setdefault(d["type"], []).append(nid)
    return out


def cut_vertices(state):
    by_index = {i: n for n, i in state._ix.items()}
    return sorted(by_index[v["index"]] for v in TGraph.CutVertices(state.graph))


def to_igraph(nodes, edges):
    """(igraph.Graph, colours) from plain node and edge records; colours index the sorted node types."""
    import igraph as ig

    ids = sorted(n["id"] for n in nodes)
    ix = {n: i for i, n in enumerate(ids)}
    by_id = {n["id"]: n for n in nodes}
    g = ig.Graph(n=len(ids), edges=[(ix[e["a"]], ix[e["b"]]) for e in edges if e["a"] in ix and e["b"] in ix])
    g.simplify()
    types = sorted({str(n.get("type")) for n in nodes})
    return g, [types.index(str(by_id[n].get("type"))) for n in ids], types


def compare(nodes_a, edges_a, nodes_b, edges_b):
    """VF2 verdict on two graphs given as plain records."""
    ga, ca, ta = to_igraph(nodes_a, edges_a)
    gb, cb, tb = to_igraph(nodes_b, edges_b)
    same_size = ga.vcount() == gb.vcount() and ga.ecount() == gb.ecount()
    out = dict(nodes=(ga.vcount(), gb.vcount()), edges=(ga.ecount(), gb.ecount()),
               degree_sequences_equal=sorted(ga.degree()) == sorted(gb.degree()),
               node_types_equal=ta == tb and sorted(ca) == sorted(cb),
               isomorphic=False, isomorphic_typed=False)
    if same_size:
        out["isomorphic"] = bool(ga.isomorphic_vf2(gb))
        if out["node_types_equal"]:
            out["isomorphic_typed"] = bool(ga.isomorphic_vf2(gb, color1=ca, color2=cb))
    return out


def compare_states(a, b):
    return compare(list(a.nodes().values()), a.edges(), list(b.nodes().values()), b.edges())
