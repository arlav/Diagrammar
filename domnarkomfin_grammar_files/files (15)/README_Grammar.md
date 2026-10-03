# Dom Narkomfin — the grammar, in two parts

Two grammars over the one element dictionary, composed by a single production.

| | grammar A — **BLOCK** | grammar B — **SOCIAL CONDENSER** |
|---|---|---|
| operates by | subdividing a repetitive frame (SPLIT) | merging levels into a collective volume (UNION) |
| axiom | one prism, 80.5 × 9.9 × 19.3 m | one prism, 10.65 × 9.96 × 11.2 m |
| productions | A0–A8 | B0–B6 |
| final state | 851 cells, graph 118 nodes / 136 edges | 27 cells, graph 11 nodes / 11 edges |

They are kept separate because their rules run in opposite directions, and because they should be
varied independently. Grammar B knows nothing about grammar A except one **interface node**
(`IFACE.BLOCK_L1_CORRIDOR`); `B6 R_BRIDGE` is the only production that touches it, and in the graph
`SP.BRIDGE` is a cut vertex — delete it and the design falls into two components.

## The rules you asked to foreground

**A3 R_BAY — the bay / party-wall pair.** SPLIT-X of a storey band on the 3.66 m rhythm. It is a
*pair* because neither half means anything alone: each cut yields two bay slabs **and** the party wall
on the cut line, with `CO.RECT` absorbed into that wall (which is why walls arrive as `_s0/_s1`
pieces — a rule that adds a column must re-split the wall). In the graph: one node becomes two,
joined by a **blind** edge — adjacent but not connected. That distinction is the whole reason to keep
the graph alongside the shapes.

**A7 R_FACADE — the facade split.** SPLIT-Z of each envelope panel at h = 1.00 m into `EN.SPAND`
below and `EN.WIN.RIBBON` above, the pane running end to end. Two things matter: the pane is *not*
subdivided by the bay rule, so the facade is deliberately out of step with the structure (a per-bay
window would generate a different architecture from the same plan); and h is a parameter — at h = 0
the same rule yields the condenser's `EN.WIN.CURT`, so **ribbon and curtain wall are one rule**.
The graph is unchanged by this rule: envelope is style, not topology.

**A4 R_CORRIDOR.** SPLIT-Y at 1.80 m into the common corridor and the dwelling band, with
`DV.WALL.CORR` on the cut. The corridor nodes form an open chain — the internal street — and each
dwelling gets exactly one entrance-door edge to it.

**A5 R_LCELL / R_UCELL — the L and U volumes around the corridor.** One rule, one parameter:

```
section(levels, corridor_level)   =   bay rectangle  −  corridor notch
```

* `levels = 2`, corridor at the **bottom** → **L** — the K type. The upper level runs the full 9.90 m
  depth *over* the corridor; one street serves two floors.
* `levels = 3`, corridor through the **middle** → **U** — the F type. Full-depth levels below *and*
  above the street, joined by a 1.58 m hall band beside it; **one street serves three floors.** This is
  the move that makes the building Narkomfin rather than any ribbon-window slab.

In the graph the stacked bay nodes **collapse into one dwelling node**. The section rule is therefore
visible as a change in node count, which is exactly what a graph grammar can be made to drive.

## Section family (the variant engine)

| id | levels | corridor level | section | |
|---|---|---|---|---|
| V1 | 2 | 0 | **L** | as built (K) |
| V2 | 3 | 1 | **U** | as built (F) |
| V3 | 2 | 1 | **Γ** | unbuilt: access *over* the dwelling |
| V4 | 4 | 1 | **Z** | unbuilt: skip-stop, one street per four floors |

The same four parameters (`levels`, `corridor_level`, `corridor_depth`, `hall_band`) plus the facade
split height and the bay count generate the family. Later, driving these from the graph side means:
propose a graph (how many floors per street, how many dwellings per core), then let the section rule
realise it.

## Files

* `DomNarkomfin_Grammar.blend` — `Rules/` (six LHS→RHS cards), `Derivation_A_Block/Step_00…08`,
  `Derivation_B_Condenser/Step_00…06`, `Variants_SectionFamily/`. Every step is a complete snapshot with
  its graph drawn above it (nodes as cubes, edges as a line mesh).
* `narkomfin_grammar.py` — the rule set. Each rule is a function `rule(state) -> note` that rewrites
  cells *and* graph; `GRAMMAR_A` / `GRAMMAR_B` are ordered lists, so a derivation is
  `run_derivation(name, GRAMMAR_A, collection)`. `section(levels, corridor_level)` is the L/U generator.
* `narkomfin_grammar.json` — steps with cell/node/edge counts and the description of each production,
  rule cards, variants, parameters.
* `narkomfin_grammar.md` — the same as prose.
* `preview_rule_*.png`, `preview_derivation_A.png`, `preview_derivation_B.png`,
  `preview_step_*.png`, `preview_variants_section_family.png`.

## Reconciliation with the graph grammar

A5 now also covers the **end units** (levels = 1, no corridor notch → the flat section: L, U and flat are
one production), and A6 **carries the street through the core** with a door on each side, so the corridor
chain is continuous. With those in place the shape grammar's access graph and the graph grammar's are
isomorphic, type-preserving: 115 nodes, 121 edges, one component, max degree 7, 49 cut vertices.

## Where the graph and shape sides meet

Per-rule graph behaviour, which is what a graph-grammar counterpart would have to reproduce:

| rule | shape operation | graph operation |
|---|---|---|
| A1 R_LIFT | SPLIT-Z | node → 2 nodes, `supports` |
| A2 R_STACK | repeated SPLIT-Z | vertical chain of `above` |
| A3 R_BAY | SPLIT-X + wall/column pair | node → *n*, chained by **blind** edges |
| A4 R_CORRIDOR | SPLIT-Y + door wall | node → 2; corridor chain + one door edge each |
| A5 R_LCELL/R_UCELL | merge stack − notch | *k* nodes → 1, one door edge to the street |
| A6 R_CORE | relabel + flights | the only **vertical** access edges |
| A7 R_FACADE | SPLIT-Z (parametric h) | **no change** |
| B2 R_MERGE | UNION of two storeys | 2 nodes → 1 of high degree (= social condenser) |
| B3 R_GALLERY | SUBTRACT curved void | node adjacent by an **open** edge |
| B6 R_BRIDGE | ATTACH | joins two components through a **cut vertex** |

The asymmetries in that table are the interesting part: A7 changes the shape and not the graph, B2
changes the graph more than the shape, and A5 is the only rule that *reduces* the node count. A mirror
graph grammar therefore cannot be a one-to-one map of the shape rules — it will need rules at the
level of A3/A4/A5 and B2/B6 only.
