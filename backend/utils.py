from __future__ import annotations

import json
import math
import os
import re
import stat
from hashlib import sha1
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DASHBOARD_DIR = ROOT / "dashboard"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_run_date(timezone: str = "Asia/Shanghai") -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d")


SENSITIVE_CONFIG_FILES = {"live_trading.json", "llm_provider.json"}


def _ensure_sensitive_file_permission(path: Path) -> None:
    if path.name in SENSITIVE_CONFIG_FILES and path.exists():
        current_mode = stat.S_IMODE(path.stat().st_mode)
        if current_mode != 0o600:
            os.chmod(path, 0o600)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        _ensure_sensitive_file_permission(path)
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.name in SENSITIVE_CONFIG_FILES:
        os.chmod(path, 0o600)


def num(value: Any) -> float | None:
    if value in (None, "", False):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def clamp(value: Any, minimum: float, maximum: float) -> float:
    parsed = num(value)
    if parsed is None:
        return minimum
    return max(minimum, min(maximum, parsed))


def clean_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def one_line(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def safe_last(items: list[Any] | None) -> Any:
    if not items:
        return None
    return items[-1]


def sha1_hex(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()


def parse_klines(
    rows: list[list[Any]] | None,
    *,
    reverse: bool = False,
    quote_volume_index: int = 7,
    close_time_index: int | None = 6,
    min_length: int = 5,
    interval_ms: int | None = None,
) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    iterable = reversed(rows) if reverse else rows
    for row in iterable or []:
        if not isinstance(row, (list, tuple)) or len(row) < min_length:
            continue
        close_value = num(row[4])
        if close_value is None:
            continue
        open_time = int(num(row[0]) or 0)
        if close_time_index is not None and close_time_index < len(row):
            close_time = row[close_time_index]
        elif interval_ms is not None:
            close_time = open_time + interval_ms
        else:
            close_time = open_time
        quote_volume = None
        if quote_volume_index < len(row):
            quote_volume = num(row[quote_volume_index])
        if quote_volume is None and quote_volume_index != 6 and len(row) > 6:
            quote_volume = num(row[6])
        parsed.append(
            {
                "openTime": open_time,
                "closeTime": close_time,
                "open": num(row[1]),
                "high": num(row[2]),
                "low": num(row[3]),
                "close": close_value,
                "volume": num(row[5]),
                "quoteVolume": quote_volume,
            }
        )
    return parsed


def parse_json_loose(raw_text: str) -> Any:
    text = str(raw_text or "").strip()
    if not text:
      raise ValueError("empty JSON payload")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.S)
    if fence_match:
        return json.loads(fence_match.group(1))
    brace_match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if brace_match:
        return json.loads(brace_match.group(1))
    raise ValueError("could not find JSON object in response")
