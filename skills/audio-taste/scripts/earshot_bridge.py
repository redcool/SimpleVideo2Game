#!/usr/bin/env python3
"""可选后端：调用外部的 earshot（https://github.com/Leonxlnx/earshot）。

为什么是"可选"而不是依赖：
- earshot 需要 **CPU 版 torch + CLAP 模型**（首次还要从 HuggingFace 下载）。
  本仓库的 AGENTS 硬规则是"venv 里不装 torch"（GPU 归 ComfyUI），所以它必须装在自己的环境里。
- PyPI 上名为 earshot 的包是**另一个项目**（语音活动检测 VAD），pip install earshot 装的不是它。

本桥接只做两件事：找到它、把它的 JSON 摘出来。找不到就明确说怎么装，绝不让主流程失败。

用法：
  python earshot_bridge.py doctor                     # 探测是否可用
  python earshot_bridge.py measure sfx.wav --json     # 客观测量（不加载模型，快）
  python earshot_bridge.py describe sfx.wav --json    # 语义描述（加载模型，20-40 s）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ENVIRONMENT_VARIABLE = "EARSHOT_CMD"

INSTALL_HINT = chr(10).join([
    "没找到 earshot（可选后端：CPU torch + CLAP 模型，必须装在本仓库之外）：",
    "  uv tool install earshot @ git+https://github.com/Leonxlnx/earshot",
    "  或 clone 后建独立 venv：python -m pip install torch --index-url https://download.pytorch.org/whl/cpu，再 pip install -e .[mcp]",
    "装好后把可执行文件加到 PATH，或设 EARSHOT_CMD=<路径>。",
    "注意：PyPI 上的 earshot 是另一个包（VAD），不是它。",
])


def find_earshot() -> str | None:
    """按 EARSHOT_CMD → PATH 的顺序找可执行文件。"""
    explicit = os.environ.get(ENVIRONMENT_VARIABLE)
    if explicit:
        candidate = Path(explicit).expanduser()
        return str(candidate) if candidate.exists() else None
    return shutil.which("earshot")


def run_earshot(command_name: str, arguments: list[str], capture_json: bool = True) -> dict:
    """跑一条 earshot 命令，返回解析后的结果或错误说明。"""
    executable = find_earshot()
    if executable is None:
        return {"available": False, "error": "not-installed", "hint": INSTALL_HINT}
    # Windows 上 earshot 可能是 .exe/.cmd；如果给的是 .py（本项目自测用的 stub），就用当前解释器跑。
    if executable.lower().endswith(".py"):
        command = [sys.executable, executable, command_name, *arguments]
    else:
        command = [executable, command_name, *arguments]
    if capture_json and "--json" not in command:
        command.append("--json")
    completed = subprocess.run(command, capture_output=True, text=True, check=False,
                               encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        return {"available": True, "error": (completed.stderr or completed.stdout).strip()[:800] or "failed"}
    if not capture_json:
        return {"available": True, "stdout": completed.stdout}
    # 有些命令会先打摘要再打 JSON；从第一个 { 开始尝试解析。
    for candidate in (completed.stdout, completed.stdout[completed.stdout.find("{"):]):
        try:
            return {"available": True, "result": json.loads(candidate)}
        except (json.JSONDecodeError, ValueError):
            continue
    return {"available": True, "raw": completed.stdout[:2000]}


def measure(path: Path) -> dict:
    """客观测量（模型无关）：LUFS、真峰、LRA、包络、频谱、速度/调性。"""
    return run_earshot("measure", [str(path)])


def describe(path: Path) -> dict:
    """语义描述：像什么声音、AudioSet 标签。要加载模型。"""
    return run_earshot("describe", [str(path)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["doctor", "measure", "describe"])
    parser.add_argument("source", nargs="?")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()

    if arguments.command == "doctor":
        executable = find_earshot()
        payload = {"available": executable is not None, "path": executable}
        if executable is None:
            payload["hint"] = INSTALL_HINT
        print(json.dumps(payload, ensure_ascii=False, indent=1) if arguments.json else
              (f"earshot: {executable}" if executable else INSTALL_HINT))
        return 0 if executable else 2

    if not arguments.source:
        parser.error("measure / describe 需要一个音频文件")
    source = Path(arguments.source)
    result = measure(source) if arguments.command == "measure" else describe(source)
    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    elif result.get("available"):
        print(result.get("raw") or json.dumps(result.get("result"), ensure_ascii=False)[:2000])
    else:
        print(result.get("hint", "earshot 不可用"))
    return 0 if result.get("available") else 2


if __name__ == "__main__":
    sys.exit(main())