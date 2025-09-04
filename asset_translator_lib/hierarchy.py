from typing import Dict, cast
import UnityPy
from UnityPy.classes import GameObject, Transform, RectTransform

def traverse_hierarchy(go: GameObject, path: str, path_id: int, transform: str = "RectTransform"):
    """Recursively traverse the hierarchy of GameObjects."""
    yield go, path_id, path
    transform_component = None
    if transform == "Transform":
        if go.m_Transform:
            transform_component = cast(Transform, go.m_Transform.read())
    elif transform == "RectTransform":
        for component in go.m_Components:
            if component.type.name == "RectTransform":
                transform_component = cast(RectTransform, component.read())
                break

    if not transform_component:
        return

    for child_tf_ptr in transform_component.m_Children:
        child_tf = child_tf_ptr.read()
        if child_tf.m_GameObject:
            child_go = cast(GameObject, child_tf.m_GameObject.read())
            yield from traverse_hierarchy(child_go, f"{path}/{child_go.m_Name}", child_tf.m_GameObject.path_id, transform)

def construct_scene_hierarchy(env: UnityPy.AssetsManager) -> Dict:
    """Gather root objects from the environment."""
    scene_hierarchy = {}
    for asset in env.assets:
        scene_hierarchy[asset.name] = {}
        for path_id, obj in asset.objects.items():
            if obj.type.name == "GameObject":
                if obj.path_id in scene_hierarchy[asset.name]:
                    continue
                go = cast(GameObject, obj.read())
                scene_hierarchy[asset.name][path_id] = go.m_Name
                if any(component.type.name == "RectTransform" for component in go.m_Components):
                    for _, path_id, path in traverse_hierarchy(go, go.m_Name, path_id):
                        scene_hierarchy[asset.name][path_id] = path
                elif go.m_Transform:
                    for _, path_id, path in traverse_hierarchy(go, go.m_Name, path_id, transform="Transform"):
                        scene_hierarchy[asset.name][path_id] = path
    return scene_hierarchy