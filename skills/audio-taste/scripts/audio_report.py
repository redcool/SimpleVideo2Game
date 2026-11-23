#!/usr/bin/env python3
"""给一条音频出"可验收"的报告：响度、峰值、静音、亮度、循环接缝。

为什么需要它：生成出来的音效经常是"能听见但没用"——peak 削顶、整体太轻、
首尾接不上导致循环咔哒。这些问题肉眼（肉耳）要听很多遍，用数字一秒就能看出。

全部指标都来自 ffmpeg 的标准滤镜（astats / ebur128 / silencedetect），不做自研 DSP。

用法：
  python audio_report.py sfx_crawl.wav
  python audio_report.py take.mp4            # 视频也能测（自动取音轨）
  python audio_report.py loop.wav --profile loop --loop-seam
  python audio_report.py music.wav --profile music --json

退出码：0 正常；加 --strict 时有任一指标超出该档位的区间则返回 1。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 三个档位的起步阈值。都是"游戏里能直接用的"经验值，不是广播标准。
PROFILES: dict[str, dict[str, object]] = {
    "sfx": {
        "peak_db_max": -1.0,        # 不许削顶
        # 短促瞬态（落地、火花）受真峰 -1.5 dBTP 限制，通常到不了 -16 LUFS：
        # 别为了响度把峰值顶到 0（会削顶），所以这一档放宽到 -26。
        "lufs_range": (-26.0, -13.0),
        "duration_range": (0.2, 10.0),
        "silence_fraction_max": 0.6,
        "description": "单次音效（跳跃、落地、弹射）",
    },
    "music": {
        "peak_db_max": -1.0,
        "lufs_range": (-21.0, -15.0),
        "duration_range": (2.0, 300.0),
        "silence_fraction_max": 0.5,
        "lra_min": 2.0,             # 完全平的动态会被听成"垫底噪音"
        "description": "背景音乐 / drone",
    },
    "drone": {
        "peak_db_max": -1.0,
        "lufs_range": (-24.0, -14.0),
        "duration_range": (5.0, 300.0),
        "silence_fraction_max": 0.4,
        # 环境铺底音本来就该是平的：不要求 LRA，只看响度与削顶
        "description": "环境铺底（地下空间、机器低鸣）",
    },
    "loop": {
        "peak_db_max": -1.0,
        "lufs_range": (-24.0, -12.0),
        "duration_range": (0.5, 60.0),
        "silence_fraction_max": 0.5,
        "seam_db_max": 6.0,         # 首尾 RMS 差
        # 接缝跳变阈值：真实会响的咔哒在 0.4-0.6（实测原始 hum 0.42、修复后 0.07-0.10）；
        # 0.15 这条线能把"只有一个采样点的相位误差"和"真的断开"分开。
        "seam_jump_max": 0.15,
        "description": "循环音效（风、引擎、机械嗡鸣）",
    },
}

NUMBER = r"(-?\d+(?:\.\d+)?)"


def run(command: list[str]) -> subprocess.CompletedProcess:
    """跑一条外部命令，返回完成结果（调用方自己判断 returncode）。"""
    return subprocess.run(command, capture_output=True, text=True, check=False)


def probe_media(audio_path: Path) -> dict[str, object]:
    """时长、采样率、声道、编码。"""
    completed = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=codec_name,sample_rate,channels",
                     "-show_entries", "format=duration", "-of", "json", str(audio_path)])
    if completed.returncode != 0:
        raise SystemExit(f"ffprobe 读不出音轨：{audio_path}")
    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise SystemExit(f"文件里没有音轨：{audio_path}")
    return {
        "duration": round(float((payload.get("format") or {}).get("duration") or 0.0), 3),
        "sample_rate": int(streams[0].get("sample_rate") or 0),
        "channels": int(streams[0].get("channels") or 0),
        "codec": streams[0].get("codec_name"),
    }


def measure_levels(audio_path: Path) -> dict[str, float]:
    """峰值、RMS、过零率、动态范围（EBU R128）。"""
    completed = run(["ffmpeg", "-hide_banner", "-v", "info", "-i", str(audio_path),
                     "-af", "astats=reset=0,ebur128=peak=true", "-f", "null", "-"])
    log = completed.stderr

    def last(pattern: str) -> float | None:
        matches = re.findall(pattern, log)
        return float(matches[-1]) if matches else None

    peak_level = last(r"Peak level dB:\s*" + NUMBER)
    rms_level = last(r"RMS level dB:\s*" + NUMBER)
    zero_crossings = last(r"Zero crossings rate:\s*" + NUMBER)
    integrated = last(r"I:\s*" + NUMBER + r"\s*LUFS")
    loudness_range = last(r"LRA:\s*" + NUMBER + r"\s*LU")
    true_peak = last(r"Peak:\s*" + NUMBER + r"\s*dBFS")
    result: dict[str, float] = {}
    for key, value in (("peak_db", peak_level), ("rms_db", rms_level),
                       ("zero_crossing_rate", zero_crossings), ("lufs_integrated", integrated),
                       ("loudness_range_lu", loudness_range), ("true_peak_db", true_peak)):
        if value is not None:
            result[key] = round(value, 2)
    return result


def measure_silence(audio_path: Path, duration: float, threshold_db: float = -50.0) -> float:
    """静音时长占比（阈值 -50 dB，超过 100 ms 才算）。"""
    completed = run(["ffmpeg", "-hide_banner", "-v", "info", "-i", str(audio_path),
                     "-af", f"silencedetect=noise={threshold_db}dB:d=0.1", "-f", "null", "-"])
    log = completed.stderr
    total_silence = 0.0
    start = None
    for line in log.splitlines():
        start_match = re.search(r"silence_start:\s*" + NUMBER, line)
        end_match = re.search(r"silence_end:\s*" + NUMBER, line)
        if start_match:
            start = float(start_match.group(1))
        elif end_match and start is not None:
            total_silence += float(end_match.group(1)) - start
            start = None
    if start is not None and duration > start:
        total_silence += duration - start
    return round(total_silence / duration, 3) if duration > 0 else 0.0


def decode_window(audio_path: Path, start_seconds: float, seconds: float) -> bytes:
    """解出一小段单声道 f32le，用来比循环接缝。"""
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start_seconds:.3f}", "-i", str(audio_path),
         "-t", f"{seconds:.3f}", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
        capture_output=True, check=False)
    return completed.stdout


def measure_loop_seam(audio_path: Path, duration: float, window_seconds: float = 0.1) -> dict[str, float]:
    """循环接缝：整段解码一次，看"最后一帧 → 第一帧"跳变与首尾能量差。

    两个容易做错的地方：
    1. 归一化基准要用**整段峰值**，不能用窗口峰值——窗口里可能全是小信号，会把跳变放大十倍；
    2. 比"首尾两段是否相似"是错的（噪声类音效永远不相似），要比**接缝处的样本是否跳变**。
    """
    import array
    import math

    # 关键：不要重采样。降采样滤波器的边界补零会污染首尾样本，把接缝"量"出来
    # （实测同一文件在 8 kHz 下算 0.24，在原生 44.1 kHz 下算 0.02）。
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio_path), "-ac", "1", "-f", "f32le", "-"],
        capture_output=True, check=False)
    raw = completed.stdout
    if not raw or len(raw) < 8:
        return {}
    samples = array.array("f")
    samples.frombytes(raw[: len(raw) - len(raw) % 4])
    if len(samples) < 8:
        return {}

    peak = max(abs(value) for value in samples) or 1e-9
    # 用"样本数 / 时长"反推采样率，避免再调一次 ffprobe
    sample_rate = max(1, int(len(samples) / duration)) if duration > 0 else 44100
    window = max(1, int(window_seconds * sample_rate))
    head = samples[:window]
    tail = samples[-window:]

    def rms(values) -> float:
        return math.sqrt(sum(value * value for value in values) / len(values))

    head_rms = rms(head)
    tail_rms = rms(tail)
    seam_db = 20 * math.log10((head_rms + 1e-9) / (tail_rms + 1e-9))

    seam_jump = abs(samples[0] - samples[-1]) / peak
    slope_jump = abs((samples[1] - samples[0]) - (samples[-1] - samples[-2])) / peak
    return {"seam_db": round(min(abs(seam_db), 99.0), 2),
            "seam_jump": round(min(2.0, seam_jump), 4),
            "seam_slope_jump": round(min(2.0, slope_jump), 4)}


def judge(metrics: dict[str, object], profile_name: str) -> list[dict[str, object]]:
    """按档位给结论。"""
    profile = PROFILES[profile_name]
    rows: list[dict[str, object]] = []

    def add(name: str, value, low, high, ok: bool, hint: str) -> None:
        rows.append({"metric": name, "value": value, "range": [low, high],
                     "verdict": "OK" if ok else "FAIL", "hint": "" if ok else hint})

    peak = metrics.get("peak_db")
    if peak is not None:
        add("peak_db", peak, None, profile["peak_db_max"], peak <= profile["peak_db_max"],
            "削顶：整体降增益，或改用软限幅")
    lufs = metrics.get("lufs_integrated")
    if lufs is not None:
        low, high = profile["lufs_range"]
        add("lufs_integrated", lufs, low, high, low <= lufs <= high,
            "响度不在游戏可用区间：用 loudnorm 归一化")
    duration = metrics.get("duration")
    if duration:
        low, high = profile["duration_range"]
        add("duration", duration, low, high, low <= duration <= high, "时长不对：重新生成或裁剪")
    silence = metrics.get("silence_fraction")
    if silence is not None:
        add("silence_fraction", silence, None, profile["silence_fraction_max"],
            silence <= profile["silence_fraction_max"], "静音太多：内容稀")
    if "lra_min" in profile:
        lra = metrics.get("loudness_range_lu")
        if lra is not None:
            add("loudness_range_lu", lra, profile["lra_min"], None, lra >= profile["lra_min"],
                "动态太扁：加起伏，别当垫底噪音")
    if "seam_db_max" in profile:
        seam_db = metrics.get("seam_db")
        if seam_db is not None:
            add("seam_db", seam_db, None, profile["seam_db_max"], seam_db <= profile["seam_db_max"],
                "循环首尾能量不匹配：做交叉淡化")
        jump = metrics.get("seam_jump")
        if jump is not None:
            add("seam_jump", jump, None, profile["seam_jump_max"],
                jump <= profile["seam_jump_max"], "接缝处有跳变（会咔哒）：做交叉淡化")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="sfx")
    parser.add_argument("--loop-seam", action="store_true", help="额外交接缝测量（循环音效用）")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--earshot", action="store_true",
                        help="额外调用可选的 earshot 后端（客观测量；--earshot-describe 才会加载模型）")
    parser.add_argument("--earshot-describe", action="store_true", help="让 earshot 给一段语义描述（慢）")
    arguments = parser.parse_args()

    audio_path = Path(arguments.source)
    if not audio_path.exists():
        raise SystemExit(f"文件不存在：{audio_path}")

    metrics: dict[str, object] = {}
    metrics.update(probe_media(audio_path))
    metrics.update(measure_levels(audio_path))
    metrics["silence_fraction"] = measure_silence(audio_path, float(metrics.get("duration") or 0.0))
    if arguments.loop_seam or arguments.profile == "loop":
        metrics.update(measure_loop_seam(audio_path, float(metrics.get("duration") or 0.0)))
    rows = judge(metrics, arguments.profile)

    earshot_payload = None
    if arguments.earshot or arguments.earshot_describe:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import earshot_bridge  # noqa: PLC0415  可选依赖，放在函数内导入
            earshot_payload = earshot_bridge.measure(audio_path)
            if arguments.earshot_describe:
                earshot_payload = {"measure": earshot_payload,
                                   "describe": earshot_bridge.describe(audio_path)}
        except Exception as error:  # 可选后端不该让主流程失败
            earshot_payload = {"available": False, "error": str(error)[:300]}

    if arguments.json:
        print(json.dumps({"source": str(audio_path), "profile": arguments.profile,
                          "metrics": metrics, "judgements": rows, "earshot": earshot_payload},
                         ensure_ascii=False, indent=1))
    else:
        print(f"音频报告  {audio_path.name}  档位={arguments.profile}（{PROFILES[arguments.profile]['description']}）")
        print(f"  {metrics.get('duration')} s · {metrics.get('sample_rate')} Hz · {metrics.get('channels')} ch · {metrics.get('codec')}")
        print(f"  峰值 {metrics.get('peak_db')} dBFS（真峰 {metrics.get('true_peak_db')}）"
              f" · RMS {metrics.get('rms_db')} dB · 响度 {metrics.get('lufs_integrated')} LUFS"
              f" · LRA {metrics.get('loudness_range_lu')} LU")
        print(f"  过零率 {metrics.get('zero_crossing_rate')} · 静音占比 {metrics.get('silence_fraction')}"
              + (f" · 接缝 {metrics.get('seam_db')} dB / 跳变 {metrics.get('seam_jump')}" if "seam_db" in metrics else ""))
        print()
        for row in rows:
            print(f"  {row['verdict']:<5}{row['metric']:<20}{str(row['value']):>9}   期望 {row['range']}   {row['hint']}")
        failures = [row for row in rows if row["verdict"] != "OK"]
        print()
        print("结论：" + ("通过，可以直接进游戏。" if not failures else f"{len(failures)} 项不合格，先修再入库。"))
        if earshot_payload is not None:
            if earshot_payload.get("available"):
                print("earshot：" + json.dumps(earshot_payload.get("result", earshot_payload), ensure_ascii=False)[:600])
            else:
                print("earshot：不可用（可选后端）——" + str(earshot_payload.get("hint", ""))[:200])

    if arguments.strict and any(row["verdict"] != "OK" for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())