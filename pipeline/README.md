# WHS Knowledge Graph Pipeline

Reproducible pipeline that turns the official UNESCO World Heritage syndication
export into the five-star RDF knowledge graph described in the paper
(*Building an Interoperable Knowledge Graph of the UNESCO World Heritage Sites*).

## Design

Scripts compute what is deterministic; humans curate small **authority files**
for what is editorial; the pipeline **flags gaps instead of guessing**.

| Step | Script | Output |
|------|--------|--------|
| 1. Extract | `extract.py` | `data/raw/whc-sites-<date>.csv` (dated snapshot) |
| 2. Clean (paper 4.1) | `clean.py` | `data/clean/sites.json` |
| 3. Reconcile | `reconcile.py` | `authority/*.csv` + `authority/review_needed.txt` |
| 4. Build & validate | `build_graph.py` | `out/whs.ttl`, `out/whs.nt`, `out/stats.txt`, SHACL report |
| 5. Diff (optional) | `diff.py` | `out/changelog-<date>.txt`, `out/delta-<date>.ru` (SPARQL UPDATE patch) |

## Authority files (in `authority/`)

- `wikidata_sites.csv` - id_no -> Wikidata QID, fetched deterministically via
  **P757 (World Heritage Site ID)**. Rebuilt by `reconcile.py`; review only the
  rows flagged as missing/duplicated.
- `states_tgn.csv` - ISO 3166-1 alpha-2 -> Wikidata QID -> **P1667 (Getty TGN ID)**.
  Rebuilt by `reconcile.py`; human-check once, then commit.
- `regions.csv` - the five WH regions -> UNESCO Thesaurus microthesauri
  (`mt7.x`). Hand-curated; never overwritten by scripts.
- `danger_types.csv` - id_no -> UNESCO Thesaurus threat concept. Hand-curated
  (editorial judgement, see paper Limitations); unmapped sites are emitted
  without `dcterms:subject` so that **SHACL validation reports them** as
  curation gaps.

## Setup

    # Linux/macOS
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

    # Windows (PowerShell)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Run

    python extract.py       # downloads the syndication export
    python clean.py         # applies the ten cleaning operations of 4.1
    python reconcile.py     # refreshes authority files, reports gaps
    python build_graph.py   # writes Turtle/N-Triples, validates, prints stats
    python diff.py          # optional: changelog + SPARQL UPDATE delta vs previous run

`diff.py` compares the two most recent cleaned snapshots. The full rebuild
remains the canonical dump; the delta file lets a triple store hosting the
graph be updated in place, and the changelog documents exactly what each
World Heritage Committee session changed.

`build_graph.py` prints the statistics block used in the paper's Results
section (triple count, site/danger-event counts, TGN/Wikidata link counts) and
runs pySHACL against `whs-shapes.ttl`.

## Notes

- Endpoints used: Wikidata Query Service (`query.wikidata.org/sparql`).
  Getty TGN IDs are obtained *via Wikidata* (P1667), avoiding fuzzy matching
  against Getty's own endpoint.
- Every run is a dated snapshot; re-run after each World Heritage Committee
  session to refresh the graph (paper future-work item i).
- The `rev` suffix is mapped to version 2 by default (`SUFFIX_VERSION` in
  `clean.py`); adjust if a site carries both `rev` and an ordinal suffix.
