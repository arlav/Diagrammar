# `topogrammar` — implementation plan (viewer first)

Status: P0 and P1 complete. P2 (element data and shape rule packs) next. Date: 2026-09-27.
Source brief: `BRIEF_topogrammar_ClaudeCode (1).md`. Prototype: `domnarkomfin_grammar_files/`.

## 1. Decisions taken

| Decision | Choice |
|---|---|
| Viewer platform | Web app: three.js front end, local Python server running TopologicPy |
| Interaction in v1 | Graph-side driving, graph views, derivation timeline |
| Sequencing | Viewer first, library grown underneath it |
| Package name | `topogrammar`, inside the `Diagrammar` repo |
| Prototype folders | Reference material only; never imported by the library |

Not in v1: click-to-apply on shape cells, live parameter sliders. Picking in the 3D model is for
inspection; parameters are set in an axiom form and applied on submit.

## 2. Prototype inventory

| Folder | Contents | Ported as |
|---|---|---|
| `files (13)`, `files (15)` | `narkomfin_grammar.py` (A0–A8, B0–B6), `narkomfin_grammar.json`, rule-card previews | `examples/narkomfin/` shape rule packs |
| `files (14)` | `narkomfin_graph_grammar.py` (GA/GB), report and variant graph JSON | `topogrammar/graph/`, golden fixtures |
| `files (16)` | `narkomfin_element_dictionary.py`, `narkomfin_elements.json` (33 types, ports, parameters) | `topogrammar/elements/` as data + Cell builders |
| `files (17)` | `build_narkomfin.py`, `narkomfin_to_topologic.py`, elements schedule CSV, OBJ | `topogrammar/realise/`, `interop/blender.py`, regression figures |

Files shared between folders are byte-identical.

## 3. Environment

Verified on this machine (macOS arm64):

- `pythonocc-core 8.0.1` (OCCT 8.0.1) is on conda-forge for osx-arm64.
- The `topologicpy 0.9.80` wheel contains `ShapeGrammar.py`, `CSG.py`, `TGraph.py`, `pythonocc_backend/_provenance.py`.
- Installed today: `topologicpy 0.9.71` under pyenv, no OCC. `micromamba` is available, `conda` is not.

```bash
micromamba create -n topogrammar -c conda-forge python=3.11 pythonocc-core=8.0.1
micromamba activate topogrammar
pip install "topologicpy>=0.9.80" python-igraph numpy pytest fastapi "uvicorn[standard]"
export TOPOLOGICPY_CORE_BACKEND=pythonocc
```

Confirmed in P0: Python 3.11.16 with `pythonocc-core 8.0.1` resolves; the active backend is
`PythonOCCBackend`. Run commands with `micromamba run -n topogrammar ...`.

## 4. How the two directions are wired

The brief's default (axis D3) runs shape → ledger → graph. The viewer drives from the graph. Both hold:

1. **Driven side.** The user selects node(s) and applies a constructive graph rule (GA/GB).
2. **Following side.** The paired shape rule runs through `ShapeGrammar`; the ledger records the events;
   the provenance-driven `TGraph` is rebuilt from those events.
3. **Lockstep.** The two access graphs are compared with igraph VF2, type-preserving, after each step.
   The result is a live badge in the viewer and an assertion in the tests.

Until P4 the following side is the prototype's `interpret()` (graph → cells from node dictionaries).

## 5. Rules become site-level

Prototype rules are whole-building batch functions (`GA3_bay` rewrites every storey at once).
Interactive selection needs match sites. Every rule is therefore:

```
match(state)               -> list of sites
apply(state, site, params) -> new state + ledger event
stage                      -> gates what the rule palette offers
```

"Apply to all matches" reproduces the prototype's batch step, so the golden figures still hold.
Rules load from YAML/JSON as the brief requires; Python only for procedural right-hand sides.

## 6. Repository layout

```
topogrammar/            library, as in the brief (elements, axiom, shape, provenance, graph,
                        realise, search, registry, interop)
topogrammar/scene/      scene contract: state -> JSON (cells, faces, graph, ledger, metrics, rules)
viewer/server/          FastAPI + WebSocket, sessions, derivation tree
viewer/web/             Vite + React + TypeScript + three.js
examples/narkomfin/     rule packs, axiom, golden fixtures
tests/  docs/
```

The library never imports the viewer. The viewer consumes only the scene contract.

## 7. Viewer

Stack: react-three-fiber, `three-mesh-bvh` for picking, Cytoscape.js for the 2D graph, zustand for state.

| Panel | Content |
|---|---|
| 3D model | Space cells; shared faces coloured by access (none, door, open, stair); realised elements as a layer |
| Graph in 3D | Nodes at cell centroids; access-bearing edges thick and warm, adjacency-only thin and grey; full or access subgraph |
| Graph 2D | Abstract layout; node selection; linked highlighting with the 3D model |
| Rule palette | Rules applicable at the selection; LHS → RHS card; preview before apply |
| Timeline | Step, undo, branch; count of unresolved non-terminals at each step |
| Ledger | Events per step, coloured by the six relations, with lineage |
| Invariants | Live metrics against the golden figures |
| Variants | Small multiples of V1–V5 with reachability |
| Element dictionary | The 33 types with ports and parameters |

## 8. Phases

| Phase | Deliverable | Done when |
|---|---|---|
| P0 | Environment, M0 probe, scaffold | `docs/occt8_probe.md` lists exact binding names; `ShapeGrammar` smoke test passes on the OCC backend |
| P1 | Viewer on the graph grammar | GA/GB as site-level rules; as-built derivable by selecting rules; access graph 115 / 121 / 1 / 7; V1–V5 reachability |
| P2 | M1 elements + M2 shape packs | 33 types load from JSON, each builder returns one valid `Cell`; `History()` non-empty for every application |
| P3 | M3 ledger + policy engine | Party-wall faces carry `DV.WALL.PARTY` from the rule; MERGED conflicts reported; ledger hashes deterministically |
| P4 | M4 provenance-driven `TGraph` | Lockstep badge green on the as-built derivation; step < 50 ms, full derivation < 1 s |
| P5 | M5 axiom, variants, search | Variants gallery; canonical de-dup; over-constrained axiom fails fast |
| P6 | M6 realisation + interop | Thick elements layer; Blender and JSON export; 1,776 elements as regression figure |

P1 needs no OCCT: the prototype's graph rewriting is pure Python and the interpreter's prisms can be
meshed directly for display.

## 9. Golden figures

Taken from `graph_grammar_report.json` and the brief, not from the READMEs.

| Metric | Value |
|---|---|
| Access subgraph nodes / edges | 115 / 121 |
| Components / max degree / cut vertices | 1 / 7 / 49 |
| Node types | bridge 1, corridor 40, dwelling 53, gallery 1, ground 1, hall 1, interface 1, stairwell 17 |
| Edges by access | open 35, door 69, stair 17 |
| Full composed graph | 137 / 232 |
| Reachability | V1 53/53, V2 49/49, V3 37/37, V4 45/45, V5 24/24 |

## 10. Findings in the prototype

| # | Finding | Proposed handling |
|---|---|---|
| 1 | READMEs are stale: composed graph given as 137 / 240 with 77 door edges (JSON: 232, 69); shape side given as 118 / 136 (JSON: 126 / 198) | Use the JSON; correct the READMEs when ported |
| 2 | `GA8_roof` relabels every surviving `bay` node as `roof`. V3 ends with 36 `roof` nodes, which includes mid-building bays | Restrict to the top level so a leftover bay is a real failure |
| 3 | Two `storey` nodes survive every final state (condenser levels that GB never rewrites) | Add a terminal rule for them, or exempt them explicitly |
| 4 | K dwellings: the grammars make 16 one-bay K nodes (8 marked as mirror pairs); the element dictionary and as-built model have 8 two-bay K units | Decided, see §11 |
| 5 | Corridor depth is 1.80 in both grammars and 1.29 in `SP.CORRIDOR` | Decided, see §11 |
| 6 | `SP.CELL.K` and `SP.CELL.F` are plain cuboids in the dictionary; the grammar gives them L and U sections | Builders take `(levels, corridor_level)` and call the section rule |
| 7 | `narkomfin_element_dictionary.py` line 504 writes to a hard-coded `/home/claude/out2/rows.json` | Irrelevant once ported as data; do not run the script as is |
| 8 | `occurrences` mixes integers and strings ("≈180 pieces") | Schema: `count` integer or null, plus `count_note` string |

### Found while porting the graph grammar (P1)

| # | Finding | Handling |
|---|---|---|
| 9 | **The prototype fused stacked cells.** A dwelling was named by tag and bay only, so where two or three groups share a tag (V2, V3, V4) the cells of one bay were one node. The recorded 49, 37 and 45 dwellings are that artefact | Dwellings are separate: 81, 53 and 61, all reachable. A test undoes the correction and recovers the prototype's figures exactly, so this is the whole difference. **The brief's V2-V4 figures need Theo's confirmation** |
| 10 | The lobby door to the dwelling beside a core was given only to tags K and F, so V3 and V4 had none | Given to every cell tag |
| 11 | That lobby door attaches on the dwelling's lowest level, not the level it is entered on. For an F cell that is L3, while its street is on L4. Both prototype grammars agree on this | Kept, because the as-built figures depend on it. **Open question** |
| 12 | V5 leaves bay 7 outside both the cells and the end units: `ends = 3` was written for cores at lines 2 and 19 | Kept as recorded (24 dwellings); reported as 5 unresolved bays and as a warning |
| 13 | The prototype placed the condenser away from the block for display, so its bridge touched nothing | Placed as built, from the elements README: origin (-7.21, -22.96) in the block's frame |
| 14 | `Graph.ByVerticesEdges` is not needed: `TGraph` is the state. A copy takes about 4 ms and a whole as-built derivation about 0.15 s | Within the brief's budgets |

## 11. Decisions on the findings (Theo, 2026-09-27)

1. **K units.** Keep 16 one-bay K dwellings; the 115 / 121 figures stand. The two-bay pair is added
   later as its own contraction rule (`R_PAIR`, giving 45 dwellings).
2. **Corridor depth.** 1.80 m is authoritative. `SP.CORRIDOR` in the ported element data is corrected
   from 1.29 to 1.80.
3. **P0 approved.**

## 12. What P1 delivered

- `topogrammar/graph/`: `GraphState` on `TGraph` with semantic ids; site-level rules with stages;
  derivation tree with preview, undo and branches; metrics, reachability, VF2 comparison.
- `examples/narkomfin/graph/`: the rule pack as data (`pack.json`) plus procedures, an interpreter
  (graph to prisms) and a parameter check that fails fast.
- `viewer/`: server and web app. 3D cells and graph, 2D graph in elevation, plan or force layout,
  rule palette with sites, preview before apply, derivation tree, checks against the golden figures,
  the event of each production, the element dictionary.
- 44 tests. As built: 115 / 121, one component, max degree 7, 49 cut vertices; every production
  matches the prototype's recorded step; VF2 type-preserving against the recorded graph.

Two departures from section 7 of this plan: the server answers over plain HTTP rather than a
WebSocket, since every action returns one scene; and picking uses three.js raycasting directly, which
is fast enough at this size without `three-mesh-bvh`.

## 13. What the M0 probe changes

Full results in `docs/occt8_probe.md`.

- Every identity and history binding the brief asks about exists, so the B2 adapter (axis B) and the
  A2 native UID (axis A) are both feasible. Call signatures are still to be exercised.
- **The cut face is not GENERATED.** `ShapeGrammar` `Divide` reports it as `modified` with
  `sourceRole = tool` (Face -> Face, operation `Slice`), carrying an empty dictionary. The M3 classifier
  therefore maps `modified` + `tool` + Face under a divide to the grammar-level GENERATED relation, and
  the rule supplies the dictionary (`DV.WALL.PARTY`, `access = none`). This is exact identity, not
  geometric matching.
- No face in the result is history-silent: 11 faces, 11 face records.
- Cost: a 22-way divide of one cell takes about 250 ms and yields 743 history records. Six storeys is
  about 1.5 s, which is fine for the shape side; the 50 ms budget applies to the graph rewrite.

## 14. Questions for Wassim

As listed in §8 of the brief; answers collected in `docs/wassim_questions.md`.
