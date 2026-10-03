# Variants: from a sequence of procedures to a grammar

Branch `variants`. Status: options for discussion, nothing implemented yet. Date: 2026-10-03.

Theo's two questions:

1. The P1 rules have no left-hand side → right-hand side form and are applied in a strict sequence.
   Could they be applied in another order, as verbs?
2. How do we build the mechanisms that generate variants?

This note diagnoses what P1 is, sets out what the shape-grammar and graph-transformation literature
offers, and lays out the options along four independent axes: how a rule is written, how application
is controlled, where variation comes from, and how the space is searched. A recommendation follows,
with a plan for this branch.

## 1. Diagnosis: P1 is a parametric template, not yet a grammar

In P1 a production is a Python procedure with a hand-written `sites()` function. That reproduces the
prototype exactly, which is what P1 was for, but it has five consequences:

| | What P1 does | Why it matters |
|---|---|---|
| a | The left-hand side is implicit: `sites()` is code that knows where the rule applies | Nothing can be matched that the author did not foresee; no emergence; no second rule with the same LHS |
| b | The right-hand side is a procedure | Cannot be drawn, compared, hashed or transformed |
| c | Rules write the consequences of other rules | `GA6 R_CORE` creates the lobby doors that `GA5`'s dwellings need; `GA5` deletes the corridor doors that `GA4` made. This is what forces the order |
| d | Sites are computed from the parameters `P`, not matched in the state | `ends = 3` is a number in `P` instead of a pattern ("a band beyond the last core"); that is the V5 fault (finding 12) |
| e | Stages are a fixed program | Inside a stage the order is free but the result is the same; across stages the order is fixed |

The derivation tree can branch, but every branch converges on the same final state. So the language
of the P1 grammar is exactly the set of parameter vectors: one design per `P`. Variation by hand
cannot happen *inside* a derivation. That is the deficit to repair.

Note that stages themselves are not the problem. The Palladian grammar (Stiny & Mitchell 1978), the
Prairie houses (Koning & Eizenberg 1981) and the Queen Anne houses (Flemming 1987) are all written as
sequences of stages. The difference is that in those grammars the choices *inside* a stage produce
different designs. Ours do not.

## 2. What the literature gives us

The classic sources are not on arXiv; they are cited from the literature. The three arXiv papers
read for this note are marked.

**Shape grammars as such.** Stiny & Gips (1972) and Stiny (1980) define a grammar as ⟨S, L, R, I⟩:
shapes, labels, rules α → β and an initial shape. A rule applies wherever a transformation takes α
onto a subshape of the current shape; labels (markers) carry state and control which rules may fire;
*parametric* grammars (Stiny 1980) make α and β schemata with variables, so one rule stands for a
family. Emergence (Stiny 1994, 2006; Knight 2003) is the point of matching on shapes rather than on
the symbols the designer put there: a rule can see a shape nobody drew.

**Control.** Three mechanisms recur: *stages* (the architectural grammars above), *labels/markers*
(Stiny), and *priorities* (CGA shape, below). The graph-transformation literature adds a fourth that
is the honest baseline: no control at all, with the order left free, and *confluence* analysed
afterwards to find exactly the pairs of rules whose order matters.

**Transformations of grammars.** Knight (1983, 1994) shows that a new style is reached by adding,
deleting or changing rules of an existing grammar, and that the changes can be systematic. For us:
Narkomfin → the Stroykom types → the Unité d'Habitation is a chain of grammar transformations, not a
parameter sweep.

**Variants by search.** Duarte's Malagueira grammar (2001, 2005) pairs a shape grammar with a
*description* grammar and heuristics, so that a brief (areas, rooms, budget) drives the choice of rule
at each step; this is the closest precedent for the brief's axiom with constraints and objectives.
Talton et al. (2011) search the space of derivations of a procedural grammar by MCMC against a
likelihood; Ruiz-Montiel et al. (2013) do it by reinforcement learning over shape-grammar states.

**Grammars as verbs.** Split grammars (Wonka et al. 2003) and CGA shape (Müller et al. 2006) write a
rule as a *symbol* and a sequence of *operations* with parameters: `Lot → extrude(h) Mass`,
`Mass → split(x){ 3.66: Bay }*`. The symbol is the LHS, the verbs are the RHS; rules carry priorities;
context sensitivity comes from queries on the current model. This is the form Theo is asking for, and
the Narkomfin rules fall into it almost word for word: lift, stack, bay, street, cell, core are all
split, repeat, comp and attach with parameters. FaçAID (arXiv 2406.01829) uses a split grammar as the
target language of a facade-reconstruction model, which shows the form also serves as an output format.

**Grammars on graphs.** GRAPE (Grasl & Economou 2013) implements parametric shape grammars by
representing shapes as graphs and matching the LHS by subgraph isomorphism; the Durand grammar for
Shape Machine (Agarwal, arXiv 2404.14448, read) organises its rules into stages (lay out, mark rooms,
build rooms, detail) and gets its variants by *swapping rule sets* behind a fixed interface, which is
Knight's transformation in software-engineering clothes. Heisserman (1994) and Hoisl & Shea (2011)
show rules on 3D solids; TopologicPy's `ShapeGrammar` already is one: a rule is (input topology,
output topology, operation), matched by `IsSimilar`.

**Graph transformation theory.** The double-pushout approach (Ehrig et al. 2006) gives a rule as
L ← K → R: what is matched, what is kept, what results. Negative and nested application conditions
(Habel & Pennemann 2009; arXiv 2408.06196, 2608.12096) let a rule say "and there is no door here
already". Critical-pair analysis (Plump 1993; tools AGG, Henshin; arXiv 2003.11010 on computing rule
overlaps) decides whether two rules commute, which is the formal version of "can these be applied in
another order". "Effect-oriented" transformation (arXiv 2305.03432) designs rules from the state they
must reach rather than the edit they make, which is close to how an architect thinks about a move.

**Induction.** SIGI (Hermans, Winters & De Raedt, arXiv 2109.10217, read) infers shapes and a shape
grammar from 3D grid examples by local search over segmentations and shares rules between matching
shapes; its own conclusion is that local rules alone miss global structure. Talton et al. (2012) learn
Bayesian grammars from examples. Both are later options for us: we have an as-built model of 1,776
elements to learn from.

## 3. Verbs: can the rules be applied in another order?

Yes, once the hidden consequences in (c) and the parameters in (d) become rules of their own. Here is
the as-built grammar rewritten as local productions. Each has an explicit LHS (a small typed pattern
with attribute constraints), application conditions (NAC = "no such thing present"), and an RHS. The
verb column is the CGA-style reading of the same rule.

| # | Verb | LHS | NAC | RHS | Was |
|---|---|---|---|---|---|
| 1 | lift | mass (block) | | ground, mass; supports | GA1 |
| 2 | stack(n) | mass | | storey × n, chained above | GA2 |
| 3 | bay(n) | storey | | bay × n, chained party | GA3 |
| 4 | *stack-adjacent* | bay(l, i), bay(l+1, i) | no above edge | above edge | hidden in GA3 |
| 5 | street | bay(l, i) | no corridor at (l, i) | corridor, band, door | GA4 |
| 6 | *street-link* | corridor(l, i), corridor(l, i+1) | no edge | corridor edge | hidden in GA4 |
| 7 | cell(k, ci) | run of k bands in one bay, the band at index ci has a door to a corridor | no other door in the run | dwelling(kind by k, ci), door kept | GA5 |
| 8 | end-unit | band(l, i), no corridor at (l, i), party-adjacent to a stairwell or an end unit | | dwelling (flat) | GA5 + `ends` |
| 9 | core | stack of bays at line i | | stairwells, stair chain | GA6 |
| 10 | *lobby-street* | stairwell(l, i), corridor(l, i±1) | no edge | core_door | hidden in GA6 |
| 11 | *lobby-dwelling* | stairwell(l, i), dwelling entered on l at bay i±1 | no edge | core_door | hidden in GA6 |
| 12 | *lobby-end* | stairwell(l, i), end unit(l, i±1 or i±2) | no edge | core_door | hidden in GA6 |
| 13 | *street-stop* | end unit with a corridor door | | door removed | hidden in GA5 |
| 14 | roof | bay | no bay above | roof | GA8 |
| 15 | penthouse | stairwell | nothing above | penthouse, stair | GA8 |
| 16 | facade | (identity) | | | GA7 |
| 17 | merge | storey(B, l) above storey(B, l+1) | | hall | GB2 |
| 18 | gallery | hall | no gallery | gallery, open edge | GB3 |
| 19 | core-B | hall | no core | stairwells, core_door to hall and gallery | GB5 |
| 20 | bridge | stairwell(B, 1), corridor(A, 1, first bay) | no bridge | bridge, two bridge edges, door | GB6 |

Three things follow.

**Most of the order disappears.** Rules 4, 6, 10, 11, 12 are glue: they fire whenever their pattern
exists, in any order, and reach the same state. (They are also exactly what provenance gives for free
on the shape side: a shared face between two cells *is* the adjacency edge. The brief's axis D3 makes
them unnecessary there.) Rules 1–3, 5, 7, 9, 14, 15 are ordered only by what they need: you cannot
make a dwelling before there are bands. That order is semantic and comes out of the LHS, not out of a
stage number.

**The order that remains is design.** Two pairs do not commute:

- *core before street* vs *street before core*. As built, the cores consume their bays first and the
  street stops at them; a street cut first runs through the core line, and the core then interrupts
  it. The P1 reconciliation chose "interrupted, with a door each side". Both are buildings.
- *cell before street* is impossible (rule 7 needs the door), but *cell(k) at one bay before cell(k′)
  at the next* is free, and *which k at which bay* is a choice: a block that mixes L and U cells along
  its length is a different building from Narkomfin, which mixes them by level.

In graph-transformation terms these are the critical pairs. In architectural terms they are the
decisions. The engine should find them (critical-pair analysis on the rule set) and the viewer should
offer them as such.

**The parameters thin out.** `ends` disappears into rule 8; `core_lines` becomes a choice of where to
apply rule 9; `cells` becomes which `cell(k, ci)` to apply at which bay; `corridor_levels` becomes
where to apply rule 5. What is left in `P` is dimensions and counts (`bays`, `levels`), which is what a
parametric grammar should hold. This also removes finding 12 (V5) and makes finding 9 (the fused
cells) impossible to write.

## 4. Axis R: how a rule is written

| Option | Rule is | Matching | Pro | Con |
|---|---|---|---|---|
| R1 procedure (P1) | Python `sites` + `apply` | hand-coded | exact parity with the prototype | everything in §1 |
| R2 declarative graph rule | LHS pattern, NACs, RHS, attribute morphism, as data | subgraph isomorphism on `TGraph` (igraph VF2 with node colours; patterns have 1–4 nodes, so it is fast) | drawable, hashable, transformable (Knight), analysable (critical pairs), emergent matches | glue rules must be written out; needs a small pattern language |
| R3 shape rule | `ShapeGrammar.AddRule(input, output, operation)` | `Topology.IsSimilar` | already in TopologicPy; provenance for free; the shape side is primary, as the brief intends | matching is geometric, so a storey cell matches a storey cell but a "run of three bands with one door" is not a shape; graph conditions must come from the graph side |
| R4 verb | `symbol → verb(args) verb(args) …` (CGA) | by symbol, plus queries | the form Theo asked for; readable; compiles to R2 or R3 | by itself it is a labelled rewriting, not a pattern grammar: no emergence, no NACs unless added |

These are not exclusive. The recommendation is R2 as the core representation on the graph side, R4
as the authoring syntax that compiles to R2 for the regular productions (lift, stack, bay, street,
cell, core, roof), and R3 as the shape counterpart of each, so that one rule in the pack has three
faces: a verb line for the author, a graph pattern for the engine, a shape rule for TopologicPy.

A rule in that form, as data:

```yaml
id: cell
verb: contract(k, ci) -> dwelling
lhs:
  nodes: {b0: {type: band}, b1: {type: band}, c: {type: corridor}}      # k = 2 shown
  edges: [[b0, b1, above], [c, b_ci, door]]
  where: {same_bay: [b0, b1], same_level: [c, b_ci]}
nac:
  - edges: [[c2, b_any, door]]            # no second street through the run
rhs:
  nodes: {d: {type: dwelling, kind: "section(k, ci)", symbol: SP.CELL.*}}
  keep: [c]                               # the interface K of the double pushout
  edges: [[c, d, door]]
morphism:
  level: {from: b0}                       # dictionary policy, brief axis C3
  bay: {from: b0}
  levels: k
  corridor_index: ci
shape:
  operation: Merge
  tool: section_prism(k, ci)
```

## 5. Axis C: how application is controlled

| Option | Mechanism | Where it comes from | Fit for us |
|---|---|---|---|
| C1 stages | rule sets in a fixed sequence | Palladian, Prairie, P1 | keeps the discipline of the brief ("stratified rules + terminal discipline"); should be a *strategy*, not the grammar |
| C2 labels / markers | rules fire only on labelled nodes and relabel | Stiny | we have it already: `type` is the label; non-terminals are the markers |
| C3 priorities | highest-priority applicable rule fires | CGA shape | good for automatic derivation; bad for a hand-driven one |
| C4 free choice | any applicable rule at any match | graph transformation | the honest baseline for the viewer: show every match, let the architect choose; needs confluence analysis to show which choices matter |
| C5 parallel | every match of a rule at once | L-systems; our "apply at all sites" | keep as a convenience |
| C6 search | an objective chooses | Duarte, Talton, Ruiz-Montiel | this is M5 |

Recommendation: C4 as the default in the viewer with C2 as the mechanism, C1 and C5 as optional
strategies ("derive in stages", "apply everywhere"), C6 as the search layer. Order is then a property
of a *derivation*, not of the grammar, and two derivations with different orders that reach different
designs are two variants.

## 6. Axis V: where variation comes from

| Option | Variation by | Needs | Yields for Narkomfin | Status |
|---|---|---|---|---|
| V1 parameters | values in `P` | satisfiability check | the section family L / U / Γ / Z; bays, levels, streets | have (P1) |
| V2 rule choice | several rules share an LHS; the derivation picks | R2 matching, C4 | which `cell(k, ci)` at which bay: blocks that mix sections along their length; where the cores go | needs R2 |
| V3 order | non-commuting pairs | critical-pair analysis | core/street interruption; what the ground floor becomes | needs R2 |
| V4 grammar transformation (Knight) | add / remove / change rules | rules as data (R2/R4), pack versioning | remove `street` + add `gallery-access` → external-gallery type; `cell(2, 0)` interlocked around a central street → the Unité section; change `merge` → different condenser programmes | needs R2 |
| V5 emergence | rules match what earlier rules made but did not name | R2 on the *graph*, R3 on the *shape* | the mirrored K pair as a 2-bay unit (`R_PAIR`, decision 1); a double-height hall found in any two stacked rooms | needs R2/R3 |
| V6 search | objectives and constraints pick rule and site | C6, metrics, canonical de-dup | dwellings per metre of street, reachability, cut vertices, degree of the condenser node, area | M5 |
| V7 induction | rules learned from the as-built model | element model, SIGI-like segmentation | an independent check of the hand-written grammar | later |

V1 and V2 together give the catalogue; V3 and V4 give the *types*; V5 is what makes the pair rule
honest; V6 is how the space is explored rather than enumerated. V7 is research for later.

The grammar as it stands has about 10⁴ parameter vectors. With V2 (say three section kinds per bay
over 16 bays and two core positions) it has 10⁸ or more, which is why V6 and canonical de-duplication
(brief axis E1: igraph canonical permutation of the typed access graph) are needed before V2 is
exposed in a viewer that can enumerate.

## 7. What each gives on the Narkomfin case

- **The Stroykom catalogue.** Ginzburg's Stroykom types A–F are one grammar with different `cell(k,
  ci)` choices and street placements: V1 + V2.
- **Narkomfin → Unité.** Le Corbusier's Unité section is `cell(2, 0)` and `cell(2, 1)` interlocked
  around a street every third level; the grammar transformation is: streets on every third level,
  two cell rules instead of two cell groups, bays become a different rhythm: V4, with V1 for the
  dimensions. This is the clearest demonstration that the rules are a language and not a drawing of
  one building.
- **The condenser as a graph property.** `merge` applied to different storeys, or twice, gives
  halls of different degree; V6 can be asked for "a node whose degree is out of proportion", which is
  the brief's definition of a social condenser.
- **Access types.** Removing `street` and adding a gallery rule along the south face gives the
  external-gallery dom-kommuna; removing it and adding `lobby` doors only gives the point-access block:
  V4, and each is checked by the same reachability and lockstep tests.

## 8. Recommendation

1. **Adopt R2 as the engine's rule form**, on `GraphState`/`TGraph`, with matching by igraph VF2
   subisomorphism on typed patterns, NACs, and the interface K of the double pushout so that
   contraction, split and attach are one mechanism. Keep the attribute morphism (brief axis C3) in the
   rule.
2. **Author rules as verbs (R4)** that compile to R2, and give each a shape face (R3) when P2 brings
   `ShapeGrammar` in. One pack entry, three faces.
3. **Make control a strategy (C4 default, C1/C5 optional)**, and compute the critical pairs of the
   pack so that the viewer can say "this choice changes the design; that one does not".
4. **Build variation in this order:** V2 and V3 (they fall out of R2), then V4 as pack versioning
   with Knight-style diffs, then V5 (`R_PAIR`), then V6 (M5). V7 stays research.
5. **Keep P1 as the oracle.** The as-built figures (115 / 121 / 1 / 7 / 49) and the step-by-step
   parity must hold for the derivation that follows the as-built order; every other derivation is a
   variant and is judged by the gates (reachability, terminal discipline, lockstep).

## 9. Plan for this branch, and its status (2026-10-03)

| Step | Work | Status |
|---|---|---|
| 1 | Pattern matcher: typed subgraph with attribute predicates and NACs on `GraphState` | **done**: `topogrammar/graph/patterns.py`; a 4-node pattern matches the as-built graph in about 1 ms |
| 2 | Rule schema (YAML) and the effect-oriented apply: delete, contract, create, relabel, link, unlink | **done**: `topogrammar/graph/rules.py`, `pack.py`, `derivation.py` |
| 3 | The Narkomfin pack rewritten as 28 local rules (19 choices, 9 consequences), with the as-built as a recorded pathway | **done**: `examples/narkomfin/graph/`; the as-built pathway reproduces the recorded access graph edge for edge, 115 / 121 / 1 / 7 / 49, in 1.3 s; `ends`, `core_lines`, `cells`, `corridor_levels` are gone from the parameters |
| 4 | Independence of offers: which choices decide against others | **done** as parallel independence (a site conflicts with another when it changes a node the other reads); exposed per site and per group. A static critical-pair analysis over the rule set, independent of the state, is not done |
| 5 | Pathways: recorded, replayed, hashed (axis E2) and the pack hashed with its lineage (axis E3) | **done**; enumeration with canonical de-duplication (V6) is not |
| 6 | Viewer: every match offered, drawn LHS → RHS cards, decisions marked, pathway panel, pack transformation panel, the Unité derivable | **done** except authoring: cards are drawn from the data, not yet drawn *into* it |

The Unité pack (`examples/unite/graph/`) extends Narkomfin by changing one rule (`street`), adding two
(`cell_up`, `cell_down`) and removing twelve (the Narkomfin cell and end unit, and the whole condenser
grammar); its recorded pathway gives 81 dwellings, all reachable, with every bay resolved.

Two things the port taught:

- **A pair holds one relation.** When a bay becomes a stairwell its plain `above` adjacency becomes a
  `stair`, and the blind `party` wall beside a lobby becomes a `core_door`. `link` therefore relabels an
  existing edge rather than refusing. This is what the brief's MERGED and MODIFIED relations will look
  like on the graph side.
- **Consequences are not choices.** Nine of the 28 rules (adjacency, street links, stair chains, lobby
  doors, the mirror mark) fire wherever they match and are kept out of the palette. They are exactly the
  rules that provenance supplies for free on the shape side (a shared face is an edge), so from P4 they
  can be replaced by the ledger without touching the choices.

### Plan as first written

| Step | Work | Done when |
|---|---|---|
| 1 | Pattern matcher: typed subgraph with attribute predicates and NACs on `GraphState`, via igraph | a 4-node pattern matches the as-built graph in under 5 ms |
| 2 | Rule schema (YAML as in §4) and the DPO apply: delete L∖K, add R∖K, morphism | the 20 rules of §3 load and run |
| 3 | Rewrite the Narkomfin pack in that form; retire `ends`, `core_lines`, `cells`, `corridor_levels` from `P` into rule choices with the as-built as a recorded *strategy* | the as-built strategy reproduces 115 / 121 and the step counts; the free strategy reaches the same state in any order of the commuting rules |
| 4 | Critical-pair report for the pack | the core/street pair and the cell-kind choice are listed; the glue rules are not |
| 5 | Variant enumeration with gates and canonical de-dup (E1) | V2 over cell kinds gives a de-duplicated catalogue with its figures |
| 6 | Viewer: verb palette with every match offered (C4), rule cards drawn as LHS → RHS graphs, "choices that matter" marked, pack diff view for V4, variant gallery | the Unité derivation can be made by hand from the Narkomfin pack |

Steps 1–4 are the same work that P2–P4 need (the shape face of each rule and the provenance-driven
graph plug into the same rule objects), so this is not a detour from the plan; it replaces the
P1 procedures with the form P2 would have needed anyway.

## 10. Decisions (Theo, 2026-10-03)

1. **Free choice, every match offered** (C4). Stages become an optional strategy.
2. **Rules are authored as drawn LHS → RHS cards**; the text form is generated from them.
3. **First transformation: Narkomfin → Unité d'Habitation.**
4. **Controls and variations are structured as pathways the architect governs**: a pathway is the
   recorded sequence of choices; the engine shows where a choice changes the design and where it does
   not; pathways are named, replayed, compared and hashed.
5. **Rule changes are versioned and hashed.** The link with the history of transformations Wassim is
   building inside Topologic is to be discussed with him.

## 11. Questions that led to the decisions

1. Is C4 (every match offered, order free, decisions marked) the way you want to drive it, with stages
   kept as an optional strategy? Or should the viewer keep stages as the default and open order only
   inside them?
2. For the verb syntax: CGA-style text (`storey → bay(3.66)*`), or should rules be authored as drawn
   LHS → RHS cards in the viewer (Shape Machine style) with the text generated from them?
3. Which transformation to demonstrate first for V4: Narkomfin → Unité, or the Stroykom types?
4. V6 objectives: which figures should the search be able to ask for in the first version?
   Candidates: dwellings per metre of street, floors per street, reachability, cut vertices, the
   condenser node's degree, floor area per dwelling.
5. Should rule changes (V4) be versioned as pack diffs that the registry hashes (brief axis E3), so
   that "derived from Narkomfin" is itself a recorded claim?

## References

Classic (not on arXiv): Stiny & Gips 1972; Stiny 1980 *Introduction to shape and shape grammars*;
Stiny & Mitchell 1978 (Palladian); Koning & Eizenberg 1981 (Prairie); Knight 1983 *Transformations of
languages of designs*, 1994; Flemming 1987 (Queen Anne); Heisserman 1994 (boundary solid grammars);
Stiny 1994, 2006, Knight 2003 (emergence); Duarte 2001, 2005 (Malagueira, discursive grammar);
Wonka et al. 2003 (split grammars); Müller et al. 2006 (CGA shape); Talton et al. 2011 (Metropolis
procedural modeling), 2012 (Bayesian grammar induction); Hoisl & Shea 2011; Grasl & Economou 2013
(GRAPE); Ruiz-Montiel et al. 2013; Ehrig et al. 2006 (algebraic graph transformation); Habel &
Pennemann 2009 (nested conditions); Plump 1993 (critical pairs).

Read for this note (arXiv): 2404.14448 Agarwal, *Object-Oriented Architecture: a shape grammar for
Durand's plates* (Shape Machine; stages and rule-set swapping); 2109.10217 Hermans, Winters & De
Raedt, *Shape inference and grammar induction* (SIGI). Located, not read in full: 2406.01829 FaçAID
(split grammar as output language); 2408.06196 and 2608.12096 (nested conditions); 2003.11010 (rule
overlaps / composition); 2305.03432 (effect-oriented graph transformation).
