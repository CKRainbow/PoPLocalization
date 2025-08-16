using System;
using System.Collections.Concurrent;
using System.CommandLine;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using DllTranslation.Models;
using DllTranslation.Services;
using DllTranslation.Utilities;

class Program
{
    static async Task<int> Main(string[] args)
    {
        var rootCommand = new RootCommand("一个用于处理 C# 文件中字符串提取、更新和应用的本地化工具");

        // === EXTRACT command ===
        var extractCommand = new Command("extract", "从 C# 文件中提取与字符串相关的语句");
        var dirOption = new Option<DirectoryInfo>("--dir")
        {
            Description = "指定要分析的文件夹路径（会递归搜索 .cs 文件）",
            Required = true,
        };

        var outputOption = new Option<DirectoryInfo>("--output")
        {
            Description = "指定输出 JSON 文件的文件夹路径",
            Required = true,
        };

        var literalsOnlyOption = new Option<bool>("--literals-only")
        {
            Description = "如果设置，则只提取包含字符串字面量的语句。",
        };

        var paratranzOutputOption = new Option<DirectoryInfo>("--paratranz-output")
        {
            Description = "如果指定，则会为 Paratranz 生成对应的 JSON 文件到该目录",
        };

        extractCommand.Options.Add(dirOption);
        extractCommand.Options.Add(outputOption);
        extractCommand.Options.Add(literalsOnlyOption);
        extractCommand.Options.Add(paratranzOutputOption);

        extractCommand.SetAction(
            (result, cancellationToken) =>
            {
                var dir = result.GetValue(dirOption)!;
                var output = result.GetValue(outputOption)!;
                var literalsOnly = result.GetValue(literalsOnlyOption);
                var paratranzOutput = result.GetValue(paratranzOutputOption);
                return TranslationExtractor.ExtractStringStatementsAsync(
                    dir,
                    output,
                    literalsOnly,
                    paratranzOutput,
                    cancellationToken
                );
            }
        );
        rootCommand.Subcommands.Add(extractCommand);

        // === UPDATE command ===
        var updateCommand = new Command("update", "比较新旧提取文件，并迁移翻译。");
        var oldTransDirOption = new Option<DirectoryInfo>("--old")
        {
            Description = "包含旧翻译的 Paratranz JSON 文件目录。",
            Required = true
        };
        var newSrcDirOption = new Option<DirectoryInfo>("--new")
        {
            Description = "包含新版 C# 源代码的目录。",
            Required = true
        };
        var updatedTransDirOption = new Option<DirectoryInfo>("--output")
        {
            Description = "输出更新后翻译文件的目录。",
            Required = true
        };

        updateCommand.Options.Add(oldTransDirOption);
        updateCommand.Options.Add(newSrcDirOption);
        updateCommand.Options.Add(updatedTransDirOption);
        updateCommand.Options.Add(literalsOnlyOption);

        updateCommand.SetAction(
            (result, cancellationToken) =>
            {
                var oldTransDir = result.GetValue(oldTransDirOption)!;
                var newSrcDir = result.GetValue(newSrcDirOption)!;
                var updatedTransDir = result.GetValue(updatedTransDirOption)!;
                var literalsOnly = result.GetValue(literalsOnlyOption)!;
                return TranslationUpdater.UpdateTranslationsCommandAsync(
                    oldTransDir,
                    newSrcDir,
                    updatedTransDir,
                    new CsEntryLoader(literalsOnly),
                    "cs",
                    cancellationToken
                );
            }
        );
        rootCommand.Subcommands.Add(updateCommand);

        // === UPDATE-ASSET command ===
        var updateAssetCommand = new Command("update-asset", "比较新旧 Asset JSON 文件，并迁移翻译。");
        updateAssetCommand.Options.Add(oldTransDirOption);
        updateAssetCommand.Options.Add(newSrcDirOption);
        updateAssetCommand.Options.Add(updatedTransDirOption);

        updateAssetCommand.SetAction(
            (result, cancellationToken) =>
            {
                var oldTransDir = result.GetValue(oldTransDirOption)!;
                var newSrcDir = result.GetValue(newSrcDirOption)!;
                var updatedTransDir = result.GetValue(updatedTransDirOption)!;
                return TranslationUpdater.UpdateTranslationsCommandAsync(
                    oldTransDir,
                    newSrcDir,
                    updatedTransDir,
                    new AssetEntryLoader(),
                    "asset",
                    cancellationToken
                );
            }
        );
        rootCommand.Subcommands.Add(updateAssetCommand);

        // === APPLY command ===
        var applyCommand = new Command("apply", "将翻译应用回 C# 源代码。");
        var transDirOption = new Option<DirectoryInfo>("--trans")
        {
            Description = "包含翻译的 Paratranz JSON 文件目录。",
            Required = true
        };
        var srcDirOption = new Option<DirectoryInfo>("--src")
        {
            Description = "C# 源代码所在目录。",
            Required = true
        };
        var applyOutputDirOption = new Option<DirectoryInfo>("--output")
        {
            Description = "输出应用翻译后代码的新目录（为了安全，不直接修改原文件）。",
            Required = true
        };

        applyCommand.Options.Add(transDirOption);
        applyCommand.Options.Add(srcDirOption);
        applyCommand.Options.Add(applyOutputDirOption);

        applyCommand.SetAction(
            (result, cancellationToken) =>
            {
                return TranslationApplier.ApplyTranslationsCommandAsync(
                    result.GetValue(transDirOption)!,
                    result.GetValue(srcDirOption)!,
                    result.GetValue(applyOutputDirOption)!,
                    cancellationToken
                );
            }
        );
        rootCommand.Subcommands.Add(applyCommand);

        // === PIPELINE command ===
        var pipelineCommand = new Command("pipeline", "从源代码提取字符串，下载并更新翻译，最后应用翻译。");
        var pipelineDirOption = new Option<DirectoryInfo>("--dir")
        {
            Description = "包含源代码的目录。",
            Required = true
        };
        var pipelineOutputDirOption = new Option<DirectoryInfo>("--output")
        {
            Description = "输出翻译文件的目录。",
            Required = true,
        };
        var pipelineLiteralsOnlyOption = new Option<bool>("--literals-only")
        {
            Description = "如果指定，则只提取字面量字符串，不提取带参数的字符串。"
        };
        var pipelineOldParatranzDirOption = new Option<DirectoryInfo>("--paratranz-dir")
        {
            Description = "下载Paratranz JSON的位置，并将其加载。",
            Required = true,
        };
        var pipelineNewParatranzDirOption = new Option<DirectoryInfo>("--new-paratranz-dir")
        {
            Description = "更新后的Paratranz JSON的位置。",
            Required = true,
        };
        var pipelineReplacedOutputDirOption = new Option<DirectoryInfo>("--replaced-output")
        {
            Description = "输出应用翻译后代码的新目录（为了安全，不直接修改原文件）。",
            Required = true
        };
        var pipelineParatranzProjectIdOption = new Option<int>("--paratranz-project-id")
        {
            Description = "Paratranz 项目 ID。",
            Required = true
        };
        var pipelineParatranzTokenOption = new Option<string>("--paratranz-token")
        {
            Description = "Paratranz API 令牌。",
            Required = true
        };

        pipelineCommand.Options.Add(pipelineDirOption);
        pipelineCommand.Options.Add(pipelineOutputDirOption);
        pipelineCommand.Options.Add(pipelineLiteralsOnlyOption);
        pipelineCommand.Options.Add(pipelineOldParatranzDirOption);
        pipelineCommand.Options.Add(pipelineNewParatranzDirOption);
        pipelineCommand.Options.Add(pipelineReplacedOutputDirOption);
        pipelineCommand.Options.Add(pipelineParatranzProjectIdOption);
        pipelineCommand.Options.Add(pipelineParatranzTokenOption);

        pipelineCommand.SetAction(
            async (result, cancellationToken) =>
            {
                var pipelineDir = result.GetValue(pipelineDirOption)!;
                var pipelineOutputDir = result.GetValue(pipelineOutputDirOption)!;
                var pipelineLiteralsOnly = result.GetValue(pipelineLiteralsOnlyOption)!;
                var pipelineOldParatranzDir = result.GetValue(pipelineOldParatranzDirOption)!;
                var pipelineNewParatranzDir = result.GetValue(pipelineNewParatranzDirOption)!;
                var pipelineReplacedOutputDir = result.GetValue(pipelineReplacedOutputDirOption)!;
                var pipelineParatranzProjectId = result.GetValue(pipelineParatranzProjectIdOption)!;
                var pipelineParatranzToken = result.GetValue(pipelineParatranzTokenOption)!;

                var extractor = await TranslationExtractor.CreateAsync(
                    pipelineDir,
                    pipelineLiteralsOnly,
                    cancellationToken
                );

                await ParatranzDownloader.DownloadTranslationsAsync(
                    pipelineParatranzProjectId,
                    pipelineParatranzToken,
                    pipelineOldParatranzDir
                );

                // The extractor has already loaded the entries. We can reuse them.
                Console.WriteLine("Updating translations using extracted data...");

                // The conversion is necessary due to ConcurrentDictionary's invariance.
                var newEntries = new ConcurrentDictionary<
                    string,
                    IReadOnlyList<ITranslatableEntry>
                >(
                    extractor.sourceData.Select(
                        kvp =>
                            new KeyValuePair<string, IReadOnlyList<ITranslatableEntry>>(
                                kvp.Key,
                                kvp.Value
                            )
                    )
                );

                var updater = await TranslationUpdater.CreateAsync(
                    newEntries,
                    pipelineOldParatranzDir,
                    "cs",
                    cancellationToken
                );

                // Update translations and save the results to the output directory.
                Console.WriteLine(
                    $"Updating and saving new translations to {pipelineNewParatranzDir.FullName}..."
                );
                await updater.UpdateTranslationAsync(
                    pipelineDir,
                    pipelineNewParatranzDir,
                    cancellationToken
                );

                // Apply translations to the source code
                Console.WriteLine("Applying translations to source code...");
                var applier = TranslationApplier.Create(updater.newTranslations);

                await applier.ApplyTranslationsAsync(
                    pipelineDir,
                    pipelineReplacedOutputDir,
                    cancellationToken
                );
            }
        );

        rootCommand.Subcommands.Add(pipelineCommand);

        return await rootCommand.Parse(args).InvokeAsync();
    }
}
