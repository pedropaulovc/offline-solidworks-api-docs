# Phase 115 — Crawl Referenced Pages

Closes the "dead link" gap left by the TOC-driven crawls. Phases 10/30/100 only
fetch pages reachable from the `expandToc` table of contents, so any page under
`/2027/english/api/` (`SOLIDWORKS_API_BOUNDARY`) that the docs *link to* but that isn't in a TOC (e.g.
`swconst` System Options / Document Properties setting pages, a handful of
`sldworksapiprogguide/Miscellaneous` topics) is never crawled and surfaces in the
Phase 120 export as a bare external link.

This phase crawls those pages so they ship in the bundle and cross-link as files.

## How it works

1. **Seed** (`link_targets.build_seed`): scan the corpus for `/api` page links and
   keep those the bundle doesn't already ship. Two source kinds:
   - *Derived files* (phases 40/50/60 XML + Phase 110 guide markdown) — absolute
     `<see href>` URLs only; they have no origin page to resolve against.
   - *Crawled help-text HTML* (phases 10/30/70/100/115), each paired with its own
     page URL so **relative** `href`s resolve. This is the ground truth for what the
     docs link to. Extraction keeps only absolute `<see href>` URLs, so a page
     linked the way multi-module examples link their sibling code pages —
     `href="DimXpert_Main_Module_CSharp.htm"` — was invisible to a scan of the
     derived files alone and shipped as a dead link.

   Generated `~` reference pages are dropped here, as in the closure: raw HTML links
   thousands of them and they are phase 20/30's territory.

   CHM aliases (`ms-its:swconst.chm::/DP_Dimensions.htm`,
   `sldworksAPIProgGuide.chm::/OVERVIEW/Type_Libraries.htm`) resolve to the page they
   name, in the CHM's folder (`swconst/`, `sldworksapiprogguide/`), via
   `shared/chm_aliases.py`. Phases 40/50/60 resolve them the same way in the `<see
   href>` and example URLs they extract.
2. **Closure** (`solidworks_scraper/spiders/referenced_spider.py`): crawl each seed
   page, follow its in-page `/api` links, and repeat until no new pages appear. The
   set of already-crawled pages is pre-seeded as "seen", so the closure stops at the
   corpus boundary instead of re-crawling the thousands of reference pages.
3. **Extract** (`extract_markdown.py`): convert each crawled page to Markdown under
   `output/markdown/<path-under-api>.md`, writing a Phase-110-compatible
   `metadata/files_created.jsonl` (`original_url` → `markdown_path`). CHM-alias links
   become links relative to the page, like its other relative links.

Phase 120 reads that manifest as a second guide source, copies the Markdown into
the bundle `docs/`, and resolves the matching `<see href>` references to relative
file links.

## Run

```bash
uv run python 115_crawl_referenced_pages/run_crawler.py      # live crawl (--resume to continue)
uv run python 115_crawl_referenced_pages/extract_markdown.py # HTML -> Markdown
uv run pytest 115_crawl_referenced_pages/tests/ -v
```

## Notes

- Crawled HTML is copyrighted by Dassault Systèmes and gitignored (`output/`);
  users re-crawl themselves, as with every crawl phase.
- "Already ships" means exported as a doc (Phase 110/115 `files_created.jsonl`) *or*
  crawled by Phase 70, whose example pages Phase 120 emits as `examples/*.md`. Miss
  the latter and the raw-HTML scan seeds ~2800 example pages the bundle already has.
- A page referenced under `/api` that is *already* crawled by another phase but not
  exported as a doc (e.g. `FunctionalCategories-sldworksapi.html`), or that the server
  answers with its "This page cannot be found." page (a dead link), stays an external
  link — it is out of scope for this closure, not un-crawled. Such a page is refetched
  a minute later (the server shows the same page during brief outages) and then
  skipped and listed under `dead_links` in `metadata/crawl_stats.json`. Any other page
  without `helpText` fails the crawl.
- The metadata committed on `main` predates CHM-alias resolution: its
  `crawl_stats.json` reports 63 skipped pages, 58 of them unresolved aliases. A crawl
  with the current code (as regenerated for release v4.0.0, PR #37) skips 6, each of
  which returned the not-found page when re-fetched (2026-11-16):
  - `help_list.htm`, `sldworksapi/DP_ImageQuality.htm`,
    `swconst/DP_Annotations-EdgeSymbols.htm`, `swconst/DP_Annotations-TransitionSymbols.htm`
    and `toolboxapi/DifferencesBetweenUnManagedAndC++CLI.html`, which the earlier run
    also reported;
  - `swconst/FileSaveAsSMGOptions.htm`, which no XML links. Its only link is a CHM
    alias on `swconst/SO_Export.htm` (`swconst.chm::/FileSaveAsSMGOptions.htm`), so
    the crawl requests this URL only now that aliases resolve.

  The 58 aliases resolve to pages the bundle already ships (55) or to the three
  image-only pages below.
- A crawled page with no text, only images
  (`sldworksapiprogguide/Miscellaneous/FreeFormCurves.htm`,
  `Geometric_Tolerance_Symbol_Libraries.htm`, `FeatureManager__InsertGussetFeature_image.htm`)
  is not written: the bundle ships no images, so it would be a single dangling
  `![](x.gif)`. Its links stay on the help page, which shows the image. Extraction
  lists such pages under `image_only_pages` in `metadata/extraction_summary.json`.
- Extraction clears `output/markdown/` first, so a page that left the closure does not
  keep its old file. Phases 90 and 120 also ship only the pages
  `files_created.jsonl` lists.
