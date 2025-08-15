import argparse
import json
import os
from typing import Dict

def parse_context(context_str: str) -> Dict[str, str]:
    """Parses a context string into a dictionary."""
    context_info = {}
    if not context_str:
        return context_info
    for line in context_str.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            context_info[key.strip()] = value.strip()
    return context_info

def migrate(args):
    """
    Merges translations from an old Paratranz JSON file into a new-format one
    by matching Script and PathID.
    """
    print("Starting translation merge...")

    # 1. Validate paths
    if not os.path.isfile(args.old_json):
        print(f"Error: Old JSON file not found at '{args.old_json}'")
        return
    if not os.path.isfile(args.new_json):
        print(f"Error: New-format JSON file not found at '{args.new_json}'")
        return

    # 2. Load old translation data into a lookup map based on Script, PathID and original text
    print(f"Loading old translations from '{args.old_json}'...")
    with open(args.old_json, "r", encoding="utf-8") as f:
        old_data = json.load(f)

    print(f"Loaded {len(old_data)} old-format entries.")
    
    translation_lookup = {}
    for entry in old_data:
        context_info = parse_context(entry.get("context"))
        script_name = context_info.get("Script")
        path_id = context_info.get("PathID")
        original_text = entry.get("original")

        if script_name and path_id and original_text:
            composite_key = f"{script_name}:{path_id}:{original_text}"
            if composite_key in translation_lookup:
                print(f"Warning: Duplicate key found in old file: {composite_key}")
            else:
                translation_lookup[composite_key] = entry
    
    print(f"Loaded {len(translation_lookup)} translations into the lookup map.")

    # 3. Load the new-format JSON file
    print(f"Loading new-format entries from '{args.new_json}'...")
    with open(args.new_json, "r", encoding="utf-8") as f:
        new_data = json.load(f)
    print(f"Loaded {len(new_data)} new-format entries.")

    # 4. Check for duplicates in the new file
    print("Checking for duplicates in new file (same PathID, Script, GameObjectID)...")
    seen_entries = {}
    duplicates_found = False
    for entry in new_data:
        context_info = parse_context(entry.get("context"))
        path_id = context_info.get("PathID")
        script_name = context_info.get("Script")
        game_object_id = context_info.get("GameObjectID")

        if path_id and script_name and game_object_id:
            duplicate_key = f"{script_name}:{path_id}:{game_object_id}"
            if duplicate_key in seen_entries:
                if not duplicates_found:
                    print("Warning: Found entries with the same PathID, Script, and GameObjectID:")
                    duplicates_found = True
                
                # Print the first occurrence if it hasn't been printed yet
                if seen_entries[duplicate_key] is not None:
                    print(f"- Key: {duplicate_key}")
                    print(f"  - Original 1: '{seen_entries[duplicate_key]}'")
                    seen_entries[duplicate_key] = None # Mark as printed
                
                print(f"  - Original 2: '{entry.get('original')}'")
            else:
                seen_entries[duplicate_key] = entry.get('original')

    if not duplicates_found:
        print("No duplicates found.")


    merged_keys = set()
    unmatched_new_keys = []

    # 4. Iterate through new data and merge translations using the lookup map
    updated_count = 0
    for entry in new_data:
        context_info = parse_context(entry.get("context"))
        script_name = context_info.get("Script")
        path_id = context_info.get("PathID")
        original_text = entry.get("original")

        if script_name and path_id and original_text:
            composite_key = f"{script_name}:{path_id}:{original_text}"
            if composite_key in translation_lookup:
                old_entry = translation_lookup[composite_key]
                
                # Update translation and stage if they exist in the old entry
                if "translation" in old_entry:
                    entry["translation"] = old_entry["translation"]
                if "stage" in old_entry:
                    entry["stage"] = old_entry["stage"]
                
                updated_count += 1
                merged_keys.add(composite_key)
            else:
                unmatched_new_keys.append(composite_key)
    
    print(f"Successfully merged translations for {updated_count} entries.")

    # Show entries from the old file that were not merged into the new file
    not_merged_old = [key for key in translation_lookup if key not in merged_keys]
    if not_merged_old:
        print(f"Warning: {len(not_merged_old)} entries from the old file were not found in the new file:")
        for key in not_merged_old:
            print(f"- {key}")

    # Show entries from the new file that did not receive a translation
    if unmatched_new_keys:
        print(f"Info: {len(unmatched_new_keys)} entries from the new file did not find a matching translation in the old file:")
        # To avoid spamming, let's show only unique keys
        for key in sorted(list(set(unmatched_new_keys))):
            print(f"- {key}")

    # 5. Write the updated data to the output file
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=4)
    print(f"Merged translation file saved to '{args.output}'")


def main():
    parser = argparse.ArgumentParser(
        description="A tool to merge translations from an old Paratranz JSON file into a new-format one.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--old-json", required=True, help="The old-format Paratranz JSON file containing the translations.")
    parser.add_argument("--new-json", required=True, help="The new-format Paratranz JSON file with correct keys/context.")
    parser.add_argument("--output", required=True, help="The path to save the final, merged Paratranz JSON file.")
    
    args = parser.parse_args()
    migrate(args)

if __name__ == "__main__":
    main()