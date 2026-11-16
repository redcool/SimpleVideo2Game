"""素材生成的编排：解析工作流 → 应用改写与上传 → 调生成服务 → 打印结果。

命令行只解析参数；所有跨模块调度收在这一层（纪律：集中流程调度）。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.comfy_bridge.generation_service import AssetGenerationService, GenerationResult
from src.comfy_bridge.http_client import ComfyHttpClient
from src.comfy_bridge.input_stager import stage_input_file
from src.comfy_bridge.workflow_editor import referenced_model_files, set_input, set_seed
from src.comfy_bridge.workflow_loader import load_api_workflow, resolve_workflow_argument
from src.common.repository_paths import find_repository_root, workflow_directory

LOGGER = logging.getLogger(__name__)

PROGRESS_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True)
class AssetRequest:
    """一次素材请求的全部参数（命令行解析后的结果）。"""

    workflow: str
    output_directory: Path
    asset_name: str | None = None
    input_assignments: tuple[str, ...] = ()
    upload_assignments: tuple[str, ...] = ()
    seed: int | None = None
    base_url: str | None = None
    timeout_seconds: float = 1800.0
    write_log: bool = True


@dataclass(frozen=True)
class AssetOutcome:
    """编排结果。"""

    workflow_path: Path
    result: GenerationResult


def parse_assignment(assignment: str, flag_name: str) -> tuple[str, str]:
    """把 `TARGET=VALUE` 拆开；拆不开就报错，不猜。"""
    if "=" not in assignment:
        raise SystemExit(f"{flag_name} 需要 TARGET=VALUE，收到 {assignment!r}")
    target, value = assignment.split("=", 1)
    return target, value


def parse_literal(raw_value: str):
    """能当 JSON 解析就用解析结果（数字、布尔、列表），否则当字符串。"""
    try:
        return json.loads(raw_value)
    except ValueError:
        return raw_value


def safe_asset_name(candidate: str | None, workflow_path: Path) -> str:
    """素材名只留字母数字与 ._-，其余换下划线；没给就用工作流名加时间。"""
    if candidate:
        cleaned = "".join(character if character.isalnum() or character in "._-" else "_"
                          for character in candidate).strip("_")
        if cleaned:
            return cleaned
    return f"{workflow_path.stem}_{time.strftime('%H%M%S')}"


def relative_workflow_label(workflow_path: Path, repository_root: Path) -> str:
    """日志里记相对路径，换机器也读得懂。"""
    try:
        return str(workflow_path.relative_to(repository_root))
    except ValueError:
        return str(workflow_path)


def run_asset_generation(request: AssetRequest) -> AssetOutcome:
    """执行一次素材生成。"""
    repository_root = find_repository_root(Path(__file__).resolve())
    workflow_path = resolve_workflow_argument(request.workflow, workflow_directory())
    workflow = load_api_workflow(workflow_path)

    for assignment in request.upload_assignments:
        target, local_path = parse_assignment(assignment, "--upload")
        staged_name = stage_input_file(Path(local_path))
        changed = set_input(workflow, target, staged_name)
        print(f"uploaded {local_path} -> input/{staged_name}（写入 "
              + ", ".join(f"{node}.{name}" for node, name in changed) + "）")

    for assignment in request.input_assignments:
        target, raw_value = parse_assignment(assignment, "--set")
        changed = set_input(workflow, target, parse_literal(raw_value))
        print(f"set {target} on {len(changed)} node(s)："
              + ", ".join(f"{node}.{name}" for node, name in changed))

    if request.seed is not None:
        changed = set_seed(workflow, request.seed)
        if changed:
            print("seed on " + ", ".join(f"{node}.{name}" for node, name in changed))
        else:
            LOGGER.warning("给了 --seed，但工作流里没有 seed / noise_seed 输入")

    asset_name = safe_asset_name(request.asset_name, workflow_path)
    service = AssetGenerationService(ComfyHttpClient(request.base_url))
    last_report_second = 0.0

    def report_progress(elapsed_seconds: float) -> None:
        nonlocal last_report_second
        if elapsed_seconds - last_report_second >= PROGRESS_INTERVAL_SECONDS:
            last_report_second = elapsed_seconds
            print(f"  ... {elapsed_seconds:.0f}s")

    result = service.generate(
        workflow,
        workflow_label=relative_workflow_label(workflow_path, repository_root),
        output_directory=request.output_directory,
        asset_name=asset_name,
        seed=request.seed,
        timeout_seconds=request.timeout_seconds,
        progress_callback=report_progress,
        write_log=request.write_log,
    )
    for path in result.files:
        print(f"{path}  ({path.stat().st_size / 1024:.0f} KB)")
    print(f"{len(result.files)} file(s) in {result.seconds:.1f}s -> {request.output_directory}")
    return AssetOutcome(workflow_path=workflow_path, result=result)


def describe_workflow(workflow_argument: str, input_assignments: tuple[str, ...] = (),
                      seed: int | None = None) -> dict:
    """--dry-run 用：返回改写后的图与引用模型，不提交任务。"""
    workflow_path = resolve_workflow_argument(workflow_argument, workflow_directory())
    workflow = load_api_workflow(workflow_path)
    messages: list[str] = []
    for assignment in input_assignments:
        target, raw_value = parse_assignment(assignment, "--set")
        changed = set_input(workflow, target, parse_literal(raw_value))
        messages.append(f"set {target} on {len(changed)} node(s)")
    if seed is not None:
        changed = set_seed(workflow, seed)
        messages.append("seed on " + ", ".join(f"{node}.{name}" for node, name in changed))
    return {"path": workflow_path, "workflow": workflow,
            "models": referenced_model_files(workflow), "messages": messages}


def list_available_workflows() -> list[str]:
    """列出 workflows/ 里可用的工作流名。"""
    return sorted(item.name for item in workflow_directory().glob("*.json"))
