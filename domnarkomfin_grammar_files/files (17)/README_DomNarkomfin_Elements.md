# Dom Narkomfin – element model for Topologic grammars

`DomNarkomfin_Elements.blend` (Blender 4.3) is the "real" counterpart of the abstract cell model in
`3d_Topologic_Model_Dom_Narkomfin__Full_Grammar_development.blend`. It sits on **exactly the same
coordinate frame**, so every abstract cell can be matched to the slabs, columns, walls, windows, doors
and stairs that realise it.

| | |
|---|---|
| Residential block (RB) | x 13.28 → 93.80 (22 bays × 3.66 m, column lines `XL[0..22]`), y 7.52 → 17.42 (9.90 m) |
| Column rows | y = 8.72 (S), 12.41 (C), 16.20 (N) – measured from the *història en obres* plans |
| Levels (top of slab) | L0 0.00 pilotis · L1 2.50 K-lower + corridor 1 + balcony · L2 5.30 K-upper · L3 8.10 F-lower · L4 10.90 F corridor · L5 13.70 F-upper · L6 16.50 roof/penthouse · L7 21.00 |
| Condenser (CB) | x 6.07 → 16.72, y −16.04 → −5.48; stair core y −5.48 → −2.08; levels 0 / 2.5 / 5.3 / 8.4 (gallery) / 10.9 (roof), core to 13.5 |
| Bridge (BR) | x 13.28 → 15.62, y −2.08 → 9.82, L1 |
| Units | 8 K-type (2 bays, L1–L2, bays 3–18, mirrored pairs), 16 F-type (1 bay, L3–L5, bays 3–18), end units bays 0–1 / 20–21, stair cores bays 2 / 19 |

Element thicknesses: slabs 0.30, exterior/party/core walls 0.30, corridor walls 0.20, partitions 0.10,
glass and door panes 0.05, columns Ø0.50 (pilotis, round) and 0.30 × 0.40 (upper floors, flush with the party walls).
Ribbon windows = 1.0 m spandrel + single glass pane up to the slab soffit. Doors 0.90 × 2.10 (WC 0.70).

## Counts (1,776 elements + 58 abstract spaces)

IfcSlab 143 · IfcColumn 421 · IfcWall 752 · IfcWindow 232 · IfcDoor 111 · IfcStair 92 · IfcRoof 25 · ground plane 1.
All meshes are closed, genus-0 solids with no mutual overlaps (walls are split at columns; door and
stair openings are notches from an edge, never holes). Every one converts to a TopologicPy `Cell`.

## Naming

`<Class>_<Block>_L<level>_<descriptor>[_s<n>]`

* Class: `Slab`, `Roof`, `Balcony`, `Parapet`, `Column`, `Wall`, `Window`, `Door`, `Stair`, `Space`
* Block: `RB` residential, `CB` condenser, `BR` bridge, `PH` penthouse, `SITE`
* descriptor: bay `b07`, column line + row `N07`, party wall line `Party_x38.90`, unit `F07` / `K03` / `EndW` / `CoreE`,
  face `N` `S` `W` `E`, role words (`Corridor`, `Hall`, `WC`, `Bath`, `Kitchen`, `Landing`, `Curved`), stair span `L3-L4`
* `_s0, _s1 …` = pieces of one wall split by the columns it runs through

Examples: `Column_RB_L0_C11` (pilotis, centre row, line 11) · `Wall_RB_L4_Corridor_b09` ·
`Window_RB_L3_N_F07` · `Door_RB_L1_K03` · `Stair_RB_CoreW_L2-L3_A` · `Slab_CB_L3_Gallery` · `Window_CB_L0_E_Glazing`.

## Custom properties (on every object, exported to Topologic dictionaries)

`IfcClass`, `Block`, `Level` (int), `LevelName`, `Bay` (int, −1 if n/a), `Unit`, `Role`, `Material`
(+ `Line`, `Row`, `Profile` on columns / party walls).

Collections: `DomNarkomfin` → `Site`, `RB_ResidentialBlock` → `RB_L0_Pilotis … RB_L7_PenthouseRoof`,
`CB_Condenser` → `CB_L0_Ground … CB_Roof`, `BR_Bridge`, `Spaces_AbstractGrammar` (hidden; the 58 cells of the
grammar model that sit on the main frame, renamed `Space_<original name>`, tagged `IfcSpace`).

## Files

* `DomNarkomfin_Elements.blend` – the model
* `build_narkomfin.py` – parametric generator; all dimensions are constants at the top
  (`blender --background --python build_narkomfin.py -- --out X.blend --spaces-from <grammar.blend>`,
  or run in Blender's text editor; also works with the pip `bpy` module)
* `narkomfin_to_topologic.py` – Blender → TopologicPy: `Cell` per object with dictionary, `Cluster`,
  optional `SelfMerge` (CellComplex / Cluster of CellComplexes) and `Graph.ByTopology`
  (`--filter "Block=RB,Level=3" --graph`). Whole-level merges take minutes (L3: 299 cells → 152 s, 3 CellComplexes,
  358 cells after coincident faces are fused); the whole building should be merged block by block or level by level.
* `DomNarkomfin_Elements.obj/.mtl` – one named `o` group per element, metres, Z up (for `Topology.ByOBJFile`)
* `DomNarkomfin_Elements_schedule.csv` – every object with its properties and bounding box
* `preview_*.png` – Workbench renders (aerial, plan cuts, cut-aways)

## Simplifications you may want to revisit

* Storeys are the abstract model's flat 2.80 m (2.50 m pilotis). The real F cells are split-level
  (2.3 m / 3.5 m rooms); the elevation suggests ≈2.55 m storeys. Change `LEVELS` in the script.
* L4 slab is only the corridor + entrance-hall strip in the F bays (the living rooms read as double height);
  set the L4 branch of the slab loop to `rect(...)` for a flat slab.
* Stairs are straight solid flights (dogleg with mid landing in the cores; single steep flights in units).
* Condenser: one ribbon per storey on the solid faces, fully glazed east face; the real punched windows are not modelled.
* Slabs are per bay (`Slab_RB_L3_b07`); merge with Topologic `Union` if one slab per level is preferred.
