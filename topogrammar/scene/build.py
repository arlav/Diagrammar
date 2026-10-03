"""
build.py -- the scene contract
==============================
Everything a viewer needs to draw one step of a derivation, as plain JSON:

    cells        one per interpreted node: id, category, dictionary, triangles, outline
    graph        nodes (id, pos, dictionary) and edges (a, b, rel, access)
    metrics      of the full graph and of the access subgraph
    invariants   the figures this derivation must reach, against what it has reached
    rules        every rule with its open sites here and, if it is held back, why
    timeline     the derivation tree
    event        what the production that led here did

The viewer consumes nothing else. When the cells come from the shape grammar instead of the
interpreter, the contract does not change.
"""
from ..graph.metrics import (access_subgraph, compare, cut_vertices, metrics, reachability, unresolved)
from .mesh import prism


def _cells(pack, state, P):
    nodes = state.nodes()
    out = []
    for c in pack.modules["interpret"].cells(state, P):
        n = nodes[c["id"]]
        out.append(dict(id=c["id"], category=c["category"], type=n.get("type"), block=n.get("block"),
                        level=n.get("level"), symbol=n.get("symbol"),
                        **prism(c["profile"], c["axis"], c["a0"], c["a1"])))
    return out


def _graph(pack, state):
    occupiable = set(pack.occupiable)
    nodes = []
    for nid, d in state.nodes().items():
        pos = d.pop("pos")
        nodes.append(dict(id=nid, pos=list(pos), type=d.get("type"), label=d.get("label", nid),
                          occupiable=d.get("type") in occupiable,
                          terminal=d.get("type") not in pack.nonterminals, dictionary=d))
    ids = {n["id"]: n for n in nodes}
    edges = []
    for e in state.edges():
        walkable = e["access"] != "none" and ids[e["a"]]["occupiable"] and ids[e["b"]]["occupiable"]
        edges.append(dict(e, in_access_graph=walkable))
    return dict(nodes=nodes, edges=edges)


def _check(name, expected, actual, pending):
    ok = expected == actual
    return dict(name=name, expected=expected, actual=actual,
                status="ok" if ok else ("pending" if pending else "fail"))


def _invariants(pack, derivation, state, complete):
    """The acceptance figures of the preset, measured on this state. Before the derivation is complete
    a figure that is not reached yet is pending, not failed."""
    preset = pack.presets.get(derivation.preset or "", {})
    expect = preset.get("expect", {})
    pending = not complete
    acc = access_subgraph(state, pack.occupiable)
    m_acc, m_full = metrics(acc), metrics(state)
    out = []
    a = expect.get("access", {})
    for key, title in (("nodes", "access graph: nodes"), ("edges", "access graph: edges"),
                       ("components", "access graph: components"), ("max_degree", "access graph: max degree"),
                       ("nodes_by_type", "access graph: node types"),
                       ("edges_by_access", "access graph: edges by access")):
        if key in a:
            out.append(_check(title, a[key], m_acc[key], pending))
    if "cut_vertices" in a:
        out.append(_check("access graph: cut vertices", a["cut_vertices"], len(cut_vertices(acc)), pending))
    for key, title in (("nodes", "full graph: nodes"), ("edges", "full graph: edges")):
        if key in expect.get("full", {}):
            out.append(_check(title, expect["full"][key], m_full[key], pending))
    r = reachability(state, pack.source, "dwelling")
    if "dwellings" in expect:
        out.append(_check("dwellings", expect["dwellings"], r["total"], pending))
    out.append(_check(f"dwellings reachable from {pack.source}", r["total"], r["reachable"], pending))
    left = unresolved(state, pack.nonterminals)
    out.append(_check("unresolved non-terminals", 0, sum(len(v) for v in left.values()), pending))

    oracle = None
    gold = pack.golden(derivation.preset) if derivation.preset else None
    if gold is not None and complete:
        keep = {n["id"] for n in gold["nodes"] if n["type"] in pack.occupiable}
        verdict = compare(list(acc.nodes().values()), acc.edges(),
                          [n for n in gold["nodes"] if n["id"] in keep],
                          [e for e in gold["edges"] if pack.relations[e["rel"]] != "none"
                           and e["a"] in keep and e["b"] in keep])
        oracle = dict(against="the prototype's recorded access graph", method="igraph VF2", **verdict)
    return dict(checks=out, oracle=oracle, reachability=r, unresolved=left,
                access=m_acc, full=m_full, conflicts=state.conflicts)


def _rules(derivation):
    out = []
    for a in derivation.applicable():
        r = a["rule"]
        out.append(dict(id=r.id, name=r.name, grammar=r.grammar, stage=r.stage, operation=r.operation,
                        shape_operation=r.shape_operation, description=r.description, identity=r.identity,
                        symbols=list(r.symbols), enabled=a["enabled"], reason=a["reason"],
                        sites=[dict(key=s.key, label=s.label, nodes=list(s.nodes)) for s in a["sites"]]))
    return out


def _timeline(derivation):
    path = set(derivation.path())
    return [dict(id=s.id, parent=s.parent, rule=s.rule, site=s.site, label=s.label,
                 nodes=s.metrics["nodes"], edges=s.metrics["edges"], applications=s.applications,
                 elapsed_ms=round(s.elapsed_ms, 2), children=list(s.children), on_path=s.id in path)
            for s in derivation.steps.values()]


def _step(step):
    return dict(id=step.id, parent=step.parent, rule=step.rule, site=step.site, label=step.label,
                note=step.note, applications=step.applications, elapsed_ms=round(step.elapsed_ms, 2))


def scene(derivation, preview=None):
    """The scene at the head of the derivation, or of a previewed step that has not been taken."""
    pack = derivation.pack
    step = preview if preview is not None else derivation.steps[derivation.head]
    state = step.state
    complete = preview is None and derivation.complete()
    P = {k: v for k, v in derivation.P.items() if k != "dim"}
    return dict(
        preview=preview is not None,
        preset=derivation.preset, parameters=P, dimensions=derivation.P["dim"],
        step=_step(step), head=derivation.head, complete=complete,
        event=step.event,
        cells=_cells(pack, state, derivation.P),
        graph=_graph(pack, state),
        invariants=_invariants(pack, derivation, state, complete),
        rules=[] if preview is not None else _rules(derivation),
        timeline=_timeline(derivation),
    )


def describe(pack):
    """What a viewer needs to know about a pack before any derivation exists."""
    d = pack.data
    return dict(title=pack.title, version=pack.version, model=d["model"], source=pack.source,
                relations=pack.relations, occupiable=pack.occupiable, nonterminals=pack.nonterminals,
                dimensions=pack.dimensions, parameters=d["parameters"], parameter_notes=d["parameter_notes"],
                presets={k: dict(title=v["title"], note=v["note"], parameters=v["parameters"],
                                 expect=v.get("expect", {}), prototype=v.get("prototype"))
                         for k, v in pack.presets.items()},
                rules=[{k: r[k] for k in ("id", "name", "grammar", "stage", "operation", "shape_operation",
                                          "description")} | dict(identity=r.get("identity", False),
                                                                 symbols=r.get("symbols", []))
                       for r in d["rules"]])
