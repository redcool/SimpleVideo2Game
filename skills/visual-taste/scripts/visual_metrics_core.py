#!/usr/bin/env python3
"""视觉指标的核心计算：解码、颜色空间、直方图、边缘。

本文件只做「把像素变成数字」：不做命令行解析，也不下结论。
判断在 palette_report.py 与 frame_metrics.py 里，各自只负责一件事。

用法（作为库）：
    from visual_metrics_core import decode_frames, analyze_frame, measure_edges
    frames = decode_frames(Path("shot.png"))
    report = analyze_frame(frames[0])

依赖：ffmpeg / ffprobe（解码）、Python 标准库。刻意不用 Pillow，
这样技能可以原样搬到别的库，不额外背一个第三方包。
"""
from __future__ import annotations

import json
import logging
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# 统计前统一缩到这个宽度：指标关心分布，不关心原分辨率，缩小快十倍。
ANALYSIS_WIDTH = 320
# 颜色量化到每通道 4 bit（16 级），与上游 study_video.py 口径一致，便于对照。
QUANTIZE_BITS = 4
HUE_BIN_COUNT = 12
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


@dataclass(frozen=True)
class RgbPixel:
    """一个像素的 0-255 三通道值。"""

    red: int
    green: int
    blue: int


@dataclass(frozen=True)
class FramePixels:
    """一帧解码后的像素矩阵（按行展开）。"""

    width: int
    height: int
    pixels: tuple[RgbPixel, ...]

    @property
    def pixel_count(self) -> int:
        return len(self.pixels)


@dataclass(frozen=True)
class MediaInfo:
    """ffprobe 能给出的事实：尺寸与时长。"""

    width: int
    height: int
    duration_seconds: float

    @property
    def is_video(self) -> bool:
        return self.duration_seconds > 0.0


def probe_media(path: Path) -> MediaInfo:
    """读取宽高与时长；静图没有时长，返回 0。"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 读不出媒体信息：{path}")
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError(f"没有视频流：{path}")
    duration_text = (payload.get("format") or {}).get("duration")
    return MediaInfo(
        width=int(streams[0]["width"]),
        height=int(streams[0]["height"]),
        duration_seconds=float(duration_text) if duration_text else 0.0,
    )


def scaled_height(media: MediaInfo, target_width: int = ANALYSIS_WIDTH) -> int:
    """按比例算缩放后的高，并保证是偶数（rgb24 逐行切分需要偶数宽高）。"""
    height = round(media.height * target_width / media.width)
    return max(2, height - height % 2)


def _run_ffmpeg(input_path: Path, filter_chain: str) -> bytes:
    """让 ffmpeg 吐裸 rgb24 字节流。"""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(input_path), "-vf", filter_chain,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(
            f"ffmpeg 解码失败：{input_path}（filter={filter_chain}）："
            f"{result.stderr.decode('utf-8', 'replace')[:400]}"
        )
    return result.stdout


def _run_ffmpeg_single_frame(input_path: Path, at_second: float, target_width: int) -> bytes:
    """取指定时刻的一帧。-ss 放在 -i 前面，避免整段解码。"""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{at_second:.3f}", "-i", str(input_path),
         "-frames:v", "1", "-vf", f"scale={target_width}:-2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"取 {at_second}s 的画面失败：{input_path}")
    return result.stdout


def _pack_frame(raw: bytes, width: int, height: int) -> FramePixels:
    """把 rgb24 字节流打包成像素元组。"""
    expected = width * height * 3
    if len(raw) < expected:
        raise RuntimeError(f"像素不足：期望 {expected} 字节，实际 {len(raw)}")
    pixels = tuple(
        RgbPixel(raw[index], raw[index + 1], raw[index + 2])
        for index in range(0, expected, 3)
    )
    return FramePixels(width=width, height=height, pixels=pixels)


def decode_frames(path: Path, sample_count: int = 1, at_second: float | None = None) -> list[FramePixels]:
    """解码一张图或一段视频，返回若干帧。

    静图固定 1 帧；视频均匀抽 sample_count 帧（抽帧就够，指标看的是分布）。
    指定 at_second 时只取那一帧——对比图流程需要「同一个位置」。
    """
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在：{path}")
    media = probe_media(path)
    height = scaled_height(media)

    if not media.is_video:
        return [_pack_frame(_run_ffmpeg(path, f"scale={ANALYSIS_WIDTH}:{height}"), ANALYSIS_WIDTH, height)]

    if at_second is not None:
        raw = _run_ffmpeg_single_frame(path, at_second, ANALYSIS_WIDTH)
        return [_pack_frame(raw, ANALYSIS_WIDTH, height)]

    sample_count = max(1, sample_count)
    frames_per_second = sample_count / media.duration_seconds
    raw = _run_ffmpeg(path, f"fps={frames_per_second:.6f},scale={ANALYSIS_WIDTH}:{height}")
    frame_size = ANALYSIS_WIDTH * height * 3
    complete = len(raw) // frame_size
    if complete <= 0:
        raise RuntimeError(f"没有解出完整帧：{path}")
    return [
        _pack_frame(raw[offset * frame_size:(offset + 1) * frame_size], ANALYSIS_WIDTH, height)
        for offset in range(complete)
    ]


def luma(pixel: RgbPixel) -> float:
    """Rec.601 亮度（0-255）。人眼对绿色更敏感，所以不是三通道平均。"""
    return 0.299 * pixel.red + 0.587 * pixel.green + 0.114 * pixel.blue


def saturation_and_value(pixel: RgbPixel) -> tuple[float, float]:
    """返回 HSV 的 S（艳不艳）与 V（亮不亮），范围 0-1。"""
    maximum = max(pixel.red, pixel.green, pixel.blue) / 255.0
    minimum = min(pixel.red, pixel.green, pixel.blue) / 255.0
    if maximum <= 0.0:
        return 0.0, 0.0
    return (maximum - minimum) / maximum, maximum


def hue_degrees(pixel: RgbPixel) -> float | None:
    """色相角（0-360）。灰色像素没有色相，返回 None——不要把它算进 0° 那一格。"""
    red, green, blue = pixel.red / 255.0, pixel.green / 255.0, pixel.blue / 255.0
    maximum, minimum = max(red, green, blue), min(red, green, blue)
    delta = maximum - minimum
    if delta <= 1e-6:
        return None
    if maximum == red:
        hue = ((green - blue) / delta) % 6
    elif maximum == green:
        hue = (blue - red) / delta + 2
    else:
        hue = (red - green) / delta + 4
    return hue * 60.0


def quantize_key(pixel: RgbPixel) -> tuple[int, int, int]:
    """把像素压到 4 bit/通道的分箱键。"""
    shift = 8 - QUANTIZE_BITS
    return pixel.red >> shift, pixel.green >> shift, pixel.blue >> shift


def percentile(sorted_values: list[float], fraction: float) -> float:
    """取分位数（values 必须已升序），用于对比度 P95-P5。"""
    if not sorted_values:
        return 0.0
    position = min(len(sorted_values) - 1, max(0, int(round(fraction * (len(sorted_values) - 1)))))
    return sorted_values[position]


def shannon_entropy(counts: list[int], total: int) -> float:
    """香农熵（bit）：亮度分布有多散。单色画面接近 0。"""
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def analyze_frame(frame: FramePixels) -> dict[str, object]:
    """把一帧压成指标字典：配色、明暗分区、对比、色相分布。"""
    total = frame.pixel_count
    bins: dict[tuple[int, int, int], int] = {}
    bin_sums: dict[tuple[int, int, int], list[int]] = {}
    hues = [0] * HUE_BIN_COUNT
    saturation_total = 0.0
    value_total = 0.0
    shadow = mid = highlight = 0
    black_pixels = white_pixels = 0
    luma_values: list[float] = []
    luma_histogram = [0] * 32

    for pixel in frame.pixels:
        key = quantize_key(pixel)
        bins[key] = bins.get(key, 0) + 1
        sums = bin_sums.setdefault(key, [0, 0, 0])
        sums[0] += pixel.red
        sums[1] += pixel.green
        sums[2] += pixel.blue

        pixel_luma = luma(pixel)
        luma_values.append(pixel_luma)
        luma_histogram[min(31, int(pixel_luma / 8))] += 1
        saturation, value = saturation_and_value(pixel)
        saturation_total += saturation
        value_total += value

        if pixel_luma < 64:
            shadow += 1
        elif pixel_luma < 186:
            mid += 1
        else:
            highlight += 1
        if pixel_luma <= 8:
            black_pixels += 1
        if pixel_luma >= 247:
            white_pixels += 1

        if saturation > 0.15:
            degrees = hue_degrees(pixel)
            if degrees is not None:
                hues[min(HUE_BIN_COUNT - 1, int(degrees / (360 / HUE_BIN_COUNT)))] += 1

    luma_values.sort()
    dominant_colors = [
        {
            "hex": "#%02x%02x%02x" % (bin_sums[key][0] // count, bin_sums[key][1] // count, bin_sums[key][2] // count),
            "share": round(count / total, 4),
        }
        for key, count in sorted(bins.items(), key=lambda item: item[1], reverse=True)
    ]
    hue_total = sum(hues) or 1

    return {
        "pixel_count": total,
        "width": frame.width,
        "height": frame.height,
        "dominant_colors": dominant_colors,
        "palette_concentration_top5": round(sum(item["share"] for item in dominant_colors[:5]), 4),
        "distinct_color_bins": len(bins),
        "mean_saturation": round(saturation_total / total, 4),
        "mean_value": round(value_total / total, 4),
        "mean_luma": round(sum(luma_values) / total, 2),
        "contrast_p95_minus_p5": round(percentile(luma_values, 0.95) - percentile(luma_values, 0.05), 2),
        "shadow_fraction": round(shadow / total, 4),
        "mid_fraction": round(mid / total, 4),
        "highlight_fraction": round(highlight / total, 4),
        "pure_black_fraction": round(black_pixels / total, 4),
        "pure_white_fraction": round(white_pixels / total, 4),
        "luma_entropy_bits": round(shannon_entropy(luma_histogram, total), 3),
        "hue_histogram": [round(count / hue_total, 4) for count in hues],
    }


def measure_edges(frame: FramePixels) -> float:
    """平均梯度（0-1）：画面有多少细节。

    取相邻像素亮度差的平均值，不引入 numpy。太小＝画面空/糊，太大＝画面碎。
    """
    if frame.width < 3 or frame.height < 3:
        return 0.0
    gray = [luma(pixel) for pixel in frame.pixels]
    gradient_total = 0.0
    comparison_count = 0
    for row in range(frame.height - 1):
        for column in range(frame.width - 1):
            index = row * frame.width + column
            gradient_total += abs(gray[index] - gray[index + 1])
            gradient_total += abs(gray[index] - gray[index + frame.width])
            comparison_count += 2
    return round(gradient_total / comparison_count / 255.0, 5)


def region_statistics(frame: FramePixels, box: tuple[int, int, int, int]) -> dict[str, float]:
    """统计指定矩形（左,上,宽,高）的亮度与饱和度均值。

    用来做层次检验：主体区与背景区的差异越大，主角越跳得出来。
    这不是语义分割——框由人给，脚本只把框变成数字，不做猜测。
    """
    left, top, width, height = box
    inside_luma: list[float] = []
    inside_saturation: list[float] = []
    outside_luma: list[float] = []
    outside_saturation: list[float] = []
    for row in range(frame.height):
        for column in range(frame.width):
            pixel = frame.pixels[row * frame.width + column]
            pixel_luma = luma(pixel)
            saturation, _ = saturation_and_value(pixel)
            if left <= column < left + width and top <= row < top + height:
                inside_luma.append(pixel_luma)
                inside_saturation.append(saturation)
            else:
                outside_luma.append(pixel_luma)
                outside_saturation.append(saturation)

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    return {
        "subject_mean_luma": mean(inside_luma),
        "subject_mean_saturation": mean(inside_saturation),
        "background_mean_luma": mean(outside_luma),
        "background_mean_saturation": mean(outside_saturation),
        "luma_gap": round(abs(mean(inside_luma) - mean(outside_luma)), 2),
        "saturation_gap": round(abs(mean(inside_saturation) - mean(outside_saturation)), 4),
    }
