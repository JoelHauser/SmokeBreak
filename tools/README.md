# tools

## make_cigarette_model.py

Generates the in-hands models and exports an FBX for Unity 2022.3.

```
blender --background --python make_cigarette_model.py -- --out C:/temp/cigs.fbx
```

Needs Blender 4.2 LTS or similar. Nothing else.

Three objects come out, so you can decide what the hands hold:

| Object | Size | Notes |
|---|---|---|
| `Cigarette_Single` | 8 x 8 x 84 mm | paper and filter on separate material slots; origin at the filter |
| `Cigarette_Pack` | 55 x 22 x 65 mm | origin at the base centre |
| `Pack_Lid` | 55 x 22 x 20 mm | origin on the hinge, so opening it is one X rotation |

Everything is authored in real millimetres and exported in metres. In Unity the
import inspector should show **File Scale 1**. If it shows 0.01, the export
scale options did not apply and the model will be a hundredth of its size.

Colours are flat placeholders. UVs are unwrapped and ready for real textures.

### Tuning

The constants at the top of the script are the whole interface - pack
dimensions, cigarette length, filter length, bevel width, cylinder sides and
colours. Change and re-run; it takes a second.
