# Unity Asset Translator

这是一个用于处理 Unity Asset 文件（`.asset`, `.prefab`）中 `MonoBehaviour` 组件文本本地化的命令行工具。它提供文本提取、更新、应用、字体更换以及一键式流水线功能，采用 Python 和 C# 混合的解决方案，以兼顾灵活性和更新逻辑的健robustness。

## 功能特性

- **提取 (Extract)**: 使用 `UnityPy` 从单个 Unity Asset 文件中提取 `MonoBehaviour` 内的 `m_text` 字段，并生成 Paratranz 兼容的 JSON 文件。
- **更新 (Update)**: 通过 `dotnet run` 调用外部的 C# `DllTranslation` 项目，智能地比较新旧提取文件，并迁移现有翻译。
- **应用 (Apply)**: 将翻译完成的 JSON 文件安全地写回到 Unity Asset 文件中。
- **更换字体 (Change Font)**: 基于配置文件，通过 `PathID` 精准替换 Asset 中的 `TMP_FontAsset` 及其关联的纹理和材质。
- **流水线 (Pipeline)**: 提供一键式操作，将提取、更新、应用翻译和更换字体的完整流程串联起来，并通过内存操作链进行优化，减少不必要的磁盘读写，提升效率。

## 安装与要求

1.  **Python 3.7+**: 确保您的系统已安装 Python。
2.  **.NET SDK 8.0+**: 用于通过 `dotnet run` 运行 C# 项目。
3.  **依赖库**: 安装所需的 Python 库。
    ```bash
    pip install UnityPy Pillow
    ```
4.  **DllTranslation 项目**: 您需要拥有 `DllTranslation` C# 项目的源代码。

## 使用方法

该工具通过 `asset_translator.py` 脚本运行，并提供五个子命令：`extract`, `update`, `apply`, `change_font`, `pipeline`。

---

### 1. `extract`

从单个 Asset 文件中提取所有可翻译的文本。

**命令格式:**
```bash
python asset_translator.py extract --input <asset_file_path> --dll-folder <managed_dll_folder> --unity-version <version> --output <output_json_path>
```
**示例:**
```bash
python asset_translator.py extract --input ./assets/globalgamemanagers.asset --dll-folder ./Managed --unity-version 2019.4.16f1 --output ./extracted/globalgamemanagers.asset.json
```

---

### 2. `update`

使用 C# 项目的源代码来更新翻译。

**命令格式:**
```bash
python asset_translator.py update --tool-project-dir <path_to_csproj_dir> --old <old_trans_dir> --new <new_extracted_dir> --output <updated_trans_dir>
```
**参数说明:**
- `--tool-project-dir`: `DllTranslation` C# 项目的根目录路径。

**示例:**
```bash
python asset_translator.py update --tool-project-dir ./DllTranslation --old ./translated_v1 --new ./extracted_v2 --output ./translated_v2
```

---

### 3. `apply`

将翻译好的 JSON 文件写回到 Asset 文件中。

**命令格式:**
```bash
python asset_translator.py apply --trans <translated_json> --src <source_asset> --dll-folder <managed_dll_folder> --unity-version <version> --output <modified_asset>
```
**示例:**
```bash
python asset_translator.py apply --trans ./translated/globalgamemanagers.asset.json --src ./assets/globalgamemanagers.asset --dll-folder ./Managed --unity-version 2019.4.16f1 --output ./modified_assets/globalgamemanagers.asset
```

---

### 4. `change_font`

基于 JSON 配置文件，精准替换 Asset 中的字体及相关资源。此方法通过 `PathID` 进行操作，可实现高度定制化的批量替换。

**命令格式:**
```bash
python asset_translator.py change_font --target-asset <asset_file> --new-font-asset <new_font_asset_file> --config <config_json_path> --dll-folder <target_dll_folder> --new-font-dll-folder <new_font_dll_folder> --unity-version <version> --output <output_asset>
```
**参数说明:**
- `--target-asset`: 要修改的目标 Asset 文件。
- `--new-font-asset`: 包含新字体、新纹理等资源的源 Asset 文件。
- `--config`: 定义替换规则的 JSON 配置文件路径。
- `--dll-folder`: **目标 Asset** 所需的 `Managed` 文件夹路径。
- `--new-font-dll-folder`: **新字体 Asset** 所需的 `Managed` 文件夹路径。

**示例:**
```bash
python asset_translator.py change_font --target-asset ./assets/sharedassets0.asset --new-font-asset ./new_font/font.asset --config ./font_config.json --dll-folder ./Managed_old --new-font-dll-folder ./Managed_new --unity-version 2019.4.16f1 --output ./final_assets/sharedassets0.asset
```

#### `font_config.json` 配置文件详解

该文件是 `change_font` 命令的核心，它以列表形式定义了多组资源的替换关系。

**结构示例:**
```json
{
  "font_assets": [
    {
      "source_path_id": 123,
      "target_path_id": 456
    }
  ],
  "textures": [
    {
      "source_path_id": 124,
      "target_path_id": 457
    }
  ],
  "materials": [
    {
      "target_path_id": 458
    }
  ]
}
```
**字段说明:**
- **`font_assets`**: `TMP_FontAsset` 资源的替换列表。
  - `source_path_id`: 新字体在 `--new-font-asset` 文件中的 `PathID`。
  - `target_path_id`: 要被替换的旧字体在 `--target-asset` 文件中的 `PathID`。
- **`textures`**: `Texture2D` 资源的替换列表。纹理数据将直接从源 `PathID` 对应的对象中复制。
  - `source_path_id`: 新纹理在 `--new-font-asset` 文件中的 `PathID`。
  - `target_path_id`: 要被替换的旧纹理在 `--target-asset` 文件中的 `PathID`。
- **`materials`**: `Material` 资源的修改列表。脚本会对其进行预设的调整（例如修改 `_UnderlayOffset`）。
  - `target_path_id`: 要修改的材质在 `--target-asset` 文件中的 `PathID`。

---

### 5. `pipeline` (推荐)

执行从提取到更换字体的完整自动化流程，是处理资源本地化的最高效方式。

**命令格式:**
```bash
python asset_translator.py pipeline --input-asset <asset_file> --dll-folder <managed_dll_folder> --unity-version <version> --tool-project-dir <path_to_csproj_dir> --old-trans-dir <old_trans_dir> --new-font-asset <new_font_asset_file> --font-config <config_json_path> --new-font-dll-folder <new_font_dll_folder> --output-asset <final_asset_path> --work-dir <path_for_temp_files>
```
**参数说明:**
- `--input-asset`: 流水线的起始源 Asset 文件。
- `--old-trans-dir`: 用于 `update` 步骤的旧翻译目录。
- `--font-config`: 用于 `change_font` 步骤的 JSON 配置文件。
- `--new-font-dll-folder`: 新字体 Asset 所需的 `Managed` 文件夹。
- `--output-asset`: 流水线处理完成后最终输出的 Asset 文件路径。
- `--work-dir`: 用于存放流水线过程中产生的中间文件（如提取的JSON）的目录，默认为 `./pipeline_workdir`。

**示例:**
```bash
python asset_translator.py pipeline \
    --input-asset ./assets/globalgamemanagers.asset \
    --dll-folder ./Managed_old \
    --unity-version 2019.4.16f1 \
    --tool-project-dir ./DllTranslation \
    --old-trans-dir ./translated_v1 \
    --new-font-asset ./new_font/font.asset \
    --font-config ./font_config.json \
    --new-font-dll-folder ./Managed_new \
    --output-asset ./final_assets/globalgamemanagers.asset
```

## 推荐工作流程

对于大多数场景，直接使用 `pipeline` 命令是最高效的选择。

1.  **准备资源**: 准备好你的源 Asset 文件、旧的翻译目录（如果是第一次运行，可以是一个空目录）、以及新的字体资源和 `font_config.json` 配置文件。
2.  **执行流水线**: 运行 `pipeline` 命令，并提供所有必要的参数。
3.  **检查结果**: 在指定的输出路径检查最终生成的 Asset 文件。
4.  **翻译新文本**: `pipeline` 的 `--work-dir` 中的 `2_updated` 目录会包含最新的翻译文件。将其中新增和待翻译的条目完成后，可以作为下一次迭代的 `--old-trans-dir` 使用。