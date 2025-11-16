"""
Shared constants for the SolidWorks API documentation pipeline.

These constants ensure consistency across all phases.
"""

# SolidWorks API documentation URLs
SOLIDWORKS_DOMAIN = "help.solidworks.com"
SOLIDWORKS_BASE_URL = "https://help.solidworks.com"
SOLIDWORKS_API_VERSION = "2026"
SOLIDWORKS_API_LANGUAGE = "english"
SOLIDWORKS_API_PRODUCT = "api"

# Full API base path
SOLIDWORKS_API_BASE_PATH = f"/{SOLIDWORKS_API_VERSION}/{SOLIDWORKS_API_LANGUAGE}/{SOLIDWORKS_API_PRODUCT}"

# Full API base URL (domain + path)
SOLIDWORKS_API_FULL_BASE_URL = f"{SOLIDWORKS_BASE_URL}{SOLIDWORKS_API_BASE_PATH}"

# Example: https://help.solidworks.com/2026/english/api


def make_absolute_url(relative_url: str) -> str:
    """
    Convert a relative URL to an absolute URL.

    Args:
        relative_url: Relative URL starting with / (e.g., /sldworksapi/...)

    Returns:
        Absolute URL (e.g., https://help.solidworks.com/2026/english/api/sldworksapi/...)

    Examples:
        >>> make_absolute_url('/sldworksapi/IModelDoc2~GetTitle.html')
        'https://help.solidworks.com/2026/english/api/sldworksapi/IModelDoc2~GetTitle.html'
    """
    if relative_url.startswith("/"):
        return f"{SOLIDWORKS_API_FULL_BASE_URL}{relative_url}"
    elif relative_url.startswith("http"):
        return relative_url
    else:
        return f"{SOLIDWORKS_API_FULL_BASE_URL}/{relative_url}"
