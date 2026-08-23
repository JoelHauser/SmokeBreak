"""
Exports EFT's character rig from skeleton.bundle as a hierarchy with local
transforms, ready to be rebuilt as a Blender armature.

    python extract_skeleton.py --game "H:/SPT4.1.X" --out ./out/skeleton.json

The bundle holds 79 bones, an Avatar and an Animator in 60 KB. Bones are plain
GameObjects with Transforms, so the rig is recovered by walking the Transform
parent/child links and recording each bone's local position, rotation and
scale.

Requires UnityPy.
"""

import argparse
import json
import os
import sys

try:
    import UnityPy
except ImportError:
    sys.exit("UnityPy is not installed. pip install UnityPy")

SKELETON = "EscapeFromTarkov_Data/StreamingAssets/Windows/assets/content/characters/character/skeleton.bundle"


def vec(v, keys):
    out = []
    for k in keys:
        val = getattr(v, k, None)
        out.append(float(val) if val is not None else 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", default="out/skeleton.json")
    args = ap.parse_args()

    path = os.path.join(args.game, *SKELETON.split("/"))
    if not os.path.isfile(path):
        sys.exit("not found: %s" % path)

    env = UnityPy.load(path)

    # Transform -> the GameObject it belongs to, so bones can be named.
    transforms = {}
    for obj in env.objects:
        if obj.type.name != "Transform":
            continue
        data = obj.read()
        name = "?"
        try:
            go = data.m_GameObject.read()
            name = go.m_Name
        except Exception:
            pass
        transforms[obj.path_id] = {
            "name": name,
            "data": data,
            "children": [getattr(c, "path_id", None) for c in (getattr(data, "m_Children", None) or [])],
            "parent": getattr(getattr(data, "m_Father", None), "path_id", None),
        }

    bones = {}
    for path_id, entry in transforms.items():
        data = entry["data"]
        parent_id = entry["parent"]
        bones[str(path_id)] = {
            "name": entry["name"],
            "parent": transforms.get(parent_id, {}).get("name") if parent_id else None,
            "children": [transforms[c]["name"] for c in entry["children"] if c in transforms],
            "local_position": vec(getattr(data, "m_LocalPosition", None), ("x", "y", "z")),
            "local_rotation": vec(getattr(data, "m_LocalRotation", None), ("x", "y", "z", "w")),
            "local_scale": vec(getattr(data, "m_LocalScale", None), ("x", "y", "z")),
        }

    roots = [b["name"] for b in bones.values() if not b["parent"]]

    payload = {
        "source": SKELETON,
        "bone_count": len(bones),
        "roots": roots,
        "bones": {b["name"]: {k: v for k, v in b.items() if k != "name"} for b in bones.values()},
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print("bones: %d" % len(bones))
    print("roots: %s" % ", ".join(roots))
    print("")

    def show(name, depth=0, seen=None):
        seen = seen or set()
        if name in seen or depth > 4:
            return
        seen.add(name)
        entry = payload["bones"].get(name)
        if not entry:
            return
        print("   %s%s" % ("  " * depth, name))
        for child in entry["children"]:
            show(child, depth + 1, seen)

    for r in roots:
        show(r)

    print("")
    print("written to %s" % args.out)


if __name__ == "__main__":
    main()
