#!/usr/bin/env python3
"""给单帧出「结构指标」：对比、细节量、明暗分布，以及主体是否跳得出来。

和 palette_report.py 的分工：那个看配色与气质，这个看画面结构。
层次检验需要一个主体框（人给），因为脚本不做语义分割，也不猜。

用法：
  python frame_metrics.py shot.png
  python frame_metrics.py shot.png --subject-box 480,540,320,420
  python frame_metrics.py shot.png --json

退出码：0；加 --strict 时，主体层次不达标返回 1。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from visual_metrics_core import (analyze_frame, decode_frames, measure_edges,  # noqa: E402
                                 region_statistics)

# 结构阈值：起步值，见 references/metrics.md「怎么校准」。
STRUCTURE_TARGETS: dict[str, tuple[float, float]] = {
    "contrast_p95_minus_p5": (30.0, 110.0),
    "luma_entropy_bits": (2.5, 4.8),
    "edge_density": (0.006, 0.045),
    "highlight_fraction": (0.02, 0.35),
}
# 层次：主体区与背景区的差多少才算「跳得出来」。
SUBJECT_LUMA_GAP_MINIMUM = 25.0
SUBJECT_SATURATION_GAP_MINIMUM = 0.15


def parse_box(text: str) -> tuple[int, int, int, int]:
    """把 "左,上,宽,高" 解析成四元组。"""
    parts = [int(piece) for piece in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--subject-box 需要四个整数：左,上,宽,高")
    return parts[0], parts[1], parts[2], parts[3]


def structure_rows(metrics: dict[str, float]) -> list[dict[str, object]]:
    """逐项对照结构阈值。"""
    rows: list[dict[str, object]] = []
    for name, (low, high) in STRUCTURE_TARGETS.items():
        value = float(metrics[name])
        verdict = "OK" if low <= value <= high else ("LOW" if value < low else "HIGH")
        rows.append({"metric": name, "value": value, "range": [low, high], "verdict": verdict})
    return rows


def hierarchy_verdict(statistics: dict[str, float]) -> dict[str, object]:
    """主体是否跳得出来：亮度差或饱和度差，满足一项即可。"""
    readable = (statistics["luma_gap"] >= SUBJECT_LUMA_GAP_MINIMUM
                or statistics["saturation_gap"] >= SUBJECT_SATURATION_GAP_MINIMUM)
    return {
        "readable": readable,
        "luma_gap": statistics["luma_gap"],
        "saturation_gap": statistics["saturation_gap"],
        "rule": f"亮度差 >= {SUBJECT_LUMA_GAP_MINIMUM} 或 饱和度差 >= {SUBJECT_SATURATION_GAP_MINIMUM}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="图片路径，或视频（配合 --at）")
    parser.add_argument("--at", type=float, default=None, help="视频中取第几秒")
    parser.add_argument("--subject-box", type=parse_box, default=None, help="主体框：左,上,宽,高（解码后 320 宽坐标系）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="层次不达标时返回 1")
    arguments = parser.parse_args()

    frames = decode_frames(Path(arguments.source), sample_count=1, at_second=arguments.at)
    frame = frames[0]
    metrics = analyze_frame(frame)
    metrics["edge_density"] = measure_edges(frame)
    rows = structure_rows(metrics)

    statistics = None
    hierarchy = None
    if arguments.subject_box is not None:
        statistics = region_statistics(frame, arguments.subject_box)
        hierarchy = hierarchy_verdict(statistics)

    if arguments.json:
        print(json.dumps({"source": str(arguments.source), "metrics": metrics,
                          "judgements": rows, "subject": statistics, "hierarchy": hierarchy},
                         ensure_ascii=False, indent=1))
    else:
        print(f"结构指标  {Path(arguments.source).name}  {frame.width}x{frame.height}（统计尺寸）")
        for row in rows:
            low, high = row["range"]
            print(f"  {row['metric']:<26}{row['value']:>9}   期望 [{low}, {high}]   {row['verdict']}")
        if statistics and hierarchy:
            print(f"  主体区亮度 {statistics['subject_mean_luma']}  背景亮度 {statistics['background_mean_luma']}"
                  f"  差 {statistics['luma_gap']}")
            print(f"  主体区饱和度 {statistics['subject_mean_saturation']}  背景 {statistics['background_mean_saturation']}"
                  f"  差 {statistics['saturation_gap']}")
            print(f"  层次：{'主体跳得出来' if hierarchy['readable'] else '主体陷进背景'}（{hierarchy['rule']}）")
        else:
            print("  未给 --subject-box，跳过层次检验。加框的方法见 references/metrics.md。")

    if arguments.strict and any(row["verdict"] != "OK" for row in rows):
        return 1
    if arguments.strict and hierarchy is not None and not hierarchy["readable"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
