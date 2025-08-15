using System.Text.Json.Serialization;

namespace DllTranslation.Models;

public record AssetEntry : ITranslatableEntry
{
    [JsonPropertyName("original")]
    public string Text { get; init; } = "";

    [JsonPropertyName("key")]
    public string Hash { get; init; } = "";

    [JsonPropertyName("context")]
    public string FullContext { get; init; } = "";

    public string GetContext(string relativePath)
    {
        // The context from the JSON file already contains all necessary info,
        // including the original file name.
        return FullContext;
    }
}
