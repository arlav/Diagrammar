"""
mesh.py -- prisms as triangles
==============================
A cell reaches the viewer as flat-shaded triangles plus the edges of its outline. Vertices are not
shared between faces, so a viewer that averages normals still draws every face flat.

    axis "z"   profile in (x, y), extruded along z
    axis "x"   profile in (y, z), extruded along x
    axis "y"   profile in (x, z), extruded along y
"""

_PLACE = {"z": lambda u, v, a: (u, v, a), "x": lambda u, v, a: (a, u, v), "y": lambda u, v, a: (u, a, v)}


def area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def _inside(p, a, b, c):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return side(a, b, p) >= 0 and side(b, c, p) >= 0 and side(c, a, p) >= 0


def triangulate(poly):
    """Ear clipping of a simple polygon given counter-clockwise. Returns index triples."""
    idx = list(range(len(poly)))
    out = []
    while len(idx) > 3:
        for k in range(len(idx)):
            i, j, l = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i], poly[j], poly[l]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:                           # reflex or degenerate corner: not an ear
                continue
            if any(_inside(poly[m], a, b, c) for m in idx if m not in (i, j, l)):
                continue
            out.append((i, j, l))
            idx.pop(k)
            break
        else:                                            # only slivers left
            idx.pop(0)
    if len(idx) == 3:
        out.append(tuple(idx))
    return out


def prism(profile, axis, a0, a1):
    """dict(positions, indices, lines, centroid, bounds, volume) for a closed profile extruded along an axis."""
    poly = [tuple(map(float, p)) for p in profile]
    # drop repeated points (a one-level section has a zero-height step)
    poly = [p for i, p in enumerate(poly) if abs(p[0] - poly[i - 1][0]) + abs(p[1] - poly[i - 1][1]) > 1e-9]
    if area(poly) < 0:
        poly = poly[::-1]
    a0, a1 = sorted((float(a0), float(a1)))
    place = _PLACE[axis]
    flip = axis == "y"                                   # the one placement that mirrors
    positions, indices, lines = [], [], []

    def face(points, triangles):
        base = len(positions) // 3
        for p in points:
            positions.extend(round(c, 4) for c in p)
        for t in triangles:
            indices.extend(base + i for i in (t[::-1] if flip else t))

    caps = triangulate(poly)
    face([place(u, v, a0) for u, v in poly], [t[::-1] for t in caps])
    face([place(u, v, a1) for u, v in poly], caps)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        face([place(*poly[i], a0), place(*poly[j], a0), place(*poly[j], a1), place(*poly[i], a1)],
             [(0, 1, 2), (0, 2, 3)])
        for p, q in ((place(*poly[i], a0), place(*poly[j], a0)), (place(*poly[i], a1), place(*poly[j], a1)),
                     (place(*poly[i], a0), place(*poly[i], a1))):
            lines.extend(round(c, 4) for c in p + q)

    corners = [place(u, v, a) for u, v in poly for a in (a0, a1)]
    lo = [min(c[k] for c in corners) for k in range(3)]
    hi = [max(c[k] for c in corners) for k in range(3)]
    # centroid of the profile, so an L or a U is labelled inside its own section
    cu = sum((poly[i][0] + poly[(i + 1) % n][0]) * (poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1])
             for i in range(n)) / (6 * area(poly))
    cv = sum((poly[i][1] + poly[(i + 1) % n][1]) * (poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1])
             for i in range(n)) / (6 * area(poly))
    return dict(positions=positions, indices=indices, lines=lines,
                centroid=[round(c, 3) for c in place(cu, cv, (a0 + a1) / 2)],
                bounds=[[round(c, 3) for c in lo], [round(c, 3) for c in hi]],
                volume=round(area(poly) * (a1 - a0), 2))
