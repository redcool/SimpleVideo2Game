"""把本地参考图送进 ComfyUI 的 input/，返回工作流里该写的文件名。

为什么需要：`LoadImage` 只认 ComfyUI 自己 input/ 里的文件名，不接受任意绝对路径。
命名用"内容哈希前缀 + 原名"，既不覆盖同名文件（纪律），也顺便打破 ComfyUI 的同名缓存。
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path

LOGGER = logging.getLogger(__name__)

HOME_ENV_NAME = "COMFY_HOME"
INPUT_ENV_NAME = "COMFY_INPUT"


class InputStagingError(RuntimeError):
    """找不到 ComfyUI 的 input 目录，或参考图不存在。"""


def resolve_input_directory() -> Path:
    """按 COMFY_INPUT → COMFY_HOME/ComfyUI/input 的顺序解析，都不行就报错。"""
    explicit = os.environ.get(INPUT_ENV_NAME)
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_dir():
            raise InputStagingError(f"{INPUT_ENV_NAME} 指向的目录不存在：{candidate}")
        return candidate

    home = os.environ.get(HOME_ENV_NAME)
    if home:
        candidate = Path(home).expanduser() / "ComfyUI" / "input"
        if candidate.is_dir():
            return candidate
        raise InputStagingError(
            f"{HOME_ENV_NAME}={home} 下没有 ComfyUI/input。请把它指到 ComfyUI portable 根目录，"
            f"或直接设 {INPUT_ENV_NAME}。"
        )

    raise InputStagingError(
        f"不知道 ComfyUI 的 input 目录：请设 {HOME_ENV_NAME}（portable 根目录）或 {INPUT_ENV_NAME}（input 目录本身）。"
    )


def content_prefix(path: Path) -> str:
    """文件内容的短哈希。"""
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:8]


def stage_input_file(local_path: Path) -> str:
    """复制到 ComfyUI input/，返回文件名。"""
    if not local_path.is_file():
        raise InputStagingError(f"要送进 ComfyUI 的文件不存在：{local_path}")
    target_directory = resolve_input_directory()
    target_name = f"{content_prefix(local_path)}_{local_path.name}"
    target_path = target_directory / target_name
    if not target_path.exists():
        shutil.copyfile(local_path, target_path)
        LOGGER.debug("已复制参考图到 %s", target_path)
    return target_name
