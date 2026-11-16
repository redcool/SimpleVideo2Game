"""把整段视频压成一张联络表（sheet.jpg），先看它再看单帧。

24 格、6 列，格间距白边：白底最能暴露画面偏色。
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .media_probe import MediaInfo

LOGGER = logging.getLogger(__name__)

COLUMNS = 6
CELLS = 24
CELL_WIDTH = 480
PADDING_COLOR = "white"
SHEET_FILENAME = "sheet.jpg"


def build_contact_sheet(video_path: Path, directory: Path, media: MediaInfo) -> Path:
    """生成 CELLS 格的联络表，返回文件路径。"""
    if media.duration_seconds <= 0:
        raise RuntimeError("视频时长为 0，无法生成联络表")
    rows = max(1, -(-CELLS // COLUMNS))
    seconds_per_cell = media.duration_seconds / (COLUMNS * rows)
    destination = directory / SHEET_FILENAME
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video_path), "-vf",
         f"fps=1/{seconds_per_cell:.4f},scale={CELL_WIDTH}:-2,"
         f"tile={COLUMNS}x{rows}:padding=6:color={PADDING_COLOR}",
         "-frames:v", "1", str(destination)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"联络表生成失败：{completed.stderr.strip()[:300]}")
    LOGGER.debug("联络表 %s（%d 格）", destination, CELLS)
    return destination
