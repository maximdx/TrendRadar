# coding=utf-8
"""
HTML 报告渲染模块

提供 HTML 格式的热点新闻报告生成功能
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

import yaml

from trendradar.report.helpers import html_escape
from trendradar.utils.time import convert_time_for_display
from trendradar.utils.time_display import (
    normalize_time_display_mode,
    extract_publish_time_display,
    resolve_show_observation_count,
    resolve_time_display,
)
from trendradar.ai.formatter import render_ai_analysis_html_rich


def render_html_content(
    report_data: Dict,
    total_titles: int,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
    *,
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[List[Dict]] = None,
    rss_new_items: Optional[List[Dict]] = None,
    display_mode: str = "keyword",
    standalone_data: Optional[Dict] = None,
    ai_analysis: Optional[Any] = None,
    show_new_section: bool = True,
    time_display_mode: Optional[str] = None,
    show_observation_count: Optional[bool] = None,
    theme_mode: Optional[str] = None,
) -> str:
    """渲染HTML内容

    Args:
        report_data: 报告数据字典，包含 stats, new_titles, failed_ids, total_new_count
        total_titles: 新闻总数
        mode: 报告模式 ("daily", "current", "incremental")
        update_info: 更新信息（可选）
        region_order: 区域显示顺序列表
        get_time_func: 获取当前时间的函数（可选，默认使用 datetime.now）
        rss_items: RSS 统计条目列表（可选）
        rss_new_items: RSS 新增条目列表（可选）
        display_mode: 显示模式 ("keyword"=按关键词分组, "platform"=按平台分组)
        standalone_data: 独立展示区数据（可选），包含 platforms 和 rss_feeds
        ai_analysis: AI 分析结果对象（可选），AIAnalysisResult 实例
        show_new_section: 是否显示新增热点区域
        time_display_mode: 时间显示模式（hidden/observed/publish/publish_or_observed）
        show_observation_count: 是否显示出现次数（None 时按模式自动）
        theme_mode: HTML 主题模式（light/dark/system）

    Returns:
        渲染后的 HTML 字符串
    """
    # 默认区域顺序
    default_region_order = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]
    if region_order is None:
        region_order = default_region_order

    def get_env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on", "y"}

    # time_display_mode/show_observation_count 支持 config 传入，缺省时回退环境变量
    if time_display_mode is not None:
        time_mode = normalize_time_display_mode(time_display_mode, default="hidden")
    else:
        time_mode = normalize_time_display_mode(
            os.getenv("HTML_TIME_DISPLAY_MODE", "hidden"),
            default="hidden",
        )

    if show_observation_count is None:
        show_observation_count = get_env_bool(
            "HTML_SHOW_OBSERVATION_COUNT",
            resolve_show_observation_count(time_mode, None),
        )
    else:
        show_observation_count = bool(show_observation_count)

    def normalize_theme_mode(value: Optional[str], default: str = "system") -> str:
        if value is None:
            return default
        raw = str(value).strip().lower()
        return raw if raw in {"light", "dark", "system"} else default

    def resolve_default_theme_mode() -> str:
        if theme_mode is not None:
            return normalize_theme_mode(theme_mode, default="system")

        env_theme_mode = os.getenv("HTML_THEME_MODE", "").strip()
        if env_theme_mode:
            return normalize_theme_mode(env_theme_mode, default="system")

        for config_path in ("config/config.yaml", "/app/config/config.yaml"):
            if not os.path.exists(config_path):
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                return normalize_theme_mode(
                    config_data.get("display", {}).get("theme_mode"),
                    default="system",
                )
            except Exception:
                continue

        return "system"

    default_theme_mode = resolve_default_theme_mode()

    def simplify_observed_time(time_display: str) -> str:
        if not time_display:
            return ""
        return (
            time_display.replace(" ~ ", "~")
            .replace("[", "")
            .replace("]", "")
        )

    def resolve_hotlist_time_display(item: Dict[str, Any]) -> str:
        observed_display = simplify_observed_time(item.get("time_display", ""))
        publish_display = extract_publish_time_display(item)
        return resolve_time_display(
            time_mode,
            observed_display=observed_display,
            publish_display=publish_display,
        )

    def resolve_standalone_time_display(item: Dict[str, Any]) -> str:
        publish_display = extract_publish_time_display(item)

        first_time = item.get("first_time", "")
        last_time = item.get("last_time", "")
        observed_display = ""
        if first_time and last_time and first_time != last_time:
            first_time_display = convert_time_for_display(first_time)
            last_time_display = convert_time_for_display(last_time)
            observed_display = f"{first_time_display}~{last_time_display}"
        elif first_time:
            observed_display = convert_time_for_display(first_time)

        return resolve_time_display(
            time_mode,
            observed_display=observed_display,
            publish_display=publish_display,
        )

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>热点新闻分析</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <script>
            (() => {
                const storageKey = 'trendradar_report_theme_mode';
                const defaultThemeMode = '""" + default_theme_mode + """';
                const savedMode = localStorage.getItem(storageKey);
                const themeMode = ['light', 'dark', 'system'].includes(savedMode)
                    ? savedMode
                    : defaultThemeMode;
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                const effectiveTheme = themeMode === 'system' ? (prefersDark ? 'dark' : 'light') : themeMode;

                document.documentElement.dataset.themeMode = themeMode;
                document.documentElement.dataset.theme = effectiveTheme;
                document.documentElement.style.colorScheme = effectiveTheme;
            })();
        </script>
        <style>
            * { box-sizing: border-box; }
            :root {
                color-scheme: light;
                --page-bg: #e9eef5;
                --surface-primary: #ffffff;
                --surface-secondary: #f8fbff;
                --surface-muted: #edf2f8;
                --surface-elevated: rgba(255, 255, 255, 0.96);
                --content-bg: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
                --card-bg: rgba(248, 250, 252, 0.98);
                --card-hover-bg: #f1f5f9;
                --border-default: #dbe4f0;
                --border-soft: #e9eef5;
                --text-primary: #0f172a;
                --text-secondary: #334155;
                --text-muted: #64748b;
                --text-soft: #94a3b8;
                --link-color: #0f172a;
                --link-hover: #1d4ed8;
                --link-visited: #5b21b6;
                --accent: #2563eb;
                --accent-soft: #dbeafe;
                --header-gradient: linear-gradient(135deg, #f8fbff 0%, #e8efff 52%, #dfe8ff 100%);
                --header-text: #0f172a;
                --header-subtle: rgba(15, 23, 42, 0.72);
                --header-watermark: rgba(79, 70, 229, 0.14);
                --toolbar-glass: rgba(255, 255, 255, 0.82);
                --toolbar-hover: rgba(255, 255, 255, 0.96);
                --toolbar-border: rgba(148, 163, 184, 0.4);
                --toolbar-color: #0f172a;
                --shadow-soft: 0 18px 44px rgba(15, 23, 42, 0.12);
            }

            html[data-theme="dark"] {
                color-scheme: dark;
                --page-bg: #0b1220;
                --surface-primary: #101826;
                --surface-secondary: #172033;
                --surface-muted: #1f2937;
                --surface-elevated: rgba(15, 23, 42, 0.96);
                --content-bg: linear-gradient(180deg, #101826 0%, #131d2f 100%);
                --card-bg: rgba(23, 32, 51, 0.92);
                --card-hover-bg: #223048;
                --border-default: #334155;
                --border-soft: #253041;
                --text-primary: #e5eefc;
                --text-secondary: #cbd5e1;
                --text-muted: #94a3b8;
                --text-soft: #64748b;
                --link-color: #e5eefc;
                --link-hover: #93c5fd;
                --link-visited: #d8b4fe;
                --accent: #3b82f6;
                --accent-soft: rgba(59, 130, 246, 0.18);
                --header-gradient: linear-gradient(135deg, #13233c 0%, #1f3460 46%, #4c1d95 100%);
                --header-text: #f8fafc;
                --header-subtle: rgba(255, 255, 255, 0.76);
                --header-watermark: rgba(255, 255, 255, 0.12);
                --toolbar-glass: rgba(15, 23, 42, 0.55);
                --toolbar-hover: rgba(30, 41, 59, 0.88);
                --toolbar-border: rgba(148, 163, 184, 0.24);
                --toolbar-color: #f8fafc;
                --shadow-soft: 0 18px 40px rgba(2, 6, 23, 0.34);
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                margin: 0;
                padding: 16px;
                background: var(--page-bg);
                color: var(--text-primary);
                line-height: 1.5;
                transition: background-color 0.2s ease, color 0.2s ease;
            }

            .container {
                max-width: 600px;
                margin: 0 auto;
                background: var(--surface-primary);
                border: 1px solid var(--border-default);
                border-radius: 12px;
                overflow: hidden;
                box-shadow: var(--shadow-soft);
            }

            .header {
                background: var(--header-gradient);
                color: var(--header-text);
                padding: 84px 24px 32px;
                text-align: center;
                position: relative;
                overflow: hidden;
                border-bottom: 1px solid var(--border-default);
            }

            .header-watermark {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: clamp(40px, 8vw, 80px);
                font-weight: 900;
                letter-spacing: 0.05em;
                color: var(--header-watermark);
                pointer-events: none;
                z-index: 1;
                white-space: nowrap;
                -webkit-mask-image: radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%);
                mask-image: radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%);
                transition: -webkit-mask-image 0.3s ease, mask-image 0.3s ease;
                user-select: none;
            }

            .header-toolbar {
                position: absolute;
                top: 16px;
                right: 16px;
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 8px;
                max-width: calc(100% - 32px);
                flex-wrap: wrap;
            }

            .save-buttons {
                display: flex;
                gap: 8px;
                z-index: 10;
            }

            .save-btn-group {
                position: relative;
                display: flex;
            }

            .save-btn {
                background: var(--toolbar-glass);
                border: 1px solid var(--toolbar-border);
                color: var(--toolbar-color);
                padding: 10px 18px;
                border-radius: 6px 0 0 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                white-space: nowrap;
                min-height: 38px;
                border-right: none;
            }

            .sr-only {
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
            }

            .theme-controls {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                padding: 8px 12px;
                border-radius: 999px;
                border: 1px solid var(--toolbar-border);
                background: var(--toolbar-glass);
                backdrop-filter: blur(14px);
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
                justify-content: center;
            }

            .theme-status {
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.02em;
                white-space: nowrap;
                color: var(--toolbar-color);
            }

            .theme-switch {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                white-space: nowrap;
            }

            .theme-switch.is-disabled {
                cursor: not-allowed;
                opacity: 0.72;
            }

            .theme-switch-label {
                font-size: 12px;
                font-weight: 600;
                color: var(--toolbar-color);
                opacity: 0.92;
            }

            .theme-switch-track {
                position: relative;
                width: 44px;
                height: 24px;
                border-radius: 999px;
                border: 1px solid var(--toolbar-border);
                background: var(--surface-muted);
            }

            .theme-switch-thumb {
                position: absolute;
                top: 2px;
                left: 2px;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: linear-gradient(135deg, #ffffff, #dbeafe);
                box-shadow: 0 3px 8px rgba(15, 23, 42, 0.25);
                transition: transform 0.2s ease, background 0.2s ease;
            }

            .theme-switch input:checked + .theme-switch-thumb {
                transform: translateX(20px);
                background: linear-gradient(135deg, #facc15, #fb7185);
            }

            .save-btn:hover {
                background: var(--toolbar-hover);
            }

            .save-btn:active {
                transform: translateY(0);
            }

            .save-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .save-dropdown-trigger {
                background: var(--toolbar-glass);
                border: 1px solid var(--toolbar-border);
                color: var(--toolbar-color);
                padding: 10px 10px;
                border-radius: 0 6px 6px 0;
                cursor: pointer;
                font-size: 11px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                min-height: 38px;
                display: flex;
                align-items: center;
            }

            .save-dropdown-trigger:hover {
                background: var(--toolbar-hover);
            }

            .save-dropdown-menu {
                position: absolute;
                top: 100%;
                right: 0;
                margin-top: 4px;
                background: var(--surface-elevated);
                backdrop-filter: blur(16px);
                border: 1px solid var(--border-default);
                border-radius: 8px;
                padding: 4px;
                min-width: 140px;
                opacity: 0;
                visibility: hidden;
                transform: translateY(-4px);
                transition: all 0.2s ease;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16);
            }

            .save-btn-group:hover .save-dropdown-menu,
            .save-dropdown-menu:hover {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }

            .save-dropdown-item {
                display: block;
                width: 100%;
                padding: 9px 14px;
                background: none;
                border: none;
                color: var(--text-primary);
                font-size: 13px;
                cursor: pointer;
                border-radius: 5px;
                text-align: left;
                transition: background 0.15s;
                white-space: nowrap;
            }

            .save-dropdown-item:hover {
                background: var(--surface-muted);
            }

            .dropdown-icon {
                width: 14px;
                height: 14px;
                margin-right: 8px;
                vertical-align: -2px;
                flex-shrink: 0;
            }

            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
                position: relative;
                z-index: 2;
                color: var(--header-text);
            }

            .header-info {
                position: relative;
                z-index: 2;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                font-size: 14px;
                color: var(--header-text);
                opacity: 0.98;
            }

            .info-item {
                text-align: center;
            }

            .info-label {
                display: block;
                font-size: 12px;
                color: var(--header-subtle);
                margin-bottom: 4px;
            }

            .info-value {
                font-weight: 600;
                font-size: 16px;
                color: var(--header-text);
            }

            .content {
                padding: 24px;
                background: var(--content-bg);
            }

            .outline-panel {
                position: relative;
                z-index: 5;
                margin-bottom: 20px;
                padding: 12px;
                border: 1px solid var(--border-default);
                border-radius: 10px;
                background: var(--surface-elevated);
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
            }

            .outline-panel.is-floating-side {
                position: fixed;
                top: 16px;
                z-index: 30;
                margin-bottom: 0;
                max-height: calc(100vh - 24px);
                display: flex;
                flex-direction: column;
            }

            .outline-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                margin-bottom: 8px;
            }

            .outline-title {
                font-size: 13px;
                font-weight: 600;
                color: var(--text-secondary);
            }

            .outline-actions {
                display: flex;
                align-items: center;
                gap: 6px;
            }

            .outline-action-btn {
                border: 1px solid var(--border-default);
                background: var(--surface-secondary);
                color: var(--text-secondary);
                font-size: 12px;
                border-radius: 6px;
                padding: 4px 8px;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .outline-action-btn:hover {
                background: var(--surface-muted);
                border-color: var(--text-soft);
            }

            .outline-links {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                max-height: 180px;
                overflow-y: auto;
                padding-right: 4px;
            }

            .outline-panel.is-floating-side .outline-links {
                flex: 1;
                flex-direction: column;
                flex-wrap: nowrap;
                gap: 6px;
                max-height: none;
                padding-right: 2px;
                min-height: 0;
            }

            .outline-link {
                display: inline-flex;
                align-items: center;
                padding: 4px 8px;
                border-radius: 999px;
                border: 1px solid var(--border-default);
                background: var(--surface-secondary);
                color: var(--text-secondary);
                text-decoration: none;
                font-size: 12px;
                line-height: 1.4;
                transition: all 0.2s ease;
            }

            .outline-panel.is-floating-side .outline-link {
                display: block;
                border-radius: 8px;
                padding: 6px 8px;
            }

            .outline-link:hover {
                background: var(--accent-soft);
                border-color: rgba(37, 99, 235, 0.28);
                color: var(--link-hover);
            }

            .outline-link.level-2 {
                font-size: 11px;
                padding: 4px 7px;
            }

            .outline-panel.is-floating-side .outline-link.level-2 {
                margin-left: 8px;
                font-size: 11px;
            }

            .outline-link.active {
                background: var(--accent-soft);
                border-color: rgba(37, 99, 235, 0.32);
                color: var(--link-hover);
                font-weight: 600;
            }

            [data-outline-title] {
                scroll-margin-top: 80px;
            }

            .word-group {
                margin-bottom: 40px;
            }

            .word-group:first-child {
                margin-top: 0;
            }

            .word-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid var(--border-default);
            }

            .fold-header {
                cursor: pointer;
                user-select: none;
            }

            .fold-header:focus-visible {
                outline: 2px solid var(--accent);
                outline-offset: 2px;
                border-radius: 6px;
            }

            .word-header-right {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .fold-toggle {
                color: var(--text-muted);
                font-size: 13px;
                line-height: 1;
                min-width: 12px;
                text-align: center;
            }

            .foldable-section.is-collapsed .word-header {
                margin-bottom: 0;
            }

            .foldable-section.is-collapsed {
                margin-bottom: 20px;
            }

            .foldable-section.is-collapsed > .fold-body {
                display: none;
            }

            .word-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .word-name {
                font-size: 17px;
                font-weight: 600;
                color: var(--text-primary);
            }

            .word-count {
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 500;
            }

            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }

            .word-index {
                color: var(--text-muted);
                font-size: 12px;
            }

            .news-item {
                margin-bottom: 14px;
                padding: 16px 14px;
                border: 1px solid var(--border-soft);
                border-radius: 14px;
                background: var(--card-bg);
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
                position: relative;
                display: flex;
                gap: 12px;
                align-items: flex-start;
                transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
            }

            .news-item:last-child {
                margin-bottom: 0;
            }

            .news-item:hover {
                background: var(--card-hover-bg);
                border-color: var(--border-default);
                box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
            }

            .news-item.new::after {
                content: "NEW";
                position: absolute;
                top: 12px;
                right: 14px;
                background: #f59e0b;
                color: #ffffff;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
                border-radius: 999px;
                letter-spacing: 0.5px;
            }

            .news-number {
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 600;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
                background: var(--surface-primary);
                border: 1px solid var(--border-default);
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                align-self: flex-start;
                margin-top: 8px;
                position: relative;
                cursor: pointer;
                transition: background 0.15s, color 0.15s;
            }
            .news-number .num-text { transition: opacity 0.15s; }
            .news-number .copy-icon {
                position: absolute;
                opacity: 0;
                transition: opacity 0.15s;
            }
            .news-item:hover .news-number .num-text { opacity: 0; }
            .news-item:hover .news-number .copy-icon { opacity: 1; }
            .news-item:hover .news-number {
                background: var(--accent-soft);
                color: var(--accent);
            }
            .news-number.copied {
                background: #dcfce7 !important;
                color: #166534 !important;
            }
            .news-number.copied .num-text { opacity: 0 !important; }
            .news-number.copied .copy-icon { opacity: 1 !important; }

            .news-content {
                flex: 1;
                min-width: 0;
                padding-right: 40px;
                display: grid;
                grid-template-columns: minmax(160px, 240px) minmax(0, 1fr);
                column-gap: 18px;
                align-items: start;
            }

            .news-item.new .news-content {
                padding-right: 50px;
            }

            .news-header {
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
                align-content: flex-start;
                min-width: 0;
                padding-top: 2px;
            }

            .source-name {
                color: var(--text-secondary);
                font-size: 12px;
                font-weight: 600;
            }

            .keyword-tag {
                color: var(--accent);
                font-size: 12px;
                font-weight: 600;
                background: var(--accent-soft);
                padding: 3px 7px;
                border-radius: 999px;
            }

            .rank-num {
                color: #fff;
                background: #475569;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }

            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }

            .time-info {
                color: var(--text-secondary);
                font-size: 11px;
                font-weight: 500;
            }

            .count-info {
                color: #047857;
                font-size: 11px;
                font-weight: 700;
            }

            .trend-info {
                font-size: 11px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 10px;
                line-height: 1;
            }

            .trend-info.up {
                color: #065f46;
                background: #d1fae5;
            }

            .trend-info.down {
                color: #9a3412;
                background: #ffedd5;
            }

            .trend-info.flat {
                color: var(--text-secondary);
                background: var(--surface-muted);
            }

            .news-title {
                font-size: 15px;
                line-height: 1.4;
                color: var(--text-primary);
                margin: 0;
                min-width: 0;
                text-align: left;
            }

            .news-link {
                color: var(--link-color);
                text-decoration: none;
                display: block;
                font-weight: 600;
                word-break: break-word;
            }

            .news-link:hover {
                color: var(--link-hover);
                text-decoration: underline;
            }

            .news-link:visited {
                color: var(--link-visited);
            }

            /* 通用区域分割线样式 */
            .section-divider {
                margin-top: 32px;
                padding-top: 24px;
                border-top: 2px solid var(--border-default);
            }

            /* 热榜统计区样式 */
            .hotlist-section {
                /* 默认无边框，由 section-divider 动态添加 */
            }

            .new-section {
                margin-top: 40px;
                padding-top: 24px;
            }

            .new-section-title {
                color: var(--text-primary);
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }

            .new-source-group {
                margin-bottom: 24px;
            }

            .new-source-title {
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 500;
                margin: 0 0 12px 0;
                padding-bottom: 6px;
                border-bottom: 1px solid var(--border-soft);
            }

            .new-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 0;
                border-bottom: 1px solid var(--border-soft);
            }

            .new-item:last-child {
                border-bottom: none;
            }

            .new-item-number {
                color: var(--text-muted);
                font-size: 12px;
                font-weight: 600;
                min-width: 18px;
                text-align: center;
                flex-shrink: 0;
                background: var(--surface-secondary);
                border-radius: 50%;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .new-item-rank {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 8px;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
            }

            .new-item-rank.top { background: #dc2626; }
            .new-item-rank.high { background: #ea580c; }

            .new-item-content {
                flex: 1;
                min-width: 0;
            }

            .new-item-title {
                font-size: 14px;
                line-height: 1.4;
                color: var(--text-primary);
                margin: 0;
            }

            .error-section {
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }

            .error-title {
                color: #dc2626;
                font-size: 14px;
                font-weight: 600;
                margin: 0 0 8px 0;
            }

            .error-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }

            .error-item {
                color: #991b1b;
                font-size: 13px;
                padding: 2px 0;
                font-family: 'SF Mono', Consolas, monospace;
            }

            .footer {
                margin-top: 32px;
                padding: 20px 24px;
                background: var(--surface-secondary);
                border-top: 1px solid var(--border-default);
                text-align: center;
            }

            .footer-content {
                font-size: 13px;
                color: var(--text-secondary);
                line-height: 1.6;
            }

            .footer-link {
                color: var(--accent);
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s ease;
            }

            .footer-link:hover {
                color: var(--link-hover);
                text-decoration: underline;
            }

            .project-name {
                font-weight: 600;
                color: var(--text-primary);
            }

            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { padding: 24px 20px; }
                .content { padding: 20px; }
                .footer { padding: 16px 20px; }
                .outline-panel,
                .outline-panel.is-floating-side {
                    position: relative;
                    top: auto;
                    left: auto !important;
                    width: auto !important;
                    max-height: none;
                    display: block;
                }
                .outline-header {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .outline-links {
                    max-height: 140px;
                }
                .outline-panel.is-floating-side .outline-links {
                    flex-direction: row;
                    flex-wrap: wrap;
                    gap: 8px;
                }
                .header-info { grid-template-columns: 1fr; gap: 12px; }
                .news-header { gap: 6px; }
                .news-content {
                    padding-right: 45px;
                    grid-template-columns: 1fr;
                    row-gap: 8px;
                }
                .news-item { gap: 8px; }
                .new-item { gap: 8px; }
                .news-number { width: 20px; height: 20px; font-size: 12px; }
                .save-buttons {
                    display: flex;
                    gap: 8px;
                    flex-direction: column;
                    justify-content: center;
                    width: 100%;
                }
                .save-btn-group {
                    flex: 1;
                }
                .save-btn {
                    width: 100%;
                    border-radius: 6px 0 0 6px;
                }
                .header-toolbar {
                    position: static;
                    margin-bottom: 16px;
                    flex-direction: column;
                    align-items: stretch;
                }
                .theme-controls {
                    width: 100%;
                    justify-content: center;
                    border-radius: 16px;
                }
                .theme-status {
                    text-align: center;
                }
            }

            /* RSS 订阅内容样式 */
            .rss-section {
                margin-top: 32px;
                padding-top: 24px;
            }

            .rss-section-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
            }

            .rss-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #059669;
            }

            .rss-section-count {
                color: var(--text-secondary);
                font-size: 14px;
            }

            .feed-group {
                margin-bottom: 24px;
            }

            .feed-group:last-child {
                margin-bottom: 0;
            }

            .feed-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 2px solid #10b981;
            }

            .feed-name {
                font-size: 15px;
                font-weight: 600;
                color: #059669;
            }

            .feed-count {
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 500;
            }

            .rss-item {
                margin-bottom: 12px;
                padding: 14px;
                background: rgba(16, 185, 129, 0.08);
                border-radius: 8px;
                border-left: 3px solid #10b981;
            }

            .rss-item:last-child {
                margin-bottom: 0;
            }

            .rss-meta {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 6px;
                flex-wrap: wrap;
            }

            .rss-time {
                color: var(--text-secondary);
                font-size: 12px;
            }

            .rss-author {
                color: #059669;
                font-size: 12px;
                font-weight: 500;
            }

            .rss-title {
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 6px;
            }

            .rss-link {
                color: var(--text-primary);
                text-decoration: none;
                font-weight: 500;
            }

            .rss-link:hover {
                color: #059669;
                text-decoration: underline;
            }

            .rss-summary {
                font-size: 13px;
                color: var(--text-secondary);
                line-height: 1.5;
                margin: 0;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }

            /* 独立展示区样式 - 复用热点词汇统计区样式 */
            .standalone-section {
                margin-top: 32px;
                padding-top: 24px;
            }

            .standalone-section-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
            }

            .standalone-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #059669;
            }

            .standalone-section-count {
                color: var(--text-secondary);
                font-size: 14px;
            }

            .standalone-group {
                margin-bottom: 40px;
            }

            .standalone-group:last-child {
                margin-bottom: 0;
            }

            .standalone-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid var(--border-soft);
            }

            .standalone-name {
                font-size: 17px;
                font-weight: 600;
                color: var(--text-primary);
            }

            .standalone-count {
                color: var(--text-secondary);
                font-size: 13px;
                font-weight: 500;
            }

            /* AI 分析区块样式 */
            .ai-section {
                margin-top: 32px;
                padding: 24px;
                background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                border-radius: 12px;
                border: 1px solid #bae6fd;
            }

            .ai-section-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 20px;
            }

            .ai-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #0369a1;
            }

            .ai-section-badge {
                background: #0ea5e9;
                color: white;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            }

            .ai-block {
                margin-bottom: 16px;
                padding: 16px;
                background: var(--surface-elevated);
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                border: 1px solid var(--border-soft);
            }

            .ai-block:last-child {
                margin-bottom: 0;
            }

            .ai-block-title {
                font-size: 14px;
                font-weight: 600;
                color: #0369a1;
                margin-bottom: 8px;
            }

            .ai-block-content {
                font-size: 14px;
                line-height: 1.6;
                color: var(--text-secondary);
                white-space: pre-wrap;
            }

            .ai-error {
                padding: 16px;
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                color: #991b1b;
                font-size: 14px;
            }

            html[data-theme="dark"] .outline-panel {
                box-shadow: 0 10px 30px rgba(2, 6, 23, 0.28);
            }

            html[data-theme="dark"] .outline-action-btn:hover {
                background: #243244;
                border-color: #64748b;
            }

            html[data-theme="dark"] .outline-link:hover {
                background: rgba(96, 165, 250, 0.12);
                border-color: rgba(96, 165, 250, 0.35);
                color: #bfdbfe;
            }

            html[data-theme="dark"] .outline-link.active {
                background: rgba(59, 130, 246, 0.22);
                border-color: rgba(96, 165, 250, 0.45);
                color: #dbeafe;
            }

            html[data-theme="dark"] .keyword-tag {
                color: #bfdbfe;
                background: rgba(59, 130, 246, 0.16);
            }

            html[data-theme="dark"] .trend-info.flat {
                color: #cbd5e1;
                background: #334155;
            }

            html[data-theme="dark"] .rss-item {
                background: rgba(16, 185, 129, 0.12);
            }

            html[data-theme="dark"] .ai-section {
                background: linear-gradient(135deg, rgba(2, 132, 199, 0.2) 0%, rgba(14, 165, 233, 0.12) 100%);
                border-color: rgba(125, 211, 252, 0.28);
            }

            html[data-theme="dark"] .theme-switch-track {
                background: rgba(15, 23, 42, 0.45);
            }

            html[data-theme="dark"] .news-item:hover .news-number {
                background: rgba(96, 165, 250, 0.2);
                color: #bfdbfe;
            }

            html[data-theme="dark"] .news-number.copied {
                background: rgba(34, 197, 94, 0.22) !important;
                color: #bbf7d0 !important;
            }

            .ai-info {
                padding: 16px;
                background: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 8px;
                color: #0369a1;
                font-size: 14px;
            }

            /* ===== 浏览器增强样式（渐进增强，邮件客户端无影响） ===== */

            /* 宽屏模式 - 基础 */
            body.wide-mode .container { max-width: 1200px; }
            body.wide-mode .header-info { grid-template-columns: repeat(4, 1fr); }
            body.wide-mode .content { padding: 32px 40px; }

            /* 宽屏模式 - RSS feed-group 两列 */
            body.wide-mode .rss-feeds-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .feed-group { margin-bottom: 0; }

            /* 宽屏模式 - AI 分析区两列网格 */
            body.wide-mode .ai-section .ai-blocks-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }
            body.wide-mode .ai-block { margin-bottom: 0; }

            /* 宽屏模式 - 新增热点多列 */
            body.wide-mode .new-section .new-sources-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .new-source-group { margin-bottom: 0; }

            /* 宽屏模式 - 独立展示区多列 */
            body.wide-mode .standalone-section .standalone-groups-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .standalone-group { margin-bottom: 0; }

            /* Tab 栏 */
            .tab-bar {
                display: none;
                overflow-x: auto;
                white-space: nowrap;
                padding: 8px 0 12px 0;
                margin-bottom: 20px;
                border-bottom: 2px solid var(--border-default);
                -webkit-overflow-scrolling: touch;
                scrollbar-width: thin;
                position: sticky;
                top: 0;
                background: var(--surface-primary);
                z-index: 10;
                gap: 4px;
            }
            body.wide-mode .tab-bar { display: flex; }
            body.wide-mode .tab-bar.tab-hidden { display: none; }

            .tab-btn {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 8px 16px;
                border: none;
                background: var(--surface-muted);
                color: var(--text-secondary);
                border-radius: 8px 8px 0 0;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                white-space: nowrap;
                transition: all 0.2s ease;
                flex-shrink: 0;
            }
            .tab-btn:hover { background: var(--card-hover-bg); color: var(--text-primary); }
            .tab-btn.active { background: var(--accent); color: white; }
            .tab-count {
                font-size: 11px;
                background: rgba(0,0,0,0.1);
                padding: 1px 6px;
                border-radius: 10px;
            }
            .tab-btn.active .tab-count { background: rgba(255,255,255,0.3); }
            .tab-bar::-webkit-scrollbar { height: 4px; }
            .tab-bar::-webkit-scrollbar-track { background: var(--surface-muted); border-radius: 2px; }
            .tab-bar::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 2px; }

            /* 搜索栏 */
            .search-bar { display: none; padding: 0 0 16px 0; }
            .search-input {
                width: 100%;
                padding: 10px 16px;
                border: 1px solid var(--border-default);
                background: var(--surface-primary);
                color: var(--text-primary);
                border-radius: 8px;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s;
                box-sizing: border-box;
            }
            .search-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
            .search-input::placeholder { color: var(--text-soft); }

            /* 右下角悬浮工具栏 */
            .fab-bar {
                position: fixed;
                bottom: 24px;
                right: 24px;
                display: flex;
                flex-direction: column;
                gap: 8px;
                z-index: 100;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.3s, transform 0.3s;
                pointer-events: none;
            }
            .fab-bar.visible {
                opacity: 1;
                transform: translateY(0);
                pointer-events: auto;
            }
            .fab-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: var(--accent);
                color: white;
                border: none;
                cursor: pointer;
                font-size: 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                transition: transform 0.2s, background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
            }
            .fab-btn:hover { transform: scale(1.1); background: var(--link-hover); }

            /* 快捷键 tooltip */
            .fab-tooltip {
                position: absolute;
                bottom: 0;
                right: 52px;
                background: rgba(30, 30, 50, 0.92);
                backdrop-filter: blur(12px);
                color: white;
                border-radius: 10px;
                padding: 12px 16px;
                white-space: nowrap;
                font-size: 12px;
                line-height: 1.8;
                box-shadow: 0 8px 24px rgba(0,0,0,0.25);
                border: 1px solid rgba(255,255,255,0.1);
                opacity: 0;
                visibility: hidden;
                transform: translateY(6px);
                transition: all 0.2s ease;
                pointer-events: none;
            }
            .fab-btn:hover .fab-tooltip,
            .fab-btn.show-tip .fab-tooltip {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
                pointer-events: auto;
            }
            .fab-tooltip .tip-row {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                align-items: center;
            }
            .fab-tooltip .tip-key {
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
                padding: 1px 6px;
                font-family: monospace;
                font-size: 11px;
                margin-left: 8px;
            }

            /* 折叠/展开 */
            .collapse-icon {
                display: none;
                margin-right: 6px;
                font-size: 12px;
                color: #9ca3af;
                transition: transform 0.2s;
                user-select: none;
            }
            .word-header.collapsible { cursor: pointer; }
            .word-header.collapsible .collapse-icon { display: inline; }
            .word-header.collapsible:hover {
                background: var(--surface-secondary);
                border-radius: 6px;
                margin: 0 -8px 20px -8px;
                padding: 8px;
            }
            .word-group.collapsed .news-item { display: none; }
            .word-group.collapsed .collapse-icon { transform: rotate(-90deg); }

            /* Tab 切换动画 */
            body.wide-mode .word-group[data-tab-index] { animation: tabFadeIn 0.2s ease; }
            @keyframes tabFadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* 宽屏切换按钮 */
            .toggle-wide-btn {
                background: var(--toolbar-glass);
                border: 1px solid var(--toolbar-border);
                color: var(--toolbar-color);
                padding: 10px 14px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 15px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                line-height: 1;
                min-height: 38px;
            }
            .toggle-wide-btn:hover {
                background: var(--toolbar-hover);
                border-color: var(--toolbar-border);
                transform: translateY(-1px);
            }

            /* 暗色模式切换按钮 */
            .toggle-dark-btn {
                background: var(--toolbar-glass);
                border: 1px solid var(--toolbar-border);
                color: var(--toolbar-color);
                padding: 10px 14px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 15px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                line-height: 1;
                min-height: 38px;
            }
            .toggle-dark-btn:hover {
                background: var(--toolbar-hover);
                border-color: var(--toolbar-border);
                transform: translateY(-1px);
            }

            /* 快捷键面板已集成到 fab-tooltip */

            /* 阅读进度条 */
            .reading-progress {
                position: fixed;
                top: 0; left: 0;
                width: 0;
                height: 3px;
                background: linear-gradient(90deg, var(--accent), var(--link-hover));
                z-index: 9999;
                transition: width 0.1s linear;
            }

            /* 复制按钮样式已集成到 .news-number */



            /* 新上榜标记 */
            .badge-new {
                display: inline-block;
                background: linear-gradient(135deg, #f43f5e, #ec4899);
                color: white;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
                border-radius: 3px;
                margin-left: 6px;
                vertical-align: middle;
                letter-spacing: 0.5px;
            }
            html[data-theme="dark"] .badge-new {
                background: linear-gradient(135deg, #be185d, #9333ea);
            }
        </style>
    </head>
    <body>
        <div class="reading-progress"></div>
        <div class="container">
            <div class="header">
                <div class="header-watermark">TrendRadar</div>
                <div class="header-toolbar">
                    <div class="theme-controls" aria-label="主题设置">
                        <div class="theme-status" id="theme-status" role="status" aria-live="polite">跟随系统</div>
                        <label class="theme-switch" for="theme-toggle" title="切换浅色 / 深色">
                            <span class="theme-switch-label">浅</span>
                            <span class="theme-switch-track">
                                <input type="checkbox" id="theme-toggle" class="sr-only" aria-label="切换深色模式">
                                <span class="theme-switch-thumb"></span>
                            </span>
                            <span class="theme-switch-label">深</span>
                        </label>
                    </div>
                    <div class="save-buttons">
                    <button class="toggle-wide-btn" onclick="toggleWideMode()" title="切换宽屏/窄屏">⛶</button>
                    <div class="save-btn-group">
                        <button class="save-btn" onclick="saveAsImage()">导出</button>
                        <button class="save-dropdown-trigger">▾</button>
                        <div class="save-dropdown-menu">
                            <button class="save-dropdown-item" onclick="saveAsImage()"><svg class="dropdown-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="12" height="12" rx="2"/><circle cx="8" cy="7.5" r="2.5"/><path d="M12 4h.01"/></svg>整页截图</button>
                            <button class="save-dropdown-item" onclick="saveAsMultipleImages()"><svg class="dropdown-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="4" width="10" height="10" rx="1.5"/><path d="M5 4V2.5A1.5 1.5 0 016.5 1h7A1.5 1.5 0 0115 2.5v7a1.5 1.5 0 01-1.5 1.5H12"/></svg>分段截图</button>
                        </div>
                    </div>
                </div>
                <div class="header-title">热点新闻分析</div>
                <div class="header-info">
                    <div class="info-item">
                        <span class="info-label">报告类型</span>
                        <span class="info-value">"""

    # 处理报告类型显示（根据 mode 直接显示）
    if mode == "current":
        html += "当前榜单"
    elif mode == "incremental":
        html += "增量分析"
    else:
        html += "全天汇总"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">新闻总数</span>
                        <span class="info-value">"""

    html += f"{total_titles} 条"

    # 计算筛选后的热点新闻数量
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">热点新闻</span>
                        <span class="info-value">"""

    html += f"{hot_news_count} 条"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">生成时间</span>
                        <span class="info-value">"""

    # 使用提供的时间函数或默认 datetime.now
    if get_time_func:
        now = get_time_func()
    else:
        now = datetime.now()
    html += now.strftime("%m-%d %H:%M")

    html += """</span>
                    </div>
                </div>
            </div>

            <div class="content">
                <div class="search-bar">
                    <input type="text" class="search-input" placeholder="搜索新闻标题..." oninput="handleSearch(this.value)">
                </div>
                <div class="outline-panel" id="outline-panel">
                    <div class="outline-header">
                        <div class="outline-title">快速导航</div>
                        <div class="outline-actions">
                            <button type="button" class="outline-action-btn" id="collapse-all-btn">折叠词组</button>
                            <button type="button" class="outline-action-btn" id="expand-all-btn">展开词组</button>
                        </div>
                    </div>
                    <div class="outline-links" id="outline-links"></div>
                </div>"""

    # 处理失败ID错误信息
    if report_data["failed_ids"]:
        html += """
                <div class="error-section">
                    <div class="error-title">⚠️ 请求失败的平台</div>
                    <ul class="error-list">"""
        for id_value in report_data["failed_ids"]:
            html += f'<li class="error-item">{html_escape(id_value)}</li>'
        html += """
                    </ul>
                </div>"""

    def build_trend_info_html(rank_timeline: List[Dict[str, Any]], ranks: List[int]) -> str:
        """基于最近两次有效排名渲染趋势标签（↑上升 / ↓下降 / →持平）"""
        prev_rank: Optional[int] = None
        curr_rank: Optional[int] = None

        # 优先使用完整时间线，避免 ranks(去重列表)丢失方向信息
        valid_timeline_ranks: List[int] = []
        if rank_timeline:
            for point in rank_timeline:
                if not isinstance(point, dict):
                    continue
                rank = point.get("rank")
                if rank is None:
                    continue
                try:
                    valid_timeline_ranks.append(int(rank))
                except (TypeError, ValueError):
                    continue

        if len(valid_timeline_ranks) >= 2:
            prev_rank = valid_timeline_ranks[-2]
            curr_rank = valid_timeline_ranks[-1]
        elif len(ranks) >= 2:
            try:
                prev_rank = int(ranks[-2])
                curr_rank = int(ranks[-1])
            except (TypeError, ValueError):
                return ""
        else:
            return ""

        if prev_rank is None or curr_rank is None:
            return ""

        if curr_rank < prev_rank:
            trend_class = "up"
            trend_text = "↑上升"
        elif curr_rank > prev_rank:
            trend_class = "down"
            trend_text = "↓下降"
        else:
            trend_class = "flat"
            trend_text = "→持平"

        title = html_escape(f"上次 #{prev_rank} -> 本次 #{curr_rank}")
        return f'<span class="trend-info {trend_class}" title="{title}">{trend_text}</span>'

    # 生成热点词汇统计部分的HTML
    stats_html = ""
    tab_bar_html = ""
    if report_data["stats"]:
        total_count = len(report_data["stats"])

        # 生成 Tab 栏 HTML
        tab_bar_html = '<div class="tab-bar">'
        for tab_i, tab_stat in enumerate(report_data["stats"]):
            escaped_tab_word = html_escape(tab_stat["word"])
            tab_count = tab_stat["count"]
            tab_bar_html += f'<button class="tab-btn" data-tab-index="{tab_i}">{escaped_tab_word}<span class="tab-count">{tab_count}</span></button>'
        tab_bar_html += '<button class="tab-btn" data-tab-index="all">全部</button>'
        tab_bar_html += '</div>'

        for i, stat in enumerate(report_data["stats"], 1):
            count = stat["count"]

            # 确定热度等级
            if count >= 10:
                count_class = "hot"
            elif count >= 5:
                count_class = "warm"
            else:
                count_class = ""

            escaped_word = html_escape(stat["word"])

            stats_html += f"""
                <div class="word-group foldable-section" id="word-group-{i}" data-outline-title="{escaped_word}" data-outline-level="2" data-foldable="true" data-tab-index="{i - 1}">
                    <div class="word-header fold-header" data-fold-header role="button" tabindex="0" aria-expanded="true">
                        <div class="word-info">
                            <div class="word-name">{escaped_word}</div>
                            <div class="word-count {count_class}">{count} 条</div>
                        </div>
                        <div class="word-header-right">
                            <div class="word-index">{i}/{total_count}</div>
                            <span class="fold-toggle" aria-hidden="true">▾</span>
                        </div>
                    </div>
                    <div class="fold-body" data-fold-body>"""

            # 处理每个词组下的新闻标题，给每条新闻标上序号
            for j, title_data in enumerate(stat["titles"], 1):
                is_new = title_data.get("is_new", False)
                new_class = "new" if is_new else ""

                stats_html += f"""
                    <div class="news-item {new_class}">
                        <div class="news-number">{j}</div>
                        <div class="news-content">
                            <div class="news-header">"""

                # 根据 display_mode 决定显示来源还是关键词
                if display_mode == "keyword":
                    # keyword 模式：显示来源
                    stats_html += f'<span class="source-name">{html_escape(title_data["source_name"])}</span>'
                else:
                    # platform 模式：显示关键词
                    matched_keyword = title_data.get("matched_keyword", "")
                    if matched_keyword:
                        stats_html += f'<span class="keyword-tag">[{html_escape(matched_keyword)}]</span>'

                # 处理排名显示
                ranks = title_data.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_threshold = title_data.get("rank_threshold", 10)

                    # 确定排名等级
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= rank_threshold:
                        rank_class = "high"
                    else:
                        rank_class = ""

                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"

                    stats_html += f'<span class="rank-num {rank_class}">{rank_text}</span>'

                # 趋势显示（基于最近两次有效排名）
                rank_timeline = title_data.get("rank_timeline", [])
                trend_info_html = build_trend_info_html(rank_timeline, ranks)
                if trend_info_html:
                    stats_html += trend_info_html

                # 处理时间显示（可配置：observed/publish/publish_or_observed/hidden）
                resolved_time_display = resolve_hotlist_time_display(title_data)
                if resolved_time_display:
                    stats_html += (
                        f'<span class="time-info">{html_escape(resolved_time_display)}</span>'
                    )

                # 处理出现次数
                count_info = title_data.get("count", 1)
                if show_observation_count and count_info > 1:
                    stats_html += f'<span class="count-info">{count_info}次</span>'

                stats_html += """
                            </div>
                            <div class="news-title">"""

                # 处理标题和链接
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    stats_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    stats_html += escaped_title

                stats_html += """
                            </div>
                        </div>
                    </div>"""

            stats_html += """
                    </div>
                </div>"""

    # 给热榜统计添加外层包装
    if stats_html:
        stats_html = f"""
                <div class="hotlist-section" id="section-hotlist" data-outline-title="热点词汇" data-outline-level="1">{tab_bar_html}{stats_html}
                </div>"""

    # 生成新增新闻区域的HTML
    new_titles_html = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_html += f"""
                <div class="new-section" id="section-new-hotlist" data-outline-title="本次新增热点" data-outline-level="1">
                    <div class="new-section-title">本次新增热点 (共 {report_data['total_new_count']} 条)</div>
                    <div class="new-sources-grid">"""

        for source_data in report_data["new_titles"]:
            escaped_source = html_escape(source_data["source_name"])
            titles_count = len(source_data["titles"])

            new_titles_html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">{escaped_source} · {titles_count}条</div>"""

            # 为新增新闻也添加序号
            for idx, title_data in enumerate(source_data["titles"], 1):
                ranks = title_data.get("ranks", [])

                # 处理新增新闻的排名显示
                rank_class = ""
                if ranks:
                    min_rank = min(ranks)
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= title_data.get("rank_threshold", 10):
                        rank_class = "high"

                    if len(ranks) == 1:
                        rank_text = str(ranks[0])
                    else:
                        rank_text = f"{min(ranks)}-{max(ranks)}"
                else:
                    rank_text = "?"

                new_titles_html += f"""
                        <div class="new-item">
                            <div class="new-item-number">{idx}</div>
                            <div class="new-item-rank {rank_class}">{rank_text}</div>
                            <div class="new-item-content">
                                <div class="new-item-title">"""

                # 处理新增新闻的链接
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    new_titles_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    new_titles_html += escaped_title

                new_titles_html += """
                                </div>
                            </div>
                        </div>"""

            new_titles_html += """
                    </div>"""

        new_titles_html += """
                    </div>
                </div>"""

    # 生成 RSS 统计内容
    def render_rss_stats_html(
        stats: List[Dict],
        title: str = "RSS 订阅更新",
        section_id: str = "section-rss",
        outline_title: Optional[str] = None,
    ) -> str:
        """渲染 RSS 统计区块 HTML

        Args:
            stats: RSS 分组统计列表，格式与热榜一致：
                [
                    {
                        "word": "关键词",
                        "count": 5,
                        "titles": [
                            {
                                "title": "标题",
                                "source_name": "Feed 名称",
                                "time_display": "12-29 08:20",
                                "url": "...",
                                "is_new": True/False
                            }
                        ]
                    }
                ]
            title: 区块标题

        Returns:
            渲染后的 HTML 字符串
        """
        if not stats:
            return ""

        # 计算总条目数
        total_count = sum(stat.get("count", 0) for stat in stats)
        if total_count == 0:
            return ""

        escaped_outline_title = html_escape(outline_title or title)
        rss_html = f"""
                <div class="rss-section" id="{section_id}" data-outline-title="{escaped_outline_title}" data-outline-level="1">
                    <div class="rss-section-header">
                        <div class="rss-section-title">{title}</div>
                        <div class="rss-section-count">{total_count} 条</div>
                    </div>
                    <div class="rss-feeds-grid">"""

        # 按关键词分组渲染（与热榜格式一致）
        for stat in stats:
            keyword = stat.get("word", "")
            titles = stat.get("titles", [])
            if not titles:
                continue

            keyword_count = len(titles)

            rss_html += f"""
                    <div class="feed-group">
                        <div class="feed-header">
                            <div class="feed-name">{html_escape(keyword)}</div>
                            <div class="feed-count">{keyword_count} 条</div>
                        </div>"""

            for title_data in titles:
                item_title = title_data.get("title", "")
                url = title_data.get("url", "")
                time_display = title_data.get("time_display", "")
                source_name = title_data.get("source_name", "")
                is_new = title_data.get("is_new", False)

                rss_html += """
                        <div class="rss-item">
                            <div class="rss-meta">"""

                if time_display:
                    rss_html += f'<span class="rss-time">{html_escape(time_display)}</span>'

                if source_name:
                    rss_html += f'<span class="rss-author">{html_escape(source_name)}</span>'

                if is_new:
                    rss_html += '<span class="rss-author" style="color: #dc2626;">NEW</span>'

                rss_html += """
                            </div>
                            <div class="rss-title">"""

                escaped_title = html_escape(item_title)
                if url:
                    escaped_url = html_escape(url)
                    rss_html += f'<a href="{escaped_url}" target="_blank" class="rss-link">{escaped_title}</a>'
                else:
                    rss_html += escaped_title

                rss_html += """
                            </div>
                        </div>"""

            rss_html += """
                    </div>"""

        rss_html += """
                    </div>
                </div>"""
        return rss_html

    # 生成独立展示区内容
    def render_standalone_html(data: Optional[Dict]) -> str:
        """渲染独立展示区 HTML（复用热点词汇统计区样式）

        Args:
            data: 独立展示数据，格式：
                {
                    "platforms": [
                        {
                            "id": "zhihu",
                            "name": "知乎热榜",
                            "items": [
                                {
                                    "title": "标题",
                                    "url": "链接",
                                    "rank": 1,
                                    "ranks": [1, 2, 1],
                                    "first_time": "08:00",
                                    "last_time": "12:30",
                                    "count": 3,
                                }
                            ]
                        }
                    ],
                    "rss_feeds": [
                        {
                            "id": "hacker-news",
                            "name": "Hacker News",
                            "items": [
                                {
                                    "title": "标题",
                                    "url": "链接",
                                    "published_at": "2025-01-07T08:00:00",
                                    "author": "作者",
                                }
                            ]
                        }
                    ]
                }

        Returns:
            渲染后的 HTML 字符串
        """
        if not data:
            return ""

        platforms = data.get("platforms", [])
        rss_feeds = data.get("rss_feeds", [])

        if not platforms and not rss_feeds:
            return ""

        # 计算总条目数
        total_platform_items = sum(len(p.get("items", [])) for p in platforms)
        total_rss_items = sum(len(f.get("items", [])) for f in rss_feeds)
        total_count = total_platform_items + total_rss_items

        if total_count == 0:
            return ""

        # 收集所有分组信息用于生成 tab
        all_groups = []
        for p in platforms:
            items = p.get("items", [])
            if items:
                all_groups.append({"name": p.get("name", p.get("id", "")), "count": len(items)})
        for f in rss_feeds:
            items = f.get("items", [])
            if items:
                all_groups.append({"name": f.get("name", f.get("id", "")), "count": len(items)})

        standalone_html = f"""
                <div class="standalone-section" id="section-standalone" data-outline-title="独立展示区" data-outline-level="1">
                    <div class="standalone-section-header">
                        <div class="standalone-section-title">独立展示区</div>
                        <div class="standalone-section-count">{total_count} 条</div>
                    </div>"""

        # 生成 tab 栏（2+ 分组时）
        if len(all_groups) >= 2:
            standalone_html += """
                    <div class="tab-bar standalone-tab-bar">"""
            for idx, g in enumerate(all_groups):
                active = ' active' if idx == 0 else ''
                standalone_html += f"""
                        <button class="tab-btn{active}" data-standalone-tab="{idx}">{html_escape(g["name"])}<span class="tab-count">{g["count"]}</span></button>"""
            standalone_html += f"""
                        <button class="tab-btn" data-standalone-tab="all">全部<span class="tab-count">{total_count}</span></button>
                    </div>"""

        standalone_html += """
                    <div class="standalone-groups-grid">"""

        group_idx = 0
        # 渲染热榜平台（复用 word-group 结构）
        for platform in platforms:
            platform_name = platform.get("name", platform.get("id", ""))
            items = platform.get("items", [])
            if not items:
                continue

            standalone_html += f"""
                    <div class="standalone-group" data-standalone-tab="{group_idx}">
                        <div class="standalone-header">
                            <div class="standalone-name">{html_escape(platform_name)}</div>
                            <div class="standalone-count">{len(items)} 条</div>
                        </div>"""

            # 渲染每个条目（复用 news-item 结构）
            for j, item in enumerate(items, 1):
                title = item.get("title", "")
                url = item.get("url", "") or item.get("mobileUrl", "")
                rank = item.get("rank", 0)
                ranks = item.get("ranks", [])
                rank_timeline = item.get("rank_timeline", [])
                count = item.get("count", 1)

                standalone_html += f"""
                        <div class="news-item">
                            <div class="news-number">{j}</div>
                            <div class="news-content">
                                <div class="news-header">"""

                # 排名显示（复用 rank-num 样式，无 # 前缀）
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)

                    # 确定排名等级
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= 10:
                        rank_class = "high"
                    else:
                        rank_class = ""

                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"

                    standalone_html += f'<span class="rank-num {rank_class}">{rank_text}</span>'
                elif rank > 0:
                    if rank <= 3:
                        rank_class = "top"
                    elif rank <= 10:
                        rank_class = "high"
                    else:
                        rank_class = ""
                    standalone_html += f'<span class="rank-num {rank_class}">{rank}</span>'

                # 趋势显示（基于最近两次有效排名）
                trend_info_html = build_trend_info_html(rank_timeline, ranks)
                if trend_info_html:
                    standalone_html += trend_info_html

                # 时间显示（支持 publish / observed 配置）
                standalone_time_display = resolve_standalone_time_display(item)
                if standalone_time_display:
                    standalone_html += f'<span class="time-info">{html_escape(standalone_time_display)}</span>'

                # 出现次数（复用 count-info 样式）
                if show_observation_count and count > 1:
                    standalone_html += f'<span class="count-info">{count}次</span>'

                standalone_html += """
                                </div>
                                <div class="news-title">"""

                # 标题和链接（复用 news-link 样式）
                escaped_title = html_escape(title)
                if url:
                    escaped_url = html_escape(url)
                    standalone_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    standalone_html += escaped_title

                standalone_html += """
                                </div>
                            </div>
                        </div>"""

            standalone_html += """
                    </div>"""
            group_idx += 1

        # 渲染 RSS 源（复用相同结构）
        for feed in rss_feeds:
            feed_name = feed.get("name", feed.get("id", ""))
            items = feed.get("items", [])
            if not items:
                continue

            standalone_html += f"""
                    <div class="standalone-group" data-standalone-tab="{group_idx}">
                        <div class="standalone-header">
                            <div class="standalone-name">{html_escape(feed_name)}</div>
                            <div class="standalone-count">{len(items)} 条</div>
                        </div>"""

            for j, item in enumerate(items, 1):
                title = item.get("title", "")
                url = item.get("url", "")
                published_at = item.get("published_at", "")
                author = item.get("author", "")

                standalone_html += f"""
                        <div class="news-item">
                            <div class="news-number">{j}</div>
                            <div class="news-content">
                                <div class="news-header">"""

                # 时间显示（格式化 ISO 时间）
                if published_at:
                    try:
                        from datetime import datetime as dt
                        if "T" in published_at:
                            dt_obj = dt.fromisoformat(published_at.replace("Z", "+00:00"))
                            time_display = dt_obj.strftime("%m-%d %H:%M")
                        else:
                            time_display = published_at
                    except:
                        time_display = published_at

                    standalone_html += f'<span class="time-info">{html_escape(time_display)}</span>'

                # 作者显示
                if author:
                    standalone_html += f'<span class="source-name">{html_escape(author)}</span>'

                standalone_html += """
                                </div>
                                <div class="news-title">"""

                escaped_title = html_escape(title)
                if url:
                    escaped_url = html_escape(url)
                    standalone_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    standalone_html += escaped_title

                standalone_html += """
                                </div>
                            </div>
                        </div>"""

            standalone_html += """
                    </div>"""
            group_idx += 1

        standalone_html += """
                    </div>
                </div>"""
        return standalone_html

    # 生成 RSS 统计和新增 HTML
    rss_stats_html = (
        render_rss_stats_html(
            rss_items,
            "RSS 订阅更新",
            "section-rss-updates",
            "RSS 订阅更新",
        )
        if rss_items
        else ""
    )
    rss_new_html = (
        render_rss_stats_html(
            rss_new_items,
            "RSS 新增更新",
            "section-rss-new-updates",
            "RSS 新增更新",
        )
        if rss_new_items
        else ""
    )

    # 生成独立展示区 HTML
    standalone_html = render_standalone_html(standalone_data)

    # 生成 AI 分析 HTML
    ai_html = render_ai_analysis_html_rich(ai_analysis) if ai_analysis else ""
    if ai_html:
        ai_html = f"""
                <div class="ai-section-wrapper" id="section-ai-analysis" data-outline-title="AI 分析" data-outline-level="1">
                    {ai_html}
                </div>"""

    # 准备各区域内容映射
    region_contents = {
        "hotlist": stats_html,
        "rss": rss_stats_html,
        "new_items": (new_titles_html, rss_new_html),  # 元组，分别处理
        "standalone": standalone_html,
        "ai_analysis": ai_html,
    }

    def add_section_divider(content: str) -> str:
        """为内容的外层 div 添加 section-divider 类"""
        if not content or 'class="' not in content:
            return content
        first_class_pos = content.find('class="')
        if first_class_pos != -1:
            insert_pos = first_class_pos + len('class="')
            return content[:insert_pos] + "section-divider " + content[insert_pos:]
        return content

    # 按 region_order 顺序组装内容，动态添加分割线
    has_previous_content = False
    for region in region_order:
        content = region_contents.get(region, "")
        if region == "new_items":
            # 特殊处理 new_items 区域（包含热榜新增和 RSS 新增两部分）
            new_html, rss_new = content
            if new_html:
                if has_previous_content:
                    new_html = add_section_divider(new_html)
                html += new_html
                has_previous_content = True
            if rss_new:
                if has_previous_content:
                    rss_new = add_section_divider(rss_new)
                html += rss_new
                has_previous_content = True
        elif content:
            if has_previous_content:
                content = add_section_divider(content)
            html += content
            has_previous_content = True

    html += """
            </div>

            <div class="footer">
                <div class="footer-content">
                    由 <span class="project-name">TrendRadar</span> 生成 ·
                    <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">
                        GitHub 开源项目
                    </a>"""

    if update_info:
        html += f"""
                    <br>
                    <span style="color: #ea580c; font-weight: 500;">
                        发现新版本 {update_info['remote_version']}，当前版本 {update_info['current_version']}
                    </span>"""

    html += """
                </div>
            </div>
        </div>

        <div class="fab-bar">
            <button class="fab-btn" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="返回顶部">↑</button>
            <button class="fab-btn fab-help">
                <span>?</span>
                <div class="fab-tooltip">
                    <div class="tip-row"><span>切换宽屏</span><span class="tip-key">W</span></div>
                    <div class="tip-row"><span>暗色模式</span><span class="tip-key">D</span></div>
                    <div class="tip-row"><span>搜索</span><span class="tip-key">/</span></div>
                    <div class="tip-row"><span>上一个 Tab</span><span class="tip-key">←</span></div>
                    <div class="tip-row"><span>下一个 Tab</span><span class="tip-key">→</span></div>
                    <div class="tip-row"><span>序号可复制</span><span class="tip-key">点击</span></div>
                </div>
            </button>
        </div>

        <script>
            const DEFAULT_THEME_MODE = '""" + default_theme_mode + """';
            const THEME_STORAGE_KEY = 'trendradar_report_theme_mode';
            const systemThemeMedia = window.matchMedia('(prefers-color-scheme: dark)');
            let foldableSections = [];
            let outlineObserver = null;

            function getStoredThemeMode() {
                const savedMode = localStorage.getItem(THEME_STORAGE_KEY);
                return ['light', 'dark', 'system'].includes(savedMode) ? savedMode : DEFAULT_THEME_MODE;
            }

            function resolveEffectiveTheme(mode = getStoredThemeMode()) {
                if (mode === 'system') {
                    return systemThemeMedia.matches ? 'dark' : 'light';
                }
                return mode;
            }

            function updateThemeControls() {
                const themeMode = getStoredThemeMode();
                const effectiveTheme = resolveEffectiveTheme(themeMode);
                const themeToggle = document.getElementById('theme-toggle');
                const themeStatus = document.getElementById('theme-status');

                if (themeToggle) {
                    themeToggle.checked = effectiveTheme === 'dark';
                    const themeSwitch = themeToggle.closest('.theme-switch');
                    if (themeSwitch) {
                        themeSwitch.classList.remove('is-disabled');
                        themeSwitch.title = '切换浅色 / 深色';
                    }
                }

                if (themeStatus) {
                    themeStatus.textContent = `${themeMode === 'system' ? '跟随系统' : '手动'} · ${effectiveTheme === 'dark' ? '深色' : '浅色'}`;
                }
            }

            function applyTheme(mode, { persist = true } = {}) {
                const normalizedMode = ['light', 'dark', 'system'].includes(mode) ? mode : 'system';
                const effectiveTheme = resolveEffectiveTheme(normalizedMode);

                if (persist) {
                    localStorage.setItem(THEME_STORAGE_KEY, normalizedMode);
                }

                document.documentElement.dataset.themeMode = normalizedMode;
                document.documentElement.dataset.theme = effectiveTheme;
                document.documentElement.style.colorScheme = effectiveTheme;
                updateThemeControls();
            }

            function initThemeControls() {
                const themeToggle = document.getElementById('theme-toggle');

                if (themeToggle) {
                    themeToggle.addEventListener('change', event => {
                        applyTheme(event.target.checked ? 'dark' : 'light');
                    });
                }

                const handleSystemThemeChange = () => {
                    if (getStoredThemeMode() === 'system') {
                        applyTheme('system', { persist: false });
                    }
                };

                if (typeof systemThemeMedia.addEventListener === 'function') {
                    systemThemeMedia.addEventListener('change', handleSystemThemeChange);
                } else if (typeof systemThemeMedia.addListener === 'function') {
                    systemThemeMedia.addListener(handleSystemThemeChange);
                }

                applyTheme(getStoredThemeMode(), { persist: false });
            }

            function setSectionCollapsed(section, collapsed) {
                if (!section) return;
                const header = section.querySelector('[data-fold-header]');
                const body = section.querySelector('[data-fold-body]');
                if (!header || !body) return;
                const toggleIcon = header.querySelector('.fold-toggle');

                section.classList.toggle('is-collapsed', collapsed);
                header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                body.setAttribute('aria-hidden', collapsed ? 'true' : 'false');
                if (toggleIcon) {
                    toggleIcon.textContent = collapsed ? '▸' : '▾';
                }
            }

            function initFoldableSections() {
                foldableSections = Array.from(document.querySelectorAll('[data-foldable="true"]'))
                    .filter(section => section.querySelector('[data-fold-header]') && section.querySelector('[data-fold-body]'));

                foldableSections.forEach(section => {
                    const header = section.querySelector('[data-fold-header]');
                    const toggleFold = event => {
                        if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') {
                            return;
                        }
                        if (event.type === 'keydown') {
                            event.preventDefault();
                        }
                        const targetElement = event.target instanceof Element
                            ? event.target
                            : event.target && event.target.parentElement
                                ? event.target.parentElement
                                : null;
                        if (targetElement && targetElement.closest('a')) {
                            return;
                        }
                        setSectionCollapsed(section, !section.classList.contains('is-collapsed'));
                    };

                    header.addEventListener('click', toggleFold);
                    header.addEventListener('keydown', toggleFold);
                    setSectionCollapsed(section, section.dataset.foldDefault === 'collapsed');
                });
            }

            function setAllFoldState(collapsed) {
                foldableSections.forEach(section => setSectionCollapsed(section, collapsed));
            }

            function getFoldStateSnapshot() {
                return foldableSections.map(section => section.classList.contains('is-collapsed'));
            }

            function restoreFoldStateSnapshot(snapshot) {
                if (!Array.isArray(snapshot)) return;
                foldableSections.forEach((section, index) => {
                    if (index < snapshot.length) {
                        setSectionCollapsed(section, snapshot[index]);
                    }
                });
            }

            function setupOutlineActiveState(sections) {
                const links = Array.from(document.querySelectorAll('.outline-link'));
                const linksById = new Map(links.map(link => [link.dataset.targetId, link]));

                const setActive = targetId => {
                    links.forEach(link => {
                        link.classList.toggle('active', link.dataset.targetId === targetId);
                    });
                };

                if (!sections.length) return;
                setActive(sections[0].id);

                if (outlineObserver) {
                    outlineObserver.disconnect();
                }

                outlineObserver = new IntersectionObserver(entries => {
                    const visibleEntries = entries
                        .filter(entry => entry.isIntersecting)
                        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);

                    if (!visibleEntries.length) return;
                    const activeId = visibleEntries[0].target.id;
                    if (linksById.has(activeId)) {
                        setActive(activeId);
                    }
                }, {
                    root: null,
                    threshold: [0.2, 0.6],
                    rootMargin: '-80px 0px -60% 0px',
                });

                sections.forEach(section => outlineObserver.observe(section));
            }

            function buildOutline() {
                const outlinePanel = document.getElementById('outline-panel');
                const outlineLinks = document.getElementById('outline-links');
                if (!outlinePanel || !outlineLinks) return;

                const sections = Array.from(document.querySelectorAll('[data-outline-title][id]'));
                if (!sections.length) {
                    outlinePanel.style.display = 'none';
                    return;
                }

                outlineLinks.innerHTML = '';
                sections.forEach(section => {
                    const link = document.createElement('a');
                    const level = section.dataset.outlineLevel || '1';
                    link.href = `#${section.id}`;
                    link.className = `outline-link level-${level}`;
                    link.dataset.targetId = section.id;
                    link.textContent = section.dataset.outlineTitle || section.id;
                    link.addEventListener('click', event => {
                        event.preventDefault();
                        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    });
                    outlineLinks.appendChild(link);
                });

                setupOutlineActiveState(sections);
            }

            function updateOutlinePanelLayout() {
                const outlinePanel = document.getElementById('outline-panel');
                const container = document.querySelector('.container');
                if (!outlinePanel || !container) return;

                const containerRect = container.getBoundingClientRect();
                const gap = 16;
                const left = containerRect.right + gap;
                const availableWidth = window.innerWidth - left - 12;
                const shouldFloatSide = window.innerWidth >= 1120 && availableWidth >= 180;

                if (shouldFloatSide) {
                    outlinePanel.classList.add('is-floating-side');
                    outlinePanel.style.left = `${left}px`;
                    outlinePanel.style.width = `${Math.min(260, availableWidth)}px`;
                } else {
                    outlinePanel.classList.remove('is-floating-side');
                    outlinePanel.style.left = '';
                    outlinePanel.style.width = '';
                }
            }

            function bindOutlineActions() {
                const collapseBtn = document.getElementById('collapse-all-btn');
                const expandBtn = document.getElementById('expand-all-btn');
                const actions = document.querySelector('.outline-actions');
                const hasFoldableSections = foldableSections.length > 0;

                if (!hasFoldableSections && actions) {
                    actions.style.display = 'none';
                    return;
                }

                if (collapseBtn) {
                    collapseBtn.addEventListener('click', () => setAllFoldState(true));
                }
                if (expandBtn) {
                    expandBtn.addEventListener('click', () => setAllFoldState(false));
                }
            }
            // ===== 浏览器增强功能 =====

            function toggleWideMode() {
                document.body.classList.toggle('wide-mode');
                var isWide = document.body.classList.contains('wide-mode');
                try { localStorage.setItem('trendradar-wide-mode', isWide ? '1' : '0'); } catch(e) {}
                var btn = document.querySelector('.toggle-wide-btn');
                if (btn) btn.textContent = isWide ? '⊡' : '⛶';
                initTabVisibility();
                initCollapseVisibility();
                initStandaloneTabVisibility();
            }

            function toggleDarkMode() {
                applyTheme(resolveEffectiveTheme() === 'dark' ? 'light' : 'dark');
            }

            function initTabs() {
                var tabBar = document.querySelector('.tab-bar');
                if (!tabBar) return;
                var tabs = tabBar.querySelectorAll('.tab-btn');
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                initTabVisibility();

                function activateTab(index) {
                    tabs.forEach(function(t) { t.classList.remove('active'); });
                    if (index === 'all') {
                        var allBtn = tabBar.querySelector('[data-tab-index="all"]');
                        if (allBtn) allBtn.classList.add('active');
                        groups.forEach(function(g) { g.style.display = ''; });
                        try { history.replaceState(null, '', '#all'); } catch(e) {}
                        return;
                    }
                    var idx = parseInt(index);
                    tabs.forEach(function(t) {
                        if (parseInt(t.dataset.tabIndex) === idx) t.classList.add('active');
                    });
                    if (document.body.classList.contains('wide-mode') && !tabBar.classList.contains('tab-hidden')) {
                        groups.forEach(function(g) {
                            g.style.display = (parseInt(g.dataset.tabIndex) === idx) ? '' : 'none';
                        });
                    }
                    try { history.replaceState(null, '', '#tab-' + idx); } catch(e) {}
                }

                tabs.forEach(function(tab) {
                    tab.addEventListener('click', function() {
                        var idx = tab.dataset.tabIndex;
                        activateTab(idx === 'all' ? 'all' : parseInt(idx));
                    });
                });

                tabBar.addEventListener('keydown', function(e) {
                    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                        var tabsArr = Array.from(tabs);
                        var ci = tabsArr.findIndex(function(t) { return t.classList.contains('active'); });
                        var dir = e.key === 'ArrowRight' ? 1 : -1;
                        var ni = Math.max(0, Math.min(tabsArr.length - 1, ci + dir));
                        var nt = tabsArr[ni];
                        activateTab(nt.dataset.tabIndex === 'all' ? 'all' : parseInt(nt.dataset.tabIndex));
                        nt.focus();
                        e.preventDefault();
                    }
                });

                var hash = window.location.hash;
                if (hash === '#all') { activateTab('all'); }
                else if (hash.indexOf('#tab-') === 0) { activateTab(parseInt(hash.replace('#tab-', ''))); }
                else { activateTab(0); }
            }

            function initTabVisibility() {
                var tabBar = document.querySelector('.tab-bar');
                if (!tabBar) return;
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                var isWide = document.body.classList.contains('wide-mode');
                if (!isWide || groups.length <= 2) {
                    tabBar.classList.add('tab-hidden');
                    groups.forEach(function(g) { g.style.display = ''; });
                } else {
                    tabBar.classList.remove('tab-hidden');
                    var activeTab = tabBar.querySelector('.tab-btn.active');
                    if (activeTab) { activeTab.click(); }
                    else {
                        var firstTab = tabBar.querySelector('.tab-btn');
                        if (firstTab) firstTab.click();
                    }
                }
            }

            function handleSearch(query) {
                query = query.toLowerCase();
                document.querySelectorAll('.news-item').forEach(function(item) {
                    var title = (item.querySelector('.news-title') || {}).textContent || '';
                    item.style.display = (!query || title.toLowerCase().indexOf(query) !== -1) ? '' : 'none';
                });
                document.querySelectorAll('.rss-item').forEach(function(item) {
                    var title = (item.querySelector('.rss-title') || {}).textContent || '';
                    item.style.display = (!query || title.toLowerCase().indexOf(query) !== -1) ? '' : 'none';
                });
            }

            function initBackToTop() {
                var fabBar = document.querySelector('.fab-bar');
                if (!fabBar) return;
                window.addEventListener('scroll', function() {
                    fabBar.classList.toggle('visible', window.scrollY > 300);
                });
            }

            function initCollapse() {
                document.querySelectorAll('.word-header').forEach(function(header) {
                    header.addEventListener('click', function() {
                        var tabBar = document.querySelector('.tab-bar');
                        if (document.body.classList.contains('wide-mode') && tabBar && !tabBar.classList.contains('tab-hidden')) return;
                        var group = header.closest('.word-group');
                        if (group) group.classList.toggle('collapsed');
                    });
                });
                initCollapseVisibility();
            }

            function initCollapseVisibility() {
                var headers = document.querySelectorAll('.word-header');
                var tabBar = document.querySelector('.tab-bar');
                var isTabMode = document.body.classList.contains('wide-mode') && tabBar && !tabBar.classList.contains('tab-hidden');
                headers.forEach(function(h) {
                    if (isTabMode) { h.classList.remove('collapsible'); }
                    else { h.classList.add('collapsible'); }
                });
                if (isTabMode) {
                    document.querySelectorAll('.word-group.collapsed').forEach(function(g) {
                        g.classList.remove('collapsed');
                    });
                }
            }

            // 独立展示区 Tab 切换
            function initStandaloneTabs() {
                var tabBar = document.querySelector('.standalone-tab-bar');
                if (!tabBar) return;
                var groups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                var btns = tabBar.querySelectorAll('.tab-btn[data-standalone-tab]');

                function activateStandaloneTab(val) {
                    btns.forEach(function(b) {
                        var bVal = b.getAttribute('data-standalone-tab');
                        b.classList.toggle('active', bVal === String(val));
                    });
                    groups.forEach(function(g) {
                        var gVal = g.getAttribute('data-standalone-tab');
                        g.style.display = (val === 'all' || gVal === String(val)) ? '' : 'none';
                    });
                }

                btns.forEach(function(btn) {
                    btn.addEventListener('click', function() {
                        activateStandaloneTab(btn.getAttribute('data-standalone-tab'));
                    });
                });

                // 初始状态
                initStandaloneTabVisibility();
            }

            function initStandaloneTabVisibility() {
                var tabBar = document.querySelector('.standalone-tab-bar');
                if (!tabBar) return;
                var groups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                var isWide = document.body.classList.contains('wide-mode');
                if (!isWide || groups.length <= 1) {
                    tabBar.classList.add('tab-hidden');
                    groups.forEach(function(g) { g.style.display = ''; });
                } else {
                    tabBar.classList.remove('tab-hidden');
                    var activeBtn = tabBar.querySelector('.tab-btn.active');
                    if (activeBtn) activeBtn.click();
                    else { var first = tabBar.querySelector('.tab-btn'); if (first) first.click(); }
                }
            }

            function prepareForScreenshot() {
                var state = {
                    wasWide: document.body.classList.contains('wide-mode'),
                    hiddenGroups: []
                };
                document.body.classList.remove('wide-mode');
                document.querySelectorAll('.word-group[data-tab-index]').forEach(function(g, i) {
                    if (g.style.display === 'none') {
                        state.hiddenGroups.push(i);
                        g.style.display = '';
                    }
                });
                state.hiddenStandaloneGroups = [];
                document.querySelectorAll('.standalone-group[data-standalone-tab]').forEach(function(g, i) {
                    if (g.style.display === 'none') {
                        state.hiddenStandaloneGroups.push(i);
                        g.style.display = '';
                    }
                });
                document.querySelectorAll('.tab-bar, .standalone-tab-bar, .search-bar, .fab-bar, .toggle-wide-btn').forEach(function(el) {
                    el.dataset.prevDisplay = el.style.display || '';
                    el.style.display = 'none';
                });
                document.querySelectorAll('.toggle-dark-btn').forEach(function(el) {
                    el.dataset.prevDisplay = el.style.display || ''; el.style.display = 'none';
                });
                document.querySelectorAll('.reading-progress').forEach(function(el) { el.style.display = 'none'; });
                document.querySelectorAll('.header-watermark').forEach(function(el) { el.style.display = 'none'; });
                return state;
            }

            function restoreAfterScreenshot(state) {
                if (state.wasWide) document.body.classList.add('wide-mode');
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                state.hiddenGroups.forEach(function(i) {
                    if (groups[i]) groups[i].style.display = 'none';
                });
                var standaloneGroups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                if (state.hiddenStandaloneGroups) {
                    state.hiddenStandaloneGroups.forEach(function(i) {
                        if (standaloneGroups[i]) standaloneGroups[i].style.display = 'none';
                    });
                }
                document.querySelectorAll('.tab-bar, .standalone-tab-bar, .search-bar, .fab-bar, .toggle-wide-btn').forEach(function(el) {
                    el.style.display = el.dataset.prevDisplay || '';
                    delete el.dataset.prevDisplay;
                });
                document.querySelectorAll('.toggle-dark-btn').forEach(function(el) {
                    el.style.display = el.dataset.prevDisplay || ''; delete el.dataset.prevDisplay;
                });
                document.querySelectorAll('.reading-progress').forEach(function(el) { el.style.display = ''; });
                document.querySelectorAll('.reading-progress').forEach(function(el) { el.style.display = ''; });
                document.querySelectorAll('.header-watermark').forEach(function(el) { el.style.display = ''; });
                initTabVisibility();
                initCollapseVisibility();
                initStandaloneTabVisibility();
                var fabBar = document.querySelector('.fab-bar');
                if (fabBar && window.scrollY > 300) fabBar.classList.add('visible');
            }

            // ===== 截图功能 =====
            async function saveAsImage() {
                const button = event.target;
                const originalText = button.textContent;
                const foldStateSnapshot = getFoldStateSnapshot();
                setAllFoldState(false);

                try {
                    button.textContent = '生成中...';
                    button.disabled = true;
                    window.scrollTo(0, 0);

                    // 等待页面稳定
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // 截图前准备：切回窄屏布局
                    var screenshotState = prepareForScreenshot();

                    // 截图前隐藏按钮
                    const buttons = document.querySelector('.save-buttons');
                    const outlinePanel = document.querySelector('.outline-panel');
                    const headerToolbar = document.querySelector('.header-toolbar');
                    buttons.style.visibility = 'hidden';
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'hidden';
                    }
                    if (headerToolbar) {
                        headerToolbar.style.visibility = 'hidden';
                    }

                    // 再次等待确保按钮完全隐藏
                    await new Promise(resolve => setTimeout(resolve, 100));

                    const container = document.querySelector('.container');
                    const captureBackground = getComputedStyle(container).backgroundColor || '#ffffff';

                    const canvas = await html2canvas(container, {
                        backgroundColor: captureBackground,
                        scale: 1.5,
                        useCORS: true,
                        allowTaint: false,
                        imageTimeout: 10000,
                        removeContainer: false,
                        foreignObjectRendering: false,
                        logging: false,
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        x: 0,
                        y: 0,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: window.innerWidth,
                        windowHeight: window.innerHeight
                    });

                    buttons.style.visibility = 'visible';
                    restoreAfterScreenshot(screenshotState);
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'visible';
                    }
                    if (headerToolbar) {
                        headerToolbar.style.visibility = 'visible';
                    }

                    const link = document.createElement('a');
                    const now = new Date();
                    const filename = `TrendRadar_热点新闻分析_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}.png`;

                    link.download = filename;
                    link.href = canvas.toDataURL('image/png', 1.0);

                    // 触发下载
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    button.textContent = '保存成功!';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    restoreAfterScreenshot(screenshotState);
                    const outlinePanel = document.querySelector('.outline-panel');
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'visible';
                    }
                    button.textContent = '保存失败';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                } finally {
                    restoreFoldStateSnapshot(foldStateSnapshot);
                }
            }

            async function saveAsMultipleImages() {
                const button = event.target;
                const originalText = button.textContent;
                const container = document.querySelector('.container');
                const scale = 1.5;
                const maxHeight = 5000 / scale;
                const foldStateSnapshot = getFoldStateSnapshot();
                const headerToolbar = document.querySelector('.header-toolbar');
                const captureBackground = getComputedStyle(container).backgroundColor || '#ffffff';
                var screenshotState2 = prepareForScreenshot();
                setAllFoldState(false);

                try {
                    button.textContent = '分析中...';
                    button.disabled = true;

                    // 获取所有可能的分割元素
                    const newsItems = Array.from(container.querySelectorAll('.news-item'));
                    const wordGroups = Array.from(container.querySelectorAll('.word-group'));
                    const newSection = container.querySelector('.new-section');
                    const errorSection = container.querySelector('.error-section');
                    const header = container.querySelector('.header');
                    const footer = container.querySelector('.footer');

                    // 计算元素位置和高度
                    const containerRect = container.getBoundingClientRect();
                    const elements = [];

                    // 添加header作为必须包含的元素
                    elements.push({
                        type: 'header',
                        element: header,
                        top: 0,
                        bottom: header.offsetHeight,
                        height: header.offsetHeight
                    });

                    // 添加错误信息（如果存在）
                    if (errorSection) {
                        const rect = errorSection.getBoundingClientRect();
                        elements.push({
                            type: 'error',
                            element: errorSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    // 按word-group分组处理news-item
                    wordGroups.forEach(group => {
                        const groupRect = group.getBoundingClientRect();
                        const groupNewsItems = group.querySelectorAll('.news-item');

                        // 添加word-group的header部分
                        const wordHeader = group.querySelector('.word-header');
                        if (wordHeader) {
                            const headerRect = wordHeader.getBoundingClientRect();
                            elements.push({
                                type: 'word-header',
                                element: wordHeader,
                                parent: group,
                                top: groupRect.top - containerRect.top,
                                bottom: headerRect.bottom - containerRect.top,
                                height: headerRect.height
                            });
                        }

                        // 添加每个news-item
                        groupNewsItems.forEach(item => {
                            const rect = item.getBoundingClientRect();
                            elements.push({
                                type: 'news-item',
                                element: item,
                                parent: group,
                                top: rect.top - containerRect.top,
                                bottom: rect.bottom - containerRect.top,
                                height: rect.height
                            });
                        });
                    });

                    // 添加新增新闻部分
                    if (newSection) {
                        const rect = newSection.getBoundingClientRect();
                        elements.push({
                            type: 'new-section',
                            element: newSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    // 添加footer
                    const footerRect = footer.getBoundingClientRect();
                    elements.push({
                        type: 'footer',
                        element: footer,
                        top: footerRect.top - containerRect.top,
                        bottom: footerRect.bottom - containerRect.top,
                        height: footer.offsetHeight
                    });

                    // 计算分割点
                    const segments = [];
                    let currentSegment = { start: 0, end: 0, height: 0, includeHeader: true };
                    let headerHeight = header.offsetHeight;
                    currentSegment.height = headerHeight;

                    for (let i = 1; i < elements.length; i++) {
                        const element = elements[i];
                        const potentialHeight = element.bottom - currentSegment.start;

                        // 检查是否需要创建新分段
                        if (potentialHeight > maxHeight && currentSegment.height > headerHeight) {
                            // 在前一个元素结束处分割
                            currentSegment.end = elements[i - 1].bottom;
                            segments.push(currentSegment);

                            // 开始新分段
                            currentSegment = {
                                start: currentSegment.end,
                                end: 0,
                                height: element.bottom - currentSegment.end,
                                includeHeader: false
                            };
                        } else {
                            currentSegment.height = potentialHeight;
                            currentSegment.end = element.bottom;
                        }
                    }

                    // 添加最后一个分段
                    if (currentSegment.height > 0) {
                        currentSegment.end = container.offsetHeight;
                        segments.push(currentSegment);
                    }

                    button.textContent = `生成中 (0/${segments.length})...`;

                    // 隐藏保存按钮
                    const buttons = document.querySelector('.save-buttons');
                    const outlinePanel = document.querySelector('.outline-panel');
                    buttons.style.visibility = 'hidden';
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'hidden';
                    }
                    if (headerToolbar) {
                        headerToolbar.style.visibility = 'hidden';
                    }

                    // 为每个分段生成图片
                    const images = [];
                    for (let i = 0; i < segments.length; i++) {
                        const segment = segments[i];
                        button.textContent = `生成中 (${i + 1}/${segments.length})...`;

                        // 创建临时容器用于截图
                        const tempContainer = document.createElement('div');
                        tempContainer.style.cssText = `
                            position: absolute;
                            left: -9999px;
                            top: 0;
                            width: ${container.offsetWidth}px;
                            background: ${captureBackground};
                        `;
                        tempContainer.className = 'container';

                        // 克隆容器内容
                        const clonedContainer = container.cloneNode(true);

                        // 移除克隆内容中的工具栏
                        const clonedToolbar = clonedContainer.querySelector('.header-toolbar');
                        if (clonedToolbar) {
                            clonedToolbar.style.display = 'none';
                        }
                        const clonedOutline = clonedContainer.querySelector('.outline-panel');
                        if (clonedOutline) {
                            clonedOutline.style.display = 'none';
                        }

                        tempContainer.appendChild(clonedContainer);
                        document.body.appendChild(tempContainer);

                        // 等待DOM更新
                        await new Promise(resolve => setTimeout(resolve, 100));

                        // 使用html2canvas截取特定区域
                        const canvas = await html2canvas(clonedContainer, {
                            backgroundColor: captureBackground,
                            scale: scale,
                            useCORS: true,
                            allowTaint: false,
                            imageTimeout: 10000,
                            logging: false,
                            width: container.offsetWidth,
                            height: segment.end - segment.start,
                            x: 0,
                            y: segment.start,
                            windowWidth: window.innerWidth,
                            windowHeight: window.innerHeight
                        });

                        images.push(canvas.toDataURL('image/png', 1.0));

                        // 清理临时容器
                        document.body.removeChild(tempContainer);
                    }

                    // 恢复按钮显示
                    buttons.style.visibility = 'visible';
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'visible';
                    }
                    if (headerToolbar) {
                        headerToolbar.style.visibility = 'visible';
                    }

                    // 下载所有图片
                    const now = new Date();
                    const baseFilename = `TrendRadar_热点新闻分析_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;

                    for (let i = 0; i < images.length; i++) {
                        const link = document.createElement('a');
                        link.download = `${baseFilename}_part${i + 1}.png`;
                        link.href = images[i];
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        // 延迟一下避免浏览器阻止多个下载
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }

                    button.textContent = `已保存 ${segments.length} 张图片!`;
                    restoreAfterScreenshot(screenshotState2);
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    console.error('分段保存失败:', error);
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    restoreAfterScreenshot(screenshotState2);
                    const headerToolbar = document.querySelector('.header-toolbar');
                    if (headerToolbar) {
                        headerToolbar.style.visibility = 'visible';
                    }
                    const outlinePanel = document.querySelector('.outline-panel');
                    if (outlinePanel) {
                        outlinePanel.style.visibility = 'visible';
                    }
                    button.textContent = '保存失败';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                } finally {
                    restoreFoldStateSnapshot(foldStateSnapshot);
                }
            }

            document.addEventListener('DOMContentLoaded', function() {
                window.scrollTo(0, 0);
                initThemeControls();
                initFoldableSections();

                // 自动检测宽屏模式
                var savedMode = null;
                try { savedMode = localStorage.getItem('trendradar-wide-mode'); } catch(e) {}
                if (savedMode === '1' || (savedMode === null && window.innerWidth > 768)) {
                    document.body.classList.add('wide-mode');
                    var btn = document.querySelector('.toggle-wide-btn');
                    if (btn) btn.textContent = '⊡';
                }

                // 启用搜索栏
                var searchBar = document.querySelector('.search-bar');
                if (searchBar) searchBar.style.display = 'block';

                // 初始化增强功能
                initTabs();
                initBackToTop();
                initStandaloneTabs();
                buildOutline();
                bindOutlineActions();
                updateOutlinePanelLayout();
                window.addEventListener('resize', updateOutlinePanelLayout);

                // 键盘快捷键
                document.addEventListener('keydown', function(e) {
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                    var helpBtn = document.querySelector('.fab-help');
                    switch(e.key) {
                        case '?':
                            if (helpBtn) {
                                helpBtn.classList.toggle('show-tip');
                                var fabBar = document.querySelector('.fab-bar');
                                if (fabBar) fabBar.classList.add('visible');
                            }
                            break;
                        case 'Escape':
                            if (helpBtn) helpBtn.classList.remove('show-tip');
                            break;
                        case 'w': case 'W': toggleWideMode(); break;
                        case 'd': case 'D': toggleDarkMode(); break;
                        case '/': e.preventDefault(); var si = document.querySelector('.search-input'); if (si) si.focus(); break;
                    }
                });

                // 阅读进度条
                var progressBar = document.querySelector('.reading-progress');
                if (progressBar) {
                    window.addEventListener('scroll', function() {
                        var h = document.documentElement.scrollHeight - window.innerHeight;
                        progressBar.style.width = (h > 0 ? (window.scrollY / h * 100) : 0) + '%';
                    });
                }

                // 一键复制：hover 时数字变复制图标
                var copySvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M5 11H3.5A1.5 1.5 0 012 9.5v-7A1.5 1.5 0 013.5 1h7A1.5 1.5 0 0112 2.5V5"/></svg>';
                var checkSvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="#22c55e" stroke-width="2"><path d="M3 8.5l3.5 3.5 7-7"/></svg>';
                document.querySelectorAll('.news-item .news-number').forEach(function(numEl) {
                    var item = numEl.closest('.news-item');
                    var titleEl = item ? item.querySelector('.news-title a') : null;
                    if (!titleEl) return;
                    var numText = numEl.textContent.trim();
                    numEl.innerHTML = '<span class="num-text">' + numText + '</span><span class="copy-icon">' + copySvg + '</span>';
                    numEl.title = '点击复制标题和链接';
                    numEl.addEventListener('click', function(e) {
                        e.stopPropagation();
                        var text = titleEl.textContent.trim() + ' ' + titleEl.href;
                        navigator.clipboard.writeText(text).then(function() {
                            numEl.classList.add('copied');
                            numEl.querySelector('.copy-icon').innerHTML = checkSvg;
                            setTimeout(function() {
                                numEl.classList.remove('copied');
                                numEl.querySelector('.copy-icon').innerHTML = copySvg;
                            }, 1500);
                        });
                    });
                });



                // Header watermark 鼠标跟随揭示
                (function() {
                    var header = document.querySelector('.header');
                    var watermark = document.querySelector('.header-watermark');
                    if (!header || !watermark) return;

                    var radius = 100;

                    header.addEventListener('mousemove', function(e) {
                        var rect = watermark.getBoundingClientRect();
                        var x = e.clientX - rect.left;
                        var y = e.clientY - rect.top;
                        var maskVal = 'radial-gradient(circle ' + radius + 'px at ' + x + 'px ' + y + 'px, rgba(0,0,0,1) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0) 100%)';
                        watermark.style.webkitMaskImage = maskVal;
                        watermark.style.maskImage = maskVal;
                        watermark.style.color = 'rgba(255, 255, 255, 0.25)';
                    });

                    header.addEventListener('mouseleave', function() {
                        watermark.style.webkitMaskImage = 'radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)';
                        watermark.style.maskImage = 'radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)';
                        watermark.style.color = 'rgba(255, 255, 255, 0.15)';
                    });
                })();
            });
        </script>
    </body>
    </html>
    """

    return html
