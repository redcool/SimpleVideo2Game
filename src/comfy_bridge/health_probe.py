"""产线与主机能力自检：还缺什么，一条命令回答。

它不是"打印一堆信息"，而是按能力分组给出 OK / MISSING，并在结论里只列缺的那几项。
检查口径写成本模块里的常量，改判定标准就改这里，不要散落在别处。
"""
from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .http_client import ComfyHttpClient, ComfyRequestError

LOGGER = logging.getLogger(__name__)

OK = "OK"
MISSING = "MISSING"
WARNING = "WARN"

# 能力 -> 必须存在的节点类名（子串匹配）
REQUIRED_NODE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("视频 MiniMax H3", ("MiniMaxH3Easy", "H3OneNode")),
    ("图像 H3（本地）", ("PH3ImageConditioning", "MiniMaxH3ImageConditioning")),
    ("图像 MOSS（本地）", ("TextEncodeMOSSImageEdit", "MOSSImageControl")),
    ("图像基础链路", ("CheckpointLoaderSimple", "KSampler", "CLIPTextEncode", "VAEDecode", "SaveImage")),
    ("抠图（内置）", ("LoadBackgroundRemovalModel", "RemoveBackground")),
    ("3D Hunyuan3D v2", ("EmptyLatentHunyuan3Dv2", "Hunyuan3Dv2Conditioning")),
    ("3D Trellis2", ("EmptyTrellis2LatentStructure",)),
    ("3D 导出", ("SaveGLB", "MeshToFile3D")),
    ("音频 ACE-Step", ("EmptyAceStep1.5LatentAudio",)),
    ("音频 StableAudio", ("ConditioningStableAudio",)),
    ("音频 MiniMax Music3", ("MiniMaxMusic3TextEncode",)),
)

# 能力 -> (要搜的模型目录, 文件名片段；命中任一片段即可)
REQUIRED_MODEL_GROUPS: tuple[tuple[str, tuple[tuple[str, ...], tuple[str, ...]]], ...] = (
    ("视频 H3 fl2va", (("diffusion_models",), ("minimax_h3_fl2va",))),
    ("视频 H3 ref2va", (("diffusion_models",), ("minimax_h3_ref2va",))),
    ("图像 H3（w4a8）", (("diffusion_models",), ("minimax_h3_image",))),
    ("图像 MOSS", (("diffusion_models",), ("moss_image",))),
    ("图像 Z-Image turbo", (("diffusion_models",), ("z_image_turbo",))),
    ("图像 Qwen-Image-Edit", (("diffusion_models",), ("qwen_image_edit",))),
    ("3D 混元 checkpoint", (("checkpoints",), ("hunyuan_3d_v2",))),
    ("3D 混元 DiT", (("diffusion_models",), ("hunyuan3d_dit",))),
    ("3D 混元 VAE", (("diffusion_models",), ("hunyuan3d_vae",))),
    ("抠图 BiRefNet", (("background_removal",), ("birefnet",))),
    ("音效 Stable Audio", (("checkpoints",), ("stable-audio", "stable_audio"))),
    ("音乐 ACE-Step", (("checkpoints", "diffusion_models"), ("acestep", "ace_step"))),
    ("音乐 MiniMax Music3", (("diffusion_models",), ("minimax_music3",))),
)


@dataclass(frozen=True)
class HealthRow:
    """一行检查结果。"""

    capability: str
    state: str
    detail: str


@dataclass(frozen=True)
class HealthReport:
    """完整报告。"""

    host_rows: tuple[HealthRow, ...]
    pipeline_rows: tuple[HealthRow, ...]
    platform_text: str

    @property
    def missing_rows(self) -> tuple[HealthRow, ...]:
        return tuple(row for row in self.pipeline_rows if row.state == MISSING)

    @property
    def is_healthy(self) -> bool:
        return not self.missing_rows


def find_chrome_executable() -> str | None:
    """与录屏器保持同一套候选路径。"""
    environment = os.environ
    candidates = [
        environment.get("CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
        environment.get("ProgramFiles") and Path(environment["ProgramFiles"]) / "Google/Chrome/Application/chrome.exe",
        environment.get("ProgramFiles(x86)") and Path(environment["ProgramFiles(x86)"]) / "Google/Chrome/Application/chrome.exe",
        environment.get("LOCALAPPDATA") and Path(environment["LOCALAPPDATA"]) / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(str(candidate)).exists():
            return str(candidate)
    return None


def probe_host() -> tuple[HealthRow, ...]:
    """主机侧：解释器、ffmpeg、node、Chrome、venv 里是否误装 torch。"""
    rows = [HealthRow("Python（本仓库 venv）", OK, f"{sys.version.split()[0]} @ {sys.executable}")]
    for tool in ("ffmpeg", "ffprobe", "node"):
        location = shutil.which(tool)
        rows.append(HealthRow(tool, OK if location else MISSING, location or "不在 PATH"))
    chrome = find_chrome_executable()
    rows.append(HealthRow("Chrome（录屏）", OK if chrome else WARNING,
                          chrome or "没找到；设 CHROME_PATH 或 npx playwright install chromium"))
    torch_check = subprocess.run([sys.executable, "-c", "import torch;print(torch.__version__)"],
                                 capture_output=True, text=True, check=False)
    if torch_check.returncode == 0:
        rows.append(HealthRow("venv 里的 torch", WARNING,
                              f"{torch_check.stdout.strip()}（本仓库 venv 应保持无 GPU 依赖）"))
    return tuple(rows)


def probe_pipeline(client: ComfyHttpClient) -> tuple[HealthRow, ...]:
    """ComfyUI 侧：版本、显卡、节点类、模型文件。"""
    statistics = client.system_statistics()
    system_information = statistics.get("system", {})
    rows = [HealthRow("ComfyUI", OK, f"{system_information.get('comfyui_version', '?')} @ {client.base_url}")]
    rows.append(HealthRow(
        "ComfyUI Python",
        OK,
        f"{str(system_information.get('python_version', '?')).split()[0]} / {system_information.get('pytorch_version', '?')}",
    ))
    for device in statistics.get("devices", []):
        total = device.get("vram_total", 0) / 1024 ** 3
        free = device.get("vram_free", 0) / 1024 ** 3
        rows.append(HealthRow(f"GPU {str(device.get('name', '?')).split(' : ')[0]}", OK,
                              f"{total:.0f} GB，空闲 {free:.1f} GB"))

    node_classes = client.object_information().keys()
    rows.append(HealthRow("节点类总数", OK, str(len(node_classes))))
    for label, required in REQUIRED_NODE_GROUPS:
        found = [name for name in required if any(name in existing for existing in node_classes)]
        rows.append(HealthRow(f"节点 {label}", OK if len(found) == len(required) else MISSING,
                              ", ".join(found) if found else "缺少 " + ", ".join(required)))

    model_listing: dict[str, list[str]] = {}
    for folder in client.model_folders():
        try:
            model_listing[folder] = client.model_files(folder)
        except ComfyRequestError:
            model_listing[folder] = []

    for label, (folders, fragments) in REQUIRED_MODEL_GROUPS:
        matches = [f"{folder}/{name}" for folder in folders for name in model_listing.get(folder, [])
                   if any(fragment in name.lower() for fragment in fragments)]
        rows.append(HealthRow(f"模型 {label}", OK if matches else MISSING,
                              matches[0] if matches else "未在 " + "/".join(folders) + " 找到"))
    return tuple(rows)


def build_health_report(base_url: str | None = None) -> HealthReport:
    """跑一遍主机与产线检查。ComfyUI 不可达时只返回主机结论并标记 MISSING。"""
    host_rows = probe_host()
    client = ComfyHttpClient(base_url, timeout_seconds=20)
    try:
        pipeline_rows = probe_pipeline(client)
    except ComfyRequestError as error:
        pipeline_rows = (HealthRow("ComfyUI", MISSING, str(error)),)
    return HealthReport(host_rows=host_rows, pipeline_rows=pipeline_rows,
                        platform_text=platform.platform())
