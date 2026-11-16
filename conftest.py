"""
Pytest configuration for the multi-phase project.

Every phase directory (10_crawl_toc_pages, 30_crawl_type_members, ...) is its own
import root, and several of them define the same top-level module names: five
crawl phases each ship a ``solidworks_scraper`` package, and ``run_crawler``,
``validate_crawl`` etc. repeat too. In one interpreter ``sys.modules`` holds a
single ``solidworks_scraper``, so without intervention every phase's tests would
exercise whichever phase happened to be imported first.

To keep each phase's tests on that phase's code, this conftest switches the
"active phase" before a phase's tests are collected (imported) and before each of
its tests runs: the phase directory moves to the front of ``sys.path``, and the
modules behind the shared names are swapped in ``sys.modules`` (stashed per phase,
so a phase's modules are imported once and keep their identity across switches).
"""

import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
PHASE_DIRS = sorted(p for p in PROJECT_ROOT.iterdir() if p.is_dir() and re.match(r"\d+_", p.name))


def _top_level_modules(phase_dir: Path) -> set[str]:
    """Names importable from a phase directory: ``*.py`` modules and packages."""
    names = {p.stem for p in phase_dir.glob("*.py") if p.name != "__init__.py"}
    names |= {p.parent.name for p in phase_dir.glob("*/__init__.py")}
    return names


def _shared_names() -> frozenset[str]:
    """Top-level module names defined by more than one phase."""
    seen: set[str] = set()
    shared: set[str] = set()
    for phase_dir in PHASE_DIRS:
        names = _top_level_modules(phase_dir)
        shared |= seen & names
        seen |= names
    return frozenset(shared)


PHASE_LOCAL_NAMES = _shared_names()

_active_phase: Path | None = None
_stash: dict[Path, dict[str, ModuleType]] = {}


def _phase_of(path: Path | str | None) -> Path | None:
    if path is None:
        return None
    path = Path(path).resolve()
    return next((d for d in PHASE_DIRS if path.is_relative_to(d)), None)


def _module_phase(module: ModuleType) -> Path | None:
    location = getattr(module, "__file__", None)
    if location is None:
        location = next(iter(getattr(module, "__path__", [])), None)
    return _phase_of(location)


def _activate(phase: Path) -> None:
    global _active_phase
    if sys.path[:1] != [str(phase)]:
        while str(phase) in sys.path:
            sys.path.remove(str(phase))
        sys.path.insert(0, str(phase))
    if phase == _active_phase:
        return
    for name in [n for n in sys.modules if n.partition(".")[0] in PHASE_LOCAL_NAMES]:
        module = sys.modules.pop(name)
        owner = _module_phase(module)
        if owner is not None:
            _stash.setdefault(owner, {}).setdefault(name, module)
    sys.modules.update(_stash.pop(phase, {}))
    _active_phase = phase


def _activate_for(path: Path | None) -> Path | None:
    phase = _phase_of(path)
    if phase is not None:
        _activate(phase)
    return phase


def _assert_modules_belong_to(phase: Path) -> None:
    """Every loaded module behind a shared name must be ``phase``'s own copy.

    This is the invariant the activation exists for; checking it here covers every
    phase (present and future) instead of per-file guard tests."""
    strays = sorted(
        f"{name} ({owner.name})"
        for name, module in sys.modules.items()
        if name.partition(".")[0] in PHASE_LOCAL_NAMES
        and (owner := _module_phase(module)) is not None
        and owner != phase
    )
    if strays:
        raise RuntimeError(f"{phase.name} is active but other phases' modules are loaded: {', '.join(strays)}")


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector: pytest.Collector):  # type: ignore[no-untyped-def]
    phase = _activate_for(collector.path)
    report = yield
    if phase is not None:
        _assert_modules_belong_to(phase)
    return report


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):  # type: ignore[no-untyped-def]
    phase = _activate_for(item.path)
    if phase is not None:
        _assert_modules_belong_to(phase)
    return (yield)


@pytest.fixture
def crawler_spider():  # type: ignore[no-untyped-def]
    """Factory for a spider bound to a configured Crawler (settings and stats), as in a real crawl.

    Spider code that retries through ``get_retry_request`` or reads crawler stats needs
    one; a bare ``Spider()`` has no ``crawler``. Nothing is downloaded: the reactor is
    installed only because Scrapy's ``get_crawler`` checks the crawler settings against it.
    """
    from scrapy.utils.reactor import install_reactor, is_reactor_installed
    from scrapy.utils.test import get_crawler

    if not is_reactor_installed():
        install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

    def make(spidercls, **kwargs):  # type: ignore[no-untyped-def]
        return spidercls.from_crawler(get_crawler(spidercls), **kwargs)

    return make
