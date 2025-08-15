using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;

namespace DllTranslation.Services;

public class AssetEntryLoader : IEntryLoader
{
    public async Task<ConcurrentDictionary<
        string,
        IReadOnlyList<ITranslatableEntry>
    >?> LoadEntriesAsync(DirectoryInfo directory, CancellationToken cancellationToken)
    {
        if (!directory.Exists)
        {
            await Console.Error.WriteLineAsync($"❌ Directory does not exist: {directory.FullName}");
            return null;
        }

        var jsonFiles = directory.GetFiles("*.json", SearchOption.AllDirectories);
        if (!jsonFiles.Any())
        {
            Console.WriteLine("⚠ No .json files found in the directory.");
            return null;
        }

        var allAssetEntries = new ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>>();
        var jsonOptions = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

        await Parallel.ForEachAsync(
            jsonFiles,
            cancellationToken,
            async (file, ct) =>
            {
                try
                {
                    var json = await File.ReadAllTextAsync(file.FullName, ct);
                    var entries = JsonSerializer.Deserialize<List<AssetEntry>>(json, jsonOptions);
                    Console.WriteLine(file.FullName);
                    if (entries != null && entries.Any())
                    {
                        // We cast List<AssetEntry> to IReadOnlyList<ITranslatableEntry>
                        allAssetEntries.TryAdd(
                            file.FullName,
                            entries.Cast<ITranslatableEntry>().ToList()
                        );
                    }
                }
                catch (Exception ex)
                {
                    await Console.Error.WriteLineAsync(
                        $"❌ Error reading or deserializing file {file.FullName}: {ex.Message}"
                    );
                }
            }
        );

        if (cancellationToken.IsCancellationRequested)
            return null;

        Console.WriteLine($"✅ Loaded {allAssetEntries.Count} asset files.");
        return allAssetEntries;
    }
}
