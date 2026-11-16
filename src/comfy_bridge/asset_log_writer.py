"""把每次生成追加进 asset_log.json。

这份日志就是素材的来源凭证：哪个工作流、哪个模型、什么 seed、跑了多久、产出哪些文件。
游戏 README 的素材表直接读它，不要手写。
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

LOGGER = logging.getLogger(__name__)

LOG_FILENAME = "asset_log.json"


def append_asset_record(directory: Path, record: dict) -> Path:
    """追加一条记录，返回日志路径。"""
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / LOG_FILENAME
    records: list[dict] = []
    if log_path.exists():
        try:
            records = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 日志坏了不能吞掉，但也不该让一次生成白跑：备份后重建。
            backup = log_path.with_suffix(f".broken_{time.strftime('%H%M%S')}.json")
            log_path.rename(backup)
            LOGGER.warning("asset_log.json 解析失败，已备份为 %s 并重建", backup.name)
    records.append(record)
    log_path.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    return log_path
