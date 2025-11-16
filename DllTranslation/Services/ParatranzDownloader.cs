using System;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;

namespace DllTranslation.Services
{
    public static class ParatranzDownloader
    {
        private static readonly HttpClient client = new();

        /// <summary>
        /// 从 Paratranz 下载翻译文件。
        /// </summary>
        /// <param name="projectId">Paratranz 项目 ID。</param>
        /// <param name="apiToken">Paratranz API 令牌。</param>
        /// <param name="outputDir">保存翻译文件的目录。</param>
        /// <remarks>
        /// 此方法假定 API 端点为 "https://paratranz.cn/api/projects/{projectId}/artifacts"，
        /// 并且会下载一个包含所有翻译文件的 zip 压缩包。
        /// </remarks>
        public static async Task DownloadTranslationsAsync(
            int projectId,
            string apiToken,
            DirectoryInfo outputDir
        )
        {
            if (string.IsNullOrEmpty(apiToken))
            {
                throw new ArgumentException("必须提供 API 令牌。", nameof(apiToken));
            }

            if (!outputDir.Exists)
            {
                outputDir.Create();
            }

            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
                "Bearer",
                apiToken
            );

            var requestUri = $"https://paratranz.cn/api/projects/{projectId}/artifacts/download";

            Console.WriteLine($"正在从 {requestUri} 下载翻译文件...");

            try
            {
                var zipPath = Path.Combine(Path.GetTempPath(), $"{projectId}.zip");
                using (
                    var response = await client.GetAsync(
                        requestUri,
                        HttpCompletionOption.ResponseHeadersRead
                    )
                )
                {
                    response.EnsureSuccessStatusCode();

                    using (
                        var fileStream = new FileStream(zipPath, FileMode.Create, FileAccess.Write)
                    )
                    {
                        await response.Content.CopyToAsync(fileStream);
                    }
                }

                Console.WriteLine($"已下载文件到 {zipPath}。");
                Console.WriteLine($"正在解压到 {outputDir.FullName}...");

                if (outputDir.Exists)
                {
                    outputDir.Delete(true);
                }

                var parentDir = outputDir.Parent;
                var utf8DirPath = Path.Combine(parentDir.FullName, "utf8");
                if (Directory.Exists(utf8DirPath))
                {
                    Console.WriteLine($"发现已存在的临时文件夹 {utf8DirPath}，正在删除...");
                    Directory.Delete(utf8DirPath, true);
                }

                ZipFile.ExtractToDirectory(zipPath, parentDir!.FullName);

                File.Delete(zipPath);

                // 将最外层的utf8文件夹重命名为outputDir

                var utf8Dir = new DirectoryInfo(utf8DirPath);
                if (utf8Dir.Exists)
                {
                    const int maxRetries = 5;
                    for (int i = 0; i < maxRetries; i++)
                    {
                        try
                        {
                            utf8Dir.MoveTo(outputDir.FullName);
                            break; // Success
                        }
                        catch (IOException ex) when (i < maxRetries - 1)
                        {
                            Console.WriteLine($"移动目录时发生 IO 异常: {ex.Message}");
                            Console.WriteLine($"将在 200ms 后重试... (尝试次数 {i + 1}/{maxRetries})");
                            await Task.Delay(200);
                        }
                    }
                }

                Console.WriteLine("成功下载并解压了翻译文件。");
            }
            catch (HttpRequestException e)
            {
                Console.WriteLine($"下载翻译文件时出错: {e.Message}");
                throw;
            }
        }
    }
}
