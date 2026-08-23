# Smoke Break

Makes EFT's four cigarette packs smokable. Server mod for SPT 4.1.x.

## Status

**0.2.0 — cigarettes are consumable and carry a buff. Visuals are still placeholder.**

Cigarettes ship as barter items under the "Other" node with no consumable
properties at all. This mod reparents them onto the Food/Drink node and fills in
the food schema, which is enough for the client to build them as consumables.

Using one plays **EFT's existing hand-to-mouth consume animation** — the same
one used for food and drink. There is no smoking animation in the game; a search
of `Assembly-CSharp` turns up nothing for "smok" beyond smoke grenades, muzzle
smoke and BTR exhaust, and no cigarette strings at all. A real smoking animation
means authoring a clip and shipping it in an AssetBundle, which is a later step.

So: functional now, visually a placeholder.

## What it changes

For each cigarette pack:

| Property | Value | Why |
|---|---|---|
| `_parent` | `5448e8d04bdc2ddf718b4569` | the Food/Drink node |
| `FoodUseTime` | 6 | vanilla food sits between 2 and 9 |
| `FoodEffectType` | `afterUse` | matches every vanilla food item |
| `MaxResource` | 20 | smokes per pack, shown as a resource bar |
| `EffectsHealth` | Energy +5, Hydration -3 | see below |
| `EffectsDamage` | empty | present and empty on all vanilla food |
| `ItemSound` | `generic` | what cigarettes already carry |

`AnimationVariantsNumber` is deliberately untouched. All 22 vanilla food items
sit at 0, which is what cigarettes already have.

Energy is satiety in EFT, so a small gain reads as nicotine blunting hunger. The
hydration cost is what stops it being free food.

## Config

`config/config.json`, applied at server start.

| Setting | Effect |
|---|---|
| `enabled` | `false` leaves cigarettes as barter items |
| `useTimeSeconds` | Length of the animation |
| `smokesPerPack` | Uses per pack. `1` consumes the whole pack at once |
| `effects.energy` / `effects.hydration` | Applied per smoke |
| `itemSound` | `generic`, `food_snack` and `drink` all exist |
| `buff.enabled` | `false` for no buff at all |
| `buff.name` | Group name written into globals |
| `buff.entries` | The buff itself. Empty entries + a vanilla group name reuses that group |
| `cigaretteIds` | The four packs. Add more item IDs to convert them too |

## The buff

Smoking registers a buff group into globals and points the cigarettes at it.
Defaults, applied 2 seconds in and lasting 2 minutes:

| Effect | Value | Why |
|---|---|---|
| `SkillRate` / StressResistance | +1 | the calming half |
| `StaminaRate` | -1 | the cost |
| `MaxStamina` | -10 | the cost |

Calm at the price of wind. Both halves are tunable in config.

Note `HandsTremor` looks tempting for a calming item but does the opposite: every
vanilla use of it is `Value: 0` with a long `Delay`, which is the pattern for a
stim's *after-effect* tremor rather than tremor removal.

## Known caveats

- **Cigarettes already in your stash** were created without food resource data.
  They should default to a full pack, but if any behave oddly, dropping and
  re-acquiring one is the quick check. Setting `smokesPerPack` to `1` sidesteps
  the resource system entirely.
- **The animation is a drink animation.** That is expected at this stage.
- Runs at `OnLoadOrder.GameCallbacks`, well ahead of the 4.1.3 item-table cutoff
  at `SaveCallbacks`. Only existing items are edited, never added.

## Releases

Release archives are **not** tracked in this repo - `dist/` is gitignored. Build
one with `-t:PackageRelease`. Tracking them means the zip appears and vanishes
as you switch branches, which has already caused a stale archive to be published
once on a sibling project.

Rebuild the archive after **every** fix. `Build` alone updates the installed DLL
but leaves the zip stale.

## Building

```
dotnet build -c Release -p:SPTPath="H:\SPT4.1.X"
```

`-p:DeployToSPT=true` copies into the install, `-t:PackageRelease` builds a zip.
Requires a .NET 10 SDK.
