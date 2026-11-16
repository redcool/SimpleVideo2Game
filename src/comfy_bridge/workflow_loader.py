"""读入并校验 ComfyUI 的 **API 格式**工作流。

为什么校验：ComfyUI 的界面能导出两种 JSON——"文件格式（UI 格式）"带 nodes/links，
"Export (API)" 才是 `{节点id: {class_type, inputs}}`。后者才能直接喂 /prompt。
搞混的人会在这里卡很久，所以错误信息要说清楚去哪导出。
"""
from __future__ import annotations

import json
from pathlib import Path

IMAGE_ALT_SUFFIX = ".json"


class WorkflowFormatError(ValueError):
    """工作流不是 API 格式，或文件不可读。"""


def looks_like_api_workflow(candidate: object) -> bool:
    """每个节点都有 class_type，且整体是非空字典。"""
    return isinstance(candidate, dict) and bool(candidate) and all(
        isinstance(node, dict) and "class_type" in node for node in candidate.values()
    )


def load_api_workflow(path: Path) -> dict:
    """读取工作流；UI 格式与坏 JSON 都要给出可操作的报错。"""
    if not path.is_file():
        raise WorkflowFormatError(f"工作流文件不存在：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowFormatError(f"{path} 不是合法 JSON：{error}") from None
    if isinstance(payload, dict) and ("nodes" in payload or "links" in payload) and not looks_like_api_workflow(payload):
        raise WorkflowFormatError(
            f"{path} 是 ComfyUI 的 UI 格式；请在 ComfyUI 里用 Workflow → Export (API) 另存一份"
        )
    if not looks_like_api_workflow(payload):
        raise WorkflowFormatError(f"{path} 不是 API 格式（应为 {{节点id: {{class_type, inputs}}}}）")
    return payload


def resolve_workflow_argument(argument: str, search_directory: Path) -> Path:
    """把命令行给的名字解析成文件：先当路径，再当 workflows/ 下的名字。"""
    direct = Path(argument)
    if direct.is_file():
        return direct
    for candidate in (search_directory / argument, search_directory / f"{argument}{IMAGE_ALT_SUFFIX}"):
        if candidate.is_file():
            return candidate
    available = sorted(item.name for item in search_directory.glob("*.json")) if search_directory.is_dir() else []
    raise WorkflowFormatError(
        f"找不到工作流 {argument!r}。{search_directory} 里有：{', '.join(available) or '（空）'}"
    )
