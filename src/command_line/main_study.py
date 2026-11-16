#!/usr/bin/env python3
"""命令行：研究一段 gameplay 视频（抽帧、联络表、主色、切点）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.common.logging_setup import configure_logging
from src.pipeline_orchestrator.study_pipeline import run_study
from src.video_study.cut_detector import DEFAULT_THRESHOLD


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把 gameplay 视频拆成可研究的东西，并写 study.json")
    parser.add_argument("video")
    parser.add_argument("-o", "--out", default="study", help="输出目录（默认 study）")
    parser.add_argument("--every", type=float, default=0.25, help="抽帧间隔秒（默认 0.25）")
    parser.add_argument("--colors", type=int, default=10, help="主色数量（默认 10）")
    parser.add_argument("--cut-threshold", type=float, default=DEFAULT_THRESHOLD, help="切点阈值（默认 0.35）")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging(arguments.verbose)
    run_study(Path(arguments.video), Path(arguments.out), arguments.every,
              arguments.colors, arguments.cut_threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
