"""结构化日志配置。

约定（纪律）：给人看的命令结果用 print；诊断信息、进度、异常走 logging。
这样 --json、管道、脚本调用时不会混进噪声，排查时又能看到全过程。
"""
from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(verbose: bool = False) -> None:
    """配置根 logger；重复调用无副作用。"""
    level = logging.DEBUG if verbose else logging.INFO
    if os.environ.get("SKILL_LOG_LEVEL"):
        level = getattr(logging, os.environ["SKILL_LOG_LEVEL"].upper(), level)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
