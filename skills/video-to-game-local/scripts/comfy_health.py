#!/usr/bin/env python3
"""Check that this machine can actually run the local video2game pipeline.

Answers one question: "what is still missing before a game can be built here?"
It inspects the running ComfyUI (version, GPU, node classes, model files), then the
host toolchain (ffmpeg, node, Chrome, this venv), and prints OK / MISSING per capability.

Usage:
  python skill/scripts/comfy_health.py
  python skill/scripts/comfy_health.py --url http://127.0.0.1:8188
  python skill/scripts/comfy_health.py --json      # machine readable

Exit code: 0 if ComfyUI answers and the image path is ready, 1 otherwise.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_client import ComfyClient, ComfyError  # noqa: E402

OK, BAD, WARN = '  OK  ', 'MISSING', ' WARN '

# Capability -> node classes that must exist (substring match, case sensitive).
NODE_GROUPS = [
    ('视频 MiniMax H3', ['MiniMaxH3Easy', 'H3OneNode']),
    ('图像 Z-Image', ['LoadZImageModel']),
    ('图像 基础链路', ['CheckpointLoaderSimple', 'KSampler', 'CLIPTextEncode', 'VAEDecode', 'SaveImage']),
    ('3D Hunyuan3D v2', ['EmptyLatentHunyuan3Dv2', 'Hunyuan3Dv2Conditioning']),
    ('3D Trellis2', ['EmptyTrellis2LatentStructure']),
    ('3D 导出', ['SaveGLB', 'MeshToFile3D']),
    ('音频 ACE-Step', ['EmptyAceStep1.5LatentAudio']),
    ('音频 StableAudio', ['ConditioningStableAudio']),
    ('音频 存盘', ['SaveAudio']),
    ('音频 MiniMax Music3', ['MiniMaxMusic3TextEncode']),
]

# Capability -> (folders to search, filename fragments; any fragment match counts).
MODEL_GROUPS = [
    ('视频 H3 fl2va', (['diffusion_models'], ['minimax_h3_fl2va'])),
    ('视频 H3 ref2va', (['diffusion_models'], ['minimax_h3_ref2va'])),
    ('图像 Z-Image turbo', (['diffusion_models'], ['z_image_turbo'])),
    ('图像 Qwen-Image-Edit', (['diffusion_models'], ['qwen_image_edit'])),
    ('3D 混元 checkpoint', (['checkpoints'], ['hunyuan_3d_v2'])),
    ('3D 混元 DiT', (['diffusion_models'], ['hunyuan3d_dit'])),
    ('3D 混元 VAE', (['diffusion_models'], ['hunyuan3d_vae'])),
    ('抠图 BiRefNet', (['background_removal'], ['birefnet'])),
    ('音效 Stable Audio', (['checkpoints'], ['stable-audio', 'stable_audio'])),
    ('音乐 ACE-Step', (['checkpoints', 'diffusion_models'], ['acestep', 'ace_step'])),
    ('音乐 MiniMax Music3', (['diffusion_models'], ['minimax_music3'])),
]


def chrome_path():
    """Same candidate list as record_play.mjs, so the two agree on this machine."""
    env = os.environ
    cands = [env.get('CHROME_PATH'),
             '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium',
             env.get('ProgramFiles', '') and Path(env['ProgramFiles']) / 'Google/Chrome/Application/chrome.exe',
             env.get('ProgramFiles(x86)', '') and Path(env['ProgramFiles(x86)']) / 'Google/Chrome/Application/chrome.exe',
             env.get('LOCALAPPDATA', '') and Path(env['LOCALAPPDATA']) / 'Google/Chrome/Application/chrome.exe']
    for c in cands:
        if c and Path(str(c)).exists():
            return str(c)
    return None


def which(name):
    return shutil.which(name)


def host_section(report):
    rows = []
    py = sys.version.split()[0]
    rows.append(('Python (this venv)', OK, f'{py} @ {sys.executable}'))
    for tool in ('ffmpeg', 'ffprobe', 'node'):
        p = which(tool)
        rows.append((tool, OK if p else BAD, p or 'not on PATH'))
    c = chrome_path()
    rows.append(('Chrome (录屏用)', OK if c else WARN,
                 c or 'not found; set CHROME_PATH or "npx playwright install chromium"'))
    torch = None
    try:
        torch = subprocess.run([sys.executable, '-c', 'import torch;print(torch.__version__)'],
                               capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    if torch and torch.returncode == 0:
        rows.append(('torch in venv', WARN, f'{torch.stdout.strip()} (this venv must stay GPU-free)'))
    report['host'] = rows
    return rows


def comfy_section(report, url):
    rows = []
    client = ComfyClient(url, timeout=20)
    try:
        stats = client.system_stats()
    except ComfyError as e:
        rows.append(('ComfyUI', BAD, str(e)))
        report['comfy'] = rows
        return rows, None
    sysinfo = stats.get('system', {})
    rows.append(('ComfyUI', OK, f'{sysinfo.get("comfyui_version", "?")} @ {client.url}'))
    rows.append(('ComfyUI Python', OK, f'{sysinfo.get("python_version", "?").split()[0]} / {sysinfo.get("pytorch_version", "?")}'))
    for d in stats.get('devices', []):
        total = d.get('vram_total', 0) / 1024 ** 3
        free = d.get('vram_free', 0) / 1024 ** 3
        rows.append((f'GPU {d.get("name", "?").split(" : ")[0]}', OK, f'{total:.0f} GB, {free:.1f} GB free'))

    classes = client.node_classes()
    rows.append(('节点类总数', OK, str(len(classes))))
    # 抠图走 ComfyUI 核心内置节点（RemoveBackground + LoadBackgroundRemovalModel），
    # 不是第三方节点包；Bria / Recraft / Tripo 那些是云端 API 节点，不算本地能力。
    builtin_matting = [name for name in ('LoadBackgroundRemovalModel', 'RemoveBackground') if name in classes]
    rows.append(('抠图节点（内置）', OK if len(builtin_matting) == 2 else BAD,
                 ', '.join(builtin_matting) if builtin_matting else '需要 ComfyUI 核心的 RemoveBackground 节点'))

    for label, wanted in NODE_GROUPS:
        hit = [w for w in wanted if any(w in c for c in classes)]
        rows.append((f'节点 {label}', OK if len(hit) == len(wanted) else BAD,
                     ', '.join(hit) if hit else 'none of ' + ', '.join(wanted)))

    folders = {}
    try:
        listing = {}
        for folder in client.model_folders():
            try:
                listing[folder] = client.models(folder)
            except ComfyError:
                listing[folder] = []
        folders = listing
    except ComfyError as e:
        rows.append(('模型目录', BAD, str(e)))

    for label, (where, fragments) in MODEL_GROUPS:
        hits = []
        for folder in where:
            for f in folders.get(folder, []):
                if any(frag in f.lower() for frag in fragments):
                    hits.append(f'{folder}/{f}')
        rows.append((f'模型 {label}', OK if hits else BAD, hits[0] if hits else 'not found in ' + '/'.join(where)))

    report['comfy'] = rows
    report['comfy_raw'] = {'url': client.url, 'folders': {k: len(v) for k, v in folders.items()}}
    return rows, client


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default=None, help='ComfyUI base url (default: $COMFY_URL or 127.0.0.1:8188)')
    ap.add_argument('--json', action='store_true', help='print one JSON report instead of the table')
    a = ap.parse_args()

    report = {'platform': platform.platform()}
    host = host_section(report)
    comfy, _ = comfy_section(report, a.url)

    if a.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print(f'video2game-local 产线自检  ({platform.platform()})')
        for title, rows in (('主机工具链', host), ('本机 ComfyUI', comfy)):
            print(f'\n[{title}]')
            for name, state, detail in rows:
                print(f'  {state}  {name:<24} {detail}')

        bad = [r for r in comfy if r[1] == BAD]
        print()
        if not bad:
            print('结论：ComfyUI 已通，图像 / 3D / 音频 / 视频 的节点与模型都在位，可以建工作流。')
        else:
            print(f'结论：{len(bad)} 项缺失 —— 先补这些再开游戏：')
            for name, _, detail in bad:
                print(f'  - {name}: {detail}')

    comfy_ok = any(r[0] == 'ComfyUI' and r[1] == OK for r in comfy)
    image_ok = any(r[0] == '节点 图像 基础链路' and r[1] == OK for r in comfy)
    return 0 if (comfy_ok and image_ok) else 1


if __name__ == '__main__':
    sys.exit(main())