"""从 ComfyUI 的 history 里挑出可下载文件。

为什么单独一个模块：自定义节点的输出形状不止一种——
图片是 `{filename, subfolder, type}` 字典，3D/音频节点常常只给一个字符串文件名。
两种都要认，认不出的就不猜（宁可少收，不要乱命名）。
"""
from __future__ import annotations

MEDIA_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp4", ".webm", ".mov",
    ".mp3", ".wav", ".flac", ".ogg",
    ".glb", ".gltf", ".obj", ".fbx", ".ply", ".splat",
)


class CollectedOutput:
    """一个待下载的输出文件。"""

    __slots__ = ("node_id", "output_key", "filename", "subfolder", "storage_type")

    def __init__(self, node_id: str, output_key: str, filename: str,
                 subfolder: str = "", storage_type: str = "output") -> None:
        self.node_id = node_id
        self.output_key = output_key
        self.filename = filename
        self.subfolder = subfolder
        self.storage_type = storage_type

    def __repr__(self) -> str:
        return f"CollectedOutput({self.node_id}.{self.output_key} -> {self.filename})"


def collect_outputs(history_entry: dict) -> list[CollectedOutput]:
    """遍历 outputs，收集所有可下载文件。"""
    collected: list[CollectedOutput] = []
    for node_id, node_outputs in (history_entry.get("outputs") or {}).items():
        for output_key, raw_value in (node_outputs or {}).items():
            for item in (raw_value if isinstance(raw_value, list) else [raw_value]):
                if isinstance(item, dict) and item.get("filename"):
                    collected.append(CollectedOutput(
                        node_id=node_id, output_key=output_key, filename=item["filename"],
                        subfolder=item.get("subfolder", ""), storage_type=item.get("type", "output"),
                    ))
                    continue
                if isinstance(item, str) and item.lower().endswith(MEDIA_SUFFIXES):
                    # 有些 3D/音频节点只给相对 output/ 的路径字符串
                    normalized = item.replace("\\", "/")
                    directory, _, name = normalized.rpartition("/")
                    collected.append(CollectedOutput(
                        node_id=node_id, output_key=output_key, filename=name,
                        subfolder=directory, storage_type="output",
                    ))
    return collected
