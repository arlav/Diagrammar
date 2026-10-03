# Dom Narkomfin — element dictionary (the grammar's alphabet)

33 element types in 6 categories, one canonical instance of each, in
`DomNarkomfin_ElementDictionary.blend`. This is the vocabulary of terminals the shape rules will
rewrite; `DomNarkomfin_Elements.blend` (the completed building) is the same vocabulary instantiated
1,776 times.

## Categories and symbols

**Structure (9)** `SL.BAY` bay floor slab · `SL.STRIP` partial slab strip · `SL.BALC` balcony strip ·
`SL.BALC.SEMI` semicircular balcony · `SL.GALL` gallery slab with curved edge · `SL.ROOF` roof slab ·
`CO.PIL` round pilotis · `CO.RECT` rectangular column in the party wall · `CO.RND.INT` interior round column

**Envelope (7)** `EN.SPAND` spandrel band · `EN.WIN.RIBBON` ribbon window pane · `EN.WIN.CURT` storey-high
curtain pane · `EN.WIN.CURVED` curved glazing · `EN.WALL.END` blank gable · `EN.PARAPET` ·
`EN.PARAPET.CURVED`

**Division (5)** `DV.WALL.PARTY` blind party wall · `DV.WALL.CORE` core wall with door · `DV.WALL.CORR`
corridor wall with entrance door · `DV.WALL.PART` partition · `DV.WALL.WC` WC partition with paired doors

**Circulation (4)** `CI.FLIGHT` half-storey flight · `CI.LANDING` · `CI.STAIR.K` K-unit stair ·
`CI.STAIR.F` F-unit stair

**Opening (2)** `OP.DOOR` · `OP.DOOR.WC`

**Space (6)** `SP.CELL.K` · `SP.CELL.F` · `SP.CORRIDOR` · `SP.STAIRWELL` · `SP.HALL` · `SP.BRIDGE`
(the graph-side terminals: the volumes the solids bound)

## Canonical local frames

Each element sits at its own origin so LHS/RHS matching and `Topology.IsSimilar` need no repositioning:

| kind | frame |
|---|---|
| slabs, plates, landings | x 0..length, y 0..depth, z −t..0 — **z = 0 is the finished floor** |
| walls | x = the run (0..length), y = the thickness (−t/2..t/2), z 0..h |
| columns | centred on x = y = 0, z 0..h |
| panes (glass, door leaves) | x 0..width, y ±t/2, z 0..h |
| spaces | x 0..length, y 0..depth, z 0..h |

Curved elements (`SL.BALC.SEMI`, `EN.WIN.CURVED`, `EN.PARAPET.CURVED`) are centred on their arc centre,
sweeping 90°→270°, so a rule can rotate them about the origin.

## Ports

Every element carries labelled attachment points as parented empties, `Port_<SYMBOL>_<name>`, each with a
`Direction` custom property (the outward normal; arrow empties show it). These are the grammar's handles —
`top`/`soffit`/`edge_N`… on slabs, `base`/`head`/`face_W`/`face_E` on walls, `base`/`head` on columns,
`door` on walls that carry an opening, `foot`/`head` on flights, `up`/`down`/`corridor` on the stairwell
volume. Rules attach RHS elements by matching a port, not by absolute coordinates.

## Properties on every object

`Symbol`, `ElementName`, `Category`, `IfcClass`, `Material`, `Occurrences` (how many are in the building),
`Where`, `GrammarRole` (what operation produces or consumes it), `Ports`, plus every parameter as
`p_<name>` (`p_length`, `p_thickness`, `p_height`, `p_radius`…). `narkomfin_to_topologic.py` carries all of
these into the Topologic `Dictionary`, so element identity survives into the graph.

## Constants

bay 3.66 m · block depth 9.90 m · storey 2.80 m (pilotis 2.50 m) · slab 0.30 · exterior/party/core wall 0.30 ·
corridor wall 0.20 · partition 0.10 · pane 0.05 · spandrel 1.00 · door 0.90 × 2.10 (WC 0.70) ·
column 0.30 × 0.40 · pilotis Ø0.50.

## Files

* `DomNarkomfin_ElementDictionary.blend` — the catalogue, one collection per category
* `narkomfin_element_dictionary.py` — generator; `dictionary()` returns the whole thing as Python data, so
  rules can be written against it directly (`from narkomfin_element_dictionary import dictionary`)
* `narkomfin_elements.json` — machine-readable: symbol, params, ports (position + direction), occurrences,
  grammar role, catalogue location
* `narkomfin_elements.md` — the same as tables
* `preview_dictionary_*.png` — the catalogue and each category row

All 33 meshes are closed, genus-0 solids and all 33 convert to Topologic `Cell`s with their dictionaries
(checked with TopologicPy 0.9.70 / topologic_core 8.0.4 via `object_to_cell` in `narkomfin_to_topologic.py`).

## Notes for the rule set

* `EN.WIN.RIBBON` is deliberately a bay-length pane that the rules keep **continuous** across bays; a
  per-bay window would encode the wrong style.
* `CO.RECT` sits inside `DV.WALL.PARTY`, which is why walls in the building model appear as `_s0/_s1`
  pieces — the column splits them. A rule that adds a column must therefore re-split the wall.
* `SP.CELL.F` is entered from its **middle** level: the corridor-serves-three-floors move. This is the one
  relation the grammar has to get right for the building to be Narkomfin rather than any ribbon-window slab.
* `SP.BRIDGE` is the articulation point of the graph — removing it splits the building into two components.
