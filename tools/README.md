# tools

## make_cigarette_model.py

Generates the in-hands models and exports FBX for Unity 2022.3.

```
blender --background --python make_cigarette_model.py -- --out C:/temp/models
```

`--out` is a **directory**. One FBX per brand, each with its contents at the
origin so it drops into Unity as a prefab, plus a standalone cigarette:

| File | Contents | Tris |
|---|---|---|
| `ApolloSoyuz.fbx` | Body + 20 cigarettes + Lid | 1096 |
| `Malboro.fbx` | same | 1096 |
| `Strike.fbx` | same | 1096 |
| `Wilston.fbx` | same | 1096 |
| `Cigarette_Single.fbx` | one cigarette, filter at the origin end | 92 |

Each pack holds **20 cigarettes in the real 7-6-7 nested arrangement, filters
up**, so an opened lid shows twenty filter ends.

The cigarette diameter is not a guess. It is derived from the pack interior:
seven across sets a width limit, three nested rows set a depth limit (nested
rows sit `sqrt(3)/2` apart rather than stacking), and the tighter of the two
wins. At the shipped pack size that comes out at 7.32 mm.

The twenty cigarettes are joined into one mesh per pack. They never move
independently, and twenty child transforms on an in-hands prop is waste.

### Object origins

| Object | Origin | Why |
|---|---|---|
| `*_Body` | base centre | predictable reference for the hand bone |
| `*_Lid` | on the hinge | opening it is one X rotation, no correction |
| `*_Cigarettes` | pack base | moves with the body |
| `Cigarette_Single` | filter end | the end held, and the end that meets the lips |

### Scale

Authored in real millimetres, exported in metres. In Unity the import inspector
should show **File Scale 1**. If it shows 0.01, the export scale options did not
apply and the model will be a hundredth of its size.

If your Blender build has dropped the legacy FBX exporter, the script says so
and prints the manual settings (Forward -Z, Up Y, Apply Scalings "FBX All",
Scale 1.0).

Verified on Blender 5.2.0 LTS.

## preview_render.py

Renders a PNG of all four packs with their lids open, so the geometry can be
looked at rather than taken on trust.

```
blender --background --python preview_render.py -- --out C:/temp/preview.png
```

It imports the build functions from `make_cigarette_model.py` rather than
duplicating them, so the preview cannot drift from what actually gets exported.
It has already caught two bugs that would otherwise have reached Unity.

Output goes to `tools/out/`, which is gitignored.

## Game asset extraction

Three scripts pull the real cigarette assets out of EFT. They need `UnityPy`:

```
pip install UnityPy
```

### extract_cig_textures.py

```
python extract_cig_textures.py --game "H:/SPT4.1.X" --out ./out/textures
```

The four barter bundles are ~26 KB each and contain **no textures at all** -
only meshes and a material pointer. Every cigarette pack shares one atlas,
`assets/content/materials/scrap_d.bundle`, which holds a 2048x2048 albedo
(`scrap_d`) and a 1024x1024 normal (`scrap_n`) covering every barter item in
the game.

The dependency is recorded in `StreamingAssets/Windows/Windows.json`, which is
how the atlas was found rather than by guessing.

### trace_cig_materials.py

Reports each bundle's external references. All four packs point at the same
material `path_id`, which is what first suggested a shared atlas.

### preview_authentic.py

```
blender --background --python preview_authentic.py -- --assets ./out --out ./out/authentic.png
```

Imports BSG's own pack meshes and renders them with the game atlas, to confirm
the UVs land before anything is built on top. They do.

**Atlas regions**, read from each mesh's UVs rather than eyeballed:

| Brand | Atlas pixels (2048x2048) |
|---|---|
| ApolloSoyuz | x 1471-1699, y 1886-2046 |
| Malboro | x 1815-2040, y 565-754 |
| Strike | x 1946-2048, y 1040-1352 |
| Wilston | x 1816-2041, y 722-910 |

**Two orientation traps.** UnityPy writes the OBJ Z-up, so asking Blender to
convert from Y-up lays the pack on its back. And BSG authored the meshes with
-Z as up, so the artwork imports upside down; a 180 degree roll about Y rights
it while keeping the printed face pointing the same way. Both are handled in
`preview_authentic.py`.

BSG's packs measure 60.6 x 27.3 x 94.8 mm, noticeably larger than the real
55 x 22 x 85 the generator uses.

### bake_pack_textures.py

```
python bake_pack_textures.py --assets ./out --scale 4
```

Crops each pack's artwork out of the atlas, upscales it 4x with Lanczos, and
writes `<Brand>_albedo.png` plus `pack_uvs.json`. The generator picks those up
automatically and skins the packs with them; without them it falls back to the
flat placeholder colours.

BSG's pack proportions are deliberately **not** copied. Those meshes are barter
props that never reach the player's hands, so only the artwork is worth taking.

Source faces are tiny - the fronts are around 76x118 px - which is why the
upscale matters. Lanczos keeps the lettering legible where nearest would just
enlarge the pixels and bilinear would smear them.

The mapping records, per face, its UV rect and which local axis drives u and v,
so artwork laid out one way on a 60.6 x 27.3 x 94.8 mm prop lands correctly on
a 55 x 22 x 85 mm pack.

**Two conventions worth knowing**, both settled by rendering rather than by
reasoning - handedness arguments got them wrong twice:

- The vertices are never mirrored to correct BSG's -Z-up. Mirroring reverses
  handedness, which silently inverts the flip detection. The flip is applied in
  two narrow places instead: naming the face, and sampling vertical position.
- `u_flip` is stored **inverted**, because BSG's horizontal axis runs opposite
  to the generated box's.

The generator applies UVs *before* the bevel, so the bevel's new faces inherit
them by interpolation, and it normalises positions against the whole pack
height, so the body and lid pick up the correct lower and upper portions of the
same artwork with no explicit splitting.

### build_pack_sheets.py

```
python build_pack_sheets.py --src "./out/upscaled textures" --assets ./out
```

Builds the packs from hand-supplied artwork instead of the extracted game
atlas. Run whichever of the two you want last - both write `pack_uvs.json`, and
the generator uses whatever is there.

The supplied images are photographs and dielines, not UV unwraps, so panels are
cropped out by rectangle and reassembled into a fixed layout:

```
+------------------+--------+
|      front       |  side  |   row 1, pack height
+------------------+--------+
|       top        | bottom |   row 2, pack depth
+------------------+--------+
```

Front is reused for the back, and side for both sides, with `u_flip` set on the
back and one side so the artwork wraps round the corner rather than mirroring.
Real packs are near enough symmetrical, and in first person the back is never
seen.

The crop rectangles in `SOURCES` were picked by eye and then checked by cropping
them out and looking - the first pass clipped the "Marlboro" wordmark and cut
"APOLLO GOLD3" off at the bottom.

Two sources are missing panels, handled rather than ignored: the Apollo packs
are photographed from above so no side is visible, and its side is stretched
from a patch of the front's plain card; Winston has no usable top, so its top is
filled with the average colour of the front's upper strip.

## Tuning

The constants at the top of `make_cigarette_model.py` are the whole interface:
pack dimensions, wall thickness, cigarette and filter length, row layout, bevel,
cylinder sides, and the brand table. `BRANDS` carries each pack's colour
alongside its EFT template id, so the models and the server config cannot drift
apart unnoticed.
