"""Tests for shared.markdown_links."""

import pytest

from shared.markdown_links import markdown_destination


@pytest.mark.parametrize(
    ("path", "fragment", "destination"),
    [
        ("../swconst/DP_Units.md", "", "../swconst/DP_Units.md"),
        ("../swconst/DP_Units.md", "#remarks", "../swconst/DP_Units.md#remarks"),
        # A space or parenthesis would end a bare CommonMark destination.
        ("Add-ins/Add-in Toolbars.md", "", "<Add-ins/Add-in Toolbars.md>"),
        ("Arrays (VBA).md", "", "<Arrays (VBA).md>"),
        # A '#' in the file name is not a fragment.
        ("Visual C#.md", "", "<Visual C%23.md>"),
        ("C#.md", "#top", "C%23.md#top"),
    ],
)
def test_markdown_destination(path: str, fragment: str, destination: str) -> None:
    assert markdown_destination(path, fragment) == destination
