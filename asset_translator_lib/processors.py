import re
from abc import ABC, abstractmethod
from typing import Dict, List, Type, Optional, cast

import UnityPy
from UnityPy.classes import MonoBehaviour
from UnityPy.helpers.Tpk import get_typetree_node

from .common import ParatranzEntry, generate_hash


class MonoBehaviourProcessor(ABC):
    """Abstract base class for processing different MonoBehaviour types."""

    def __init__(self, obj: UnityPy.classes.Object, scene_hierarchy: Dict):
        self.obj = obj
        self.data = obj.read_typetree()
        node = get_typetree_node(obj.class_id, obj.version)
        monobehaviour = cast(MonoBehaviour, obj.parse_as_object(node, check_read=False))
        script = monobehaviour.m_Script.deref_parse_as_object()
        self.script_name = script.m_Name
        self.game_object_path_id = self.data["m_GameObject"]["m_PathID"]
        scene = self.obj.assets_file.name
        self.game_object_path = scene_hierarchy.get(scene, {}).get(self.game_object_path_id, "UnknownPath")

    @classmethod
    @abstractmethod
    def can_handle(cls, script_name: str) -> bool:
        """Check if this processor can handle the given script name."""
        pass

    @abstractmethod
    def extract(self) -> List[ParatranzEntry]:
        """Extract text entries from the MonoBehaviour."""
        pass

    @abstractmethod
    def apply(self, translations: List[Dict]) -> bool:
        """Apply translations to the MonoBehaviour."""
        pass


class TextProcessor(MonoBehaviourProcessor):
    """Processor for standard text components (like TextMeshPro)."""

    @classmethod
    def can_handle(cls, script_name: str) -> bool:
        return "text" in script_name.lower()

    def extract(self) -> List[ParatranzEntry]:
        original_text = None
        if "m_text" in self.data and self.data["m_text"]:
            original_text = self.data["m_text"]
        elif "m_Text" in self.data and self.data["m_Text"]:
            original_text = self.data["m_Text"]

        if not original_text:
            return []

        key_source = f"{self.game_object_path_id}:{self.script_name}:{self.obj.path_id}:{original_text}"
        key = generate_hash(key_source)
        context = f"GameObjectID: {self.game_object_path_id}\nGameObjectPath: {self.game_object_path}\nPathID: {self.obj.path_id}\nScript: {self.script_name}"

        entry = ParatranzEntry(
            key=key,
            original=original_text,
            translation="",
            stage=0,
            context=context,
        )
        return [entry]

    def apply(self, translations: List[Dict]) -> bool:
        if not translations:
            return False
            
        translation = translations[0].get("translation")
        if not translation:
            return False

        modified = False
        if "m_text" in self.data and self.data["m_text"]:
            self.data["m_text"] = translation
            modified = True
        elif "m_Text" in self.data and self.data["m_Text"]:
            self.data["m_Text"] = translation
            modified = True
        
        if modified:
            self.obj.save_typetree(self.data)
        return modified


class ItemControllerProcessor(MonoBehaviourProcessor):
    """Processor for ItemController scripts."""

    ITEM_CATEGORIES = ["commonItems", "rareItems", "legendaryItems", "specialItems", "mythicItems"]

    @classmethod
    def can_handle(cls, script_name: str) -> bool:
        return "itemcontroller" in script_name.lower()

    def extract(self) -> List[ParatranzEntry]:
        entries = []
        for category in self.ITEM_CATEGORIES:
            for item in self.data.get(category, []):
                name = item.get("name")
                description = item.get("description")
                if not name or not description:
                    continue

                key_source = f"{self.game_object_path_id}:{self.script_name}:{self.obj.path_id}:{category}:{name}:{description}"
                key = generate_hash(key_source)
                context = f"GameObjectID: {self.game_object_path_id}\nPathID: {self.obj.path_id}\nScript: {self.script_name}\nJsonPath: {category}_{name}"

                entries.append(ParatranzEntry(
                    key=key,
                    original=description,
                    translation="",
                    stage=0,
                    context=context,
                ))
        return entries

    def apply(self, translations: List[Dict]) -> bool:
        if not translations:
            return False

        translation_map = {
            re.search(r"JsonPath:\s*(.+)", entry["context"]).group(1): entry["translation"]
            for entry in translations if entry.get("translation")
        }
        
        if not translation_map:
            return False

        modified = False
        for category in self.ITEM_CATEGORIES:
            for item in self.data.get(category, []):
                name = item.get("name")
                if not name or not item.get("description"):
                    continue
                
                lookup_key = f"{category}_{name}"
                if lookup_key in translation_map:
                    item["description"] = translation_map[lookup_key]
                    modified = True

        if modified:
            self.obj.save_typetree(self.data)
        return modified


class DropdownProcessor(MonoBehaviourProcessor):
    """Processor for Dropdown components."""
    
    @classmethod
    def can_handle(cls, script_name: str) -> bool:
        return "dropdown" in script_name.lower()

    def extract(self) -> List[ParatranzEntry]:
        entries = []
        options = self.data.get("m_Options", {}).get("m_Options", [])
        for option in options:
            original_text = option.get("m_Text")
            if not original_text:
                continue

            key_source = f"{self.game_object_path_id}:{self.script_name}:{self.obj.path_id}:{original_text}"
            key = generate_hash(key_source)
            context = f"GameObjectID: {self.game_object_path_id}\nPathID: {self.obj.path_id}\nScript: {self.script_name}"

            entries.append(ParatranzEntry(
                key=key,
                original=original_text,
                translation="",
                stage=0,
                context=context,
            ))
        return entries

    def apply(self, translations: List[Dict]) -> bool:
        if not translations:
            return False

        translation_map = {
            entry["original"]: entry["translation"]
            for entry in translations if entry.get("translation")
        }

        if not translation_map:
            return False

        options = self.data.get("m_Options", {}).get("m_Options", [])
        modified = False
        for option in options:
            original_text = option.get("m_Text")
            if original_text in translation_map:
                option["m_Text"] = translation_map[original_text]
                modified = True
        
        if modified:
            self.obj.save_typetree(self.data)
        return modified


# List of available processors. To add support for a new type, just add its class here.
PROCESSOR_CLASSES: List[Type[MonoBehaviourProcessor]] = [
    ItemControllerProcessor,
    DropdownProcessor,
    TextProcessor,  # TextProcessor should be last as it's a bit generic
]

def get_processor_for_script(script_name: str) -> Optional[Type[MonoBehaviourProcessor]]:
    """Finds the appropriate processor class for a given script name."""
    for processor_class in PROCESSOR_CLASSES:
        if processor_class.can_handle(script_name):
            return processor_class
    return None