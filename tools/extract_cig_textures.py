"""
Pulls the cigarette pack textures out of EFT's asset bundles.

    python extract_cig_textures.py --game "H:/SPT4.1.X" --out ./out/textures

The four barter bundles are only ~26 KB each, which is nowhere near enough for
albedo maps, so they almost certainly reference textures held elsewhere. This
script reports exactly what each bundle contains before trying to save
anything, so the next step is based on what is actually there rather than a
guess.

Requires UnityPy.
"""

import argparse
import os
import sys

try:
    import UnityPy
except ImportError:
    sys.exit("UnityPy is not installed. pip install UnityPy")


BUNDLE_DIR = "EscapeFromTarkov_Data/StreamingAssets/Windows/assets/content/items/barter/cigarettes"

BRANDS = {
    "item_cigarettes_soyuz_apollo.bundle": "ApolloSoyuz",
    "item_cigarettes_malboro.bundle": "Malboro",
    "item_cigarettes_strike.bundle": "Strike",
    "item_cigarettes_wilston.bundle": "Wilston",
}


def describe(env, label):
    """List every object in a bundle by type, so we can see whether textures
    are present or merely referenced."""
    counts = {}
    details = []
    for obj in env.objects:
        counts[obj.type.name] = counts.get(obj.type.name, 0) + 1
        if obj.type.name in ("Texture2D", "Material", "Mesh", "Shader"):
            try:
                data = obj.read()
                name = getattr(data, "m_Name", None) or getattr(data, "name", "<unnamed>")
                extra = ""
                if obj.type.name == "Texture2D":
                    w = getattr(data, "m_Width", "?")
                    h = getattr(data, "m_Height", "?")
                    fmt = getattr(data, "m_TextureFormat", "?")
                    extra = "  %sx%s  %s" % (w, h, fmt)
                details.append((obj.type.name, name, extra))
            except Exception as exc:
                details.append((obj.type.name, "<unreadable: %s>" % exc, ""))

    print("")
    print("=" * 70)
    print("%s" % label)
    print("=" * 70)
    print("  object types: %s" % ", ".join("%s x%d" % kv for kv in sorted(counts.items())))
    for kind, name, extra in details:
        print("    %-10s %s%s" % (kind, name, extra))
    return counts, details


def save_textures(env, out_dir, prefix):
    saved = []
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        try:
            data = obj.read()
            name = getattr(data, "m_Name", None) or "texture"
            image = data.image
            if image is None:
                continue
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, "%s_%s.png" % (prefix, name))
            image.save(path)
            saved.append((path, image.size))
        except Exception as exc:
            print("    could not save a Texture2D: %s" % exc)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, help="SPT / EFT install root")
    ap.add_argument("--out", default="out/textures")
    args = ap.parse_args()

    bundle_dir = os.path.join(args.game, *BUNDLE_DIR.split("/"))
    if not os.path.isdir(bundle_dir):
        sys.exit("cigarette bundle folder not found: %s" % bundle_dir)

    total_saved = 0
    for filename, brand in BRANDS.items():
        path = os.path.join(bundle_dir, filename)
        if not os.path.isfile(path):
            print("missing: %s" % path)
            continue
        env = UnityPy.load(path)
        describe(env, "%s  (%s, %s bytes)" % (brand, filename, os.path.getsize(path)))
        saved = save_textures(env, args.out, brand)
        for p, size in saved:
            print("    saved %s  %sx%s" % (os.path.basename(p), size[0], size[1]))
        total_saved += len(saved)

    print("")
    print("=" * 70)
    print("textures saved: %d" % total_saved)
    if total_saved == 0:
        print("None embedded. The bundles reference textures held elsewhere,")
        print("so the next step is finding the bundle that owns them.")
    print("=" * 70)


if __name__ == "__main__":
    main()
