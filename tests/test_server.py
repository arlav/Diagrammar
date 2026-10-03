"""The server answers every action with a scene the viewer can draw as it is."""
from fastapi.testclient import TestClient

from viewer.server.app import app

client = TestClient(app)


def start(**body):
    r = client.post("/api/session", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_packs_are_described():
    packs = client.get("/api/packs").json()
    names = {p["name"]: p for p in packs}
    assert {"narkomfin", "unite"} <= set(names)
    assert names["unite"]["diff"]["base"] == "Dom Narkomfin"
    assert names["narkomfin"]["relations"]["party"] == "none"
    assert any(r["auto"] for r in names["narkomfin"]["rules"])


def test_a_rule_card_is_drawn_from_the_data():
    card = client.get("/api/pack/narkomfin/card/cell", params={"params": '{"k": 2, "ci": 0}'}).json()
    assert list(card["lhs"]["nodes"]) == ["b0", "b1", "c"]
    assert card["rhs"]["contract"]["nodes"] == ["b0", "b1"]


def test_element_dictionary_has_33_types():
    assert len(client.get("/api/elements").json()["elements"]) == 33


def test_a_new_derivation_offers_the_two_axioms():
    s = start(pack="narkomfin", preset="V1_as_built")
    assert s["graph"]["nodes"] == [] and s["cells"] == []
    assert [r["id"] for r in s["rules"] if r["enabled"]] == ["axiom_block", "axiom_condenser"]
    assert s["strategy"]["id"] == "as_built" and s["strategy"]["cursor"] == 0


def test_apply_preview_undo():
    s = start(preset="V1_as_built")
    sid = s["session"]
    post = lambda path, **body: client.post(f"/api/session/{sid}/{path}", json=body)
    for rule in ("axiom_block", "lift", "stack"):
        assert post("apply", rule=rule).status_code == 200
    p = post("preview", rule="bay", select={"where": "s.level == 3"}).json()
    assert p["preview"] and p["head"] == 3
    assert p["event"]["nodes_removed"] == ["L3"] and len(p["event"]["nodes_added"]) == 22
    assert len(client.get(f"/api/session/{sid}").json()["timeline"]) == 4
    a = post("apply", rule="bay", select={"where": "s.level == 3"}).json()
    assert a["head"] == 4 and len(a["cells"]) == 1 + 5 + 22
    assert post("undo").json()["head"] == 3
    assert post("apply", rule="cell", select="*").status_code == 409


def test_the_pathway_runs_to_the_recorded_building():
    s = start(preset="V1_as_built")
    done = client.post(f"/api/session/{s['session']}/run", json={"mode": "all"}).json()
    assert done["complete"] is False                      # the condenser storeys and a few offers remain
    inv = done["invariants"]
    assert (inv["access"]["nodes"], inv["access"]["edges"]) == (115, 121)
    assert inv["oracle"] is None or inv["oracle"]["isomorphic_typed"]
    assert done["pathway"]["hash"] and len(done["pathway"]["steps"]) == 19
    assert done["strategy"]["cursor"] == 19


def test_the_pathway_can_be_followed_step_by_step():
    s = start(preset="V1_as_built")
    sid = s["session"]
    a = client.post(f"/api/session/{sid}/run", json={"mode": "next"}).json()
    assert a["strategy"]["cursor"] == 1 and a["step"]["rule"] == "axiom_block"
    b = client.post(f"/api/session/{sid}/run", json={"mode": "continue"}).json()
    assert b["strategy"]["cursor"] == 19 and b["invariants"]["reachability"]["valid"]


def test_a_pathway_replays_in_a_fresh_derivation():
    s = start(preset="V1_as_built")
    sid = s["session"]
    client.post(f"/api/session/{sid}/run", json={"mode": "continue"})
    p = client.get(f"/api/session/{sid}/pathway").json()
    t = start(preset="V1_as_built")
    r = client.post(f"/api/session/{t['session']}/replay", json={"pathway": p})
    assert r.status_code == 200, r.text
    assert r.json()["pathway"]["hash"] == p["hash"]


def test_the_unite_derives():
    s = start(pack="unite", preset="unite")
    done = client.post(f"/api/session/{s['session']}/run", json={"mode": "continue"}).json()
    assert done["invariants"]["reachability"] == dict(total=81, reachable=81, unreachable=[], valid=True)
    assert any(c["id"] == "U03_L2" for c in done["cells"])


def test_parameters_are_checked_before_anything_is_derived():
    r = client.post("/api/session", json=dict(preset="V1_as_built", parameters=dict(storeys=3)))
    assert r.status_code == 422
    r = client.post("/api/session", json=dict(parameters=dict(bays="twenty")))
    assert r.status_code == 422
