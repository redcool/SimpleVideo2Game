#!/usr/bin/env python3
"""命令行：产线与主机能力自检。"""
from __future__ import annotations

import argparse
import sys

from src.common.logging_setup import configure_logging
from src.pipeline_orchestrator.health_pipeline import run_health_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查本机产线还缺什么（节点、模型、工具链）")
    parser.add_argument("--url", default=None, help="ComfyUI 地址（默认 $COMFY_URL 或 127.0.0.1:8188）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging(arguments.verbose)
    return run_health_check(arguments.url, arguments.json)


if __name__ == "__main__":
    sys.exit(main())
