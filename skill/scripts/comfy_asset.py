#!/usr/bin/env python3
"""Run one local ComfyUI workflow, download what it returns, and log the call.

This is the local replacement for the upstream skill's fal_asset.py: same contract
(one job at a time, everything logged next to the outputs), but the model runs on this
machine's ComfyUI instead of a paid endpoint.

Usage:
  python skill/scripts/comfy_asset.py workflows/smoke_empty_image.json -o assets --name smoke
  python skill/scripts/comfy_asset.py zimage_t2i -o games/demo/assets --name hero_concept \
      --set prompt="the hero alone, full body, A-pose, plain light grey background" \
      --set width=1024 --set height=1024 --seed 7
  python skill/scripts/comfy_asset.py hunyuan3d_i23d -o games/demo/assets --name hero_mesh \
      --set 7.image=hero_cutout.png --seed 11
  python skill/scripts/comfy_asset.py --list                     # workflows available here

--set TARGET=VALUE   TARGET is "input" (every node owning it) or "node_id.input".
                     VALUE is parsed as JSON when it parses (numbers, true, lists), else string.
--seed N             sets every seed / noise_seed input in the graph.
--dry-run            print the resolved graph and the model files it uses, queue nothing.

Every run appends to <out>/asset_log.json: workflow, prompt_id, seed, model files,
seconds, and the saved files. That log is the game README's asset table; do not edit it
by hand.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_client import (ComfyClient, ComfyError, collect_files, load_workflow,  # noqa: E402
                          models_used, set_input, set_seed)

REPO = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO / 'workflows'


def parse_value(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def resolve_workflow(arg):
    """A path, or a name inside workflows/ (with or without .json)."""
    direct = Path(arg)
    if direct.is_file():
        return direct
    for cand in (WORKFLOW_DIR / arg, WORKFLOW_DIR / f'{arg}.json'):
        if cand.is_file():
            return cand
    available = sorted(p.name for p in WORKFLOW_DIR.glob('*.json')) if WORKFLOW_DIR.is_dir() else []
    raise SystemExit(f'workflow {arg!r} not found. Available in workflows/: {", ".join(available) or "(none)"}')


def safe_name(text):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', text).strip('_') or 'asset'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workflow', nargs='?', help='path to an API-format workflow, or a name in workflows/')
    ap.add_argument('-o', '--out', default='assets', help='output directory (default: assets)')
    ap.add_argument('--name', help='base name for the saved files (default: workflow name + time)')
    ap.add_argument('--set', action='append', default=[], metavar='TARGET=VALUE', dest='sets')
    ap.add_argument('--seed', type=int, help='set every seed/noise_seed input')
    ap.add_argument('--url', default=None, help='ComfyUI base url (default: $COMFY_URL or 127.0.0.1:8188)')
    ap.add_argument('--timeout', type=float, default=1800, help='seconds to wait for the job (default 1800)')
    ap.add_argument('--dry-run', action='store_true', help='print the resolved graph, queue nothing')
    ap.add_argument('--no-log', action='store_true', help='do not append to asset_log.json')
    ap.add_argument('--list', action='store_true', help='list workflows available in workflows/')
    ap.add_argument('-q', '--quiet', action='store_true')
    a = ap.parse_args()

    if a.list:
        for p in sorted(WORKFLOW_DIR.glob('*.json')):
            print(p.name)
        return
    if not a.workflow:
        ap.error('a workflow is required (or use --list)')

    wf_path = resolve_workflow(a.workflow)
    wf = load_workflow(wf_path)

    for assignment in a.sets:
        if '=' not in assignment:
            raise SystemExit(f'--set needs TARGET=VALUE, got {assignment!r}')
        target, raw = assignment.split('=', 1)
        changed = set_input(wf, target, parse_value(raw))
        if not a.quiet:
            print(f'set {target} on {len(changed)} node(s): ' + ', '.join(f'{n}.{i}' for n, i in changed))
    if a.seed is not None:
        changed = set_seed(wf, a.seed)
        if not changed:
            print('warning: --seed given but the graph has no seed input', file=sys.stderr)
        elif not a.quiet:
            print('seed on ' + ', '.join(f'{n}.{i}' for n, i in changed))

    used = models_used(wf)
    if a.dry_run:
        print(json.dumps(wf, indent=1))
        print('models: ' + json.dumps(used, indent=1))
        return

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = safe_name(a.name or f'{wf_path.stem}_{time.strftime("%H%M%S")}')

    client = ComfyClient(a.url)
    t0 = time.time()
    prompt_id = client.submit(wf)
    if not a.quiet:
        print(f'queued {wf_path.name} -> {prompt_id}')
    last = [-10.0]

    def tick(elapsed):
        if not a.quiet and elapsed - last[0] >= 10:
            last[0] = elapsed
            print(f'  ... {elapsed:.0f}s')

    entry = client.wait(prompt_id, timeout=a.timeout, on_poll=tick)
    seconds = time.time() - t0

    files = collect_files(entry)
    saved = []
    for i, f in enumerate(files):
        blob = client.view(f['filename'], f.get('subfolder', ''), f.get('type', 'output'))
        ext = os.path.splitext(f['filename'])[1] or '.bin'
        dest = out / (name + ('' if len(files) == 1 else f'_{i}') + ext)
        dest.write_bytes(blob)
        saved.append(str(dest))
        if not a.quiet:
            print(f'{dest}  ({len(blob) / 1024:.0f} KB, node {f["node"]}.{f["key"]})')
    if not files:
        print('warning: the job finished but reported no files; check the Graph/Preview node', file=sys.stderr)
        print(json.dumps(entry.get('outputs', {}), indent=1)[:1500], file=sys.stderr)

    if not a.no_log:
        log_path = out / 'asset_log.json'
        log = json.loads(log_path.read_text()) if log_path.exists() else []
        log.append({
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'local-comfy',
            'workflow': str(wf_path.relative_to(REPO)) if wf_path.is_relative_to(REPO) else str(wf_path),
            'name': name,
            'prompt_id': prompt_id,
            'seed': a.seed,
            'seconds': round(seconds, 1),
            'models': {k: v for k, v in used.items()},
            'files': [str(Path(p)) for p in saved],
        })
        log_path.write_text(json.dumps(log, indent=1))
    if not a.quiet:
        print(f'{len(saved)} file(s) in {seconds:.1f}s -> {out}')


if __name__ == '__main__':
    try:
        main()
    except ComfyError as e:
        sys.exit(f'comfy error: {e}')
