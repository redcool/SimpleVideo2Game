#!/usr/bin/env python3
"""End-to-end check of the local asset bridge against the running ComfyUI.

Submits workflows/smoke_empty_image.json (a 64x64 colour patch, no model, no GPU work),
waits for it, downloads the PNG and verifies it is really a PNG. That proves the whole
path `comfy_asset.py` depends on: /prompt -> /history -> /view -> file on disk.

Usage:
  python tests/smoke_comfy.py
  python tests/smoke_comfy.py --url http://127.0.0.1:8188 --keep

Exit code: 0 pass, 2 ComfyUI not reachable (skip), 1 failure.
"""
import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if not (REPOSITORY_ROOT / 'src' / 'comfy_bridge').is_dir():
    raise SystemExit(f'找不到实现目录：{REPOSITORY_ROOT / "src"}')
sys.path.insert(0, str(REPOSITORY_ROOT))
from src.comfy_bridge.http_client import ComfyHttpClient, ComfyRequestError  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default=None)
    ap.add_argument('--keep', action='store_true', help='keep the output directory')
    a = ap.parse_args()

    client = ComfyHttpClient(a.url, timeout_seconds=20)
    try:
        stats = client.system_statistics()
    except ComfyRequestError as e:
        print(f'SKIP: {e}')
        return 2
    print(f"ComfyUI {stats.get('system', {}).get('comfyui_version', '?')} at {client.base_url}")

    out = Path(tempfile.mkdtemp(prefix='v2gl-smoke-'))
    script = REPOSITORY_ROOT / 'skills' / 'video-to-game-local' / 'scripts' / 'comfy_asset.py'
    cmd = [sys.executable, str(script), 'workflows/smoke_empty_image.json',
           '-o', str(out), '--name', 'smoke', '--url', client.base_url]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0
    if r.returncode:
        print('FAIL: comfy_asset.py exited ' + str(r.returncode))
        print((r.stdout + r.stderr).strip()[:2000])
        return 1

    pngs = sorted(out.glob('smoke*.png'))
    if not pngs:
        print('FAIL: no PNG came back')
        print((r.stdout + r.stderr).strip()[:2000])
        return 1
    data = pngs[0].read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        print('FAIL: downloaded file is not a PNG')
        return 1
    log = out / 'asset_log.json'
    if not log.exists():
        print('FAIL: asset_log.json was not written')
        return 1
    print(f'PASS: {pngs[0].name} {len(data)} bytes in {elapsed:.1f}s, log written')
    print(f'  workflow: {json_first(log)}')
    if not a.keep:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
    else:
        print(f'  kept: {out}')
    return 0


def json_first(path):
    import json
    entry = json.loads(Path(path).read_text())[0]
    return f"{entry['workflow']} seed={entry['seed']} models={list(entry['models'])}"


if __name__ == '__main__':
    sys.exit(main())