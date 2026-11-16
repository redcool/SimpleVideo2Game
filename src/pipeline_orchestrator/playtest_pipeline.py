"""试玩录像的编排：挑最活窗口 → 打印 →（可选）剪出最好的一段。"""
from __future__ import annotations

from pathlib import Path

from src.playtest_capture.take_window_ranker import (cut_window, rank_windows,
                                                    score_frames)


def rank_take(video_path: Path, length_seconds: float, top_count: int,
              skip_seconds: float, cut_path: Path | None = None) -> list:
    """挑窗口并打印；cut_path 给了就切片。"""
    windows = rank_windows(score_frames(video_path), length_seconds, skip_seconds, top_count)
    for window in windows:
        print(f"{window.start_second:6.2f} s -> {window.end_second:6.2f} s   分数 {window.score:.4f}")
    if cut_path and windows:
        cut_window(video_path, windows[0], cut_path)
        print(cut_path)
    return windows
