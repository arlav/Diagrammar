"""
validate.py -- is this set of parameters a building the grammar can derive?
===========================================================================
Returns a list of problems in plain words; an empty list means the derivation can start. This is the
fail-fast half of the axiom's satisfiability check: it looks at the parameters only, before any rule
is applied.
"""


def problems(P):
    out = []
    ints = ("bays", "levels", "ends", "cb_levels", "cb_core_levels")
    for k in ints:
        if not isinstance(P.get(k), int) or isinstance(P.get(k), bool) or P[k] < 0:
            out.append(f"{k} must be a whole number, zero or more")
    if out:
        return out
    bays, levels = P["bays"], P["levels"]
    if not 3 <= bays <= 60:
        out.append("bays must be between 3 and 60")
    if not 1 <= levels <= 20:
        out.append("levels must be between 1 and 20")

    cores = list(P["core_lines"])
    if not cores:
        out.append("there must be at least one core line, or nothing above the ground can be reached")
    if any(not isinstance(c, int) or not 0 <= c < bays for c in cores):
        out.append(f"every core line must be a bay between 0 and {bays - 1}")
    if sorted(set(cores)) != cores:
        out.append("core lines must be in ascending order, without repeats")

    streets = list(P["corridor_levels"])
    if any(not isinstance(lv, int) or not 1 <= lv <= levels for lv in streets):
        out.append(f"every street must be on a level between 1 and {levels}")
    if len(set(streets)) != len(streets):
        out.append("two streets cannot be on the same level")

    covered = {}
    for cell in P["cells"]:
        if len(cell) != 4:
            out.append(f"cell {list(cell)} must be [lowest level, highest level, pierced index, tag]")
            continue
        lo, hi, ci, tag = cell
        if not (isinstance(lo, int) and isinstance(hi, int) and isinstance(ci, int) and isinstance(tag, str) and tag):
            out.append(f"cell {list(cell)} must be [whole number, whole number, whole number, tag]")
            continue
        if not 1 <= lo <= hi <= levels:
            out.append(f"cell {tag} runs from L{lo} to L{hi}, outside the {levels} levels of the block")
            continue
        if tag == "E":
            out.append("the tag E is kept for the end units")
        if not 0 <= ci <= hi - lo:
            out.append(f"cell {tag} (L{lo}-L{hi}) cannot be pierced at index {ci}")
        elif lo + ci not in streets:
            out.append(f"cell {tag} (L{lo}-L{hi}) is entered on L{lo + ci}, where there is no street")
        inside = [lv for lv in streets if lo <= lv <= hi]
        if len(inside) > 1:
            out.append(f"cell {tag} (L{lo}-L{hi}) is crossed by {len(inside)} streets; a cell has one")
        for lv in range(lo, hi + 1):
            if lv in covered:
                out.append(f"L{lv} belongs to both cell {covered[lv]} and cell {tag}")
            covered[lv] = tag

    if cores and all(isinstance(c, int) for c in cores) and bays - P["ends"] <= cores[0] + 1:
        out.append("no bay is left for dwellings between the first core and the end bays")

    lo, hi = P["cb_merge"]
    if not 0 <= lo < hi < P["cb_levels"]:
        out.append(f"the hall must merge at least two of the condenser's {P['cb_levels']} storeys")
    if P["cb_core_levels"] < hi + 1:
        out.append("the condenser core must reach the gallery level")
    return out


def warnings(P):
    """Things the grammar will derive, but that leave work undone."""
    out = []
    covered = {lv for (lo, hi, _, _) in P["cells"] for lv in range(lo, hi + 1)}
    gaps = [lv for lv in range(1, P["levels"]) if lv not in covered]
    if gaps:
        out.append("no cell covers " + ", ".join(f"L{lv}" for lv in gaps)
                   + ": the bays there stay unresolved")
    last = P["bays"] - P["ends"]
    if P["core_lines"] and last < P["core_lines"][-1]:
        n = P["core_lines"][-1] - last
        out.append(f"{n} bay{'s' if n > 1 else ''} before the last core "
                   f"{'are' if n > 1 else 'is'} outside both the cells and the end units (ends = {P['ends']})")
    return out
