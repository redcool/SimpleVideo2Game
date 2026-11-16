"""产线自检的编排：调 health_probe 并按"缺什么"打印。"""
from __future__ import annotations

import json

from src.comfy_bridge.health_probe import (MISSING, HealthReport, HealthRow,
                                           build_health_report)


def _print_rows(title: str, rows: tuple[HealthRow, ...]) -> None:
    print(f"\n[{title}]")
    for row in rows:
        print(f"  {row.state:<8}{row.capability:<26}{row.detail}")


def _report_as_payload(report: HealthReport) -> dict:
    return {
        "platform": report.platform_text,
        "host": [{"capability": row.capability, "state": row.state, "detail": row.detail}
                 for row in report.host_rows],
        "pipeline": [{"capability": row.capability, "state": row.state, "detail": row.detail}
                     for row in report.pipeline_rows],
        "missing": [row.capability for row in report.missing_rows],
    }


def run_health_check(base_url: str | None = None, as_json: bool = False) -> int:
    """执行自检，返回进程退出码。"""
    report = build_health_report(base_url)
    if as_json:
        print(json.dumps(_report_as_payload(report), ensure_ascii=False, indent=1))
    else:
        print(f"视频游戏本地产线自检（{report.platform_text}）")
        _print_rows("主机工具链", report.host_rows)
        _print_rows("本机 ComfyUI", report.pipeline_rows)
        print()
        if report.is_healthy:
            print("结论：节点与模型都在位，可以建工作流。")
        else:
            print(f"结论：{len(report.missing_rows)} 项缺失，先补这些：")
            for row in report.missing_rows:
                print(f"  - {row.capability}：{row.detail}")
    comfy_reachable = any(row.capability == "ComfyUI" and row.state != MISSING
                          for row in report.pipeline_rows)
    image_ready = any(row.capability == "节点 图像基础链路" and row.state != MISSING
                      for row in report.pipeline_rows)
    return 0 if (comfy_reachable and image_ready) else 1
