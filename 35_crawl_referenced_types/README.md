# Phase 35 — Crawl Referenced Types

Closes the gap left by TOC-driven discovery: reference pages that exist, are linked
from the docs, and belong to assemblies this project ships — but that `expandToc`
never lists, so phases 10/30 never fetch them.

## Why the TOC misses them

The source TOC is defective. For several namespaces the **"Enumerations" node
returns the *Interfaces* list verbatim**:

```bash
# Both return the same 51 IDimXpert* interfaces; neither yields a single _e page.
curl -s 'https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=2.4.1'  # "Interfaces"
curl -s 'https://help.solidworks.com/expandToc?version=2026&language=english&product=api&queryParam=?id=2.4.2'  # "Enumerations"
```

Confirmed for ids `2.3`, `2.4`, `2.6`, `2.7`. Only `swconst` (2.10) and
`swcommands` (2.11) serve real enum children — which is exactly why phase 60 only
ever produced `swconst`/`swcommands`/`swbrowser` enums, and why an enum like
`swDimXpertGtolType_e` was referenced by `IDimXpertPart::InsertGtol` but shipped
nowhere.

Since the TOC cannot reach these pages, discovery has to come from the links. Same
technique as phase 115, opposite side of the `~` test: phase 115 crawls *doc* pages
and refuses to enter the reference tree; this phase crawls only the reference tree.

## How it works

1. **Seed** (`reference_targets.build_seed`): scan the crawled help-text HTML of
   phases 10/30/70/100/115 for `Assembly~Namespace.Type[~Member]` links, drop the
   ones already crawled, and keep the rest.
2. **Scope**: bounded to assemblies the pipeline already ships, derived from phase
   10/30's crawl manifests rather than hardcoded — adding a root to phase 10's
   `TOC_ROOT_IDS` widens this crawl automatically. The docs also link into reference
   trees this project does not crawl at all (Routing, PDM, FeatureWorks, …, each its
   own `expandToc` root); those are skipped and **counted per assembly in
   `crawl_stats.json`**, so a growing external surface stays visible.
3. **Completion**: a newly discovered *type* is fetched together with its
   `_members` companion page, and the member pages linked from that list. Phase 20
   builds its type list from `*_members*` pages and phase 50 reads member pages, so
   without this the type would arrive as an empty stub. Only member-list pages
   expand; every other reference page is a leaf here.
4. **Output**: `output/html/<assembly>/<page>.html`, the same per-assembly layout
   phases 10/30 use, so the extraction phases read it as one more input directory.

## Wiring

Phases 20/40/50/60 take `--input-dirs` (plural) and default to their original
directory **plus** this phase's output. Note phase 20 matches `*_members*.html`:
phase 10 appends a query hash (`..._members_1a2b3c4d_....html`) while this phase
crawls the query-less URL (`..._members.html`).

Runs after phase 30 (it seeds from phase 30's member pages) and before 40/50/60.
Phase 20 re-runs after it so `api_members.xml` — which phases 90 and 120 consume —
includes the newly discovered types.

## Run

```bash
uv run python 35_crawl_referenced_types/run_crawler.py      # live crawl (--resume to continue)
uv run pytest 35_crawl_referenced_types/tests/ -v
```

## Notes

- Crawled HTML is copyrighted by Dassault Systèmes and gitignored (`output/`);
  users re-crawl themselves, as with every crawl phase.
- A referenced page whose `helpText` is empty is a source-side stub (the site
  answers 200 for pages that do not exist). Those are skipped, not failures.
