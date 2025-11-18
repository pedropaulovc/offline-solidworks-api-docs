"""
Tests for Phase 200 release export functionality.
"""

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from export_releases import ReleaseExporter


@pytest.fixture
def temp_project():
    """Create a temporary project structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create Phase 90 output directory with sample XML files
        xmldoc_dir = project_root / "90_export_xmldoc" / "output"
        xmldoc_dir.mkdir(parents=True)

        (xmldoc_dir / "SolidWorks.Interop.sldworks.xml").write_text(
            '<?xml version="1.0"?><doc><assembly><name>SolidWorks.Interop.sldworks</name></assembly></doc>'
        )
        (xmldoc_dir / "SolidWorks.Interop.swconst.xml").write_text(
            '<?xml version="1.0"?><doc><assembly><name>SolidWorks.Interop.swconst</name></assembly></doc>'
        )

        # Create Phase 120 output directory with sample markdown files
        llm_docs_dir = project_root / "120_export_llm_docs" / "output"

        # Create api/ structure
        api_dir = llm_docs_dir / "api"
        api_types_dir = api_dir / "types" / "IModelDoc2"
        api_types_dir.mkdir(parents=True)

        (api_types_dir / "_overview.md").write_text("# IModelDoc2\n\nOverview content")
        (api_types_dir / "Save.md").write_text("# IModelDoc2.Save\n\nSave method")

        api_index_dir = api_dir / "index"
        api_index_dir.mkdir(parents=True)
        (api_index_dir / "by_category.md").write_text("# By Category\n\nIndex")

        # Create docs/ structure
        docs_dir = llm_docs_dir / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "Overview.md").write_text("# Programming Guide\n\nOverview")

        # Create output directories
        output_dir = project_root / "200_export_full_release" / "output"
        output_dir.mkdir(parents=True)

        metadata_dir = project_root / "200_export_full_release" / "metadata"
        metadata_dir.mkdir(parents=True)

        yield {
            "project_root": project_root,
            "xmldoc_dir": xmldoc_dir,
            "llm_docs_dir": llm_docs_dir,
            "output_dir": output_dir,
            "metadata_dir": metadata_dir,
        }


@pytest.fixture
def exporter(temp_project):
    """Create a ReleaseExporter instance for testing."""
    return ReleaseExporter(
        project_root=temp_project["project_root"],
        output_dir=temp_project["output_dir"],
        metadata_dir=temp_project["metadata_dir"],
        verbose=False,
    )


class TestReleaseExporter:
    """Test suite for ReleaseExporter class."""

    def test_initialization(self, exporter, temp_project):
        """Test that exporter initializes correctly."""
        assert exporter.project_root == temp_project["project_root"]
        assert exporter.output_dir == temp_project["output_dir"]
        assert exporter.metadata_dir == temp_project["metadata_dir"]
        assert exporter.output_dir.exists()
        assert exporter.metadata_dir.exists()

    @patch("subprocess.run")
    def test_get_git_version_success(self, mock_run, exporter):
        """Test getting git version successfully."""
        mock_run.return_value = MagicMock(
            stdout="v1.0.0\nv0.9.0\nv0.8.0\n", returncode=0
        )

        version = exporter.get_git_version()

        assert version == "v1.0.0"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_git_version_no_tags(self, mock_run, exporter):
        """Test getting git version when no tags exist."""
        mock_run.return_value = MagicMock(stdout="\n", returncode=0)

        version = exporter.get_git_version()

        assert version == "v0.0.0"

    @patch("subprocess.run")
    def test_get_git_version_error(self, mock_run, exporter):
        """Test getting git version when git command fails."""
        mock_run.side_effect = Exception("Git not found")

        version = exporter.get_git_version()

        assert version == "v0.0.0"

    def test_export_xmldoc_package(self, exporter, temp_project):
        """Test exporting XMLDoc package."""
        version = "v1.0.0"
        metadata = exporter.export_xmldoc_package(version)

        # Check metadata
        assert metadata is not None
        assert metadata["version"] == version
        assert metadata["package_type"] == "xmldoc"
        assert metadata["file_count"] == 2  # Two XML files
        assert "SolidWorks.Interop.sldworks.xml" in metadata["files"]
        assert "SolidWorks.Interop.swconst.xml" in metadata["files"]

        # Check zip file was created
        zip_path = temp_project["output_dir"] / f"SolidWorks.Interop.xmldoc.{version}.zip"
        assert zip_path.exists()

        # Check zip contents
        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert len(file_list) == 2
            assert "SolidWorks.Interop.sldworks.xml" in file_list
            assert "SolidWorks.Interop.swconst.xml" in file_list

            # Verify content
            content = zipf.read("SolidWorks.Interop.sldworks.xml").decode("utf-8")
            assert "SolidWorks.Interop.sldworks" in content

    def test_export_xmldoc_package_missing_source(self, exporter, temp_project):
        """Test exporting XMLDoc package when source directory doesn't exist."""
        # Remove source directory
        import shutil

        shutil.rmtree(temp_project["xmldoc_dir"])

        version = "v1.0.0"
        metadata = exporter.export_xmldoc_package(version)

        assert metadata is None

    def test_export_llm_docs_package(self, exporter, temp_project):
        """Test exporting LLM docs package."""
        version = "v1.0.0"
        metadata = exporter.export_llm_docs_package(version)

        # Check metadata
        assert metadata is not None
        assert metadata["version"] == version
        assert metadata["package_type"] == "llm_docs"
        assert metadata["file_count"] == 4  # 4 markdown files

        # Check zip file was created
        zip_path = temp_project["output_dir"] / f"SolidWorks.Interop.llms.{version}.zip"
        assert zip_path.exists()

        # Check zip contents
        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert len(file_list) == 4

            # Check directory structure
            assert any(f.startswith("api/") for f in file_list)
            assert any(f.startswith("docs/") for f in file_list)

            # Check specific files
            assert "api/types/IModelDoc2/_overview.md" in file_list
            assert "api/types/IModelDoc2/Save.md" in file_list
            assert "api/index/by_category.md" in file_list
            assert "docs/Overview.md" in file_list

    def test_export_llm_docs_package_missing_source(self, exporter, temp_project):
        """Test exporting LLM docs package when source directory doesn't exist."""
        # Remove source directory
        import shutil

        shutil.rmtree(temp_project["llm_docs_dir"])

        version = "v1.0.0"
        metadata = exporter.export_llm_docs_package(version)

        assert metadata is None

    def test_save_metadata(self, exporter, temp_project):
        """Test saving metadata files."""
        metadata_list = [
            {
                "package_name": "SolidWorks.Interop.xmldoc.v1.0.0.zip",
                "version": "v1.0.0",
                "package_type": "xmldoc",
                "file_count": 2,
                "archive_size_bytes": 1024,
            },
            {
                "package_name": "SolidWorks.Interop.llms.v1.0.0.zip",
                "version": "v1.0.0",
                "package_type": "llm_docs",
                "file_count": 4,
                "archive_size_bytes": 2048,
            },
        ]

        exporter.save_metadata(metadata_list)

        # Check manifest was created
        manifest_path = temp_project["metadata_dir"] / "export_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["version"] == "v1.0.0"
        assert manifest["total_packages"] == 2
        assert manifest["total_size_bytes"] == 3072  # 1024 + 2048
        assert len(manifest["packages"]) == 2

        # Check individual metadata files
        xmldoc_metadata_path = (
            temp_project["metadata_dir"] / "SolidWorks.Interop.xmldoc.v1.0.0.json"
        )
        assert xmldoc_metadata_path.exists()

        llm_metadata_path = (
            temp_project["metadata_dir"] / "SolidWorks.Interop.llms.v1.0.0.json"
        )
        assert llm_metadata_path.exists()

    @patch.object(ReleaseExporter, "get_git_version", return_value="v1.0.0")
    def test_export_all(self, mock_version, exporter, temp_project):
        """Test exporting all packages."""
        success = exporter.export_all()

        assert success is True

        # Check both packages were created
        xmldoc_zip = (
            temp_project["output_dir"] / "SolidWorks.Interop.xmldoc.v1.0.0.zip"
        )
        llm_zip = temp_project["output_dir"] / "SolidWorks.Interop.llms.v1.0.0.zip"

        assert xmldoc_zip.exists()
        assert llm_zip.exists()

        # Check manifest was created
        manifest_path = temp_project["metadata_dir"] / "export_manifest.json"
        assert manifest_path.exists()

    def test_add_directory_to_zip(self, exporter, temp_project):
        """Test adding a directory to a zip file."""
        # Create a test directory with some files
        test_dir = temp_project["project_root"] / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")

        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file3.txt").write_text("content3")

        # Create a zip and add the directory
        zip_path = temp_project["output_dir"] / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            file_count = exporter._add_directory_to_zip(
                zipf, test_dir, arc_prefix="prefix"
            )

        # Check results
        assert file_count == 3

        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert len(file_list) == 3
            assert "prefix/file1.txt" in file_list
            assert "prefix/file2.txt" in file_list
            assert "prefix/subdir/file3.txt" in file_list


class TestZipContentValidation:
    """Tests for validating zip package contents."""

    def test_xmldoc_package_content(self, exporter):
        """Test that XMLDoc package contains valid XML."""
        version = "v1.0.0"
        metadata = exporter.export_xmldoc_package(version)

        assert metadata is not None

        zip_path = exporter.output_dir / metadata["package_name"]

        with zipfile.ZipFile(zip_path, "r") as zipf:
            for xml_file in metadata["files"]:
                content = zipf.read(xml_file).decode("utf-8")
                # Basic XML validation
                assert '<?xml version="1.0"?>' in content or "<?xml" in content
                assert "<doc>" in content
                assert "<assembly>" in content

    def test_llm_docs_package_structure(self, exporter):
        """Test that LLM docs package has correct structure."""
        version = "v1.0.0"
        metadata = exporter.export_llm_docs_package(version)

        assert metadata is not None

        zip_path = exporter.output_dir / metadata["package_name"]

        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()

            # Check that we have both api/ and docs/
            has_api = any(f.startswith("api/") for f in file_list)
            has_docs = any(f.startswith("docs/") for f in file_list)

            assert has_api, "Missing api/ directory in package"
            assert has_docs, "Missing docs/ directory in package"

            # Check markdown files are valid
            for md_file in [f for f in file_list if f.endswith(".md")]:
                content = zipf.read(md_file).decode("utf-8")
                # Basic markdown validation - should have some text
                assert len(content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
