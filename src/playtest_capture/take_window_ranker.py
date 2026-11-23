"""给录像的每个窗口打分，挑出"最活的几秒"。

打分 = 窗口内场景变化分的平均值 + 中位数：一直有运动胜过"一次大爆炸"。
分数只说明有动静，不说明好看——挑完必须打开帧看一眼。
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 3.0
DEFAULT_SKIP_SECONDS = 1.0
DEFAULT_TOP_COUNT = 3
STEP_SECONDS = 0.25
TIMESTAMP_PATTERN = re.compile(r"pts_time:([\d.]+)")
SCENE_PATTERN = re.compile(r"lavfi\.scene_score=([\d.]+)")


@dataclass(frozen=True)
class ScoredWindow:
    """一个候选窗口。"""

    start_second: float
    length_seconds: float
    score: float

    @property
    def end_second(self) -> float:
        return round(self.start_second + self.length_seconds, 2)


def score_frames(video_path: Path) -> list[tuple[float, float]]:
    """返回 [(秒, 场景变化分)]。

    先缩到 160 宽再算 scene 分：ffmpeg 的 scene 是逐像素帧差，
    **胶片颗粒/噪声会被当成运动**（实测：去掉颗粒后同一条路的分数掉了 3 倍），
    缩放之后细噪声被平均掉，分数才反映"画面里真的有东西在动"。
    """
    completed = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(video_path),
         "-vf", "scale=160:-2,select='gte(scene,0)',metadata=print", "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    timestamps = [float(value) for value in TIMESTAMP_PATTERN.findall(completed.stderr)]
    scores = [float(value) for value in SCENE_PATTERN.findall(completed.stderr)]
    return list(zip(timestamps, scores))


def rank_windows(scored_frames: list[tuple[float, float]], length_seconds: float = DEFAULT_WINDOW_SECONDS,
                 skip_seconds: float = DEFAULT_SKIP_SECONDS,
                 top_count: int = DEFAULT_TOP_COUNT) -> list[ScoredWindow]:
    """滑窗打分并去重（窗口之间不重叠）。"""
    usable = [(second, score) for second, score in scored_frames if second >= skip_seconds]
    if not usable:
        raise SystemExit("没有可打分的帧：录像为空，或 --skip 设得太大")
    end_second = usable[-1][0]
    candidates: list[ScoredWindow] = []
    start = usable[0][0]
    while start + length_seconds <= end_second:
        window = [score for second, score in usable if start <= second < start + length_seconds]
        if window:
            ordered = sorted(window)
            median = ordered[len(ordered) // 2]
            candidates.append(ScoredWindow(round(start, 2), length_seconds,
                                           sum(window) / len(window) + median))
        start += STEP_SECONDS
    candidates.sort(key=lambda item: item.score, reverse=True)

    picked: list[ScoredWindow] = []
    for candidate in candidates:
        if all(abs(candidate.start_second - chosen.start_second) >= length_seconds for chosen in picked):
            picked.append(candidate)
        if len(picked) == top_count:
            break
    LOGGER.debug("从 %d 个候选窗口里挑出 %d 个", len(candidates), len(picked))
    return picked


def cut_window(video_path: Path, window: ScoredWindow, destination: Path) -> Path:
    """把窗口剪成一个无声 mp4（trailer 用）。"""
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(window.start_second), "-i", str(video_path),
         "-t", str(window.length_seconds), "-c:v", "libx264", "-crf", "18", "-an", str(destination)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"切片失败：{completed.stderr.strip()[:300]}")
    return destination