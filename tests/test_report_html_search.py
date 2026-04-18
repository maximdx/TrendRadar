import sys
import types
import unittest

litellm_stub = types.ModuleType("litellm")
litellm_stub.completion = lambda *args, **kwargs: None
sys.modules.setdefault("litellm", litellm_stub)

from trendradar.report.html import render_html_content


class ReportHtmlSearchTest(unittest.TestCase):
    def test_search_placeholder_mentions_source(self):
        html = render_html_content(
            report_data={"stats": [], "new_titles": [], "failed_ids": []},
            total_titles=0,
        )
        self.assertIn('placeholder="搜索新闻标题或来源..."', html)

    def test_news_items_embed_source_for_search(self):
        html = render_html_content(
            report_data={
                "stats": [
                    {
                        "word": "国际",
                        "count": 1,
                        "titles": [
                            {
                                "title": "标题里没有目标来源",
                                "source_name": "澎湃新闻",
                                "url": "https://example.com/news/1",
                                "ranks": [5],
                            }
                        ],
                    }
                ],
                "new_titles": [],
                "failed_ids": [],
            },
            total_titles=1,
        )
        self.assertIn('data-search-source="澎湃新闻"', html)
        self.assertIn("var haystack = (title + ' ' + source).toLowerCase();", html)


if __name__ == "__main__":
    unittest.main()
