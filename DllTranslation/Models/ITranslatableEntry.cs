namespace DllTranslation.Models;

public interface ITranslatableEntry
{
    string Text { get; }
    string Hash { get; }
    string GetContext(string relativePath);
}
