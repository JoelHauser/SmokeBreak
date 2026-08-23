"""
Imports BSG's own cigarette pack meshes and renders them with the game's atlas
texture, to confirm the UVs land correctly before anything is built on top.

    blender --background --python preview_authentic.py -- --assets ./out --out ./out/authentic.png

Expects extract_cig_textures.py and the mesh export to have already produced:

    <assets>/meshes/<Brand>.obj
    <assets>/textures/scrap_d.png
"""

import bpy
import math
import os
import sys


BRANDS = ("ApolloSoyuz", "Malboro", "Strike", "Wilston")


def parse_arg(flag, default):
    argv = sys.argv
    if "--" not in argv:
        return default
    argv = argv[argv.index("--") + 1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def wipe_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_obj(path):
    """Blender 4.x/5.x use wm.obj_import; import_scene.obj was removed."""
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "obj_import"):
        # UnityPy already writes the OBJ Z-up, so asking Blender to convert from
        # Y-up rotates the pack 90 degrees onto its back. Import it as-is.
        bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    else:
        bpy.ops.import_scene.obj(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        return None
    obj = new[0]
    # BSG authored these with -Z as up, so straight off the import the artwork is
    # upside down. A 180 degree roll about Y rights it while keeping the printed
    # face pointing the same way. Baked in, so the exported mesh is correct too.
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    obj.rotation_euler = (0.0, math.radians(180.0), 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def atlas_material(texture_path):
    """One material for every pack, because the game uses one atlas for every
    barter item. Sharing it here keeps the preview honest."""
    existing = bpy.data.materials.get("scrap_d")
    if existing:
        return existing
    mat = bpy.data.materials.new("scrap_d")
    if not getattr(mat, "use_nodes", True):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(texture_path)
    tex.interpolation = "Closest" if False else "Linear"
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.75
    return mat


def add_lighting():
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

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    if not getattr(world, "use_nodes", True):
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)


def pick_engine():
    try:
        options = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    except Exception:
        options = []
    for c in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"):
        if c in options:
            return c
    return None


def main():
    assets = parse_arg("--assets", os.path.join(os.getcwd(), "out"))
    out_path = parse_arg("--out", os.path.join(assets, "authentic.png"))
    mesh_dir = os.path.join(assets, "meshes")
    tex_path = os.path.join(assets, "textures", "scrap_d.png")

    if not os.path.isfile(tex_path):
        sys.exit("missing atlas: %s" % tex_path)

    wipe_scene()
    mat = atlas_material(tex_path)

    spacing = 0.078
    x0 = -(len(BRANDS) - 1) * spacing / 2.0
    report = []

    for index, brand in enumerate(BRANDS):
        obj_path = os.path.join(mesh_dir, "%s.obj" % brand)
        if not os.path.isfile(obj_path):
            print("missing mesh: %s" % obj_path)
            continue
        obj = import_obj(obj_path)
        if obj is None:
            print("import produced nothing for %s" % brand)
            continue
        obj.name = brand
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.location.x = x0 + index * spacing
        d = obj.dimensions
        report.append((brand, d.x * 1000, d.y * 1000, d.z * 1000, len(obj.data.polygons)))
        print("   %s rotation_euler = %s" % (brand, tuple(round(math.degrees(a), 1) for a in obj.rotation_euler)))

    add_lighting()

    focus = bpy.data.objects.new("Focus", None)
    bpy.context.collection.objects.link(focus)
    focus.location = (0.0, 0.0, 0.047)
    bpy.context.collection.objects.link(focus) if False else None

    bpy.ops.object.camera_add(location=(0.02, -0.70, 0.26))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    con = cam.constraints.new(type="TRACK_TO")
    con.target = focus
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam.data.lens = 52

    scene = bpy.context.scene
    engine = pick_engine()
    if engine:
        scene.render.engine = engine
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 620
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    print("")
    print("=" * 64)
    for brand, x, y, z, faces in report:
        print("  %-12s %5.1f x %5.1f x %5.1f mm   %d faces" % (brand, x, y, z, faces))
    print("")
    print("  preview: %s" % out_path)
    print("=" * 64)


if __name__ == "__main__":
    main()
