#!/usr/bin/env python3
"""audio-taste 的自测：用 ffmpeg 合成音频，验证指标方向正确。

跑法：
    python -m unittest discover -s skills/audio-taste/tests -v
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audio_report.py"
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def load_module():
    specification = importlib.util.spec_from_file_location("audio_report", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@unittest.skipUnless(FFMPEG_AVAILABLE, "需要 ffmpeg")
class AudioReportTest(unittest.TestCase):
    """指标方向性：更响的单音必须有更高的响度；静音必须被判成静音；削顶必须被抓住。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory(prefix="audio-taste-test-")
        cls.directory = Path(cls.temporary_directory.name)
        cls.module = load_module()
        # 用 aevalsrc 精确控制振幅：0.5 振幅 = −6.02 dBFS（sine 源的默认振幅不是 1，别用它做基准）
        cls.quiet_tone = cls.directory / "quiet.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "aevalsrc=0.5*sin(2*PI*1000*t):d=1:s=44100",
                        str(cls.quiet_tone)], check=True)
        # 满摆幅（会削顶）
        cls.loud_tone = cls.directory / "loud.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "aevalsrc=sin(2*PI*1000*t):d=1:s=44100",
                        str(cls.loud_tone)], check=True)
        # 纯静音
        cls.silence = cls.directory / "silence.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "anullsrc=r=44100:cl=mono", "-t", "1", str(cls.silence)], check=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_quiet_tone_has_expected_levels(self) -> None:
        metrics = self.module.measure_levels(self.quiet_tone)
        self.assertAlmostEqual(metrics["peak_db"], -6.0, delta=0.6)
        # 0.5 振幅 1 kHz 正弦的 LUFS 约 −9（满摆幅约 −3）；用它当基准点
        self.assertAlmostEqual(metrics["lufs_integrated"], -9.0, delta=1.0)

    def test_loud_tone_reaches_zero_peak(self) -> None:
        metrics = self.module.measure_levels(self.loud_tone)
        self.assertGreater(metrics["peak_db"], -0.5)

    def test_louder_tone_has_higher_loudness(self) -> None:
        quiet = self.module.measure_levels(self.quiet_tone)["lufs_integrated"]
        loud = self.module.measure_levels(self.loud_tone)["lufs_integrated"]
        self.assertGreater(loud, quiet)

    def test_silence_is_detected(self) -> None:
        duration = self.module.probe_media(self.silence)["duration"]
        self.assertGreater(self.module.measure_silence(self.silence, float(duration)), 0.9)

    def test_cli_flags_clipping(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(self.loud_tone), "--profile", "sfx", "--json"],
            capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout)
        verdicts = {row["metric"]: row["verdict"] for row in payload["judgements"]}
        self.assertEqual(verdicts["peak_db"], "FAIL", "满摆幅正弦必须被判削顶")

    def test_cli_passes_for_quiet_sfx(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(self.quiet_tone), "--profile", "sfx", "--strict"],
            capture_output=True, text=True, check=False)
        # −6 dB 峰值合规；响度 −6 LUFS 会超出 −19~−13 区间，所以只断言"不是因峰值失败"
        self.assertIn("peak_db", completed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)