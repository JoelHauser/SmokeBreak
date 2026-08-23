# Smoke Break

Makes EFT's cigarettes smokable. Server mod plus client plugin for **SPT 4.1.x**.

Cigarettes ship as barter items with no consumable properties at all — you can
sell them and nothing else. This mod makes all four packs usable, gives smoking
a real trade-off, and puts an actual cigarette pack in your hands.

---

## Status — 0.3.0

| Feature | State |
|---|---|
| All four packs consumable | **working**, verified in game |
| 20 smokes per pack, resource bar | **working** |
| Buff: calm at the cost of wind | **working**, verified on a live server |
| Pack model in hand | **in progress** — reaches the raid at correct scale, placement being tuned |
| Custom smoking animation | not started, see [Roadmap](#roadmap) |

The animation you see is EFT's own food-eating animation. That is deliberate:
there is no smoking animation in the game, and authoring one is a much larger
job than making the item work.

---

## Installing

1. Stop the server.
2. Extract `dist/SmokeBreak-0.3.0-SPT4.1.x.zip` into your SPT folder.
3. Build the client plugin (see [Building](#building)) — it deploys itself and
   the bundles to `BepInEx/plugins/SmokeBreak/`.
4. Start the server. **Smoke Break** should appear in the mod list.

### Requirement

`simulateItemsBeingTaken` must be `true` in
`SPT_Runtime/SPT_Data/configs/insurance.json`. It is by default. The server
console warns you at startup if it is not.

---

## What it changes

For each of the four cigarette packs:

| Property | Value | Why |
|---|---|---|
| `_parent` | `5448e8d04bdc2ddf718b4569` | the Food/Drink node, which is what makes it consumable |
| `UsePrefab` | a vanilla usable_items container | hands, animator and animation, borrowed from a real item |
| `FoodUseTime` | 9 | matches the borrowed animation's length |
| `MaxResource` | 20 | smokes per pack, shown as a resource bar |
| `EffectsHealth` | Energy +5, Hydration −3 | nicotine blunting hunger, at a cost |
| `StimulatorBuffs` | `Buffs_SmokeBreak` | see below |

`AnimationVariantsNumber` is deliberately untouched — all 22 vanilla food items
sit at 0, which is what cigarettes already carry.

### The buff

Registered into globals and referenced by the packs. Two minutes, starting two
seconds in:

| Effect | Value | Role |
|---|---|---|
| `SkillRate` / StressResistance | +1 | the calm |
| `StaminaRate` | −1 | the cost |
| `MaxStamina` | −10 | the cost |

`HandsTremor` looks like the obvious choice for a calming item and does the
opposite — every vanilla use of it is `Value: 0` with a long `Delay`, which is
the pattern for a stim's *after-effect* tremor. Using it would make smoking
shake your hands.

---

## Configuration

`config/config.json`, applied at server start. The defaults are tuned and need
no changes.

| Setting | Effect |
|---|---|
| `enabled` | `false` leaves cigarettes as barter items |
| `useTimeSeconds` | Animation length. Must match the borrowed prefab's clip |
| `smokesPerPack` | Uses per pack. `1` consumes the whole pack at once |
| `effects.energy` / `.hydration` | Applied per smoke |
| `itemSound` | `generic`, `food_snack` and `drink` all exist |
| `useInHandsPrefab` | Which vanilla container to borrow hands and animation from |
| `inHandsPrefabs` | Per-item model override, by template id |
| `buff.*` | The buff group. Empty `entries` plus a vanilla name reuses that group |
| `cigaretteIds` | The four packs. Add ids to convert more items |

---

## Repository layout

```
SmokeBreak.csproj          server mod (net10.0)
SmokeBreak*.cs             server mod source
config/config.json         runtime configuration

client/                    BepInEx client plugin (net472)
  SmokeBreakPlugin.cs      swaps the held model at runtime

bundles/smokebreak/        built AssetBundles, Unity 2022.3.43f1
bundles.json               unused, kept for reference — see below

tools/                     the asset pipeline, all headless
  make_cigarette_model.py  generates the pack models in Blender
  preview_render.py        renders them, so they can be checked by eye
  extract_cig_textures.py  pulls the game's shared texture atlas
  trace_cig_materials.py   finds which bundle owns a material
  bake_pack_textures.py    crops and upscales pack art from the atlas
  build_pack_sheets.py     builds textures from hand-supplied artwork
  analyse_pack_uvs.py      works out BSG's per-face UV layout
  extract_skeleton.py      exports EFT's character rig
  build_armature.py        rebuilds that rig as a Blender armature
  preview_obj.py           renders any extracted OBJ with a texture
  out/                     everything the pipeline produced

dist/                      release archives
```

**Nothing is gitignored.** The generated models, extracted game assets, baked
textures, render previews, built bundles and release archives are all committed,
so the work can be inspected without running anything.

---

## Building

### Server mod

```
dotnet build -c Release -p:SPTPath="H:\SPT4.1.X"
```

Add `-p:DeployToSPT=true` to install, or `-t:PackageRelease` for a zip.
**Requires a .NET 10 SDK** — the mod targets `net10.0`, because the 4.1 server
does.

### Client plugin

```
cd client
dotnet build -c Release -p:SPTPath="H:\SPT4.1.X" -p:DeployToSPT=true
```

Targets `net472`. Deploys the DLL and the bundles to
`BepInEx/plugins/SmokeBreak/`.

### Models

```
blender --background --python tools/make_cigarette_model.py -- --out tools/out --assets tools/out
blender --background --python tools/preview_render.py     -- --out tools/out/preview.png
```

Blender 4.x or 5.x. See [`tools/README.md`](tools/README.md) for the pipeline in
detail — it documents the extraction, the UV transfer, and several traps that
cost real time.

### Bundles

Unity **2022.3.43f1**, exactly — hash `85497d293fa1`, matching the game's
`UnityPlayer.dll`. A different version will not load.

```
Unity.exe -batchmode -quit -projectPath <proj> -executeMethod SmokeBreakBuild.Build -logFile -
```

---

## Why the model swap is client-side

Worth writing down, because it is not obvious and it cost an evening.

A `UsePrefab` bundle is **not a model**. EFT's own
`item_slickers_container.bundle` holds 131 GameObjects: both arms, every finger
joint, an `AnimatorController`, three `AnimationClip`s, twenty `LActionState`
behaviours and a `UsableHandsPrefab` component. It is a complete hands package.

Shipping a bare mesh as a `UsePrefab` makes the client hang at *"starting local
game"* — silently, with no error, waiting for parts that are not there.

So the server mod points `UsePrefab` at a **real** vanilla container, and the
hands and animation stay BSG's. The client plugin then hides the borrowed item's
renderers and mounts our pack in its place. EFT never treats our bundle as a
hands prefab, so that failure cannot recur.

`bundles.json` is kept for reference but is unused — SPT's bundle pipeline is
not involved at all.

---

## Roadmap

The target is an FDDA-style sequence: take the pack out, flip the lid, knock a
cigarette up, take it, light it, smoke it, flick it away.

**Done.** Consumable items and the buff. Four textured packs with hinged lids
and twenty cigarettes each, plus an independently animatable "hero" cigarette
for the knock-up beat. A loose cigarette. The Crickent lighter, extracted from
the game. And EFT's character rig rebuilt as a Blender armature
(`tools/out/eft_rig.blend`) — 79 bones with IK targets, bend goals and
`Weapon_root`.

**Remaining.** Placement tuning for the held pack; smoke particles and an ember;
and the animation itself, a two-handed sequence that needs a person with a
viewport. Every prop and the rig are ready for whoever does it.

---

## Credits

Cigarette artwork derives from the game's own `scrap_d` atlas and from supplied
reference images. The character rig, lighter and container prefabs are
Battlestate Games' assets, read from a local install.

MIT licensed — see [LICENSE](LICENSE).
