"""
rules.py -- a production as data
================================
A rule has a left-hand side (a pattern), negative application conditions, and a right-hand side
written as effects on the matched nodes:

    create     new nodes, attributes from templates and expressions
    contract   several matched nodes become one new node; outside edges survive
    relabel    attributes (and the id) of a matched node change
    delete     matched nodes go
    link / unlink / set_edge

Rules may carry parameters (`params`), each with the list of values it may take; a rule with
parameters stands for one concrete rule per combination. Rules marked `auto` are consequences, not
choices: the engine applies them to a fixpoint after every step.
"""
import hashlib
import itertools
import json
from dataclasses import dataclass, field

from .patterns import Expr, Ns, Pattern, Snapshot, expand, expand_names, extends, matches, value

EFFECTS = ("delete", "contract", "create", "relabel", "unlink", "link", "set_edge", "flag")


@dataclass(frozen=True)
class Site:
    """One place a rule can be applied: a binding of its variables, under one set of parameters."""
    rule: str
    params: tuple                               # ((name, value), ...)
    binding: tuple                              # ((var, node id), ...)
    key: str
    label: str
    group: str
    nodes: tuple                                # the matched nodes, for highlighting
    touched: tuple                              # the matched nodes the rule changes or removes

    @property
    def bound(self):
        return dict(self.binding)


class Rule:
    def __init__(self, spec, source=None):
        self.spec = spec
        self.id = spec["id"]
        self.title = spec.get("title", self.id)
        self.verb = spec.get("verb", "")
        self.grammar = spec.get("grammar", "")
        self.description = spec.get("description", "")
        self.symbols = tuple(spec.get("symbols", ()))
        self.shape = spec.get("shape", {})
        self.auto = bool(spec.get("auto", False))
        self.identity = bool(spec.get("identity", False))
        self.params = spec.get("params", {}) or {}
        self.group = spec.get("group", self.title)
        self.label = spec.get("label", "")
        self.source = source
        self._touch_vars = None

    # -- identity --------------------------------------------------------
    def hash(self):
        canon = json.dumps(self.spec, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canon.encode()).hexdigest()[:16]

    # -- parameters --------------------------------------------------------
    def param_sets(self, env):
        """Every combination of parameter values. A value list may be an expression of the pack's
        parameters (`"=[P.levels]"`) or of parameters declared before it (`"=range(k)"`)."""
        names = list(self.params)
        if not names:
            return [()]
        out = []

        def rec(i, acc):
            if i == len(names):
                out.append(tuple(acc.items()))
                return
            spec = self.params[names[i]]
            values = Expr(spec[1:])({**env, **acc}) if isinstance(spec, str) and spec.startswith("=") else spec
            for v in values:
                rec(i + 1, {**acc, names[i]: v})

        rec(0, {})
        return out

    # -- matching ------------------------------------------------------------
    def patterns(self, params, env):
        key = (params, tuple(sorted(env["P"]._d.items())) if "P" in env else ())
        cache = self.__dict__.setdefault("_pattern_cache", {})
        if key not in cache:
            cache[key] = self._patterns(params, env)
        return cache[key]

    def _patterns(self, params, env):
        e = {**env, **dict(params)}
        lhs = Pattern.build(self.spec.get("lhs") or {}, e)
        nacs = []
        for spec in expand(self.spec.get("nac") or [], e):      # a NAC with `for` is several NACs
            # a NAC extends the LHS: its nodes are additional, its edges may reach LHS variables
            p = Pattern.build(spec, e)
            # LHS variables referenced by the NAC are fixed when it is checked; declare them typeless
            for a, b, _ in p.edges:
                for v in (a, b):
                    if v not in p.nodes and v in lhs.nodes:
                        p.nodes[v] = {}
            for w in p.where:
                for v in w.names & set(lhs.nodes):
                    p.nodes.setdefault(v, {})
            nacs.append(p)
        return lhs, nacs

    def still_valid(self, site, snap, env):
        """Does this site still match, after other applications changed the state?"""
        e = {**env, **dict(site.params)}
        lhs, nacs = self.patterns(site.params, env)
        binding = site.bound
        if any(n not in snap.nodes for n in binding.values()):
            return False
        if not any(True for _ in matches(lhs, snap, e, bound=binding, first=True)):
            return False
        return not any(extends(n, snap, e, binding) for n in nacs)

    def touched_vars(self, params, env):
        """Which LHS variables the right-hand side changes or removes."""
        cache = self.__dict__.setdefault("_touched", {})
        if params in cache:
            return cache[params]
        rhs = expand(self.spec.get("rhs") or {}, {**env, **dict(params)})
        out = set(rhs.get("delete") or [])
        if rhs.get("contract"):
            out |= set(value(rhs["contract"].get("nodes") or [], {**env, **dict(params)}))
        out |= set((rhs.get("relabel") or {}).keys())
        for a, b in rhs.get("unlink") or []:
            out |= {a, b}
        cache[params] = out
        return out

    def sites(self, snap, env):
        out = []
        for params in self.param_sets(env):
            lhs, nacs = self.patterns(params, env)
            touched = self.touched_vars(params, env)
            e = {**env, **dict(params)}
            for binding in matches(lhs, snap, e):
                if any(extends(n, snap, e, binding) for n in nacs):
                    continue
                be = {**e, **{v: snap.ns[n] for v, n in binding.items()}}
                nodes = tuple(binding[v] for v in lhs.vars)
                key = f"{self.id}" + (f"({','.join(f'{k}={v}' for k, v in params)})" if params else "") + \
                      ("@" + ",".join(nodes) if nodes else "")
                try:
                    label = value(self.label, be) if self.label else (nodes[0] if nodes else self.title)
                    group = value(self.group, be)
                except Exception as ex:                     # a label must never stop a match
                    label, group = f"{self.id} ({ex})", self.title
                out.append(Site(self.id, params, tuple(sorted(binding.items())), key, str(label), str(group),
                                nodes, tuple(sorted(binding[v] for v in touched if v in binding))))
        return out

    # -- applying ------------------------------------------------------------
    def apply(self, state, site, env, pos_of=None):
        """Execute the right-hand side at the site. Returns the ids of nodes created."""
        e = {**env, **dict(site.params)}
        names = {v: n for v, n in site.binding}                      # var -> node id, grows as nodes are made
        rhs = expand(self.spec.get("rhs") or {}, {**e, **{v: Ns(state.node(n)) for v, n in names.items()}})

        # the matched nodes as the rule saw them: evaluated before anything is deleted or relabelled
        seen = {v: Ns(state.node(n)) for v, n in names.items()}

        def ns():
            return {**e, **seen, **{v: Ns({"id": n}) for v, n in names.items() if v not in seen}}

        def attrs(spec, ex):
            out = {}
            for k, v in (spec or {}).items():
                if k == "pos":
                    continue
                out[k] = value(v, ex)
            return out

        created = []
        for var in rhs.get("delete") or []:
            state.remove(names.pop(var))
        if rhs.get("contract"):
            c = rhs["contract"]
            into = c["into"]
            spec = (rhs.get("create") or {}).get(into) or {}
            ex = ns()
            a = attrs(spec, ex)
            new_id = a.pop("id", None) or into
            pos = value(spec["pos"], ex) if "pos" in spec else None
            members = value(c["nodes"], ex)
            state.contract([names[v] for v in members if v in names], new_id, pos=pos, **a)
            for v in members:
                names.pop(v, None)
            names[into] = new_id
            created.append(new_id)
        for var, spec in (rhs.get("create") or {}).items():
            if rhs.get("contract") and var == rhs["contract"]["into"]:
                continue
            ex = ns()
            a = attrs(spec, ex)
            new_id = a.pop("id", None) or var
            pos = value(spec["pos"], ex) if "pos" in spec else (0.0, 0.0, 0.0)
            state.add(new_id, pos, **a)
            names[var] = new_id
            created.append(new_id)
        for var, spec in (rhs.get("relabel") or {}).items():
            ex = ns()
            a = attrs(spec, ex)
            new_id = a.pop("id", None)
            state.update(names[var], **a)
            if new_id and new_id != names[var]:
                state.rename(names[var], new_id)
                names[var] = new_id
        for a, b in rhs.get("unlink") or []:
            state.unlink(names[a], names[b])
        for item in rhs.get("link") or []:
            a, b, rel = item[0], item[1], item[2]
            props = attrs(item[3], ns()) if len(item) > 3 and isinstance(item[3], dict) else {}
            state.link(names[a], names[b], rel, **props)
        for a, b, props in rhs.get("set_edge") or []:
            state.update_edge(names[a], names[b], **attrs(props, ns()))
        for f in rhs.get("flag") or []:
            state.flags.add(f)
        if pos_of is not None:
            for nid in created:
                p = pos_of(nid)
                if p is not None:
                    state.update(nid, pos=p)
        return created

    # -- for the viewer --------------------------------------------------------
    def card(self, env, params=None):
        """The rule drawn: LHS nodes and edges, NACs, RHS effects, for one parameter set."""
        params = params or (self.param_sets(env)[0] if self.params else ())
        lhs, nacs = self.patterns(params, env)
        e = {**env, **dict(params)}
        rhs = expand(self.spec.get("rhs") or {}, e)
        if rhs.get("contract") and isinstance(rhs["contract"].get("nodes"), str):
            rhs["contract"]["nodes"] = value(rhs["contract"]["nodes"], e)
        show = lambda c: {k: (repr(v) if isinstance(v, Expr) else v) for k, v in c.items()}
        return dict(id=self.id, params=dict(params),
                    lhs=dict(nodes={v: show(c) for v, c in lhs.nodes.items()},
                             edges=[list(x) for x in lhs.edges], where=[w.src for w in lhs.where],
                             flags=lhs.flags),
                    nac=[dict(nodes={v: show(c) for v, c in n.nodes.items()}, edges=[list(x) for x in n.edges],
                              where=[w.src for w in n.where], flags=n.flags) for n in nacs],
                    rhs=rhs, touched=sorted(self.touched_vars(params, env)))


def describe(rule):
    return dict(id=rule.id, title=rule.title, verb=rule.verb, grammar=rule.grammar, description=rule.description,
                symbols=list(rule.symbols), shape=rule.shape, auto=rule.auto, identity=rule.identity,
                params={k: (v if isinstance(v, list) else str(v)) for k, v in rule.params.items()},
                hash=rule.hash())
