"""Tests for the crawl's safety limit, source selection, and save-failure handling.

These exercise the spider/pipeline objects directly rather than through scrapy's
crawler, so they stay network-free.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import jsonlines
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_DIR = REPO_ROOT / "35_crawl_referenced_types"
sys.path.insert(0, str(PHASE_DIR))
sys.path.insert(0, str(REPO_ROOT))


def _load(name, rel):
    """Load by path: every crawl phase ships a package named solidworks_scraper,
    so a plain import resolves to whichever phase reached sys.path first."""
    spec = importlib.util.spec_from_file_location(name, PHASE_DIR / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spider_mod = _load(
    "phase35_spider", "solidworks_scraper/spiders/referenced_types_spider.py"
)
pipelines = _load("phase35_pipelines2", "solidworks_scraper/pipelines.py")

from shared.api_urls import build_exclusion_keys, build_saved_page_keys  # noqa: E402

SEED = "https://help.solidworks.com/2026/english/api/sldworksapi/A~B.C.html"


class TestCorpusPhases:
    def test_first_pass_ignores_phases_that_have_not_rerun_yet(self):
        """70/100/115 run *after* this phase, so on a repeat refresh they still
        hold the previous cycle's HTML -- seeding from it resurrects types the
        current corpus no longer links to."""
        early = spider_mod.corpus_phases(include_late=False)
        assert "70_crawl_examples" not in early
        assert "100_crawl_programming_guide" not in early
        assert "115_crawl_referenced_pages" not in early
        assert "10_crawl_toc_pages" in early
        assert "30_crawl_type_members" in early
        # Its own log, so --resume does not re-crawl.
        assert "35_crawl_referenced_types" in early

    def test_second_pass_adds_them(self):
        late = spider_mod.corpus_phases(include_late=True)
        assert set(spider_mod.corpus_phases(include_late=False)) < set(late)
        assert "70_crawl_examples" in late
        assert "115_crawl_referenced_pages" in late


class TestScheduleLimit:
    """MAX_PAGES has to bind where requests are created; checking it only before
    expanding a response cannot stop seeds, which are all queued up front."""

    @pytest.fixture
    def spider(self):
        # `logger` is a read-only property on scrapy.Spider, so subclass to stub it.
        class Stub(spider_mod.ReferencedTypesSpider):
            MAX_PAGES = 3

            def __init__(self):
                self.scheduled = 0
                self.limit_hit = False
                self.stats = {"unscheduled_pages": 0}
                self.warnings: list[str] = []

            @property
            def logger(self):
                return SimpleNamespace(warning=self.warnings.append)

        return Stub()

    def test_schedules_up_to_the_limit(self, spider):
        assert all(spider.schedule(SEED) is not None for _ in range(3))
        assert spider.scheduled == 3

    def test_refuses_past_the_limit_and_counts_the_refusals(self, spider):
        for _ in range(3):
            spider.schedule(SEED)
        assert spider.schedule(SEED) is None
        assert spider.schedule(SEED) is None
        assert spider.scheduled == 3
        assert spider.stats["unscheduled_pages"] == 2

    def test_the_limit_is_reported_once_not_per_refusal(self, spider):
        for _ in range(10):
            spider.schedule(SEED)
        assert len(spider.warnings) == 1


class TestSaveFailure:
    def test_an_unwritable_page_is_dropped_and_counted(self, tmp_path, monkeypatch):
        """Otherwise MetadataLogPipeline (400, after this one at 300) records the
        URL with no file behind it -- missing from extraction and skipped by the
        next --resume as already crawled."""
        pipe = pipelines.HtmlSavePipeline()
        monkeypatch.setattr(pipe, "output_dir", tmp_path / "output" / "html")
        monkeypatch.setattr(pipe, "url_to_file_path", lambda url: tmp_path / "output" / "html" / "p.html")

        def explode(*args, **kwargs):
            raise OSError("No space left on device")

        monkeypatch.setattr("builtins.open", explode)
        spider = SimpleNamespace(
            logger=SimpleNamespace(error=lambda *a, **k: None, debug=lambda *a, **k: None),
            stats={"failed_pages": 0},
        )
        with pytest.raises(pipelines.DropItem):
            pipe.process_item({"url": SEED, "content": "<html/>"}, spider)
        assert spider.stats["failed_pages"] == 1

    def test_a_writable_page_passes_through(self, tmp_path, monkeypatch):
        pipe = pipelines.HtmlSavePipeline()
        monkeypatch.setattr(pipe, "output_dir", tmp_path / "output" / "html")
        monkeypatch.setattr(pipe, "url_to_file_path", lambda url: tmp_path / "output" / "html" / "p.html")
        spider = SimpleNamespace(
            logger=SimpleNamespace(error=lambda *a, **k: None, debug=lambda *a, **k: None),
            stats={"failed_pages": 0},
        )
        item = pipe.process_item({"url": SEED, "content": "<html/>"}, spider)
        assert item["file_path"]
        assert spider.stats["failed_pages"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


class TestSelfExclusion:
    """metadata/ is committed but output/ is gitignored, so a recorded page whose
    HTML is absent must not be treated as already crawled."""

    def _write(self, phase_dir, rows):
        (phase_dir / "metadata").mkdir(parents=True, exist_ok=True)
        meta = phase_dir / "metadata" / "urls_crawled.jsonl"
        with jsonlines.open(meta, mode="w") as w:
            for r in rows:
                w.write(r)
        return meta

    def test_a_recorded_page_with_no_file_is_not_excluded(self, tmp_path):
        rows = [
            {"url": f"{SEED}", "file_path": "output/html/present.html"},
            {
                "url": "https://help.solidworks.com/2026/english/api/sldworksapi/X~Y.Z.html",
                "file_path": "output/html/vanished.html",
            },
        ]
        meta = self._write(tmp_path, rows)
        (tmp_path / "output" / "html").mkdir(parents=True)
        (tmp_path / "output" / "html" / "present.html").write_text("<html/>")

        kept = build_saved_page_keys(tmp_path, meta)
        every = build_exclusion_keys([meta])

        assert len(every) == 2, "manifest-only view excludes both"
        assert len(kept) == 1, "the page whose HTML vanished stays crawlable"
        assert kept < every
