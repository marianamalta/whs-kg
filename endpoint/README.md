# Deploying the public WHS SPARQL endpoint

This folder contains a minimal, reproducible deployment of a read-only public
SPARQL endpoint for the WHS knowledge graph, based on **Apache Jena Fuseki**
(Docker). Use it on an institutional server (e.g., a VM at INESC TEC or FEUP)
or any host with Docker.

## 1. Build the data to load

From `pipeline/`:

    python build_graph.py     # core graph  -> out/whs.ttl, validated with SHACL
    python build_views.py     # entailed + CRM views -> out/whs-all.trig

Copy `pipeline/out/whs-all.trig` into `endpoint/data/`.

## 2. Start the endpoint

> The paths to the TDB loader and the Fuseki server inside the container
> (`load.sh`) depend on the Docker image; check them for the image/version you
> pin in `docker-compose.yml` before the first start.

    cd endpoint
    docker compose up -d

The dataset is loaded into a TDB2 store at start-up (see `load.sh`) and is
served read-only at

    http://<host>:3030/whs/sparql      (query)
    http://<host>:3030/whs/            (Fuseki UI disabled for writes)

Put it behind HTTPS with your web server (nginx/Apache) and expose it as, for
example, `https://<institutional-host>/whs/sparql`.

Named graphs (the default graph is the union of all of them):

| Graph | Content |
|---|---|
| `https://w3id.org/whs/graph/core` | the knowledge graph as built by the MAP |
| `https://w3id.org/whs/graph/entailed` | RDFS entailments (DCMI / CRM / schema.org views of the local terms) |
| `https://w3id.org/whs/graph/crm` | CIDOC CRM-conformant view |
| `https://w3id.org/whs/graph/schema` | WHS element set, alignment axioms, SHACL shapes |

Because the entailments are pre-computed, no reasoner is needed at query time:
a DCMI-only consumer simply queries `dcterms:spatial`, a CRM-only consumer
queries the `crm` graph.

## 3. Make the persistent URIs dereference per entity

Ask w3id.org to update the `whs/` rules (pull request to
https://github.com/perma-id/w3id.org, folder `whs/`). See `w3id-htaccess.txt`:
`text/turtle` / `application/rdf+xml` / `application/ld+json` requests for a
site or danger URI are redirected to a SPARQL `DESCRIBE` on the endpoint;
HTML requests go to the documentation page; `/whs/terms/` resolves to the
element set; `/whs/profile` resolves to the profile documentation.

## 4. Updating after a World Heritage Committee session

    python extract.py && python clean.py && python reconcile.py
    python build_graph.py && python build_views.py
    python diff.py                          # changelog + SPARQL UPDATE delta
    # copy out/whs-all.trig to endpoint/data and restart:
    docker compose restart

Then create a new GitHub release (Zenodo mints a new version DOI).
