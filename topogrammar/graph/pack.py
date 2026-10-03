"""
pack.py -- a rule pack, and a pack as a transformation of another
=================================================================
A pack is a directory with `pack.yaml`:

    title, version, model
    extends:      another pack this one transforms (Knight 1983: rules added, removed, changed)
    dimensions:   the numbers the rules may use as D.*
    parameters:   the numbers a derivation starts from, as P.*
    relations:    rel -> access
    occupiable, nonterminals, source
    modules:      helpers (functions for expressions), interpret (graph -> cells)
    rules:        files or inline rule specs; with `extends`, also `remove: [ids]`
    strategies:   files, each a recorded pathway

The hash of a pack covers its rules and dimensions, so a transformed pack carries the hash of the
pack it came from and its own. That is the brief's axis E3.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import yaml

from .rules import Rule


class Pack:
    def __init__(self, path):
        self.path = Path(path)
        self.data = yaml.safe_load((self.path / "pack.yaml").read_text())
        self.base = Pack(self.path / self.data["extends"]) if self.data.get("extends") else None
        inherit = lambda key, default: dict(self.base.data.get(key, default)) if self.base else dict(default)
        self.title = self.data["title"]
        self.version = self.data["version"]
        self.model = self.data.get("model", self.base.model if self.base else "")
        self.dimensions = {**inherit("dimensions", {}), **(self.data.get("dimensions") or {})}
        self.parameters = {**inherit("parameters", {}), **(self.data.get("parameters") or {})}
        self.parameter_notes = {**inherit("parameter_notes", {}), **(self.data.get("parameter_notes") or {})}
        self.constants = {**inherit("constants", {}), **(self.data.get("constants") or {})}
        self.relations = {**inherit("relations", {}), **(self.data.get("relations") or {})}
        for key in ("occupiable", "nonterminals", "source"):
            setattr(self, key, self.data.get(key, getattr(self.base, key) if self.base else None))
        self.modules = {}
        if self.base:
            self.modules.update(self.base.modules)
        for name, file in (self.data.get("modules") or {}).items():
            self.modules[name] = self._load(file)
        # presets and strategies are not inherited: a transformed grammar has its own buildings
        self.presets = dict(self.data.get("presets") or {})

        # rules: the base's, minus `remove`, with this pack's replacing or adding by id
        rules = dict(self.base.rules) if self.base else {}
        removed = set(self.data.get("remove") or [])
        rules = {k: v for k, v in rules.items() if k not in removed}
        own = {}
        for item in self.data.get("rules") or []:
            specs = yaml.safe_load((self.path / item).read_text()) if isinstance(item, str) else [item]
            for spec in specs:
                own[spec["id"]] = Rule(spec, source=str(item) if isinstance(item, str) else None)
        self.changed = sorted(k for k in own if k in rules and rules[k].hash() != own[k].hash())
        self.added = sorted(k for k in own if k not in rules)
        self.removed = sorted(removed)
        rules.update(own)
        self.rules = rules
        self.by_id = rules
        self.strategies = {}
        for file in self.data.get("strategies") or []:
            s = yaml.safe_load((self.path / file).read_text())
            self.strategies[s["id"]] = s

    def _load(self, file):
        spec = importlib.util.spec_from_file_location(f"{self.path.name}_{Path(file).stem}", self.path / file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # -- environment for expressions ----------------------------------------
    def env(self, P):
        from .patterns import Ns
        helpers = self.modules.get("helpers")
        out = {name: getattr(helpers, name) for name in getattr(helpers, "__all__", [])} if helpers else {}
        out.update(P=Ns(P), D=Ns(self.dimensions), C=Ns(self.constants))
        return out

    def params(self, preset=None, **over):
        P = dict(self.parameters)
        if preset is not None:
            P.update(self.presets[preset].get("parameters") or {})
        P.update(over)
        return P

    # -- identity -------------------------------------------------------------
    def hash(self):
        canon = json.dumps(dict(rules={k: r.hash() for k, r in self.rules.items()},
                                dimensions=self.dimensions, constants=self.constants), sort_keys=True)
        return hashlib.sha256(canon.encode()).hexdigest()[:16]

    def lineage(self):
        """This pack and what it was transformed from."""
        out = [dict(title=self.title, version=self.version, hash=self.hash(), path=str(self.path))]
        return (self.base.lineage() if self.base else []) + out

    def diff(self):
        """What this pack changed in the one it extends."""
        if not self.base:
            return None
        return dict(base=self.base.title, base_hash=self.base.hash(), added=self.added, removed=self.removed,
                    changed=self.changed,
                    dimensions={k: (self.base.dimensions.get(k), v) for k, v in self.dimensions.items()
                                if self.base.dimensions.get(k) != v},
                    parameters={k: (self.base.parameters.get(k), v) for k, v in self.parameters.items()
                                if self.base.parameters.get(k) != v})

    def golden(self, preset):
        file = self.presets.get(preset, {}).get("golden")
        if not file:
            return None
        root = self.path if (self.path / file).exists() else (self.base.path if self.base else self.path)
        return json.loads((root / file).read_text())
