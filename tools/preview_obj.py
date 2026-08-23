"""
Renders a single extracted OBJ with a texture, for eyeballing anything pulled
out of the game bundles.

    blender --background --python preview_obj.py -- --obj X.obj --tex Y.png --out Z.png

Applies the same corrective roll as the pack meshes: BSG authors these with -Z
as up, so straight off the import the artwork is upside down.
"""

import bpy
import math
import os
import sys


def parse_arg(flag, default=None):
    argv = sys.argv
    if "--" not in argv:
        return default
    argv = argv[argv.index("--") + 1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def main():
    obj_path = parse_arg("--obj")
    tex_path = parse_arg("--tex")
    out_path = parse_arg("--out", "preview_obj.png")
    if not obj_path or not os.path.isfile(obj_path):
        sys.exit("need --obj pointing at a file")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=obj_path, forward_axis="Y", up_axis="Z")
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not new:
        sys.exit("import produced no mesh")
    obj = new[0]

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.rotation_euler = (0.0, math.radians(180.0), 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    if tex_path and os.path.isfile(tex_path):
        mat = bpy.data.materials.new("Extracted")
        if not getattr(mat, "use_nodes", True):
            mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(tex_path)
        if bsdf:
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = 0.5
        obj.data.materials.clear()
        obj.data.materials.append(mat)

    d = obj.dimensions
    span = max(d.x, d.y, d.z) or 0.1

    bpy.ops.object.light_add(type="AREA", location=(span * 2, -span * 2.5, span * 3))
    key = bpy.context.active_object
    key.data.energy = span * span * 900
    key.data.size = span * 3
    key.rotation_euler = (math.radians(40), 0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-span * 2.5, -span * 2, span * 1.5))
    fill = bpy.context.active_object
    fill.data.energy = span * span * 280
    fill.data.size = span * 4
    fill.rotation_euler = (math.radians(70), 0, math.radians(-45))

    world = bpy.data.worlds.new("W")
    bpy.context.scene.world = world
    if not getattr(world, "use_nodes", True):
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.06, 0.06, 0.07, 1.0)

    focus = bpy.data.objects.new("Focus", None)
    bpy.context.collection.objects.link(focus)
    focus.location = tuple(obj.location) if False else (0.0, 0.0, d.z / 2.0)

    bpy.ops.object.camera_add(location=(span * 1.1, -span * 2.6, span * 1.4))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam
    con = cam.constraints.new(type="TRACK_TO")
    con.target = focus
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam.data.lens = 60

    scene = bpy.context.scene
    try:
        options = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
        for c in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
            if c in options:
                scene.render.engine = c
                break
    except Exception:
        pass
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    print("")
    print("=" * 58)
    print("  %s" % os.path.basename(obj_path))
    print("  %.1f x %.1f x %.1f mm   %d faces" % (d.x * 1000, d.y * 1000, d.z * 1000,
                                                  len(obj.data.polygons)))
    print("  preview: %s" % out_path)
    print("=" * 58)


if __name__ == "__main__":
    main()
