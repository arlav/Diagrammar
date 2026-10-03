"""
build.py -- the scene contract
==============================
Everything a viewer needs to draw one step of a derivation, as plain JSON:

    cells        one per interpreted node: id, category, dictionary, triangles, outline
    graph        nodes (id, pos, dictionary) and edges (a, b, rel, access)
    metrics      of the full graph and of the access subgraph
    invariants   the figures this derivation must reach, against what it has reached
    rules        every rule that is a choice, with its open sites grouped, and what each competes with
    pathway      the choices made so far, with their hash chain
    timeline     the derivation tree
    event        what the production that led here did, and the consequences that followed

The viewer consumes nothing else. When the cells come from the shape grammar instead of the
interpreter, the contract does not change.
"""
from ..graph.metrics import access_subgraph, compare, cut_vertices, metrics, reachability, unresolved
from ..graph.rules import describe as describe_rule
from .mesh import prism


def _cells(pack, state, P):
    nodes = state.nodes()
    out = []
    for c in pack.modules["interpret"].cells(state, dict(P, dim=pack.dimensions)):
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
    r = reachability(state, pack.source, "dwelling")
    if "dwellings" in expect:
        out.append(_check("dwellings", expect["dwellings"], r["total"], pending))
    out.append(_check(f"dwellings reachable from {pack.source}", r["total"], r["reachable"], pending))
    out.append(_check("access graph: one component", 1, m_acc["components"] if m_acc["nodes"] else 1, pending))
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


def _site(o):
    s = o["site"]
    return dict(key=s.key, label=s.label, nodes=list(s.nodes), touched=list(s.touched), params=dict(s.params),
                decisive=o["decisive"], conflicts_with=o["conflicts_with"], conflicts=len(o["conflicts"]))


def _rules(pack, derivation):
    """Every rule, with its open sites grouped the way the rule asks, and what each group competes with."""
    offers = derivation.offers()
    by_rule = {}
    for o in offers:
        by_rule.setdefault(o["site"].rule, []).append(o)
    out = []
    for r in pack.rules.values():
        if r.auto:
            continue
        groups = {}
        for o in by_rule.get(r.id, []):
            g = groups.setdefault(o["site"].group, dict(label=o["site"].group, sites=[], competes_with=set(), params=dict(o["site"].params)))
            g["sites"].append(_site(o))
            g["competes_with"] |= set(o["conflicts_with"]) - {r.id}
        out.append(dict(describe_rule(r), enabled=bool(groups), site_count=len(by_rule.get(r.id, [])),
                        groups=[dict(g, competes_with=sorted(g["competes_with"])) for g in groups.values()]))
    return out


def _timeline(derivation):
    path = set(derivation.path())
    return [dict(id=s.id, parent=s.parent, rule=s.rule, site=(s.sites[0].key if len(s.sites) == 1 else "*") if s.sites else None,
                 label=s.label, nodes=s.metrics["nodes"], edges=s.metrics["edges"], applications=s.applications,
                 consequences=len(s.consequences), elapsed_ms=round(s.elapsed_ms, 2), children=list(s.children),
                 on_path=s.id in path, decisions=s.decisions)
            for s in derivation.steps.values()]


def _step(step):
    return dict(id=step.id, parent=step.parent, rule=step.rule, label=step.label, applications=step.applications, decisions=step.decisions,
                consequences=[dict(rule=r, label=l) for r, l in step.consequences], elapsed_ms=round(step.elapsed_ms, 2),
                params=dict(step.sites[0].params) if step.sites else {})


def scene(derivation, preview=None, extra=None):
    """The scene at the head of the derivation, or of a previewed step that has not been taken."""
    pack = derivation.pack
    step = preview if preview is not None else derivation.steps[derivation.head]
    state = step.state
    complete = preview is None and derivation.complete()
    return dict(
        preview=preview is not None,
        pack=pack.title, pack_hash=pack.hash(), preset=derivation.preset, parameters=derivation.P,
        dimensions=pack.dimensions,
        step=_step(step), head=derivation.head, complete=complete,
        event=step.event,
        cells=_cells(pack, state, derivation.P),
        graph=_graph(pack, state),
        invariants=_invariants(pack, derivation, state, complete),
        rules=[] if preview is not None else _rules(pack, derivation),
        timeline=_timeline(derivation),
        pathway=derivation.pathway(),
        **(extra or {}),
    )


def describe(pack, name=None):
    """What a viewer needs to know about a pack before any derivation exists."""
    return dict(name=name, title=pack.title, version=pack.version, model=pack.model, hash=pack.hash(),
                lineage=pack.lineage(), diff=pack.diff(), source=pack.source,
                relations=pack.relations, occupiable=pack.occupiable, nonterminals=pack.nonterminals,
                dimensions=pack.dimensions, parameters=pack.parameters, parameter_notes=pack.parameter_notes,
                presets={k: dict(title=v["title"], note=v.get("note", ""), parameters=v.get("parameters", {}),
                                 strategy=v.get("strategy"), expect=v.get("expect", {}))
                         for k, v in pack.presets.items()},
                strategies={k: dict(id=k, title=v["title"], note=v.get("note", ""), steps=len(v["steps"]))
                            for k, v in pack.strategies.items()},
                rules=[describe_rule(r) for r in pack.rules.values()])
