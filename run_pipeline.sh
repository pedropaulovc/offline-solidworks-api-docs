#!/usr/bin/env bash
#
# Full pipeline orchestrator for the offline SOLIDWORKS API docs project.
#
# Runs every phase in order (10 -> 200) against the live 2026 docs, stopping on
# the first hard failure. Each phase's main step is fatal (the run aborts);
# validation steps are advisory (logged, never fatal). All output is tee'd to a
# timestamped log under ./logs/.
#
# Usage:
#   ./run_pipeline.sh                 # run the whole pipeline
#   ./run_pipeline.sh --from 70       # resume starting at phase 70
#
# Crawl phases (10/30/70/100) support --resume internally; re-running a crawl
# phase from scratch re-crawls it.

set -uo pipefail

cd "$(dirname "$0")"

FROM="0"
if [[ "${1:-}" == "--from" && -n "${2:-}" ]]; then
  FROM="$2"
fi

mkdir -p logs
LOG="logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
echo "Pipeline log: $LOG"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

# run <phase-number> <description> <command...>  -- fatal on non-zero exit
run() {
  local phase="$1"; shift
  local desc="$1"; shift
  if (( phase < FROM )); then
    log "SKIP  phase $phase ($desc) [--from $FROM]"
    return 0
  fi
  log "===== phase $phase START: $desc ====="
  if "$@" >>"$LOG" 2>&1; then
    log "===== phase $phase OK: $desc ====="
  else
    local rc=$?
    log "##### phase $phase FAILED (rc=$rc): $desc -- aborting. See $LOG"
    exit "$rc"
  fi
}

# validate <phase-number> <command...>  -- advisory, never fatal
validate() {
  local phase="$1"; shift
  if (( phase < FROM )); then return 0; fi
  log "----- phase $phase validation -----"
  if "$@" >>"$LOG" 2>&1; then
    log "----- phase $phase validation passed -----"
  else
    log "----- phase $phase validation reported issues (advisory) -----"
  fi
}

PY="uv run python"

log "Starting full pipeline refresh (FROM=$FROM)"

# Phase 10 - crawl TOC pages
run 10 "crawl TOC pages"           $PY 10_crawl_toc_pages/run_crawler.py
validate 10                        $PY 10_crawl_toc_pages/validate_crawl.py

# Phase 20 - extract types from TOC (drives the phase 30 crawl)
run 20 "extract types"             $PY 20_extract_types/extract_members.py
validate 20                        $PY 20_extract_types/validate_extraction.py

# Phase 30 - crawl type member pages
run 30 "crawl type members"        $PY 30_crawl_type_members/run_crawler.py
validate 30                        $PY 30_crawl_type_members/validate_crawl.py

# Phase 35 - crawl reference pages the source TOC never exposes (its "Enumerations"
# nodes return the Interfaces list for several namespaces), seeded from the links
# in what phases 10/30 already crawled.
run 35 "crawl referenced types"    $PY 35_crawl_referenced_types/run_crawler.py

# Phase 20 again - api_members.xml feeds phases 90/120, so it has to include the
# types phase 35 just discovered. Pure local re-extraction over both input dirs.
# Numbered 36, not 20: `run` skips anything below --from, so numbering this 20
# would drop the refresh from exactly the `--from 35` resume that needs it.
run 36 "extract types (+phase 35)" $PY 20_extract_types/extract_members.py
validate 36                        $PY 20_extract_types/validate_extraction.py

# Phase 40 - extract type details (descriptions, examples, remarks)
run 40 "extract type details"      $PY 40_extract_type_details/extract_type_info.py
validate 40                        $PY 40_extract_type_details/validate_extraction.py

# Phase 50 - extract member details
run 50 "extract member details"    $PY 50_extract_type_member_details/extract_member_details.py
validate 50                        $PY 50_extract_type_member_details/validate_extraction.py

# Phase 60 - extract enum members
run 60 "extract enum members"      $PY 60_extract_enum_members/extract_enum_members.py

# Phase 70 - recover orphan examples from legacy versions, then crawl examples
run 70 "harvest legacy examples"   $PY 70_crawl_examples/harvest_legacy_examples.py
run 70 "crawl examples"            $PY 70_crawl_examples/run_crawler.py
validate 70                        $PY 70_crawl_examples/validate_crawl.py

# Phase 80 - parse examples
run 80 "parse examples"            $PY 80_parse_examples/parse_examples.py
validate 80                        $PY 80_parse_examples/validate_parse.py

# Phase 90 - export XMLDoc
run 90 "export xmldoc"             $PY 90_export_xmldoc/generate_xmldoc.py
validate 90                        $PY 90_export_xmldoc/validate_xmldoc.py

# Phase 100 - crawl programming guide
run 100 "crawl programming guide"  $PY 100_crawl_programming_guide/run_crawler.py
validate 100                       $PY 100_crawl_programming_guide/validate_crawl.py

# Phase 110 - extract programming guide to markdown
run 110 "extract docs markdown"    $PY 110_extract_docs_md/extract_markdown.py
validate 110                       $PY 110_extract_docs_md/validate_extraction.py

# Phase 115 - crawl /api pages referenced but not covered by earlier phases, then extract
run 115 "crawl referenced pages"   $PY 115_crawl_referenced_pages/run_crawler.py
run 115 "extract referenced md"    $PY 115_crawl_referenced_pages/extract_markdown.py

# Phase 35 second pass - phases 70/100/115 are seed sources for the referenced-type
# crawl too, and none of them existed when it first ran. --resume fetches only what
# their pages reference beyond the first pass (4 pages on the 2026 corpus), so the
# local re-extractions below fold it into the exports before phase 120 reads them.
run 116 "crawl referenced types (pass 2)"   $PY 35_crawl_referenced_types/run_crawler.py --resume
run 117 "extract types (+pass 2)"           $PY 20_extract_types/extract_members.py
run 117 "extract type details (+pass 2)"    $PY 40_extract_type_details/extract_type_info.py
run 117 "extract member details (+pass 2)"  $PY 50_extract_type_member_details/extract_member_details.py
run 117 "extract enum members (+pass 2)"    $PY 60_extract_enum_members/extract_enum_members.py
run 117 "export xmldoc (+pass 2)"           $PY 90_export_xmldoc/generate_xmldoc.py
validate 117                                $PY 90_export_xmldoc/validate_xmldoc.py

# Phase 120 - export LLM-friendly docs (flat enum files)
run 120 "export llm docs"          $PY 120_export_llm_docs/export_pipeline.py
validate 120                       $PY 120_export_llm_docs/validate_export.py

# Phase 200 - build versioned release bundle (xmldoc + llms zips)
run 200 "export full release"      $PY 200_export_full_release/export_releases.py
validate 200                       $PY 200_export_full_release/validate_releases.py

log "PIPELINE COMPLETE"
