"""
grammar.py -- rule packs, sites and derivations
===============================================
A rule is applied at a SITE. Each rule answers two questions:

    sites(state, P)        where can I be applied?
    apply(state, site, P)  rewrite the state there

Rules are stratified. A rule is enabled only when no earlier stage of its own grammar still has open
sites, so the order inside a stage is free and the order between stages is not.

A rule pack is a directory: `pack.json` holds everything that is data (titles, stages, operations,
relations, parameters, presets); a Python module beside it holds the procedures the data cannot yet
express.
"""
import importlib.util
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .metrics import metrics
from .state import GraphState

ALL = "*"


@dataclass(frozen=True)
class Site:
    rule: str
    key: str                                   # stable within one state
    label: str
    nodes: tuple = ()                          # the nodes the left-hand side binds
    args: dict = field(default_factory=dict, compare=False, hash=False)


@dataclass
class Rule:
    id: str
    name: str
    grammar: str
    stage: int
    operation: str                             # what the production does to the graph
    shape_operation: str                       # what its counterpart does to the shape
    description: str
    sites: object = None
    apply: object = None
    identity: bool = False
    symbols: tuple = ()


class RulePack:
    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads((self.path / "pack.json").read_text())
        self.title = self.data["title"]
        self.version = self.data["version"]
        self.relations = self.data["relations"]
        self.occupiable = self.data["occupiable"]
        self.nonterminals = self.data["nonterminals"]
        self.source = self.data["source"]
        self.dimensions = self.data["dimensions"]
        self.presets = self.data["presets"]
        self.modules = {name: self._load(file) for name, file in self.data["modules"].items()}
        procedures = self.modules["rules"].PROCEDURES
        self.rules = []
        for r in self.data["rules"]:
            sites, apply = procedures[r["id"]]
            self.rules.append(Rule(id=r["id"], name=r["name"], grammar=r["grammar"], stage=r["stage"],
                                   operation=r["operation"], shape_operation=r["shape_operation"],
                                   description=r["description"], identity=r.get("identity", False),
                                   symbols=tuple(r.get("symbols", ())), sites=sites, apply=apply))
        self.by_id = {r.id: r for r in self.rules}

    def _load(self, file):
        spec = importlib.util.spec_from_file_location(f"{self.path.name}_{Path(file).stem}", self.path / file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def params(self, preset=None, **over):
        """Parameters of a derivation: the pack's defaults, then a preset, then explicit overrides."""
        P = dict(self.data["parameters"])
        if preset is not None:
            P.update(self.presets[preset]["parameters"])
        P.update(over)
        P = {k: _tuples(v) for k, v in P.items()}
        P["dim"] = dict(self.dimensions)
        return P

    def golden(self, preset):
        """The recorded graph a preset must reproduce, if the pack holds one."""
        file = self.presets.get(preset, {}).get("golden")
        return json.loads((self.path / file).read_text()) if file else None


def _tuples(v):
    return tuple(_tuples(x) for x in v) if isinstance(v, list) else v


@dataclass
class Step:
    id: int
    parent: object
    rule: object
    site: object
    label: str
    state: GraphState
    metrics: dict
    event: dict
    note: str = ""
    applications: int = 1
    elapsed_ms: float = 0.0
    children: list = field(default_factory=list)


def diff(before, after):
    """What a production did, read off the two states."""
    nb, na = before.nodes(), after.nodes()
    key = lambda e: (min(e["a"], e["b"]), max(e["a"], e["b"]))
    eb = {key(e): e for e in before.edges()}
    ea = {key(e): e for e in after.edges()}
    changed = sorted(n for n in nb.keys() & na.keys()
                     if {k: v for k, v in nb[n].items() if k != "pos"} != {k: v for k, v in na[n].items() if k != "pos"})
    return dict(nodes_removed=sorted(nb.keys() - na.keys()), nodes_added=sorted(na.keys() - nb.keys()),
                nodes_changed=changed,
                edges_removed=[eb[k] for k in sorted(eb.keys() - ea.keys())],
                edges_added=[ea[k] for k in sorted(ea.keys() - eb.keys())],
                edges_changed=[ea[k] for k in sorted(eb.keys() & ea.keys()) if eb[k] != ea[k]])


class Derivation:
    """A tree of states. Applying a rule at the head adds a child; going back and applying another
    rule starts a branch."""

    def __init__(self, pack, params=None, preset=None):
        self.pack = pack
        self.preset = preset
        self.P = params if params is not None else pack.params(preset)
        root = GraphState(pack.title, pack.relations)
        self.steps = {0: Step(0, None, None, None, "start", root, metrics(root),
                              diff(root, root), note="The empty state, before any axiom.")}
        self.head = 0

    @property
    def state(self):
        return self.steps[self.head].state

    # -- what can be done here ---------------------------------------------
    def applicable(self, step=None):
        """Every rule of the pack with its open sites at this step and, if it is held back, why."""
        state = self.steps[self.head if step is None else step].state
        open_sites = {r.id: r.sites(state, self.P) for r in self.pack.rules}
        out = []
        for r in self.pack.rules:
            blocking = [q.id for q in self.pack.rules
                        if q.grammar == r.grammar and q.stage < r.stage and open_sites[q.id]]
            sites = open_sites[r.id]
            if blocking:
                reason = "waits for " + ", ".join(blocking)
            elif not sites:
                reason = "no site matches"
            else:
                reason = ""
            out.append(dict(rule=r, sites=sites, enabled=bool(sites) and not blocking, reason=reason))
        return out

    def complete(self, step=None):
        return not any(a["enabled"] for a in self.applicable(step))

    # -- doing it ------------------------------------------------------------
    def _rewrite(self, rule_id, site_key):
        entry = next(a for a in self.applicable() if a["rule"].id == rule_id)
        rule = entry["rule"]
        if not entry["enabled"]:
            raise ValueError(f"{rule_id} cannot be applied here: {entry['reason']}")
        if site_key is None:
            if len(entry["sites"]) != 1:
                raise ValueError(f"{rule_id} has {len(entry['sites'])} sites here; name one, or use '*'")
            site_key = entry["sites"][0].key
        before = self.steps[self.head].state
        state = before.copy()
        t0 = time.perf_counter()
        notes, applied = [], []
        if site_key == ALL:
            for key in [s.key for s in entry["sites"]]:
                site = next((s for s in rule.sites(state, self.P) if s.key == key), None)
                if site is not None:                     # an earlier application may have consumed it
                    notes.append(rule.apply(state, site, self.P))
                    applied.append(site)
        else:
            site = next((s for s in entry["sites"] if s.key == site_key), None)
            if site is None:
                raise ValueError(f"{rule_id} has no site '{site_key}' here")
            notes.append(rule.apply(state, site, self.P))
            applied.append(site)
        elapsed = (time.perf_counter() - t0) * 1000
        event = diff(before, state)
        event.update(rule=rule.id, operation=rule.operation, shape_operation=rule.shape_operation,
                     identity=rule.identity, sites=[s.key for s in applied],
                     matched=sorted({n for s in applied for n in s.nodes}))
        label = applied[0].label if len(applied) == 1 else f"{len(applied)} sites"
        return Step(max(self.steps) + 1, self.head, rule.id, ALL if len(applied) > 1 else applied[0].key,
                    label, state, metrics(state), event, note=next((n for n in notes if n), ""),
                    applications=len(applied), elapsed_ms=elapsed)

    def preview(self, rule_id, site_key=None):
        """What applying the rule would give, without taking the step."""
        return self._rewrite(rule_id, site_key)

    def apply(self, rule_id, site_key=None):
        """Apply a rule at one site, or at every open site with `site_key=ALL`."""
        step = self._rewrite(rule_id, site_key)
        self.steps[step.id] = step
        self.steps[self.head].children.append(step.id)
        self.head = step.id
        return step

    def goto(self, step):
        if step not in self.steps:
            raise ValueError(f"no step {step}")
        self.head = step
        return self.steps[step]

    def undo(self):
        parent = self.steps[self.head].parent
        return self.goto(self.head if parent is None else parent)

    def path(self, step=None):
        """The steps from the start to `step`."""
        out, s = [], self.head if step is None else step
        while s is not None:
            out.append(s)
            s = self.steps[s].parent
        return out[::-1]

    def run(self, until=None):
        """The canonical derivation: every enabled rule, in pack order, at all its sites. Stops after
        the rule `until` has been applied, or when nothing is left to apply."""
        done = []
        while True:
            entry = next((a for a in self.applicable() if a["enabled"]), None)
            if entry is None:
                return done
            done.append(self.apply(entry["rule"].id, ALL))
            if until is not None and entry["rule"].id == until:
                return done
