"""按固定间隔抽帧，供 agent 逐帧研究视频。

关键点：抽帧前清空旧的 `f_*.jpg`。否则第二次跑会留下上一次的帧，
时间戳和文件名对不上，帧表直接错乱（这是踩过的坑）。
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

FRAME_WIDTH = 960
FRAME_PREFIX = "f_"


@dataclass(frozen=True)
class ExtractedFrame:
    """一帧：时间点与文件名。"""

    second: float
    filename: str


def clear_previous_frames(directory: Path) -> int:
    """删掉旧的 f_*.jpg（只删抽帧产物，不碰别的文件）。"""
    removed = 0
    if directory.is_dir():
        for stale in directory.glob(f"{FRAME_PREFIX}*.jpg"):
            stale.unlink()
            removed += 1
    if removed:
        LOGGER.debug("清掉上一轮的 %d 张帧", removed)
    return removed


def extract_frames(video_path: Path, directory: Path, interval_seconds: float) -> list[ExtractedFrame]:
    """每 interval_seconds 秒存一帧（宽 960，保持比例）。"""
    directory.mkdir(parents=True, exist_ok=True)
    clear_previous_frames(directory)
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video_path),
         "-vf", f"fps=1/{interval_seconds},scale={FRAME_WIDTH}:-2",
         "-q:v", "3", str(directory / f"{FRAME_PREFIX}%03d.jpg")],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"抽帧失败：{completed.stderr.strip()[:300]}")
    names = sorted(item.name for item in directory.glob(f"{FRAME_PREFIX}*.jpg"))
    return [ExtractedFrame(second=round(index * interval_seconds, 2), filename=name)
            for index, name in enumerate(names)]
