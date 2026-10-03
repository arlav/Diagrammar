"""
patterns.py -- the left-hand side of a rule, and how it is matched
==================================================================
A pattern is a small typed graph: variables standing for nodes, each with attribute constraints,
edges between them that must exist, and `where` predicates over the bound nodes. A rule's LHS is one
pattern; each of its NACs (negative application conditions) is a pattern that must NOT extend a match.

Patterns are written as data. Three kinds of value appear in them:

    "A"              a literal: the attribute must equal it
    "=b.level + 1"   an expression: the attribute must equal its value
    "L{s.level}"     a template (right-hand sides only): formatted with the bound nodes

Variables may be families, `b[j]` with `for: "j in range(k)"`, so one rule can stand for a run of k
nodes. Expressions are evaluated in a restricted Python: no imports, no attribute access to private
names, only the names of bound nodes, rule parameters, pack constants and a few builtins.
"""
import ast
import re
from dataclasses import dataclass, field

_BUILTINS = dict(abs=abs, min=min, max=max, range=range, len=len, round=round, int=int, float=float,
                 str=str, sorted=sorted, any=any, all=all, tuple=tuple, list=list, set=set, sum=sum,
                 enumerate=enumerate, zip=zip)
_ALLOWED = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name,
            ast.Constant, ast.Attribute, ast.Subscript, ast.Tuple, ast.List, ast.Dict, ast.Set,
            ast.IfExp, ast.ListComp, ast.GeneratorExp, ast.comprehension, ast.Slice, ast.Load, ast.Store,
            ast.And, ast.Or, ast.Not, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
            ast.Pow, ast.USub, ast.UAdd, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
            ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.JoinedStr, ast.FormattedValue)
_FAMILY = re.compile(r"\b([A-Za-z_]\w*)\[([^\[\]]+)\]")


class Ns:
    """A bound node, seen from an expression: `b.level`, `b.bay`. A missing key is None."""
    __slots__ = ("_d",)

    def __init__(self, d):
        object.__setattr__(self, "_d", d)

    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        return self._d.get(k)

    def __getitem__(self, k):
        return self._d.get(k)

    def __repr__(self):
        return f"Ns({self._d.get('id')})"


_EXPRS = {}


class Expr:
    """A compiled restricted expression. Compiling is cached by source text."""
    __slots__ = ("src", "code", "names")

    def __new__(cls, src):
        if src in _EXPRS:
            return _EXPRS[src]
        self = object.__new__(cls)
        self._init(src)
        _EXPRS[src] = self
        return self

    def _init(self, src):
        self.src = src
        tree = ast.parse(src, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED):
                raise ValueError(f"'{src}': {type(node).__name__} is not allowed in a rule expression")
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                raise ValueError(f"'{src}': private attributes are not allowed")
            if isinstance(node, ast.Name) and node.id.startswith("_"):
                raise ValueError(f"'{src}': private names are not allowed")
        self.code = compile(tree, f"<rule: {src}>", "eval")
        self.names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

    def __call__(self, env):
        # names go in globals, so that comprehensions (which have their own scope) can see them
        return eval(self.code, {"__builtins__": {}, **_BUILTINS, **env})

    def __repr__(self):
        return f"={self.src}"


def expand_names(text, env):
    """`b[j+1]` -> `b2` for j = 1: family references become plain names. A reference whose index
    cannot be evaluated yet (it names a node not bound at this point) is left as it is."""
    def sub(m):
        try:
            return m.group(1) + str(Expr(m.group(2))(env))
        except Exception:
            return m.group(0)
    return _FAMILY.sub(sub, text)


def _subst_loop(text, var, val):
    """A loop variable written into a string: `=expr` gets its value, `{j:02d}` is formatted."""
    if text.startswith("="):
        return re.sub(rf"(?<![\w.]){var}(?!\w)", repr(val), text)
    return re.sub(r"\{" + var + r"(:[^}]*)?\}", lambda m: format(val, (m.group(1) or ":")[1:]), text)


def value(spec, env):
    """A literal, an `=expression` or a `{template}` evaluated against the environment."""
    if isinstance(spec, str):
        if spec.startswith("="):
            return Expr(expand_names(spec[1:], env))(env)
        if "{" in spec:
            return spec.format(**env)
    return spec


def _loop(clause, env):
    """`"j in range(k)"` -> the bindings of j."""
    var, _, iterable = clause.partition(" in ")
    for v in Expr(expand_names(iterable.strip(), env))(env):
        yield {var.strip(): v}


def expand(spec, env, loop=None):
    """A pattern or effect spec with `for` clauses and family names, made concrete for one set of
    parameters. Works on nested dicts and lists; strings are name-expanded and loop variables are
    written in, but nothing is evaluated."""
    loop = loop or {}
    e = {**env, **loop}
    if isinstance(spec, dict):
        out = {}
        for key, val in spec.items():
            clause = val.get("for") if isinstance(val, dict) else None
            if clause:
                for binding in _loop(clause, e):
                    k = expand_names(key, {**e, **binding})
                    out[k] = expand({x: y for x, y in val.items() if x != "for"}, env, {**loop, **binding})
            else:
                out[expand_names(key, e) if isinstance(key, str) else key] = expand(val, env, loop)
        return out
    if isinstance(spec, list):
        out = []
        for item in spec:
            clause = None
            if isinstance(item, list) and item and isinstance(item[-1], dict) and "for" in item[-1]:
                clause, body = item[-1]["for"], item[:-1]
            elif isinstance(item, dict) and "for" in item:
                clause, body = item["for"], {x: y for x, y in item.items() if x != "for"}
            if clause:
                for binding in _loop(clause, e):
                    out.append(expand(body, env, {**loop, **binding}))
            else:
                out.append(expand(item, env, loop))
        return out
    if isinstance(spec, str):
        s = expand_names(spec, e) if "[" in spec else spec
        for var, val in loop.items():
            s = _subst_loop(s, var, val)
        return s
    return spec


@dataclass
class Pattern:
    """A concrete pattern: variables with constraints, edges, predicates."""
    nodes: dict                                  # var -> {attr: literal | Expr}
    edges: list = field(default_factory=list)    # (a, b, rel or None)
    where: list = field(default_factory=list)    # Expr
    flags: list = field(default_factory=list)    # derivation flags that must be set

    @classmethod
    def build(cls, spec, env):
        spec = expand(spec or {}, env)
        nodes = {}
        for var, cons in (spec.get("nodes") or {}).items():
            nodes[var] = {k: (Expr(v[1:]) if isinstance(v, str) and v.startswith("=") else v)
                          for k, v in (cons or {}).items()}
        edges = []
        for e in spec.get("edges") or []:
            a, b = e[0], e[1]
            rel = e[2] if len(e) > 2 and not isinstance(e[2], dict) else None
            edges.append((a, b, rel))
        where = [Expr(w) for w in spec.get("where") or []]
        return cls(nodes, edges, where, list(spec.get("flags") or []))

    @property
    def vars(self):
        return list(self.nodes)


class Snapshot:
    """One state, indexed for matching: attributes by id, ids by type, adjacency."""

    def __init__(self, state):
        self.nodes = state.nodes()
        self.by_type = {}
        for nid, d in self.nodes.items():
            self.by_type.setdefault(d.get("type"), []).append(nid)
        self.adj = {nid: {} for nid in self.nodes}
        for e in state.edges():
            d = {k: v for k, v in e.items() if k not in ("a", "b")}
            self.adj[e["a"]][e["b"]] = d
            self.adj[e["b"]][e["a"]] = d
        self.flags = set(state.flags)
        self.ns = {nid: Ns(d) for nid, d in self.nodes.items()}
        self._index = {}

    def edge(self, a, b):
        return self.adj.get(a, {}).get(b)

    def lookup(self, key, val):
        """The ids whose attribute `key` equals `val`; indexed on first use."""
        if key not in self._index:
            ix = {}
            for nid, d in self.nodes.items():
                v = d.get(key)
                if isinstance(v, (str, int, float, bool)) or v is None:
                    ix.setdefault(v, []).append(nid)
            self._index[key] = ix
        return self._index[key].get(val, [])


def _free(expr, pattern_vars):
    return expr.names & pattern_vars


def matches(pattern, snap, env, bound=None, first=False):
    """Every injective binding of the pattern's variables to nodes of the snapshot. `bound` fixes
    some variables beforehand (the way a NAC extends a match)."""
    if any(f not in snap.flags for f in pattern.flags):
        return
    bound = dict(bound or {})
    pvars = set(pattern.nodes)
    todo = [v for v in pattern.nodes if v not in bound]
    # evaluation order: a variable constrained by an edge to a bound one is cheap to enumerate
    base_env = dict(env)

    def env_of(b):
        e = dict(base_env)
        e.update({v: snap.ns[n] for v, n in b.items()})
        return e

    def ok_attrs(var, nid, b):
        cons = pattern.nodes[var]
        d = snap.nodes[nid]
        for k, c in cons.items():
            if isinstance(c, Expr):
                if not _free(c, pvars) <= set(b) | {var}:
                    continue                         # checked once its variables are bound
                if d.get(k) != c(env_of({**b, var: nid})):
                    return False
            elif d.get(k) != c:
                return False
        return True

    def ok_edges(var, nid, b):
        for a, c, rel in pattern.edges:
            if var not in (a, c):
                continue
            other = c if a == var else a
            if other == var:
                return False
            if other in b:
                e = snap.edge(nid, b[other])
                if e is None or (rel is not None and e.get("rel") != rel):
                    return False
        return True

    def ok_where(b, just_bound):
        e = env_of(b)
        for w in pattern.where:
            fv = _free(w, pvars)
            if just_bound in fv and fv <= set(b):
                if not w(e):
                    return False
        return True

    def ok_late(var, nid, b):
        """Expression constraints on earlier variables that only became checkable now."""
        for v in b:
            if v == var:
                continue
            for k, c in pattern.nodes[v].items():
                if isinstance(c, Expr) and var in _free(c, pvars) and _free(c, pvars) <= set(b):
                    if snap.nodes[b[v]].get(k) != c(env_of(b)):
                        return False
        return True

    def candidates(var, b):
        for a, c, rel in pattern.edges:
            if var in (a, c):
                other = c if a == var else a
                if other in b:
                    return [n for n, e in snap.adj[b[other]].items() if rel is None or e.get("rel") == rel]
        # the smallest index over the attributes whose required value is already known
        best = None
        e = None
        for k, c in pattern.nodes[var].items():
            if isinstance(c, Expr):
                if not _free(c, pvars) <= set(b):
                    continue
                e = e if e is not None else env_of(b)
                try:
                    want = c(e)
                except Exception:
                    continue
            else:
                want = c
            if isinstance(want, (str, int, float, bool)) or want is None:
                found = snap.lookup(k, want)
                if best is None or len(found) < len(best):
                    best = found
        if best is not None:
            return best
        return list(snap.nodes)

    def complete(b):
        env2 = env_of(b)
        for v, nid in b.items():
            d = snap.nodes.get(nid)
            if d is None:
                return False
            for k, c in pattern.nodes.get(v, {}).items():
                want = c(env2) if isinstance(c, Expr) else c
                if d.get(k) != want:
                    return False
        for a, c, rel in pattern.edges:
            e = snap.edge(b[a], b[c]) if a in b and c in b else None
            if e is None or (rel is not None and e.get("rel") != rel):
                return False
        return all(w(env2) for w in pattern.where if _free(w, pvars) <= set(b))

    def rec(i, b):
        if i == len(todo):
            if complete(b):
                yield dict(b)
            return
        var = todo[i]
        used = set(b.values())
        for nid in candidates(var, b):
            if nid in used:
                continue
            if not ok_attrs(var, nid, b) or not ok_edges(var, nid, b):
                continue
            nb = {**b, var: nid}
            if not ok_late(var, nid, nb) or not ok_where(nb, var):
                continue
            yield from rec(i + 1, nb)

    # fixed variables still have to satisfy the pattern (a NAC's shared variables are trusted)
    for b in rec(0, bound):
        yield b
        if first:
            return


def extends(nac, snap, env, binding):
    """Does the NAC pattern extend this binding anywhere? Shared variables are fixed."""
    shared = {v: n for v, n in binding.items() if v in nac.nodes}
    env2 = {**env, **{v: snap.ns[n] for v, n in binding.items()}}
    if not any(True for _ in matches(nac, snap, env2, bound=shared, first=True)):
        return False
    # a NAC with only shared variables and only flags or predicates: check them
    return True
