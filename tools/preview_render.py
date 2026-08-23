"""
Renders a preview PNG of the models built by make_cigarette_model.py, so the
geometry can be looked at rather than taken on trust.

    blender --background --python preview_render.py -- --out C:/path/preview.png

Lays the four branded packs out in a row with their lids open, so the twenty
filter ends inside each are visible, and puts a loose cigarette in front for
scale. Purely a review aid; it exports nothing.
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
    # Area lights of 25W around an 8cm object blow the render out completely.
    # These are sized for props measured in centimetres.
    bpy.ops.object.light_add(type="AREA", location=(0.22, -0.30, 0.42))
    key = bpy.context.active_object
    key.data.energy = 6
    key.data.size = 0.45
    key.rotation_euler = (math.radians(38), 0, math.radians(32))

    bpy.ops.object.light_add(type="AREA", location=(-0.32, -0.22, 0.24))
    fill = bpy.context.active_object
    fill.data.energy = 2
    fill.data.size = 0.6
    fill.rotation_euler = (math.radians(68), 0, math.radians(-42))

    world = bpy.data.worlds.new("PreviewWorld")
    bpy.context.scene.world = world
    if not getattr(world, "use_nodes", True):
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
        bg.inputs[1].default_value = 1.0


def add_camera(target, location):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    constraint = cam.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    cam.data.lens = 42
    return cam


def add_ground():
    """A floor gives the eye a scale reference; without it these read as
    abstract shapes floating in the void."""
    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, 0))
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

    spacing = 0.072
    count = len(builder.BRANDS)
    x0 = -(count - 1) * spacing / 2.0

    assets = os.path.dirname(os.path.abspath(out_path))
    mapping = builder.load_pack_mapping(assets)
    if mapping:
        print("using game textures for: %s" % ", ".join(sorted(mapping)))

    for index, (brand, colour, _template_id) in enumerate(builder.BRANDS):
        body, cigs, hero, lid = builder.build_brand(brand, colour, mapping.get(brand))
        x = x0 + index * spacing
        for obj in (body, cigs, hero, lid):
            obj.location.x += x
        # Knocked up out of the pack, as beat 2 of the animation requires.
        hero.location.z += 0.022
        # Well past vertical, so the camera sees down into the pack and the
        # twenty filter ends actually read.
        lid.rotation_euler.x = math.radians(-115)

    # A loose cigarette in front, for scale and to show the filter split.
    single = builder.build_cigarette(
        "Cigarette_Single", builder.CIG_RADIUS, builder.CIG_SIDES, filter_up=False
    )
    single.location = (-0.02, -0.075, builder.CIG_RADIUS)
    single.rotation_euler = (0, math.radians(90), math.radians(-4))

    add_ground()
    add_lighting()

    focus = bpy.data.objects.new("Focus", None)
    bpy.context.collection.objects.link(focus)
    focus.location = (0.0, -0.02, 0.05)
    add_camera(focus, location=(0.12, -0.42, 0.34))

    scene = bpy.context.scene
    engine = pick_engine()
    if engine:
        scene.render.engine = engine
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 640
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
