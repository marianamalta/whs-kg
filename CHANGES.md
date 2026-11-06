# Changes

## 2.0.0 (MAP 2.0) — resubmission to ACM JOCCH

Data model (requires regenerating the graph with `pipeline/build_graph.py`):

* DCMI Metadata Terms declared as the **primary target vocabulary** of the profile.
* New element set `https://w3id.org/whs/terms/` (`vocab/whs-terms.ttl`) with
  three refinements of DCMI terms and one class:
  `whs:stateParty` ⊑ `dcterms:spatial`, `whs:region` ⊑ `dcterms:spatial`,
  `whs:justification` ⊑ `dcterms:description`, `whs:criterionJustification`
  ⊑ `dcterms:relation`, class `whs:CriterionJustification`.
* `edm:country` → `whs:stateParty` (EDM is no longer used).
* `dcterms:spatial` (region) → `whs:region`, with values from a new SKOS
  scheme of the five World Heritage regions (`vocab/whs-regions.ttl`,
  `https://w3id.org/whs/region/…`) mapped to dereferenceable UNESCO Thesaurus
  concepts; the MAP 1.0 microthesaurus URIs (`mt7.x`) did not dereference.
* `schema:description` (justification) → `whs:justification`; justifications
  segmented by criterion markers ("Criterion (ii): …") are also published as
  structured `whs:CriterionJustification` nodes.
* `dbo:areaTotal` is now `xsd:decimal` in square metres (was `xsd:double` in
  hectares), matching the DBpedia definition and avoiding exponential notation.
* **Bug fix:** criterion (i) used `wd:Q15911738` (a hydroelectric power
  station) instead of `wd:Q23038972`; affected the 264 properties meeting
  criterion (i) in release 1.x.
* New `dcterms:source` link from each site to its official page
  `https://whc.unesco.org/en/list/{id_no}`.

New resources:

* `pipeline/whs-shapes.ttl` — the SHACL shapes (missing from the 1.x repository).
* `alignment/whs-alignment.ttl` — RDFS/OWL alignment axioms.
* `alignment/whs-mappings.sssom.tsv` — SSSOM mapping set (vocabulary alignment worksheet).
* `alignment/crm-view.rq` — CONSTRUCT producing a CIDOC CRM-conformant view.
* `pipeline/build_views.py` — builds the entailed and CRM views and a TriG file for the endpoint.
* `queries/` — SPARQL queries for the competency questions.
* `endpoint/` — Fuseki deployment and proposed w3id rules for per-entity dereferencing.
* `docs/PROFILE.md` — user documentation of the profile.

Maintenance:

* `pipeline/check_update.py` + `.github/workflows/check-unesco-update.yml`:
  weekly content-based check of the UNESCO export; on change, full rebuild and
  a pull request for review.
* `.github/workflows/release.yml`: a release (and Zenodo version DOI) when a
  reviewed update is merged; `endpoint/vm-update.sh` reloads the endpoint.
* Properties removed from the List keep resolvable URIs (named graph
  `.../graph/removed`, `dcterms:valid` interval).
* `pipeline/run_queries.py`: runs the competency questions of the paper.

## 1.0.1 — initial submission
