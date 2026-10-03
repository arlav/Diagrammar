# Diagrammar

`topogrammar`: a Topologic shape + graph grammar toolset. An architect supplies an axiom and a rule
pack; the library derives architectural variants through a shape grammar and a graph grammar that are
checked against each other. First case study: Dom Narkomfin (Ginzburg & Milinis, 1928-30).

The plan, its status and the findings so far are in [`docs/PLAN.md`](docs/PLAN.md).

## Set up

```bash
micromamba create -n topogrammar -c conda-forge python=3.11 pythonocc-core=8.0.1
micromamba run -n topogrammar pip install "topologicpy>=0.9.80" python-igraph numpy pytest httpx fastapi "uvicorn[standard]"
micromamba run -n topogrammar pip install -e . --no-deps
cd viewer/web && npm ci && npm run build
```

## Run the viewer

```bash
micromamba run -n topogrammar python -m uvicorn viewer.server.app:app --port 8765
```

Then open <http://127.0.0.1:8765>. Pick a rule on the left, pick a site, look at the preview, apply.

While working on the viewer itself, run `npm run dev` in `viewer/web` beside the server and open
<http://127.0.0.1:5183> instead; it reloads as you edit.

## Test

```bash
micromamba run -n topogrammar python -m pytest
TOPOLOGICPY_CORE_BACKEND=pythonocc micromamba run -n topogrammar python scripts/probe_occt8.py
```

## Layout

| Path | Contents |
|---|---|
| `topogrammar/graph/` | graph state on `TGraph`, site-level rules, derivations, metrics, VF2 comparison |
| `topogrammar/scene/` | the scene contract the viewer draws |
| `examples/narkomfin/graph/` | the Narkomfin rule pack: `pack.json` and its procedures |
| `examples/narkomfin/golden/` | the prototype's recorded graphs and report |
| `viewer/server/`, `viewer/web/` | the viewer |
| `domnarkomfin_grammar_files/` | the prototype, kept for reference |
