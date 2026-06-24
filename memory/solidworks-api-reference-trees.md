---
name: solidworks-api-reference-trees
description: SolidWorks help hosts 16 separate API reference trees (TOC ids 2-17); how to add one to the crawl pipeline
metadata:
  type: project
---

The SolidWorks API help (`help.solidworks.com/2026/english/api/SWHelp_List.html`) is **16 separate
API references**, each a top-level `expandToc` node `id=2..17` under the same `/2026/english/api/`
boundary, each with its own assembly:

- `id=2` core SOLIDWORKS API (10 assemblies: sldworks, swconst, swcommands, swpublished, swdimxpert,
  swmotionstudy, swscanto3d, sw3dprinter, swhtmlcontrol, dsgnchk)
- `id=13` Toolbox API (`swbrowser`, `sldtoolboxconfigureaddin`) — added 2026-06-23
- Others (not yet crawled): Electrical(3), PDM Pro(4) + PDM web(5), FeatureWorks(6), Costing(7),
  Document Manager(8), Inspection(9), Routing(10), Simulation(11), Sustainability(12),
  Utilities(14), Visualize(15), eDrawings(16), DraftSight(17).

**The pipeline is assembly-generic** — no hardcoded assembly list anywhere. Phase 90
(`data_merger.py`) groups by the `Assembly`/`Namespace` it reads from page data; phase 30 iterates
*all* `Type` elements. So **adding a reference = appending its TOC root id to `TOC_ROOT_IDS`** in
`10_crawl_toc_pages/solidworks_scraper/spiders/api_docs_spider.py`, then re-running the pipeline
(10→20→30→40/50/60→70/80→90→120→200). Everything else flows through unchanged.

Gotchas observed adding Toolbox:
- `DOWNLOAD_DELAY` is **0.1s** (not 2s as CLAUDE.md's "2-second delays" claims) — full crawl is
  ~10-15 min (phase 10, 2250 pages) + ~8 min (phase 30, ~11.5k member pages), not hours.
- Phase 10/30 `--resume` does NOT skip already-downloaded URLs; it re-crawls. For a clean,
  consistent snapshot run **fresh** (no `--resume`), which clears + regenerates metadata.
- `20_extract_types/metadata/api_members.xml` is gitignored (reproducible intermediate); the
  committed deliverables are phases 40/50/60/90/120/200 metadata.
- A new reference may have no Functional Categories node and no linked example pages (Toolbox had
  neither) — the exporters tolerate uncategorized/example-less types.

Related: [[bundle-discoverability-fix]].
