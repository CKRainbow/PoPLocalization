import argparse
import json
import os
import subprocess
import shutil
from dataclasses import asdict

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

from asset_translator_lib.operations import core_apply, core_change_font, core_extract

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
                    indented_context = "      ".join(context.splitlines(True))
                    print(f"    - \033[96mContext {i+1}:\033[0m\n      ---\n      {indented_context}\n      ---")
        
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
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

    command = [
        "dotnet", "run", "--project", project_dir, "--",
        "update-asset", "--old", old_dir, "--new", new_dir, "--output", output_dir,
    ]

    print(f"Running command: {' '.join(command)}")

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        rc = process.poll()
        if rc != 0:
            raise RuntimeError(f"Update command failed with return code {rc}. Check the output above for details.")
        
        print("Update command executed successfully.")

    except FileNotFoundError:
        raise RuntimeError("Error: 'dotnet' command not found. Please ensure the .NET SDK is installed and in your PATH.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while running the update command: {e}")


def change_font(args):
    """
    Wrapper for changing font. Handles file I/O and calls the core logic.
    """
    print("Executing 'change_font' command...")

    if not all(os.path.exists(p) for p in [args.target_asset, args.new_font_asset, args.config, args.dll_folder, args.new_font_dll_folder]):
        print("Error: One or more input files/folders not found.")
        return

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        shutil.copy2(args.target_asset, args.output)
        
        target_generator = TypeTreeGenerator(args.unity_version)
        target_generator.load_local_dll_folder(args.dll_folder)
        target_env = UnityPy.load(args.output)
        target_env.typetree_generator = target_generator

        new_font_generator = TypeTreeGenerator(args.unity_version)
        new_font_generator.load_local_dll_folder(args.new_font_dll_folder)
        new_font_env = UnityPy.load(args.new_font_asset)
        new_font_env.typetree_generator = new_font_generator

        modified_env = core_change_font(target_env, new_font_env, config_data)

        with open(args.output, "wb") as f:
            f.write(modified_env.file.save())
        
        print(f"Successfully changed font and saved to '{args.output}'")
    except Exception as e:
        print(f"An error occurred during change_font: {e}")


def apply(args):
    """
    Wrapper for applying translations. Handles file I/O and calls the core logic.
    """
    print("Executing 'apply' command...")

    if not all(os.path.exists(p) for p in [args.trans, args.src, args.dll_folder]):
        print("Error: One or more input files/folders not found.")
        return

    try:
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        shutil.copy2(args.src, args.output)

        generator = TypeTreeGenerator(args.unity_version)
        generator.load_local_dll_folder(args.dll_folder)
        env = UnityPy.load(args.output)
        env.typetree_generator = generator

        modified_env = core_apply(env, args.trans)

        with open(args.output, "wb") as f:
            f.write(modified_env.file.save(packer="lz4"))
        
        print(f"Successfully saved applied translations to '{args.output}'")
    except Exception as e:
        print(f"An error occurred during apply: {e}")


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
                raise FileNotFoundError(f"Critical: Updated translation file '{updated_json_path}' was not generated. Halting.")
            
            modified_env = core_apply(env, updated_json_path)
        
        # === Step 4: Change Font (in memory) ===
        print("\n--- [Step 4/4] Changing font ---")
        with open(args.font_config, "r", encoding="utf-8") as f:
            font_config_data = json.load(f)
        
        new_font_generator = TypeTreeGenerator(args.unity_version)
        new_font_generator.load_local_dll_folder(args.new_font_dll_folder)
        new_font_env = UnityPy.load(args.new_font_asset)
        new_font_env.typetree_generator = new_font_generator

        final_env = core_change_font(modified_env, new_font_env, font_config_data)

        # === Final Step: Save to File ===
        print("\n--- [Final] Saving all changes to output file ---")
        os.makedirs(os.path.dirname(args.output_asset), exist_ok=True)
        with open(args.output_asset, "wb") as f:
            f.write(final_env.file.save(packer="lz4"))

        print(f"\n✅ Pipeline finished successfully! Final asset saved to '{args.output_asset}'")

    except Exception as e:
        print(f"\n❌ An error occurred during the pipeline: {e}")
        raise


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
    parser_pipeline.add_argument("--input-asset", required=True, help="The source Unity asset file to start the pipeline.")
    parser_pipeline.add_argument("--dll-folder", required=True, help="Path to the Managed folder containing game DLLs.")
    parser_pipeline.add_argument("--unity-version", required=True, help="The Unity version of the game.")
    parser_pipeline.add_argument("--tool-project-dir", required=True, help="Path to the DllTranslation C# project directory.")
    parser_pipeline.add_argument("--old-trans-dir", required=True, help="Directory with old Paratranz JSON translations for the update step.")
    parser_pipeline.add_argument("--new-font-asset", required=True, help="The asset file containing the new font assets and textures.")
    parser_pipeline.add_argument("--font-config", required=True, help="Path to the JSON config file for font replacement.")
    parser_pipeline.add_argument("--new-font-dll-folder", required=True, help="Path to the Managed folder for the NEW FONT asset.")
    parser_pipeline.add_argument("--output-asset", required=True, help="The final output path for the modified asset file.")
    parser_pipeline.add_argument("--work-dir", default="./pipeline_workdir", help="Directory to store intermediate files.")
    parser_pipeline.set_defaults(func=pipeline)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()