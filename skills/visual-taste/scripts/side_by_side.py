#!/usr/bin/env python3
"""把参考视频和你的画面并排放在一起，让「像不像」变成一张图。

改编自上游 lovisdotio/video-to-game 的 scripts/side_by_side.py（MIT）；
行为保持一致，注释与文案改为中文，去掉了单字母变量名。

用法：
  python side_by_side.py 参考.mp4 我的录像.mp4 -o pairs --times 1,3,5,8
  python side_by_side.py 参考.mp4 截图.png    -o pairs --times 4
  python side_by_side.py 参考.mp4 我的录像.mp4 -o pairs --every 1 --game-offset 2.5

要点：每次对比都用**同样几个时间点**，否则比的是运气。
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

STILL_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def probe_duration_seconds(path: Path) -> float:
    """读取参考素材的时长。"""
    output = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(output.strip())


def build_time_list(duration: float, times: str | None, every: float | None) -> list[float]:
    """决定要比哪几个时间点：给了 --times 就用它，否则按 --every 铺满。"""
    if times:
        return [float(piece) for piece in times.split(",")]
    step = every or 1.0
    return [round(index * step, 2) for index in range(int(duration / step))]


def write_pair(source: Path, game: Path, moment: float, game_offset: float,
               output_path: Path, height: int, game_is_still: bool) -> None:
    """出一张并排图：左参考、右游戏，等高。"""
    game_input = ["-i", str(game)] if game_is_still else ["-ss", str(max(0.0, moment + game_offset)), "-i", str(game)]
    filter_chain = (
        f"[0:v]scale=-2:{height},setsar=1[reference];"
        f"[1:v]scale=-2:{height},setsar=1[game];"
        f"[reference][game]hstack=2"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(moment), "-i", str(source), *game_input,
         "-filter_complex", filter_chain, "-frames:v", "1", "-q:v", "3", str(output_path)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="参考视频")
    parser.add_argument("game", help="你的录像（.mp4）或截图（.png/.jpg）")
    parser.add_argument("-o", "--out", default="pairs", help="输出目录（默认 pairs）")
    parser.add_argument("--times", help="逗号分隔的秒数，例如 2,5,8")
    parser.add_argument("--every", type=float, help="或者每 N 秒一张")
    parser.add_argument("--game-offset", type=float, default=0.0, help="游戏时间 = 参考时间 + 偏移")
    parser.add_argument("--height", type=int, default=540, help="输出高度（默认 540）")
    arguments = parser.parse_args()

    source = Path(arguments.source)
    game = Path(arguments.game)
    output_directory = Path(arguments.out)
    output_directory.mkdir(parents=True, exist_ok=True)

    duration = probe_duration_seconds(source)
    moments = build_time_list(duration, arguments.times, arguments.every)
    game_is_still = game.suffix.lower() in STILL_SUFFIXES

    for moment in moments:
        destination = output_directory / f"pair_{moment:06.2f}.jpg"
        write_pair(source, game, moment, arguments.game_offset, destination, arguments.height, game_is_still)
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
