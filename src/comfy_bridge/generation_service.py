"""一次素材生成的完整流程：提交 → 等待 → 收集 → 下载 → 记账。

这是 comfy_bridge 里唯一把所有零件串起来的类；命令行只调它，不直接碰 HTTP。

为什么要有 submit / collect 两半：H3 视频这类任务要 2-4 分钟，一次性阻塞等待
很容易撞上调用方的墙钟上限（真实发生过：客户端被 600 s 杀掉，成品还躺在 ComfyUI 里）。
拆开之后调用方可以先拿 prompt_id，过一会儿再取回，任务本身不受影响。
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


class SubmittedJob:
    """已提交、尚未取回的任务。--detach 写进磁盘的就是它的字段。"""

    def __init__(self, prompt_id: str, workflow_label: str, asset_name: str,
                 output_directory: Path, seed: int | None, workflow: dict,
                 submitted_at: str) -> None:
        self.prompt_id = prompt_id
        self.workflow_label = workflow_label
        self.asset_name = asset_name
        self.output_directory = output_directory
        self.seed = seed
        self.workflow = workflow
        self.submitted_at = submitted_at

    def to_record(self) -> dict:
        """落盘用：把取回任务所需的全部信息写全，collect 就不需要别的参数。"""
        return {
            "prompt_id": self.prompt_id,
            "workflow_label": self.workflow_label,
            "asset_name": self.asset_name,
            "output_directory": str(self.output_directory),
            "seed": self.seed,
            "submitted_at": self.submitted_at,
            "workflow": self.workflow,
        }

    @classmethod
    def from_record(cls, record: dict) -> "SubmittedJob":
        """从磁盘读回。"""
        return cls(
            prompt_id=record["prompt_id"],
            workflow_label=record["workflow_label"],
            asset_name=record["asset_name"],
            output_directory=Path(record["output_directory"]),
            seed=record.get("seed"),
            workflow=record["workflow"],
            submitted_at=record.get("submitted_at", ""),
        )


class AssetGenerationService:
    """执行一次生成：可以整体跑，也可以拆成提交与取回。"""

    def __init__(self, client: ComfyHttpClient) -> None:
        self.client = client

    def submit(self, workflow: dict, workflow_label: str, output_directory: Path,
               asset_name: str, seed: int | None = None) -> SubmittedJob:
        """只提交，立刻返回任务句柄。"""
        prompt_id = self.client.submit_workflow(workflow)
        LOGGER.info("已排队 %s（%s）", prompt_id, workflow_label)
        return SubmittedJob(prompt_id=prompt_id, workflow_label=workflow_label,
                            asset_name=asset_name, output_directory=output_directory,
                            seed=seed, workflow=workflow,
                            submitted_at=time.strftime("%Y-%m-%d %H:%M:%S"))

    def collect(self, job: SubmittedJob, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                progress_callback=None, write_log: bool = True) -> GenerationResult:
        """等它跑完、下载产物、记账。"""
        started_at = time.monotonic()
        history_entry = wait_for_completion(
            self.client, job.prompt_id, timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
        )
        wait_seconds = time.monotonic() - started_at
        # 记账要写"从提交到产出"的真实耗时：--detach 之后再去 collect，
        # 只记 collect 的等待时间会变成 0.0，看不出这条任务其实跑了多久。
        seconds = wait_seconds
        if job.submitted_at:
            try:
                submitted_epoch = time.mktime(time.strptime(job.submitted_at, "%Y-%m-%d %H:%M:%S"))
                seconds = max(wait_seconds, time.time() - submitted_epoch)
            except ValueError:
                LOGGER.warning("任务句柄里的 submitted_at 解析不了：%r", job.submitted_at)

        outputs = collect_outputs(history_entry)
        files = download_outputs(self.client, outputs, job.output_directory, job.asset_name)
        model_files = referenced_model_files(job.workflow)
        log_path: Path | None = None
        if write_log:
            log_path = append_asset_record(job.output_directory, {
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "local-comfy",
                "workflow": job.workflow_label,
                "asset_name": job.asset_name,
                "prompt_id": job.prompt_id,
                "seed": job.seed,
                "seconds": round(seconds, 1),
                "models": model_files,
                "files": [str(path) for path in files],
            })

        if not files:
            LOGGER.warning("任务完成但没有产出文件，检查工作流末尾是否有 Save* 节点")
        return GenerationResult(job.prompt_id, files, seconds, model_files, log_path)

    def generate(self, workflow: dict, workflow_label: str, output_directory: Path,
                 asset_name: str, seed: int | None = None,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                 progress_callback=None, write_log: bool = True) -> GenerationResult:
        """提交并等待（老接口，行为不变）。"""
        job = self.submit(workflow, workflow_label, output_directory, asset_name, seed)
        return self.collect(job, timeout_seconds=timeout_seconds,
                            progress_callback=progress_callback, write_log=write_log)