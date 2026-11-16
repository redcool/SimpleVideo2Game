"""仓库内固定位置的解析：仓库根、workflows 目录。

不放任何绝对路径。技能目录、src 目录、命令行入口都在变，所以统一靠"标记目录"判断仓库根：
同时含 workflows/ 与 tests/ 的那一层。找不到就明确报错，不做退路猜测。
"""
from __future__ import annotations

from pathlib import Path

REPOSITORY_MARKERS = ("workflows", "tests")


def find_repository_root(start: Path) -> Path:
    """从 start 向上找同时含 workflows/ 与 tests/ 的目录。"""
    for candidate in (start, *start.parents):
        if all((candidate / marker).is_dir() for marker in REPOSITORY_MARKERS):
            return candidate
    raise SystemExit(
        f"找不到仓库根目录：从 {start} 向上没有同时含 {'/'.join(REPOSITORY_MARKERS)} 的目录"
    )


def workflow_directory() -> Path:
    """工作流目录。"""
    return find_repository_root(Path(__file__).resolve().parent) / "workflows"
