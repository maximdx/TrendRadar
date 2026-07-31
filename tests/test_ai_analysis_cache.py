import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from trendradar.__main__ import NewsAnalyzer
from trendradar.ai.analyzer import AIAnalysisResult
from trendradar.core.scheduler import ResolvedSchedule
from trendradar.report.html import render_html_content
from trendradar.storage.local import LocalStorageBackend


class FakeScheduler:
    def __init__(self, executed=False, payload=None):
        self.executed = executed
        self.payload = payload
        self.record_calls = []

    def already_executed(self, period_key, action, date_str):
        return self.executed

    def get_execution_payload(self, period_key, action, date_str):
        return self.payload

    def record_execution(self, period_key, action, date_str, payload=None):
        self.executed = True
        self.payload = payload
        self.record_calls.append((period_key, action, date_str, payload))


class FakeContext:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.config = {
            "AI_ANALYSIS": {
                "ENABLED": True,
                "MODE": "follow_report",
            },
            "AI": {"MODEL": "deepseek/deepseek-v4-flash"},
            "DEBUG": False,
        }

    def create_scheduler(self):
        return self.scheduler

    def format_date(self):
        return "2026-07-26"

    @staticmethod
    def get_time():
        return datetime(2026, 7, 26, 21, 0, 0)


def make_analyzer(scheduler):
    analyzer = object.__new__(NewsAnalyzer)
    analyzer.ctx = FakeContext(scheduler)
    return analyzer


def make_schedule():
    return ResolvedSchedule(
        period_key="evening_summary",
        period_name="晚间汇总",
        day_plan="all_day",
        collect=True,
        analyze=True,
        push=True,
        report_mode="daily",
        ai_mode="daily",
        once_analyze=True,
        once_push=True,
    )


class AIAnalysisCacheTest(unittest.TestCase):
    def test_successful_analysis_is_reused_without_calling_ai_again(self):
        scheduler = FakeScheduler()
        analyzer = make_analyzer(scheduler)
        expected = AIAnalysisResult(
            core_trends="缓存中的 AI 总结",
            success=True,
            analyzed_news=12,
            standalone_summaries={"zhihu": "知乎摘要"},
        )

        with patch("trendradar.__main__.AIAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.return_value = expected
            first = analyzer._run_ai_analysis(
                stats=[{"word": "AI", "count": 1, "titles": []}],
                rss_items=[],
                mode="daily",
                report_type="当日汇总",
                id_to_name={"zhihu": "知乎"},
                schedule=make_schedule(),
            )
            second = analyzer._run_ai_analysis(
                stats=[{"word": "AI", "count": 1, "titles": []}],
                rss_items=[],
                mode="daily",
                report_type="当日汇总",
                id_to_name={"zhihu": "知乎"},
                schedule=make_schedule(),
            )

        self.assertEqual(analyzer_class.call_count, 1)
        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(second.core_trends, "缓存中的 AI 总结")
        self.assertEqual(second.standalone_summaries, {"zhihu": "知乎摘要"})
        self.assertEqual(len(scheduler.record_calls), 1)

        html = render_html_content(
            report_data={"stats": [], "new_titles": [], "failed_ids": []},
            total_titles=0,
            ai_analysis=second,
        )
        self.assertIn('id="section-ai-analysis"', html)
        self.assertIn("缓存中的 AI 总结", html)

    def test_legacy_execution_without_payload_self_heals(self):
        scheduler = FakeScheduler(executed=True, payload=None)
        analyzer = make_analyzer(scheduler)
        expected = AIAnalysisResult(core_trends="重新生成", success=True)

        with patch("trendradar.__main__.AIAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.return_value = expected
            result = analyzer._run_ai_analysis(
                stats=[{"word": "AI", "count": 1, "titles": []}],
                rss_items=[],
                mode="daily",
                report_type="当日汇总",
                id_to_name={"zhihu": "知乎"},
                schedule=make_schedule(),
            )

        self.assertEqual(analyzer_class.call_count, 1)
        self.assertTrue(result.success)
        self.assertEqual(scheduler.payload["core_trends"], "重新生成")

    def test_invalid_cached_payload_self_heals(self):
        scheduler = FakeScheduler(
            executed=True,
            payload={"success": True, "standalone_summaries": None},
        )
        analyzer = make_analyzer(scheduler)
        expected = AIAnalysisResult(core_trends="修复损坏缓存", success=True)

        with patch("trendradar.__main__.AIAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.return_value = expected
            result = analyzer._run_ai_analysis(
                stats=[{"word": "AI", "count": 1, "titles": []}],
                rss_items=[],
                mode="daily",
                report_type="当日汇总",
                id_to_name={"zhihu": "知乎"},
                schedule=make_schedule(),
            )

        self.assertEqual(analyzer_class.call_count, 1)
        self.assertEqual(result.core_trends, "修复损坏缓存")
        self.assertEqual(scheduler.payload["standalone_summaries"], {})

    def test_model_change_reanalyzes_and_replaces_cache(self):
        cached = AIAnalysisResult(
            core_trends="Pro 总结",
            success=True,
            model="deepseek/deepseek-v4-pro",
        )
        scheduler = FakeScheduler(executed=True, payload=cached.to_dict())
        analyzer = make_analyzer(scheduler)
        expected = AIAnalysisResult(core_trends="Flash 总结", success=True)

        with patch("trendradar.__main__.AIAnalyzer") as analyzer_class:
            analyzer_class.return_value.analyze.return_value = expected
            result = analyzer._run_ai_analysis(
                stats=[{"word": "AI", "count": 1, "titles": []}],
                rss_items=[],
                mode="daily",
                report_type="当日汇总",
                id_to_name={"zhihu": "知乎"},
                schedule=make_schedule(),
            )

        self.assertEqual(analyzer_class.call_count, 1)
        self.assertEqual(result.core_trends, "Flash 总结")
        self.assertEqual(result.model, "deepseek/deepseek-v4-flash")
        self.assertEqual(
            scheduler.payload["model"], "deepseek/deepseek-v4-flash"
        )

    def test_result_round_trip_ignores_unknown_fields(self):
        original = AIAnalysisResult(
            core_trends="趋势",
            success=True,
            include_rss=False,
            standalone_summaries={"v2ex": "摘要"},
        )
        payload = original.to_dict()
        payload["future_field"] = "ignored"

        restored = AIAnalysisResult.from_dict(payload)

        self.assertEqual(restored.core_trends, "趋势")
        self.assertFalse(restored.include_rss)
        self.assertEqual(restored.standalone_summaries, {"v2ex": "摘要"})

    def test_legacy_database_migrates_and_preserves_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            news_dir = Path(temp_dir) / "news"
            news_dir.mkdir()
            db_path = news_dir / "2026-07-26.db"
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE period_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_date TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(execution_date, period_key, action)
                )
            """)
            conn.execute("""
                INSERT INTO period_executions
                    (execution_date, period_key, action)
                VALUES ('2026-07-26', 'evening_summary', 'analyze')
            """)
            conn.commit()
            conn.close()

            backend = LocalStorageBackend(data_dir=temp_dir)
            self.assertIsNone(
                backend.get_period_execution_payload(
                    "2026-07-26", "evening_summary", "analyze"
                )
            )

            payload = {"success": True, "core_trends": "已缓存"}
            self.assertTrue(
                backend.record_period_execution(
                    "2026-07-26", "evening_summary", "analyze", payload
                )
            )
            backend.record_period_execution(
                "2026-07-26", "evening_summary", "analyze"
            )

            self.assertEqual(
                backend.get_period_execution_payload(
                    "2026-07-26", "evening_summary", "analyze"
                ),
                payload,
            )
            backend.cleanup()


if __name__ == "__main__":
    unittest.main()
