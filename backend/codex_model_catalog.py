# coding: utf-8
"""读取 Codex 远端模型目录中的思考等级。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def model_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    items = payload.get("models")
    if isinstance(items, list):
        return items
    items = payload.get("data")
    return items if isinstance(items, list) else []


def _decode_catalog(output):
    text = str(output or "").strip().lstrip("\ufeff")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def fetch_codex_model_catalog(timeout_seconds=20):
    """调用 Codex CLI；默认命令会刷新远端目录，失败时由调用方回退。"""
    command = os.environ.get("CONFIGPILOT_CODEX_COMMAND") or shutil.which("codex")
    if not command:
        return []
    completed = subprocess.run(
        [command, "debug", "models"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(f"codex debug models 退出码 {completed.returncode}")
    return model_items(_decode_catalog(completed.stdout))
