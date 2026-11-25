#!/usr/bin/env python3
"""把「做成片」和「参考片」按同一时间点逐帧对比，输出数字与并排图。

为什么要这个：靠人眼反复看截图、口头反馈"这里被挡了/这里太暗"，一轮一轮改不动。
参考视频才是验收标准——这个脚本把它变成可复现的数字对照，agent 自己就能判断改到位没有。

用法：
  python clip_compare.py 参考.mp4 我们的.mp4 -o 输出目录
  python clip_compare.py 参考.mp4 我们的.mp4 -o out --samples 6

输出：
  - 控制台：每条片的时长/分辨率，逐采样点的 5 项指标与差值，最后一行的平均偏差
  - out/compare_<t>.jpg：同一时间点的左右并排图（左参考、右我们）

退出码：0 正常；加 --strict 且平均偏差超过阈值时返回 1（可当门禁）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
PALETTE_SCRIPT = Path(__file__).resolve().parent / "palette_report.py"

METRIC_LABELS = [
    ("mean_saturation", "饱和", 3),
    ("contrast_p95_minus_p5", "对比", 1),
    ("highlight_fraction", "高光", 3),
    ("edge_density", "细节", 4),
    ("luma_entropy_bits", "熵", 2),
]
# 「做成片 vs 参考片」能接受的平均偏差。视觉这件事绝对值不重要，趋势一致才重要。
DEFAULT_TOLERANCE = {"mean_saturation": 0.08, "contrast_p95_minus_p5": 35.0,
                     "highlight_fraction": 0.05, "edge_density": 0.008,
                     "luma_entropy_bits": 0.6}


def probe_media(path: Path) -> dict:
    """时长、尺寸、帧率。"""
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    stream = (payload.get("streams") or [{}])[0]
    numerator, _, denominator = str(stream.get("r_frame_rate", "0/1")).partition("/")
    frame_rate = float(numerator) / float(denominator or 1) if float(denominator or 1) else 0.0
    return {"duration": float((payload.get("format") or {}).get("duration") or 0.0),
            "width": int(stream.get("width") or 0), "height": int(stream.get("height") or 0),
            "fps": round(frame_rate, 2)}


def grab_frame(video: Path, at_seconds: float, destination: Path) -> bool:
    """抽一帧到 destination。"""
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{at_seconds:.3f}", "-i", str(video),
         "-frames:v", "1", str(destination)], capture_output=True, text=True, check=False)
    return completed.returncode == 0 and destination.exists()


def metric_row(frame_path: Path) -> dict:
    """把一帧跑成指标字典。

    这里走 palette_report 的子进程，而不是直接调 visual_metrics_core：
    edge_density（细节量）是在 palette_report 里算的，核心不提供——
    复用它才能保证「单图报告」和「片对片对比」用的是同一套口径。
    """
    completed = subprocess.run([sys.executable, str(PALETTE_SCRIPT), str(frame_path), "--json"],
                               capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)["metrics"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference", help="参考片（验收标准）")
    parser.add_argument("candidate", help="我们做出来的片")
    parser.add_argument("-o", "--out", help="并排图输出目录（默认 tmp/clip-compare）")
    parser.add_argument("--samples", type=int, default=5, help="采样点数（默认 5）")
    parser.add_argument("--strict", action="store_true", help="平均偏差超阈值时返回 1")
    parser.add_argument("--candidate-range", metavar="START:END", default=None,
                        help="只比候选片的一段（秒），例如 0:8 比站台段——参考片往往只有两三秒的一个镜头")
    arguments = parser.parse_args()

    reference = Path(arguments.reference)
    candidate = Path(arguments.candidate)
    for path in (reference, candidate):
        if not path.exists():
            raise SystemExit(f"文件不存在：{path}")

    output_directory = Path(arguments.out or "tmp/clip-compare")
    output_directory.mkdir(parents=True, exist_ok=True)

    reference_info = probe_media(reference)
    candidate_info = probe_media(candidate)
    print(f"参考：{reference.name}  {reference_info['width']}x{reference_info['height']} "
          f"{reference_info['fps']} fps  {reference_info['duration']:.2f} s")
    print(f"我们：{candidate.name}  {candidate_info['width']}x{candidate_info['height']} "
          f"{candidate_info['fps']} fps  {candidate_info['duration']:.2f} s")

    # 候选片可以只取一段：参考片通常是两三秒的单个镜头，拿我们 25 秒的整段去比是错的
    candidate_start = 0.0
    candidate_end = candidate_info["duration"]
    if arguments.candidate_range:
        start_text, _, end_text = arguments.candidate_range.partition(":")
        candidate_start = float(start_text or 0.0)
        candidate_end = float(end_text or candidate_info["duration"])
        candidate_end = min(candidate_end, candidate_info["duration"])
        print(f"候选片只取 {candidate_start:.2f}-{candidate_end:.2f} s（{candidate_end - candidate_start:.2f} s）")

    # 按「相对时间」对齐：参考 2.3 秒、我们 25 秒，也能比同一叙事位置
    sample_count = max(2, arguments.samples)
    header = "时间点".ljust(10) + "".join(f"{label:>16}" for _, label, _ in METRIC_LABELS)
    print()
    print(header)
    totals = {key: 0.0 for key, _, _ in METRIC_LABELS}
    for index in range(sample_count):
        fraction = (index + 0.5) / sample_count
        reference_time = reference_info["duration"] * fraction
        candidate_time = candidate_start + (candidate_end - candidate_start) * fraction
        reference_frame = output_directory / f"ref_{index}.png"
        candidate_frame = output_directory / f"cand_{index}.png"
        if not grab_frame(reference, reference_time, reference_frame):
            print(f"抽取参考帧失败（t={reference_time:.2f}s）")
            continue
        if not grab_frame(candidate, candidate_time, candidate_frame):
            print(f"抽取候选帧失败（t={candidate_time:.2f}s）")
            continue

        reference_metrics = metric_row(reference_frame)
        candidate_metrics = metric_row(candidate_frame)
        cells = ""
        for key, _, digits in METRIC_LABELS:
            delta = candidate_metrics[key] - reference_metrics[key]
            totals[key] += abs(delta)
            cells += f"{reference_metrics[key]:>{16 - len(f' ({delta:+.4f})')}.{digits}f}"                      f"({delta:+.{digits}f})"
            cells = cells.rjust(len(cells))
        print(f"{fraction * 100:>5.0f}%".ljust(10) + cells)

        # 并排图：左参考、右我们
        left = Image.open(reference_frame).convert("RGB")
        right = Image.open(candidate_frame).convert("RGB")
        height = 360
        left.thumbnail((640, height))
        right.thumbnail((640, height))
        sheet = Image.new("RGB", (left.width + right.width + 12, max(left.height, right.height) + 22), (14, 16, 14))
        sheet.paste(left, (0, 22))
        sheet.paste(right, (left.width + 12, 22))
        ImageDraw.Draw(sheet).text((6, 6), f"ref {reference_time:.2f}s  |  ours {candidate_time:.2f}s", fill=(200, 210, 195))
        sheet.save(output_directory / f"compare_{index}.jpg", quality=86, optimize=True)

    print()
    print("平均偏差（越小越接近）：")
    failures = 0
    for key, label, digits in METRIC_LABELS:
        average = totals[key] / sample_count
        tolerance = DEFAULT_TOLERANCE[key]
        verdict = "OK" if average <= tolerance else "超限"
        if verdict != "OK":
            failures += 1
        print(f"  {label:<4} {average:>8.{digits}f}   容差 {tolerance:<6} {verdict}")
    print()
    print("并排图在：" + str(output_directory))
    if arguments.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
