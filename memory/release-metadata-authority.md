---
name: release-metadata-authority
description: Which committed metadata file holds the authoritative type/example counts when cutting a release, and why some manifests look stale
metadata:
  type: project
---

When cutting a release, the committed `120_export_llm_docs/metadata/export_summary.json`
and `200_export_full_release/metadata/export_manifest.json` can lag the actual build —
they've been generated on different machines/runs (e.g. a Linux cloud run with
`/home/pedro/...` paths, 1575 types, 10 xmldoc assemblies) and not regenerated since.

The authoritative, up-to-date counts live in `90_export_xmldoc/metadata/generation_summary.json`
(committed, Windows paths). As of v3.6.0 the correct figures are **12 assemblies, 1525 types,
3633 properties, 8298 methods, 10468 enum members, 2839 examples (623 recovered C#/VB.NET)**.
Phase 120's `total_types` = regular types (565) + enums (960) = 1525, and must match phase 90.

**Why:** pipeline intermediate data (phases 20–60 XML, 70 HTML) is gitignored and lives only
locally; a machine's local crawl can diverge from what a past release shipped. A 1575→1525
"regression" scare on rebuild is a stale `export_summary.json`, not lost data — confirm by
checking your rebuild reproduces `generation_summary.json` exactly.

**How to apply:** before packaging, re-run 80→90→120 and verify phase 90's rebuild matches the
committed `generation_summary.json` to the integer. If it does, local data is canonical — proceed.
Phase 115's regenerated metadata (`urls_crawled.jsonl` etc.) is pure platform noise on Windows
(backslash paths, reordering, identical `content_hash`) — revert it, don't commit. See
[[solidworks-api-reference-trees]] and [[bundle-discoverability-fix]].
