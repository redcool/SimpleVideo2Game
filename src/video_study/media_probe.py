"""用 ffprobe 读视频基本事实：尺寸、帧率、时长。

只做这一件事。抽帧、调色板、切点都依赖这几个数字，所以先独立出来。
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaInfo:
    """一段视频的基本信息。"""

    width: int
    height: int
    frames_per_second: float
    duration_seconds: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.frames_per_second,
            "duration": self.duration_seconds,
        }


def probe_media(path: Path) -> MediaInfo:
    """读取音视频元信息；失败时抛 RuntimeError，让调用方看到真实原因。"""
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe 读不出媒体信息：{path}；{completed.stderr.strip()[:300]}")
    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError(f"没有视频流：{path}")
    numerator, _, denominator = str(streams[0].get("r_frame_rate", "0/1")).partition("/")
    frames_per_second = round(int(numerator) / int(denominator or 1), 3) if int(denominator or 1) else 0.0
    duration_text = (payload.get("format") or {}).get("duration")
    return MediaInfo(
        width=int(streams[0]["width"]),
        height=int(streams[0]["height"]),
        frames_per_second=frames_per_second,
        duration_seconds=round(float(duration_text), 3) if duration_text else 0.0,
    )
