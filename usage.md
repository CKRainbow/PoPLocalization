# Unity 游戏本地化混合解决方案

这是一个为 Unity 游戏设计的综合性本地化工具集，采用 C# 和 Python 混合的解决方案。它旨在自动化处理游戏逻辑（DLLs）和游戏资源（Assets）中的文本提取、翻译管理和应用流程。

整个流程围绕两大核心组件构建：

1.  **`DllTranslation` (C#)**: 一个强大的 .NET 命令行工具，专门负责处理从游戏 DLL 反编译出的 C# 源代码。它能够提取代码中的字符串，通过 Paratranz平台管理和更新翻译，并将翻译后的文本安全地应用回源代码中。
2.  **`asset_translator.py` (Python)**: 一个基于 `UnityPy` 的灵活脚本，用于处理 Unity Asset 文件（如 `.asset`, `.prefab`）。它负责提取 `MonoBehaviour` 中的文本、应用翻译，并支持高精度的字体替换。

通过顶层的 Shell 脚本（如 `pipeline.sh`），这两个组件被协同调度，形成一个完整、高效的自动化本地化流水线。

## 整体工作流程

推荐使用 `pipeline.sh` 脚本来一键执行完整的本地化流程。该脚本会自动协调以下步骤：

1.  **C# 代码处理 (并行)**:
    *   调用 `DllTranslation` 工具的 `pipeline` 命令。
    *   从 `decompiled/` 目录中提取所有 `.cs` 文件中的可翻译字符串。
    *   从 Paratranz 下载最新的翻译文件到 `old/` 目录。
    *   比较新提取的字符串和旧的翻译，智能迁移已有翻译，并将结果保存到 `new/` 目录。
    *   将 `new/` 目录中的翻译应用回 C# 源代码，生成修改后的代码到 `replaced/` 目录。

2.  **Unity Asset 处理 (并行)**:
    *   调用 `asset_translator.py` 工具的 `pipeline` 命令。
    *   从指定的 Asset 文件（如 `data.unity3D`）中提取文本。
    *   使用 `old/` 目录中的翻译（与 C# 代码共享）来更新 Asset 文本。
    *   根据 `font_change_config.json` 配置文件，将 Asset 中的字体替换为 `TMPfont/` 中定义的新字体。
    *   将修改后的 Asset 文件输出到 `output_assets/` 目录。

3.  **编译 (并行)**:
    *   在 `replaced/` 目录中，使用 `dotnet build` 编译已应用翻译的 C# 项目。

脚本会等待所有并行的任务完成后结束，从而高效地完成对代码和资源的双重本地化处理。

## 目录结构说明

为了使流水线正常工作，项目依赖于特定的目录结构，其中大部分是临时工作目录：

-   `decompiled/`: 存放从游戏 `Assembly-CSharp.dll` 反编译出的 C# 源代码。**这是 C# 流水线的输入。**
-   `old/`: 存放从 Paratranz 下载的、作为基准的旧版翻译文件（JSON 格式）。
-   `new/`: 存放 C# 工具在 `old/` 基础上更新后生成的最新翻译文件。
-   `replaced/`: 存放已应用 `new/` 中翻译的 C# 源代码。**这是 C# 流水线的输出。**
-   `output_assets/`: 存放由 Python 脚本处理（应用翻译、替换字体）后生成的最终 Asset 文件。
-   `TMPfont/`: 包含用于替换的新字体资源。
-   `DllTranslation/`: C# 核心工具的项目源代码。
-   `asset_translator.py`: Python 核心工具的脚本文件。

## 安装与要求

1.  **Python 3.7+**: 确保您的系统已安装 Python。
2.  **.NET SDK 9.0+**: 用于运行和构建 `DllTranslation` C# 项目。
3.  **Python 依赖库**: 安装所需的 Python 库。
    ```bash
    pip install -r requirements.txt
    ```
4.  **环境变量**: `pipeline.sh` 脚本需要一个名为 `PARATRANZ_TOKEN` 的环境变量来访问 Paratranz API。
    ```bash
    export PARATRANZ_TOKEN="YOUR_PARATRANZ_API_TOKEN"
    ```

## 使用方法

### 主要流水线 (推荐)

直接运行 `pipeline.sh` 来处理所有事务。在运行前，请确保 `decompiled/` 目录已准备好，并设置了 `PARATRANZ_TOKEN` 环境变量。

```bash
./pipeline.sh
```

### 仅处理 DLL

如果只需要处理 C# 代码的本地化，可以运行 `dll_pipeline.sh`。

```bash
./dll_pipeline.sh
```

---

## 附录：核心组件命令详解

### `DllTranslation` (C#)

通过 `dotnet run --project DllTranslation -- [command] [options]` 调用。

-   **`extract`**: 从 C# 文件中提取字符串。
-   **`update`**: 比较新旧代码，迁移翻译。
-   **`apply`**: 将翻译应用回 C# 代码。
-   **`pipeline`**: 执行 `extract` -> `download` -> `update` -> `apply` 的完整流程。

*更多详细参数请直接阅读 `DllTranslation/Program.cs`。*

### `asset_translator.py` (Python)

通过 `python asset_translator.py [command] [options]` 调用。

#### 1. `extract`
从单个 Asset 文件中提取所有可翻译的文本。
```bash
python asset_translator.py extract --input <asset_file_path> --dll-folder <managed_dll_folder> --unity-version <version> --output <output_json_path>
```

#### 2. `update`
使用 C# 项目的 `update-asset` 命令来更新翻译。
```bash
python asset_translator.py update --tool-project-dir <path_to_csproj_dir> --old <old_trans_dir> --new <new_extracted_dir> --output <updated_trans_dir>
```

#### 3. `apply`
将翻译好的 JSON 文件写回到 Asset 文件中。
```bash
python asset_translator.py apply --trans <translated_json> --src <source_asset> --dll-folder <managed_dll_folder> --unity-version <version> --output <modified_asset>
```

#### 4. `change_font`
基于 JSON 配置文件，精准替换 Asset 中的字体及相关资源。
```bash
python asset_translator.py change_font --target-asset <asset_file> --new-font-asset <new_font_asset_file> --config <config_json_path> --dll-folder <target_dll_folder> --new-font-dll-folder <new_font_dll_folder> --unity-version <version> --output <output_asset>
```

#### 5. `pipeline` (推荐)
执行从提取到更换字体的完整自动化流程。
```bash
python asset_translator.py pipeline --input-asset <asset_file> --dll-folder <managed_dll_folder> --unity-version <version> --tool-project-dir <path_to_csproj_dir> --old-trans-dir <old_trans_dir> --new-font-asset <new_font_asset_file> --font-config <config_json_path> --new-font-dll-folder <new_font_dll_folder> --output-asset <final_asset_path> --work-dir <path_for_temp_files>