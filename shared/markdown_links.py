"""Markdown link destinations for the bundle's file paths.

Guide pages are named after their TOC titles, so paths hold spaces, parentheses and
``#`` (``Programming with the SOLIDWORKS API/Visual C#.md``). Phases 110 and 120 both
write links to them and build the destination here, so the rule cannot drift.
"""

import re


def markdown_destination(path: str, fragment: str = "") -> str:
    """The Markdown link destination for a file ``path`` plus an optional ``#fragment``.

    A ``#`` in the path is part of the file name, but in a destination it starts the
    fragment, so it is percent-encoded. A bare space or parenthesis ends a CommonMark
    destination, so such a destination is angle-wrapped (``<...>``). ``fragment`` is
    ``"#section"`` or ``""`` and is appended as is.
    """
    destination = path.replace("#", "%23") + fragment
    return f"<{destination}>" if re.search(r"[ ()]", destination) else destination
