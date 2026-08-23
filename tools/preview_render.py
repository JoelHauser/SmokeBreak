"""
Renders a preview PNG of the models built by make_cigarette_model.py, so the
geometry can actually be looked at instead of taken on trust.

    blender --background --python preview_render.py -- --out C:/path/preview.png

Lays the three objects out side by side, lights them, and renders a three
quarter view. Purely a review aid; it exports nothing.
"""

import bpy
import math
import sys
import os
import importlib.util


def parse_arg(flag, default):
    argv = sys.argv
    if "--" not in argv:
        return default
    argv = argv[argv.index("--") + 1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def load_builder():
    """Reuse the real build functions rather than duplicating the geometry, so
    the preview cannot drift from what actually gets exported."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "make_cigarette_model.py")
    spec = importlib.util.spec_from_file_location("cig_builder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cig_builder"] = module
    spec.loader.exec_module(module)
    return module


def pick_engine():
    """EEVEE was renamed across recent versions; take whichever exists."""
    try:
        options = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    except Exception:
        options = []
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"):
        if candidate in options:
            return candidate
    return None


def add_lighting():
    bpy.ops.object.light_add(type="AREA", location=(0.25, -0.3, 0.4))
    key = bpy.context.active_object
    key.data.energy = 4
    key.data.size = 0.35
    key.rotation_euler = (math.radians(45), 0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-0.3, -0.2, 0.2))
    fill = bpy.context.active_object
    fill.data.energy = 1.2
    fill.data.size = 0.6
    fill.rotation_euler = (math.radians(70), 0, math.radians(-40))

    world = bpy.data.worlds.new("PreviewWorld")
    bpy.context.scene.world = world
    if not getattr(world, "use_nodes", True):
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
        bg.inputs[1].default_value = 1.0


def add_camera(target, distance=0.38):
    bpy.ops.object.camera_add(location=(distance * 0.75, -distance, distance * 0.62))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    constraint = cam.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    cam.data.lens = 60
    return cam


def add_ground():
    """A floor gives the eye a scale reference; without it these read as
    abstract shapes floating in the void."""
    bpy.ops.mesh.primitive_plane_add(size=0.6, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Ground"
    mat = bpy.data.materials.new("Ground")
    if not getattr(mat, "use_nodes", True):
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf and "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (0.09, 0.09, 0.11, 1.0)
    if bsdf and "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.9
    plane.data.materials.append(mat)
    return plane


def main():
    out_path = parse_arg("--out", os.path.join(os.getcwd(), "preview.png"))
    directory = os.path.dirname(out_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    builder = load_builder()
    builder.wipe_scene()

    pack = builder.build_pack_body()
    lid = builder.build_pack_lid()
    cig = builder.build_single_cigarette()

    # Spread them out. The lid keeps its real position relative to the pack so
    # the flip-top relationship stays readable, and gets tilted open a little to
    # show the hinge origin doing its job.
    pack.location.x = -0.055
    lid.location.x = -0.055
    lid.rotation_euler.x = math.radians(-55)

    # Lying along X keeps the cigarette broadside to the camera, so the filter
    # split is actually visible rather than foreshortened into the distance.
    cig.location = (-0.005, -0.055, builder.CIG_RADIUS)
    cig.rotation_euler = (0, math.radians(90), math.radians(-6))

    add_ground()
    add_lighting()

    focus = bpy.data.objects.new("Focus", None)
    bpy.context.collection.objects.link(focus)
    focus.location = (0.0, -0.02, 0.042)
    add_camera(focus)

    scene = bpy.context.scene
    engine = pick_engine()
    if engine:
        scene.render.engine = engine
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 620
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    # Filmic/AgX view transforms desaturate hard, which made a dark red pack
    # render as pale pink. Standard shows the actual material colours.
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.render.filepath = out_path

    bpy.ops.render.render(write_still=True)

    print("")
    print("=" * 60)
    print("preview written: %s" % out_path)
    print("engine: %s" % (engine or "default"))
    print("=" * 60)


if __name__ == "__main__":
    main()
