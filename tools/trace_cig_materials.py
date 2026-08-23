"""
Traces what the cigarette bundles reference externally, to find where their
materials and textures actually live.

    python trace_cig_materials.py --game "H:/SPT4.1.X"

The bundles hold meshes but no textures, so each MeshRenderer points at a
material in another file. Unity records those targets in the serialized file's
externals table; this prints them.
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


def externals_of(env):
    """Every serialized file inside the bundle lists the other files it refers
    to. That table is where an out-of-bundle material shows up."""
    found = []
    for name, sfile in getattr(env, "files", {}).items():
        for ext in getattr(sfile, "externals", []) or []:
            path = getattr(ext, "path", None) or getattr(ext, "pathName", "")
            if path:
                found.append(path)
    return found


def renderer_materials(env):
    """Read each MeshRenderer's material pointers. A file_id of 0 means the
    material is in this same file; anything else indexes the externals table."""
    rows = []
    for obj in env.objects:
        if obj.type.name != "MeshRenderer":
            continue
        try:
            data = obj.read()
        except Exception as exc:
            rows.append(("<unreadable MeshRenderer>", str(exc)))
            continue
        mats = getattr(data, "m_Materials", None) or []
        for ptr in mats:
            file_id = getattr(ptr, "file_id", "?")
            path_id = getattr(ptr, "path_id", "?")
            resolved = "<unresolved>"
            try:
                mat = ptr.read()
                resolved = getattr(mat, "m_Name", None) or "<unnamed material>"
            except Exception:
                pass
            rows.append(("file_id=%s path_id=%s" % (file_id, path_id), resolved))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    args = ap.parse_args()

    bundle_dir = os.path.join(args.game, *BUNDLE_DIR.split("/"))
    if not os.path.isdir(bundle_dir):
        sys.exit("not found: %s" % bundle_dir)

    all_externals = set()

    for filename, brand in sorted(BRANDS.items(), key=lambda kv: kv[1]):
        path = os.path.join(bundle_dir, filename)
        if not os.path.isfile(path):
            continue
        env = UnityPy.load(path)

        print("")
        print("=" * 72)
        print(brand)
        print("=" * 72)

        exts = externals_of(env)
        if exts:
            print("  externals:")
            for e in exts:
                print("    %s" % e)
                all_externals.add(e)
        else:
            print("  externals: none recorded")

        rows = renderer_materials(env)
        if rows:
            print("  material pointers:")
            for ref, name in rows:
                print("    %-34s -> %s" % (ref, name))
        else:
            print("  material pointers: none")

    print("")
    print("=" * 72)
    print("distinct external files referenced:")
    for e in sorted(all_externals):
        print("  %s" % e)
    if not all_externals:
        print("  (none - materials may be resolved by the game at runtime")
        print("   rather than through a recorded dependency)")
    print("=" * 72)


if __name__ == "__main__":
    main()
