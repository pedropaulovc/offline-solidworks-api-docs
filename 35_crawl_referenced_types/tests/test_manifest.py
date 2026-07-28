"""The crawl manifest is the reproducibility/compliance record for a run, so it
has to describe the policy the crawl actually used rather than a restated ideal."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from scrapy.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_DIR = REPO_ROOT / "35_crawl_referenced_types"
sys.path.insert(0, str(PHASE_DIR))

# Every crawl phase ships a package literally named `solidworks_scraper`, so a
# plain import resolves to whichever phase landed on sys.path first. Load this
# phase's module by path instead.
_spec = importlib.util.spec_from_file_location(
    "phase35_pipelines", PHASE_DIR / "solidworks_scraper" / "pipelines.py"
)
_pipelines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pipelines)
MetadataLogPipeline = _pipelines.MetadataLogPipeline


class FakeSpider:
    def __init__(self, settings):
        self.settings = settings


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    pipe = MetadataLogPipeline()
    monkeypatch.setattr(pipe, "manifest_file", tmp_path / "manifest.json")
    return pipe


def test_manifest_reports_the_settings_in_force(pipeline):
    pipeline.open_spider(
        FakeSpider(
            Settings(
                {
                    "USER_AGENT": "test-agent/1.0",
                    "ROBOTSTXT_OBEY": False,
                    "DOWNLOAD_DELAY": 0.1,
                    "CONCURRENT_REQUESTS_PER_DOMAIN": 5,
                }
            )
        )
    )
    manifest = json.loads(pipeline.manifest_file.read_text())
    assert manifest["user_agent"] == "test-agent/1.0"
    assert manifest["respect_robots_txt"] is False
    assert manifest["crawl_delay_seconds"] == 0.1
    assert manifest["concurrent_requests_per_domain"] == 5


def test_manifest_tracks_a_politer_configuration(pipeline):
    """Change the settings and the record changes with them -- the point of
    reading them rather than hardcoding a claim."""
    pipeline.open_spider(
        FakeSpider(Settings({"ROBOTSTXT_OBEY": True, "DOWNLOAD_DELAY": 2.0}))
    )
    manifest = json.loads(pipeline.manifest_file.read_text())
    assert manifest["respect_robots_txt"] is True
    assert manifest["crawl_delay_seconds"] == 2.0


def test_the_shipped_settings_match_what_the_manifest_would_record():
    """Guards against the settings module and the manifest drifting apart."""
    spec = importlib.util.spec_from_file_location(
        "phase35_settings", PHASE_DIR / "solidworks_scraper" / "settings.py"
    )
    phase_settings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(phase_settings)

    assert phase_settings.ROBOTSTXT_OBEY is False
    assert phase_settings.DOWNLOAD_DELAY == 0.1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
