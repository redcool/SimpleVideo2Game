#!/usr/bin/env python3
"""从录像里挑最活窗口（入口薄壳 → src/）

薄壳：实现已迁到 src/。保留这个入口，是为了让 SKILL.md 与既有命令不用改。
"""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_repository_root_on_path() -> None:
    """把仓库根放进 sys.path，才能 import src.*。"""
    for candidate in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents):
        if (candidate / "src").is_dir() and (candidate / "workflows").is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise SystemExit("找不到仓库根目录：向上没有同时含 src/ 与 workflows/ 的目录")


ensure_repository_root_on_path()

from src.command_line.main_rank_take import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
