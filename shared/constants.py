"""
Shared constants for the SolidWorks API documentation pipeline.

These constants ensure consistency across all phases. The documentation year
lives ONLY in ``SOLIDWORKS_API_VERSION``; every phase derives its URLs, path
prefixes and boundaries from it, so a yearly doc refresh is a one-line change
here (plus re-mapping the TOC root ids in the Phase 10 spider).
"""

# SolidWorks API documentation URLs
SOLIDWORKS_DOMAIN = "help.solidworks.com"
SOLIDWORKS_BASE_URL = "https://help.solidworks.com"
SOLIDWORKS_API_VERSION = "2027"
SOLIDWORKS_API_LANGUAGE = "english"
SOLIDWORKS_API_PRODUCT = "api"

# Full API base path
SOLIDWORKS_API_BASE_PATH = f"/{SOLIDWORKS_API_VERSION}/{SOLIDWORKS_API_LANGUAGE}/{SOLIDWORKS_API_PRODUCT}"

# Crawl boundary: every in-scope page path starts with this (e.g. /2027/english/api/)
SOLIDWORKS_API_BOUNDARY = f"{SOLIDWORKS_API_BASE_PATH}/"

# Same as the boundary without the leading slash (e.g. 2027/english/api/), the
# form URL paths take after ``urlparse(url).path.lstrip("/")``
SOLIDWORKS_API_PATH_PREFIX = SOLIDWORKS_API_BOUNDARY.lstrip("/")

# Full API base URL (domain + path)
SOLIDWORKS_API_FULL_BASE_URL = f"{SOLIDWORKS_BASE_URL}{SOLIDWORKS_API_BASE_PATH}"

# Example: https://help.solidworks.com/2027/english/api


def expand_toc_url(toc_id: str | int) -> str:
    """
    Build the expandToc JSON API URL for a TOC node.

    Examples:
        >>> expand_toc_url(4)  # doctest: +SKIP
        'https://help.solidworks.com/expandToc?version=2027&language=english&product=api&queryParam=?id=4'
    """
    return (
        f"{SOLIDWORKS_BASE_URL}/expandToc?version={SOLIDWORKS_API_VERSION}"
        f"&language={SOLIDWORKS_API_LANGUAGE}&product={SOLIDWORKS_API_PRODUCT}&queryParam=?id={toc_id}"
    )


def make_absolute_url(relative_url: str) -> str:
    """
    Convert a relative URL to an absolute URL.

    Args:
        relative_url: Relative URL starting with / (e.g., /sldworksapi/...)

    Returns:
        Absolute URL (e.g., https://help.solidworks.com/2027/english/api/sldworksapi/...)

    Examples:
        >>> make_absolute_url('/sldworksapi/IModelDoc2~GetTitle.html')  # doctest: +SKIP
        'https://help.solidworks.com/2027/english/api/sldworksapi/IModelDoc2~GetTitle.html'
    """
    if relative_url.startswith("/"):
        return f"{SOLIDWORKS_API_FULL_BASE_URL}{relative_url}"
    elif relative_url.startswith("http"):
        return relative_url
    else:
        return f"{SOLIDWORKS_API_FULL_BASE_URL}/{relative_url}"
