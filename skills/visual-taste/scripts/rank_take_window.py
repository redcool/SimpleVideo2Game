#!/usr/bin/env python3
"""从一段录像里挑出「最活的几秒」：按画面变化量给窗口打分。

改编自上游 lovisdotio/video-to-game 的 scripts/best_window.py（MIT）；
行为保持一致，变量名改为见名知意，注释与文案改为中文。

打分用 ffmpeg 的 scene score（相邻帧差），一个窗口的分数 = 平均值 + 中位数，
这样「一直有运动」胜过「一下大爆炸」。分数只说明有动静，**不说明好看**，
所以务必打开挑中的那几帧亲眼看一下。

用法：
  python rank_take_window.py take.mp4 --length 3
  python rank_take_window.py take.mp4 --length 10 --top 3 --cut best.mp4

依赖：ffmpeg。
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

TIMESTAMP_PATTERN = re.compile(r"pts_time:([\d.]+)")
SCENE_PATTERN = re.compile(r"lavfi\.scene_score=([\d.]+)")


def score_frames(path: Path) -> list[tuple[float, float]]:
    """返回 [(秒, 场景变化分)]，分数越大说明画面动得越多。"""
    stderr = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf", "select='gte(scene,0)',metadata=print",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    ).stderr
    timestamps = [float(value) for value in TIMESTAMP_PATTERN.findall(stderr)]
    scores = [float(value) for value in SCENE_PATTERN.findall(stderr)]
    return list(zip(timestamps, scores))


def rank_windows(scored_frames: list[tuple[float, float]], length: float,
                 skip_seconds: float, top_count: int) -> list[tuple[float, float]]:
    """滑动窗口打分并去重（挑出的窗口之间不重叠）。"""
    usable = [(moment, score) for moment, score in scored_frames if moment >= skip_seconds]
    if not usable:
        raise SystemExit("没有可打分的帧：检查录像是否为空，或把 --skip 调小")
    end_second = usable[-1][0]
    ranked: list[tuple[float, float]] = []
    step = 0.25
    start = usable[0][0]
    while start + length <= end_second:
        window = [score for moment, score in usable if start <= moment < start + length]
        if window:
            ordered = sorted(window)
            median = ordered[len(ordered) // 2]
            ranked.append((sum(window) / len(window) + median, round(start, 2)))
        start += step
    ranked.sort(reverse=True)

    picked: list[tuple[float, float]] = []
    for score, window_start in ranked:
        if all(abs(window_start - other_start) >= length for _, other_start in picked):
            picked.append((score, window_start))
        if len(picked) == top_count:
            break
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("take", help="录像文件")
    parser.add_argument("--length", type=float, default=3.0, help="窗口长度（秒）")
    parser.add_argument("--top", type=int, default=3, help="输出几个候选窗口")
    parser.add_argument("--skip", type=float, default=1.0, help="忽略开头几秒（加载、标题）")
    parser.add_argument("--cut", help="顺便把最好的窗口剪成这个文件")
    arguments = parser.parse_args()

    take = Path(arguments.take)
    picked = rank_windows(score_frames(take), arguments.length, arguments.skip, arguments.top)
    for score, window_start in picked:
        print(f"{window_start:6.2f} s -> {window_start + arguments.length:6.2f} s   分数 {score:.4f}")

    if arguments.cut and picked:
        best_start = picked[0][1]
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(best_start), "-i", str(take),
             "-t", str(arguments.length), "-c:v", "libx264", "-crf", "18", "-an", arguments.cut],
            check=True,
        )
        print(arguments.cut)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
