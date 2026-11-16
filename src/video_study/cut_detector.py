"""检测镜头切换点。

方法：ffmpeg 的 scene 分数超过阈值就记一次。切点用来发现"视频里其实有两三个镜头"，
避免把不同机位当成同一个设计。
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.35
TIMESTAMP_PATTERN = re.compile(r"pts_time:([\d.]+)")


def detect_cuts(video_path: Path, threshold: float = DEFAULT_THRESHOLD) -> list[float]:
    """返回切点时间（秒），升序。"""
    completed = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(video_path), "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    cuts = sorted(round(float(value), 2) for value in TIMESTAMP_PATTERN.findall(completed.stderr))
    LOGGER.debug("检出 %d 个切点（阈值 %.2f）", len(cuts), threshold)
    return cuts
