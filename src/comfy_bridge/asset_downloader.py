"""把 ComfyUI 的输出下载到本地，并按素材名命名。

命名约定：`<名字>.<扩展名>`；一次任务多个文件时加 `_0`、`_1` 下标。
同名文件默认不覆盖（纪律），改为加 `_v2` 序号，避免悄悄覆盖上一版素材。
"""
from __future__ import annotations

import logging
from pathlib import Path

from .http_client import ComfyHttpClient
from .output_collector import CollectedOutput

LOGGER = logging.getLogger(__name__)


def unique_destination(directory: Path, base_name: str, suffix: str) -> Path:
    """同名文件存在就加 _v2、_v3……不覆盖。"""
    candidate = directory / f"{base_name}{suffix}"
    version = 2
    while candidate.exists():
        candidate = directory / f"{base_name}_v{version}{suffix}"
        version += 1
    return candidate


def download_outputs(client: ComfyHttpClient, outputs: list[CollectedOutput],
                     directory: Path, base_name: str) -> list[Path]:
    """逐个下载并落地，返回保存路径。"""
    directory.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, output in enumerate(outputs):
        content = client.download_output(output.filename, output.subfolder, output.storage_type)
        suffix = Path(output.filename).suffix or ".bin"
        name = base_name if len(outputs) == 1 else f"{base_name}_{index}"
        destination = unique_destination(directory, name, suffix)
        destination.write_bytes(content)
        LOGGER.debug("下载 %s -> %s（%d KB，来自节点 %s.%s）",
                     output.filename, destination, len(content) // 1024, output.node_id, output.output_key)
        saved.append(destination)
    return saved
