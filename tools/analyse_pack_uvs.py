"""
Works out how BSG lays each pack face out in the shared atlas.

    python analyse_pack_uvs.py --meshes ./out/meshes

Reads the exported OBJs, groups triangles into box faces by normal, and reports
each face's UV rectangle. That mapping is what lets the same artwork be placed
onto a differently proportioned pack: the faces are matched by which way they
point, not by vertex order.
"""

import argparse
import os
import json

BRANDS = ("ApolloSoyuz", "Malboro", "Strike", "Wilston")

# Which way a face points -> what it is on a standing pack.
FACE_NAMES = {
    (0, -1, 0): "front",
    (0, 1, 0): "back",
    (-1, 0, 0): "left",
    (1, 0, 0): "right",
    (0, 0, 1): "top",
    (0, 0, -1): "bottom",
}


def load_obj(path):
    verts, uvs, faces = [], [], []
    for line in open(path, encoding="utf-8"):
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            verts.append(tuple(float(x) for x in parts[1:4]))
        elif parts[0] == "vt":
            uvs.append(tuple(float(x) for x in parts[1:3]))
        elif parts[0] == "f":
            tri = []
            for token in parts[1:]:
                bits = token.split("/")
                vi = int(bits[0]) - 1
                ti = int(bits[1]) - 1 if len(bits) > 1 and bits[1] else None
                tri.append((vi, ti))
            faces.append(tri)
    return verts, uvs, faces


def normal_of(verts, tri):
    a, b, c = (verts[i] for i, _ in tri[:3])
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    n = (u[1] * v[2] - u[2] * v[1],
         u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0])
    length = sum(x * x for x in n) ** 0.5 or 1.0
    return tuple(x / length for x in n)


def snap(normal):
    """Box faces are axis aligned, so round to the dominant axis."""
    best_axis = max(range(3), key=lambda i: abs(normal[i]))
    out = [0, 0, 0]
    out[best_axis] = 1 if normal[best_axis] > 0 else -1
    return tuple(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meshes", default="out/meshes")
    ap.add_argument("--json", default=None, help="write the mapping here")
    args = ap.parse_args()

    result = {}

    for brand in BRANDS:
        path = os.path.join(args.meshes, "%s.obj" % brand)
        if not os.path.isfile(path):
            print("missing %s" % path)
            continue
        verts, uvs, faces = load_obj(path)

        grouped = {}
        for tri in faces:
            key = snap(normal_of(verts, tri))
            us = [uvs[t][0] for _, t in tri if t is not None]
            vs = [uvs[t][1] for _, t in tri if t is not None]
            if not us:
                continue
            lo_u, hi_u = min(us), max(us)
            lo_v, hi_v = min(vs), max(vs)
            if key in grouped:
                p = grouped[key]
                grouped[key] = (min(p[0], lo_u), min(p[1], lo_v),
                                max(p[2], hi_u), max(p[3], hi_v))
            else:
                grouped[key] = (lo_u, lo_v, hi_u, hi_v)

        print("")
        print("=" * 74)
        print(brand)
        print("=" * 74)
        brand_map = {}
        for key, rect in sorted(grouped.items(), key=lambda kv: FACE_NAMES.get(kv[0], "?")):
            name = FACE_NAMES.get(key, str(key))
            u0, v0, u1, v1 = rect
            brand_map[name] = [u0, v0, u1, v1]
            print("  %-7s u %.4f..%.4f  v %.4f..%.4f   px %4.0f..%4.0f  %4.0f..%4.0f  (%.0fx%.0f)"
                  % (name, u0, u1, v0, v1,
                     u0 * 2048, u1 * 2048, (1 - v1) * 2048, (1 - v0) * 2048,
                     (u1 - u0) * 2048, (v1 - v0) * 2048))
        result[brand] = brand_map

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print("")
        print("mapping written to %s" % args.json)


if __name__ == "__main__":
    main()
