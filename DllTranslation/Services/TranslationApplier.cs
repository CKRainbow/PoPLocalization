using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;
using DllTranslation.Utilities;
using Microsoft.CodeAnalysis;

namespace DllTranslation.Services;

public partial class TranslationApplier
{
    [GeneratedRegex(
        @"^File: (?<file>.*?):(?<line>\d+)\nMethod: (?<method>.*?)\nPosition: (?<pos>\d+)\nLength: (?<len>\d+)$",
        RegexOptions.Multiline
    )]
    private static partial Regex ContextRegex();

    public Dictionary<
        string,
        List<(StatementEntry Statement, string Translation)>
    > translationsByFile;

    private TranslationApplier(
        Dictionary<string, List<(StatementEntry Statement, string Translation)>> translationsByFile
    )
    {
        this.translationsByFile = translationsByFile;
    }

    public static async Task<TranslationApplier> CreateAsync(
        DirectoryInfo transDir,
        CancellationToken cancellationToken
    )
    {
        // 1. 加载并按文件路径分组翻译
        Console.WriteLine("📂 正在加载并分组翻译文件...");
        var translationsByFile =
            new Dictionary<string, List<(StatementEntry Statement, string Translation)>>();
        var allTransFiles = transDir.GetFiles("*.json", SearchOption.AllDirectories);

        foreach (var file in allTransFiles)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            try
            {
                var json = await File.ReadAllTextAsync(file.FullName, cancellationToken);
                var entries = JsonSerializer.Deserialize<List<ParatranzEntry>>(json);
                if (entries == null)
                    continue;

                foreach (var entry in entries)
                {
                    if (string.IsNullOrEmpty(entry.Translation))
                        continue;

                    var match = ContextRegex().Match(entry.Context);
                    if (!match.Success)
                        continue;

                    var relativePath = match
                        .Groups["file"]
                        .Value.Replace('/', Path.DirectorySeparatorChar);

                    var statement = new StatementEntry(
                        Text: entry.Original,
                        Hash: entry.Key,
                        StartPosition: int.Parse(match.Groups["pos"].Value),
                        Length: int.Parse(match.Groups["len"].Value),
                        ContainingMethod: match.Groups["method"].Value,
                        StartLine: int.Parse(match.Groups["line"].Value)
                    );

                    if (!translationsByFile.TryGetValue(relativePath, out var list))
                    {
                        list = new List<(StatementEntry Statement, string Translation)>();
                        translationsByFile[relativePath] = list;
                    }
                    list.Add((statement, entry.Translation));
                }
            }
            catch (Exception ex)
            {
                await Console.Error.WriteLineAsync($"❌ 读取翻译文件 {file.Name} 失败: {ex.Message}");
            }
        }
        Console.WriteLine($"✅ 成功加载并为 {translationsByFile.Count} 个源文件分组了翻译。");

        return new TranslationApplier(translationsByFile);
    }

    public static TranslationApplier Create(Dictionary<string, List<ParatranzEntry>> translations)
    {
        var translationsByFile =
            new Dictionary<string, List<(StatementEntry Statement, string Translation)>>();
        foreach (var pair in translations)
        {
            var list = new List<(StatementEntry Statement, string Translation)>();
            foreach (var entry in pair.Value)
            {
                if (string.IsNullOrEmpty(entry.Translation))
                    continue;

                var match = ContextRegex().Match(entry.Context);
                if (!match.Success)
                    continue;

                var statement = new StatementEntry(
                    Text: entry.Original,
                    Hash: entry.Key,
                    StartPosition: int.Parse(match.Groups["pos"].Value),
                    Length: int.Parse(match.Groups["len"].Value),
                    ContainingMethod: match.Groups["method"].Value,
                    StartLine: int.Parse(match.Groups["line"].Value)
                );
                list.Add((statement, entry.Translation));
            }
            translationsByFile[pair.Key] = list;
        }

        return new TranslationApplier(translationsByFile);
    }

    public async Task ApplyTranslationsAsync(
        DirectoryInfo srcDir,
        DirectoryInfo outputDir,
        CancellationToken cancellationToken
    )
    {
        // 2. 将所有源文件复制到输出目录，以确保所有文件都存在
        Console.WriteLine("COPYING all source files to the output directory...");
        if (outputDir.Exists)
        {
            outputDir.Delete(true);
        }
        outputDir.Create();

        foreach (var file in srcDir.EnumerateFiles("*.*", SearchOption.AllDirectories))
        {
            var relativePath = Path.GetRelativePath(srcDir.FullName, file.FullName);
            var destPath = Path.Combine(outputDir.FullName, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(destPath)!);
            file.CopyTo(destPath, true);
        }
        Console.WriteLine("COPYING finished.");

        // 3. 对每个包含翻译的文件应用更改
        Console.WriteLine("🚀 开始应用翻译到代码...");
        int appliedCount = 0;
        int fileModifiedCount = 0;

        foreach (var pair in translationsByFile)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            var relativePath = pair.Key;
            var entriesToApply = pair.Value;
            var fullOutputPath = Path.Combine(outputDir.FullName, relativePath);

            if (!File.Exists(fullOutputPath))
            {
                await Console.Error.WriteLineAsync($"⚠️ 源文件不存在于输出目录，跳过: {relativePath}");
                continue;
            }

            try
            {
                var originalSourceCode = await File.ReadAllTextAsync(
                    fullOutputPath,
                    cancellationToken
                );
                var newSourceText = new StringBuilder();
                var lastIndex = 0;
                bool fileModified = false;

                // 按 StartPosition 升序排序
                var orderedEntries = entriesToApply.OrderBy(e => e.Statement.StartPosition);

                foreach (var (statement, translation) in orderedEntries)
                {
                    // 添加从上一个位置到当前替换点的原文
                    newSourceText.Append(
                        originalSourceCode.Substring(lastIndex, statement.StartPosition - lastIndex)
                    );
                    // 添加翻译
                    newSourceText.Append(translation);
                    // 更新索引
                    lastIndex = statement.StartPosition + statement.Length;
                    appliedCount++;
                    fileModified = true;
                }

                // 添加最后一个替换点到文件末尾的剩余内容
                if (lastIndex < originalSourceCode.Length)
                {
                    newSourceText.Append(originalSourceCode.Substring(lastIndex));
                }

                if (fileModified)
                {
                    await File.WriteAllTextAsync(
                        fullOutputPath,
                        newSourceText.ToString(),
                        cancellationToken
                    );
                    // Console.WriteLine($"✏️ 已更新文件: {relativePath}");
                    fileModifiedCount++;
                }
            }
            catch (Exception ex)
            {
                await Console.Error.WriteLineAsync($"❌ 处理文件 {relativePath} 失败: {ex.Message}");
            }
        }

        Console.WriteLine($"✅ 翻译应用完成！共应用 {appliedCount} 处翻译，修改了 {fileModifiedCount} 个文件。");
        Console.WriteLine($"📂 输出目录: {outputDir.FullName}");
    }

    public static async Task ApplyTranslationsCommandAsync(
        DirectoryInfo transDir,
        DirectoryInfo srcDir,
        DirectoryInfo outputDir,
        CancellationToken cancellationToken
    )
    {
        Console.WriteLine("🔄 开始应用翻译...");

        var applier = await CreateAsync(transDir, cancellationToken);

        await applier.ApplyTranslationsAsync(srcDir, outputDir, cancellationToken);
    }
}
