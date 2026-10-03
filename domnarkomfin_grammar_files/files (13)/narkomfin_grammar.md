# Dom Narkomfin — the grammar, in two parts


## Grammar A: BLOCK

### A0 AXIOM

*1 cells · graph 1 nodes / 0 edges*

A0 AXIOM: a single prism, 80.5 x 9.9 x 19.3 m, labelled BLOCK

### A1 R_LIFT

*71 cells · graph 2 nodes / 1 edges*

A1 R_LIFT: SPLIT-Z at 2.50 m. The lower part is emptied to a colonnade of CO.PIL (3 rows x 23 lines) and the upper part relabelled MASS: the ground plane is given away, which is the first political act of the building. Graph: one node becomes two, joined by a 'supports' edge.

### A2 R_STACK

*83 cells · graph 7 nodes / 6 edges*

A2 R_STACK: repeated SPLIT-Z of MASS into 6 storey bands of 2.80 m, each a slab band + a storey volume, closed by SL.ROOF. Graph: a vertical chain of 'above' edges - stacking is the only rule so far that makes the graph three-dimensional, and R_LCELL/R_UCELL will later exploit it.

### A3 R_BAY (bay / party-wall pair)

*749 cells · graph 133 nodes / 126 edges*

A3 R_BAY (the bay / party-wall pair): SPLIT-X of a storey band on a 3.66 m rhythm. The rule is a PAIR because neither half is meaningful alone: each cut produces a bay slab AND the party wall on the cut line, and the column CO.RECT is absorbed into that wall, splitting it into pieces. Graph: 22 bay nodes per level, chained by blind 'party wall' edges - adjacency without access, which is exactly what a party wall means.

### A4 R_CORRIDOR

*837 cells · graph 133 nodes / 126 edges*

A4 R_CORRIDOR: SPLIT-Y of levels L1, L4 into a 1.80 m common corridor on the south and the dwelling band on the north, with DV.WALL.CORR (door notch per bay) on the cut. Graph: the corridor nodes form an open chain - the 'internal street'. This is the level at which the whole social programme is decided.

### A5 R_LCELL / R_UCELL

*789 cells · graph 125 nodes / 165 edges*

A5 R_LCELL / R_UCELL (one rule, one parameter): a run of stacked bays is merged into a single dwelling whose SECTION is the bay rectangle minus the corridor notch. K: 2 levels, corridor at index 0 -> section L; F: 3 levels, corridor at index 1 -> section U; E: 1 level, no corridor notch -> flat (the end units beyond the cores). The K cell is an L: two levels, corridor at the bottom, so the upper level runs the full 9.90 m depth over the corridor. The F cell is a U: three levels, corridor through the MIDDLE, so the dwelling has a full-depth level below AND above the street and only a narrow hall band beside it. One corridor therefore serves three floors. Graph: the stacked bay nodes COLLAPSE into one dwelling node with a single 'entrance door' edge to the corridor - the section rule is visible in the graph as a change of node count, which is what we want to drive variants from. The END UNITS are the degenerate case of the same production - levels = 1, no notch - which is the cheapest possible proof that L, U and flat are one rule and not three.

### A6 R_CORE

*809 cells · graph 125 nodes / 197 edges*

A6 R_CORE: two bays (lines 2 and 19) are relabelled as vertical cores - CI.FLIGHT pairs + SP.STAIRWELL. Graph: the only nodes carrying VERTICAL edges. Until this rule the graph is a set of horizontal chains; after it the graph is genuinely three-dimensional. The core also CARRIES THE STREET: because it interrupts the corridor, it takes a door on each side, so the chain runs corridor - stairwell - corridor rather than breaking into two dangling halves. The end units and the dwellings beside the core are entered from the same lobby.

### A7 R_FACADE (facade split)

*833 cells · graph 125 nodes / 197 edges*

A7 R_FACADE (facade split): every envelope panel is SPLIT-Z at 1.00 m into EN.SPAND below and EN.WIN.RIBBON above, the pane running from end to end of the block. Two things matter grammatically: (i) the split height is a parameter - at spandrel = 0 the same rule yields the condenser's EN.WIN.CURT, so ribbon and curtain wall are ONE rule, not two; (ii) the pane is NOT subdivided by the bay rule, so the facade is deliberately out of step with the structure. A per-bay window would generate a different architecture with the same plan. The graph is unchanged: the facade split adds no nodes, only exterior faces - envelope is style, not topology.

### A8 R_END + R_ROOF

*851 cells · graph 126 nodes / 198 edges*

A8 R_END + R_ROOF: EN.WALL.END terminates the repetition along x (a blind gable - the rule that says 'stop'), with SL.BALC.SEMI attached to its outer face on L2-L5, and the stack is closed by parapet and penthouse. Graph: one terminal node on top of a core.


## Grammar B: SOCIAL CONDENSER

### B0 AXIOM

*1 cells · graph 2 nodes / 0 edges*

B0 AXIOM: a second, separate prism - the social condenser. It is a SEPARATE GRAMMAR because its rules are different in kind: the block subdivides a repetitive frame, the condenser merges levels into a single collective volume. Same operations, opposite direction.

### B1 R_STACK

*9 cells · graph 5 nodes / 3 edges*

B1 R_STACK: the same SPLIT-Z as A2, 4 storeys.

### B2 R_MERGE (condenser)

*7 cells · graph 4 nodes / 2 edges*

B2 R_MERGE (the social condenser rule): delete an intermediate slab and UNION the two storeys into one double-height volume - gymnasium / dining / library. Graph: two nodes collapse into one of HIGH degree. That is the graph-theoretic definition of a 'social condenser': not a room type but a node whose degree is out of proportion to the rest of the graph.

### B3 R_GALLERY

*8 cells · graph 5 nodes / 3 edges*

B3 R_GALLERY: SUBTRACT a curved void from a slab inside the hall, giving SL.GALL. Graph: a node adjacent to the hall by an OPEN edge (no wall, no door) - the relation that makes a gallery a gallery rather than a room.

### B4 R_FACADE (curtain)

*16 cells · graph 5 nodes / 3 edges*

B4 R_FACADE (spandrel = 0): the SAME facade split as A7 with the split height driven to zero, so the whole east face becomes one storey-high pane per level. Ribbon and curtain wall are one rule with one parameter - this is the strongest evidence that the two grammars share an alphabet.

### B5 R_CORE

*26 cells · graph 10 nodes / 9 edges*

B5 R_CORE: a core strip is attached to the north face (ATTACH on a face port, not a split). It overshoots the roof by one level, which is what gives the condenser its roof terrace.

### B6 R_BRIDGE

*27 cells · graph 11 nodes / 11 edges*

B6 R_BRIDGE (the composition rule): a single volume at L1 linking the condenser core to the block's corridor. In the graph it is a CUT VERTEX - delete it and the design falls into two components. The two grammars are therefore composed by exactly one production, which is why they can be developed, and varied, independently.


## Section family (the variant engine)

| id | levels | corridor level | section | note |
|---|---|---|---|---|
| V1 | 2 | 0 | L | as built: K-type, 2 levels, corridor at the bottom |
| V2 | 3 | 1 | U | as built: F-type, 3 levels, corridor through the middle |
| V3 | 2 | 1 | Gamma | unbuilt: corridor at the TOP - the L flipped, access over the dwelling |
| V4 | 4 | 1 | Z | unbuilt: 4 levels, corridor at level 1 - a skip-stop section, one street per four floors |
