"""
The graph grammar as local productions, against the prototype's recorded results.

Golden figures come from `graph_grammar_report.json` and the recorded as-built graph.
"""
import json
import re
from pathlib import Path

import pytest

from topogrammar.graph.derivation import ALL, Derivation
from topogrammar.graph.metrics import access_subgraph, compare, cut_vertices, metrics, reachability, unresolved
from topogrammar.graph.pack import Pack
from topogrammar.graph.patterns import Expr, Pattern, Snapshot, expand, matches

ROOT = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module")
def pack():
    return Pack(ROOT / "narkomfin" / "graph")


@pytest.fixture(scope="module")
def unite():
    return Pack(ROOT / "unite" / "graph")


def derive(pack, preset):
    d = Derivation(pack, params=pack.params(preset), preset=preset)
    d.run(pack.strategies[pack.presets[preset]["strategy"]])
    return d


def norm(nid):
    """The prototype named a cell by tag and bay, and had one penthouse."""
    return re.sub(r"_L\d+$", "", nid.replace("PH_02", "PENTHOUSE"))


# ---------------------------------------------------------------- the acceptance figures (brief, section 3)
def test_as_built_access_subgraph(pack):
    d = derive(pack, "V1_as_built")
    acc = access_subgraph(d.state, pack.occupiable)
    m = metrics(acc)
    assert (m["nodes"], m["edges"]) == (115, 121)
    assert m["components"] == 1
    assert m["max_degree"] == 7
    assert m["nodes_by_type"] == dict(bridge=1, corridor=40, dwelling=53, gallery=1, ground=1, hall=1,
                                      interface=1, stairwell=17)
    assert m["edges_by_access"] == dict(door=69, open=35, stair=17)
    assert len(cut_vertices(acc)) == 49


def test_as_built_access_graph_is_the_recorded_one(pack):
    """Same nodes, same access edges, same relations as the prototype's composed graph."""
    d = derive(pack, "V1_as_built")
    gold = pack.golden("V1_as_built")
    acc = access_subgraph(d.state, pack.occupiable)
    keep = {n["id"] for n in gold["nodes"] if n["type"] in pack.occupiable}
    assert {norm(n) for n in acc.ids()} == keep
    pair = lambda e: (min(norm(e["a"]), norm(e["b"])), max(norm(e["a"]), norm(e["b"])), e["rel"])
    gold_edges = {pair(e) for e in gold["edges"] if pack.relations[e["rel"]] != "none"
                  and e["a"] in keep and e["b"] in keep}
    assert {pair(e) for e in acc.edges()} == gold_edges
    verdict = compare(list(acc.nodes().values()), acc.edges(), [n for n in gold["nodes"] if n["id"] in keep],
                      [e for e in gold["edges"] if pack.relations[e["rel"]] != "none" and e["a"] in keep and e["b"] in keep])
    assert verdict["isomorphic_typed"]


def test_the_full_graph_has_the_recorded_node_count(pack):
    d = derive(pack, "V1_as_built")
    assert metrics(d.state)["nodes"] == 137


@pytest.mark.parametrize("preset,dwellings", [("V1_as_built", 53), ("V2_all_U", 81), ("V3_gamma", 57),
                                              ("V4_skip_stop", 61)])
def test_every_dwelling_is_reachable_from_the_ground(pack, preset, dwellings):
    d = derive(pack, preset)
    r = reachability(d.state, pack.source, "dwelling")
    assert r["valid"], r["unreachable"]
    assert r["total"] == dwellings == pack.presets[preset]["expect"]["dwellings"]
    assert metrics(access_subgraph(d.state, pack.occupiable))["components"] == 1


# ---------------------------------------------------------------- terminal discipline
def test_no_bay_survives_the_as_built_derivation(pack):
    d = derive(pack, "V1_as_built")
    left = unresolved(d.state, pack.nonterminals)
    assert left == dict(storey=["CB0", "CB3"])          # the condenser storeys no rule rewrites


def test_gamma_leaves_its_third_level_to_the_architect(pack):
    d = derive(pack, "V3_gamma")
    left = unresolved(d.state, pack.nonterminals)["bay"]
    assert len(left) == 12 and all(d.state.get(n, "level") == 3 for n in left)
    assert any(o["site"].rule == "street" and d.state.get(o["site"].nodes[0], "level") == 3 for o in d.offers())


# ---------------------------------------------------------------- rules as data
def test_expressions_are_restricted():
    assert Expr("abs(a - b) + 1")({"a": 1, "b": 3}) == 3
    with pytest.raises(ValueError):
        Expr("__import__('os')")
    with pytest.raises(ValueError):
        Expr("a._secret")


def test_families_expand_for_parameters():
    spec = {"nodes": {"b[j]": {"type": "bay", "for": "j in range(k)"}},
            "edges": [["b[j]", "b[j+1]", "above", {"for": "j in range(k - 1)"}]]}
    out = expand(spec, {"k": 3})
    assert list(out["nodes"]) == ["b0", "b1", "b2"]
    assert out["edges"] == [["b0", "b1", "above"], ["b1", "b2", "above"]]


def test_a_pattern_matches_what_it_describes(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    snap = Snapshot(d.state)
    p = Pattern.build({"nodes": {"a": {"type": "bay"}, "b": {"type": "bay", "bay": "=a.bay", "level": "=a.level + 1"}},
                       "edges": [["a", "b", "above"]]}, {})
    found = list(matches(p, snap, {}))
    assert len(found) == 22 * 5
    assert all(d.state.get(m["b"], "level") == d.state.get(m["a"], "level") + 1 for m in found)


def test_rules_have_cards(pack):
    card = pack.rules["cell"].card(pack.env(pack.params()), params=(("k", 3), ("ci", 1)))
    assert list(card["lhs"]["nodes"]) == ["b0", "b1", "b2", "c"]
    assert ["c", "b1", "door"] in card["lhs"]["edges"]
    assert len(card["nac"]) == 2                          # no second door on b0 or b2
    assert card["rhs"]["contract"]["into"] == "d"


# ---------------------------------------------------------------- free choice
def test_every_match_is_offered_and_consequences_are_not(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    offers = d.offers()
    rules = {o["site"].rule for o in offers}
    assert {"street", "core", "roof", "axiom_condenser"} <= rules
    assert not any(pack.rules[r].auto for r in rules)
    assert sum(1 for o in offers if o["site"].rule == "street") == 132
    assert sum(1 for o in offers if o["site"].rule == "core") == 132


def test_consequences_follow_every_choice(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run({"steps": pack.strategies["as_built"]["steps"][:3]})
    step = d.apply("bay", ALL)
    assert [r for r, _ in step.consequences] == ["stack_adjacent"] * 110
    assert step.event["edges_added"] and all(e["rel"] in ("party", "above") for e in step.event["edges_added"])


def test_the_order_of_independent_choices_does_not_matter(pack):
    a = Derivation(pack, preset="V1_as_built")
    a.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    b = Derivation(pack, preset="V1_as_built")
    b.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    a.apply("street", {"where": "b.level == 1"}), a.apply("street", {"where": "b.level == 4"})
    b.apply("street", {"where": "b.level == 4"}), b.apply("street", {"where": "b.level == 1"})
    pair = lambda e: (min(e["a"], e["b"]), max(e["a"], e["b"]), e["rel"])
    assert set(a.state.ids()) == set(b.state.ids())
    assert {pair(e) for e in a.state.edges()} == {pair(e) for e in b.state.edges()}


def test_the_order_of_conflicting_choices_is_a_design(pack):
    """Street before core: the street runs through the core. Core before street: it stops there."""
    a = Derivation(pack, preset="V1_as_built")
    a.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    a.apply("street", {"where": "b.level == 1"}), a.apply("core", {"where": "b.bay == 2"})
    b = Derivation(pack, preset="V1_as_built")
    b.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    b.apply("core", {"where": "b.bay == 2"}), b.apply("street", {"where": "b.level == 1"})
    assert "c1_02" in a.state and "c1_02" not in b.state
    assert a.state.edge("S1_02", "c1_02")["rel"] == "door"
    assert a.state.edge("c1_01", "c1_02")["rel"] == "corridor"


def test_conflicts_are_marked(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run({"steps": pack.strategies["as_built"]["steps"][:6]})
    cell = next(o for o in d.offers() if o["site"].rule == "cell" and dict(o["site"].params) == {"k": 2, "ci": 0}
                and "b1_03" in o["site"].nodes)
    assert cell["decisive"]
    assert {"cell", "street", "core"} <= set(cell["conflicts_with"])
    facade = next(o for o in d.offers() if o["site"].rule == "facade")
    assert not facade["decisive"]


def test_a_preview_takes_no_step_and_a_branch_keeps_both(pack):
    d = Derivation(pack, preset="V1_as_built")
    d.run({"steps": pack.strategies["as_built"]["steps"][:3]})
    before = len(d.steps)
    p = d.preview("bay", ALL)
    assert p.metrics["nodes"] == 133 and len(d.steps) == before
    fork = d.head
    d.apply("bay", {"where": "s.level == 1"})
    d.goto(fork)
    d.apply("bay", {"where": "s.level == 6"})
    assert len(d.steps[fork].children) == 2
    assert "b6_00" in d.state and "b1_00" not in d.state


# ---------------------------------------------------------------- pathways
def test_a_pathway_replays_and_hashes_the_same(pack):
    d = derive(pack, "V1_as_built")
    p = d.pathway()
    assert p["pack"] == pack.hash() and len(p["steps"]) == len(d.path()) - 1 == 19
    e = Derivation(pack, preset="V1_as_built")
    e.replay(p)
    assert e.pathway()["hash"] == p["hash"]
    assert metrics(e.state) == metrics(d.state)


def test_a_different_choice_gives_a_different_hash(pack):
    a = Derivation(pack, preset="V1_as_built")
    a.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    b = Derivation(pack, preset="V1_as_built")
    b.run({"steps": pack.strategies["as_built"]["steps"][:4]})
    a.apply("core", {"where": "b.bay == 2"})
    b.apply("core", {"where": "b.bay == 3"})
    assert a.pathway()["hash"] != b.pathway()["hash"]
    assert a.pathway()["steps"][:4] == b.pathway()["steps"][:4]


# ---------------------------------------------------------------- transformation: Narkomfin -> Unité
def test_the_unite_is_a_transformation_of_narkomfin(unite, pack):
    diff = unite.diff()
    assert diff["base_hash"] == pack.hash()
    assert diff["changed"] == ["street"]
    assert diff["added"] == ["cell_down", "cell_up"]
    assert "cell" in diff["removed"] and "bridge" in diff["removed"]
    assert diff["dimensions"]["depth"] == (9.9, 24.0)
    assert [l["title"] for l in unite.lineage()] == ["Dom Narkomfin", "Unité d'Habitation"]
    assert unite.hash() != pack.hash()


def test_the_unite_derives_with_interlocked_cells(unite):
    d = derive(unite, "unite")
    r = reachability(d.state, unite.source, "dwelling")
    assert r["valid"] and r["total"] == 81
    acc = access_subgraph(d.state, unite.occupiable)
    assert metrics(acc)["components"] == 1
    assert not unresolved(d.state, unite.nonterminals)
    up = d.state.node("U03_L2")
    down = d.state.node("D03_L1")
    assert up["kind"] == "up" and down["kind"] == "down"
    assert d.state.edge("U03_L2", "c2_03")["rel"] == "door" and d.state.edge("D03_L1", "c2_03")["rel"] == "door"
    assert d.state.edge("U03_L2", "D03_L1")["rel"] == "above"          # the down cell's lower level is under the up cell's street half


def test_unite_cells_are_interpreted_as_sections(unite):
    d = derive(unite, "unite")
    cells = {c["id"]: c for c in unite.modules["interpret"].cells(d.state, dict(d.P, dim=unite.dimensions))}
    assert len(cells["U03_L2"]["profile"]) == 6 and cells["U03_L2"]["axis"] == "x"
    assert cells["c2_03"]["profile"][0][1] == pytest.approx(24.0 / 2 - 2.6 / 2)


def test_a_rewrite_step_is_within_budget(pack):
    d = derive(pack, "V1_as_built")
    assert max(s.elapsed_ms / max(1, s.applications) for s in d.steps.values() if s.id) < 50
