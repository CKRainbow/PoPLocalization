using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;

namespace DllTranslation.Services;

public interface IEntryLoader
{
    Task<ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>>?> LoadEntriesAsync(
        DirectoryInfo directory,
        CancellationToken cancellationToken
    );
}
