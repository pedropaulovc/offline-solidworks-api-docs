"""URL identity and link-scanning primitives for the ``/2026/english/api/`` tree.

Shared by the link-driven crawl phases (115 referenced pages, 35 referenced types),
which both answer the same two questions about a documentation URL: *is this the
same page as one I already have?* and *what does this page link to?*

- :func:`canonical_key` reduces a page URL to a case- and encoding-insensitive
  identity, so a reference and its crawled copy match however they were spelled.
- :func:`is_reference_page` recognises the generated ``Assembly~Type~Member`` pages.
  Phase 115 uses it to stay *out* of that tree; phase 35 uses it to stay *in*.
- :func:`iter_page_links` yields every ``/api`` page a chunk of text links to,
  resolving relative ``href``s against the page they came from.
- :class:`ReferenceSource` / :func:`crawled_html_sources` pair a saved help-text
  file with the URL its relative links resolve against.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import jsonlines

HOST = "https://help.solidworks.com"
API_PREFIX = "2026/english/api/"
PAGE_SUFFIXES = (".htm", ".html")

# Absolute page URLs under the /api boundary, e.g.
# https://help.solidworks.com/2026/english/api/swconst/DP_Dimensions.htm
_ABS_API_URL = re.compile(
    r"https?://help\.solidworks\.com/2026/english/api/[^\s\"'<>)\]]+?\.html?",
    re.IGNORECASE,
)

# href/src attributes in help-text HTML. Mostly relative (``Foo.htm``,
# ``../swconst/Bar.htm``), so resolving them needs the containing page's URL.
_HREF_ATTR = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.IGNORECASE)


@dataclass(frozen=True)
class ReferenceSource:
    """A corpus file scanned for page links.

    ``base_url`` is the URL of the page the file's content came from; it is what
    relative ``href``s resolve against. ``None`` for derived files (extracted XML,
    Markdown) that carry no single origin page -- those yield absolute URLs only.
    """

    path: Path
    base_url: str | None = None


def canonical_key(url: str) -> str | None:
    """Case-insensitive identity of an ``/api`` documentation page.

    Returns ``<lower path under api>`` with collapsed slashes and no query, or
    ``None`` when the URL is not a page (wrong host/tree, or not ``.htm``/``.html``).

    Percent-escapes are decoded so a link written ``Multiselect_Same%20and_...`` and
    the crawl manifest's ``Multiselect_Same and_...`` share one identity -- otherwise
    the encoded form dodges the crawled-set boundary and gets fetched twice.
    """
    if not url:
        return None

    parsed = urlparse(url)
    # Accept absolute help.solidworks.com URLs and host-relative paths (e.g. the
    # ``/2026/...`` form stored in Phase 110's manifest); reject other hosts.
    if parsed.netloc and parsed.netloc != "help.solidworks.com":
        return None

    path = re.sub(r"/{2,}", "/", unquote(parsed.path)).strip("/").lower()
    if not path.startswith(API_PREFIX):
        return None
    if not path.endswith(PAGE_SUFFIXES):
        return None
    return path


def page_assembly(url: str) -> str | None:
    """The assembly folder a page lives in (``sldworksapi``, ``swconst``, …), or
    ``None`` when the URL is not an ``/api`` page inside one."""
    key = canonical_key(url)
    if not key:
        return None
    rest = key[len(API_PREFIX):]
    folder, _, remainder = rest.partition("/")
    return folder if remainder else None


def is_reference_page(url: str) -> bool:
    """True for a generated API reference type/member page.

    These use a ``Assembly~Namespace.Type~Member`` filename (the ``~`` is the tell).
    An index page like FunctionalCategories links to hundreds, and a URL-encoding
    mismatch (e.g. a space rendered ``%20``) could otherwise slip one past a
    crawled-set boundary, so the check is on the decoded key.
    """
    key = canonical_key(url)
    return bool(key and "~" in key)


def normalize_request_url(url: str, base: str | None = None) -> str | None:
    """Resolve ``url`` (possibly relative to ``base``) to an absolute page URL
    under the boundary, collapsing accidental double slashes. Returns ``None``
    when it is not a crawlable ``/api`` page.

    Original casing is preserved (the live site is case-sensitive); only the
    matching *key* is lowercased.
    """
    absolute = urljoin(base, url) if base else url
    if absolute.startswith("/"):
        absolute = HOST + absolute
    if canonical_key(absolute) is None:
        return None

    parsed = urlparse(absolute)
    clean_path = re.sub(r"/{2,}", "/", parsed.path)
    return f"{HOST}{clean_path}"


def iter_page_links(text: str, base: str | None = None) -> Iterable[str]:
    """Yield every ``/api`` page URL reachable from ``text``, absolutized.

    Two link forms are picked up: absolute URLs appearing literally (the ``<see
    href>`` form the extracted corpus stores), and ``href``/``src`` attributes,
    which in raw help-text HTML are typically relative and need ``base`` -- the
    URL of the page ``text`` came from -- to resolve. Without a ``base``, relative
    attributes are unresolvable and skipped.

    May yield the same page twice (once per form); callers dedupe by key.
    """
    for match in _ABS_API_URL.finditer(text):
        yield match.group(0)

    for raw in _HREF_ATTR.findall(text):
        resolved = normalize_request_url(raw, base=base)
        if resolved:
            yield resolved


def build_exclusion_keys(metadata_files: Iterable[Path]) -> set[str]:
    """Union of :func:`canonical_key` for every page in the given
    ``urls_crawled.jsonl`` files (missing files are skipped)."""
    keys: set[str] = set()
    for meta in metadata_files:
        if not Path(meta).exists():
            continue
        with jsonlines.open(meta) as reader:
            for entry in reader:
                key = canonical_key(entry.get("url", ""))
                if key:
                    keys.add(key)
    return keys


def crawled_html_sources(phase_dir: Path, metadata_file: Path) -> list[ReferenceSource]:
    """:class:`ReferenceSource` per page saved by a crawl phase, each carrying the
    page's own URL as the base for its relative links.

    Reads the phase's ``urls_crawled.jsonl`` (``url`` + ``file_path``). Paths are
    stored with Windows separators, so they are normalized before joining. Entries
    whose file is gone (output/ is gitignored and re-crawled) are skipped.
    """
    if not Path(metadata_file).exists():
        return []

    sources: list[ReferenceSource] = []
    with jsonlines.open(metadata_file) as reader:
        for entry in reader:
            url = entry.get("url", "")
            raw_path = (entry.get("file_path") or "").replace("\\", "/")
            if not url or not raw_path:
                continue
            path = Path(phase_dir) / raw_path
            if path.exists():
                sources.append(ReferenceSource(path=path, base_url=url))
    return sources
