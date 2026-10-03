"""
rules.py -- the Dom Narkomfin graph grammar, as site-level productions
======================================================================
Ported from the prototype `narkomfin_graph_grammar.py`. There every production rewrote the whole
building at once; here every production names its SITES and rewrites one of them, so a derivation can
be driven by hand. Applying a production at all its sites reproduces the prototype step.

    Grammar GA  "BLOCK"       GA0 axiom, GA1 lift, GA2 stack, GA3 bay, GA4 corridor,
                              GA5 cell (L / U / end unit), GA6 core, GA7 facade (IDENTITY), GA8 roof
    Grammar GB  "CONDENSER"   GB0 axiom, GB1 stack, GB2 merge, GB3 gallery,
                              GB4 facade (IDENTITY), GB5 core, GB6 bridge (composition)

Titles, stages and descriptions are data, in pack.json. What is here is only what the data cannot say.
"""
from topogrammar.graph.grammar import Site


def _z(P, lv):
    """Height of the middle of storey `lv` of the block (levels count from 1)."""
    d = P["dim"]
    return d["pilotis"] + (lv - 0.5) * d["storey"]


def _end_bays(P):
    return list(range(P["core_lines"][0])) + list(range(P["core_lines"][-1] + 1, P["bays"]))


def cell_id(P, tag, bay, lo):
    """Semantic id of a dwelling. Groups may share a tag (V2 stacks three F cells in one bay); the level
    then belongs to the id, or the cells of one bay would be the same node."""
    shared = sum(1 for c in P["cells"] if c[3] == tag) > 1
    return f"{tag}{bay:02d}_L{lo}" if shared else f"{tag}{bay:02d}"


def section_kind(levels, ci):
    if levels < 2:
        return "flat"
    if ci == 0:
        return "L"
    if ci == levels - 1:
        return "Gamma"
    return "U" if levels == 3 else "Z"


# ---------------------------------------------------------------- GRAMMAR GA : the block
def ga0_sites(s, P):
    return [] if "GA0" in s.flags else [Site("GA0", "block", "the block")]


def ga0_apply(s, site, P):
    d = P["dim"]
    s.add("BLOCK", (P["bays"] * d["bay"] / 2, d["depth"] / 2, 8.0), label="BLOCK", type="mass", block="A")
    s.flags.add("GA0")


def ga1_sites(s, P):
    return [Site("GA1", n, "BLOCK", (n,)) for n in s.match(type="mass", block="A") if n == "BLOCK"]


def ga1_apply(s, site, P):
    d = P["dim"]
    s.remove("BLOCK")
    s.add("GROUND", (P["bays"] * d["bay"] / 2, d["depth"] / 2, 1.2), label="GROUND", type="ground", block="A")
    s.add("MASS", (P["bays"] * d["bay"] / 2, d["depth"] / 2, 11.0), label="MASS", type="mass", block="A")
    s.link("GROUND", "MASS", "supports")


def ga2_sites(s, P):
    return [Site("GA2", n, "MASS", (n,)) for n in s.match(type="mass", block="A") if n == "MASS"]


def ga2_apply(s, site, P):
    d = P["dim"]
    s.remove("MASS")
    for lv in range(1, P["levels"] + 1):
        s.add(f"L{lv}", (P["bays"] * d["bay"] / 2, d["depth"] / 2, _z(P, lv)),
              label=f"STOREY L{lv}", type="storey", level=lv, block="A")
        s.link(f"L{lv-1}" if lv > 1 else "GROUND", f"L{lv}", "above")


def ga3_sites(s, P):
    return [Site("GA3", n, f"storey L{s.get(n, 'level')}", (n,), dict(level=s.get(n, "level")))
            for n in s.match(type="storey", block="A")]


def ga3_apply(s, site, P):
    d, lv = P["dim"], site.args["level"]
    s.remove(f"L{lv}")
    for i in range(P["bays"]):
        s.add(f"b{lv}_{i:02d}", ((i + 0.5) * d["bay"], d["depth"] / 2, _z(P, lv)),
              label=f"BAY {i}", type="bay", level=lv, bay=i, block="A")
        if i:
            s.link(f"b{lv}_{i-1:02d}", f"b{lv}_{i:02d}", "party")
    # a bay sits on the bay below and under the bay above, wherever those storeys are already divided
    for i in range(P["bays"]):
        s.link(f"b{lv-1}_{i:02d}", f"b{lv}_{i:02d}", "above")
        s.link(f"b{lv}_{i:02d}", f"b{lv+1}_{i:02d}", "above")


def ga4_sites(s, P):
    out = []
    for lv in P["corridor_levels"]:
        bays = s.match(type="bay", level=lv)
        if bays and not s.match(type="corridor", level=lv):
            out.append(Site("GA4", f"street_L{lv}", f"street on L{lv}", tuple(bays), dict(level=lv)))
    return out


def ga4_apply(s, site, P):
    d, lv = P["dim"], site.args["level"]
    prev = None
    for i in range(P["bays"]):
        bid = f"b{lv}_{i:02d}"
        if bid not in s:
            continue
        cid = f"c{lv}_{i:02d}"
        s.add(cid, ((i + 0.5) * d["bay"], d["corridor"] / 2, _z(P, lv)),
              label=f"CORRIDOR L{lv}", type="corridor", level=lv, bay=i, symbol="SP.CORRIDOR", block="A")
        s.update(bid, pos=((i + 0.5) * d["bay"], (d["corridor"] + d["depth"]) / 2, _z(P, lv)))
        s.link(cid, bid, "door")
        if prev:
            s.link(prev, cid, "corridor")
        prev = cid


def ga5_sites(s, P):
    out = []
    for (lo, hi, ci, tag) in P["cells"]:
        levels = hi - lo + 1
        for i in range(P["core_lines"][0] + 1, P["bays"] - P["ends"]):
            if i in P["core_lines"]:
                continue
            run = [f"b{lv}_{i:02d}" for lv in range(lo, hi + 1) if s.get(f"b{lv}_{i:02d}", "type") == "bay"]
            if len(run) == levels:
                out.append(Site("GA5", f"{tag}{i:02d}_L{lo}", f"{tag} [{section_kind(levels, ci)}] bay {i}, L{lo}-L{hi}",
                                tuple(run), dict(kind="cell", lo=lo, hi=hi, ci=ci, tag=tag, bay=i)))
    # the end bays are single-level end dwellings; their access arrives with GA6
    for i in _end_bays(P):
        for lv in range(1, P["levels"]):
            bid = f"b{lv}_{i:02d}"
            if s.get(bid, "type") == "bay":
                out.append(Site("GA5", f"E{lv}_{i:02d}", f"end unit bay {i}, L{lv}", (bid,),
                                dict(kind="end", level=lv, bay=i)))
    return out


def ga5_apply(s, site, P):
    d, a = P["dim"], site.args
    i = a["bay"]
    if a["kind"] == "end":
        lv = a["level"]
        nid = s.contract(site.nodes, f"E{lv}_{i:02d}", label=f"END UNIT L{lv} b{i}", type="dwelling", tag="E",
                         kind="flat", levels=1, corridor_index=0, bay=i, level=lv, symbol="SP.CELL.E", block="A")
        # the street stops at the cores: an end unit is entered from the stair lobby, so the corridor
        # door it inherited from GA4 goes
        for other, e in s.neighbours(nid):
            if e["rel"] == "door" and s.get(other, "type") == "corridor":
                s.unlink(nid, other)
        return
    lo, hi, ci, tag = a["lo"], a["hi"], a["ci"], a["tag"]
    levels = hi - lo + 1
    kind = section_kind(levels, ci)
    nid = s.contract(site.nodes, cell_id(P, tag, i, lo),
               pos=((i + 0.5) * d["bay"], (d["corridor"] + d["depth"]) / 2,
                    d["pilotis"] + (lo - 1 + levels / 2) * d["storey"]),
               label=f"{tag} [{kind}] b{i}", type="dwelling", tag=tag, kind=kind, levels=levels,
               corridor_index=ci, bay=i, level=lo, symbol=f"SP.CELL.{tag}", block="A")
    # K dwellings are built in mirrored pairs; mark the shared party edge
    if tag == "K":
        for other, e in s.neighbours(nid):
            if e["rel"] == "party" and s.get(other, "tag") == "K":
                if abs(s.get(other, "bay") - i) == 1 and min(s.get(other, "bay"), i) % 2 == 1:
                    s.update_edge(nid, other, mirror=True)


def ga6_sites(s, P):
    out = []
    for i in P["core_lines"]:
        stack = [f"b{lv}_{i:02d}" for lv in range(1, P["levels"] + 1) if s.get(f"b{lv}_{i:02d}", "type") == "bay"]
        if stack:
            out.append(Site("GA6", f"core_{i:02d}", f"core on line {i}", tuple(stack), dict(bay=i)))
    return out


def ga6_apply(s, site, P):
    d, i = P["dim"], site.args["bay"]
    for lv in range(1, P["levels"] + 1):
        s.remove(f"b{lv}_{i:02d}", f"c{lv}_{i:02d}")
        sid = f"S{lv}_{i:02d}"
        s.add(sid, ((i + 0.5) * d["bay"], d["depth"] - 2.5, _z(P, lv)),
              label=f"STAIRWELL b{i}", type="stairwell", level=lv, bay=i, symbol="SP.STAIRWELL", block="A")
        s.link(f"S{lv-1}_{i:02d}" if lv > 1 else "GROUND", sid, "stair")
        # the core interrupts the street, so it carries it: a door on each side
        if lv in P["corridor_levels"]:
            for nb in (f"c{lv}_{i-1:02d}", f"c{lv}_{i+1:02d}"):
                s.link(sid, nb, "core_door")
        # the end units on this level are entered from the stair lobby
        for nb in (f"E{lv}_{i-1:02d}", f"E{lv}_{i+1:02d}", f"E{lv}_{i-2:02d}", f"E{lv}_{i+2:02d}"):
            s.link(sid, nb, "core_door")
        # so is the dwelling beside the core, once, on the level it is entered from
        tags = {c[3] for c in P["cells"]}
        for n in s.match(type="dwelling", level=lv):
            if s.get(n, "tag") in tags and abs(s.get(n, "bay") - i) == 1:
                s.link(sid, n, "core_door")


def _identity(rule_id, needs):
    def sites(s, P):
        if rule_id in s.flags or not s.match(**needs):
            return []
        return [Site(rule_id, "envelope", "the envelope")]

    def apply(s, site, P):
        s.flags.add(rule_id)                    # deliberately nothing else: no graph counterpart

    return sites, apply


def ga8_sites(s, P):
    out = []
    top = s.match(type="bay", level=P["levels"])
    if top:
        out.append(Site("GA8", "roof", f"roof zone, L{P['levels']}", tuple(top), dict(kind="roof")))
    core = f"S{P['levels']}_{P['core_lines'][0]:02d}"
    if core in s and "PENTHOUSE" not in s:
        out.append(Site("GA8", "penthouse", "penthouse on the west core", (core,), dict(kind="penthouse", core=core)))
    return out


def ga8_apply(s, site, P):
    d = P["dim"]
    if site.args["kind"] == "roof":
        for n in site.nodes:
            s.update(n, type="roof", label="ROOF ZONE " + s.get(n, "label"), symbol="SL.ROOF")
        return
    s.add("PENTHOUSE", (P["bays"] * d["bay"] * 0.36, d["depth"] * 0.75, d["pilotis"] + P["levels"] * d["storey"] + 1.4),
          label="PENTHOUSE", type="dwelling", tag="PH", kind="flat", levels=1, block="A")
    s.link(site.args["core"], "PENTHOUSE", "stair")


# ---------------------------------------------------------------- GRAMMAR GB : the condenser
def _cb(P):
    """Centre of the condenser in plan."""
    d = P["dim"]
    return d["cb_origin"][0] + d["cb_length"] / 2, d["cb_origin"][1] + d["cb_depth"] / 2


def _cb_core(P):
    d = P["dim"]
    return d["cb_origin"][0] + d["cb_core_length"] / 2, d["cb_origin"][1] + d["cb_depth"] + d["cb_core_depth"] / 2


def gb0_sites(s, P):
    return [] if "GB0" in s.flags else [Site("GB0", "condenser", "the condenser")]


def gb0_apply(s, site, P):
    d = P["dim"]
    cx, cy = _cb(P)
    s.add("COND", (cx, cy, 5.0), label="CONDENSER", type="mass", block="B")
    s.add("IFACE", (0.0, d["corridor"] / 2, _z(P, 1)), label="[interface] BLOCK L1 corridor",
          type="interface", block="A/B")
    s.flags.add("GB0")


def gb1_sites(s, P):
    return [Site("GB1", n, "CONDENSER", (n,)) for n in s.match(type="mass", block="B")]


def gb1_apply(s, site, P):
    h = P["dim"]["storey"]
    cx, cy = _cb(P)
    s.remove("COND")
    for lv in range(P["cb_levels"]):
        s.add(f"CB{lv}", (cx, cy, (lv + 0.5) * h), label=f"CB L{lv}", type="storey", level=lv, block="B")
        if lv:
            s.link(f"CB{lv-1}", f"CB{lv}", "above")


def gb2_sites(s, P):
    lo, hi = P["cb_merge"]
    run = [f"CB{lv}" for lv in range(lo, hi + 1) if s.get(f"CB{lv}", "type") == "storey"]
    if len(run) == hi - lo + 1 and "HALL" not in s:
        return [Site("GB2", "hall", f"storeys CB{lo}-CB{hi}", tuple(run))]
    return []


def gb2_apply(s, site, P):
    h = P["dim"]["storey"]
    lo, hi = P["cb_merge"]
    cx, cy = _cb(P)
    s.contract(site.nodes, "HALL", pos=(cx, cy, (lo + (hi - lo + 1) / 2) * h),
               label="SP.HALL (social condenser)", type="hall", symbol="SP.HALL", block="B",
               level=lo, levels=hi - lo + 1)


def gb3_sites(s, P):
    if "HALL" in s and "GALLERY" not in s:
        return [Site("GB3", "gallery", "gallery in the hall", ("HALL",))]
    return []


def gb3_apply(s, site, P):
    h = P["dim"]["storey"]
    cx, cy = _cb(P)
    s.add("GALLERY", (cx, cy - 1.2, (P["cb_merge"][1] + 0.6) * h), label="GALLERY", type="gallery",
          symbol="SL.GALL", block="B", level=P["cb_merge"][1])
    s.link("HALL", "GALLERY", "open")


def gb5_sites(s, P):
    if "HALL" in s and "CBS0" not in s:
        return [Site("GB5", "core", "condenser core", ("HALL",))]
    return []


def gb5_apply(s, site, P):
    h = P["dim"]["storey"]
    x, y = _cb_core(P)
    for lv in range(P["cb_core_levels"]):
        sid = f"CBS{lv}"
        s.add(sid, (x, y, (lv + 0.5) * h), label=f"CB CORE L{lv}", type="stairwell", level=lv,
              symbol="SP.STAIRWELL", block="B")
        if lv:
            s.link(f"CBS{lv-1}", sid, "stair")
    s.link("CBS1", "HALL", "core_door")
    s.link("CBS2", "GALLERY", "core_door")


def gb6_sites(s, P):
    street = s.match(type="corridor", level=P["corridor_levels"][0])
    if "CBS1" in s and "IFACE" in s and "BRIDGE" not in s and street:
        return [Site("GB6", "bridge", "bridge to the block's street", ("CBS1", "IFACE", street[0]))]
    return []


def gb6_apply(s, site, P):
    d = P["dim"]
    y0 = d["cb_origin"][1] + d["cb_depth"] + d["cb_core_depth"]
    s.add("BRIDGE", (d["bridge_width"] / 2, y0 / 2, _z(P, 1)), label="SP.BRIDGE", type="bridge",
          symbol="SP.BRIDGE", block="A/B", level=1)
    s.link("CBS1", "BRIDGE", "bridge")
    s.link("BRIDGE", "IFACE", "bridge")
    # GLUING: the interface node is identified with the block's first corridor node
    s.link("IFACE", site.nodes[2], "door")


PROCEDURES = {
    "GA0": (ga0_sites, ga0_apply), "GA1": (ga1_sites, ga1_apply), "GA2": (ga2_sites, ga2_apply),
    "GA3": (ga3_sites, ga3_apply), "GA4": (ga4_sites, ga4_apply), "GA5": (ga5_sites, ga5_apply),
    "GA6": (ga6_sites, ga6_apply), "GA7": _identity("GA7", dict(block="A")), "GA8": (ga8_sites, ga8_apply),
    "GB0": (gb0_sites, gb0_apply), "GB1": (gb1_sites, gb1_apply), "GB2": (gb2_sites, gb2_apply),
    "GB3": (gb3_sites, gb3_apply), "GB4": _identity("GB4", dict(block="B")), "GB5": (gb5_sites, gb5_apply),
    "GB6": (gb6_sites, gb6_apply),
}
