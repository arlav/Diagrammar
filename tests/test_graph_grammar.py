"""
The graph grammar against the prototype's recorded results.

Golden figures come from `graph_grammar_report.json` and the two recorded graphs, not from the READMEs.
"""
import json
from pathlib import Path

import pytest

from topogrammar.graph.grammar import ALL, Derivation, RulePack
from topogrammar.graph.metrics import (access_subgraph, compare, cut_vertices, metrics, reachability,
                                       unresolved)

ROOT = Path(__file__).resolve().parents[1] / "examples" / "narkomfin"
REPORT = json.loads((ROOT / "golden" / "graph_grammar_report.json").read_text())
VARIANTS = {v["name"]: v for v in REPORT["variants"]}


@pytest.fixture(scope="module")
def pack():
    return RulePack(ROOT / "graph")


def derive(pack, preset):
    d = Derivation(pack, preset=preset)
    return d, d.run()


def recorded_steps(name):
    v = VARIANTS[name]
    return [(s["rule"], s["nodes"], s["edges"]) for s in v["steps_A"] + v["steps_B"]]


# ---------------------------------------------------------------- the acceptance figures (brief, section 3)
def test_as_built_access_subgraph(pack):
    d, _ = derive(pack, "V1_as_built")
    acc = access_subgraph(d.state, pack.occupiable)
    m = metrics(acc)
    assert (m["nodes"], m["edges"]) == (115, 121)
    assert m["components"] == 1
    assert m["max_degree"] == 7
    assert m["nodes_by_type"] == dict(bridge=1, corridor=40, dwelling=53, gallery=1, ground=1, hall=1,
                                      interface=1, stairwell=17)
    assert m["edges_by_access"] == dict(door=69, open=35, stair=17)
    assert len(cut_vertices(acc)) == 49


def test_as_built_is_the_recorded_graph(pack):
    """Same ids, same edges, same relations as the prototype's composed graph."""
    d, _ = derive(pack, "V1_as_built")
    gold = pack.golden("V1_as_built")
    assert set(d.state.ids()) == {n["id"] for n in gold["nodes"]}
    pair = lambda e: (min(e["a"], e["b"]), max(e["a"], e["b"]), e["rel"], bool(e.get("mirror")))
    assert {pair(e) for e in d.state.edges()} == {pair(e) for e in gold["edges"]}
    for n in gold["nodes"]:
        mine = d.state.node(n["id"])
        assert mine["type"] == n["type"]
        if n["block"] == "A" and n["id"] != "PENTHOUSE":      # the condenser is placed as built, see pack.json
            assert mine["pos"] == pytest.approx(tuple(n["pos"]), abs=1e-3)


def test_as_built_access_graph_is_isomorphic_to_the_recorded_one(pack):
    d, _ = derive(pack, "V1_as_built")
    gold = pack.golden("V1_as_built")
    acc = access_subgraph(d.state, pack.occupiable)
    keep = {n["id"] for n in gold["nodes"] if n["type"] in pack.occupiable}
    nodes = [n for n in gold["nodes"] if n["id"] in keep]
    edges = [e for e in gold["edges"] if pack.relations[e["rel"]] != "none" and e["a"] in keep and e["b"] in keep]
    verdict = compare(list(acc.nodes().values()), acc.edges(), nodes, edges)
    assert verdict["degree_sequences_equal"]
    assert verdict["isomorphic"]
    assert verdict["isomorphic_typed"]


@pytest.mark.parametrize("preset", ["V1_as_built", "V5_short_block"])
def test_every_production_matches_the_recorded_step(pack, preset):
    _, steps = derive(pack, preset)
    assert [(s.rule, s.metrics["nodes"], s.metrics["edges"]) for s in steps] == recorded_steps(preset)


@pytest.mark.parametrize("preset", sorted(VARIANTS))
def test_every_dwelling_is_reachable_from_the_ground(pack, preset):
    d, _ = derive(pack, preset)
    r = reachability(d.state, pack.source, "dwelling")
    assert r["valid"], r["unreachable"]
    assert r["total"] == pack.presets[preset]["expect"]["dwellings"]
    if preset in ("V1_as_built", "V5_short_block"):
        assert r["total"] == VARIANTS[preset]["dwellings"]


# ---------------------------------------------------------------- where the port departs from the prototype
def as_prototype(state, P):
    """Undo the two corrections the port makes, to show they are the whole difference.

    1. The prototype names a dwelling by tag and bay only, so stacked cells that share a tag (V2, V3,
       V4) are one node, carrying the level of the last cell. Here they are separate dwellings.
    2. The prototype gives the dwelling beside a core its lobby door only if it is tagged K or F."""
    s = state.copy()
    groups = {}
    for n in s.match(type="dwelling"):
        if s.get(n, "bay") is not None and s.get(n, "tag") != "E":
            groups.setdefault((s.get(n, "tag"), s.get(n, "bay")), []).append(n)
    top = {key: max(s.get(n, "level") for n in nodes) for key, nodes in groups.items()}
    for e in s.edges():
        if e["rel"] != "core_door":
            continue
        for n in (e["a"], e["b"]):
            key = (s.get(n, "tag"), s.get(n, "bay"))
            if key in groups and (key[0] not in ("K", "F") or s.get(n, "level") != top[key]):
                s.unlink(e["a"], e["b"])
    for (tag, bay), nodes in groups.items():
        if len(nodes) > 1:
            s.contract(sorted(nodes), f"{tag}{bay:02d}", type="dwelling", tag=tag, bay=bay)
    return s


@pytest.mark.parametrize("preset", ["V2_all_U_3levels", "V3_gamma_access_over", "V4_skipstop_Z4"])
def test_stacked_cells_account_for_the_whole_difference(pack, preset):
    d, _ = derive(pack, preset)
    recorded = VARIANTS[preset]
    s = as_prototype(d.state, d.P)
    m = metrics(s)
    assert (m["nodes"], m["edges"]) == (recorded["metrics"]["nodes"], recorded["metrics"]["edges"])
    assert m["edges_by_access"] == recorded["metrics"]["edges_by_access"]
    assert len(s.match(type="dwelling")) == recorded["dwellings"]


def test_v4_reduced_to_the_prototype_is_the_recorded_graph(pack):
    d, _ = derive(pack, "V4_skipstop_Z4")
    gold = json.loads((ROOT / "golden" / "graph_V4_skipstop_Z4_dicts.json").read_text())
    s = as_prototype(d.state, d.P)
    verdict = compare(list(s.nodes().values()), s.edges(), gold["nodes"], gold["edges"])
    assert verdict["isomorphic"]


@pytest.mark.parametrize("preset,dwellings", [("V2_all_U_3levels", 81), ("V3_gamma_access_over", 53),
                                              ("V4_skipstop_Z4", 61)])
def test_stacked_cells_are_separate_dwellings(pack, preset, dwellings):
    d, _ = derive(pack, preset)
    assert len(d.state.match(type="dwelling")) == dwellings
    assert not d.state.conflicts


# ---------------------------------------------------------------- terminal discipline
def test_no_bay_survives_the_as_built_derivation(pack):
    d, _ = derive(pack, "V1_as_built")
    left = unresolved(d.state, pack.nonterminals)
    assert "bay" not in left and "mass" not in left
    assert left == dict(storey=["CB0", "CB3"])          # the condenser storeys GB never rewrites


@pytest.mark.parametrize("preset,bays", [("V3_gamma_access_over", 16), ("V5_short_block", 5)])
def test_leftover_bays_are_reported_not_relabelled(pack, preset, bays):
    """The prototype's roof rule turned every surviving bay into roof, which hid these."""
    d, _ = derive(pack, preset)
    left = unresolved(d.state, pack.nonterminals)["bay"]
    assert len(left) == bays
    assert all(d.state.get(n, "level") < d.P["levels"] for n in left)


# ---------------------------------------------------------------- site-level derivation
def test_order_inside_a_stage_is_free(pack):
    """Derive by hand, one site at a time, in reverse order: the result is the same graph."""
    a, _ = derive(pack, "V1_as_built")
    b = Derivation(pack, preset="V1_as_built")
    while True:
        entry = next((e for e in b.applicable() if e["enabled"]), None)
        if entry is None:
            break
        b.apply(entry["rule"].id, entry["sites"][-1].key)
    pair = lambda e: (min(e["a"], e["b"]), max(e["a"], e["b"]), e["rel"], bool(e.get("mirror")))
    assert set(a.state.ids()) == set(b.state.ids())
    assert {pair(e) for e in a.state.edges()} == {pair(e) for e in b.state.edges()}
    assert len(b.steps) > 70                              # every site was its own step


def test_stages_hold_rules_back(pack):
    d = Derivation(pack, preset="V1_as_built")
    enabled = lambda: {e["rule"].id for e in d.applicable() if e["enabled"]}
    assert enabled() == {"GA0", "GB0"}
    d.apply("GA0"), d.apply("GA1"), d.apply("GA2")
    d.apply("GA3", "L1")
    assert "GA4" not in enabled()                         # five storeys are still undivided
    with pytest.raises(ValueError, match="waits for GA3"):
        d.apply("GA4", ALL)
    d.apply("GA3", ALL)
    assert "GA4" in enabled()


def test_the_bridge_needs_the_street(pack):
    """Grammar GB is derived on its own; only R_BRIDGE waits for grammar GA."""
    d = Derivation(pack, preset="V1_as_built")
    for rule in ("GB0", "GB1", "GB2", "GB3", "GB4", "GB5"):
        d.apply(rule)
    assert not next(e for e in d.applicable() if e["rule"].id == "GB6")["enabled"]
    assert metrics(d.state)["components"] == 2           # the condenser, and the interface node
    for rule in ("GA0", "GA1", "GA2"):
        d.apply(rule)
    d.apply("GA3", ALL), d.apply("GA4", ALL)
    d.apply("GB6")
    assert d.state.edge("IFACE", "c1_00")["rel"] == "door"


def test_facade_is_an_identity_production(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run(until="GA6")
    before = metrics(d.state)
    step = d.apply("GA7")
    assert step.metrics == before
    assert step.event["identity"]
    assert not step.event["nodes_added"] and not step.event["edges_added"]
    assert not next(e for e in d.applicable() if e["rule"].id == "GA7")["sites"]


def test_going_back_and_choosing_again_starts_a_branch(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run(until="GA2")
    fork = d.head
    d.apply("GA3", "L1")
    d.goto(fork)
    d.apply("GA3", "L6")
    assert len(d.steps[fork].children) == 2
    assert "b6_00" in d.state and "b1_00" not in d.state


def test_a_rewrite_step_is_within_budget(pack):
    _, steps = derive(pack, "V1_as_built")
    assert max(s.elapsed_ms / s.applications for s in steps) < 50
