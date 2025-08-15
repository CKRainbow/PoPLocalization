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

                ZipFile.ExtractToDirectory(zipPath, parentDir!.FullName);

                File.Delete(zipPath);

                // 将最外层的utf8文件夹重命名为outputDir

                var utf8Dir = new DirectoryInfo(Path.Combine(parentDir.FullName, "utf8"));
                if (utf8Dir.Exists)
                {
                    utf8Dir.MoveTo(outputDir.FullName);
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
