"""Resolve compiled-help (CHM) alias links to the web help page they name.

The help pages were authored as CHM files, and many cross-file links still carry the
CHM form: ``ms-its:swconst.chm::/DP_Dimensions.htm`` or, without the protocol,
``sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm``. The web help serves each
CHM's pages from a sibling folder under ``/api`` named after the CHM, lowercased
(``swconst/``, ``sldworksapiprogguide/``), so the alias is resolvable. Left as is, a
browser or crawler joins it onto the linking page's folder
(``.../api/sldworksapi/ms-its:swconst.chm::/DP_Dimensions.htm``), which the server
answers with its "page cannot be found" page.

Only the folder is rewritten; the path inside the CHM keeps its case
(``OVERVIEW/Type_Libraries.htm`` vs the TOC's ``Overview/``). The server matches
paths case-insensitively, and every in-bundle lookup (Phase 115's
``canonical_key``, Phase 120's ``guide_link_key``) compares lowercased forms.
"""

import re

from shared.constants import SOLIDWORKS_API_PATH_PREFIX

# ``[ms-its:]<name>.chm::/<path>``; the separator is sometimes doubled (``::/``+``/``).
_CHM_ALIAS = re.compile(r"(?:ms-its:)?([\w.-]+)\.chm::/+", re.IGNORECASE)
# The last folder of the part before the alias: the folder the link was written in.
_LAST_FOLDER = re.compile(r"[^/]+/$")
_API_ROOT_SUFFIX = "/" + SOLIDWORKS_API_PATH_PREFIX


def resolve_chm_alias(link: str) -> str:
    """``link`` with a CHM alias replaced by the web folder it names; other links unchanged.

    The alias stands for a page in a sibling folder of the one the link sits in, so
    the folder before it is swapped for the CHM's folder. Works on every form the
    pipeline handles:

    - absolute: ``https://.../api/sldworksapi/sldworksAPIProgGuide.chm::/OVERVIEW/X.htm``
      -> ``https://.../api/sldworksapiprogguide/OVERVIEW/X.htm`` (an alias written
      directly under ``/api`` -- ``.../api/ms-its:swconst.chm::/X.htm`` -- has no
      folder to swap and becomes ``.../api/swconst/X.htm``)
    - API-root relative, as Phases 40/50 record example URLs:
      ``/swconst/ms-its:sldworksapi.chm::/X.htm`` -> ``/sldworksapi/X.htm``
    - relative to a sibling folder: ``../swconst/ms-its:x.chm::/Y.htm`` -> ``../x/Y.htm``
    - bare, relative to the linking page: ``ms-its:swconst.chm::/X.htm`` -> ``../swconst/X.htm``
    """
    match = _CHM_ALIAS.search(link)
    if match is None:
        return link
    before, rest = link[: match.start()], link[match.end() :]
    if not before:
        folder_root = "../"
    elif before.endswith(_API_ROOT_SUFFIX):
        folder_root = before
    else:
        folder_root = _LAST_FOLDER.sub("", before)
    return f"{folder_root}{match.group(1).lower()}/{rest}"
