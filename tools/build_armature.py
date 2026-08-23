"""
Rebuilds EFT's character rig as a Blender armature from the exported hierarchy.

    blender --background --python build_armature.py -- --json ./out/skeleton.json \
        --blend ./out/eft_rig.blend --preview ./out/rig.png

Produces a .blend containing:

    EFT_Rig        the armature, 79 bones, parented as in the game
    Rig_Debug      a tube mesh along the same bones, purely so the rig can be
                   rendered and looked at - armatures do not render

Unity is Y-up and left-handed, Blender is Z-up and right-handed, so every
transform is converted on the way in. Swapping Y and Z does both jobs at once:
it puts up where Blender expects it and flips handedness in the same move.
"""

import bpy
import json
import math
import os
import sys
from mathutils import Matrix, Quaternion, Vector


# Swapping Y and Z converts Unity's Y-up left-handed space to Blender's Z-up
# right-handed one. It is its own inverse, which is why it appears on both
# sides of the basis change below.
CONV = Matrix(((1, 0, 0, 0),
               (0, 0, 1, 0),
               (0, 1, 0, 0),
               (0, 0, 0, 1)))

# Leaf bones have no child to point at, so they get a short stub. Bones are
# never zero length in Blender - a zero length bone is silently deleted.
LEAF_LENGTH = 0.02
MIN_LENGTH = 0.005


def parse_arg(flag, default=None):
    argv = sys.argv
    if "--" not in argv:
        return default
    argv = argv[argv.index("--") + 1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def local_matrix(entry):
    p = entry["local_position"]
    r = entry["local_rotation"]
    s = entry["local_scale"]
    # JSON stores the quaternion x,y,z,w; mathutils wants w,x,y,z.
    quat = Quaternion((r[3], r[0], r[1], r[2]))
    return Matrix.LocRotScale(Vector(p), quat, Vector(s))


def world_matrices(bones, roots):
    """Walk the hierarchy accumulating world transforms, then convert each into
    Blender space."""
    world = {}

    def walk(name, parent_matrix):
        entry = bones.get(name)
        if entry is None:
            return
        matrix = parent_matrix @ local_matrix(entry)
        world[name] = matrix
        for child in entry["children"]:
            walk(child, matrix)

    for root in roots:
        walk(root, Matrix.Identity(4))

    return {name: CONV @ m @ CONV for name, m in world.items()}


def build_armature(bones, roots, world):
    armature = bpy.data.armatures.new("EFT_Rig")
    obj = bpy.data.objects.new("EFT_Rig", armature)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")

    created = {}
    for name, matrix in world.items():
        bone = armature.edit_bones.new(name)
        head = matrix.to_translation()

        # Point each bone at its first child. That is what makes a rig readable
        # in the viewport instead of a cloud of identical stubs.
        children = [c for c in bones[name]["children"] if c in world]
        if children:
            tail = world[children[0]].to_translation()
            if (tail - head).length < MIN_LENGTH:
                tail = head + matrix.to_3x3().normalized() @ Vector((0, LEAF_LENGTH, 0))
        else:
            direction = matrix.to_3x3().normalized() @ Vector((0, 1, 0))
            tail = head + direction * LEAF_LENGTH

        bone.head = head
        bone.tail = tail
        if bone.length < MIN_LENGTH:
            bone.tail = head + Vector((0, 0, LEAF_LENGTH))
        created[name] = bone

    for name, bone in created.items():
        parent = bones[name]["parent"]
        if parent and parent in created:
            bone.parent = created[parent]

    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def build_debug_mesh(bones, world):
    """Armatures do not render, so lay a tube along every bone. This exists only
    so the rig can be checked by eye."""
    verts = []
    edges = []
    index = {}
    for name, matrix in world.items():
        index[name] = len(verts)
        verts.append(matrix.to_translation())
    # Helpers are parented to the spine but positioned out at the hands, hips
    # and elbows, so drawing an edge to them puts a starburst through the chest.
    # They stay in the armature - an animator needs them - but not in the
    # picture, which exists to confirm the skeleton is shaped like a person.
    helpers = ("IK_", "Bend_Goal", "weapon_holster", "Camera_", "Weapon_root")

    def is_helper(name):
        return any(name.startswith(h) for h in helpers) or name.endswith("_anim")

    for name in world:
        if is_helper(name):
            continue
        for child in bones[name]["children"]:
            if child in index and not is_helper(child):
                edges.append((index[name], index[child]))

    mesh = bpy.data.meshes.new("Rig_Debug")
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new("Rig_Debug", mesh)
    bpy.context.collection.objects.link(obj)

    # SKIN, not WIREFRAME. The wireframe modifier builds from faces, and this
    # mesh is edges only, so it silently produces nothing at all.
    obj.modifiers.new("Skin", "SKIN")
    bpy.context.view_layer.objects.active = obj
    layer = mesh.skin_vertices[0].data if mesh.skin_vertices else []
    for item in layer:
        item.radius = (0.012, 0.012)
    return obj


def render_preview(target, out_path):
    span = max(target.dimensions) or 1.0
    centre = target.location + Vector((0, 0, target.dimensions.z / 2.0))

    bpy.ops.object.light_add(type="AREA", location=(span, -span * 1.6, span * 1.5))
    key = bpy.context.active_object
    key.data.energy = span * span * 260
    key.data.size = span
    key.rotation_euler = (math.radians(45), 0, math.radians(30))

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    if not getattr(world, "use_nodes", True):
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

    focus = bpy.data.objects.new("Focus", None)
    bpy.context.collection.objects.link(focus)
    focus.location = centre

    bpy.ops.object.camera_add(location=(span * 0.9, -span * 2.0, span * 1.0))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    con = cam.constraints.new(type="TRACK_TO")
    con.target = focus
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam.data.lens = 50

    scene = bpy.context.scene
    try:
        options = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
        for c in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
            if c in options:
                scene.render.engine = c
                break
    except Exception:
        pass
    scene.render.resolution_x = 760
    scene.render.resolution_y = 1000
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)


def main():
    json_path = parse_arg("--json", "out/skeleton.json")
    blend_path = parse_arg("--blend", "out/eft_rig.blend")
    preview_path = parse_arg("--preview", "out/rig.png")

    if not os.path.isfile(json_path):
        sys.exit("missing %s - run extract_skeleton.py first" % json_path)

    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    bones = data["bones"]
    roots = data["roots"]

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    world = world_matrices(bones, roots)
    rig = build_armature(bones, roots, world)
    debug = build_debug_mesh(bones, world)

    for path in (blend_path, preview_path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    render_preview(debug, preview_path)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend_path))

    heights = [m.to_translation().z for m in world.values()]
    print("")
    print("=" * 62)
    print("  bones placed : %d of %d" % (len(world), data["bone_count"]))
    print("  height span  : %.3f m to %.3f m" % (min(heights), max(heights)))
    for key_bone in ("Weapon_root", "IK_S_RPalm", "Base HumanRPalm", "Base HumanHead"):
        if key_bone in world:
            v = world[key_bone].to_translation()
            print("  %-16s [%6.3f %6.3f %6.3f]" % (key_bone, v.x, v.y, v.z))
    print("")
    print("  blend   : %s" % blend_path)
    print("  preview : %s" % preview_path)
    print("=" * 62)


if __name__ == "__main__":
    main()
