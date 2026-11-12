#!/usr/bin/env python3
"""给一张图或一段视频出「配色报告」：主色、占比、艳度、明暗分区，并对标准给结论。

用途：把「这个画面好不好看／像不像参考」从形容词变成几行数字。
判断标准是起步值（见 references/metrics.md），每个项目要按自己的风格校准。

用法：
  python palette_report.py shot.png
  python palette_report.py gameplay.mp4 --samples 8
  python palette_report.py shot.png --profile vivid --colors 6
  python palette_report.py shot.png --json > palette.json

退出码：报告本身成功即 0；加 --strict 时，任一指标出界返回 1。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from visual_metrics_core import analyze_frame, decode_frames, measure_edges  # noqa: E402

# 起步阈值：quiet 表示「安静、协调、不要荧光色」，vivid 表示「高饱和、明快」。
# 这些数字来自对上游 31 个成品游戏的观感校准，不是物理定律；项目风格不同就改这里。
COLOR_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
    "quiet": {
        "mean_saturation": (0.12, 0.45),
        "contrast_p95_minus_p5": (30.0, 165.0),
        "palette_concentration_top5": (0.25, 0.95),
        "highlight_fraction": (0.02, 0.45),
        "shadow_fraction": (0.02, 0.55),
        "luma_entropy_bits": (2.5, 4.8),
        "edge_density": (0.006, 0.045),
        "pure_fraction": (0.0, 0.06),
    },
    "vivid": {
        "mean_saturation": (0.30, 0.75),
        "contrast_p95_minus_p5": (40.0, 175.0),
        "palette_concentration_top5": (0.22, 0.95),
        "highlight_fraction": (0.02, 0.55),
        "shadow_fraction": (0.01, 0.45),
        "luma_entropy_bits": (3.0, 5.0),
        "edge_density": (0.008, 0.06),
        "pure_fraction": (0.0, 0.08),
    },
}


# 与参考逐项比时允许多大漂移：超出就是"跑偏了"，不是"出界了"。
DELTA_TOLERANCES: dict[str, float] = {
    "mean_saturation": 0.06,
    "contrast_p95_minus_p5": 18.0,
    "palette_concentration_top5": 0.10,
    "highlight_fraction": 0.08,
    "shadow_fraction": 0.08,
    "luma_entropy_bits": 0.35,
    "edge_density": 0.008,
    "pure_fraction": 0.03,
}


def compare_with_baseline(metrics: dict[str, float], baseline: dict[str, float]) -> list[dict[str, object]]:
    """与参考的指标逐项比差值。审美上"和参考一致"比"落在绝对区间"更有意义。"""
    rows: list[dict[str, object]] = []
    for name, tolerance in DELTA_TOLERANCES.items():
        if name not in baseline:
            continue
        reference_value = float(baseline[name])
        current_value = float(metrics[name])
        delta = round(current_value - reference_value, 4)
        rows.append({
            "metric": name,
            "reference": reference_value,
            "current": current_value,
            "delta": delta,
            "tolerance": tolerance,
            "verdict": "OK" if abs(delta) <= tolerance else ("DRIFT" if delta > 0 else "DRIFT"),
        })
    return rows


def aggregate_frames(frames) -> dict[str, float]:
    """多帧取平均，避免单帧运气影响结论。"""
    reports = [analyze_frame(frame) for frame in frames]
    edges = [measure_edges(frame) for frame in frames]
    count = len(reports)

    def mean_of(name: str) -> float:
        return round(sum(float(report[name]) for report in reports) / count, 4)

    return {
        "frame_count": count,
        "mean_saturation": mean_of("mean_saturation"),
        "contrast_p95_minus_p5": mean_of("contrast_p95_minus_p5"),
        "palette_concentration_top5": mean_of("palette_concentration_top5"),
        "highlight_fraction": mean_of("highlight_fraction"),
        "shadow_fraction": mean_of("shadow_fraction"),
        "luma_entropy_bits": mean_of("luma_entropy_bits"),
        "pure_fraction": round(mean_of("pure_black_fraction") + mean_of("pure_white_fraction"), 4),
        "edge_density": round(sum(edges) / count, 5),
        "mean_value": mean_of("mean_value"),
    }


def judge(metrics: dict[str, float], profile_name: str) -> list[dict[str, object]]:
    """逐项对照阈值，返回每一行的判定。"""
    profile = COLOR_PROFILES[profile_name]
    rows: list[dict[str, object]] = []
    for name, (low, high) in profile.items():
        value = float(metrics[name])
        if value < low:
            verdict, hint = "LOW", f"低于 {low}：{'太少变化' if name != 'mean_saturation' else '太灰、没精神'}"
        elif value > high:
            verdict, hint = "HIGH", f"高于 {high}：{'太艳、抢戏' if name == 'mean_saturation' else '太多噪声/太满'}"
        else:
            verdict, hint = "OK", ""
        rows.append({"metric": name, "value": value, "range": [low, high], "verdict": verdict, "hint": hint})
    return rows


def dominant_palette(frames, color_count: int) -> list[dict[str, object]]:
    """合并多帧的分箱，给出整段素材的主色。"""
    merged: dict[str, float] = {}
    for frame in frames:
        for item in analyze_frame(frame)["dominant_colors"]:
            merged[item["hex"]] = merged.get(item["hex"], 0.0) + float(item["share"])
    total = sum(merged.values()) or 1.0
    ordered = sorted(merged.items(), key=lambda item: item[1], reverse=True)
    return [{"hex": hex_value, "share": round(share / total, 4)} for hex_value, share in ordered[:color_count]]


def print_baseline_report(baseline_path: Path, delta_rows: list[dict[str, object]]) -> None:
    """打印"相对参考"的表。"""
    print(f"相对参考  {baseline_path.name}")
    print(f"  {'指标':<30}{'参考':>10}{'当前':>10}{'差':>10}   容差   判定")
    for row in delta_rows:
        print(f"  {row['metric']:<30}{row['reference']:>10}{row['current']:>10}{row['delta']:>10}"
              f"   ±{row['tolerance']}   {row['verdict']}")
    drifted = [row for row in delta_rows if row["verdict"] != "OK"]
    print()
    if drifted:
        print(f"结论：{len(drifted)} 项偏离参考。按差值方向判断是过艳/过灰/过满，一次只改一项。")
    else:
        print("结论：与参考一致（在容差内）。这时才轮到人的主观判断。")


def print_report(source: Path, metrics: dict[str, float], rows: list[dict[str, object]],
                 palette: list[dict[str, object]], profile_name: str) -> None:
    print(f"配色报告  {source.name}  帧数={metrics['frame_count']}  档位={profile_name}")
    print("  主色：" + "  ".join(f"{item['hex']}({item['share']:.2f})" for item in palette))
    print(f"  {'指标':<30}{'值':>9}   期望区间            判定")
    for row in rows:
        low, high = row["range"]
        print(f"  {row['metric']:<30}{row['value']:>9}   [{low}, {high}]   {row['verdict']}  {row['hint']}")
    failures = [row for row in rows if row["verdict"] != "OK"]
    print()
    if failures:
        print(f"结论：{len(failures)} 项出界。先只改一项，改完在同一位置重跑，别一次改五个。")
    else:
        print("结论：全部在区间内。可以进入并排图对比（compare-routine.md）。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="图片或视频路径")
    parser.add_argument("--colors", type=int, default=8, help="列出多少个主色（默认 8）")
    parser.add_argument("--samples", type=int, default=6, help="视频抽多少帧（默认 6）")
    parser.add_argument("--at", type=float, default=None, help="只取某一秒的画面")
    parser.add_argument("--profile", choices=sorted(COLOR_PROFILES), default="quiet", help="判断档位")
    parser.add_argument("--baseline", default=None,
                        help="参考素材之前的 --json 输出；给了就和参考比差值，不再比绝对区间")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="任一指标出界时返回 1")
    arguments = parser.parse_args()

    source = Path(arguments.source)
    frames = decode_frames(source, sample_count=arguments.samples, at_second=arguments.at)
    metrics = aggregate_frames(frames)
    palette = dominant_palette(frames, arguments.colors)

    delta_rows: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    if arguments.baseline:
        baseline_path = Path(arguments.baseline)
        baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        delta_rows = compare_with_baseline(metrics, baseline_payload["metrics"])
    else:
        rows = judge(metrics, arguments.profile)

    if arguments.json:
        print(json.dumps({"source": str(source), "profile": arguments.profile,
                          "metrics": metrics, "palette": palette,
                          "judgements": rows, "baseline_deltas": delta_rows},
                         ensure_ascii=False, indent=1))
    elif arguments.baseline:
        print_baseline_report(Path(arguments.baseline), delta_rows)
    else:
        print_report(source, metrics, rows, palette, arguments.profile)

    if arguments.strict:
        drifting = [row for row in (delta_rows or rows) if row["verdict"] != "OK"]
        if drifting:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())