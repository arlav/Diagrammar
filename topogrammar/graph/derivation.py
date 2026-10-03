"""
derivation.py -- choices, consequences and pathways
===================================================
A derivation is a tree of states. At every state the engine offers every match of every rule that is
a choice; rules marked `auto` are consequences and are applied to a fixpoint after each choice.

Two offered sites are INDEPENDENT when neither changes a node the other reads (parallel independence
in the double-pushout sense): applying them in either order gives the same state. When they are not,
the choice between them is a decision. The engine marks those.

A PATHWAY is the sequence of choices from the start to a state: rule, parameters, the nodes matched.
It can be named, replayed on a fresh derivation, compared with another, and hashed (a chain over the
steps, together with the hash of the pack): the brief's axis E2.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field

from .metrics import metrics
from .patterns import Snapshot, Expr, Ns
from .state import GraphState

ALL = "*"


@dataclass
class Step:
    id: int
    parent: object
    rule: object
    sites: list                                  # the sites chosen
    label: str
    state: GraphState
    metrics: dict
    event: dict
    consequences: list = field(default_factory=list)   # (rule id, site label) applied automatically
    decisions: int = 0                                   # how many of the chosen sites had competitors
    elapsed_ms: float = 0.0
    children: list = field(default_factory=list)

    @property
    def applications(self):
        return len(self.sites)


def diff(before, after):
    nb, na = before.nodes(), after.nodes()
    key = lambda e: (min(e["a"], e["b"]), max(e["a"], e["b"]))
    eb = {key(e): e for e in before.edges()}
    ea = {key(e): e for e in after.edges()}
    strip = lambda d: {k: v for k, v in d.items() if k != "pos"}
    changed = sorted(n for n in nb.keys() & na.keys() if strip(nb[n]) != strip(na[n]))
    return dict(nodes_removed=sorted(nb.keys() - na.keys()), nodes_added=sorted(na.keys() - nb.keys()),
                nodes_changed=changed,
                edges_removed=[eb[k] for k in sorted(eb.keys() - ea.keys())],
                edges_added=[ea[k] for k in sorted(ea.keys() - eb.keys())],
                edges_changed=[ea[k] for k in sorted(eb.keys() & ea.keys()) if eb[k] != ea[k]])


class Derivation:
    def __init__(self, pack, params=None, preset=None):
        self.pack = pack
        self.preset = preset
        self.P = params if params is not None else pack.params(preset)
        self.env = pack.env(self.P)
        root = GraphState(pack.title, pack.relations)
        self.steps = {0: Step(0, None, None, [], "start", root, metrics(root), diff(root, root))}
        self.head = 0
        self._offers = {}                         # step id -> offers, computed once per state

    @property
    def state(self):
        return self.steps[self.head].state

    # -- positions come from the interpreter, so rules need not know geometry ------------
    def _pos_of(self, state):
        interp = self.pack.modules.get("interpret")
        if interp is None:
            return None
        from ..scene.mesh import centroid
        cache = {}

        def pos(nid):
            if not cache:
                for c in interp.cells(state, dict(self.P, dim=self.pack.dimensions)):
                    cache[c["id"]] = centroid(c["profile"], c["axis"], c["a0"], c["a1"])
            return cache.get(nid)
        return pos

    def _place(self, state, ids):
        pos = self._pos_of(state)
        if pos is None:
            return
        for nid in ids:
            p = pos(nid)
            if p is not None:
                state.update(nid, pos=p)

    # -- what can be done here ------------------------------------------------
    def offers(self, step=None):
        """Every site of every rule that is a choice, with its independence from the others."""
        sid = self.head if step is None else step
        if sid in self._offers:
            return self._offers[sid]
        snap = Snapshot(self.steps[sid].state)
        sites = []
        for r in self.pack.rules.values():
            if not r.auto:
                sites.extend(r.sites(snap, self.env))
        # a site conflicts with another when it changes a node the other reads, or vice versa
        reads = {}
        for i, s in enumerate(sites):
            for n in s.nodes:
                reads.setdefault(n, set()).add(i)
        conflicts = [set() for _ in sites]
        for i, s in enumerate(sites):
            for n in s.touched:
                for j in reads.get(n, ()):
                    if j != i:
                        conflicts[i].add(j)
                        conflicts[j].add(i)
        out = []
        for i, s in enumerate(sites):
            with_rules = sorted({sites[j].rule for j in conflicts[i]})
            out.append(dict(site=s, conflicts=sorted(sites[j].key for j in conflicts[i]), conflicts_with=with_rules,
                            decisive=any(sites[j].rule != s.rule or sites[j].params != s.params for j in conflicts[i])))
        self._offers[sid] = out
        return out

    def complete(self, step=None):
        return not self.offers(step)

    def _find(self, rule_id, selection, offers):
        """The sites a selection names: a key, a list of keys, '*', or {'where': expr, 'params': {...}}."""
        mine = [o["site"] for o in offers if o["site"].rule == rule_id]
        if rule_id not in self.pack.rules:
            raise ValueError(f"There is no rule called {rule_id}.")
        if not mine:
            raise ValueError(f"{rule_id} has no site in this state.")
        if selection is None:
            if len(mine) != 1:
                raise ValueError(f"{rule_id} has {len(mine)} sites here; choose one, or '*'.")
            return mine
        if selection == ALL:
            return mine
        if isinstance(selection, str):
            found = [s for s in mine if s.key == selection]
            if not found:
                raise ValueError(f"{rule_id} has no site '{selection}' here.")
            return found
        if isinstance(selection, (list, tuple)):
            keys = set(selection)
            found = [s for s in mine if s.key in keys]
            if len(found) != len(keys):
                raise ValueError(f"{rule_id}: {len(keys) - len(found)} of the named sites are not in this state.")
            return found
        if isinstance(selection, dict):
            params = selection.get("params")
            where = Expr(selection["where"]) if selection.get("where") else None
            snap = Snapshot(self.state)
            found = []
            for s in mine:
                if params and any(dict(s.params).get(k) != v for k, v in params.items()):
                    continue
                if where is not None:
                    env = {**self.env, **dict(s.params), **{v: snap.ns[n] for v, n in s.binding}}
                    if not where(env):
                        continue
                found.append(s)
            if selection.get("group") is not None:
                found = [s for s in found if s.group == selection["group"]]
            return found
        raise ValueError("A selection is a site key, a list of keys, '*' or {where, params, group}.")

    # -- doing it ----------------------------------------------------------------
    def _consequences(self, state):
        """Apply every `auto` rule until none matches. Returns what was applied."""
        done = []
        auto = [r for r in self.pack.rules.values() if r.auto]
        for _ in range(1000):
            applied = 0
            for r in auto:
                snap = Snapshot(state)
                for site in r.sites(snap, self.env):
                    if applied and not r.still_valid(site, Snapshot(state), self.env):
                        continue
                    r.apply(state, site, self.env)
                    done.append((site.rule, site.label))
                    applied += 1
            if not applied:
                return done
        raise RuntimeError("the automatic rules do not reach a fixpoint")

    def _rewrite(self, rule_id, selection, with_consequences=True):
        rule = self.pack.rules.get(rule_id)
        if rule is None:
            raise ValueError(f"There is no rule called {rule_id}.")
        if rule.auto:
            raise ValueError(f"{rule_id} is a consequence, not a choice; it is applied automatically.")
        offers = self.offers()
        chosen = self._find(rule_id, selection, offers)
        decisive = {o["site"].key for o in offers if o["decisive"]}
        before = self.state
        state = before.copy()
        t0 = time.perf_counter()
        applied = []
        for site in chosen:
            # earlier applications may have consumed this site
            if applied and not rule.still_valid(site, Snapshot(state), self.env):
                continue
            rule.apply(state, site, self.env)
            applied.append(site)
        consequences = self._consequences(state) if with_consequences else []
        # every node is placed from its cell once the step is complete: a rule need not know geometry,
        # and a band moves when its street is cut
        self._place(state, state.ids())
        elapsed = (time.perf_counter() - t0) * 1000
        event = diff(before, state)
        event.update(rule=rule.id, operation=rule.verb, shape_operation=rule.shape.get("operation", ""),
                     identity=rule.identity, sites=[s.key for s in applied],
                     params=dict(applied[0].params) if applied else {},
                     matched=sorted({n for s in applied for n in s.nodes}),
                     consequences=[dict(rule=r, label=l) for r, l in consequences])
        label = applied[0].label if len(applied) == 1 else f"{len(applied)} sites"
        return Step(max(self.steps) + 1, self.head, rule.id, applied, label, state, metrics(state), event,
                    consequences=consequences, decisions=sum(1 for s in applied if s.key in decisive),
                    elapsed_ms=elapsed)

    def preview(self, rule_id, selection=None):
        return self._rewrite(rule_id, selection)

    def apply(self, rule_id, selection=None):
        step = self._rewrite(rule_id, selection)
        if not step.sites:
            raise ValueError(f"{rule_id}: nothing to apply.")
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
        out, s = [], self.head if step is None else step
        while s is not None:
            out.append(s)
            s = self.steps[s].parent
        return out[::-1]

    # -- strategies and pathways ------------------------------------------------------
    def run(self, strategy):
        """Follow a recorded strategy: a list of {rule, params, select, repeat} steps."""
        done = []
        for item in strategy["steps"]:
            selection = item.get("select")
            if isinstance(selection, dict) and item.get("params"):
                selection = {**selection, "params": item["params"]}
            elif item.get("params") and selection is None:
                selection = {"params": item["params"]}
            elif item.get("params") and selection == ALL:
                selection = {"params": item["params"]}
            for _ in range(1000):
                offers = [o for o in self.offers() if o["site"].rule == item["rule"]]
                if not offers:
                    break
                try:
                    step = self.apply(item["rule"], selection)
                except ValueError:
                    break
                done.append(step)
                if not item.get("repeat"):
                    break
        return done

    def pathway(self, step=None):
        """The choices from the start to here, with a hash chain over them."""
        out, h = [], hashlib.sha256(self.pack.hash().encode()).hexdigest()
        for sid in self.path(step)[1:]:
            s = self.steps[sid]
            entry = dict(rule=s.rule, params=dict(s.sites[0].params) if s.sites else {},
                         sites=[sorted(site.nodes) for site in s.sites],
                         consequences=len(s.consequences), nodes=s.metrics["nodes"], edges=s.metrics["edges"])
            label, decisions = s.label, s.decisions
            h = hashlib.sha256((h + json.dumps(entry, sort_keys=True)).encode()).hexdigest()
            out.append(dict(entry, hash=h[:16], label=label, decisions=decisions, step=sid))
        return dict(pack=self.pack.hash(), lineage=self.pack.lineage(), preset=self.preset,
                    parameters=self.P, steps=out, hash=h[:16])

    def replay(self, pathway):
        """Apply a pathway's choices on this derivation, matching sites by the nodes they bound."""
        done = []
        for entry in pathway["steps"]:
            offers = [o["site"] for o in self.offers() if o["site"].rule == entry["rule"]
                      and dict(o["site"].params) == entry["params"]]
            wanted = [set(n) for n in entry["sites"]]
            keys = [s.key for s in offers if set(s.nodes) in wanted]
            if len(keys) != len(wanted):
                raise ValueError(f"step {len(done) + 1} ({entry['rule']}) does not match this state")
            done.append(self.apply(entry["rule"], keys if len(keys) > 1 else keys[0]))
        return done
