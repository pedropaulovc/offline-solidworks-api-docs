#!/usr/bin/env python3
"""
Harvest example links from legacy SOLIDWORKS API doc versions.

Why this exists
---------------
The pipeline discovers example pages *only* by following the ``<a ..._Example_...htm>``
links found in the "Example" section of the CURRENT (``SOLIDWORKS_API_VERSION``) type/member help-text.
Example pages are not nodes in the TOC tree, so an example is reachable only if some
crawled page links to it.

SOLIDWORKS sometimes drops those cross-reference links in newer doc versions while
leaving the example pages live on the server. For instance the 2017
``IChainPatternFeatureData`` type page links ``Modify_Chain_Pattern_Feature_Example_*``,
but the 2026 page did not -- even though ``Modify_Chain_Pattern_Feature_Example_CSharp.htm``
still returns HTTP 200. Those now-orphaned examples are invisible to link-graph discovery
and therefore missing from the final bundle.

This script recovers them: for every current type page it fetches the equivalent
legacy-version page(s), extracts the example links from their "Example" section,
normalizes each to a current-version URL, verifies the example still resolves
(HTTP 200) in the current version, and writes the recovered URLs to
``metadata/legacy_example_urls.txt``. The phase 70 spider unions that file into its
crawl set.
"""

import argparse
import importlib.util
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.constants import SOLIDWORKS_API_BOUNDARY, SOLIDWORKS_API_VERSION, SOLIDWORKS_DOMAIN  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; offline-solidworks-api-docs/1.0)"
DEFAULT_VERSION = SOLIDWORKS_API_VERSION
DEFAULT_LEGACY_VERSIONS = ["2017"]
# The part of a help URL path below ``/<year>/<language>/api/``.
_API_TREE_PATH = re.compile(r"^/\d{4}/[^/]+/api/(.+)$", re.IGNORECASE)
# A host path (``/<year>/...``), as opposed to an API-root path (``/sldworksapi/...``).
_VERSIONED_PATH = re.compile(r"^/\d{4}/")


def _load_type_info_extractor():
    """Load TypeInfoExtractor from the numerically-prefixed phase 40 module."""
    module_path = PROJECT_ROOT / "40_extract_type_details" / "extract_type_info.py"
    spec = importlib.util.spec_from_file_location("extract_type_info", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TypeInfoExtractor


TypeInfoExtractor = _load_type_info_extractor()


def fetch(url: str, timeout: int = 30) -> str | None:
    """Fetch a URL, returning the body text or None on any error."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


def url_exists(url: str, timeout: int = 30) -> bool:
    """Return True if the URL resolves with HTTP 200 (GET; HEAD is often blocked)."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def extract_help_text(page_html: str) -> str | None:
    """Pull the helpText HTML out of the __NEXT_DATA__ JSON (same as the spider)."""
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = page_html.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = page_html.find("</script>", start)
    if end == -1:
        return None
    try:
        data = json.loads(page_html[start:end])
    except json.JSONDecodeError:
        return None
    return (
        data.get("props", {})
        .get("pageProps", {})
        .get("helpContentData", {})
        .get("helpText")
    )


def extract_example_hrefs(help_text: str) -> list[str]:
    """Extract example-section links from a type page's helpText, as TypeInfoExtractor
    records them with an empty prefix: the href as written, or for a CHM alias the
    API-root path of the page it names (``/sldworksapi/X_Example_VB.htm``)."""
    parser = TypeInfoExtractor(url_prefix="")
    try:
        parser.feed(help_text)
    except Exception:
        return []
    return [ex["Url"] for ex in parser.examples if ex.get("Url")]


def iter_type_page_urls(toc_jsonl: Path) -> list[str]:
    """Yield the current-version type-page URLs from the phase 10 TOC crawl."""
    urls: set[str] = set()
    with open(toc_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                url = json.loads(line).get("url", "")
            except json.JSONDecodeError:
                continue
            path = urlparse(url).path.lower()
            name = path.rsplit("/", 1)[-1]
            # Type pages: exactly one '~', end in .html, not members/namespace/specials.
            if name.count("~") != 1 or not name.endswith(".html"):
                continue
            if "_members" in name or "_namespace" in name:
                continue
            if name.startswith(("functionalcategories", "releasenotes", "help_list")):
                continue
            urls.add(url.split("?")[0])
    return sorted(urls)


def to_version(url: str, version: str) -> str:
    """Rewrite a help.solidworks.com URL to a different doc version year."""
    parts = urlparse(url)
    segments = parts.path.split("/")
    # Path looks like /<year>/english/api/<subdir>/<file>
    if len(segments) > 1 and segments[1].isdigit():
        segments[1] = version
    return f"{parts.scheme}://{parts.netloc}{'/'.join(segments)}"


def subdir_of(url: str) -> str:
    """Return the api subdir (e.g. 'sldworksapi') for a type-page URL."""
    return urlparse(url).path.split("/")[-2]


def _api_tree_path(url: str, subdir: str) -> str | None:
    """The path below ``/api`` that an example link on a type page in ``subdir`` names,
    or None when it points outside the help's API tree (another host or tree)."""
    parsed = urlparse(url)
    if (parsed.scheme or parsed.netloc) and parsed.netloc.lower() != SOLIDWORKS_DOMAIN:
        return None
    # Resolve the link the way a browser on the type page would, dot segments
    # included, then check where it landed. Host paths (/<year>/...) stand as
    # written; an API-root path (a resolved CHM alias, /sldworksapi/X.htm) starts at
    # /api; anything else is relative to the type page's folder.
    base = f"{SOLIDWORKS_API_BOUNDARY}{subdir}/"
    path = parsed.path
    if path.startswith("/") and not _VERSIONED_PATH.match(path):
        base, path = SOLIDWORKS_API_BOUNDARY, path.lstrip("/")
    in_api_tree = _API_TREE_PATH.match(posixpath.normpath(posixpath.join(base, path)))
    return in_api_tree.group(1) if in_api_tree else None


def normalize_example_url(url: str, subdir: str, version: str) -> str | None:
    """Canonical current-version URL of an example link found on a type page in ``subdir``,
    or None for a link outside the help's API tree.

    ``url`` comes from :func:`extract_example_hrefs`. Absolute help URLs may use any
    scheme, year or casing (``http://.../2017/English/api/SldWorksAPI/X.htm``); the
    result uses the canonical prefix and lowercase folders, as Phases 40/50 record
    them. The file name keeps its case; :func:`main` compares case-insensitively.
    """
    api_path = _api_tree_path(url, subdir)
    if api_path is None:
        return None
    folders, _, filename = api_path.rpartition("/")
    return f"https://help.solidworks.com/{version}/english/api/{posixpath.join(folders.lower(), filename)}"


def load_known_example_urls(version: str) -> set[str]:
    """Absolute current-version example URLs already discovered from phases 40 & 50."""
    base = f"https://help.solidworks.com/{version}/english/api"
    known: set[str] = set()
    xml_files = [
        PROJECT_ROOT / "40_extract_type_details" / "metadata" / "api_types.xml",
        PROJECT_ROOT / "50_extract_type_member_details" / "metadata" / "api_member_details.xml",
    ]
    for xml_file in xml_files:
        if not xml_file.exists():
            continue
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue
        for url_el in root.findall(".//Example/Url"):
            raw = (url_el.text or "").strip()
            if not raw:
                continue
            known.add(base + raw if raw.startswith("/") else raw)
    return known


def harvest_from_type_page(
    type_url: str, legacy_versions: list[str], version: str
) -> set[str]:
    """Return current-version example URLs harvested from a single type page's legacy variants."""
    subdir = subdir_of(type_url)
    found: set[str] = set()
    for legacy in legacy_versions:
        page = fetch(to_version(type_url, legacy))
        if not page:
            continue
        help_text = extract_help_text(page)
        if not help_text:
            continue
        for url in extract_example_hrefs(help_text):
            candidate = normalize_example_url(url, subdir, version)
            if candidate:
                found.add(candidate)
    return found


def unknown_candidates(candidates: set[str], known: set[str]) -> list[str]:
    """Candidates that are not already known, compared and deduplicated case-insensitively.

    The server matches paths case-insensitively, so a differently cased link to a known
    example (or to another candidate) is the same page and would be crawled twice.
    """
    known_keys = {url.lower() for url in known}
    unknown: dict[str, str] = {}
    for candidate in sorted(candidates):
        if candidate.lower() not in known_keys:
            unknown.setdefault(candidate.lower(), candidate)
    return sorted(unknown.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toc-jsonl",
        type=Path,
        default=PROJECT_ROOT / "10_crawl_toc_pages" / "metadata" / "urls_crawled.jsonl",
        help="Phase 10 TOC crawl metadata (source of current type-page URLs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "metadata" / "legacy_example_urls.txt",
        help="Where to write recovered example URLs",
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Current doc version year")
    parser.add_argument(
        "--legacy-versions",
        nargs="+",
        default=DEFAULT_LEGACY_VERSIONS,
        help="Legacy doc version years to harvest example links from",
    )
    parser.add_argument("--workers", type=int, default=8, help="Concurrent HTTP workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit type pages (0 = all; for testing)")
    args = parser.parse_args()

    if not args.toc_jsonl.exists():
        print(f"[ERROR] TOC metadata not found: {args.toc_jsonl}")
        print("Run phase 10 (10_crawl_toc_pages/run_crawler.py) first.")
        return 1

    type_urls = iter_type_page_urls(args.toc_jsonl)
    if args.limit:
        type_urls = type_urls[: args.limit]
    print(f"Harvesting legacy example links from {len(type_urls)} type pages")
    print(f"  Legacy versions: {', '.join(args.legacy_versions)} -> current: {args.version}")

    known = load_known_example_urls(args.version)
    print(f"  Already discovered (phases 40/50): {len(known)} example URLs")

    # 1) Harvest candidate example URLs from legacy type pages.
    candidates: set[str] = set()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(harvest_from_type_page, url, args.legacy_versions, args.version): url
            for url in type_urls
        }
        for i, fut in enumerate(as_completed(futures), 1):
            candidates |= fut.result()
            if i % 200 == 0:
                print(f"  ...scanned {i}/{len(type_urls)} type pages, {len(candidates)} candidates so far")

    new_candidates = unknown_candidates(candidates, known)
    print(f"  Harvested {len(candidates)} example URLs ({len(new_candidates)} not already known)")

    # 2) Keep only candidates that still resolve in the current version.
    recovered: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = pool.map(lambda u: (u, url_exists(u)), new_candidates)
        for url, ok in results:
            if ok:
                recovered.append(url)

    recovered.sort()
    missing = len(new_candidates) - len(recovered)
    print(f"  Verified {len(recovered)} recovered examples exist in {args.version} ({missing} dropped as 404)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for url in recovered:
            f.write(f"{url}\n")
    print(f"Wrote {len(recovered)} recovered example URLs to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
