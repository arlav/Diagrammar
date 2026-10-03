"""The server answers every action with a scene the viewer can draw as it is."""
import pytest
from fastapi.testclient import TestClient

from viewer.server.app import app

client = TestClient(app)


def start(**body):
    r = client.post("/api/session", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_pack_is_described():
    p = client.get("/api/pack").json()
    assert len(p["rules"]) == 16
    assert set(p["presets"]) >= {"V1_as_built", "V4_skipstop_Z4"}
    assert p["relations"]["party"] == "none"


def test_element_dictionary_has_33_types():
    assert len(client.get("/api/elements").json()["elements"]) == 33


def test_a_new_derivation_offers_the_two_axioms():
    s = start(preset="V1_as_built")
    assert s["graph"]["nodes"] == [] and s["cells"] == []
    assert [r["id"] for r in s["rules"] if r["enabled"]] == ["GA0", "GB0"]
    assert all(c["status"] != "fail" for c in s["invariants"]["checks"])


def test_apply_preview_undo():
    s = start(preset="V1_as_built")
    sid = s["session"]
    post = lambda path, **body: client.post(f"/api/session/{sid}/{path}", json=body)
    for rule in ("GA0", "GA1", "GA2"):
        assert post("apply", rule=rule).status_code == 200
    p = post("preview", rule="GA3", site="L3").json()
    assert p["preview"] and p["head"] == 3
    assert p["event"]["nodes_removed"] == ["L3"] and len(p["event"]["nodes_added"]) == 22
    assert len(client.get(f"/api/session/{sid}").json()["timeline"]) == 4      # a preview takes no step
    a = post("apply", rule="GA3", site="L3").json()
    assert a["head"] == 4 and len(a["cells"]) == 1 + 5 + 22
    assert post("undo").json()["head"] == 3
    assert post("apply", rule="GA4", site="*").status_code == 409


def test_the_complete_as_built_scene():
    s = start(preset="V1_as_built")
    done = client.post(f"/api/session/{s['session']}/run", json={}).json()
    assert done["complete"]
    inv = done["invariants"]
    assert (inv["access"]["nodes"], inv["access"]["edges"]) == (115, 121)
    assert inv["oracle"]["isomorphic_typed"]
    failed = [c["name"] for c in inv["checks"] if c["status"] != "ok"]
    assert failed == ["unresolved non-terminals"]                 # the two condenser storeys
    assert sum(e["in_access_graph"] for e in done["graph"]["edges"]) == 121
    cell = next(c for c in done["cells"] if c["id"] == "F03")
    assert len(cell["positions"]) % 3 == 0 and max(cell["indices"]) < len(cell["positions"]) // 3
    assert {c["id"] for c in done["cells"]} == {n["id"] for n in done["graph"]["nodes"]} - {"IFACE"}


def test_parameters_are_checked_before_anything_is_derived():
    r = client.post("/api/session", json=dict(preset="V1_as_built", parameters=dict(corridor_levels=[2, 4])))
    assert r.status_code == 422
    assert "entered on L1, where there is no street" in " ".join(r.json()["detail"]["problems"])
    r = client.post("/api/session", json=dict(parameters=dict(storeys=3)))
    assert r.status_code == 422


def test_an_edited_preset_is_not_held_to_the_preset_figures():
    s = start(preset="V1_as_built", parameters=dict(bays=12, core_lines=[2, 9], ends=3))
    assert s["preset"] is None
    done = client.post(f"/api/session/{s['session']}/run", json={}).json()
    assert done["invariants"]["reachability"]["valid"]
    assert done["invariants"]["oracle"] is None


def test_warnings_name_what_will_stay_unresolved():
    assert any("L3" in w for w in start(preset="V3_gamma_access_over")["warnings"])
    assert start(preset="V1_as_built")["warnings"] == []
