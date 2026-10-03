"""
app.py -- the viewer's server
=============================
Holds derivations in memory and answers every action with the scene that results. The viewer keeps no
state of its own beyond what it is looking at.

    uvicorn viewer.server.app:app --port 8765          (from the repository root)
"""
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from topogrammar.graph.grammar import Derivation, RulePack
from topogrammar.scene.build import describe, scene

ROOT = Path(__file__).resolve().parents[2]
PACK = Path(os.environ.get("TOPOGRAMMAR_PACK", ROOT / "examples" / "narkomfin" / "graph"))
ELEMENTS = ROOT / "examples" / "narkomfin" / "elements" / "prototype_elements.json"
DIST = ROOT / "viewer" / "web" / "dist"

app = FastAPI(title="topogrammar viewer")
pack = RulePack(PACK)
sessions = {}


class NewSession(BaseModel):
    preset: str | None = None
    parameters: dict | None = None


class Action(BaseModel):
    rule: str
    site: str | None = None


class Goto(BaseModel):
    step: int


class Run(BaseModel):
    until: str | None = None


def derivation(sid):
    if sid not in sessions:
        raise HTTPException(404, "This derivation is no longer in memory. Start a new one.")
    return sessions[sid]


def answer(sid, d, **kw):
    return dict(session=sid, warnings=pack.modules["validate"].warnings(d.P), **scene(d, **kw))


def attempt(fn):
    try:
        return fn()
    except (ValueError, StopIteration) as ex:
        raise HTTPException(409, str(ex) or "That rule is not in this pack.")


@app.get("/api/pack")
def get_pack():
    return describe(pack)


@app.get("/api/elements")
def get_elements():
    return json.loads(ELEMENTS.read_text())


@app.post("/api/session")
def new_session(body: NewSession):
    if body.preset is not None and body.preset not in pack.presets:
        raise HTTPException(404, f"There is no preset called {body.preset}.")
    P = pack.params(body.preset, **(body.parameters or {}))
    unknown = sorted(set(body.parameters or {}) - set(pack.data["parameters"]))
    found = [f"{k} is not a parameter of this pack" for k in unknown] or pack.modules["validate"].problems(P)
    if found:
        raise HTTPException(422, dict(message="These parameters do not describe a building the grammar can derive.",
                                      problems=found))
    sid = uuid.uuid4().hex[:12]
    # a preset that has been edited is no longer that preset: its figures do not apply
    sessions[sid] = Derivation(pack, params=P, preset=None if body.parameters else body.preset)
    return answer(sid, sessions[sid])


@app.get("/api/session/{sid}")
def get_scene(sid: str):
    return answer(sid, derivation(sid))


@app.post("/api/session/{sid}/preview")
def preview(sid: str, body: Action):
    d = derivation(sid)
    return answer(sid, d, preview=attempt(lambda: d.preview(body.rule, body.site)))


@app.post("/api/session/{sid}/apply")
def apply(sid: str, body: Action):
    d = derivation(sid)
    attempt(lambda: d.apply(body.rule, body.site))
    return answer(sid, d)


@app.post("/api/session/{sid}/goto")
def goto(sid: str, body: Goto):
    d = derivation(sid)
    attempt(lambda: d.goto(body.step))
    return answer(sid, d)


@app.post("/api/session/{sid}/undo")
def undo(sid: str):
    d = derivation(sid)
    d.undo()
    return answer(sid, d)


@app.post("/api/session/{sid}/run")
def run(sid: str, body: Run):
    d = derivation(sid)
    if body.until is not None and body.until not in pack.by_id:
        raise HTTPException(404, f"There is no rule called {body.until}.")
    d.run(until=body.until)
    return answer(sid, d)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
