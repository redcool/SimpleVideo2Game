#!/usr/bin/env python3
"""visual-taste 的自测：只用 ffmpeg 合成图，不依赖 ComfyUI、不依赖网络。

跑法：
    python -m unittest discover -s skills/visual-taste/tests -v
或：
    python skills/visual-taste/tests/test_visual_metrics.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))

from visual_metrics_core import (analyze_frame, decode_frames, measure_edges,  # noqa: E402
                                 region_statistics)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
# ffmpeg 生成 PNG 时走了一次 RGB→YUV→RGB，通道值可能差 1，所以 hex 用 ±2 比较。
HEX_TOLERANCE = 2


def hex_distance(first: str, second: str) -> int:
    """两个 #RRGGBB 的最大单通道差。"""
    left = [int(first[index:index + 2], 16) for index in (1, 3, 5)]
    right = [int(second[index:index + 2], 16) for index in (1, 3, 5)]
    return max(abs(a - b) for a, b in zip(left, right))


def make_picture(destination: Path, color: str, draw_box: str | None = None) -> Path:
    """用 ffmpeg 生成一张纯色图，可选在上面画一个矩形。"""
    filters = ["-f", "lavfi", "-i", f"color=c={color}:s=320x180:d=1"]
    if draw_box:
        filters += ["-vf", draw_box]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *filters, "-frames:v", "1", str(destination)], check=True)
    return destination


@unittest.skipUnless(FFMPEG_AVAILABLE, "需要 ffmpeg")
class VisualMetricsTest(unittest.TestCase):
    """指标口径的回归测试：纯色、双色、主体层次、命令行 JSON。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory(prefix="visual-taste-test-")
        cls.directory = Path(cls.temporary_directory.name)
        cls.gray_picture = make_picture(cls.directory / "gray.png", "0x808080")
        cls.navy_picture = make_picture(cls.directory / "navy.png", "0x204060")
        cls.split_picture = make_picture(cls.directory / "split.png", "black",
                                         "drawbox=x=160:y=0:w=160:h=180:color=white:t=fill")
        cls.subject_picture = make_picture(cls.directory / "subject.png", "black",
                                           "drawbox=x=100:y=60:w=120:h=60:color=white:t=fill")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_gray_has_no_saturation_and_one_dominant_color(self) -> None:
        """纯灰：饱和度接近 0，主色就是那个灰，且只占一个色族。"""
        metrics = analyze_frame(decode_frames(self.gray_picture)[0])
        self.assertLess(metrics["mean_saturation"], 0.02)
        self.assertLessEqual(hex_distance(metrics["dominant_colors"][0]["hex"], "#808080"), HEX_TOLERANCE)
        self.assertGreater(metrics["palette_concentration_top5"], 0.99)

    def test_navy_keeps_its_hex_and_is_saturated(self) -> None:
        """深蓝：主色不能被量化吃掉，饱和度要高。"""
        metrics = analyze_frame(decode_frames(self.navy_picture)[0])
        self.assertLessEqual(hex_distance(metrics["dominant_colors"][0]["hex"], "#204060"), HEX_TOLERANCE)
        self.assertGreater(metrics["mean_saturation"], 0.5)

    def test_split_picture_has_extreme_contrast(self) -> None:
        """左黑右白：对比接近满值，纯色率极高，边缘密度不为 0。"""
        frame = decode_frames(self.split_picture)[0]
        metrics = analyze_frame(frame)
        self.assertGreater(metrics["contrast_p95_minus_p5"], 200)
        self.assertGreater(metrics["pure_black_fraction"] + metrics["pure_white_fraction"], 0.9)
        self.assertGreater(measure_edges(frame), 0.001)

    def test_near_black_picture_is_not_reported_as_saturated(self) -> None:
        """近黑画面的 S 会被极小差值放大；指标必须先按亮度筛掉这些像素。"""
        dark_picture = make_picture(self.directory / "dark.png", "0x070305")
        metrics = analyze_frame(decode_frames(dark_picture)[0])
        self.assertLess(metrics["visible_fraction"], 0.05, "近黑画面几乎没有可见像素")
        self.assertLess(metrics["mean_saturation"], 0.05, "近黑像素不该算成高饱和")

    def test_subject_box_separates_from_background(self) -> None:
        """白块在黑底上：给对了框，层次检验必须判定"跳得出来"。"""
        frame = decode_frames(self.subject_picture)[0]
        statistics = region_statistics(frame, (100, 60, 120, 60))
        self.assertGreater(statistics["luma_gap"], 200)
        self.assertGreater(statistics["subject_mean_luma"], 200)

    def test_palette_report_cli_emits_valid_json(self) -> None:
        """命令行 JSON 合同：字段齐全，出界项要给出判定。"""
        output = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "palette_report.py"),
             str(self.navy_picture), "--json", "--profile", "quiet"],
            capture_output=True, text=True, check=True,
        ).stdout
        payload = json.loads(output)
        self.assertIn("metrics", payload)
        self.assertIn("judgements", payload)
        self.assertLessEqual(hex_distance(payload["palette"][0]["hex"], "#204060"), HEX_TOLERANCE)
        self.assertTrue(all("verdict" in row for row in payload["judgements"]))

    def test_baseline_mode_reports_drift(self) -> None:
        """拿灰图当参考、深蓝当成品：饱和度必须被判为偏离参考。"""
        baseline_path = self.directory / "gray-baseline.json"
        baseline_output = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "palette_report.py"), str(self.gray_picture), "--json"],
            capture_output=True, text=True, check=True,
        ).stdout
        baseline_path.write_text(baseline_output, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "palette_report.py"), str(self.navy_picture),
             "--baseline", str(baseline_path), "--strict"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1, "深蓝相对灰图必须判为偏离")
        self.assertIn("DRIFT", result.stdout)

    def test_flat_picture_is_flagged_by_strict_mode(self) -> None:
        """纯色画面应该被判出界：对比 0、熵 0、没有细节——门禁的意义就在这。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "frame_metrics.py"), str(self.gray_picture), "--strict"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1, "平坦画面必须被 --strict 拦住")
        self.assertIn("LOW", result.stdout)

    def test_hierarchy_line_reports_readable_subject(self) -> None:
        """命令行层次检验：给对框时，输出必须明确说"主体跳得出来"。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIRECTORY / "frame_metrics.py"),
             str(self.subject_picture), "--subject-box", "100,60,120,60"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("主体跳得出来", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)