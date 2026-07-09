---
name: plugin-bundle-vs-release
description: How the developing-solidworks plugin bundle relates to Phase 120 output and the pipeline release; how to update the local plugin cache
metadata:
  type: project
---

The `developing-solidworks` Claude Code plugin (versioned separately, e.g. `0.8.4`) ships the **Phase 120 LLM-docs output** plus plugin-only files. Two distinct version lines:
- Pipeline releases: git tags `v3.x.0` (the `.claude/commands/ship-release.md` flow → Phase 200 zips on GitHub).
- Plugin: its own semver in `.claude-plugin/plugin.json` (unrelated to the pipeline tag).

**Plugin skills dir** (`…/plugins/cache/agent-plugins/developing-solidworks/<ver>/skills/developing-solidworks/`) =
- Phase-120-generated (replace on update): `docs/ enums/ examples/ index/ types/ README.md`
- Plugin-only (PRESERVE): `SKILL.md learnings/ scripts/ .claude-plugin/ .codex-plugin/`

To refresh the local cache with a rebuilt bundle: regenerate `120_export_llm_docs/output/`, then `rm -rf`/`cp -r` only the 6 generated items into the plugin dir; never touch the plugin-only files.

**Release ordering gotcha:** Phase 200 (`export_releases.py`) reads the version from the **latest git tag** (`git tag --sort=-v:refname`). Create + push the `vX.Y.0` tag *before* running Phase 200, or the manifests get the previous version. Then commit the regenerated `200_export_full_release/metadata/*.json` as "Update release manifests for vX.Y.0" on top of the tag (the tag points to the code commit, the manifest commit sits after it — matches history). See [[release-metadata-authority]].

The prog-guide→API-reference link resolution that motivated v3.8.0 lives in Phase 120's `_rewrite_guide_api_links` (`export_pipeline.py`); relates to [[bundle-discoverability-fix]] and [[solidworks-api-reference-trees]].
