"""Functions the rules may call in their expressions."""

__all__ = ["kind", "tag"]


def kind(k, ci):
    """The section a dwelling of k levels gets when its street pierces level ci."""
    if k < 2:
        return "flat"
    if ci == 0:
        return "L"
    if ci == k - 1:
        return "Gamma"
    return "U" if k == 3 else "Z"


def tag(k, ci):
    """The Narkomfin letter for a section: K, F, G, Z, E, or k.ci for one it never had."""
    return {(2, 0): "K", (3, 1): "F", (2, 1): "G", (4, 1): "Z", (1, 0): "E"}.get((k, ci), f"C{k}{ci}")
