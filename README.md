# UNESCO World Heritage Knowledge Graph (WHS)

Permanent identifiers for the UNESCO World Heritage knowledge graph:
sites (`/whs/site/{id}`) and danger-listing events (`/whs/danger/{id}-{n}`),
as described in the paper *WHS-KG: A FAIR Linked Data Resource for the UNESCO
World Heritage List, Built with a Data-Driven Metadata Application Profile*.

## What is here (version 2.0)

| Folder | Content |
|---|---|
| `docs/` | Data dumps (`whs.ttl`, `whs.nt`), VoID/DCAT description, landing page, **profile documentation [`docs/PROFILE.md`](docs/PROFILE.md)** |
| `vocab/` | WHS element set `https://w3id.org/whs/terms/` (refinements of DCMI Terms) |
| `pipeline/` | Reproducible pipeline and SHACL shapes (`whs-shapes.ttl`) |
| `alignment/` | RDFS/OWL alignment axioms, SSSOM mapping set, CIDOC CRM view (`crm-view.rq`) |
| `queries/` | SPARQL queries for the competency questions of the paper |
| `endpoint/` | Deployment of the public SPARQL endpoint (Fuseki) and w3id rules |

SPARQL endpoint: ENDPOINT-URL-TO-FILL

See [`CHANGES.md`](CHANGES.md) for what changed from version 1.0.

Data and pipeline: https://github.com/marianamalta/whs-kg

## Maintainers

- Mariana Curado Malta, INESC TEC / Universidade do Porto
  (mariana.c.malta@inesctec.pt, GitHub: @marianamalta)
