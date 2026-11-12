#!/usr/bin/env python3
"""Static checks for this repository: structure, links, syntax, workflows, hygiene, size.

Usage:
  python tests/check_repo.py
  python tests/check_repo.py -v          # also list what was checked

Exit code 1 with a list of problems, 0 when clean. Run it before every commit.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', '.venv', '_ref', 'node_modules', '__pycache__', '.pytest_cache'}

REQUIRED_ROOT = ['README.md', 'AGENTS.md', 'LICENSE', 'NOTICE.md', 'requirements.txt', '.gitignore']
REQUIRED_SKILL = [
    'skill/SKILL.md',
    'skill/references/study-the-video.md',
    'skill/references/local-assets.md',
    'skill/references/game-loop.md',
    'skill/references/look-and-post.md',
    'skill/references/playtest.md',
    'skill/scripts/comfy_client.py',
    'skill/scripts/comfy_asset.py',
    'skill/scripts/comfy_health.py',
    'skill/scripts/study_video.py',
    'skill/scripts/side_by_side.py',
    'skill/scripts/best_window.py',
    'skill/scripts/record_play.mjs',
    'skill/templates/game.html',
    'skill/templates/play.mjs',
]
REQUIRED_GAME = ['README.md', 'SPEC.md', 'game/index.html']
MAX_BYTES = 25_000_000

# Built from pieces so this file does not trip its own scanner:
# _SEP is a literal backslash (two characters in regex source), not an escape.
_SEP = chr(92) * 2
HOME_PATH = re.compile('C:' + _SEP + 'Users' + _SEP + r'[A-Za-z0-9_.]')
WORK_PATH = re.compile('H:' + _SEP + 'aiworks' + _SEP + r'[A-Za-z0-9_.]')
SECRETS = [
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'FAL_KEY\s*=\s*["\'][^"\']{8,}'),
    re.compile(r'(?:api[_-]?key|token|secret)\s*[:=]\s*["\'][A-Za-z0-9_-]{16,}["\']', re.I),
]

errors, notes = [], []


def files(exts, skip=SKIP_DIRS):
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in skip]
        for f in fs:
            if f.endswith(exts):
                yield os.path.join(d, f)


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


def check_structure():
    for p in REQUIRED_ROOT + REQUIRED_SKILL:
        if not os.path.exists(os.path.join(ROOT, p)):
            errors.append(f'missing required file: {p}')
    games_dir = os.path.join(ROOT, 'games')
    if os.path.isdir(games_dir):
        for g in sorted(os.listdir(games_dir)):
            gd = os.path.join(games_dir, g)
            if not os.path.isdir(gd) or g.startswith('.'):
                continue
            for need in REQUIRED_GAME:
                if not os.path.exists(os.path.join(gd, need)):
                    errors.append(f'games/{g}: missing {need}')
            if os.path.isdir(os.path.join(gd, 'assets')) and not os.path.exists(os.path.join(gd, 'assets', 'asset_log.json')):
                notes.append(f'games/{g}: assets/ has no asset_log.json (generate assets through comfy_asset.py)')


def check_links():
    for p in files(('.md',)):
        text = open(p, encoding='utf-8').read()
        for link in re.findall(r'\]\(([^)\s]+)\)', text):
            if link.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            target = link.split('#')[0].split('?')[0]
            if not target:
                continue
            if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), target))):
                errors.append(f'{rel(p)}: broken link {link}')


def check_python():
    for p in files(('.py',)):
        try:
            ast.parse(open(p, encoding='utf-8').read())
        except SyntaxError as e:
            errors.append(f'{rel(p)}: {e}')


def check_node():
    if not subprocess.run(['node', '--version'], capture_output=True).returncode == 0:
        notes.append('node not available: skipped .mjs syntax checks')
        return
    for p in files(('.mjs',)):
        r = subprocess.run(['node', '--check', p], capture_output=True)
        if r.returncode:
            errors.append(f'{rel(p)}: node --check failed: {r.stderr.decode("utf-8", "replace").strip()[:300]}')


def check_workflows():
    wdir = os.path.join(ROOT, 'workflows')
    if not os.path.isdir(wdir):
        errors.append('missing workflows/')
        return
    for p in files(('.json',)):
        if os.path.dirname(p) != wdir:
            continue
        try:
            wf = json.load(open(p, encoding='utf-8'))
        except json.JSONDecodeError as e:
            errors.append(f'{rel(p)}: invalid JSON: {e}')
            continue
        if not isinstance(wf, dict) or not wf:
            errors.append(f'{rel(p)}: empty workflow')
            continue
        ui_format = ('nodes' in wf or 'links' in wf) and not all(
            isinstance(v, dict) and 'class_type' in v for v in wf.values())
        if ui_format:
            errors.append(f'{rel(p)}: UI-format workflow; export it with Workflow -> Export (API)')
            continue
        for nid, node in wf.items():
            if not isinstance(node, dict) or 'class_type' not in node:
                errors.append(f'{rel(p)}: node {nid} has no class_type')
        if not any(str(n.get('class_type', '')).startswith('Save') for n in wf.values() if isinstance(n, dict)):
            notes.append(f'{rel(p)}: no Save* node (preview output is a temp file)')


def check_hygiene():
    for p in files(('.md', '.py', '.mjs', '.js', '.html', '.json', '.txt', '.toml', '.ps1')):
        text = open(p, encoding='utf-8', errors='ignore').read()
        if HOME_PATH.search(text) or WORK_PATH.search(text):
            errors.append(f'{rel(p)}: absolute local path (use an env var or a relative path)')
        for pat in SECRETS:
            if pat.search(text):
                errors.append(f'{rel(p)}: possible secret committed')


def check_size():
    total = 0
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in fs:
            total += os.path.getsize(os.path.join(d, f))
    if total > MAX_BYTES:
        errors.append(f'repository is {total / 1e6:.1f} MB (> {MAX_BYTES / 1e6:.0f} MB); keep media out of git')
    notes.append(f'repository size: {total / 1e6:.1f} MB')


def check_gitignore():
    gi = open(os.path.join(ROOT, '.gitignore'), encoding='utf-8').read() if os.path.exists(os.path.join(ROOT, '.gitignore')) else ''
    for need in ('.venv/', '_ref/', 'node_modules/'):
        if need not in gi:
            errors.append(f'.gitignore: {need} is not ignored')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    for fn in (check_structure, check_links, check_python, check_node, check_workflows, check_hygiene, check_gitignore, check_size):
        fn()

    if errors:
        print('\n'.join(errors))
        print(f'\n{len(errors)} problem(s)')
        return 1
    print('ok' + (f' ({notes[-1]})' if notes else ''))
    if a.verbose:
        for n in notes:
            print('  note: ' + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())