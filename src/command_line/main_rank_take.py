#!/usr/bin/env python3
"""命令行：从试玩录像里挑"最活的几秒"。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.common.logging_setup import configure_logging
from src.pipeline_orchestrator.playtest_pipeline import rank_take
from src.playtest_capture.take_window_ranker import (DEFAULT_SKIP_SECONDS,
                                                    DEFAULT_TOP_COUNT,
                                                    DEFAULT_WINDOW_SECONDS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="给录像窗口打分，挑出最活的几秒（务必再看帧）")
    parser.add_argument("take")
    parser.add_argument("--length", type=float, default=DEFAULT_WINDOW_SECONDS, help="窗口长度秒（默认 3）")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_COUNT, help="候选窗口数（默认 3）")
    parser.add_argument("--skip", type=float, default=DEFAULT_SKIP_SECONDS, help="忽略开头几秒（默认 1）")
    parser.add_argument("--cut", default=None, help="把最好的窗口剪到这个文件")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging(arguments.verbose)
    rank_take(Path(arguments.take), arguments.length, arguments.top, arguments.skip,
              Path(arguments.cut) if arguments.cut else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
