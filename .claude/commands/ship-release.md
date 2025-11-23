---
description: Ship a new release with git tag, changelog, and GitHub release
---

# Ship New Release

Perform a complete release workflow for the project. Follow these steps in order:

## Step 1: Commit and Push Pending Changes

1. Check git status for any uncommitted changes
2. If there are pending changes:
   - Review the changes
   - Create a meaningful commit message based on the changes
   - Commit the changes with the standard format
   - Push to origin/main

## Step 2: Determine Next Version

1. Get the current latest git tag (e.g., v2.2.0)
2. Increment to the next minor version (e.g., v2.2.0 → v2.3.0)
3. Ask the user to confirm the version number or provide a custom one

## Step 3: Generate Changelog

1. Get git log since the last tag
2. Parse commits to extract meaningful changes
3. Group by category (Features, Fixes, Documentation, etc.)
4. Format as a clean markdown changelog
5. Show the changelog to the user for review

## Step 4: Create Git Tag

1. Create an annotated git tag with the version (e.g., v2.3.0)
2. Use the changelog as the tag message
3. Push the tag to origin

## Step 5: Run Phase 200 Export

1. Run `uv run python 200_export_full_release/export_releases.py --verbose`
2. Verify both packages were created successfully:
   - SolidWorks.Interop.xmldoc.zip
   - SolidWorks.Interop.llms.zip

## Step 6: Prepare Release Artifacts

1. Copy and rename the packages for GitHub release:
   - Copy `200_export_full_release/output/SolidWorks.Interop.xmldoc.zip` to `SolidWorks.Interop.xmldoc.v{version}.zip`
   - Copy `200_export_full_release/output/SolidWorks.Interop.llms.zip` to `SolidWorks.Interop.llms.v{version}.zip`
2. Create these versioned copies in a temporary location or the output directory

## Step 7: Create GitHub Release

1. Use `gh release create` to create the GitHub release
2. Title: "v{version}"
3. Body: The generated changelog
4. Attach the versioned zip files:
   - `SolidWorks.Interop.xmldoc.v{version}.zip`
   - `SolidWorks.Interop.llms.v{version}.zip`
5. Mark as latest release
6. Clean up the temporary versioned copies after upload

## Step 8: Summary

Provide a summary of what was done:
- Commits pushed
- Tag created
- Packages built
- GitHub release URL

## Important Notes

- ALWAYS ask for confirmation before creating tags or releases
- Ensure all tests pass before shipping a release
- Verify the package sizes are reasonable
- Double-check the version number before proceeding
- Make sure you're on the main branch
