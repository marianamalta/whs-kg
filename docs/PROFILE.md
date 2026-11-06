# WHS Metadata Application Profile (MAP) — version 2.0

User documentation of the profile used by the UNESCO World Heritage knowledge
graph (WHS-KG): what each entity and property means, which values are allowed,
and how to query it. The profile follows the Singapore Framework for Dublin
Core Application Profiles; its machine-actionable form is the SHACL shapes
graph [`pipeline/whs-shapes.ttl`](../pipeline/whs-shapes.ttl).

| | |
|---|---|
| Profile URI | `https://w3id.org/whs/profile` |
| Element set | `https://w3id.org/whs/terms/` ([`vocab/whs-terms.ttl`](../vocab/whs-terms.ttl)) |
| Shapes | `https://w3id.org/whs/shapes/` ([`pipeline/whs-shapes.ttl`](../pipeline/whs-shapes.ttl)) |
| Alignment | [`alignment/`](../alignment/) — RDFS/OWL axioms, SSSOM mapping set, CIDOC CRM view |
| Licence | CC BY 4.0 (documentation, element set, data); MIT (code, shapes) |

## 1. Functional requirements

The profile must let a consumer (i) identify every property on the World
Heritage List by a persistent URI traceable to the official record; (ii)
retrieve its names, descriptions and justification in the official languages;
(iii) know when it was inscribed, under which criteria, where it is, and in
which State(s) Party and region; (iv) know when, and for which type of danger,
it was on the List of World Heritage in Danger; and (v) link it to Wikidata,
Getty TGN and the UNESCO Thesaurus. Use cases and competency questions: see
the paper (Section 3) and [`queries/`](../queries/).

## 2. Vocabulary strategy

* **Primary target vocabulary: DCMI Metadata Terms.** Every attribute that a
  DCMI term can carry uses that term.
* **Local refinements (`whs:`) only where DCMI has no term with the needed
  meaning**, each declared `rdfs:subPropertyOf` a DCMI term. A DCMI-only
  consumer that applies RDFS entailment (or reads the pre-computed
  `graph/entailed`) sees a plain DCMI description.
* **Secondary vocabularies only where DCMI has no term at all:** W3C Basic Geo
  (coordinates), DBpedia ontology (area), schema.org (version, `sameAs`),
  Wikidata (criteria), CIDOC CRM (the two entity classes and the link to danger
  events).
* **Value vocabularies:** Getty TGN (States Parties), WHS region scheme
  (SKOS, mapped to the UNESCO Thesaurus), UNESCO Thesaurus (danger types), Wikidata (the ten criteria). Syntax encoding
  schemes: ISO 639 language tags, EDTF (Library of Congress Extended
  Date/Time Format).

## 3. Domain model

```
            whs:criterionJustification            crm:P12i_was_present_at
 CriterionJustification  <──────  Site (crm:E18_Physical_Thing)  ──────>  Danger Listing (crm:E5_Event)
 (whs:CriterionJustification)        │                                    dcterms:subject → danger type
  dcterms:subject → criterion        ├─ whs:stateParty → TGN nation        dcterms:temporal → EDTF interval(s)
  whs:justification "..."@lang       ├─ whs:region     → WHS region (SKOS)
                                     ├─ wdt:P2614      → Wikidata criterion item
                                     └─ schema:sameAs  → Wikidata item
```

URI patterns:

| Resource | Pattern | Example |
|---|---|---|
| Site | `https://w3id.org/whs/site/{id_no}` | `site/755` |
| Danger listing | `https://w3id.org/whs/danger/{id_no}-{n}` | `danger/366-1` |
| Criterion justification | `https://w3id.org/whs/justification/{id_no}-{criterion}` | `justification/755-4` |

## 4. Description set profile

### Site — `crm:E18_Physical_Thing`

`E18` rather than `E27 Site` because the List contains natural and mixed
properties and `E27` is defined for areas shaped by human activity.

| Attribute | Property | Value | Card. | Notes |
|---|---|---|---|---|
| Identifier | `dcterms:identifier` | `xsd:integer` | 1 | Official `id_no`. |
| Official record | `dcterms:source` | IRI | 1 | `https://whc.unesco.org/en/list/{id_no}`. **New in 2.0.** |
| Version | `schema:version` | `xsd:integer` ≥ 1 | 0–1 | From the UNESCO suffix: rev = 1, bis = 2, ter = 3, quater = 4, quinquies = 5. Absent = original entry (version 0). |
| Name | `dcterms:title` | `rdf:langString` | 1–n | One per language (en, fr, es, ru, ar, zh). |
| Short description | `dcterms:description` | `rdf:langString` | 0–n | One per language. |
| Justification | `whs:justification` ⊑ `dcterms:description` | `rdf:langString` | 0–n | Statement of Outstanding Universal Value (en, fr). **Replaces `schema:description` (1.0).** |
| Criterion justification | `whs:criterionJustification` | IRI → CriterionJustification | 0–n | Only when the official text is segmented by criterion. **New in 2.0.** |
| Date inscribed | `dcterms:dateAccepted` | EDTF (`YYYY` or `YYYY-MM-DD`) | 1 | |
| Secondary date | `dcterms:date` | EDTF | 0–n | Later official changes (extensions, etc.). |
| Latitude / longitude | `geo:lat` / `geo:long` | `xsd:decimal` | 0–1 | WGS84, decimal degrees; representative point. |
| Area | `dbo:areaTotal` | `xsd:decimal`, **m²** | 0–1 | Inscribed core area (not buffer zone). Source hectares × 10 000. **1.0 used `xsd:double` in hectares.** |
| Criterion | `wdt:P2614` | Wikidata item | 1–n | `wd:Q23038972` (i), `Q23038976` (ii), `Q23038977` (iii), `Q23038978` (iv), `Q23038979` (v), `Q23038980` (vi), `Q23038981` (vii), `Q23038983` (viii), `Q23038985` (ix), `Q23038986` (x). |
| State Party | `whs:stateParty` ⊑ `dcterms:spatial` | Getty TGN IRI | 1–n | Repeated for transboundary properties. **Replaces `edm:country` (1.0).** |
| Region | `whs:region` ⊑ `dcterms:spatial` | WHS region IRI | 1–n | One of the five concepts of the WHS region scheme ([`vocab/whs-regions.ttl`](../vocab/whs-regions.ttl)), mapped to the UNESCO Thesaurus. **Replaces bare `dcterms:spatial` with `mt7.x` URIs (1.0), which did not dereference.** |
| Same as | `schema:sameAs` | Wikidata IRI | 0–1 | Reconciled via P757. Not `owl:sameAs`, to avoid merging statements. |
| Danger listing | `crm:P12i_was_present_at` | IRI → Danger Listing | 0–n | One per danger type. |

Not materialised (derivable, design principle P3): **category**
(Cultural/Natural/Mixed, from the criteria — see `queries/cq06`) and
**transboundary** (more than one `whs:stateParty` — see `queries/cq05`).

### Danger Listing — `crm:E5_Event`

| Attribute | Property | Value | Card. | Notes |
|---|---|---|---|---|
| Danger type | `dcterms:subject` | danger-type VES | 1 | See below. |
| Period | `dcterms:temporal` | EDTF interval | 1–n | `2002/2006` (closed), `1986/..` (still on the List). |

Danger-type VES (excerpt of the UNESCO Thesaurus):

| Label | Concept | Note |
|---|---|---|
| War | `unescot:concept8105` | Armed conflict, civil unrest |
| Pollution | `unescot:concept6445` | |
| Natural hazards | `unescot:concept4772` | |
| Materials | `unescot:concept640` | Proxy: no Thesaurus concept for material deterioration |
| Urbanization | `unescot:concept448` | Urbanization and development pressure |

### Criterion Justification — `whs:CriterionJustification`

| Attribute | Property | Value | Card. |
|---|---|---|---|
| Criterion | `dcterms:subject` | Wikidata criterion item | 1 |
| Text | `whs:justification` | `rdf:langString` | 1–n |

## 5. Using the profile

* **Query the endpoint** (default graph = union of all graphs) with the
  prefixes in [`queries/`](../queries/). Ready-made queries for the competency
  questions of the paper: `cq01`–`cq11`.
* **If you only know DCMI Terms**: query `dcterms:spatial`,
  `dcterms:description` — the entailed graph exposes the `whs:` refinements
  under their DCMI super-properties (`queries/cq12`).
* **If you only know CIDOC CRM**: query graph
  `https://w3id.org/whs/graph/crm`, produced by
  [`alignment/crm-view.rq`](../alignment/crm-view.rq) (appellations,
  identifiers, E53 places with WKT, E54 dimensions, E52 time-spans; one
  sub-event per danger period; `queries/cq13`).
* **Validate your own data against the profile**:
  `pyshacl -s pipeline/whs-shapes.ttl -e vocab/whs-terms.ttl your-data.ttl`.

## 6. Versioning

The profile, the element set and the shapes share a semantic version
(`owl:versionInfo`). Changes from 1.0 to 2.0 are listed in
[`CHANGES.md`](../CHANGES.md). Terms are never deleted from the `whs:`
namespace; withdrawn terms will be marked `owl:deprecated true`.
