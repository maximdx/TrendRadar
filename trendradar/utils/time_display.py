# coding=utf-8
"""
时间显示策略工具

提供发布时间解析与时间显示模式处理，供 HTML 报告和推送消息复用。
"""

from datetime import datetime
from typing import Any, Dict, Optional

VALID_TIME_DISPLAY_MODES = {"hidden", "observed", "publish", "publish_or_observed"}

TIME_MODE_ALIASES = {
    "observation": "observed",
    "observe": "observed",
    "published": "publish",
    "none": "hidden",
    "off": "hidden",
    "false": "hidden",
    "0": "hidden",
}

PUBLISH_TIME_KEYS = [
    "published_at",
    "publishedAt",
    "published_time",
    "publish_time",
    "pubDate",
    "pub_date",
    "date",
    "datetime",
    "created_at",
    "createdAt",
]


def normalize_time_display_mode(mode: Optional[str], default: str = "hidden") -> str:
    """标准化时间显示模式。"""
    normalized_default = TIME_MODE_ALIASES.get(
        (default or "").strip().lower(), (default or "").strip().lower()
    )
    if normalized_default not in VALID_TIME_DISPLAY_MODES:
        normalized_default = "hidden"

    if mode is None:
        return normalized_default

    raw = str(mode).strip().lower()
    if not raw:
        return normalized_default

    normalized = TIME_MODE_ALIASES.get(raw, raw)
    if normalized not in VALID_TIME_DISPLAY_MODES:
        return normalized_default
    return normalized


def resolve_show_observation_count(
    time_display_mode: str, show_observation_count: Optional[bool]
) -> bool:
    """解析出现次数显示开关。"""
    if show_observation_count is not None:
        return bool(show_observation_count)
    return time_display_mode in {"observed", "publish_or_observed"}


def format_datetime_like(value: Any) -> str:
    """将常见时间格式规范为 `MM-DD HH:MM` 可读格式。"""
    if value is None:
        return ""

    # unix 时间戳（秒 / 毫秒）
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
        except (ValueError, OSError, OverflowError):
            return ""

    if not isinstance(value, str):
        return ""

    raw = value.strip()
    if not raw:
        return ""

    if raw.isdigit():
        try:
            ts = float(raw)
            if ts > 10_000_000_000:
                ts /= 1000.0
            return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
        except (ValueError, OSError, OverflowError):
            pass

    iso_candidates = [raw, raw.replace("Z", "+00:00")]
    for candidate in iso_candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.strftime("%m-%d %H:%M")
        except ValueError:
            continue

    known_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m-%d %H:%M",
        "%H:%M",
    ]
    for fmt in known_formats:
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%H:%M":
                return raw
            return dt.strftime("%m-%d %H:%M")
        except ValueError:
            continue

    # 兜底：原样返回，避免丢失可读时间
    return raw


def extract_publish_time_display(item: Dict[str, Any]) -> str:
    """从条目中提取发布时间并格式化。"""
    if not isinstance(item, dict):
        return ""

    sources = [item]
    extra = item.get("extra")
    if isinstance(extra, dict):
        sources.append(extra)

    for source in sources:
        for key in PUBLISH_TIME_KEYS:
            if key not in source:
                continue
            formatted = format_datetime_like(source.get(key))
            if formatted:
                return formatted

    return ""


def resolve_time_display(
    time_display_mode: str,
    observed_display: str = "",
    publish_display: str = "",
) -> str:
    """根据模式选择最终展示时间。"""
    mode = normalize_time_display_mode(time_display_mode, default="hidden")
    if mode == "hidden":
        return ""
    if mode == "publish":
        return publish_display
    if mode == "publish_or_observed":
        return publish_display or observed_display
    return observed_display
