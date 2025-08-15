using System;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text.Json;
using DllTranslation.Models;
using DllTranslation.Utilities;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace DllTranslation.Utilities;

public static class LoadUtility
{
    private static readonly string obsoleteDirName = "obsolete";

    public static async Task<
        Dictionary<string, Dictionary<string, ParatranzEntry>>
    > LoadParatranzDirAsync(
        DirectoryInfo oldTransDir,
        string subFolder,
        CancellationToken cancellationToken
    )
    {
        Console.WriteLine("📂 读取翻译目录");

        // TODO: we need a better way to handle this, like remove the extension
        string extension = "";
        if (subFolder == "cs")
            extension = ".cs";
        else if (subFolder == "asset")
            extension = ".json";

        // 1. 读取旧翻译数据
        var oldTranslations = new Dictionary<string, Dictionary<string, ParatranzEntry>>();
        var csDir = oldTransDir
            .GetDirectories(subFolder, SearchOption.AllDirectories)
            .FirstOrDefault();
        if (csDir is not null && csDir.Exists)
        {
            foreach (
                var file in csDir
                    .GetFiles("*.json", SearchOption.AllDirectories)
                    .Where(x => !x.DirectoryName!.Contains(obsoleteDirName))
            )
            {
                var relativePath = Path.ChangeExtension(
                    file.FullName.Substring(csDir.FullName.Length + 1),
                    extension
                );
                oldTranslations[relativePath] = new Dictionary<string, ParatranzEntry>();
                try
                {
                    var json = await File.ReadAllTextAsync(file.FullName, cancellationToken);
                    var entries = JsonSerializer.Deserialize<List<ParatranzEntry>>(
                        json,
                        new JsonSerializerOptions { PropertyNameCaseInsensitive = true }
                    );
                    if (entries != null)
                    {
                        foreach (var entry in entries)
                        {
                            oldTranslations[relativePath][entry.Key] = entry;
                        }
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"❌ 读取翻译文件 {file.Name} 失败: {ex.Message}");
                }
            }
        }

        return oldTranslations;
    }
}
