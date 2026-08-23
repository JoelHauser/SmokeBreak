"""
Generates cigarette in-hands models for Smoke Break and exports them as FBX
for Unity 2022.3.

Run headless:

    blender --background --python make_cigarette_model.py -- --out C:/path/cigs.fbx

Produces three separate objects so you can pick what the hands actually hold:

    Cigarette_Single   one cigarette, paper and filter as two material slots
    Cigarette_Pack     the closed pack
    Pack_Lid           the flip-top, a separate object with its hinge on the
                       origin so it can be rotated open by an animation

Dimensions are real-world millimetres converted to metres, because Unity and
EFT both work in metres, and a model authored at the wrong scale is the most
common reason an in-hands item looks absurd.
"""

import bpy
import bmesh
import math
import sys
import os

# ---------------------------------------------------------------- parameters

MM = 0.001  # author in mm, store in metres

# King size pack, and a standard cigarette.
PACK_W, PACK_H, PACK_D = 55 * MM, 85 * MM, 22 * MM
LID_H = 20 * MM                       # how much of the top is the flip lid
CIG_LEN, CIG_RADIUS = 84 * MM, 4 * MM
FILTER_LEN = 24 * MM

BEVEL_WIDTH = 0.6 * MM
BEVEL_SEGMENTS = 2
CIG_SIDES = 16                        # low, because it is seen at arm's length

# Placeholder colours. The UVs are laid out so real textures will land
# correctly when you swap these for image maps.
COL_PACK = (0.55, 0.06, 0.06, 1.0)
COL_LID = (0.50, 0.05, 0.05, 1.0)
COL_PAPER = (0.92, 0.92, 0.90, 1.0)
COL_FILTER = (0.72, 0.55, 0.32, 1.0)


# ---------------------------------------------------------------- utilities

def parse_out_path():
    """Blender passes script arguments after a bare '--'."""
    argv = sys.argv
    if "--" not in argv:
        return os.path.join(os.getcwd(), "cigarette_models.fbx")
    argv = argv[argv.index("--") + 1:]
    for i, a in enumerate(argv):
        if a in ("--out", "-o") and i + 1 < len(argv):
            return argv[i + 1]
    return os.path.join(os.getcwd(), "cigarette_models.fbx")


def wipe_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_material(name, colour, roughness=0.6):
    """Principled BSDF. Socket names moved around in Blender 4.x, so set them
    defensively rather than assuming a fixed layout."""
    mat = bpy.data.materials.new(name)
    if not getattr(mat, "use_nodes", True):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = colour
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = colour
    return mat


def add_bevel(obj, width=BEVEL_WIDTH, segments=BEVEL_SEGMENTS):
    """Real objects have no perfectly sharp edges. A small bevel is what stops
    a box reading as programmer art under a specular highlight."""
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="Bevel", type="BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def unwrap(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def set_origin_to(obj, world_point):
    """Move the object origin without moving the geometry. The origin is the
    point the hand rig attaches to, so it matters more than it looks."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    previous = tuple(bpy.context.scene.cursor.location)
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = previous


def triangle_count(obj):
    """calc_loop_triangles has been deprecated and undeprecated more than once;
    fall back to counting polygon fans if it is gone."""
    try:
        obj.data.calc_loop_triangles()
        return len(obj.data.loop_triangles)
    except Exception:
        return sum(max(len(p.vertices) - 2, 0) for p in obj.data.polygons)


def ensure_fbx_exporter():
    """Blender has been moving off the legacy io_scene_fbx exporter. Enable it if
    it is merely switched off, and report honestly if it is actually gone."""
    if hasattr(bpy.ops.export_scene, "fbx"):
        return True
    try:
        import addon_utils
        addon_utils.enable("io_scene_fbx", default_set=False, persistent=True)
    except Exception as exc:
        print("  could not enable io_scene_fbx: %s" % exc)
    return hasattr(bpy.ops.export_scene, "fbx")


# ---------------------------------------------------------------- geometry

def build_pack_body():
    body_h = PACK_H - LID_H
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, body_h / 2))
    obj = bpy.context.active_object
    obj.name = "Cigarette_Pack"
    obj.scale = (PACK_W, PACK_D, body_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    add_bevel(obj)
    unwrap(obj)
    obj.data.materials.append(make_material("Cig_Pack", COL_PACK))
    # Base centre: predictable, and an easy reference when positioning against
    # the hand bone in Unity.
    set_origin_to(obj, (0.0, 0.0, 0.0))
    return obj


def build_pack_lid():
    body_h = PACK_H - LID_H
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, body_h + LID_H / 2))
    obj = bpy.context.active_object
    obj.name = "Pack_Lid"
    obj.scale = (PACK_W, PACK_D, LID_H)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    add_bevel(obj)
    unwrap(obj)
    obj.data.materials.append(make_material("Cig_Lid", COL_LID))
    # Origin on the hinge line, the back top edge of the body, so opening the
    # lid is one rotation on X rather than a rotation plus a correction.
    set_origin_to(obj, (0.0, PACK_D / 2, body_h))
    return obj


def build_single_cigarette():
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CIG_SIDES,
        radius=CIG_RADIUS,
        depth=CIG_LEN,
        location=(0, 0, CIG_LEN / 2),
    )
    obj = bpy.context.active_object
    obj.name = "Cigarette_Single"
    # Apply LOCATION as well as scale. bmesh below works in local coordinates, and
    # without this the mesh runs -42..+42 while the object sits at world z=42, so a
    # cut at "z = 24mm" actually lands at 66mm and the filter comes out inverted.
    # Applying location makes local and world agree, which is what the filter test
    # assumes.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)

    obj.data.materials.append(make_material("Cig_Paper", COL_PAPER, roughness=0.8))
    obj.data.materials.append(make_material("Cig_Filter", COL_FILTER, roughness=0.9))

    # A default cylinder has ONE quad per side running its whole length, so every
    # side face has its centre at the midpoint and a "below the filter line" test
    # catches only the end cap. Cut the mesh at the filter line first, then the
    # test means something.
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=(0.0, 0.0, FILTER_LEN),
        plane_no=(0.0, 0.0, 1.0),
        clear_inner=False,
        clear_outer=False,
    )

    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        if face.calc_center_median().z < FILTER_LEN - 1e-6:
            face.material_index = 1

    bm.to_mesh(mesh)
    bm.free()

    unwrap(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    # Filter end: the end held between the fingers, and the end that meets the
    # lips. Rotating about the origin is then rotating about the grip. Location
    # was already applied above, so this only confirms the origin is at the base.
    set_origin_to(obj, (0.0, 0.0, 0.0))
    return obj


# ---------------------------------------------------------------- export

def main():
    out_path = parse_out_path()
    directory = os.path.dirname(out_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    wipe_scene()
    objects = [build_pack_body(), build_pack_lid(), build_single_cigarette()]

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    if not ensure_fbx_exporter():
        # Do not throw away the geometry just because the exporter moved. Saving
        # a .blend means the models survive and can be exported by hand.
        blend_path = os.path.splitext(out_path)[0] + ".blend"
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print("")
        print("=" * 64)
        print("FBX exporter unavailable in this Blender build.")
        print("Models were saved instead to:")
        print("  %s" % blend_path)
        print("")
        print("Open that file and export manually with:")
        print("  Forward -Z, Up Y, Apply Scalings 'FBX All', Scale 1.0")
        print("=" * 64)
        return

    # Blender is Z-up, Unity is Y-up. These axis settings plus FBX_SCALE_ALL are
    # what make the model arrive upright at File Scale 1, rather than rotated
    # -90 on X and a hundredth of its intended size.
    bpy.ops.export_scene.fbx(
        filepath=out_path,
        use_selection=True,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        global_scale=1.0,
        axis_forward="-Z",
        axis_up="Y",
        object_types={"MESH"},
        mesh_smooth_type="FACE",
        use_mesh_modifiers=True,
        bake_space_transform=False,
    )

    print("")
    print("=" * 64)
    print("Smoke Break - model export complete")
    print("=" * 64)
    for obj in objects:
        d = obj.dimensions
        print("  %-18s %5.1f x %5.1f x %5.1f mm   %4d tris"
              % (obj.name, d.x / MM, d.y / MM, d.z / MM, triangle_count(obj)))
    print("")
    print("  written: %s" % out_path)
    print("")
    print("  In Unity, File Scale should read 1. If it reads 0.01 the export")
    print("  scale options did not apply and the model will import tiny.")
    print("=" * 64)


if __name__ == "__main__":
    main()
