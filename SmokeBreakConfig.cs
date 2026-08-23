using System.Text.Json.Serialization;

namespace SmokeBreak
{
    internal class SmokeBreakConfig
    {
        [JsonPropertyName("enabled")]
        public bool Enabled { get; set; } = true;

        /// <summary>Seconds the smoke animation runs. Vanilla food sits between 2 and 9.</summary>
        [JsonPropertyName("useTimeSeconds")]
        public double UseTimeSeconds { get; set; } = 6;

        /// <summary>Uses per pack. 1 consumes the whole pack in one go.</summary>
        [JsonPropertyName("smokesPerPack")]
        public int SmokesPerPack { get; set; } = 20;

        [JsonPropertyName("effects")]
        public SmokeEffects Effects { get; set; } = new();

        /// <summary>Sound key. "generic" is what cigarettes already use.</summary>
        [JsonPropertyName("itemSound")]
        public string ItemSound { get; set; } = "generic";

        /// <summary>
        /// In-hands model used while smoking. Cigarettes ship with an EMPTY UsePrefab
        /// because they were never consumable, and an empty one breaks the hands
        /// outright. Must point at a prefab under usable_items, which are the ones
        /// rigged for the hands controller - the cigarette's own Prefab is an
        /// inventory model and is not a valid substitute.
        /// </summary>
        [JsonPropertyName("useInHandsPrefab")]
        public string UseInHandsPrefab { get; set; } =
            "assets/content/weapons/usable_items/item_energy_bar/item_slickers_container.bundle";

        /// <summary>Name of a buff defined in globals. Empty means no buff (see README).</summary>
        [JsonPropertyName("stimulatorBuffs")]
        public string StimulatorBuffs { get; set; } = "";

        [JsonPropertyName("cigaretteIds")]
        public List<string> CigaretteIds { get; set; } = new();
    }

    internal class SmokeEffects
    {
        /// <summary>Energy is satiety in EFT. Nicotine blunting hunger reads as a small gain.</summary>
        [JsonPropertyName("energy")]
        public double Energy { get; set; } = 5;

        [JsonPropertyName("hydration")]
        public double Hydration { get; set; } = -3;
    }
}
