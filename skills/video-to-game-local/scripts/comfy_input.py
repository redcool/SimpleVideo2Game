#!/usr/bin/env python3
"""把本地文件送进 ComfyUI 的 input 目录，返回工作流里该写的文件名。

为什么需要这一层：ComfyUI 的 LoadImage 只认自己 input/ 里的文件名，
不接受任意绝对路径。所以「用这张图跑工作流」必须先落地一个文件。

命名策略：保留原名 + 内容哈希前缀（如 `a1b2c3d4_hero.png`）。
这样既不会覆盖已有文件（纪律：同名不覆盖），也顺便打破 ComfyUI 的同名缓存。

输入目录按以下顺序解析，命中即用：
1. 环境变量 `COMFY_INPUT`（直接指到目录）
2. 环境变量 `COMFY_HOME` + `/ComfyUI/input`（ComfyUI portable 结构）
3. 都不可用 → 明确报错并说明怎么配，不猜路径。
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

COMFY_HOME_ENV = "COMFY_HOME"
COMFY_INPUT_ENV = "COMFY_INPUT"


def resolve_input_directory() -> Path:
    """返回可写的 ComfyUI input 目录。"""
    explicit = os.environ.get(COMFY_INPUT_ENV)
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_dir():
            raise SystemExit(f"{COMFY_INPUT_ENV} 指向的目录不存在：{candidate}")
        return candidate

    home = os.environ.get(COMFY_HOME_ENV)
    if home:
        candidate = Path(home).expanduser() / "ComfyUI" / "input"
        if candidate.is_dir():
            return candidate
        raise SystemExit(
            f"{COMFY_HOME_ENV}={home} 下没有 ComfyUI/input 目录。"
            f"请把 {COMFY_HOME_ENV} 指到 ComfyUI portable 根目录，或直接设 {COMFY_INPUT_ENV}。"
        )

    raise SystemExit(
        f"不知道 ComfyUI 的 input 目录：请设 {COMFY_HOME_ENV}（portable 根目录）"
        f"或 {COMFY_INPUT_ENV}（input 目录本身）。"
    )


def content_prefix(path: Path) -> str:
    """文件内容的短哈希，用于避免同名覆盖与缓存命中。"""
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:8]


def stage_input_file(local_path: Path) -> str:
    """复制到 ComfyUI input/，返回工作流里应使用的文件名。"""
    if not local_path.is_file():
        raise SystemExit(f"要上传的文件不存在：{local_path}")
    target_directory = resolve_input_directory()
    target_name = f"{content_prefix(local_path)}_{local_path.name}"
    target_path = target_directory / target_name
    if not target_path.exists():
        shutil.copyfile(local_path, target_path)
    return target_name
