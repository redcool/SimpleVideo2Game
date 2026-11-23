#!/usr/bin/env python3
"""workflow_editor 的单测：参数必须"显式生效或显式报错"，不能静默无效。

跑法：python -m unittest tests.test_workflow_editor -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.comfy_bridge.workflow_editor import (  # noqa: E402
    WorkflowEditError, referenced_model_files, set_input, set_seed,
)


def make_workflow() -> dict:
    """最小的两张节点图：一个带 width 的采样器 + 一个带 text 的编码器。"""
    return {
        "3": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20, "width": 1024}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "hello"}},
    }


class WorkflowEditorTest(unittest.TestCase):
    def test_sets_existing_input(self) -> None:
        workflow = make_workflow()
        changed = set_input(workflow, "3.width", 2048)
        self.assertEqual(changed, [("3", "width")])
        self.assertEqual(workflow["3"]["inputs"]["width"], 2048)

    def test_unknown_input_on_known_node_is_an_error(self) -> None:
        """节点存在但没有这个输入：必须报错并列出可用输入，不能悄悄加一个键。"""
        workflow = make_workflow()
        with self.assertRaises(WorkflowEditError) as context:
            set_input(workflow, "3.height", 1152)
        message = str(context.exception)
        self.assertIn("height", message)
        self.assertIn("width", message, "报错里要列出该节点现有输入")
        self.assertNotIn("height", workflow["3"]["inputs"], "不许静默写入")

    def test_unknown_node_is_an_error(self) -> None:
        with self.assertRaises(WorkflowEditError):
            set_input(make_workflow(), "99.width", 1)

    def test_bare_name_applies_to_every_matching_node(self) -> None:
        workflow = {
            "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
            "5": {"class_type": "KSampler", "inputs": {"seed": 2}},
        }
        changed = set_input(workflow, "seed", 7)
        self.assertEqual(len(changed), 2)
        self.assertEqual(workflow["5"]["inputs"]["seed"], 7)

    def test_bare_name_without_match_is_an_error(self) -> None:
        with self.assertRaises(WorkflowEditError):
            set_input(make_workflow(), "nonexistent_input", 1)

    def test_set_seed_covers_seed_and_noise_seed(self) -> None:
        workflow = {
            "3": {"class_type": "KSampler", "inputs": {"seed": 1}},
            "8": {"class_type": "SamplerCustom", "inputs": {"noise_seed": 2}},
        }
        changed = set_seed(workflow, 42)
        self.assertEqual(len(changed), 2)
        self.assertEqual(workflow["8"]["inputs"]["noise_seed"], 42)

    def test_referenced_models_found(self) -> None:
        workflow = {"54": {"class_type": "Loader", "inputs": {"ckpt_name": "a.safetensors"}}}
        self.assertEqual(referenced_model_files(workflow), {"ckpt_name": ["a.safetensors"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
