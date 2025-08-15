import argparse
import json
import os
import subprocess
import hashlib
import re
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, cast
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.Tpk import get_typetree_node
from UnityPy.classes import MonoBehaviour

# Based on DllTranslation/Models/ParatranzEntry.cs
@dataclass
class ParatranzEntry:
    key: str
    original: str
    translation: str
    stage: int
    context: str

def generate_hash(text: str) -> str:
    """Generates a SHA256 hash for the given text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def core_extract(env: UnityPy.Environment, source_file_name: str) -> List[ParatranzEntry]:
    """
    Core logic for extracting text from a loaded UnityPy Environment.
    Operates in memory and returns a list of ParatranzEntry objects.
    """
    paratranz_entries: List[ParatranzEntry] = []
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                
                if "text" not in script.m_Name.lower():
                    continue

                data = obj.read_typetree()
                if "m_text" in data and data["m_text"]:
                    original_text = data["m_text"]
                    key_source = f"{script.m_Name}:{obj.path_id}:{original_text}"
                    key = generate_hash(key_source)
                    context = f"PathID: {obj.path_id}\nScript: {script.m_Name}"

                    entry = ParatranzEntry(
                        key=key,
                        original=original_text,
                        translation="",
                        stage=0,
                        context=context,
                    )
                    paratranz_entries.append(entry)
            except Exception:
                pass
    return paratranz_entries

def extract(args):
    """
    Wrapper for text extraction. Handles file I/O and calls the core logic.
    """
    print(f"Executing 'extract' command on file: {args.input}")
    if not os.path.isfile(args.input):
        print(f"Error: Source file '{args.input}' not found.")
        return
    if not os.path.isdir(args.dll_folder):
        print(f"Error: DLL folder '{args.dll_folder}' not found.")
        return

    try:
        generator = TypeTreeGenerator(args.unity_version)
        generator.load_local_dll_folder(args.dll_folder)
        env = UnityPy.load(args.input)
        env.typetree_generator = generator
    except Exception as e:
        print(f"Error loading asset or DLLs: {e}")
        return

    paratranz_entries = core_extract(env, os.path.basename(args.input))
    
    if paratranz_entries:
        # Check for duplicate keys
        keys_seen = {}
        duplicates = {}
        for entry in paratranz_entries:
            if entry.key in keys_seen:
                if entry.key not in duplicates:
                    duplicates[entry.key] = [keys_seen[entry.key]]
                duplicates[entry.key].append(entry.context)
            else:
                keys_seen[entry.key] = entry.context

        if duplicates:
            print("\n\033[93m⚠️ WARNING: Duplicate keys were detected! This may indicate a hash collision or an issue with the source data.\033[0m")
            for key, contexts in duplicates.items():
                print(f"\n  - \033[91mDuplicate Key: {key}\033[0m")
                for i, context in enumerate(contexts):
                    # Indent context for readability
                    indented_context = "      ".join(context.splitlines(True))
                    print(f"    - \033[96mContext {i+1}:\033[0m\n      ---\n      {indented_context}\n      ---")
        
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in paratranz_entries], f, ensure_ascii=False, indent=4)
        print(f"✅ Successfully extracted {len(paratranz_entries)} entries to '{args.output}'")
    else:
        print("⚠️ No text entries found to extract.")
    print("Extraction complete.")


def update(args):
    """
    Updates translations by calling the DllTranslation tool using 'dotnet run'.
    """
    print("Executing 'update' command...")
    project_dir = args.tool_project_dir
    old_dir = args.old
    new_dir = args.new
    output_dir = args.output

    # 1. Validate paths
    if not os.path.isdir(project_dir):
        print(f"Error: DllTranslation project directory not found at '{project_dir}'")
        return
    if not os.path.isdir(old_dir):
        print(f"Error: Old translations directory not found at '{old_dir}'")
        return
    if not os.path.isdir(new_dir):
        print(f"Error: New source directory not found at '{new_dir}'")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 2. Construct the 'dotnet run' command
    command = [
        "dotnet",
        "run",
        "--project",
        project_dir,
        "--", # Separator for application arguments
        "update-asset",
        "--old",
        old_dir,
        "--new",
        new_dir,
        "--output",
        output_dir,
    ]

    print(f"Running command: {' '.join(command)}")

    # 3. Execute the command
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        
        # Real-time output streaming
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        rc = process.poll()
        if rc != 0:
            # Raise an exception to halt the pipeline on failure
            raise RuntimeError(f"Update command failed with return code {rc}. Check the output above for details.")
        
        print("Update command executed successfully.")

    except FileNotFoundError:
        raise RuntimeError("Error: 'dotnet' command not found. Please ensure the .NET SDK is installed and in your PATH.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while running the update command: {e}")


def font_asset_adoption(src_typetree: Dict, target_typetree: Dict) -> Dict:
    """
    Adopts essential properties from an old font asset typetree to a new one.
    This preserves references and metadata within the target asset file.
    """
    # Safely copy properties from old to new typetree, checking for existence first.
    src_typetree["m_Script"]["m_PathID"] = target_typetree["m_Script"]["m_PathID"]
    src_typetree["m_Name"] = target_typetree["m_Name"]
    src_typetree["hashCode"] = target_typetree["hashCode"]
    src_typetree["material"]["m_PathID"] = target_typetree["material"]["m_PathID"]
    src_typetree["materialHashCode"] = target_typetree["materialHashCode"]
    src_typetree["m_SourceFontFileGUID"] = target_typetree["m_SourceFontFileGUID"]
    src_typetree["m_FaceInfo"]["m_FamilyName"] = target_typetree["m_FaceInfo"]["m_FamilyName"]
    
    # Safely adopt atlas texture PathIDs
    for i, old_atlas_texture in enumerate(target_typetree["m_AtlasTextures"]):
        if i < len(src_typetree["m_AtlasTextures"]) and "m_PathID" in old_atlas_texture:
            src_typetree["m_AtlasTextures"][i]["m_PathID"] = old_atlas_texture["m_PathID"]

    # Safely adopt creation settings GUIDs
    if "sourceFontFileGUID" in target_typetree["m_CreationSettings"]:
        src_typetree["m_CreationSettings"]["sourceFontFileGUID"] = target_typetree["m_CreationSettings"]["sourceFontFileGUID"]
    if "referencedFontAssetGUID" in target_typetree["m_CreationSettings"]:
        src_typetree["m_CreationSettings"]["referencedFontAssetGUID"] = target_typetree["m_CreationSettings"]["referencedFontAssetGUID"]
    return src_typetree


def core_change_font(
    target_env: UnityPy.Environment,
    new_font_asset_path: str,
    config: Dict,
    generator: TypeTreeGenerator,
) -> UnityPy.Environment:
    """
    Core logic for changing fonts and related assets based on a config file.
    Operates on a loaded UnityPy Environment.
    """
    # 1. Load the asset containing the new font(s) and texture(s)
    new_font_env = UnityPy.load(new_font_asset_path)
    new_font_env.typetree_generator = generator

    def build_maps(env: UnityPy.Environment, config: Dict):
        font_asset_config = config.get("font_assets", None)
        texture_config = config.get("textures", None)
        material_config = config.get("materials", None)

        font_assets = {}
        textures = {}
        materials = {}

        for obj in env.objects:
            if font_asset_config is not None and obj.type.name == 'MonoBehaviour':
                if obj.path_id not in font_asset_config["path_id"]:
                    continue
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                if "TMP_FontAsset" != script.m_Name:
                    continue
                font_assets[obj.path_id] = obj
            elif texture_config is not None and obj.type.name == 'Texture2D':
                if obj.path_id not in texture_config["path_id"]:
                    continue
                data = obj.read()
                if data.m_Name not in texture_config["name"]:
                    continue
                textures[(obj.path_id, data.m_Name)] = obj
            elif material_config is not None and obj.type.name == 'Material':
                if obj.path_id not in material_config["path_id"]:
                    continue
                typetree = obj.read_typetree()
                if typetree["m_Name"] not in material_config["name"]:
                    continue
                materials[(obj.path_id, typetree["m_Name"])] = obj

        return font_assets, textures, materials

    source_font_assets, source_textures, _ = build_maps(new_font_env, config["source"])
    new_font_assets, new_textures, new_materials = build_maps(target_env, config["target"])

    if source_font_assets and new_font_assets:
        for src_path_id, new_path_id in zip(config["source"]["font_assets"]["path_id"], config["target"]["font_assets"]["path_id"]):
            source_font_asset_obj = source_font_assets.get(src_path_id)
            new_font_asset_obj = new_font_assets.get(new_path_id)
            if not source_font_asset_obj or not new_font_asset_obj:
                raise ValueError(f"PathID mapping for font asset (MonoBehaviour) {src_path_id}->{new_path_id} is invalid.")
            new_typetree = new_font_asset_obj.read_typetree()
            old_typetree = source_font_asset_obj.read_typetree()
            adopted_typetree = font_asset_adoption(old_typetree, new_typetree)
            new_font_asset_obj.save_typetree(adopted_typetree)
            print(f"  - Modified Font Asset: PathID {src_path_id} -> {new_path_id}")
    if source_textures and new_textures:
        for src_path_id, src_name, new_path_id, new_name in zip(
            config["source"]["textures"]["path_id"], 
            config["source"]["textures"]["name"], 
            config["target"]["textures"]["path_id"], 
            config["target"]["textures"]["name"]
        ):
            source_texture_obj = source_textures.get((src_path_id, src_name))
            new_texture_obj = new_textures.get((new_path_id, new_name))
            if not source_texture_obj or not new_texture_obj:
                raise ValueError(f"PathID mapping for texture (Texture2D) {src_path_id}->{new_path_id} is invalid.")
            src_data = source_texture_obj.read()
            new_data = new_texture_obj.read()
            new_data.image = src_data.image
            new_data.m_Width = src_data.m_Width
            new_data.m_Height = src_data.m_Height

            new_data.save()
            print(f"  - Modified Texture: PathID {src_path_id} Name {src_name} -> {new_path_id} Name {new_name}")
    if new_materials:
        for new_path_id, new_name in zip(config["target"]["materials"]["path_id"], config["target"]["materials"]["name"]):
            new_material_obj = new_materials.get((new_path_id, new_name))
            if not new_material_obj:
                raise ValueError(f"PathID mapping for material (Material) {new_path_id} is invalid.")
            material_typetree = new_material_obj.read_typetree()
            if "m_SavedProperties" in material_typetree:
                floats = material_typetree["m_SavedProperties"]["m_Floats"]
                modified = False
                for i, (name, val) in enumerate(floats):
                    if name == "_UnderlayOffsetX":
                        floats[i] = (name, 0.1)
                        modified = True
                    elif name == "_UnderlayOffsetY":
                        floats[i] = (name, -0.1)
                        modified = True
                if modified:
                    new_material_obj.save_typetree(material_typetree)
                    print(f"  - Modified Material: PathID {new_path_id}")

    return target_env

def change_font(args):
    """
    Wrapper for changing font. Handles file I/O and calls the core logic.
    """
    print("Executing 'change_font' command...")
    import shutil

    if not all(os.path.exists(p) for p in [args.target_asset, args.new_font_asset, args.config, args.dll_folder, args.new_font_dll_folder]):
        print("Error: One or more input files/folders not found.")
        return

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        shutil.copy2(args.target_asset, args.output)
        
        # Generator for the target asset
        target_generator = TypeTreeGenerator(args.unity_version)
        target_generator.load_local_dll_folder(args.dll_folder)
        target_env = UnityPy.load(args.output)
        target_env.typetree_generator = target_generator

        # Generator for the new font asset
        new_font_generator = TypeTreeGenerator(args.unity_version)
        new_font_generator.load_local_dll_folder(args.new_font_dll_folder)

        modified_env = core_change_font(
            target_env,
            args.new_font_asset,
            config_data,
            new_font_generator
        )

        with open(args.output, "wb") as f:
            f.write(modified_env.file.save())
        
        print(f"Successfully changed font and saved to '{args.output}'")
    except Exception as e:
        print(f"An error occurred during change_font: {e}")


def core_apply(env: UnityPy.Environment, trans_file_path: str) -> UnityPy.Environment:
    """
    Core logic for applying translations. Operates on a loaded UnityPy Environment.
    """
    with open(trans_file_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)

    # Filter for entries that have a translation and context
    translated_entries = [
        entry for entry in trans_data if entry.get("translation") and entry.get("context")
    ]

    translated_entry_map = {}
    translated_entry_path_id_set = set()

    for entry in translated_entries:
        context = entry["context"]
        path_id = int(re.search(r"PathID:\s*(\d+)", context).group(1))
        script = re.search(r"Script:\s*(.+)", context).group(1)

        translated_entry_map[(path_id, script)] = entry
        translated_entry_path_id_set.add(path_id)

    if not translated_entry_map:
        print("No valid translations with context found, skipping apply.")
        return env
    
    modified_count = 0
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                if obj.path_id not in translated_entry_path_id_set:
                    continue
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                script_name = script.m_Name
                if (obj.path_id, script_name) in translated_entry_map:
                    data = obj.read_typetree()
                    if "m_text" in data and data["m_text"]:
                        data["m_text"] = translated_entry_map[(obj.path_id, script_name)]["translation"]
                        obj.save_typetree(data)
                        modified_count += 1
            except Exception as e:
                print(f"Warning: Failed to process PathID {path_id}. Reason: {e}")
    
    print(f"Applied {modified_count} translations in memory.")
    return env

def pipeline(args):
    """
    Runs the full, optimized translation and font change pipeline.
    Operations are chained in memory to minimize I/O.
    """
    print("Executing 'pipeline' command...")
    work_dir = args.work_dir
    os.makedirs(work_dir, exist_ok=True)
    print(f"Working directory: {work_dir}")

    try:
        # --- Setup ---
        base_name = os.path.basename(args.input_asset)
        extracted_json_dir = os.path.join(work_dir, "1_extracted")
        extracted_json_path = os.path.join(extracted_json_dir, "asset_texts.json")
        updated_json_dir = os.path.join(work_dir, "2_updated")
        updated_json_path = os.path.join(updated_json_dir, "asset_texts.json")

        # === Step 1: Load Asset and Extract (in memory) ===
        print("\n--- [Step 1/4] Loading asset and extracting text ---")
        generator = TypeTreeGenerator(args.unity_version)
        generator.load_local_dll_folder(args.dll_folder)
        env = UnityPy.load(args.input_asset)
        env.typetree_generator = generator

        paratranz_entries = core_extract(env, base_name)
        
        if not paratranz_entries:
            print("No text entries found. Skipping translation steps.")
            # If no text, we might still want to change the font
            modified_env = env
        else:
            os.makedirs(extracted_json_dir, exist_ok=True)
            with open(extracted_json_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in paratranz_entries], f, ensure_ascii=False, indent=4)
            print(f"Extracted {len(paratranz_entries)} entries to temporary file.")

            # === Step 2: Update (external process) ===
            print("\n--- [Step 2/4] Running Update ---")
            update_args = argparse.Namespace(
                tool_project_dir=args.tool_project_dir,
                old=args.old_trans_dir,
                new=extracted_json_dir,
                output=updated_json_dir
            )
            update(update_args)

            # === Step 3: Apply (in memory) ===
            print("\n--- [Step 3/4] Applying translations ---")
            if not os.path.isfile(updated_json_path):
                raise FileNotFoundError(f"Critical: Updated translation file '{updated_json_path}' was not generated by the update step. Halting pipeline.")
            
            modified_env = core_apply(env, updated_json_path)
        
        # === Step 4: Change Font (in memory) ===
        print("\n--- [Step 4/4] Changing font ---")
        # Load config for the font change step
        with open(args.font_config, "r", encoding="utf-8") as f:
            font_config_data = json.load(f)
        
        # Create a dedicated generator for the new font asset
        new_font_generator = TypeTreeGenerator(args.unity_version)
        new_font_generator.load_local_dll_folder(args.new_font_dll_folder)

        final_env = core_change_font(
            modified_env,
            args.new_font_asset,
            font_config_data,
            new_font_generator
        )

        # === Final Step: Save to File ===
        print("\n--- [Final] Saving all changes to output file ---")
        os.makedirs(os.path.dirname(args.output_asset), exist_ok=True)
        with open(args.output_asset, "wb") as f:
            f.write(final_env.file.save())

        print(f"\n✅ Pipeline finished successfully! Final asset saved to '{args.output_asset}'")

    except Exception as e:
        print(f"\n❌ An error occurred during the pipeline: {e}")
        # Exit with a non-zero status code to indicate failure
        raise

def apply(args):
    """
    Wrapper for applying translations. Handles file I/O and calls the core logic.
    """
    print("Executing 'apply' command...")
    import shutil

    if not all(os.path.exists(p) for p in [args.trans, args.src, args.dll_folder]):
        print("Error: One or more input files/folders not found.")
        return

    try:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        shutil.copy2(args.src, args.output)

        generator = TypeTreeGenerator(args.unity_version)
        generator.load_local_dll_folder(args.dll_folder)
        env = UnityPy.load(args.output)
        env.typetree_generator = generator

        modified_env = core_apply(env, args.trans)

        with open(args.output, "wb") as f:
            f.write(modified_env.file.save())
        
        print(f"Successfully saved applied translations to '{args.output}'")
    except Exception as e:
        print(f"An error occurred during apply: {e}")


def main():
    parser = argparse.ArgumentParser(description="A tool for extracting, updating, and applying translations for Unity assets.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Extract Command ---
    parser_extract = subparsers.add_parser("extract", help="Extract text from a single Unity asset file.")
    parser_extract.add_argument("--input", required=True, help="The source Unity asset file (.asset, .prefab).")
    parser_extract.add_argument("--dll-folder", required=True, help="Path to the Managed folder containing game DLLs.")
    parser_extract.add_argument("--unity-version", required=True, help="The Unity version of the game (e.g., '2019.4.16f1').")
    parser_extract.add_argument("--output", required=True, help="The path to save the output Paratranz JSON file.")
    parser_extract.set_defaults(func=extract)

    # --- Update Command ---
    parser_update = subparsers.add_parser("update", help="Update translations by comparing old and new extractions using 'dotnet run'.")
    parser_update.add_argument("--tool-project-dir", required=True, help="Path to the DllTranslation C# project directory.")
    parser_update.add_argument("--old", required=True, help="The directory containing the old Paratranz JSON translations.")
    parser_update.add_argument("--new", required=True, help="The directory containing the new source Paratranz JSON files (from extract).")
    parser_update.add_argument("--output", required=True, help="The directory to save the updated Paratranz JSON files.")
    parser_update.set_defaults(func=update)

    # --- Change Font Command ---
    parser_change_font = subparsers.add_parser("change_font", help="Replace font assets and textures in a target asset based on a config file.")
    parser_change_font.add_argument("--target-asset", required=True, help="The asset file to modify.")
    parser_change_font.add_argument("--new-font-asset", required=True, help="The asset file containing the new font assets and textures.")
    parser_change_font.add_argument("--config", required=True, help="Path to the JSON config file for PathID mapping.")
    parser_change_font.add_argument("--dll-folder", required=True, help="Path to the Managed folder for the TARGET asset.")
    parser_change_font.add_argument("--new-font-dll-folder", required=True, help="Path to the Managed folder for the NEW FONT asset.")
    parser_change_font.add_argument("--unity-version", required=True, help="The Unity version of the game.")
    parser_change_font.add_argument("--output", required=True, help="The path to save the modified asset file.")
    parser_change_font.set_defaults(func=change_font)

    # --- Apply Command ---
    parser_apply = subparsers.add_parser("apply", help="Apply translations back to a Unity asset file.")
    parser_apply.add_argument("--trans", required=True, help="The translated Paratranz JSON file.")
    parser_apply.add_argument("--src", required=True, help="The original source Unity asset file.")
    parser_apply.add_argument("--dll-folder", required=True, help="Path to the Managed folder containing game DLLs.")
    parser_apply.add_argument("--unity-version", required=True, help="The Unity version of the game (e.g., '2019.4.16f1').")
    parser_apply.add_argument("--output", required=True, help="The path to save the modified Unity asset file.")
    parser_apply.set_defaults(func=apply)

    # --- Pipeline Command ---
    parser_pipeline = subparsers.add_parser("pipeline", help="Run the full extract-update-apply-change_font pipeline.")
    # Extract args
    parser_pipeline.add_argument("--input-asset", required=True, help="The source Unity asset file to start the pipeline.")
    # Shared args
    parser_pipeline.add_argument("--dll-folder", required=True, help="Path to the Managed folder containing game DLLs.")
    parser_pipeline.add_argument("--unity-version", required=True, help="The Unity version of the game.")
    # Update args
    parser_pipeline.add_argument("--tool-project-dir", required=True, help="Path to the DllTranslation C# project directory.")
    parser_pipeline.add_argument("--old-trans-dir", required=True, help="Directory with old Paratranz JSON translations for the update step.")
    # Change Font args
    parser_pipeline.add_argument("--new-font-asset", required=True, help="The asset file containing the new font assets and textures.")
    parser_pipeline.add_argument("--font-config", required=True, help="Path to the JSON config file for font replacement.")
    parser_pipeline.add_argument("--new-font-dll-folder", required=True, help="Path to the Managed folder for the NEW FONT asset.")
    # Final output
    parser_pipeline.add_argument("--output-asset", required=True, help="The final output path for the modified asset file.")
    parser_pipeline.add_argument("--work-dir", default="./pipeline_workdir", help="Directory to store intermediate files.")
    parser_pipeline.set_defaults(func=pipeline)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()