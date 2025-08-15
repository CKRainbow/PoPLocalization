namespace DllTranslation.Models;

public record StatementEntry(
    string Text,
    string Hash,
    int StartPosition,
    int Length,
    string? ContainingMethod,
    int StartLine
) : ITranslatableEntry
{
    public string GetContext(string relativePath)
    {
        return $"File: {relativePath}:{StartLine}\nMethod: {ContainingMethod}\nPosition: {StartPosition}\nLength: {Length}";
    }
}
