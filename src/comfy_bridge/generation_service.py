"""一次素材生成的完整流程：提交 → 等待 → 收集 → 下载 → 记账。

这是 comfy_bridge 里唯一把所有零件串起来的类；命令行只调它，不直接碰 HTTP。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .asset_downloader import download_outputs
from .asset_log_writer import append_asset_record
from .http_client import ComfyHttpClient
from .job_waiter import DEFAULT_TIMEOUT_SECONDS, wait_for_completion
from .output_collector import collect_outputs
from .workflow_editor import referenced_model_files

LOGGER = logging.getLogger(__name__)


class GenerationResult:
    """一次生成的结果，供命令行打印与测试断言。"""

    def __init__(self, prompt_id: str, files: list[Path], seconds: float,
                 model_files: dict[str, list[str]], log_path: Path | None) -> None:
        self.prompt_id = prompt_id
        self.files = files
        self.seconds = seconds
        self.model_files = model_files
        self.log_path = log_path


class AssetGenerationService:
    """执行一次生成。"""

    def __init__(self, client: ComfyHttpClient) -> None:
        self.client = client

    def generate(self, workflow: dict, workflow_label: str, output_directory: Path,
                 asset_name: str, seed: int | None = None,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                 progress_callback=None, write_log: bool = True) -> GenerationResult:
        started_at = time.monotonic()
        prompt_id = self.client.submit_workflow(workflow)
        LOGGER.info("已排队 %s（%s）", prompt_id, workflow_label)

        history_entry = wait_for_completion(
            self.client, prompt_id, timeout_seconds=timeout_seconds, progress_callback=progress_callback
        )
        seconds = time.monotonic() - started_at

        outputs = collect_outputs(history_entry)
        files = download_outputs(self.client, outputs, output_directory, asset_name)
        log_path: Path | None = None
        if write_log:
            model_files = referenced_model_files(workflow)
            log_path = append_asset_record(output_directory, {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "local-comfy",
                "workflow": workflow_label,
                "asset_name": asset_name,
                "prompt_id": prompt_id,
                "seed": seed,
                "seconds": round(seconds, 1),
                "models": model_files,
                "files": [str(path) for path in files],
            })
        else:
            model_files = referenced_model_files(workflow)

        if not files:
            LOGGER.warning("任务完成但没有产出文件，检查工作流末尾是否有 Save* 节点")
        return GenerationResult(prompt_id, files, seconds, model_files, log_path)
