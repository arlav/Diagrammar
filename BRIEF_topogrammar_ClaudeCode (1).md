# Brief for Claude Code — `topogrammar`: a Topologic shape + graph grammar toolset

**Owner:** Theo · **Collaborator:** Wassim Jabi (TopologicPy) · **First case study:** Dom Narkomfin (Ginzburg & Milinis, 1928–30)

## 0. Mission

Build a Python library in which an architect supplies an **axiom** (a sketch as a topology, plus a rule
pack, parameter ranges, constraints and objectives) and the library derives **architectural variants**
through a shape grammar and a graph grammar that run from both ends and are checked against each other.

A working prototype exists (see §3). It proved the idea but was built on hand-rolled geometry and a
hand-rolled graph. This build moves it onto **TopologicPy ≥ 0.9.80 on the pythonocc-core 8 / OCCT 8
backend**, where native Boolean history and BRepGraph give us provenance for free — and where
TopologicPy already ships a `ShapeGrammar`, a `CSG` DAG and a `TGraph` that do much of what the prototype
reinvented.

**Do not reinvent what TopologicPy now provides.** Read §2 before writing code.

---

## 1. Environment

```bash
conda create -n topogrammar -c conda-forge python=3.11 pythonocc-core   # must be an OCCT 8 build
conda activate topogrammar
pip install "topologicpy>=0.9.80" python-igraph numpy pytest
export TOPOLOGICPY_CORE_BACKEND=pythonocc     # force the OCC backend; do not silently fall back
```

**M0 probe (first task, write results to `docs/occt8_probe.md`):**

1. `from OCC.Core.BRepGraph import brepgraph, BRepGraph_NodeId, BRepGraph_ChildExplorer` imports.
2. `topologicpy.Core` reports `PythonOCCBackend` as active.
3. Probe the pythonocc bindings for the OCCT 8.0.1 identity/history API Wassim describes and record the
   **exact** Python names that exist (they are not yet used anywhere in TopologicPy 0.9.80):
   - durable identity: `UID`, `RefUID`, `ItemUID` (OCCT recommends these over raw `NodeId`)
   - `BRepGraph::ShapesView::AddWithHistory(...)`
   - `BRepGraph_LayerHistory` and its Modified / Generated / Deleted / Replaced queries, both directions
     (source → derived and derived → original, with multiple origins allowed)
4. Smoke-test `topologicpy.ShapeGrammar`: one Divide rule on a box, read `History()`, `GeneratedBy()`,
   `ModifiedBy()`, `LineageGraph()`.

If any binding is missing, do **not** work around it with geometric matching. Record the gap and continue
with the fallback path in §5.

---

## 2. What TopologicPy 0.9.80 already provides (read the source)

Source: `topologicpy/` and `topologicpy/pythonocc_backend/`. Findings from reading it:

| Module | What it does | Use it for |
|---|---|---|
| `ShapeGrammar.py` | Compiled, cached, provenance-aware grammar. `AddRule(input, output, operation=Replace\|Boolean\|Transform\|Divide, matrix, uSides/vSides/wSides, metadata)`. Matching via `Topology.IsSimilar` with a cheap pre-filter by type and structural counts. `ApplicableRules`, `Match`, `ApplyRule`, `History`, `GeneratedBy/ModifiedBy/UnchangedBy/DeletedBy`, `Origins`, `Descendants`, `LineageGraph()` and `DerivationGraph()` (both `TGraph`), `Data/Export/ByPath` (JSON, optional BREP). | **The shape-grammar engine.** Our rules become `ShapeGrammar` rules. |
| `CSG.py` | A CSG DAG (`Union/Intersect/Difference/XOR/Merge/Impose/Imprint/Slice/Transform`), `Compile/Evaluate/Invalidate`, per-operation lineage and the same `History/GeneratedBy/...` queries. | Composite rules whose RHS is a small Boolean program. |
| `TGraph.py` | Topology-first pure-Python graph: indexed vertex/edge records with Python dictionaries, optional topology representations, directed/parallel/self-loop flags, versioning. | **The graph-grammar state.** Replaces the prototype's `GState` + `Graph.ByVerticesEdges` materialisation, which was the measured bottleneck. |
| `pythonocc_backend/_provenance.py` | "Tranche 3" dictionary lineage. `transfer_by_history(result, BRepTools_History, sources, root_policy, conflict)` and `transfer_by_modifier(...)` for transforms/copies. Root policies: `merge`, `self/source/first`, `role:<name>`, `none`. Conflict: `first`/`last`. Returns a `ProvenanceReport`. | Understand the current semantics (below). |
| `pythonocc_backend/_brepgraph.py` | OCCT 8 BRepGraph used as a **cached incidence index** keyed on raw `BRepGraph_NodeId`: subshapes, super-shapes, adjacency, shared shapes, edge incidence. | Fast topological queries. Not durable identity. |
| `pythonocc_backend/_csg_lineage.py` | Context-var capture of exact BRepTools/BRepGraph source→result relations during CSG evaluation. | How ShapeGrammar/CSG lineage is recorded. |
| `pythonocc_backend/attribute_manager.py` | The dictionary store (singleton `AttributeManager`). | Metadata storage only. |

### What the current provenance does — precisely

From `transfer_by_history` (lines ~618–776):

- Relations actually distinguished: **modified**, **generated**, **unchanged** (by exact native identity
  when history is silent), and **deleted** (`IsRemoved`, counted, no target).
- **GENERATED inherits the source dictionary exactly like MODIFIED.** The relation string is stored in
  the contribution group but ignored when the dictionary is written. This is the "accidental geometric
  match" Wassim wants to turn into a policy.
- **MERGED is implicit**: a target reached from several sources gets `merge_dictionaries(..., conflict=
  "first"|"last")`. There is no MERGED relation and no semantic conflict rule.
- **COPIED** is handled separately through `transfer_by_modifier` (transform `ModifiedShape` mapping).
- Transfer is **same-kind only** (face→face, cell→cell). Cross-dimensional semantics are deferred to
  "explicit selector/key APIs".
- **History is consumed and discarded** after dictionaries are written, except when CSG/ShapeGrammar
  lineage capture is active. BRepGraph is used as a result-membership index via `NodeId`; **no UID, no
  `AddWithHistory`, no `LayerHistory`** yet.

These are the exact places our work plugs in.

---

## 3. What already exists (port, do not copy blindly)

Prototype files (in the project outputs):

| File | Contents | Port as |
|---|---|---|
| `narkomfin_element_dictionary.py` | 33 element types, canonical local frames, ports, parameters | `topogrammar/elements/` as **data** (JSON schema) + builders returning Topologic Cells |
| `narkomfin_grammar.py` | Shape grammar A (block, A0–A8) and B (condenser, B0–B6), `section(levels, corridor_level)` | `ShapeGrammar` rule packs |
| `narkomfin_graph_grammar.py` | Graph grammar GA/GB with edge access semantics, contraction rules, interpreter, variants, VF2 comparison | `topogrammar/graph/` on `TGraph` |
| `build_narkomfin.py` | 1,776-element as-built model | realisation layer (§4, step 5) |
| `narkomfin_to_topologic.py` | Blender → Topologic Cells with dictionaries | `interop/blender.py` (visualisation only) |

### Invariants the prototype established — these become acceptance tests

As-built Narkomfin, **access subgraph** (only occupiable nodes; only edges with `access != none`):

| metric | value |
|---|---|
| nodes / edges | **115 / 121** |
| components | **1** |
| max degree | **7** |
| node types | bridge 1, corridor 40, dwelling 53, gallery 1, ground 1, hall 1, interface 1, stairwell 17 |
| edges by access | open 35, door 69, stair 17 |
| shape-derived vs graph-derived | **isomorphic, type-preserving (igraph VF2)** |

Variant reachability (every dwelling reachable from GROUND over access-bearing edges):
V1 as-built 53/53 · V2 all-U 9 levels 49/49 · V3 Γ 37/37 · V4 skip-stop Z 45/45 · V5 10 bays 24/24.

### Lessons the prototype paid for

- `Graph.IsIsomorphic` returned **false negatives** on 115-node graphs. Use igraph VF2 (plain and
  colour-preserving by node `type`). Never use it for identity or de-duplication.
- Per-step Topologic graph analysis was the bottleneck (`ConnectedComponents` ~5.6 s/call; a 9-level
  derivation 77 s). Compute light metrics on the Python-side graph; call heavy analyses on final states.
- `SelfMerge` of 299 cells took 152 s. Never inside a search loop.
- Stratified rules + a terminal discipline ("no `bay` node survives a complete derivation") prune more
  cheaply than any heuristic.
- The facade split is an **identity production** on the graph. Envelope is style; the graph can't see it.
- L, U, Γ, Z and flat sections are **one production** with parameters `(levels, corridor_level)`.

---

## 4. Architecture

```
topogrammar/
  elements/      element dictionary as data (JSON schema) + Cell builders + ports
  axiom/         Axiom = ⟨seed S, rule pack R, params P, constraints C, objectives O⟩; hashing; satisfiability
  shape/         rule packs on topologicpy.ShapeGrammar; derivation driver
  provenance/    event ledger, six-relation classifier, dictionary policy engine, identity provider
  graph/         TGraph state, graph rules, provenance→graph rewrite, constructive oracle
  realise/       space cells + faces  →  thick elements (slabs, walls, columns, panes) from the element dictionary
  search/        parameter sweep, staged rule search, canonical de-dup, validity gates
  registry/      canonical IDs (topology/typology/geometry/derivation), derivation hash chain
  interop/       Blender export, JSON, IFC (later)
examples/narkomfin/   the two rule packs + axiom + golden tests
tests/
docs/
```

### The modelling decision that everything else follows from

**The grammar rewrites space cells with shared faces (Topologic's non-manifold idiom), not thick
element solids.** Walls, slabs and panes are realised afterwards from the element dictionary by
thickening the shared faces. Reasons:

1. It is how Topologic is meant to be used, and CellComplex adjacency is exact and cheap to query.
2. Provenance then carries the architecture: when R_BAY splits a storey cell, the storey cell is
   **MODIFIED** into two bay cells and the cut face is **GENERATED** — and *that generated face is the
   party wall*. Its dictionary should come from the rule (`Symbol = DV.WALL.PARTY`, `access = none`),
   not be copied from the storey. This is exactly the GENERATED-as-policy case.
3. The graph grammar then follows provenance directly (§5, axis D).

The prototype's thick-solid element model becomes the output of `realise/`, and the 1,776-element count
becomes a regression figure for that layer, not for the grammar.

---

## 5. Provenance: differential options, and what to build

Five independent axes. For each: the options, then the **v1 default** to implement behind an interface so
the others can be swapped in without touching the grammars.

### Axis A — where durable identity lives

| Option | Mechanism | Survives | Weakness |
|---|---|---|---|
| A1 NodeId index (TopologicPy today) | `BRepGraph_NodeId`, rebuilt per result | one operation | not durable; OCCT advises against it for identity |
| A2 BRepGraph UID / RefUID / ItemUID | native durable ids, stored as a reserved dictionary key | a session, across operations | must be persisted explicitly to survive BREP/JSON round trips |
| A3 Semantic ID | grammar-assigned path, e.g. `RB/L3/b07/SP.CELL.F`, derived from rule + match site | everything, incl. serialisation and the registry | must be maintained by rules; needs a native anchor |

**v1:** A3 as the primary ID, with the A2 UID captured alongside when available (A1 fallback). Keep a
per-session `semantic_id ↔ native_uid` table in `provenance/identity.py`. The registry only ever sees A3.

### Axis B — where history is recorded

| Option | Mechanism | Answers | Weakness |
|---|---|---|---|
| B1 Consume-and-discard (today) | `BRepTools_History` → dictionaries → dropped | "what dictionary does this face have?" | cannot answer "what became of this face?" two steps later |
| B2 BRepGraph `LayerHistory` via `AddWithHistory` | persistent history layer in the graph across a chain of operations | Modified / Generated / Deleted / Replaced, both directions, multiple origins | binding names unverified (M0); session-scoped |
| B3 External provenance ledger | every rule application appends `(rule_id, match_site, relation, source_ids, target_ids, params)` | full derivation, serialisable, hashable | duplicates B2 unless fed from it |

**v1:** B3 fed from `ShapeGrammar.History()/LineageGraph()` (which already sit on `BRepTools_History`).
Add a B2 adapter behind a feature flag once M0 confirms the bindings, and make it the ledger's source.
The ledger's hash chain **is** the registry's derivation ID.

### Axis C — dictionary policy per relation

Wassim's six relations, and what each means for a grammar:

| Relation | Default dictionary behaviour | Grammar example (Narkomfin) |
|---|---|---|
| UNCHANGED | keep, always (independent of `transferDictionary`) | facade split: every space cell is untouched |
| COPIED | follow at every dimension | mirrored K pair (MIRROR-X) |
| MODIFIED | each descendant inherits | R_BAY: storey cell → two bay cells inherit `level`, `block` |
| GENERATED | **policy, not inheritance** | R_BAY: the new cut face = party wall; gets its dictionary from the rule |
| MERGED | **explicit conflict rule** | R_LCELL/R_UCELL, R_MERGE: stacked cells → one dwelling / one hall |
| DELETED | none | R_CORE removes corridor segments at the core bays |

Policy options:

| Option | Where the policy lives | Fit |
|---|---|---|
| C1 Global defaults per relation | one table | too coarse: `level` should survive a merge, `bay` should not |
| C2 **Per-key schema** | each dictionary key declares its rule per relation (`inherit`, `recompute`, `from_rule`, `drop`, `merge:<fn>`) | right for element semantics (`IfcClass`, `Symbol`, `area`, `id`) |
| C3 **Per-rule morphism** | the rule's RHS declares how LHS attributes map (attributed graph rewriting) | right for grammar-specific intent |

MERGED conflict strategies to support: `first`, `last`, `role:<name>` (all exist today), plus
`union` (list of values), `sum` / `max` / `min` (areas, fire ratings), `rule` (RHS decides), and `flag`
(write both, set `_conflict=True` for human review).

**v1:** C2 + C3, applied as a **post-pass over ledger events**, not by patching TopologicPy internals.
Order: rule morphism (C3) overrides key schema (C2) overrides relation default (C1). Write the proposed
upstream hook (a policy callable passed to `transfer_by_history`) as `docs/upstream_proposal.md` for
Wassim rather than forking.

Note the **same-kind restriction** in `_provenance.py`: a face GENERATED by splitting a *cell* is
cross-dimensional and is not transferred automatically. That is precisely the party-wall case, so the
rule-assigned (C3) path is required, not optional.

### Axis D — how the graph grammar consumes provenance

| Option | Mechanism | Speed | Correspondence |
|---|---|---|---|
| D1 Post hoc | `SelfMerge` + `Graph.ByTopology` | slow | recovered, identity lost |
| D2 Constructive (prototype) | each graph rule states its effect by hand | fast | must be proven by comparison |
| D3 **Provenance-driven** | ledger events rewrite the `TGraph` automatically | fast | **by construction** |

D3 event → graph rewrite mapping:

| Event on space cells | Graph rewrite |
|---|---|
| cell MODIFIED into *k* cells | node split into *k*; incident edges re-attached by shared-face lookup |
| face GENERATED between two cells | new edge; `rel` and `access` from the face's policy dictionary (party wall → `access=none`; door face → `door`) |
| *k* cells MERGED | vertex contraction; internal edges dissolve; conflict policy on node dictionaries |
| cell DELETED | node removal |
| UNCHANGED | nothing — which is why the facade split is an identity production on the graph |

**v1:** D3, with the prototype's constructive graph rules (D2) kept as a **test oracle**: every
derivation asserts that the provenance-driven access graph is VF2-isomorphic (type-preserving) to the
constructive one. This is the "dual lockstep" as a test, not a runtime cost.

### Axis E — registry linkage

| Option | What is hashed | Answers |
|---|---|---|
| E1 Final state | canonical access graph (igraph canonical permutation + normalised types) | "has this topology been registered?" |
| E2 Derivation | ledger hash chain over (rule id, match semantic ids, relation sets, state hash) | "was this derived from that axiom?" |
| E3 Axiom + coverage | axiom hash, rule-pack hash, enumerated-space Merkle root | "what is the extent of this claim?" |

**v1:** compute and store E1 and E2 for every derivation, E3 for every completed sweep. No chain
integration yet; write IDs to JSON. Use **semantic IDs only** in hashes (native UIDs are session-scoped).

---

## 6. Milestones and acceptance criteria

| # | Deliverable | Done when |
|---|---|---|
| M0 | Environment + probe | `docs/occt8_probe.md` lists exact binding names; ShapeGrammar smoke test passes on the OCC backend |
| M1 | Element dictionary as data | 33 types load from JSON; every builder returns a single valid `Cell`; ports and parameters in dictionaries |
| M2 | Shape rule packs A and B on `ShapeGrammar` | as-built derivation completes; `History()` non-empty for every application; R_BAY yields bay cells + generated cut faces |
| M3 | Provenance ledger + policy engine | six relations classified on the Narkomfin derivation; party-wall faces carry `Symbol=DV.WALL.PARTY` from the rule; MERGED conflicts reported; ledger serialises and hashes deterministically |
| M4 | Graph grammar on `TGraph`, provenance-driven | access subgraph = **115 / 121 / 1 component / max degree 7**, type histogram and access histogram as §3; VF2 type-preserving isomorphic to the constructive oracle |
| M5 | Axiom, variants, search | Axiom object hashes deterministically incl. rule-pack version; satisfiability check fails fast on an over-constrained axiom; V1–V5 reachability as §3; canonical de-dup removes isomorphic duplicates |
| M6 | Realisation + interop | thick elements realised from faces; Blender export for review; JSON reports of every derivation |

### Performance budgets

- graph rewrite step < 50 ms; full as-built graph derivation < 1 s
- no `SelfMerge` or `Graph.ByTopology` inside a search loop
- ledger overhead < 10 % of rule application time

---

## 7. Rules of engagement

- **Rules are data.** Rule packs load from YAML/JSON (title, operation, LHS/RHS references, parameters,
  dictionary morphism, stage). Python only for procedural RHS the DSL can't express yet.
- **Genus-0 solids** in the element layer: openings are notches from an edge, never holes.
- **No geometric nearest-match heuristics** for provenance. If history is silent and identity doesn't
  resolve, record the gap.
- Don't depend on raw `NodeId` for anything that outlives one operation.
- Keep the public API backend-neutral, as `ShapeGrammar` does: no OCCT objects in signatures.
- Tests first for M3 and M4: they encode the research claim.
- When a comparison fails, fix the rule that is architecturally wrong, never the test.

---

## 8. Questions to take to Wassim (collect answers in `docs/wassim_questions.md`)

1. Exact pythonocc-core 8 names for `UID`/`RefUID`/`ItemUID`, `ShapesView::AddWithHistory`, and
   `BRepGraph_LayerHistory` queries — and whether UIDs survive `ShapeGrammar.Data(includeBREP=True)`.
2. Should GENERATED stop inheriting by default in `transfer_by_history`, with inheritance moved to a
   policy? (Today it inherits exactly like MODIFIED.)
3. Is a policy callable on `transfer_by_history` (per key, per relation) acceptable upstream, or should
   policy stay downstream of `AttributeManager`?
4. Cross-dimensional transfer: the face generated by splitting a cell is the architecturally important
   entity. Is there a planned selector/key API for it, or should rules own it?
5. Will `ShapeGrammar.History()` expose the relation per source/target pair publicly, including MERGED
   (multi-origin) targets? That would let the ledger drop its own bookkeeping.
