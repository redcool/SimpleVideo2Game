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
SKIP_DIRS = {'.git', '.venv', '_ref', 'node_modules', '__pycache__', '.pytest_cache', 'tmp', '.trash'}

REQUIRED_ROOT = ['README.md', 'AGENTS.md', 'LICENSE', 'NOTICE.md', 'requirements.txt', '.gitignore',
                 'VERSION', 'package.json', '.env.example']
REQUIRED_SKILL = [
    'skills/video-to-game-local/SKILL.md',
    'skills/video-to-game-local/references/study-the-video.md',
    'skills/video-to-game-local/references/local-assets.md',
    'skills/video-to-game-local/references/prompting-manual.md',
    'skills/video-to-game-local/references/game-loop.md',
    'skills/video-to-game-local/references/look-and-post.md',
    'skills/video-to-game-local/references/playtest.md',
    # 技能里只保留薄壳入口与录屏器，实现都在 src/
    'skills/video-to-game-local/scripts/comfy_asset.py',
    'skills/video-to-game-local/scripts/comfy_health.py',
    'skills/video-to-game-local/scripts/study_video.py',
    'skills/video-to-game-local/scripts/rank_take.py',
    'skills/video-to-game-local/scripts/record_play.mjs',
    'skills/video-to-game-local/templates/game.html',
    'skills/video-to-game-local/templates/play.mjs',
]
# 实现层：按模块分目录，每个模块只做一类事
REQUIRED_SRC = [
    'src/__init__.py',
    'src/common/repository_paths.py',
    'src/common/logging_setup.py',
    'src/comfy_bridge/http_client.py',
    'src/comfy_bridge/workflow_loader.py',
    'src/comfy_bridge/workflow_editor.py',
    'src/comfy_bridge/output_collector.py',
    'src/comfy_bridge/asset_downloader.py',
    'src/comfy_bridge/asset_log_writer.py',
    'src/comfy_bridge/job_waiter.py',
    'src/comfy_bridge/input_stager.py',
    'src/comfy_bridge/generation_service.py',
    'src/comfy_bridge/health_probe.py',
    'src/video_study/media_probe.py',
    'src/video_study/frame_extractor.py',
    'src/video_study/contact_sheet.py',
    'src/video_study/palette_sampler.py',
    'src/video_study/cut_detector.py',
    'src/video_study/study_service.py',
    'src/playtest_capture/take_window_ranker.py',
    'src/pipeline_orchestrator/asset_pipeline.py',
    'src/pipeline_orchestrator/study_pipeline.py',
    'src/pipeline_orchestrator/health_pipeline.py',
    'src/pipeline_orchestrator/playtest_pipeline.py',
    'src/command_line/main_asset.py',
    'src/command_line/main_health.py',
    'src/command_line/main_study.py',
    'src/command_line/main_rank_take.py',
]
# 通用审美量化技能：与项目无关，必须能独立跑（自带脚本与自测）。
# 已落地并验证过的工作流，必须留在仓库里（删掉就等于能力回退）。
REQUIRED_WORKFLOWS = [
    'workflows/smoke_empty_image.json',
    'workflows/birefnet_cutout.json',
    'workflows/h3_image_t2i.json',
    'workflows/moss_t2i.json',
    'workflows/moss_edit.json',
    'workflows/tangoflux_sfx.json',
    'workflows/h3_video.json',
]
REQUIRED_VISUAL_TASTE = [
    'skills/visual-taste/SKILL.md',
    'skills/visual-taste/references/metrics.md',
    'skills/visual-taste/references/look-spec.md',
    'skills/visual-taste/references/compare-routine.md',
    'skills/visual-taste/scripts/visual_metrics_core.py',
    'skills/visual-taste/scripts/palette_report.py',
    'skills/visual-taste/scripts/frame_metrics.py',
    'skills/visual-taste/scripts/side_by_side.py',
    'skills/visual-taste/scripts/rank_take_window.py',
    'skills/visual-taste/tests/test_visual_metrics.py',
]
REQUIRED_GAME = ['README.md', 'SPEC.md', 'game/index.html']
REQUIRED_TESTS = ['tests/check_repo.py', 'tests/smoke_comfy.py', 'tests/smoke_game.mjs',
                  'skills/audio-taste/tests/test_audio_report.py']
# 音频验收技能：与 visual-taste 对称，必须能独立跑
REQUIRED_AUDIO_TASTE = [
    'skills/audio-taste/SKILL.md',
    'skills/audio-taste/scripts/audio_report.py',
]
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
    for p in (REQUIRED_ROOT + REQUIRED_SKILL + REQUIRED_SRC + REQUIRED_VISUAL_TASTE
              + REQUIRED_WORKFLOWS + REQUIRED_TESTS + REQUIRED_AUDIO_TASTE):
        if not os.path.exists(os.path.join(ROOT, p)):
            errors.append(f'missing required file: {p}')
    games_dir = os.path.join(ROOT, 'games')
    if os.path.isdir(games_dir):
        for g in sorted(os.listdir(games_dir)):
            gd = os.path.join(games_dir, g)
            if not os.path.isdir(gd) or g.startswith('.'):
                continue
            # README 与 SPEC 永远要有；game/ 只有在已经动工（存在 game/ 或 assets/）时才要求，
            # 否则立项阶段会被误判成错误。
            # 以「有真实文件」为准，空目录不算动工（空 game/ 曾把立项阶段误判成缺 index.html）。
            started = (os.path.isfile(os.path.join(gd, 'game', 'index.html'))
                       or os.path.isdir(os.path.join(gd, 'assets')))
            required = REQUIRED_GAME if started else [item for item in REQUIRED_GAME if not item.startswith('game/')]
            for need in required:
                if not os.path.exists(os.path.join(gd, need)):
                    errors.append(f'games/{g}: missing {need}')
            if not started:
                notes.append(f'games/{g}: 立项阶段（有 README/SPEC，尚未动工）')
            if os.path.isdir(os.path.join(gd, 'assets')) and not os.path.exists(os.path.join(gd, 'assets', 'asset_log.json')):
                notes.append(f'games/{g}: assets/ has no asset_log.json (generate assets through comfy_asset.py)')


def check_src_comments():
    """src/ 下每个模块至少要有中文（纪律：注释与 docstring 用中文）。"""
    for path in files(('.py',)):
        relative = rel(path)
        if not relative.startswith('src/'):
            continue
        text = open(path, encoding='utf-8', errors='ignore').read()
        if not re.search(r'[\u4e00-\u9fff]', text):
            errors.append(f'{relative}: 没有中文注释或 docstring（纪律要求中文）')


def check_version():
    """版本号必须是 x.y.z.w 四段（纪律六）。"""
    version_path = os.path.join(ROOT, 'VERSION')
    if not os.path.exists(version_path):
        return
    version = open(version_path, encoding='utf-8').read().strip()
    parts = version.split('.')
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        errors.append(f'VERSION: {version!r} 不是 x.y.z.w 四段数字')
    package_path = os.path.join(ROOT, 'package.json')
    if os.path.exists(package_path):
        package_version = json.load(open(package_path, encoding='utf-8')).get('version')
        if package_version != version:
            errors.append(f'package.json version {package_version!r} 与 VERSION {version!r} 不一致')


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
        # 存盘节点不一定以 Save 开头（TangoFluxVAEDecodeAndPlay 就是自带 save_output 的），两种都认。
        writes_files = any(
            str(node.get('class_type', '')).startswith('Save')
            or (node.get('inputs') or {}).get('save_output') is True
            for node in wf.values() if isinstance(node, dict))
        if not writes_files:
            notes.append(f'{rel(p)}: 没有负责存盘的节点（preview 输出是临时文件）')


def check_hygiene():
    for p in files(('.md', '.py', '.mjs', '.js', '.html', '.json', '.txt', '.toml', '.ps1')):
        text = open(p, encoding='utf-8', errors='ignore').read()
        if HOME_PATH.search(text) or WORK_PATH.search(text):
            errors.append(f'{rel(p)}: absolute local path (use an env var or a relative path)')
        for pat in SECRETS:
            if pat.search(text):
                errors.append(f'{rel(p)}: possible secret committed')


def check_size():
    """仓库体积只统计"被 git 跟踪"的文件；assets/ 这类本地素材不算进仓库。"""
    tracked = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'], capture_output=True)
    total = 0
    if tracked.returncode == 0:
        for relative in [item for item in tracked.stdout.decode('utf-8', 'replace').split('\0') if item]:
            absolute = os.path.join(ROOT, relative)
            if os.path.exists(absolute):
                total += os.path.getsize(absolute)
    else:
        for directory, dirs, filenames in os.walk(ROOT):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for filename in filenames:
                total += os.path.getsize(os.path.join(directory, filename))
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

    for fn in (check_structure, check_src_comments, check_version, check_links, check_python, check_node,
               check_workflows, check_hygiene, check_gitignore, check_size):
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