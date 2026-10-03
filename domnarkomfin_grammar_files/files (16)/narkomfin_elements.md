# Dom Narkomfin - element dictionary

The alphabet of terminals for the shape + graph grammar. Each element sits in its own canonical local frame in `DomNarkomfin_ElementDictionary.blend`, tagged with its parameters and its ports.

Constants: bay 3.66 m, block depth 9.9 m, storey 2.8 m (pilotis 2.5 m), slab 0.3, exterior/party wall 0.3, corridor wall 0.2, partition 0.1, pane 0.05, spandrel 1.0.

## Structure

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `SL.BAY` | Bay floor slab | IfcSlab | length 3.66, depth 9.9, thickness 0.3 | top, soffit, edge_W, edge_E, edge_S, edge_N | 110 | the unit of horizontal subdivision; SPLIT-X of a slab band generates the bay rhythm |
| `SL.STRIP` | Partial slab strip (corridor / hall band) | IfcSlab | length 3.66, depth 3.38, thickness 0.3 | top, edge_N | 16 | produced by SUBTRACT of a void volume from SL.BAY; the rule that makes the F duplex |
| `SL.BALC` | Balcony slab strip | IfcSlab | length 3.66, depth 2.3, thickness 0.3 | top, edge_N, parapet_seat | 21 | OFFSET-Y of SL.BAY beyond the facade line; carries EN.PARAPET |
| `SL.BALC.SEMI` | Semicircular balcony | IfcSlab | radius 2.4, thickness 0.3 | top, wall_face | 4 | a curved terminal: rotational rule applied to the end wall, not derivable by orthogonal splits |
| `SL.GALL` | Gallery slab with curved edge | IfcSlab | length 10.65, depth 7.52, thickness 0.3, bite elliptical, 0.97 deep | top, curved_edge | 1 | SUBTRACT of a curved void from a full slab; the only non-orthogonal horizontal element |
| `SL.ROOF` | Roof slab (bay) | IfcRoof | length 3.66, depth 9.9, thickness 0.3 | top | 25 | terminal: the last slab of a vertical repetition stops the STACK-Z rule |
| `CO.PIL` | Pilotis (round column) | IfcColumn | diameter 0.5, height 2.2, profile circular | base, head | 69 | the free-standing terminal that lets the ground plane stay open; marks the pilotis storey |
| `CO.RECT` | Column (rectangular, in the party wall) | IfcColumn | width 0.3, depth 0.4, height 2.5, profile rectangular | base, head, wall_W, wall_E | 352 | the column absorbed into the division; walls are SPLIT by it (hence the _s0/_s1 pieces) |
| `CO.RND.INT` | Interior round column | IfcColumn | diameter 0.5, height 2.5, profile circular | base, head | 6 | free column inside a space: does not divide it, so the graph keeps one node |

## Envelope

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `EN.SPAND` | Spandrel band | IfcWall | length 3.66, thickness 0.3, height 1.0 | base, head, out, in | ≈180 pieces | lower half of the SPLIT-Z of a facade panel; pairs with EN.WIN.RIBBON |
| `EN.WIN.RIBBON` | Ribbon window (single pane) | IfcWindow | length 3.66, thickness 0.05, height 1.5, glazing single pane, full bay | base, head, out | ≈200 panes | upper half of the facade SPLIT-Z; the rule keeps it CONTINUOUS across bays, which is the signature of the style - a bay-wise pane would be the wrong grammar |
| `EN.WIN.CURT` | Curtain wall (storey-high pane) | IfcWindow | length 10.56, thickness 0.05, height 2.5 | base, out | 5 | degenerate case of the facade SPLIT-Z with spandrel = 0; the 'social condenser' reading |
| `EN.WIN.CURVED` | Curved glazing | IfcWindow | radius 3.16, thickness 0.05, height 2.2, sweep 180 | base, chord | 3 | rotational terminal; the LHS is an orthogonal room corner, the RHS its curved replacement |
| `EN.WALL.END` | Blank end wall (gable) | IfcWall | length 9.9, thickness 0.3, height 2.5 | base, out, corner_S, corner_N | 12 | the boundary terminal: stops the repetition along x; may carry a door to SL.BALC.SEMI |
| `EN.PARAPET` | Parapet | IfcWall | length 3.66, thickness 0.2, height 0.6 | base | ≈40 pieces | attaches to a slab edge port; the guard rule for any accessible horizontal surface |
| `EN.PARAPET.CURVED` | Curved parapet | IfcWall | radius 2.4, thickness 0.15, height 1.1, sweep 180 | base | 4 | the same guard rule following a curved edge - shows the rule is edge-driven, not axis-driven |

## Division

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `DV.WALL.PARTY` | Party wall | IfcWall | length 9.9, thickness 0.3, height 2.5 | base, head, face_W, face_E | ≈150 pieces | the DIVIDE-X operator made material: one party wall = one new node pair in the graph |
| `DV.WALL.CORE` | Core wall (with door) | IfcWall | length 9.9, thickness 0.3, height 2.5, opening 0.9 x 2.1 | base, door | ≈40 pieces | same as DV.WALL.PARTY but with a door notch: the wall that a graph EDGE passes through |
| `DV.WALL.CORR` | Corridor wall (with entrance door) | IfcWall | length 3.66, thickness 0.2, height 2.5, opening 0.9 x 2.1 | base, door, face_corr, face_unit | ≈40 pieces | the SPLIT-Y that produces the corridor; one door per dwelling = one edge corridor->unit |
| `DV.WALL.PART` | Partition | IfcWall | length 3.0, thickness 0.1, height 2.5 | base, start, end | ≈90 pieces | the light, non-structural DIVIDE inside a cell - free of the column grid, so it is the level where unit variants are generated |
| `DV.WALL.WC` | WC partition (paired doors) | IfcWall | length 2.0, thickness 0.1, height 2.5, openings 2 x 0.7 x 2.1 | base, door_1, door_2 | 16 | a repeated micro-rule: the same partition serves two cells - a shared-service motif |

## Circulation

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `CI.FLIGHT` | Stair flight (half storey) | IfcStair | width 1.5, run 2.3, rise 1.4, thickness 0.25 | foot, head | ≈60 | the vertical CONNECT operator; its two ports are what make a graph edge between levels |
| `CI.LANDING` | Stair landing | IfcStair | length 3.06, depth 1.22, thickness 0.3 | top, arrive, depart | ≈30 | the turn: two CI.FLIGHT plus one CI.LANDING = the dogleg composite |
| `CI.STAIR.K` | K-unit stair (one storey, straight) | IfcStair | width 1.2, run 2.59, rise 2.8, thickness 0.25 | foot, head | 8 | the element that turns two stacked cells into ONE dwelling node: the K duplex rule |
| `CI.STAIR.F` | F-unit stair (one storey, straight) | IfcStair | width 1.05, run 2.5, rise 2.8, thickness 0.25 | foot, head | 32 | applied twice per dwelling: the split-level F duplex that spans the corridor level |

## Opening

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `OP.DOOR` | Door (single pane) | IfcDoor | width 0.9, height 2.1, thickness 0.05 | hinge, axis | ≈95 | the OPENING terminal: it does not divide, it CONNECTS - every door is a graph edge |
| `OP.DOOR.WC` | WC door (single pane) | IfcDoor | width 0.7, height 2.1, thickness 0.05 | hinge, axis | ≈40 | narrow variant; the width is the only parameter that distinguishes service from habitable |

## Space

| symbol | element | IfcClass | parameters | ports | occurrences | role in the grammar |
|---|---|---|---|---|---|---|
| `SP.CELL.K` | K dwelling volume (2 bays, 2 levels) | IfcSpace | length 7.32, depth 9.9, height 5.3, type K: compact kitchen, no dining | entrance, facade_S, facade_N | 8 | the 2-bay x 2-level cell; MIRROR-X of this cell is the rule that makes the pair |
| `SP.CELL.F` | F dwelling volume (1 bay, 3 levels) | IfcSpace | length 3.66, depth 9.9, height 8.099999999999998, type F: duplex, no kitchen (communal dining) | entrance, facade_S, facade_N | 16 | the 1-bay x 3-level cell entered from its MIDDLE level: the section that lets one corridor serve three floors - the key move of the whole building |
| `SP.CORRIDOR` | Corridor segment | IfcSpace | length 3.66, depth 1.29, height 2.5 | west, east, unit | 2 streets | the linear connector: a chain of segments whose end nodes attach to SP.STAIRWELL |
| `SP.STAIRWELL` | Stair core volume | IfcSpace | length 3.66, depth 5.01, height 2.5 | corridor, down, up | 2 cores x 7 levels | the only terminal with vertical ports: STACK-Z of stairwells is what makes the graph 3D |
| `SP.HALL` | Condenser hall (double height) | IfcSpace | length 10.05, depth 9.96, height 5.3, programme gymnasium / dining / library | core, entrance, gallery | 2 | the social condenser: a single node of HIGH degree - the graph-level definition of 'collective' |
| `SP.BRIDGE` | Bridge / passage volume | IfcSpace | length 2.34, depth 11.9, height 2.5 | block, condenser | 1 | the bridging edge: removing this one terminal disconnects the graph into two components |
