#!/usr/bin/env python3
"""按 audio_report 的结论修音频：归一化响度、限制峰值、循环接缝交叉淡化。

为什么单独一个工具：验收（audio_report）与修复（audio_fix）是两件事，
分开之后"改了什么、改到多少"都能被重新测量，而不是凭感觉调音量。

用法：
  python audio_fix.py in.wav -o out.wav --profile sfx        # 只做响度/峰值归一
  python audio_fix.py in.wav -o out.wav --profile loop       # 归一 + 首尾交叉淡化
  python audio_fix.py in.wav -o out.wav --profile loop --crossfade 0.12 --target-lufs -18

依赖：ffmpeg。修完务必再跑一次 audio_report.py --strict，以数字确认。
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

TARGET_LOUDNESS = {"sfx": -16.0, "music": -18.0, "loop": -18.0, "drone": -20.0}
DEFAULT_CROSSFADE_SECONDS = 0.08


def probe_duration(path: Path) -> float:
    output = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return float(output.strip())


def build_filter(profile: str, duration: float, target_lufs: float,
                 crossfade_seconds: float, only_crossfade: bool = False) -> str:
    """按档位拼 ffmpeg 滤镜串。

    顺序很重要：**先归一化，再做接缝**。loudnorm 有启动斜坡，如果先接缝后归一，
    首尾会被加上不同的增益，接缝又会跳（实测 0.34）。所以 loop 档分两遍处理。
    """
    loudness = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    if profile != "loop":
        return loudness

    # 循环：把尾部 C 秒与头部 C 秒交叉淡化，再接到躯干后面。
    # 结果长度 = D - C；首尾都落在原音频的 x(C) 上，所以能接上。
    crossfade = min(crossfade_seconds, max(0.01, duration / 4))
    start = duration - crossfade
    body_end = duration - crossfade
    return (
        f"[0:a]atrim=0:{crossfade},afade=t=in:st=0:d={crossfade},asetpts=N/SR/TB[head];"
        f"[0:a]atrim={start}:{duration},afade=t=out:st=0:d={crossfade},asetpts=N/SR/TB[tail];"
        f"[0:a]atrim={crossfade}:{body_end},asetpts=N/SR/TB[body];"
        f"[tail][head]amix=inputs=2:duration=longest:normalize=0[xf];"
        + ("[body][xf]concat=n=2:v=0:a=1[out]" if only_crossfade
           else f"[body][xf]concat=n=2:v=0:a=1[joined];[joined]{loudness}[out]")
    )


def run_ffmpeg(arguments: list[str]) -> None:
    """跑一条 ffmpeg，失败就把 stderr 抛出来。"""
    completed = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"ffmpeg 处理失败：{completed.stderr.strip()[:400]}")


def normalize_into(source: Path, destination: Path, target_lufs: float) -> None:
    """只做响度/峰值归一化。"""
    run_ffmpeg(["ffmpeg", "-v", "error", "-y", "-i", str(source),
                "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                "-c:a", "pcm_s16le", str(destination)])


def crossfade_loop_into(source: Path, destination: Path, crossfade_seconds: float) -> None:
    """只做首尾交叉淡化（输入必须已经是最终增益）。"""
    duration = probe_duration(source)
    filter_complex = build_filter("loop", duration, 0.0, crossfade_seconds, only_crossfade=True)
    run_ffmpeg(["ffmpeg", "-v", "error", "-y", "-i", str(source),
                "-filter_complex", filter_complex, "-map", "[out]",
                "-c:a", "pcm_s16le", str(destination)])


def measure_loudness(path: Path) -> float:
    """读整体响度（LUFS-I）；读不到就按 −20 估算。"""
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-v", "info", "-i", str(path),
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, check=False)
    matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", completed.stderr)
    return float(matches[-1]) if matches else -20.0


def apply_static_gain(source: Path, destination: Path, gain_db: float) -> None:
    """用静态增益 + 软限幅到目标响度。静态增益不会破坏接缝（loudnorm 会）。"""
    run_ffmpeg(["ffmpeg", "-v", "error", "-y", "-i", str(source),
                "-af", f"volume={gain_db:.2f}dB,alimiter=limit=-1.5dB:level=disabled",
                "-c:a", "pcm_s16le", str(destination)])


def fix_audio(source: Path, destination: Path, profile: str, target_lufs: float,
              crossfade_seconds: float) -> None:
    """跑一遍修复。目标文件已存在时拒绝覆盖（纪律：同名不覆盖）。"""
    if not source.is_file():
        raise SystemExit(f"源文件不存在：{source}")
    if destination.exists():
        raise SystemExit(f"目标文件已存在（不覆盖）：{destination}")

    if profile != "loop":
        normalize_into(source, destination, target_lufs)
        return

    # loop 的正确顺序：先接缝，再用**静态增益**追目标响度。
    # 不能用 loudnorm：它的时变增益会让接缝两端落在不同增益上，接缝又跳（实测 0.35）。
    temporary = destination.with_name(destination.stem + ".tmp_crossfaded.wav")
    try:
        crossfade_loop_into(source, temporary, crossfade_seconds)
        measured = measure_loudness(temporary)
        apply_static_gain(temporary, destination, target_lufs - measured)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source")
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--profile", choices=sorted(TARGET_LOUDNESS), default="sfx")
    parser.add_argument("--target-lufs", type=float, default=None,
                        help="覆盖默认目标（sfx −16 / music·loop −18）")
    parser.add_argument("--crossfade", type=float, default=DEFAULT_CROSSFADE_SECONDS,
                        help="循环接缝交叉淡化秒数（默认 0.08）")
    arguments = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        raise SystemExit("需要 ffmpeg")

    target = arguments.target_lufs if arguments.target_lufs is not None else TARGET_LOUDNESS[arguments.profile]
    destination = Path(arguments.out)
    fix_audio(Path(arguments.source), destination, arguments.profile, target, arguments.crossfade)
    print(f"{arguments.source} -> {destination}（档位 {arguments.profile}，目标 {target} LUFS）")
    print("下一步：python audio_report.py " + str(destination) + " --profile " + arguments.profile + " --strict")
    return 0


if __name__ == "__main__":
    sys.exit(main())