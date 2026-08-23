"""
Crops each cigarette pack's artwork out of the shared atlas, upscales it, and
writes a per-brand texture plus the UV mapping needed to put it on a pack of
different proportions.

    python bake_pack_textures.py --assets ./out --scale 4

Reads   <assets>/textures/scrap_d.png
        <assets>/meshes/<Brand>.obj
Writes  <assets>/textures/<Brand>_albedo.png
        <assets>/pack_uvs.json

BSG's pack meshes are barter props that never reach the player's hands, so
their proportions do not matter and are not copied. Only the artwork is taken,
along with enough information about how it was laid out - which way each face
points, and which way is up on it - to reapply it to a correctly proportioned
pack.

Requires Pillow.
"""

import argparse
import json
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is not installed. pip install Pillow")

BRANDS = ("ApolloSoyuz", "Malboro", "Strike", "Wilston")

FACE_NAMES = {
    (0, -1, 0): "front",
    (0, 1, 0): "back",
    (-1, 0, 0): "left",
    (1, 0, 0): "right",
    (0, 0, 1): "top",
    (0, 0, -1): "bottom",
}

# For each face, which local axis runs across the artwork and which runs up it.
# Side faces stand up in Z; the lid and base lie flat and run in Y.
FACE_AXES = {
    "front":  (0, 2),
    "back":   (0, 2),
    "left":   (1, 2),
    "right":  (1, 2),
    "top":    (0, 1),
    "bottom": (0, 1),
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
                tri.append((int(bits[0]) - 1,
                            int(bits[1]) - 1 if len(bits) > 1 and bits[1] else None))
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
    axis = max(range(3), key=lambda i: abs(normal[i]))
    out = [0, 0, 0]
    out[axis] = 1 if normal[axis] > 0 else -1
    return tuple(out)


def analyse(path):
    """Per face: its UV rect, and whether u and v run with or against the local
    axes. The flips are what stop the artwork arriving mirrored or upside down
    once it is reapplied to a different box."""
    verts, uvs, faces = load_obj(path)

    # BSG authored these with -Z as up. Do NOT mirror the vertices to correct
    # that: mirroring reverses handedness, which silently inverts the u/v flip
    # detection below. Instead leave the geometry alone, compute normals in
    # BSG's own space, and account for the flip in two narrow places - naming
    # the face, and sampling the vertical position.
    samples = {}
    for tri in faces:
        n = snap(normal_of(verts, tri))
        name = FACE_NAMES.get((n[0], n[1], -n[2]))
        if not name:
            continue
        for vi, ti in tri:
            if ti is None:
                continue
            x, y, z = verts[vi]
            samples.setdefault(name, []).append(((x, y, -z), uvs[ti]))

    def covariance(xs, ys):
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n

    out = {}
    for name, pairs in samples.items():
        a1, a2 = FACE_AXES[name]
        us = [uv[0] for _, uv in pairs]
        vs = [uv[1] for _, uv in pairs]
        p1 = [p[a1] for p, _ in pairs]
        p2 = [p[a2] for p, _ in pairs]

        # Do NOT assume u runs along the horizontal axis. A face can be rotated
        # 90 degrees in the atlas, in which case u is driven by the vertical
        # axis instead. Pick whichever axis u actually covaries with, and give
        # v the other one. Assuming here is what mirrored the Apollo front.
        cu1, cu2 = covariance(p1, us), covariance(p2, us)
        if abs(cu1) >= abs(cu2):
            ax_u, ax_v = a1, a2
            u_sign, v_sign = cu1, covariance(p2, vs)
        else:
            ax_u, ax_v = a2, a1
            u_sign, v_sign = cu2, covariance(p1, vs)

        # u_flip is stored INVERTED on purpose. BSG's horizontal axis runs
        # opposite to the generated box's, so a face that needs no flip in
        # BSG's own frame needs one in ours. Established by rendering it both
        # ways; reasoning about the handedness got it wrong twice.
        out[name] = {
            "uv": [min(us), min(vs), max(us), max(vs)],
            "u_axis": ax_u,
            "v_axis": ax_v,
            "u_flip": bool(u_sign >= 0),
            "v_flip": bool(v_sign < 0),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default="out")
    ap.add_argument("--scale", type=int, default=4, help="upscale factor")
    ap.add_argument("--pad", type=int, default=2, help="pixels trimmed inward, to avoid atlas bleed")
    args = ap.parse_args()

    atlas_path = os.path.join(args.assets, "textures", "scrap_d.png")
    if not os.path.isfile(atlas_path):
        sys.exit("missing atlas: %s" % atlas_path)
    atlas = Image.open(atlas_path).convert("RGBA")
    AW, AH = atlas.size

    mapping = {}

    for brand in BRANDS:
        obj_path = os.path.join(args.assets, "meshes", "%s.obj" % brand)
        if not os.path.isfile(obj_path):
            print("missing mesh: %s" % obj_path)
            continue

        faces = analyse(obj_path)

        # Crop to everything this pack uses, so one texture holds one pack.
        u0 = min(f["uv"][0] for f in faces.values())
        v0 = min(f["uv"][1] for f in faces.values())
        u1 = max(f["uv"][2] for f in faces.values())
        v1 = max(f["uv"][3] for f in faces.values())

        # UV v runs bottom-up, image rows run top-down.
        px0 = int(round(u0 * AW)) + args.pad
        px1 = int(round(u1 * AW)) - args.pad
        py0 = int(round((1.0 - v1) * AH)) + args.pad
        py1 = int(round((1.0 - v0) * AH)) - args.pad
        crop = atlas.crop((px0, py0, px1, py1))

        # LANCZOS keeps the lettering legible; NEAREST would just make the
        # existing pixels bigger and BILINEAR would smear them.
        big = crop.resize((crop.width * args.scale, crop.height * args.scale), Image.LANCZOS)
        out_path = os.path.join(args.assets, "textures", "%s_albedo.png" % brand)
        big.save(out_path)

        # Rebase every face rect into the cropped image's own 0..1 space.
        cu0 = (px0) / AW
        cu1 = (px1) / AW
        cv0 = 1.0 - (py1 / AH)
        cv1 = 1.0 - (py0 / AH)
        rebased = {}
        for name, f in faces.items():
            fu0, fv0, fu1, fv1 = f["uv"]
            rebased[name] = {
                "uv": [
                    (fu0 - cu0) / (cu1 - cu0),
                    (fv0 - cv0) / (cv1 - cv0),
                    (fu1 - cu0) / (cu1 - cu0),
                    (fv1 - cv0) / (cv1 - cv0),
                ],
                "u_axis": f["u_axis"],
                "v_axis": f["v_axis"],
                "u_flip": f["u_flip"],
                "v_flip": f["v_flip"],
            }
        mapping[brand] = {"texture": os.path.basename(out_path), "faces": rebased}

        print("%-12s crop %4dx%-4d -> %5dx%-5d  (%s)" %
              (brand, crop.width, crop.height, big.width, big.height, os.path.basename(out_path)))
        for name in ("front", "back", "left", "right", "top", "bottom"):
            if name in faces:
                fu0, fv0, fu1, fv1 = faces[name]["uv"]
                print("               %-7s source %3.0fx%-3.0f px   u_flip=%-5s v_flip=%s"
                      % (name, (fu1 - fu0) * AW, (fv1 - fv0) * AH,
                         faces[name]["u_flip"], faces[name]["v_flip"]))

    json_path = os.path.join(args.assets, "pack_uvs.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2)
    print("")
    print("mapping written to %s" % json_path)


if __name__ == "__main__":
    main()
