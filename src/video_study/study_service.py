"""一次"研究视频"的编排：抽帧 + 联络表 + 主色 + 切点，写 study.json。

命令行只调这里。这样 study 的产物口径（文件名、字段名）只有一个出处。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .contact_sheet import build_contact_sheet
from .cut_detector import DEFAULT_THRESHOLD, detect_cuts
from .frame_extractor import ExtractedFrame, extract_frames
from .media_probe import MediaInfo, probe_media
from .palette_sampler import PaletteColor, sample_palette

LOGGER = logging.getLogger(__name__)

STUDY_JSON_FILENAME = "study.json"


@dataclass(frozen=True)
class StudyResult:
    """一次研究的全部产物。"""

    media: MediaInfo
    frames: tuple[ExtractedFrame, ...]
    palette: tuple[PaletteColor, ...]
    cuts: tuple[float, ...]
    sheet_path: Path
    study_json_path: Path


def study_video(video_path: Path, output_directory: Path, interval_seconds: float = 0.25,
                color_count: int = 10, cut_threshold: float = DEFAULT_THRESHOLD) -> StudyResult:
    """生成 study 目录与 study.json。"""
    if not video_path.is_file():
        raise SystemExit(f"视频不存在：{video_path}")
    output_directory.mkdir(parents=True, exist_ok=True)

    media = probe_media(video_path)
    frames = extract_frames(video_path, output_directory, interval_seconds)
    sheet_path = build_contact_sheet(video_path, output_directory, media)
    palette = sample_palette(video_path, color_count)
    cuts = detect_cuts(video_path, cut_threshold)

    study_json_path = output_directory / STUDY_JSON_FILENAME
    payload = {
        **media.as_dict(),
        "frames": [{"t": frame.second, "file": frame.filename} for frame in frames],
        "sheet": sheet_path.name,
        "palette": [{"hex": color.hex_value, "share": color.share} for color in palette],
        "cuts": list(cuts),
    }
    study_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    LOGGER.info("study 完成：%d 帧 / %d 切点 / %d 个主色", len(frames), len(cuts), len(palette))
    return StudyResult(media=media, frames=tuple(frames), palette=tuple(palette), cuts=tuple(cuts),
                       sheet_path=sheet_path, study_json_path=study_json_path)
