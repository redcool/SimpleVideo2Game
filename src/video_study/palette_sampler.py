"""从 16 张小帧里取主色，给"用色"一个可抄的数字。

口径与 skills/visual-taste 保持一致：每通道 4 bit（16 级）分箱，取箱内均值。
这样两处量出来的主色可以互相比较。
"""
from __future__ import annotations

import logging
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

SAMPLE_FRAME_COUNT = 16
SAMPLE_WIDTH = 64
SAMPLE_HEIGHT = 36
QUANTIZE_BITS = 4


@dataclass(frozen=True)
class PaletteColor:
    """一个主色。"""

    hex_value: str
    share: float


def sample_palette(video_path: Path, color_count: int) -> list[PaletteColor]:
    """取主色列表，按占比降序。"""
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video_path),
         "-vf", f"fps={SAMPLE_FRAME_COUNT}/10,scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}",
         "-frames:v", str(SAMPLE_FRAME_COUNT), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise RuntimeError("取主色失败：ffmpeg 没有输出像素")
    raw = completed.stdout
    shift = 8 - QUANTIZE_BITS
    counts: Counter[tuple[int, int, int]] = Counter()
    sums: dict[tuple[int, int, int], list[int]] = {}
    for offset in range(0, len(raw) - 2, 3):
        red, green, blue = raw[offset], raw[offset + 1], raw[offset + 2]
        key = (red >> shift, green >> shift, blue >> shift)
        counts[key] += 1
        bucket = sums.setdefault(key, [0, 0, 0])
        bucket[0] += red
        bucket[1] += green
        bucket[2] += blue
    total = sum(counts.values()) or 1
    palette: list[PaletteColor] = []
    for key, count in counts.most_common(color_count):
        bucket = sums[key]
        palette.append(PaletteColor(
            hex_value="#%02x%02x%02x" % (bucket[0] // count, bucket[1] // count, bucket[2] // count),
            share=round(count / total, 3),
        ))
    return palette
