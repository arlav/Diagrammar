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

from topogrammar.graph.derivation import Derivation
from topogrammar.graph.pack import Pack
from topogrammar.scene.build import describe, scene

ROOT = Path(__file__).resolve().parents[2]
PACKS = {name: Pack(ROOT / "examples" / name / "graph") for name in ("narkomfin", "unite")}
if os.environ.get("TOPOGRAMMAR_PACK"):
    PACKS["custom"] = Pack(os.environ["TOPOGRAMMAR_PACK"])
ELEMENTS = ROOT / "examples" / "narkomfin" / "elements" / "prototype_elements.json"
DIST = ROOT / "viewer" / "web" / "dist"

app = FastAPI(title="topogrammar viewer")
sessions = {}


class Session:
    def __init__(self, pack_name, preset, parameters):
        self.pack_name = pack_name
        pack = PACKS[pack_name]
        P = pack.params(preset, **(parameters or {}))
        # a preset that has been edited is no longer that preset: its figures do not apply
        self.derivation = Derivation(pack, params=P, preset=None if parameters else preset)
        self.strategy = pack.presets.get(preset, {}).get("strategy") if preset else None
        self.cursor = 0                         # how far along the recorded pathway this derivation is
        self.skipped = []                       # recorded steps that found nothing to apply

    @property
    def pack(self):
        return PACKS[self.pack_name]


class NewSession(BaseModel):
    pack: str = "narkomfin"
    preset: str | None = None
    parameters: dict | None = None


class Action(BaseModel):
    rule: str
    select: str | list | dict | None = None


class Goto(BaseModel):
    step: int


class Run(BaseModel):
    mode: str = "continue"                    # continue | all | next


class Replay(BaseModel):
    pathway: dict


def session(sid):
    if sid not in sessions:
        raise HTTPException(404, "This derivation is no longer in memory. Start a new one.")
    return sessions[sid]


def answer(sid, s, **kw):
    d = s.derivation
    strategy = s.pack.strategies.get(s.strategy) if s.strategy else None
    extra = dict(session=sid, pack_name=s.pack_name,
                 strategy=dict(id=s.strategy, title=strategy["title"], steps=len(strategy["steps"]), cursor=s.cursor,
                               skipped=list(s.skipped),
                               next=strategy["steps"][s.cursor] if s.cursor < len(strategy["steps"]) else None)
                 if strategy else None)
    return scene(d, extra=extra, **kw)


def attempt(fn):
    try:
        return fn()
    except (ValueError, StopIteration, KeyError) as ex:
        raise HTTPException(409, str(ex) or "That rule is not in this pack.")


@app.get("/api/packs")
def get_packs():
    return [describe(p, name) for name, p in PACKS.items()]


@app.get("/api/pack/{name}")
def get_pack(name: str):
    if name not in PACKS:
        raise HTTPException(404, f"There is no pack called {name}.")
    return describe(PACKS[name], name)


@app.get("/api/pack/{name}/card/{rule}")
def get_card(name: str, rule: str, params: str | None = None):
    pack = PACKS.get(name)
    if pack is None or rule not in pack.rules:
        raise HTTPException(404, f"There is no rule called {rule} in {name}.")
    p = tuple(sorted(json.loads(params).items())) if params else None
    return attempt(lambda: pack.rules[rule].card(pack.env(pack.params()), params=p))


@app.get("/api/elements")
def get_elements():
    return json.loads(ELEMENTS.read_text())


@app.post("/api/session")
def new_session(body: NewSession):
    if body.pack not in PACKS:
        raise HTTPException(404, f"There is no pack called {body.pack}.")
    pack = PACKS[body.pack]
    if body.preset is not None and body.preset not in pack.presets:
        raise HTTPException(404, f"There is no preset called {body.preset}.")
    unknown = sorted(set(body.parameters or {}) - set(pack.parameters))
    problems = [f"{k} is not a parameter of this pack" for k in unknown]
    for k, v in (body.parameters or {}).items():
        if k in pack.parameters and (not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 60):
            problems.append(f"{k} must be a whole number between 1 and 60")
    if problems:
        raise HTTPException(422, dict(message="These parameters do not describe a building the grammar can derive.",
                                      problems=problems))
    sid = uuid.uuid4().hex[:12]
    sessions[sid] = Session(body.pack, body.preset, body.parameters)
    return answer(sid, sessions[sid])


@app.get("/api/session/{sid}")
def get_scene(sid: str):
    return answer(sid, session(sid))


@app.post("/api/session/{sid}/preview")
def preview(sid: str, body: Action):
    s = session(sid)
    return answer(sid, s, preview=attempt(lambda: s.derivation.preview(body.rule, body.select)))


@app.post("/api/session/{sid}/apply")
def apply(sid: str, body: Action):
    s = session(sid)
    attempt(lambda: s.derivation.apply(body.rule, body.select))
    return answer(sid, s)


@app.post("/api/session/{sid}/goto")
def goto(sid: str, body: Goto):
    s = session(sid)
    attempt(lambda: s.derivation.goto(body.step))
    return answer(sid, s)


@app.post("/api/session/{sid}/undo")
def undo(sid: str):
    s = session(sid)
    s.derivation.undo()
    return answer(sid, s)


@app.post("/api/session/{sid}/run")
def run(sid: str, body: Run):
    """Follow the recorded pathway: the next step, or all the remaining ones."""
    s = session(sid)
    strategy = s.pack.strategies.get(s.strategy) if s.strategy else None
    if strategy is None:
        raise HTTPException(409, "This derivation follows no recorded pathway; choose rules by hand.")
    steps = strategy["steps"]
    if body.mode == "all":
        sessions[sid] = s = Session(s.pack_name, s.derivation.preset, None)
        s.derivation.run(strategy)
        s.cursor = len(steps)
        return answer(sid, s)
    end = min(len(steps), s.cursor + 1) if body.mode == "next" else len(steps)
    while s.cursor < end:
        done = s.derivation.run({"steps": [steps[s.cursor]]})
        if not done:
            s.skipped.append(dict(index=s.cursor, rule=steps[s.cursor]["rule"]))
        s.cursor += 1
    return answer(sid, s)


@app.get("/api/session/{sid}/pathway")
def pathway(sid: str):
    return session(sid).derivation.pathway()


@app.post("/api/session/{sid}/replay")
def replay(sid: str, body: Replay):
    s = session(sid)
    fresh = Session(s.pack_name, s.derivation.preset, None)
    fresh.derivation.P = dict(body.pathway.get("parameters") or fresh.derivation.P)
    attempt(lambda: fresh.derivation.replay(body.pathway))
    sessions[sid] = fresh
    return answer(sid, fresh)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
