"""研究视频的编排：命令行 → StudyService → 打印一行结论。"""
from __future__ import annotations

from pathlib import Path

from src.video_study.study_service import StudyResult, study_video


def run_study(video_path: Path, output_directory: Path, interval_seconds: float,
              color_count: int, cut_threshold: float) -> StudyResult:
    """执行一次研究并打印结论。"""
    result = study_video(video_path, output_directory, interval_seconds=interval_seconds,
                         color_count=color_count, cut_threshold=cut_threshold)
    media = result.media
    palette_text = " ".join(color.hex_value for color in result.palette)
    print(f"{media.width}x{media.height} {media.frames_per_second} fps {media.duration_seconds} s，"
          f"{len(result.frames)} 帧，{len(result.cuts)} 个切点，主色 {palette_text}")
    print(f"先看 {result.sheet_path}")
    return result
