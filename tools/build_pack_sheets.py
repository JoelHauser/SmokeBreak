"""
Builds a per-brand texture sheet from the hand-supplied pack artwork, and the
UV mapping that goes with it.

    python build_pack_sheets.py --src "./out/upscaled textures" --assets ./out

The supplied images are photographs and dielines rather than UV unwraps, so the
panels are cropped out by rectangle and reassembled into a fixed layout the
generator can map onto:

      +------------------+--------+
      |      front       |  side  |     row 1, pack height
      +------------------+--------+
      |       top        | bottom |     row 2, pack depth
      +------------------+--------+

Front is reused for the back and side for both sides. Real packs are close to
symmetrical, and in first person the back is never seen.

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


# Pack proportions, in millimetres, matching the generator.
PACK_W, PACK_H, PACK_D = 55, 85, 22
PX_PER_MM = 8

# Panel rectangles picked by eye from the supplied images, then checked by
# cropping them out and looking at the result.
SOURCES = {
    "ApolloSoyuz": {
        "file": "APOLLO.png",
        "front": (686, 240, 1237, 1050),
        "top": (700, 95, 1245, 240),
        # These packs are photographed from above, so no side panel is visible.
        # Sampled from the front's plain card instead, which is what that side
        # actually looks like.
        "side_from_front": (60, 620, 130, 780),
    },
    "Malboro": {
        "file": "MALBRO.png",
        "front": (928, 190, 1446, 898),
        "side": (731, 200, 833, 898),
        "top": (232, 8, 700, 190),
    },
    "Strike": {
        "file": "STRIKE.png",
        "front": (316, 250, 766, 962),
        "side": (100, 250, 290, 962),
        "side_from_front": None,
    },
    "Wilston": {
        "file": "WINSTON.png",
        "front": (195, 205, 675, 925),
        "side": (683, 205, 833, 925),
        "top": None,
    },
}


def cell_sizes():
    front_w = PACK_W * PX_PER_MM
    front_h = PACK_H * PX_PER_MM
    side_w = PACK_D * PX_PER_MM
    top_h = PACK_D * PX_PER_MM
    return front_w, front_h, side_w, top_h


def average_colour(image, box=None):
    region = image.crop(box) if box else image
    small = region.resize((1, 1), Image.LANCZOS)
    return small.getpixel((0, 0))


def build_sheet(image, spec):
    front_w, front_h, side_w, top_h = cell_sizes()
    sheet_w = front_w + side_w
    sheet_h = front_h + top_h

    front = image.crop(spec["front"]).resize((front_w, front_h), Image.LANCZOS)

    if spec.get("side"):
        side = image.crop(spec["side"]).resize((side_w, front_h), Image.LANCZOS)
    else:
        # No side panel in the source. Stretch a strip of the front's plain card
        # so the side at least matches the pack's own colour and grain.
        strip_box = spec.get("side_from_front") or (0, 0, 40, 120)
        strip = front.crop(strip_box) if max(strip_box) < max(front.size) else front.crop((0, 0, 40, 120))
        side = strip.resize((side_w, front_h), Image.LANCZOS)

    if spec.get("top"):
        top = image.crop(spec["top"]).resize((front_w, top_h), Image.LANCZOS)
    else:
        top = Image.new("RGB", (front_w, top_h), average_colour(front, (0, 0, front_w, top_h)))

    bottom = Image.new("RGB", (side_w, top_h), average_colour(front, (0, front_h - top_h, front_w, front_h)))

    sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
    sheet.paste(front, (0, 0))
    sheet.paste(side, (front_w, 0))
    sheet.paste(top, (0, front_h))
    sheet.paste(bottom, (front_w, front_h))
    return sheet


def uv_mapping():
    """UV rects for the fixed layout above. Image rows run top-down and UV v
    runs bottom-up, so row 0 is v=1."""
    front_w, front_h, side_w, top_h = cell_sizes()
    sheet_w = front_w + side_w
    sheet_h = front_h + top_h

    def rect(x0, y0, x1, y1):
        return [x0 / sheet_w, 1.0 - y1 / sheet_h, x1 / sheet_w, 1.0 - y0 / sheet_h]

    front_rect = rect(0, 0, front_w, front_h)
    side_rect = rect(front_w, 0, sheet_w, front_h)
    top_rect = rect(0, front_h, front_w, sheet_h)
    bottom_rect = rect(front_w, front_h, sheet_w, sheet_h)

    # u_flip on the back and one side so the artwork wraps rather than
    # mirroring as it turns the corner.
    return {
        "front":  {"uv": front_rect,  "u_axis": 0, "v_axis": 2, "u_flip": False, "v_flip": False},
        "back":   {"uv": front_rect,  "u_axis": 0, "v_axis": 2, "u_flip": True,  "v_flip": False},
        "left":   {"uv": side_rect,   "u_axis": 1, "v_axis": 2, "u_flip": False, "v_flip": False},
        "right":  {"uv": side_rect,   "u_axis": 1, "v_axis": 2, "u_flip": True,  "v_flip": False},
        "top":    {"uv": top_rect,    "u_axis": 0, "v_axis": 1, "u_flip": False, "v_flip": False},
        "bottom": {"uv": bottom_rect, "u_axis": 0, "v_axis": 1, "u_flip": False, "v_flip": False},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="folder holding the supplied artwork")
    ap.add_argument("--assets", default="out")
    args = ap.parse_args()

    tex_dir = os.path.join(args.assets, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    mapping = {}
    faces = uv_mapping()

    for brand, spec in SOURCES.items():
        path = os.path.join(args.src, spec["file"])
        if not os.path.isfile(path):
            print("missing source: %s" % path)
            continue
        image = Image.open(path).convert("RGB")
        sheet = build_sheet(image, spec)
        out_name = "%s_sheet.png" % brand
        sheet.save(os.path.join(tex_dir, out_name))
        mapping[brand] = {"texture": out_name, "faces": faces}
        print("%-12s %-14s -> %s  (%dx%d)" %
              (brand, spec["file"], out_name, sheet.width, sheet.height))

    json_path = os.path.join(args.assets, "pack_uvs.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2)
    print("")
    print("mapping written to %s" % json_path)


if __name__ == "__main__":
    main()
