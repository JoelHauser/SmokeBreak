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
        GlobalTable globalTable,
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

            var buffName = RegisterBuff(config);

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
                props.StimulatorBuffs = buffName;

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
                // Each brand now has its own pack model shipped in this mod's
                // bundles; the borrowed chocolate bar is only the fallback for
                // anything not listed.
                if (!config.InHandsPrefabs.TryGetValue(rawId, out var inHands) || string.IsNullOrWhiteSpace(inHands))
                {
                    inHands = config.UseInHandsPrefab;
                }

                if (!string.IsNullOrWhiteSpace(inHands))
                {
                    props.UsePrefab = new Prefab { Path = inHands, Rcid = "" };
                }
                else
                {
                    logger.Warning($"[SmokeBreak] no in-hands prefab for {item.Name}, so it keeps its blank UsePrefab and WILL break the player's hands when used.");
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

        /// <summary>
        /// Writes the configured buff group into globals and returns the name to put
        /// on each cigarette. Returns "" when buffs are off, which is a valid value
        /// for StimulatorBuffs - every vanilla food item that has no buff uses it.
        ///
        /// A named group with no entries is left alone deliberately: that is how you
        /// point cigarettes at an existing vanilla buff group without redefining it.
        /// </summary>
        private string RegisterBuff(SmokeBreakConfig config)
        {
            var buff = config.Buff;
            if (buff is null || !buff.Enabled || string.IsNullOrWhiteSpace(buff.Name))
            {
                return "";
            }

            if (buff.Entries.Count == 0)
            {
                logger.Info($"[SmokeBreak] referencing existing buff group '{buff.Name}'; no entries defined.");
                return buff.Name;
            }

            var buffs = globalTable.Configuration?.Health?.Effects?.Stimulator?.Buffs;
            if (buffs is null)
            {
                logger.Warning("[SmokeBreak] globals has no stimulator buff table, so no buff was registered.");
                return "";
            }

            buffs[buff.Name] = buff.Entries.Select(e => new Buff
            {
                BuffType = e.BuffType,
                Chance = e.Chance,
                Delay = e.Delay,
                Duration = e.Duration,
                Value = e.Value,
                AbsoluteValue = e.AbsoluteValue,
                SkillName = e.SkillName ?? ""
            }).ToList();

            var summary = string.Join(", ", buff.Entries.Select(e =>
                $"{e.BuffType}{(string.IsNullOrWhiteSpace(e.SkillName) ? "" : $"/{e.SkillName}")} {e.Value:+0.##;-0.##} for {e.Duration:0}s"));
            logger.Info($"[SmokeBreak] registered buff '{buff.Name}': {summary}");

            return buff.Name;
        }
    }
}
