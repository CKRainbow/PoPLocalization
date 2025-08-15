namespace DllTranslation.Models;

public record ParatranzEntry(
    string Key,
    string Original,
    string Translation,
    int Stage,
    string Context
);
