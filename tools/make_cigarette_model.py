"""
Generates the Smoke Break in-hands models and exports FBX for Unity 2022.3.

Run headless:

    blender --background --python make_cigarette_model.py -- --out C:/path/models

The --out value is a DIRECTORY. One FBX is written per cigarette brand, each
with its contents at the origin so it drops straight into Unity as a prefab,
plus a standalone single cigarette:

    ApolloSoyuz.fbx    Body + 20 cigarettes + Lid
    Malboro.fbx
    Strike.fbx
    Wilston.fbx
    Cigarette_Single.fbx

Each pack holds 20 cigarettes in the real 7-6-7 nested arrangement, filters
facing up, so an opened lid shows twenty filter ends the way a real pack does.

Dimensions are real millimetres converted to metres. Unity and EFT both work in
metres, and a model authored at the wrong scale is the most common reason an
in-hands item looks absurd.
"""

import bpy
import bmesh
import json
import math
import sys
import os

# ---------------------------------------------------------------- parameters

MM = 0.001  # author in mm, store in metres

# King size pack.
PACK_W, PACK_H, PACK_D = 55 * MM, 85 * MM, 22 * MM
LID_H = 20 * MM                     # how much of the top is the flip lid
WALL = 1.0 * MM                     # card thickness, sets the interior

CIG_LEN = 84 * MM
FILTER_LEN = 24 * MM
CIG_RADIUS = 4 * MM                 # the standalone one; in-pack is derived

# Real packs are 7-6-7, nested, which is what makes 20 fit a 55x22 box.
PACK_ROWS = (7, 6, 7)

BEVEL_WIDTH = 0.6 * MM
BEVEL_SEGMENTS = 2
CIG_SIDES = 16                      # standalone, seen close
CIG_SIDES_IN_PACK = 8               # twenty per pack, and only the ends show

COL_PAPER = (0.92, 0.92, 0.90, 1.0)
COL_FILTER = (0.72, 0.55, 0.32, 1.0)

# One entry per cigarette item in EFT. The template id is carried here purely so
# the model and the server config cannot drift apart unnoticed.
BRANDS = (
    ("ApolloSoyuz", (0.09, 0.16, 0.38, 1.0), "573475fb24597737fb1379e1"),
    ("Malboro",     (0.60, 0.07, 0.07, 1.0), "573476d324597737da2adc13"),
    ("Strike",      (0.87, 0.85, 0.80, 1.0), "5734770f24597738025ee254"),
    ("Wilston",     (0.72, 0.53, 0.12, 1.0), "573476f124597737e04bf328"),
)


# ---------------------------------------------------------------- utilities

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
    for block in (bpy.data.meshes, bpy.data.materials):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_material(name, colour, roughness=0.6):
    """Principled BSDF. Socket names have moved around across 4.x and 5.x, so
    set them defensively rather than assuming a fixed layout."""
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
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


def darken(colour, factor=0.82):
    return (colour[0] * factor, colour[1] * factor, colour[2] * factor, colour[3])


def add_bevel(obj, width=BEVEL_WIDTH, segments=BEVEL_SEGMENTS):
    """Real objects have no perfectly sharp edges. A small bevel is what stops a
    box reading as programmer art under a specular highlight."""
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
    try:
        obj.data.calc_loop_triangles()
        return len(obj.data.loop_triangles)
    except Exception:
        return sum(max(len(p.vertices) - 2, 0) for p in obj.data.polygons)


def ensure_fbx_exporter():
    """Blender has been migrating off the legacy io_scene_fbx exporter. Enable
    it if merely switched off, and report honestly if it is actually gone."""
    if hasattr(bpy.ops.export_scene, "fbx"):
        return True
    try:
        import addon_utils
        addon_utils.enable("io_scene_fbx", default_set=False, persistent=True)
    except Exception as exc:
        print("  could not enable io_scene_fbx: %s" % exc)
    return hasattr(bpy.ops.export_scene, "fbx")



# ------------------------------------------------------- atlas texturing

FACE_BY_NORMAL = {
    (0, -1, 0): "front",
    (0, 1, 0): "back",
    (-1, 0, 0): "left",
    (1, 0, 0): "right",
    (0, 0, 1): "top",
    (0, 0, -1): "bottom",
}


def dominant_face(normal):
    axis = max(range(3), key=lambda i: abs(normal[i]))
    key = [0, 0, 0]
    key[axis] = 1 if normal[axis] > 0 else -1
    return FACE_BY_NORMAL.get(tuple(key))


def apply_atlas_uvs(obj, faces_map):
    """Project each box face into its slice of the brand texture.

    Positions are normalised against the WHOLE pack, not against this object,
    which is what makes the body and lid pick up the correct upper and lower
    portions of the same artwork without any explicit splitting.
    """
    extents = {
        0: (-PACK_W / 2.0, PACK_W / 2.0),
        1: (-PACK_D / 2.0, PACK_D / 2.0),
        2: (0.0, PACK_H),
    }

    mesh = obj.data
    uv_layer = mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")

    for poly in mesh.polygons:
        name = dominant_face(poly.normal)
        spec = faces_map.get(name) if name else None
        if not spec:
            continue
        u0, v0, u1, v1 = spec["uv"]
        ax_u, ax_v = spec["u_axis"], spec["v_axis"]
        lo_u, hi_u = extents[ax_u]
        lo_v, hi_v = extents[ax_v]

        for loop_index in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            tu = (co[ax_u] - lo_u) / (hi_u - lo_u)
            tv = (co[ax_v] - lo_v) / (hi_v - lo_v)
            if spec["u_flip"]:
                tu = 1.0 - tu
            if spec["v_flip"]:
                tv = 1.0 - tv
            uv_layer.data[loop_index].uv = (u0 + tu * (u1 - u0), v0 + tv * (v1 - v0))


def brand_material(brand, texture_path):
    name = "%s_Albedo" % brand
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    if not getattr(mat, "use_nodes", True):
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(texture_path)
    if bsdf:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.78
    return mat


def load_pack_mapping(assets_dir):
    """Returns {brand: (faces_map, texture_path)} or {} when the baked textures
    are not present, in which case the flat placeholder colours are used."""
    path = os.path.join(assets_dir, "pack_uvs.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for brand, entry in data.items():
        tex = os.path.join(assets_dir, "textures", entry["texture"])
        if os.path.isfile(tex):
            out[brand] = (entry["faces"], tex)
    return out


# ---------------------------------------------------------------- cigarettes

def in_pack_diameter():
    """Derive the cigarette diameter from the pack interior rather than picking
    one and hoping it fits. Seven across sets the width limit; three nested rows
    set the depth limit, since nested rows sit sqrt(3)/2 apart rather than
    stacking. Whichever is tighter wins."""
    interior_w = PACK_W - 2 * WALL
    interior_d = PACK_D - 2 * WALL
    by_width = interior_w / max(PACK_ROWS)
    by_depth = interior_d / (1.0 + math.sqrt(3.0))
    return min(by_width, by_depth)


def cigarette_positions():
    """7-6-7, nested, centred on the pack. Returns offsets in metres."""
    d = in_pack_diameter()
    row_spacing = d * math.sqrt(3.0) / 2.0
    total_depth = d + 2 * row_spacing
    y0 = -total_depth / 2.0 + d / 2.0

    points = []
    for row_index, count in enumerate(PACK_ROWS):
        y = y0 + row_index * row_spacing
        x0 = -(count - 1) * d / 2.0
        for i in range(count):
            points.append((x0 + i * d, y))
    return points, d


def build_cigarette(name, radius, sides, filter_up):
    """One cigarette along +Z with its origin at the base.

    filter_up puts the filter at the TOP, which is how cigarettes sit in a pack
    and what makes an opened lid show twenty filter ends.
    """
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=sides, radius=radius, depth=CIG_LEN, location=(0, 0, CIG_LEN / 2)
    )
    obj = bpy.context.active_object
    obj.name = name
    # Apply LOCATION as well as scale. bmesh below works in local coordinates,
    # and without this the mesh runs -42..+42 while the object sits at world
    # z=42, so a cut at "24mm" lands at 66mm and the filter comes out inverted.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)

    obj.data.materials.append(make_material("Cig_Paper", COL_PAPER, roughness=0.8))
    obj.data.materials.append(make_material("Cig_Filter", COL_FILTER, roughness=0.9))

    cut_z = CIG_LEN - FILTER_LEN if filter_up else FILTER_LEN

    # A default cylinder has ONE quad per side running its whole length, so every
    # side face has its centre at the midpoint and a "past the filter line" test
    # catches only the end cap. Cut the mesh there first, then the test means
    # something.
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=(0.0, 0.0, cut_z),
        plane_no=(0.0, 0.0, 1.0),
        clear_inner=False,
        clear_outer=False,
    )
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        z = face.calc_center_median().z
        is_filter = z > cut_z + 1e-6 if filter_up else z < cut_z - 1e-6
        if is_filter:
            face.material_index = 1
    bm.to_mesh(mesh)
    bm.free()

    unwrap(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    set_origin_to(obj, (0.0, 0.0, 0.0))
    return obj


def build_pack_contents(brand):
    """Twenty cigarettes, filters up, joined into one mesh.

    Joined rather than left as twenty objects because they never move
    independently, and twenty child transforms on an in-hands prop is waste.
    """
    positions, diameter = cigarette_positions()
    radius = diameter / 2.0 * 0.97  # a hair of clearance so they do not z-fight

    made = []
    for index, (x, y) in enumerate(positions):
        cig = build_cigarette(
            "%s_Cig_%02d" % (brand, index), radius, CIG_SIDES_IN_PACK, filter_up=True
        )
        # Sit on the interior floor. With an 84mm cigarette and a 65mm body they
        # protrude 20mm into the lid, which is exactly what the lid covers.
        cig.location = (x, y, WALL)
        made.append(cig)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in made:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = made[0]
    bpy.ops.object.join()

    joined = bpy.context.active_object
    joined.name = "%s_Cigarettes" % brand
    set_origin_to(joined, (0.0, 0.0, 0.0))
    return joined


# ---------------------------------------------------------------- pack

def _finish_pack_part(obj, brand, colour, textured, origin, suffix):
    """Shared tail for the body and the lid.

    Order matters. Location is applied first so the mesh sits in pack space,
    which is what apply_atlas_uvs normalises against - and the origin is only
    moved afterwards, because moving it first would shift those coordinates out
    from under the projection. The bevel comes after the UVs so its new faces
    inherit them by interpolation instead of missing the mapping entirely.
    """
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)

    if textured:
        faces_map, texture_path = textured
        apply_atlas_uvs(obj, faces_map)
        obj.data.materials.append(brand_material(brand, texture_path))
    else:
        unwrap(obj)
        obj.data.materials.append(make_material("%s_%s" % (brand, suffix), colour))

    add_bevel(obj)
    set_origin_to(obj, origin)
    return obj


def build_pack_body(brand, colour, textured=None):
    body_h = PACK_H - LID_H
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, body_h / 2))
    obj = bpy.context.active_object
    obj.name = "%s_Body" % brand
    obj.scale = (PACK_W, PACK_D, body_h)
    return _finish_pack_part(obj, brand, colour, textured, (0.0, 0.0, 0.0), "Card")


def build_pack_lid(brand, colour, textured=None):
    body_h = PACK_H - LID_H
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, body_h + LID_H / 2))
    obj = bpy.context.active_object
    obj.name = "%s_Lid" % brand
    obj.scale = (PACK_W, PACK_D, LID_H)
    # Origin on the hinge line, the back top edge of the body, so opening the
    # lid is one rotation on X rather than a rotation plus a correction.
    return _finish_pack_part(obj, brand, darken(colour), textured,
                             (0.0, PACK_D / 2, body_h), "LidCard")


def build_brand(brand, colour, textured=None):
    return [
        build_pack_body(brand, colour, textured),
        build_pack_contents(brand),
        build_pack_lid(brand, colour, textured),
    ]


# ---------------------------------------------------------------- export

def export(objects, path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    # Blender is Z-up, Unity is Y-up. These axis settings plus FBX_SCALE_ALL are
    # what make the model arrive upright at File Scale 1, rather than rotated
    # -90 on X and a hundredth of its intended size.
    bpy.ops.export_scene.fbx(
        filepath=path,
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


def main():
    out_dir = parse_arg("--out", os.path.join(os.getcwd(), "models"))
    os.makedirs(out_dir, exist_ok=True)

    if not ensure_fbx_exporter():
        print("")
        print("FBX exporter unavailable in this Blender build.")
        print("Export by hand with: Forward -Z, Up Y, Apply Scalings 'FBX All', Scale 1.0")
        return

    assets_dir = parse_arg("--assets", out_dir)
    mapping = load_pack_mapping(assets_dir)

    positions, diameter = cigarette_positions()
    summary = []

    for brand, colour, template_id in BRANDS:
        wipe_scene()
        objects = build_brand(brand, colour, mapping.get(brand))
        path = os.path.join(out_dir, "%s.fbx" % brand)
        export(objects, path)
        summary.append((brand, template_id, sum(triangle_count(o) for o in objects),
                        "game texture" if brand in mapping else "flat colour"))

    wipe_scene()
    single = build_cigarette("Cigarette_Single", CIG_RADIUS, CIG_SIDES, filter_up=False)
    export([single], os.path.join(out_dir, "Cigarette_Single.fbx"))
    single_tris = triangle_count(single)

    print("")
    print("=" * 68)
    print("Smoke Break - model export complete")
    print("=" * 68)
    print("  pack        %.0f x %.0f x %.0f mm, %.0f mm lid" %
          (PACK_W / MM, PACK_D / MM, PACK_H / MM, LID_H / MM))
    print("  contents    %d cigarettes, rows %s, filters up" %
          (len(positions), "-".join(str(r) for r in PACK_ROWS)))
    print("  cigarette   %.2f mm across, derived from the pack interior" % (diameter / MM))
    print("")
    for brand, template_id, tris, skin in summary:
        print("  %-13s %5d tris   %-14s %s" % (brand, tris, skin, template_id))
    print("  %-13s %5d tris" % ("Single", single_tris))
    print("")
    print("  written to: %s" % out_dir)
    print("")
    print("  In Unity, File Scale should read 1. If it reads 0.01 the export")
    print("  scale options did not apply and the model will import tiny.")
    print("=" * 68)


if __name__ == "__main__":
    main()
