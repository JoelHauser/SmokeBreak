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

## Tuning

The constants at the top of `make_cigarette_model.py` are the whole interface:
pack dimensions, wall thickness, cigarette and filter length, row layout, bevel,
cylinder sides, and the brand table. `BRANDS` carries each pack's colour
alongside its EFT template id, so the models and the server config cannot drift
apart unnoticed.
