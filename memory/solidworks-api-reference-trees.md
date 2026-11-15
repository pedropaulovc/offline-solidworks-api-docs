---
name: solidworks-api-reference-trees
description: SolidWorks help hosts many API reference trees as top-level expandToc nodes (2027 ids 0-70, flattened); how to add one to the crawl pipeline
metadata:
  type: project
---

The SolidWorks API help (`help.solidworks.com/2027/english/api/SWHelp_List.html`) hosts **many
separate API references** (core, Electrical, PDM, FeatureWorks, Costing, Document Manager, ...),
all served as top-level `expandToc` nodes (`parentId=-1`) under the same `/2027/english/api/`
boundary. The doc year lives only in `shared/constants.py` (`SOLIDWORKS_API_VERSION`).

## 2026 -> 2027: the TOC was flattened

In 2026 each reference was ONE wrapper node (`id=2` core API with children `2.0` Functional
Categories, `2.1` Release Notes, `2.2..2.11` namespaces; `id=13` Toolbox; ids `2..17` = 16
references). 2027 removed the per-product wrappers: their former children are now top-level
nodes with consecutive ids, so **TOC root ids are not stable across versions** and must be
re-mapped on every yearly bump (probe `expandToc?version=<year>&language=english&product=api&queryParam=?id=N`
for N = 0.. with a browser User-Agent; the default curl UA gets 403).

2027 top-level ids (probed 2026-11-15):

- `0` Programming Guide Welcome page, `1` Programming Guide "Getting Started" (Phase 100 crawls id=1)
- **Core SOLIDWORKS API (crawled)**: `2` Functional Categories (leaf), `3` Release Notes (leaf),
  `4` SolidWorks.Interop.sldworks Namespace (`4.0` Overview, `4.1` Interfaces, `4.2` Delegates,
  `4.3..4.11` swmotionstudy, swdimxpert, swpublished, sw3dprinter, dsgnchk, swhtmlcontrol,
  swscanto3d, swconst, swcommands)
- **Toolbox API (crawled)**: `44` Welcome, `45` Release Notes, `46` Getting Started,
  `47` sldtoolboxconfigureaddin Namespace, `48` swbrowser Namespace
- Not crawled: Electrical `5`; PDM Pro `6..13` + PDM web service `14`; FeatureWorks `15..18`;
  Costing `19..22`; Document Manager `23..26`; Inspection `27..30`; Routing `31..34`;
  Simulation `35..39`; Sustainability `40..43`; Utilities `49..52`; Visualize `53..56`;
  eDrawings `57..63`; DraftSight `64..70`.

Phase 10 `TOC_ROOT_IDS` for 2027 = `["2", "3", "4", "44", "45", "46", "47", "48"]`. Leaf roots
are fine: a root's expandToc response is the node itself (with its own `url`), so the spider
still requests its page.

**The pipeline is assembly-generic** — no hardcoded assembly list anywhere. Phase 90
(`data_merger.py`) groups by the `Assembly`/`Namespace` it reads from page data; phase 30 iterates
*all* `Type` elements. So **adding a reference = appending its TOC root ids to `TOC_ROOT_IDS`** in
`10_crawl_toc_pages/solidworks_scraper/spiders/api_docs_spider.py`, then re-running the pipeline
(10→20→30→40/50/60→70/80→90→120→200). Everything else flows through unchanged.

Gotchas observed adding Toolbox (2026):
- `DOWNLOAD_DELAY` is **0.1s** (not 2s as CLAUDE.md's "2-second delays" claims) — full crawl is
  ~10-15 min (phase 10, 2250 pages) + ~8 min (phase 30, ~11.5k member pages), not hours.
- Phase 10/30 `--resume` does NOT skip already-downloaded URLs; it re-crawls. For a clean,
  consistent snapshot run **fresh** (no `--resume`), which clears + regenerates metadata.
- `20_extract_types/metadata/api_members.xml` is gitignored (reproducible intermediate); the
  committed deliverables are phases 40/50/60/90/120/200 metadata.
- A new reference may have no Functional Categories node and no linked example pages (Toolbox had
  neither) — the exporters tolerate uncategorized/example-less types.

Related: [[bundle-discoverability-fix]].
