using System.Reflection;
using SPTarkov.Common.Models.Logging;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Helpers.Server;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common.Tables;
using SPTarkov.Server.Core.Models.Enums;
using SPTarkov.Server.Core.Models.Spt.Tables;

namespace SmokeBreak
{
    /// <summary>
    /// Turns the four cigarette packs into consumables so they can be smoked.
    ///
    /// Cigarettes ship as barter items under the "Other" node with no food
    /// properties at all. Reparenting them onto the Food/Drink node and filling in
    /// the food schema is enough for the client to build them as consumable items,
    /// at which point EFT plays its existing hand-to-mouth animation. No bundle and
    /// no custom animation are involved - that comes later.
    ///
    /// Runs well before OnLoadOrder.SaveCallbacks (600000). SPT 4.1.3 snapshots the
    /// item table at that point and throws DatabaseModifiedAfterCutoffException if
    /// items appear afterwards. Only existing items are edited here, but staying
    /// ahead of the cutoff keeps it clearly safe.
    /// </summary>
    [Injectable(TypePriority = OnLoadOrder.GameCallbacks)]
    public class SmokeBreakMod(
        ModHelper modHelper,
        TemplateTable templateTable,
        ISptLogger<SmokeBreakMod> logger) : IOnLoad
    {
        /// <summary>The Food/Drink node every consumable hangs off.</summary>
        private static readonly MongoId FoodDrinkNode = new("5448e8d04bdc2ddf718b4569");

        public Task OnLoadAsync(CancellationToken cancellationToken)
        {
            var path = System.IO.Path.Combine(modHelper.GetAbsolutePathToModFolder(Assembly.GetExecutingAssembly()), "config");
            var config = modHelper.GetJsonDataFromFile<SmokeBreakConfig>(path, "config.json");

            if (config is null || !config.Enabled)
            {
                logger.Info("[SmokeBreak] disabled via config; cigarettes remain barter items.");
                return Task.CompletedTask;
            }

            if (config.CigaretteIds.Count == 0)
            {
                logger.Warning("[SmokeBreak] cigaretteIds is empty, so nothing was changed.");
                return Task.CompletedTask;
            }

            var converted = 0;
            foreach (var rawId in config.CigaretteIds)
            {
                var id = new MongoId(rawId);
                if (!templateTable.Items.TryGetValue(id, out var item) || item?.Properties is null)
                {
                    logger.Warning($"[SmokeBreak] item '{rawId}' is not in the item table and was skipped.");
                    continue;
                }

                item.Parent = FoodDrinkNode;

                var props = item.Properties;
                props.FoodUseTime = config.UseTimeSeconds;
                props.FoodEffectType = "afterUse";
                props.MaxResource = config.SmokesPerPack;
                props.StimulatorBuffs = config.StimulatorBuffs;

                // Energy and Hydration are the two factors vanilla food uses.
                props.EffectsHealth = new Dictionary<HealthFactor, EffectsHealthProperties>
                {
                    [HealthFactor.Energy] = new() { Value = config.Effects.Energy },
                    [HealthFactor.Hydration] = new() { Value = config.Effects.Hydration }
                };

                // Present and empty on every vanilla food item; a null here is not worth risking.
                props.EffectsDamage ??= new Dictionary<DamageEffectType, EffectsDamageProperties>();

                // The break that made this necessary: cigarettes carry an empty
                // UsePrefab, so the hands controller has no model to instantiate and
                // the player's hands break on use. Vanilla food all points at a
                // usable_items prefab; borrowing one is what makes them usable at all.
                if (!string.IsNullOrWhiteSpace(config.UseInHandsPrefab))
                {
                    props.UsePrefab = new Prefab { Path = config.UseInHandsPrefab, Rcid = "" };
                }
                else
                {
                    logger.Warning($"[SmokeBreak] useInHandsPrefab is empty, so {item.Name} keeps its blank UsePrefab and WILL break the player's hands when used.");
                }

                if (!string.IsNullOrWhiteSpace(config.ItemSound))
                {
                    props.ItemSound = config.ItemSound;
                }

                // AnimationVariantsNumber is deliberately left alone. Every vanilla
                // food item sits at 0, which is what cigarettes already carry.

                converted++;
                logger.Debug($"[SmokeBreak] {item.Name} ({rawId}) is now consumable.");
            }

            logger.Info($"[SmokeBreak] {converted} of {config.CigaretteIds.Count} cigarette pack(s) made smokable - {config.SmokesPerPack} smoke(s) per pack, {config.UseTimeSeconds}s each, energy {config.Effects.Energy:+0;-0}, hydration {config.Effects.Hydration:+0;-0}.");
            return Task.CompletedTask;
        }
    }
}
