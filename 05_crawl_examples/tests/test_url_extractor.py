"""Tests for the URL extractor script"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from extract_example_urls import extract_urls_from_xml


def test_extract_urls_from_simple_xml():
    """Test URL extraction from simple XML structure"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
            <Example>
                <Url>/sldworksapi/test2.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    # Create temporary XML file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        # Extract URLs
        urls = extract_urls_from_xml(temp_path)

        # Check results
        assert len(urls) == 2
        assert "/sldworksapi/test1.htm" in urls
        assert "/sldworksapi/test2.htm" in urls

    finally:
        # Clean up
        temp_path.unlink()


def test_extract_urls_removes_duplicates():
    """Test that duplicate URLs are removed"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
        </Examples>
    </Type>
    <Type>
        <Name>TestType2</Name>
        <Examples>
            <Example>
                <Url>/sldworksapi/test1.htm</Url>
            </Example>
            <Example>
                <Url>/sldworksapi/test2.htm</Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        urls = extract_urls_from_xml(temp_path)

        # Should have 2 unique URLs
        assert len(urls) == 2
        assert "/sldworksapi/test1.htm" in urls
        assert "/sldworksapi/test2.htm" in urls

    finally:
        temp_path.unlink()


def test_extract_urls_handles_empty_examples():
    """Test extraction with no examples"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
    </Type>
</Types>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        urls = extract_urls_from_xml(temp_path)
        assert len(urls) == 0

    finally:
        temp_path.unlink()


def test_extract_urls_handles_whitespace():
    """Test that URLs with surrounding whitespace are trimmed"""
    xml_content = """<?xml version="1.0" ?>
<Types>
    <Type>
        <Name>TestType1</Name>
        <Examples>
            <Example>
                <Url>  /sldworksapi/test1.htm  </Url>
            </Example>
        </Examples>
    </Type>
</Types>
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    try:
        urls = extract_urls_from_xml(temp_path)
        assert len(urls) == 1
        assert "/sldworksapi/test1.htm" in urls

    finally:
        temp_path.unlink()
