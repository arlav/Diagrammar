# Dom Narkomfin — the graph grammar (TopologicPy)

The mirror of `narkomfin_grammar.py`. Two grammars of **graph productions**, each rewriting a labelled
graph whose semantics live in dictionaries embedded on the vertices *and* the edges. Every state is
materialised as a real TopologicPy `Graph`, so it can be measured, exported and compared.

| | GA — **BLOCK** | GB — **SOCIAL CONDENSER** |
|---|---|---|
| productions | GA0 axiom, GA1 R_LIFT, GA2 R_STACK, GA3 R_BAY, GA4 R_CORRIDOR, GA5 R_LCELL/R_UCELL, GA6 R_CORE, GA7 R_FACADE (identity), GA8 R_ROOF | GB0 axiom + interface, GB1 R_STACK, GB2 R_MERGE, GB3 R_GALLERY, GB4 R_FACADE (identity), GB5 R_CORE, GB6 R_BRIDGE |
| final state | 126 nodes / 228 edges | composed: **137 nodes / 240 edges, 1 component** |

## Dictionary schema

**Vertex**: `id, label, type, block, level, bay, tag, kind, levels, corridor_index, symbol`
where `type ∈ {mass, ground, storey, bay, corridor, dwelling, stairwell, hall, gallery, bridge, roof, interface}`
and `symbol` points back into the element dictionary (`SP.CELL.F`, `SP.CORRIDOR`, `SP.STAIRWELL`…).

**Edge**: `rel ∈ {supports, above, party, door, corridor, stair, core_door, open, bridge}` plus
`access ∈ {none, open, door, stair}`.

That second key is the one that matters. A `party` edge is adjacency with access **none**. After GA3
the graph has 236 edges and *every one* is access-none — 236 adjacencies and no circulation at all.
Access appears only with GA4 (44 door, 42 open) and vertical access only with GA6 (12 stair); the
composed final state is 111 none / 77 door / 35 open / 17 stair. A graph grammar that records only
"adjacent" will cheerfully generate plans that are connected and unbuildable.

## The productions that carry the argument

**GA5 R_LCELL / R_UCELL** is a vertex **contraction**: the run of band nodes in one bay becomes one
dwelling node, the door edge to the pierced level survives and the internal `above` edges dissolve
(they are now inside a dwelling). Node count drops 177 → 129. It is the only production that reduces
the graph, and `corridor_index` is what decides L (2 levels, street at the bottom) or U (3 levels,
street through the middle).

**GB2 R_MERGE** is the *same* contraction with a different programme — a stack of storeys into a
collective volume rather than into a dwelling. The result is a node whose degree is out of proportion
to the rest of the graph, which is the graph-theoretic definition of a social condenser.

**GA7 / GB4 R_FACADE are explicit identity productions.** The facade split changes no node and no
edge. Keeping them in the rule list is the honest record that shape and graph grammars are not in
bijection: the envelope is style, and the graph cannot see it.

**GB6 R_BRIDGE** is the only production that touches the interface node `IFACE`, which stands for the
block's L1 corridor. Before it the design is 3 components; after it, 1. `Graph.CutVertices` names
`BRIDGE`, `IFACE`, `CBS1–3`, `HALL` and the top core nodes without being told to look.

## Validation

Each variant is tested for reachability over **access-bearing edges only**, from `GROUND`:

| variant | parameters | dwellings | reachable | valid | floors/street | interpreted |
|---|---|---|---|---|---|---|
| V1 as built | 22 bays, 6 levels, streets at L1+L4, K=L / F=U | 53 | 53 | ✓ | 3.0 | 92 cells, 8,744 m³ |
| V2 all-U | 9 levels, 3 streets, all 3-level U cells | 49 | 49 | ✓ | 3.0 | 102 cells, 6,720 m³ |
| V3 Γ | access *over* the dwelling | 37 | 37 | ✓ | 3.0 | 76 cells, 4,675 m³ |
| V4 skip-stop Z | 8 levels, 4-level cells, 2 streets | 45 | 45 | ✓ | 4.0 | 80 cells, 7,824 m³ |
| V5 short block | 10 bays, cores at 2 and 8 | 24 | 24 | ✓ | 3.0 | 44 cells, 3,396 m³ + CellComplex round trip |

## Graph → shape interpreter

`interpret(state)` reads the node dictionaries (`bay`, `levels`, `corridor_index`, `type`) and builds
Topologic `Cell`s face by face — the graph genuinely drives the geometry. With `cellcomplex=True` it
then runs `Topology.SelfMerge` and reads the adjacency back with `Graph.ByTopology`, closing the loop
shape → graph → shape. That round trip is run on V5 only: `SelfMerge` is minutes at full length.

## Reconciled with the shape grammar

The two divergences are closed. A5 now has an **end-unit case** (the degenerate section: one level, no
corridor notch, so L / U / flat are one production with one parameter), and A6 **carries the street
through the core** — a door on each side, so the chain reads corridor → stairwell → corridor instead of
breaking in two. Two smaller alignments followed: the core serves each adjacent dwelling once, on the
level it is entered from; and the street stops at the cores, so end units are entered from the stair
lobby rather than inheriting a corridor door.

The access graphs of the two derivations are now **identical**:

| | shape grammar | graph grammar |
|---|---|---|
| nodes | 115 | 115 |
| edges | 121 | 121 |
| components | 1 | 1 |
| max degree | 7 | 7 |
| cut vertices | 49 | 49 |
| node types | bridge 1, corridor 40, dwelling 53, gallery 1, ground 1, hall 1, interface 1, stairwell 17 | identical |
| edges by access | open 35, door 69, stair 17 | identical |
| degree sequence | equal | equal |
| **isomorphic (VF2)** | **True** — and **True** type-preserving | |

*Tool caveat:* `Graph.IsIsomorphic` in TopologicPy is an iterative refinement and returns `False` on
these graphs even though they are isomorphic. The verdict above is igraph's VF2, run plain and with
vertices coloured by node type; the report records both results.

This agreement is what makes the pair usable as a generator: derive on one side, realise on the other,
and compare access graphs as the correctness test.

## Performance note (for the method section)

Per-step TopologicPy graph analysis was the bottleneck: `ConnectedComponents` alone ran ~5.6 s per
call, making one nine-level derivation 77 s. Light metrics (degree, components, access histogram) now
run in Python during rewriting; TopologicPy is used for the final states, export, cut vertices,
degree centrality and isomorphism. `python-igraph` must be installed for `Graph.CutVertices`.

## Files

* `narkomfin_graph_grammar.py` — the grammars, the interpreter, the variant generator, the comparison.
  `python narkomfin_graph_grammar.py --json <dir> [--compare] [--blend <file>]`
  (`--compare` imports the shape grammar, and therefore `bpy`; everything else is pure TopologicPy.)
* `graphs/graph_<name>.json` — TopologicPy `Graph.ExportToJSON` per state and per variant
* `graphs/graph_<name>_dicts.json` — the same graphs as plain node/edge dictionaries plus metrics
* `graphs/graph_grammar_report.json` — every production with its description and its graph metrics,
  the variant table, the comparison, and the edge access semantics
* `DomNarkomfin_GraphGrammar.blend` — the graphs drawn in 3D: nodes coloured by type, edges as tubes,
  **thick/warm = access-bearing, thin/grey = adjacency only**, one object per relation so relations can
  be toggled; plus the interpreted cells of the as-built state
* `preview_graph_*.png`

## Next step

Both sides are now parametric over the same numbers (`levels`, `corridor_levels`, `cells`,
`core_lines`, `bays`). The obvious move is to search that space from the graph side — propose an
access graph (floors per street, dwellings per core, one or two condensers), test it for reachability
and degree, and only then let the section rule and the shape grammar realise it. The two divergences
above should be closed first, so that agreement between the two derivations can be used as the
correctness test for generated variants.
