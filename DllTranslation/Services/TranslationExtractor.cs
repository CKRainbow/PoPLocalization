using System;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;
using DllTranslation.Utilities;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace DllTranslation.Services;

public class TranslationExtractor
{
    public ConcurrentDictionary<string, IReadOnlyList<StatementEntry>> sourceData;

    private TranslationExtractor(
        ConcurrentDictionary<string, IReadOnlyList<StatementEntry>> sourceData
    )
    {
        this.sourceData = sourceData;
    }

    public static async Task<TranslationExtractor> CreateAsync(
        DirectoryInfo srcDir,
        bool literalsOnly,
        CancellationToken cancellationToken
    )
    {
        var allStringStatements = await ParserUtility.AnalyzeDirectoryAsync(
            srcDir,
            literalsOnly,
            cancellationToken
        );

        if (allStringStatements is null || cancellationToken.IsCancellationRequested)
        {
            return null;
        }

        return new TranslationExtractor(allStringStatements);
    }

    public static async Task ExtractStringStatementsAsync(
        DirectoryInfo dir,
        DirectoryInfo outputDir,
        bool literalsOnly,
        DirectoryInfo? paratranzOutputDir,
        CancellationToken cancellationToken
    )
    {
        var extractor = await CreateAsync(dir, literalsOnly, cancellationToken);

        if (extractor is null)
        {
            return;
        }

        var allStringStatements = extractor.sourceData;

        // Step 4: 将结果分别写入 JSON 文件
        Console.WriteLine("💾 正在将结果写入多个 JSON 文件...");

        if (allStringStatements.IsEmpty)
        {
            Console.WriteLine("⚠ 未找到任何与字符串相关的语句，不生成任何输出文件。");
            return;
        }

        if (outputDir.Exists)
        {
            outputDir.Delete(true);
        }
        outputDir.Create();

        var jsonOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping // 允许非 ASCII 字符
        };

        int successCount = 0;
        int errorCount = 0;

        foreach (var entry in allStringStatements.OrderBy(kvp => kvp.Key))
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                // 计算相对路径并更改扩展名
                var relativePath = Path.GetRelativePath(dir.FullName, entry.Key);
                var jsonRelativePath = Path.ChangeExtension(relativePath, ".json");
                var outputFilePath = Path.Combine(outputDir.FullName, jsonRelativePath);

                // 确保输出子目录存在
                var fileInfo = new FileInfo(outputFilePath);
                fileInfo.Directory?.Create();

                // 序列化并写入文件
                var jsonString = JsonSerializer.Serialize(entry.Value, jsonOptions);
                await File.WriteAllTextAsync(outputFilePath, jsonString, cancellationToken);
                successCount++;
            }
            catch (Exception ex)
            {
                await Console.Error.WriteLineAsync($"❌ 写入文件 for {entry.Key} 时出错: {ex.Message}");
                errorCount++;
            }
        }

        Console.WriteLine($"✅ 处理完成。成功写入 {successCount} 个文件，失败 {errorCount} 个。");
        Console.WriteLine($"📄 输出目录: {outputDir.FullName}");

        if (paratranzOutputDir != null)
        {
            Console.WriteLine("💾 正在为 Paratranz 生成 JSON 文件...");

            if (paratranzOutputDir.Exists)
            {
                paratranzOutputDir.Delete(true);
            }
            paratranzOutputDir.Create();

            var paratranzJsonOptions = new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            };

            int paratranzSuccessCount = 0;
            int paratranzErrorCount = 0;

            foreach (var entry in allStringStatements.OrderBy(kvp => kvp.Key))
            {
                if (cancellationToken.IsCancellationRequested)
                    break;

                try
                {
                    var relativePath = Path.GetRelativePath(dir.FullName, entry.Key);
                    var jsonRelativePath = Path.ChangeExtension(relativePath, ".json");
                    var outputFilePath = Path.Combine(
                        paratranzOutputDir.FullName,
                        jsonRelativePath
                    );

                    var fileInfo = new FileInfo(outputFilePath);
                    fileInfo.Directory?.Create();

                    var paratranzEntries = entry
                        .Value.Select(
                            (stmtEntry, index) =>
                            {
                                var key = stmtEntry.Hash;
                                var context =
                                    $"File: {relativePath}:{stmtEntry.StartLine}\nMethod: {stmtEntry.ContainingMethod}\nPosition: {stmtEntry.StartPosition}\nLength: {stmtEntry.Length}";
                                return new ParatranzEntry(
                                    Key: key,
                                    Original: stmtEntry.Text,
                                    Translation: "",
                                    Stage: 0,
                                    Context: context
                                );
                            }
                        )
                        .ToList();

                    if (paratranzEntries.Any())
                    {
                        var jsonString = JsonSerializer.Serialize(
                            paratranzEntries,
                            paratranzJsonOptions
                        );
                        await File.WriteAllTextAsync(outputFilePath, jsonString, cancellationToken);
                        paratranzSuccessCount++;
                    }
                }
                catch (Exception ex)
                {
                    await Console.Error.WriteLineAsync(
                        $"❌ 写入 Paratranz 文件 for {entry.Key} 时出错: {ex.Message}"
                    );
                    paratranzErrorCount++;
                }
            }

            Console.WriteLine(
                $"✅ Paratranz 处理完成。成功写入 {paratranzSuccessCount} 个文件，失败 {paratranzErrorCount} 个。"
            );
            Console.WriteLine($"📄 Paratranz 输出目录: {paratranzOutputDir.FullName}");
        }
    }
}
