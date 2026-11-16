"""Resolve compiled-help (CHM) alias links to the web help page they name.

The help pages were authored as CHM files, and many cross-file links still carry the
CHM form: ``ms-its:swconst.chm::/DP_Dimensions.htm`` or, without the protocol,
``sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm``. The web help serves each
CHM's pages from a folder directly under ``/api`` named after the CHM, lowercased
(``swconst/``, ``sldworksapiprogguide/``), so the alias is resolvable. Left as is, a
browser or crawler joins it onto the linking page's folder
(``.../api/sldworksapi/ms-its:swconst.chm::/DP_Dimensions.htm``), which the server
answers with its "page cannot be found" page.

An alias names the same page wherever it is written: whatever precedes the CHM name
(the linking page's folder, ``../``, ``ms-its:``, ``mk:@MSITStore:``) is dropped and
the page is placed under the API root. The path inside the CHM keeps its case
(``OVERVIEW/Type_Libraries.htm`` vs the TOC's ``Overview/``): the server matches
paths case-insensitively, and every in-bundle lookup (Phase 115's ``canonical_key``,
Phase 120's ``guide_link_key``) compares lowercased forms.
"""

import posixpath
import re
from urllib.parse import urlparse

from shared.constants import SOLIDWORKS_API_BOUNDARY, SOLIDWORKS_API_FULL_BASE_URL

# ``<name>.chm::/<path>``; the separator is sometimes doubled (``::/``+``/``). The
# name is word runs joined by ``.`` or ``-`` (so ``..chm`` and ``a..chm`` are no CHM)
# and stops at whatever precedes it: ``/``, a protocol's ``:``, ``@``, ``\``.
_CHM_ALIAS = re.compile(r"(\w+(?:[.-]\w+)*)\.chm::/+(.*)", re.IGNORECASE)


def chm_alias_page(link: str) -> str | None:
    """The page a CHM alias in ``link`` names, as a path under the API root, or None.

    ``sldworksapi/sldworksAPIProgGuide.chm::/OVERVIEW/X.htm`` and
    ``ms-its:sldworksapiprogguide.chm::/OVERVIEW/X.htm`` -> ``sldworksapiprogguide/OVERVIEW/X.htm``.
    """
    match = _CHM_ALIAS.search(link)
    if match is None:
        return None
    return f"{match.group(1).lower()}/{match.group(2)}"


def resolve_chm_alias(link: str) -> str:
    """The absolute URL of the page a CHM alias in ``link`` names; other links unchanged.

    Absolute, API-root-relative and page-relative aliases alike resolve to
    ``https://help.solidworks.com/<year>/english/api/<chm>/<path>``, so the result
    does not depend on how deep the linking page sits.
    """
    page = chm_alias_page(link)
    if page is None:
        return link
    return f"{SOLIDWORKS_API_FULL_BASE_URL}/{page}"


def relative_chm_alias(link: str, page_url: str) -> str:
    """A CHM alias in ``link`` as a link relative to the page it is written on; other
    links unchanged.

    ``page_url`` is that page's help URL or path. From ``.../api/swconst/X.htm``,
    ``sldworksapi.chm::/Y.htm`` becomes ``../sldworksapi/Y.htm``: the same form as the
    page's ordinary relative links, so later link resolution treats both alike.
    """
    page = chm_alias_page(link)
    if page is None:
        return link
    page_dir = posixpath.dirname(urlparse(page_url).path)
    return posixpath.relpath(f"{SOLIDWORKS_API_BOUNDARY}{page}", page_dir)
