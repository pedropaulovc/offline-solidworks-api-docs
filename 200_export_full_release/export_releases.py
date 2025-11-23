#!/usr/bin/env python3
"""
Phase 200: Export Full Release Packages

Creates distributable zip archives from Phase 90 (XMLDoc) and Phase 120 (LLM-friendly docs).
Archives are versioned using git tags for reproducibility.
"""

import argparse
import json
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ReleaseExporter:
    """Exports release packages from pipeline outputs."""

    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        metadata_dir: Path,
        verbose: bool = False,
    ):
        self.project_root = project_root
        self.output_dir = output_dir
        self.metadata_dir = metadata_dir
        self.verbose = verbose

        # Source directories
        self.xmldoc_source = project_root / "90_export_xmldoc" / "output"
        self.llm_docs_source = project_root / "120_export_llm_docs" / "output"

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def get_git_version(self) -> str:
        """Get the latest git tag for versioning."""
        try:
            # Get the latest tag
            result = subprocess.run(
                ["git", "tag", "--sort=-v:refname"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            tags = result.stdout.strip().split("\n")

            if not tags or not tags[0]:
                self._log("Warning: No git tags found, using v0.0.0")
                return "v0.0.0"

            version = tags[0]
            self._log(f"Using git version: {version}")
            return version

        except Exception as e:
            self._log(f"Error getting git tag: {e}")
            self._log("Falling back to v0.0.0")
            return "v0.0.0"

    def _log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _add_directory_to_zip(
        self, zipf: zipfile.ZipFile, source_dir: Path, arc_prefix: str = ""
    ) -> int:
        """
        Add all files from a directory to a zip file.

        Args:
            zipf: ZipFile object to add files to
            source_dir: Directory to add files from
            arc_prefix: Prefix for archive paths (e.g., "api/")

        Returns:
            Number of files added
        """
        file_count = 0

        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                # Calculate archive path
                rel_path = file_path.relative_to(source_dir)
                arc_path = Path(arc_prefix) / rel_path if arc_prefix else rel_path

                # Add to zip
                zipf.write(file_path, arcname=str(arc_path))
                file_count += 1

                if self.verbose and file_count % 100 == 0:
                    self._log(f"  Added {file_count} files...")

        return file_count

    def export_xmldoc_package(self, version: str) -> Optional[Dict]:
        """
        Export XMLDoc files to a versioned zip archive.

        Args:
            version: Version string (e.g., "v1.0.0")

        Returns:
            Metadata dict if successful, None otherwise
        """
        if not self.xmldoc_source.exists():
            self._log(f"Error: XMLDoc source directory not found: {self.xmldoc_source}")
            return None

        # Create zip filename
        zip_name = f"SolidWorks.Interop.xmldoc.{version}.zip"
        zip_path = self.output_dir / zip_name

        self._log(f"\nCreating XMLDoc package: {zip_name}")
        self._log(f"  Source: {self.xmldoc_source}")
        self._log(f"  Destination: {zip_path}")

        # Create zip file
        file_count = 0
        xml_files = []

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for xml_file in self.xmldoc_source.glob("*.xml"):
                zipf.write(xml_file, arcname=xml_file.name)
                xml_files.append(xml_file.name)
                file_count += 1
                self._log(f"  Added: {xml_file.name}")

        # Get zip file size
        zip_size = zip_path.stat().st_size

        self._log(f"  Total files: {file_count}")
        self._log(f"  Archive size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)")

        # Create metadata
        metadata = {
            "package_name": zip_name,
            "version": version,
            "package_type": "xmldoc",
            "description": "Microsoft XMLDoc files for Visual Studio IntelliSense",
            "source_phase": "90_export_xmldoc",
            "source_directory": str(self.xmldoc_source.relative_to(self.project_root)),
            "file_count": file_count,
            "archive_size_bytes": zip_size,
            "files": xml_files,
        }

        return metadata

    def export_llm_docs_package(self, version: str) -> Optional[Dict]:
        """
        Export LLM-friendly documentation to a versioned zip archive.

        Args:
            version: Version string (e.g., "v1.0.0")

        Returns:
            Metadata dict if successful, None otherwise
        """
        if not self.llm_docs_source.exists():
            self._log(
                f"Error: LLM docs source directory not found: {self.llm_docs_source}"
            )
            return None

        # Create zip filename
        zip_name = f"SolidWorks.Interop.llms.{version}.zip"
        zip_path = self.output_dir / zip_name

        self._log(f"\nCreating LLM docs package: {zip_name}")
        self._log(f"  Source: {self.llm_docs_source}")
        self._log(f"  Destination: {zip_path}")

        # Create zip file
        total_files = 0

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add api/ directory
            api_dir = self.llm_docs_source / "api"
            if api_dir.exists():
                self._log("  Adding api/ directory...")
                api_files = self._add_directory_to_zip(zipf, api_dir, "api")
                total_files += api_files
                self._log(f"    Added {api_files} files from api/")

            # Add docs/ directory
            docs_dir = self.llm_docs_source / "docs"
            if docs_dir.exists():
                self._log("  Adding docs/ directory...")
                docs_files = self._add_directory_to_zip(zipf, docs_dir, "docs")
                total_files += docs_files
                self._log(f"    Added {docs_files} files from docs/")

        # Get zip file size
        zip_size = zip_path.stat().st_size

        self._log(f"  Total files: {total_files}")
        self._log(f"  Archive size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)")

        # Create metadata
        metadata = {
            "package_name": zip_name,
            "version": version,
            "package_type": "llm_docs",
            "description": "LLM-friendly markdown documentation (grep-optimized)",
            "source_phase": "120_export_llm_docs",
            "source_directory": str(self.llm_docs_source.relative_to(self.project_root)),
            "file_count": total_files,
            "archive_size_bytes": zip_size,
        }

        return metadata

    def save_metadata(self, metadata_list: List[Dict]):
        """Save metadata about exported packages."""
        if not metadata_list:
            self._log("No metadata to save")
            return

        # Create manifest
        manifest = {
            "version": metadata_list[0]["version"] if metadata_list else "unknown",
            "packages": metadata_list,
            "total_packages": len(metadata_list),
            "total_size_bytes": sum(m["archive_size_bytes"] for m in metadata_list),
        }

        # Save manifest
        manifest_path = self.metadata_dir / "export_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        self._log(f"\nMetadata saved to: {manifest_path}")

        # Save individual package metadata
        for metadata in metadata_list:
            pkg_name = metadata["package_name"].replace(".zip", ".json")
            metadata_path = self.metadata_dir / pkg_name

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            self._log(f"  {pkg_name}")

    def export_all(self) -> bool:
        """
        Export all release packages.

        Returns:
            True if all packages were created successfully
        """
        # Get version from git
        version = self.get_git_version()

        # Export packages
        metadata_list = []

        # Export XMLDoc package
        xmldoc_metadata = self.export_xmldoc_package(version)
        if xmldoc_metadata:
            metadata_list.append(xmldoc_metadata)
        else:
            self._log("Warning: XMLDoc package export failed")

        # Export LLM docs package
        llm_metadata = self.export_llm_docs_package(version)
        if llm_metadata:
            metadata_list.append(llm_metadata)
        else:
            self._log("Warning: LLM docs package export failed")

        # Save metadata
        if metadata_list:
            self.save_metadata(metadata_list)
            return True

        return False


def main():
    parser = argparse.ArgumentParser(
        description="Export full release packages from pipeline outputs"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("200_export_full_release/output"),
        help="Output directory for zip packages (default: 200_export_full_release/output)",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("200_export_full_release/metadata"),
        help="Metadata directory (default: 200_export_full_release/metadata)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    # Get project root (parent of script directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Create exporter
    exporter = ReleaseExporter(
        project_root=project_root,
        output_dir=args.output_dir,
        metadata_dir=args.metadata_dir,
        verbose=args.verbose,
    )

    # Export all packages
    print("=== SolidWorks API Documentation - Release Export ===\n")
    success = exporter.export_all()

    if success:
        print("\n[SUCCESS] Release packages created successfully!")
        print(f"\nOutput directory: {args.output_dir}")
    else:
        print("\n[ERROR] Some packages failed to export")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
