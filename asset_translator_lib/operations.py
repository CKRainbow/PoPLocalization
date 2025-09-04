import json
import re
from typing import Dict, List, cast

import UnityPy
from UnityPy.classes import MonoBehaviour
from UnityPy.helpers.Tpk import get_typetree_node

from .common import ParatranzEntry
from .hierarchy import construct_scene_hierarchy
from .processors import get_processor_for_script


def core_extract(env: UnityPy.Environment, source_file_name: str) -> List[ParatranzEntry]:
    """
    Core logic for extracting text from a loaded UnityPy Environment.
    Operates in memory and returns a list of ParatranzEntry objects.
    """
    scene_hierarchy = construct_scene_hierarchy(env)
    paratranz_entries: List[ParatranzEntry] = []

    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                script_name = script.m_Name

                ProcessorClass = get_processor_for_script(script_name)
                if ProcessorClass:
                    processor = ProcessorClass(obj, scene_hierarchy)
                    entries = processor.extract()
                    paratranz_entries.extend(entries)

            except Exception as e:
                print(f"Warning: Failed to process PathID {obj.path_id}. Reason: {e}")
                
    return paratranz_entries


def core_apply(env: UnityPy.Environment, trans_file_path: str) -> UnityPy.Environment:
    """
    Core logic for applying translations. Operates on a loaded UnityPy Environment.
    """
    with open(trans_file_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)

    translated_entries = [e for e in trans_data if e and e.get("context")]
    
    # Group translations by object identifier (path_id, script_name, gameObject_path_id)
    entry_map: Dict[tuple, List[Dict]] = {}
    path_id_set = set()
    for entry in translated_entries:
        try:
            context = entry["context"]
            path_id = int(re.search(r"PathID:\s*(\d+)", context).group(1))
            script = re.search(r"Script:\s*(.+)", context).group(1)
            game_object_id = int(re.search(r"GameObjectID:\s*(\d+)", context).group(1))
            
            key = (path_id, script, game_object_id)
            if key not in entry_map:
                entry_map[key] = []
            entry_map[key].append(entry)
            path_id_set.add(path_id)
        except (AttributeError, IndexError):
            print(f"Warning: Could not parse context for entry with key '{entry.get('key')}'. Skipping.")

    if not entry_map:
        print("No valid translations with context found, skipping apply.")
        return env

    modified_count = 0
    scene_hierarchy = construct_scene_hierarchy(env) # Needed for context in processors

    for obj in env.objects:
        if obj.type.name == "MonoBehaviour" and obj.path_id in path_id_set:
            try:
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                script_name = script.m_Name

                data = obj.read_typetree()
                game_object_id = data["m_GameObject"]["m_PathID"]
                
                key = (obj.path_id, script_name, game_object_id)
                if key in entry_map:
                    ProcessorClass = get_processor_for_script(script_name)
                    if ProcessorClass:
                        processor = ProcessorClass(obj, scene_hierarchy)
                        if processor.apply(entry_map[key]):
                            modified_count += 1
            except Exception as e:
                print(f"Warning: Failed to process PathID {obj.path_id}. Reason: {e}")
    
    print(f"Applied translations to {modified_count} components in memory.")
    return env


def font_asset_adoption(src_typetree: Dict, target_typetree: Dict) -> Dict:
    """
    Adopts essential properties from an old font asset typetree to a new one.
    This preserves references and metadata within the target asset file.
    """
    src_typetree["m_Script"]["m_PathID"] = target_typetree["m_Script"]["m_PathID"]
    src_typetree["m_Name"] = target_typetree["m_Name"]
    src_typetree["hashCode"] = target_typetree["hashCode"]
    src_typetree["material"]["m_PathID"] = target_typetree["material"]["m_PathID"]
    src_typetree["materialHashCode"] = target_typetree["materialHashCode"]
    src_typetree["m_SourceFontFileGUID"] = target_typetree["m_SourceFontFileGUID"]
    src_typetree["m_FaceInfo"]["m_FamilyName"] = target_typetree["m_FaceInfo"]["m_FamilyName"]
    
    for i, old_atlas_texture in enumerate(target_typetree["m_AtlasTextures"]):
        if i < len(src_typetree["m_AtlasTextures"]) and "m_PathID" in old_atlas_texture:
            src_typetree["m_AtlasTextures"][i]["m_PathID"] = old_atlas_texture["m_PathID"]

    if "sourceFontFileGUID" in target_typetree["m_CreationSettings"]:
        src_typetree["m_CreationSettings"]["sourceFontFileGUID"] = target_typetree["m_CreationSettings"]["sourceFontFileGUID"]
    if "referencedFontAssetGUID" in target_typetree["m_CreationSettings"]:
        src_typetree["m_CreationSettings"]["referencedFontAssetGUID"] = target_typetree["m_CreationSettings"]["referencedFontAssetGUID"]
    return src_typetree


def core_change_font(
    target_env: UnityPy.Environment,
    new_font_env: UnityPy.Environment,
    config: Dict,
) -> UnityPy.Environment:
    """
    Core logic for changing fonts and related assets based on a config file.
    Operates on a loaded UnityPy Environment.
    """
    def build_maps(env: UnityPy.Environment, config: Dict):
        font_asset_config = config.get("font_assets", None)
        texture_config = config.get("textures", None)
        material_config = config.get("materials", None)

        font_assets, textures, materials = {}, {}, {}

        for obj in env.objects:
            if font_asset_config and obj.type.name == 'MonoBehaviour' and obj.path_id in font_asset_config["path_id"]:
                node = get_typetree_node(obj.class_id, obj.version)
                monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
                script = monobehaviour.m_Script.deref_parse_as_object()
                if script.m_Name == "TMP_FontAsset":
                    font_assets[obj.path_id] = obj
            elif texture_config and obj.type.name == 'Texture2D' and obj.path_id in texture_config["path_id"]:
                data = obj.read()
                if data.m_Name in texture_config["name"]:
                    textures[(obj.path_id, data.m_Name)] = obj
            elif material_config and obj.type.name == 'Material' and obj.path_id in material_config["path_id"]:
                typetree = obj.read_typetree()
                if typetree["m_Name"] in material_config["name"]:
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
            config["source"]["textures"]["path_id"], config["source"]["textures"]["name"], 
            config["target"]["textures"]["path_id"], config["target"]["textures"]["name"]
        ):
            source_texture_obj = source_textures.get((src_path_id, src_name))
            new_texture_obj = new_textures.get((new_path_id, new_name))
            if not source_texture_obj or not new_texture_obj:
                raise ValueError(f"PathID mapping for texture (Texture2D) {src_path_id}->{new_path_id} is invalid.")
            src_data, new_data = source_texture_obj.read(), new_texture_obj.read()
            new_data.image = src_data.image
            new_data.m_Width, new_data.m_Height = src_data.m_Width, src_data.m_Height
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
                    if name == "_UnderlayOffsetX": floats[i] = (name, 0.1); modified = True
                    elif name == "_UnderlayOffsetY": floats[i] = (name, -0.1); modified = True
                if modified:
                    new_material_obj.save_typetree(material_typetree)
                    print(f"  - Modified Material: PathID {new_path_id}")

    return target_env