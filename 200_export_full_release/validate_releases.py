#!/usr/bin/env python3
"""
Validation script for Phase 200 release packages.

Validates that exported zip packages:
1. Exist and are valid zip archives
2. Contain expected content
3. Match metadata
4. Have correct version numbering
"""

import argparse
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ReleaseValidator:
    """Validates exported release packages."""

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

        self.errors = []
        self.warnings = []
        self.info = []

    def _log(self, message: str, level: str = "info"):
        """Log a message and track it."""
        if self.verbose or level == "error":
            prefix = {
                "error": "[ERROR]",
                "warning": "[WARN]",
                "info": "[INFO]",
                "success": "[OK]",
            }.get(level, "[INFO]")
            print(f"{prefix} {message}")

        if level == "error":
            self.errors.append(message)
        elif level == "warning":
            self.warnings.append(message)
        elif level == "info":
            self.info.append(message)

    def get_git_version(self) -> str:
        """Get the latest git tag."""
        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-v:refname"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            tags = result.stdout.strip().split("\n")
            return tags[0] if tags and tags[0] else "v0.0.0"
        except subprocess.CalledProcessError:
            return "v0.0.0"

    def validate_zip_file(self, zip_path: Path) -> bool:
        """
        Validate that a file is a valid zip archive.

        Returns:
            True if valid, False otherwise
        """
        if not zip_path.exists():
            self._log(f"Package not found: {zip_path}", "error")
            return False

        try:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                # Test the zip file integrity
                bad_file = zipf.testzip()
                if bad_file:
                    self._log(f"Corrupted file in archive: {bad_file}", "error")
                    return False

            self._log(f"Valid zip archive: {zip_path.name}", "success")
            return True

        except zipfile.BadZipFile:
            self._log(f"Invalid zip file: {zip_path}", "error")
            return False

    def validate_xmldoc_package(self, version: str) -> bool:
        """Validate the XMLDoc package."""
        package_name = f"SolidWorks.Interop.xmldoc.{version}.zip"
        zip_path = self.output_dir / package_name

        print(f"\n=== Validating XMLDoc Package ===")
        print(f"Package: {package_name}")

        # Check if package exists and is valid
        if not self.validate_zip_file(zip_path):
            return False

        # Check contents
        try:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                file_list = zipf.namelist()

                # Count XML files
                xml_files = [f for f in file_list if f.endswith(".xml")]
                self._log(f"Contains {len(xml_files)} XML files", "success")

                # Check for expected assemblies
                expected_assemblies = [
                    "SolidWorks.Interop.sldworks.xml",
                    "SolidWorks.Interop.swconst.xml",
                ]

                for assembly in expected_assemblies:
                    if assembly in file_list:
                        self._log(f"  Found: {assembly}", "success")
                    else:
                        self._log(f"  Missing: {assembly}", "warning")

                # Check package size
                zip_size = zip_path.stat().st_size
                self._log(
                    f"Package size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)",
                    "info",
                )

                # Validate against metadata if available
                metadata_path = self.metadata_dir / package_name.replace(".zip", ".json")
                if metadata_path.exists():
                    with open(metadata_path, encoding="utf-8") as f:
                        metadata = json.load(f)

                    # Check file count
                    if len(xml_files) == metadata["file_count"]:
                        self._log("File count matches metadata", "success")
                    else:
                        self._log(
                            f"File count mismatch: {len(xml_files)} != {metadata['file_count']}",
                            "error",
                        )

                    # Check size
                    if zip_size == metadata["archive_size_bytes"]:
                        self._log("Package size matches metadata", "success")
                    else:
                        self._log(
                            f"Size mismatch: {zip_size} != {metadata['archive_size_bytes']}",
                            "warning",
                        )

            return True

        except Exception as e:
            self._log(f"Error validating package: {e}", "error")
            return False

    def validate_llm_docs_package(self, version: str) -> bool:
        """Validate the LLM docs package."""
        package_name = f"SolidWorks.Interop.llms.{version}.zip"
        zip_path = self.output_dir / package_name

        print(f"\n=== Validating LLM Docs Package ===")
        print(f"Package: {package_name}")

        # Check if package exists and is valid
        if not self.validate_zip_file(zip_path):
            return False

        # Check contents
        try:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                file_list = zipf.namelist()

                # Count markdown files
                md_files = [f for f in file_list if f.endswith(".md")]
                self._log(f"Contains {len(md_files)} markdown files", "success")

                # Check for expected directories
                has_api = any(f.startswith("api/") for f in file_list)
                has_docs = any(f.startswith("docs/") for f in file_list)

                if has_api:
                    api_files = [f for f in file_list if f.startswith("api/")]
                    self._log(f"  api/ directory: {len(api_files)} files", "success")
                else:
                    self._log("  Missing: api/ directory", "error")

                if has_docs:
                    docs_files = [f for f in file_list if f.startswith("docs/")]
                    self._log(f"  docs/ directory: {len(docs_files)} files", "success")
                else:
                    self._log("  Missing: docs/ directory", "error")

                # Check for key index files
                expected_indexes = [
                    "api/index/by_category.md",
                    "api/index/by_assembly.md",
                    "api/index/statistics.md",
                ]

                for index_file in expected_indexes:
                    if index_file in file_list:
                        self._log(f"  Found: {index_file}", "success")
                    else:
                        self._log(f"  Missing: {index_file}", "warning")

                # Check package size
                zip_size = zip_path.stat().st_size
                self._log(
                    f"Package size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)",
                    "info",
                )

                # Validate against metadata if available
                metadata_path = self.metadata_dir / package_name.replace(".zip", ".json")
                if metadata_path.exists():
                    with open(metadata_path, encoding="utf-8") as f:
                        metadata = json.load(f)

                    # Check file count
                    if len(file_list) == metadata["file_count"]:
                        self._log("File count matches metadata", "success")
                    else:
                        self._log(
                            f"File count mismatch: {len(file_list)} != {metadata['file_count']}",
                            "error",
                        )

                    # Check size
                    if zip_size == metadata["archive_size_bytes"]:
                        self._log("Package size matches metadata", "success")
                    else:
                        self._log(
                            f"Size mismatch: {zip_size} != {metadata['archive_size_bytes']}",
                            "warning",
                        )

            return True

        except Exception as e:
            self._log(f"Error validating package: {e}", "error")
            return False

    def validate_metadata(self, version: str) -> bool:
        """Validate export metadata files."""
        print(f"\n=== Validating Metadata ===")

        # Check manifest
        manifest_path = self.metadata_dir / "export_manifest.json"
        if not manifest_path.exists():
            self._log(f"Manifest not found: {manifest_path}", "error")
            return False

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            # Check version
            if manifest["version"] == version:
                self._log(f"Manifest version matches: {version}", "success")
            else:
                self._log(
                    f"Version mismatch: {manifest['version']} != {version}", "error"
                )

            # Check packages
            package_count = len(manifest["packages"])
            self._log(f"Manifest lists {package_count} packages", "info")

            for pkg in manifest["packages"]:
                pkg_type = pkg["package_type"]
                pkg_name = pkg["package_name"]
                self._log(f"  {pkg_type}: {pkg_name}", "info")

            return True

        except Exception as e:
            self._log(f"Error reading manifest: {e}", "error")
            return False

    def validate_all(self, version: Optional[str] = None) -> bool:
        """
        Validate all release packages.

        Returns:
            True if all validations pass
        """
        # Get version if not provided
        if not version:
            version = self.get_git_version()

        print(f"=== Release Package Validation ===")
        print(f"Version: {version}\n")

        # Validate packages
        xmldoc_valid = self.validate_xmldoc_package(version)
        llm_docs_valid = self.validate_llm_docs_package(version)
        metadata_valid = self.validate_metadata(version)

        # Print summary
        print(f"\n=== Validation Summary ===")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")

        if self.errors:
            print("\nErrors found:")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings and self.verbose:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")

        # Overall result
        all_valid = xmldoc_valid and llm_docs_valid and metadata_valid and not self.errors

        if all_valid:
            print("\n[SUCCESS] ALL VALIDATIONS PASSED")
        else:
            print("\n[FAILED] VALIDATION FAILED")

        return all_valid

    def save_report(self, report_path: Path, version: str):
        """Save validation report to JSON file."""
        report = {
            "version": version,
            "timestamp": Path(self.metadata_dir / "export_manifest.json")
            .stat()
            .st_mtime
            if (self.metadata_dir / "export_manifest.json").exists()
            else None,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "passed": len(self.errors) == 0,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\nValidation report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate exported release packages"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("200_export_full_release/output"),
        help="Output directory containing packages",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("200_export_full_release/metadata"),
        help="Metadata directory",
    )
    parser.add_argument(
        "--version", type=str, help="Version to validate (default: latest git tag)"
    )
    parser.add_argument(
        "--save-report",
        type=Path,
        help="Save validation report to JSON file",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Create validator
    validator = ReleaseValidator(
        project_root=project_root,
        output_dir=args.output_dir,
        metadata_dir=args.metadata_dir,
        verbose=args.verbose,
    )

    # Run validation
    success = validator.validate_all(version=args.version)

    # Save report if requested
    if args.save_report:
        version = args.version or validator.get_git_version()
        validator.save_report(args.save_report, version)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
