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
| 3b. Curate (optional) | `curate.py` | `authority/curation_todo.txt`, `authority/danger_types_todo.csv` |
| 4. Build & validate | `build_graph.py` | `out/whs.ttl`, `out/whs.nt`, `out/stats.txt`, SHACL report |
| 4b. Ablation (optional) | `ablate_cleaning.py` | prints SHACL violations with cleaning on vs. off (paper Table 6) |
| 5. Diff (optional) | `diff.py` | `out/changelog-<date>.txt`, `out/delta-<date>.ru` (SPARQL UPDATE patch) |

`curate.py` is a helper for the editorial work, not a build step: it reads the
cleaned data plus the authority files and lists everything that still blocks a
fully conformant graph — danger-listed sites without a type, ISO codes without a
Getty TGN id, and region strings missing from `regions.csv`. It also writes
`danger_types_todo.csv`, a fill-in sheet pre-populated with every danger-listed
site (complete the `label` column, then replace `danger_types.csv` with it).
The graph builds without it; run it after each `reconcile.py` to see what needs
hand-curation before the next `build_graph.py`.

`ablate_cleaning.py` is the reproducibility script for the paper's ablation
study (Table 6). It rebuilds the graph directly from the raw export with the
cleaning operations disabled — but reconciliation and the MAP mapping held fixed
— and validates both that and the cleaned `out/whs.ttl`, printing a before/after
count of SHACL violations broken down by constraint. It reuses `build_graph.py`,
so run it from this folder after `build_graph.py` has produced `out/whs.ttl`.

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
    python curate.py        # optional: checklist of authority gaps to hand-fill
    python build_graph.py   # writes Turtle/N-Triples, validates, prints stats
    python ablate_cleaning.py  # optional: SHACL violations, cleaning on vs. off (Table 6)
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

## Licence

- **Code** (the pipeline scripts and SHACL shapes): MIT — see [`LICENSE`](LICENSE).
- **Data** (the generated graph, authority files, and cleaned snapshots):
  Creative Commons Attribution 4.0 (CC BY 4.0) — see [`DATA_LICENSE.md`](DATA_LICENSE.md).

The records are derived from the official UNESCO World Heritage Centre
syndication export and are not endorsed by UNESCO.

## How to cite

See [`CITATION.cff`](CITATION.cff), or cite the accompanying paper:
*Building an Interoperable Knowledge Graph of the UNESCO World Heritage Sites*
(Santos, Plácido, and Curado Malta, 2026).
