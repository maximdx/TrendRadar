# coding=utf-8
"""
发布时间补全工具

用于热点列表条目的发布时间提取：
1. 优先使用已携带的发布时间字段
2. 缓存命中后直接复用
3. 对缺失条目按 URL 抓取页面元数据补全
"""

import concurrent.futures
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

import requests

from trendradar.utils.time_display import (
    extract_publish_time_display,
    format_datetime_like,
)
from trendradar.utils.url import normalize_url


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

PREFERRED_META_KEYS = (
    "article:published_time",
    "og:published_time",
    "publishdate",
    "pubdate",
    "parsely-pub-date",
    "datepublished",
    "dc.date",
    "article:published",
    "weibo: article:create_at",
)

PREFERRED_JSON_KEYS = (
    "datePublished",
    "dateCreated",
    "publishTime",
    "publishedAt",
    "published_at",
    "pubDate",
    "uploadDate",
    "dateModified",
)

DATE_DISPLAY_PATTERN = re.compile(r"^\d{2}-\d{2} \d{2}:\d{2}$")
META_TAG_PATTERN = re.compile(
    r"<meta\b[^>]*>",
    re.IGNORECASE,
)
ATTR_PATTERN = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*["\']([^"\']*)["\']')
JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
TIME_TAG_PATTERN = re.compile(
    r"<time\b[^>]*datetime\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)

GENERIC_DATE_PATTERNS = [
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"dateCreated"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"publish(?:Time|_time|At|_at)"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"pubDate"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"(?:created_at|createdAt)"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"ctime"\s*:\s*"?(\d{10,13})"?', re.IGNORECASE),
]


def _normalize_display(value: Any) -> str:
    """将候选时间值规范化为 MM-DD HH:MM。"""
    formatted = format_datetime_like(value)
    if not formatted:
        return ""
    if DATE_DISPLAY_PATTERN.match(formatted):
        return formatted
    return ""


def _collect_json_dates(obj: Any, collector: List[Any]) -> None:
    """递归收集 JSON 对象中的发布时间候选值。"""
    if isinstance(obj, dict):
        for key in PREFERRED_JSON_KEYS:
            value = obj.get(key)
            if value not in (None, "", []):
                collector.append(value)
        for value in obj.values():
            _collect_json_dates(value, collector)
    elif isinstance(obj, list):
        for item in obj:
            _collect_json_dates(item, collector)


def _extract_from_meta_tags(html: str) -> List[Any]:
    """从 meta 标签提取发布时间候选值。"""
    candidates: List[Any] = []
    preferred = {k.lower() for k in PREFERRED_META_KEYS}
    for match in META_TAG_PATTERN.finditer(html):
        attrs = {k.lower(): v for k, v in ATTR_PATTERN.findall(match.group(0))}
        key = attrs.get("property") or attrs.get("name")
        content = attrs.get("content", "")
        if key and content and key.lower() in preferred:
            candidates.append(content)
    return candidates


def _extract_from_json_ld(html: str) -> List[Any]:
    """从 JSON-LD 脚本提取发布时间候选值。"""
    candidates: List[Any] = []
    for match in JSON_LD_PATTERN.finditer(html):
        payload = match.group(1).strip()
        if not payload:
            continue
        payload = payload.strip(" \n\r\t")
        if payload.startswith("<!--") and payload.endswith("-->"):
            payload = payload[4:-3].strip()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        _collect_json_dates(data, candidates)
    return candidates


def extract_publish_time_from_html(html: str) -> str:
    """从 HTML 文本中提取发布时间（MM-DD HH:MM）。"""
    if not html:
        return ""

    candidates: List[Any] = []
    candidates.extend(_extract_from_meta_tags(html))
    candidates.extend(_extract_from_json_ld(html))
    candidates.extend(TIME_TAG_PATTERN.findall(html))
    for pattern in GENERIC_DATE_PATTERNS:
        candidates.extend(pattern.findall(html))

    for candidate in candidates:
        normalized = _normalize_display(candidate)
        if normalized:
            return normalized
    return ""


def _extract_hackernews_time(url: str, timeout: float) -> str:
    """通过 Hacker News 官方 API 获取条目发布时间。"""
    parsed = urlparse(url)
    if "news.ycombinator.com" not in parsed.netloc.lower():
        return ""

    item_id = parse_qs(parsed.query).get("id", [""])[0]
    if not item_id.isdigit():
        return ""

    api_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    try:
        response = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return ""

    return _normalize_display(payload.get("time"))


def fetch_publish_time_for_url(url: str, timeout: float = 8.0) -> str:
    """抓取 URL 并提取发布时间（MM-DD HH:MM）。"""
    if not url:
        return ""

    hn_time = _extract_hackernews_time(url, timeout)
    if hn_time:
        return hn_time

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception:
        return ""

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            payload = response.json()
        except Exception:
            return ""
        candidates: List[Any] = []
        _collect_json_dates(payload, candidates)
        for candidate in candidates:
            normalized = _normalize_display(candidate)
            if normalized:
                return normalized
        return ""

    page_html = response.text
    if len(page_html) > 800_000:
        page_html = page_html[:800_000]
    return extract_publish_time_from_html(page_html)


class PublishTimeCache:
    """发布时间缓存（SQLite）。"""

    def __init__(self, db_path: str, miss_ttl_hours: int = 24):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.miss_ttl = timedelta(hours=max(1, miss_ttl_hours))
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_tables()

    def _init_tables(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_time_cache (
                url TEXT PRIMARY KEY,
                published_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK(status IN ('ok', 'miss')),
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_publish_time_cache_status
            ON publish_time_cache(status, updated_at)
            """
        )
        self.conn.commit()

    def get(self, normalized_url: str) -> Optional[str]:
        """查询缓存：返回发布时间字符串；返回空字符串表示近期 miss；None 表示需重新抓取。"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT published_at, status, updated_at
            FROM publish_time_cache
            WHERE url = ?
            """,
            (normalized_url,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        published_at, status, updated_at = row
        if status == "ok" and published_at:
            return published_at
        if status == "miss":
            try:
                last_seen = datetime.fromisoformat(updated_at)
                if datetime.utcnow() - last_seen <= self.miss_ttl:
                    return ""
            except ValueError:
                pass
        return None

    def set(self, normalized_url: str, published_at: str) -> None:
        """写入缓存。"""
        now_iso = datetime.utcnow().isoformat(timespec="seconds")
        status = "ok" if published_at else "miss"
        self.conn.execute(
            """
            INSERT INTO publish_time_cache (url, published_at, status, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                published_at = excluded.published_at,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (normalized_url, published_at or "", status, now_iso),
        )
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def _get_best_url(title_data: Dict[str, Any]) -> str:
    """选择用于抓取发布时间的 URL。"""
    return (
        title_data.get("url")
        or title_data.get("mobileUrl")
        or title_data.get("mobile_url")
        or ""
    )


def _iter_stat_titles(stats: Sequence[Dict[str, Any]]) -> Sequence[Dict[str, Any]]:
    """遍历统计中的标题数据对象。"""
    for stat in stats:
        for title_data in stat.get("titles", []):
            if isinstance(title_data, dict):
                yield title_data


def enrich_stats_publish_times(
    stats: Sequence[Dict[str, Any]],
    cache_db_path: str = "output/news/publish_time_cache.db",
    max_fetch_per_run: int = 200,
    request_timeout: float = 8.0,
    max_workers: int = 8,
    miss_ttl_hours: int = 24,
) -> Dict[str, int]:
    """
    为热点统计条目补齐发布时间字段。

    Returns:
        处理统计信息（用于日志）
    """
    summary = {
        "titles_total": 0,
        "already_has_publish": 0,
        "cache_hit": 0,
        "cache_recent_miss": 0,
        "no_url": 0,
        "pending_urls": 0,
        "fetched_urls_success": 0,
        "fetched_urls_fail": 0,
        "fetched_titles_success": 0,
        "fetched_titles_fail": 0,
        "skipped_by_limit": 0,
    }

    if not stats:
        return summary

    cache = PublishTimeCache(cache_db_path, miss_ttl_hours=miss_ttl_hours)
    pending: Dict[str, List[Dict[str, Any]]] = {}
    url_by_key: Dict[str, str] = {}

    for title_data in _iter_stat_titles(stats):
        summary["titles_total"] += 1

        existing_publish = extract_publish_time_display(title_data)
        if existing_publish:
            title_data["published_at"] = existing_publish
            summary["already_has_publish"] += 1
            continue

        raw_url = _get_best_url(title_data).strip()
        if not raw_url:
            summary["no_url"] += 1
            continue

        cache_key = normalize_url(raw_url) or raw_url
        cached = cache.get(cache_key)
        if cached is None:
            pending.setdefault(cache_key, []).append(title_data)
            if cache_key not in url_by_key:
                url_by_key[cache_key] = raw_url
            continue
        if cached:
            title_data["published_at"] = cached
            summary["cache_hit"] += 1
        else:
            summary["cache_recent_miss"] += 1

    pending_keys = list(pending.keys())
    summary["pending_urls"] = len(pending_keys)

    if max_fetch_per_run > 0 and len(pending_keys) > max_fetch_per_run:
        summary["skipped_by_limit"] = len(pending_keys) - max_fetch_per_run
        pending_keys = pending_keys[:max_fetch_per_run]

    if pending_keys:
        workers = max(1, min(max_workers, len(pending_keys)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(fetch_publish_time_for_url, url_by_key[key], request_timeout): key
                for key in pending_keys
            }
            for future in concurrent.futures.as_completed(future_map):
                key = future_map[future]
                resolved = ""
                try:
                    resolved = future.result() or ""
                except Exception:
                    resolved = ""

                cache.set(key, resolved)
                if resolved:
                    summary["fetched_urls_success"] += 1
                    for title_data in pending.get(key, []):
                        title_data["published_at"] = resolved
                        summary["fetched_titles_success"] += 1
                else:
                    summary["fetched_urls_fail"] += 1
                    summary["fetched_titles_fail"] += len(pending.get(key, []))

    cache.close()
    return summary
