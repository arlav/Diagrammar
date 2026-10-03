import importlib

import pytest

SUBPACKAGES = ["elements", "axiom", "shape", "provenance", "graph", "realise", "search", "registry",
               "interop", "scene"]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    assert importlib.import_module(f"topogrammar.{name}").__doc__
