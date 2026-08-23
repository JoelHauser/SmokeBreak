using SPTarkov.Server.Core.Models.Spt.Mod;

namespace SmokeBreak
{
    public record SmokeBreakMetadata : IModMetadata
    {
        public string ModGuid { get; init; } = "com.mybutthasarash.smokebreak";
        public string Name { get; init; } = "Smoke Break";
        public string Author { get; init; } = "JoelHauser";
        public List<string>? Contributors { get; init; }
        public SemanticVersioning.Version Version { get; init; } = new("0.2.0");
        public SemanticVersioning.Range SptVersion { get; init; } = new("~4.1.0");
        public bool HasPrepatcher { get; init; } = false;
        public List<string>? Incompatibilities { get; init; }
        public Dictionary<string, SemanticVersioning.Range>? ModDependencies { get; init; }
        public string? Url { get; init; } = "https://github.com/JoelHauser/SmokeBreak";
        public string License { get; init; } = "MIT";
    }
}
