# Phase 115 — Crawl Referenced Pages

Closes the "dead link" gap left by the TOC-driven crawls. Phases 10/30/100 only
fetch pages reachable from the `expandToc` table of contents, so any page under
`/2026/english/api/` that the docs *link to* but that isn't in a TOC (e.g.
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
2. **Closure** (`solidworks_scraper/spiders/referenced_spider.py`): crawl each seed
   page, follow its in-page `/api` links, and repeat until no new pages appear. The
   set of already-crawled pages is pre-seeded as "seen", so the closure stops at the
   corpus boundary instead of re-crawling the thousands of reference pages.
3. **Extract** (`extract_markdown.py`): convert each crawled page to Markdown under
   `output/markdown/<path-under-api>.md`, writing a Phase-110-compatible
   `metadata/files_created.jsonl` (`original_url` → `markdown_path`).

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
  exported as a doc (e.g. `FunctionalCategories-sldworksapi.html`), or that returns
  no `helpText` (a source-side stub, e.g. `sldworksapi/DP_ImageQuality.htm`), stays
  an external link — it is out of scope for this closure, not un-crawled.
