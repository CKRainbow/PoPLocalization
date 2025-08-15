using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;
using DllTranslation.Utilities;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace DllTranslation.Services;

public class TranslationUpdater
{
    public Dictionary<string, Dictionary<string, ParatranzEntry>> oldTranslations;
    public ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>> newSourceData;
    public Dictionary<string, List<ParatranzEntry>> newTranslations;

    private TranslationUpdater(
        ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>> newSourceData,
        Dictionary<string, Dictionary<string, ParatranzEntry>> oldTranslations
    )
    {
        this.newSourceData = newSourceData;
        this.oldTranslations = oldTranslations;

        newTranslations = new Dictionary<string, List<ParatranzEntry>>();
    }

    public static async Task<TranslationUpdater> CreateAsync(
        ConcurrentDictionary<string, IReadOnlyList<ITranslatableEntry>> newSourceData,
        DirectoryInfo oldTransDir,
        string subFolder,
        CancellationToken cancellationToken
    )
    {
        var oldTranslations = await LoadUtility.LoadParatranzDirAsync(
            oldTransDir,
            subFolder,
            cancellationToken
        );
        return new TranslationUpdater(newSourceData, oldTranslations);
    }

    private string GetWeakHash(string text)
    {
        return HashUtility.ComputeSha256Hash(text);
    }

    private List<ParatranzEntry> MatchEntries(
        string relativePath,
        IReadOnlyList<ITranslatableEntry> newEntries,
        Dictionary<string, ParatranzEntry> oldEntries,
        out HashSet<string> usedOldKeys
    )
    {
        var matchedEntries = new List<ParatranzEntry>();
        usedOldKeys = new HashSet<string>();

        var oldEntriesByWeakHash = oldEntries
            .Values.ToLookup(e => GetWeakHash(e.Original))
            .ToDictionary(g => g.Key, g => g.ToList());

        foreach (var newEntry in newEntries)
        {
            // 1. 尝试用强哈希直接匹配
            if (
                !usedOldKeys.Contains(newEntry.Hash)
                && oldEntries.TryGetValue(newEntry.Hash, out var exactMatch)
            )
            {
                matchedEntries.Add(
                    exactMatch with
                    {
                        Key = newEntry.Hash,
                        Original = newEntry.Text,
                        Context = newEntry.GetContext(relativePath)
                    }
                );
                usedOldKeys.Add(newEntry.Hash);
                continue;
            }

            // 2. 强哈希失败，尝试用弱哈希（原文）进行模糊匹配
            var weakHash = GetWeakHash(newEntry.Text);
            if (oldEntriesByWeakHash.TryGetValue(weakHash, out var candidates))
            {
                ParatranzEntry? bestMatch = null;
                foreach (var candidate in candidates)
                {
                    if (!usedOldKeys.Contains(candidate.Key))
                    {
                        bestMatch = candidate;
                        break;
                    }
                }

                if (bestMatch != null)
                {
                    var stage = bestMatch.Stage;
                    if (bestMatch.Stage != 0)
                    {
                        stage = 2;
                    }
                    matchedEntries.Add(
                        bestMatch with
                        {
                            Key = newEntry.Hash, // 使用新的强哈希作为Key
                            Original = newEntry.Text,
                            Context = newEntry.GetContext(relativePath),
                            Stage = stage // 标记为模糊匹配
                        }
                    );
                    usedOldKeys.Add(bestMatch.Key);
                    continue;
                }
            }

            // 3. 完全没找到，作为新条目
            matchedEntries.Add(
                new ParatranzEntry(
                    Key: newEntry.Hash,
                    Original: newEntry.Text,
                    Translation: "",
                    Stage: 0,
                    Context: newEntry.GetContext(relativePath)
                )
            );
        }

        return matchedEntries;
    }

    public async Task UpdateTranslationAsync(
        DirectoryInfo newSrcDir,
        DirectoryInfo outputDir,
        CancellationToken cancellationToken
    )
    {
        var newTranslations = new ConcurrentDictionary<string, List<ParatranzEntry>>();
        var obsoleteEntries = new Dictionary<string, List<ParatranzEntry>>();
        var allUsedOldKeys = new ConcurrentDictionary<string, HashSet<string>>();

        int migratedCount = 0;
        int newCount = 0;

        // 并行处理每个文件
        Parallel.ForEach(
            newSourceData,
            fileEntry =>
            {
                var relativePath = Path.GetRelativePath(newSrcDir.FullName, fileEntry.Key);
                oldTranslations.TryGetValue(relativePath, out var oldFileEntries);
                oldFileEntries ??= new Dictionary<string, ParatranzEntry>();

                var matched = MatchEntries(
                    relativePath,
                    fileEntry.Value,
                    oldFileEntries,
                    out var usedKeys
                );

                // 更新统计数据
                Interlocked.Add(ref migratedCount, usedKeys.Count);
                Interlocked.Add(ref newCount, matched.Count - usedKeys.Count);

                newTranslations[relativePath] = matched;
                allUsedOldKeys.TryAdd(relativePath, usedKeys);
            }
        );

        // 计算过时条目
        foreach (var oldFile in oldTranslations)
        {
            var relativePath = oldFile.Key;
            var oldFileEntries = oldFile.Value;

            if (allUsedOldKeys.TryGetValue(relativePath, out var usedKeys))
            {
                var obsolete = oldFileEntries
                    .Where(kvp => !usedKeys.Contains(kvp.Key))
                    .Select(kvp => kvp.Value)
                    .ToList();
                if (obsolete.Any())
                {
                    obsoleteEntries[relativePath] = obsolete;
                }
            }
            else // 如果新数据里完全没有这个文件，那整个旧文件都是过时的
            {
                obsoleteEntries[relativePath] = oldFileEntries.Values.ToList();
            }
        }

        int obsoleteCount = obsoleteEntries.Values.Sum(x => x.Count);
        this.newTranslations = newTranslations.ToDictionary(kv => kv.Key, kv => kv.Value);

        // 5. 写入更新后的翻译文件
        if (outputDir.Exists)
        {
            outputDir.Delete(true);
        }
        outputDir.Create();

        var jsonOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        };

        // 写入主要翻译文件
        foreach (var entry in newTranslations)
        {
            var outputPath = Path.ChangeExtension(
                Path.Combine(outputDir.FullName, entry.Key),
                ".json"
            );
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            var json = JsonSerializer.Serialize(entry.Value, jsonOptions);
            await File.WriteAllTextAsync(outputPath, json, cancellationToken);
        }

        // 写入过时条目文件
        if (obsoleteCount > 0)
        {
            var obsoleteDir = Path.Combine(outputDir.FullName, "obsolete");
            foreach (var entry in obsoleteEntries)
            {
                var obsoletePath = Path.ChangeExtension(
                    Path.Combine(obsoleteDir, entry.Key),
                    ".json"
                );
                Directory.CreateDirectory(Path.GetDirectoryName(obsoletePath)!);
                await File.WriteAllTextAsync(
                    obsoletePath,
                    JsonSerializer.Serialize(entry.Value, jsonOptions),
                    cancellationToken
                );
            }
        }

        Console.WriteLine($"✅ 翻译更新完成！迁移: {migratedCount}, 新增: {newCount}, 过时: {obsoleteCount}");
    }

    public static async Task UpdateTranslationsCommandAsync(
        DirectoryInfo oldTransDir,
        DirectoryInfo newSrcDir,
        DirectoryInfo outputDir,
        IEntryLoader entryLoader,
        string subFolder,
        CancellationToken cancellationToken
    )
    {
        Console.WriteLine("🔄 开始更新翻译...");

        // 2. Use the provided loader to extract new source data
        var newSourceData = await entryLoader.LoadEntriesAsync(newSrcDir, cancellationToken);

        if (
            newSourceData == null
            || !newSourceData.Any()
            || cancellationToken.IsCancellationRequested
        )
        {
            Console.WriteLine("⚠ 未提取到新数据，更新终止");
            return;
        }

        var updater = await CreateAsync(newSourceData, oldTransDir, subFolder, cancellationToken);

        await updater.UpdateTranslationAsync(newSrcDir, outputDir, cancellationToken);
    }
}
