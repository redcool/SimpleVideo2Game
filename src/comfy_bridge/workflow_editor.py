"""改写工作流：设置输入、设置 seed、列出用到的模型。

只改字典，不碰 HTTP。这样 `--dry-run` 能在不提交任何任务的情况下检查改写结果。
"""
from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)

MODEL_FILE_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft")
SEED_INPUT_NAMES = ("seed", "noise_seed")


class WorkflowEditError(ValueError):
    """要改的节点或输入不存在。"""


def node_ids_matching(workflow: dict, class_substring: str | None = None,
                      input_name: str | None = None) -> list[str]:
    """按类名子串和/或输入名筛选节点。"""
    matched: list[str] = []
    for node_id, node in workflow.items():
        if class_substring and class_substring not in str(node.get("class_type", "")):
            continue
        if input_name and input_name not in (node.get("inputs") or {}):
            continue
        matched.append(node_id)
    return matched


def set_input(workflow: dict, target: str, value) -> list[tuple[str, str]]:
    """设置输入。target 形如 `input`（所有拥有该输入的节点）或 `节点id.input`。

    返回真正被改动的 (节点id, 输入名) 列表，让调用方能报告"改动了几个节点"，
    而不是悄悄把半个图改掉。
    """
    if "." in target:
        node_id, input_name = target.split(".", 1)
        if node_id not in workflow:
            raise WorkflowEditError(f"工作流里没有节点 {node_id!r}")
        workflow[node_id].setdefault("inputs", {})[input_name] = value
        return [(node_id, input_name)]

    changed: list[tuple[str, str]] = []
    for node_id, node in workflow.items():
        if target in (node.get("inputs") or {}):
            node["inputs"][target] = value
            changed.append((node_id, target))
    if not changed:
        similar = sorted({key for node in workflow.values()
                          for key in (node.get("inputs") or {}) if target.lower() in key.lower()})
        hint = f"；相近的输入名：{', '.join(similar[:8])}" if similar else ""
        raise WorkflowEditError(
            f"没有节点带名为 {target!r} 的输入{hint}。用 --dry-run 先看一遍图。"
        )
    return changed


def set_seed(workflow: dict, seed: int) -> list[tuple[str, str]]:
    """把所有 seed / noise_seed 输入设为同一个值，保证可复现。"""
    changed: list[tuple[str, str]] = []
    for node_id, node in workflow.items():
        inputs = node.get("inputs") or {}
        for name in SEED_INPUT_NAMES:
            if name in inputs:
                inputs[name] = seed
                changed.append((node_id, name))
    return changed


def referenced_model_files(workflow: dict) -> dict[str, list[str]]:
    """列出工作流引用的模型文件，按输入名分组（用于记账）。"""
    used: dict[str, list[str]] = {}
    for node in workflow.values():
        for name, value in (node.get("inputs") or {}).items():
            if isinstance(value, str) and value.lower().endswith(MODEL_FILE_SUFFIXES):
                used.setdefault(name, []).append(value)
    return used
