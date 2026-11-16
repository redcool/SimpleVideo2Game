#!/usr/bin/env python3
"""命令行：生成一个素材（一次一个 ComfyUI 工作流）。

只做参数解析与错误出口；真正的流程在 pipeline_orchestrator.asset_pipeline。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.comfy_bridge.http_client import ComfyRequestError
from src.comfy_bridge.input_stager import InputStagingError
from src.comfy_bridge.job_waiter import JobFailedError
from src.comfy_bridge.workflow_editor import WorkflowEditError
from src.comfy_bridge.workflow_loader import WorkflowFormatError
from src.common.logging_setup import configure_logging
from src.pipeline_orchestrator.asset_pipeline import (AssetRequest, describe_workflow,
                                                      list_available_workflows,
                                                      run_asset_generation)

USAGE_EPILOG = """示例：
  python skills/video-to-game-local/scripts/comfy_asset.py --list
  python .../comfy_asset.py birefnet_cutout -o games/demo/assets --name hero_cutout \
      --upload 1.image=refs/hero.png --seed 7
  python .../comfy_asset.py workflows/h3_image_t2i.json --dry-run --set 3.text="a courier boy"
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="在本机 ComfyUI 上跑一个工作流，下载产物并写 asset_log.json",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=USAGE_EPILOG)
    parser.add_argument("workflow", nargs="?", help="工作流路径，或 workflows/ 下的名字")
    parser.add_argument("-o", "--out", default="assets", help="输出目录（默认 assets）")
    parser.add_argument("--name", help="素材名（默认工作流名 + 时间）")
    parser.add_argument("--set", action="append", default=[], dest="input_assignments",
                        metavar="TARGET=VALUE", help="改写输入：input 或 节点id.input")
    parser.add_argument("--upload", action="append", default=[], dest="upload_assignments",
                        metavar="TARGET=PATH", help="把参考图送进 ComfyUI input/ 并写入 TARGET")
    parser.add_argument("--seed", type=int, help="设置所有 seed / noise_seed")
    parser.add_argument("--url", default=None, help="ComfyUI 地址（默认 $COMFY_URL 或 127.0.0.1:8188）")
    parser.add_argument("--timeout", type=float, default=1800.0, help="等待上限秒数（默认 1800）")
    parser.add_argument("--dry-run", action="store_true", help="只打印改写后的工作流，不提交")
    parser.add_argument("--no-log", action="store_true", help="不写 asset_log.json")
    parser.add_argument("--list", action="store_true", help="列出 workflows/ 里可用的工作流")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging(arguments.verbose)

    if arguments.list:
        for name in list_available_workflows():
            print(name)
        return 0
    if not arguments.workflow:
        build_parser().error("需要一个工作流（或用 --list）")

    try:
        if arguments.dry_run:
            described = describe_workflow(arguments.workflow, tuple(arguments.input_assignments),
                                          arguments.seed)
            for message in described["messages"]:
                print(message)
            print(json.dumps(described["workflow"], ensure_ascii=False, indent=1))
            print("models: " + json.dumps(described["models"], ensure_ascii=False, indent=1))
            return 0

        run_asset_generation(AssetRequest(
            workflow=arguments.workflow,
            output_directory=Path(arguments.out),
            asset_name=arguments.name,
            input_assignments=tuple(arguments.input_assignments),
            upload_assignments=tuple(arguments.upload_assignments),
            seed=arguments.seed,
            base_url=arguments.url,
            timeout_seconds=arguments.timeout,
            write_log=not arguments.no_log,
        ))
    except (ComfyRequestError, WorkflowFormatError, WorkflowEditError,
            InputStagingError, JobFailedError) as error:
        print(f"失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
