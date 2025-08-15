using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;
using DllTranslation.Utilities;

namespace DllTranslation.Services;

public class CsEntryLoader : IEntryLoader
{
    private readonly bool _literalsOnly;

    public CsEntryLoader(bool literalsOnly)
    {
        _literalsOnly = literalsOnly;
    }

    public async Task<ConcurrentDictionary<
        string,
        IReadOnlyList<ITranslatableEntry>
    >?> LoadEntriesAsync(DirectoryInfo directory, CancellationToken cancellationToken)
    {
        var sourceData = await ParserUtility.AnalyzeDirectoryAsync(
            directory,
            _literalsOnly,
            cancellationToken
        );

        if (sourceData == null)
        {
            return null;
        }

        // Since IReadOnlyList<T> is covariant, we can cast directly.
        // This is more efficient than creating a new dictionary and lists.
        return new ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>>(
            sourceData.Select(
                kvp =>
                    new KeyValuePair<string, IReadOnlyList<ITranslatableEntry>>(kvp.Key, kvp.Value)
            )
        );
    }
}
