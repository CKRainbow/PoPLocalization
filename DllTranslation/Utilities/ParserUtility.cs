using System;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using DllTranslation.Models;
using DllTranslation.Utilities;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace DllTranslation.Utilities;

public static class ParserUtility
{
    private static readonly HashSet<string> ClassesForConstructorExtraction =
        new()
        {
            // 在这里添加需要提取构造函数的类名
            // 例如: "Passive", "PassiveTooltip"
            "Passives"
        };

    public static async Task<ConcurrentDictionary<
        string,
        IReadOnlyList<StatementEntry>
    >?> AnalyzeDirectoryAsync(
        DirectoryInfo dir,
        bool literalsOnly,
        CancellationToken cancellationToken
    )
    {
        if (!dir.Exists)
        {
            await Console.Error.WriteLineAsync($"❌ 文件夹不存在: {dir.FullName}");
            return null;
        }

        var csFiles = Directory.EnumerateFiles(dir.FullName, "*.cs", SearchOption.AllDirectories);
        if (!csFiles.Any())
        {
            Console.WriteLine("⚠ 未找到任何 .cs 文件");
            return null;
        }

        // Step 1: 并行读取和解析文件为语法树
        Console.WriteLine("🔍 开始并行解析文件...");
        var syntaxTrees = new ConcurrentBag<SyntaxTree>();
        await Parallel.ForEachAsync(
            csFiles,
            cancellationToken,
            async (filePath, ct) =>
            {
                try
                {
                    var code = await File.ReadAllTextAsync(filePath, ct);
                    var tree = CSharpSyntaxTree.ParseText(
                        code,
                        path: filePath,
                        cancellationToken: ct
                    );
                    syntaxTrees.Add(tree);
                }
                catch (Exception ex)
                {
                    await Console.Error.WriteLineAsync($"❌ 读取或解析文件 {filePath} 时出错: {ex.Message}");
                }
            }
        );

        if (cancellationToken.IsCancellationRequested)
            return null;
        Console.WriteLine($"✅ 完成解析 {syntaxTrees.Count} 个文件。");

        // Step 2: 创建包含所有语法树的单个编译实例
        Console.WriteLine("⚙️ 正在创建编译实例...");
        var compilation = CSharpCompilation
            .Create("StringAnalysisCompilation")
            .AddReferences(
                MetadataReference.CreateFromFile(typeof(object).Assembly.Location),
                MetadataReference.CreateFromFile(typeof(Console).Assembly.Location)
            )
            .AddSyntaxTrees(syntaxTrees);
        Console.WriteLine("✅ 编译实例创建完成。");

        // Step 3: 并行进行语义分析
        Console.WriteLine("🔬 开始并行语义分析...");
        var allStringStatements = new ConcurrentDictionary<string, IReadOnlyList<StatementEntry>>();
        Parallel.ForEach(
            syntaxTrees,
            tree =>
            {
                if (cancellationToken.IsCancellationRequested)
                    return;
                try
                {
                    var model = compilation.GetSemanticModel(tree);
                    var root = tree.GetRoot(cancellationToken);

                    var stringExpressions = root.DescendantNodes()
                        .OfType<ExpressionSyntax>()
                        .Where(expr =>
                        {
                            if (literalsOnly)
                            {
                                return expr.IsKind(SyntaxKind.StringLiteralExpression);
                            }
                            var typeInfo = model.GetTypeInfo(expr, cancellationToken).Type;
                            return typeInfo?.SpecialType == SpecialType.System_String;
                        });

                    var candidateNodes = stringExpressions
                        .Select(e =>
                        {
                            var statement = e.FirstAncestorOrSelf<StatementSyntax>();
                            if (statement != null)
                                return (SyntaxNode)statement;

                            var member = e.FirstAncestorOrSelf<MemberDeclarationSyntax>();
                            if (
                                member is FieldDeclarationSyntax
                                || member is PropertyDeclarationSyntax
                            )
                                return member;

                            return null;
                        })
                        .Where(s =>
                        {
                            if (s is null)
                                return false;
                            var ctor = s.FirstAncestorOrSelf<ConstructorDeclarationSyntax>();
                            if (ctor is null)
                                return true; // Not in a constructor, so include it

                            // It's in a constructor, check if the class is in the extraction list
                            if (ctor.Parent is ClassDeclarationSyntax classDecl)
                            {
                                // If the class is in the list, we should EXCLUDE the string statement
                                // because the whole constructor will be extracted.
                                return !ClassesForConstructorExtraction.Contains(
                                    classDecl.Identifier.ValueText
                                );
                            }

                            return true; // Not in a class (shouldn't happen for a ctor), include it
                        })
                        .Distinct();

                    var nodesByScope = candidateNodes.GroupBy(
                        node => node.FirstAncestorOrSelf<MemberDeclarationSyntax>()
                    );

                    var statements = new List<StatementEntry>();

                    foreach (var group in nodesByScope)
                    {
                        var scopeNode = group.Key;
                        if (scopeNode is null)
                            continue;

                        var memberName = scopeNode switch
                        {
                            MethodDeclarationSyntax m => m.Identifier.ValueText,
                            ConstructorDeclarationSyntax c => c.Identifier.ValueText,
                            DestructorDeclarationSyntax d => d.Identifier.ValueText,
                            PropertyDeclarationSyntax p => p.Identifier.ValueText,
                            FieldDeclarationSyntax f
                                => string.Join(
                                    ", ",
                                    f.Declaration.Variables.Select(v => v.Identifier.ValueText)
                                ),
                            _ => "GlobalScope"
                        };

                        var candidateNodesInScope = group;

                        var topLevelNodesInScope = candidateNodesInScope.Where(
                            node =>
                                !candidateNodesInScope.Any(
                                    other => node != other && node.Ancestors().Contains(other)
                                )
                        );

                        foreach (var s in topLevelNodesInScope)
                        {
                            var text = s.ToFullString().Trim();
                            var hash = HashUtility.ComputePositionAwareSha256Hash(
                                text,
                                s.Span.Start
                            );
                            var startLine =
                                s.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                            statements.Add(
                                new StatementEntry(
                                    text,
                                    hash,
                                    s.Span.Start,
                                    s.Span.Length,
                                    memberName,
                                    startLine
                                )
                            );
                        }
                    }

                    // Add constructors as entries
                    var constructorDeclarations = root.DescendantNodes()
                        .OfType<ConstructorDeclarationSyntax>()
                        .Where(
                            ctor =>
                                ctor.Parent is ClassDeclarationSyntax classDecl
                                && ClassesForConstructorExtraction.Contains(
                                    classDecl.Identifier.ValueText
                                )
                        );
                    foreach (var ctor in constructorDeclarations)
                    {
                        var text = ctor.ToFullString().Trim();
                        var hash = HashUtility.ComputePositionAwareSha256Hash(
                            text,
                            ctor.Span.Start
                        );
                        var startLine = ctor.GetLocation().GetLineSpan().StartLinePosition.Line + 1;
                        statements.Add(
                            new StatementEntry(
                                text,
                                hash,
                                ctor.Span.Start,
                                ctor.Span.Length,
                                ctor.Identifier.ValueText, // memberName
                                startLine
                            )
                        );
                    }

                    if (statements.Any())
                    {
                        allStringStatements.TryAdd(tree.FilePath, statements);
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"❌ 分析文件 {tree.FilePath} 时出错: {ex.Message}");
                }
            }
        );

        if (cancellationToken.IsCancellationRequested)
            return null;
        Console.WriteLine("✅ 语义分析完成，共找到字符串语句：" + allStringStatements.Sum(kvp => kvp.Value.Count));

        return allStringStatements;
    }
}
