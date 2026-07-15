"""Step 4 - Build the knowledge graph per the MAP and validate it.

Reads data/clean/sites.json + the authority files, emits out/whs.ttl and
out/whs.nt, validates with pySHACL against whs-shapes.ttl, and prints the
statistics block used in the paper's Results section.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

# ---- namespaces (paper Table: Namespaces) ----------------------------------
WHS_SITE = Namespace("https://w3id.org/whs/site/")
WHS_DANGER = Namespace("https://w3id.org/whs/danger/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SCHEMA = Namespace("http://schema.org/")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
EDM = Namespace("http://www.europeana.eu/schemas/edm/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
WD = Namespace("http://www.wikidata.org/entity/")
DBO = Namespace("http://dbpedia.org/ontology/")
TGN = Namespace("http://vocab.getty.edu/tgn/")

CRITERIA_QIDS = ["Q15911738", "Q23038976", "Q23038977", "Q23038978",
                 "Q23038979", "Q23038980", "Q23038981", "Q23038983",
                 "Q23038985", "Q23038986"]  # (i)..(x)

AUTH = Path("authority")
OUT = Path("out")
CLEAN = Path("data/clean")


def load_csv(name: str, key: str) -> dict:
    path = AUTH / name
    if not path.exists():
        sys.exit(f"{path} not found - run reconcile.py first.")
    with path.open(encoding="utf-8") as fh:
        return {r[key].strip(): {k: (v or "").strip() for k, v in r.items()}
                for r in csv.DictReader(fh)}


def load_authorities() -> dict:
    return {
        "wikidata": load_csv("wikidata_sites.csv", "id_no"),
        "states": load_csv("states_tgn.csv", "iso2"),
        "regions": load_csv("regions.csv", "region_en"),
        "danger_types": load_csv("danger_types.csv", "id_no"),
        "danger_concepts": load_csv("danger_concepts.csv", "label"),
    }


def new_graph() -> Graph:
    g = Graph()
    for prefix, ns in [("whs-site", WHS_SITE), ("whs-danger", WHS_DANGER),
                       ("dcterms", DCTERMS), ("schema", SCHEMA), ("geo", GEO),
                       ("crm", CRM), ("edm", EDM), ("wdt", WDT), ("wd", WD),
                       ("dbo", DBO), ("tgn", TGN)]:
        g.bind(prefix, ns)
    return g


def add_site(g: Graph, s: dict, auth: dict) -> dict:
    """Emit all triples for one site (and its danger events) per the MAP.
    Returns per-site counters."""
    wikidata, states = auth["wikidata"], auth["states"]
    regions, danger_types = auth["regions"], auth["danger_types"]
    n_tgn_links = n_wd_links = n_events = 0
    if True:
        site = WHS_SITE[str(s["id_no"])]
        g.add((site, RDF.type, CRM["E18_Physical_Thing"]))
        g.add((site, DCTERMS.identifier,
               Literal(s["id_no"], datatype=XSD.integer)))

        if s.get("version"):
            g.add((site, SCHEMA.version,
                   Literal(s["version"], datatype=XSD.integer)))

        for lang, text in s["names"].items():
            g.add((site, DCTERMS.title, Literal(text, lang=lang)))
        for lang, text in s["descriptions"].items():
            g.add((site, DCTERMS.description, Literal(text, lang=lang)))
        for lang, text in s["justifications"].items():
            g.add((site, SCHEMA.description, Literal(text, lang=lang)))

        if s.get("date_inscribed"):                       # EDTF literal
            g.add((site, DCTERMS.dateAccepted, Literal(s["date_inscribed"])))
        for d in s.get("secondary_dates", []):
            g.add((site, DCTERMS.date, Literal(d)))

        if s.get("latitude") is not None:
            # pass the lexical form, not the Python float: rdflib marks
            # Literal(float, datatype=XSD.decimal) as ill-typed and pySHACL
            # then rejects every coordinate.
            g.add((site, GEO.lat,
                   Literal(str(s["latitude"]), datatype=XSD.decimal)))
            g.add((site, GEO.long,
                   Literal(str(s["longitude"]), datatype=XSD.decimal)))
        # the WHC export uses 0 to mean "area not reported" -> omit the triple
        if s.get("area_hectares"):
            g.add((site, DBO.areaTotal,
                   Literal(s["area_hectares"], datatype=XSD.double)))

        for c in s["criteria"]:
            g.add((site, WDT.P2614, WD[CRITERIA_QIDS[c - 1]]))

        for iso in s["iso_codes"]:                        # states via TGN
            row = states.get(iso, {})
            if row.get("tgn_id"):
                g.add((site, EDM.country, TGN[row["tgn_id"]]))
                n_tgn_links += 1

        # transboundary sites may carry several comma-separated regions
        for reg_name in [r.strip() for r in
                         s.get("region_en", "").split(",") if r.strip()]:
            reg = regions.get(reg_name, {})
            if reg.get("unescot_uri"):
                g.add((site, DCTERMS.spatial, URIRef(reg["unescot_uri"])))

        wd_row = wikidata.get(str(s["id_no"]), {})
        if wd_row.get("wikidata_qid") and wd_row.get("status") == "ok":
            g.add((site, SCHEMA.sameAs, WD[wd_row["wikidata_qid"]]))
            n_wd_links += 1

        # danger listings: one event per danger type (0-n), each event with
        # 1-n EDTF interval periods (paper P4)
        for n, listing in enumerate(s.get("danger", []), start=1):
            ev = WHS_DANGER[f"{s['id_no']}-{n}"]
            n_events += 1
            g.add((site, CRM["P12i_was_present_at"], ev))
            g.add((ev, RDF.type, CRM["E5_Event"]))
            # event-specific key ("119-2") wins over the site-wide one
            dt = (danger_types.get(f"{s['id_no']}-{n}")
                  or danger_types.get(str(s["id_no"]), {}))
            if dt.get("label"):
                concept = auth["danger_concepts"].get(dt["label"])
                if concept is None:
                    raise SystemExit(
                        f"danger_types.csv: label {dt['label']!r} for site "
                        f"{s['id_no']} is not in danger_concepts.csv")
                g.add((ev, DCTERMS.subject, URIRef(concept["unescot_uri"])))
            # if unmapped: emitted without subject -> SHACL flags it (by design)
            for interval in listing["intervals"]:
                g.add((ev, DCTERMS.temporal, Literal(interval)))

    return {"tgn": n_tgn_links, "wd": n_wd_links, "events": n_events}


def remove_site(g: Graph, id_no) -> None:
    """Delete a site and all of its danger events from an in-memory graph."""
    g.remove((WHS_SITE[str(id_no)], None, None))
    prefix = f"{WHS_DANGER}{id_no}-"
    for ev in {s for s in g.subjects() if str(s).startswith(prefix)}:
        g.remove((ev, None, None))


def graph_stats(g: Graph) -> list[str]:
    """Statistics read back from the finished graph, so the same numbers are
    reported whether the graph was built from scratch or patched in place."""
    country = list(g.triples((None, EDM.country, None)))
    n_sites = len(set(g.subjects(RDF.type, CRM["E18_Physical_Thing"])))
    n_events = len(set(g.subjects(RDF.type, CRM["E5_Event"])))
    n_wd = sum(1 for _ in g.triples((None, SCHEMA.sameAs, None)))
    return [
        f"triples:              {len(g):,}",
        f"site resources:       {n_sites:,}",
        f"danger events:        {n_events}",
        f"edm:country links:    {len(country)} (distinct TGN entries: "
        f"{len({o for _, _, o in country})})",
        f"wikidata sameAs:      {n_wd}",
    ]


def build_full() -> Graph:
    """Rebuild the whole graph from the current cleaned snapshot."""
    sites = json.loads((CLEAN / "sites.json").read_text("utf-8"))
    auth = load_authorities()
    g = new_graph()
    for s in sites:
        add_site(g, s, auth)
    return g


def build_incremental() -> Graph | None:
    """Patch the existing out/whs.ttl using the two most recent cleaned
    snapshots, instead of rebuilding from scratch. Returns None (so the caller
    falls back to a full build) when there is no existing graph or fewer than
    two snapshots.

    Assumes out/whs.ttl corresponds to the second-most-recent snapshot, i.e.
    the state left by the previous pipeline run (extract -> clean -> build)."""
    ttl = OUT / "whs.ttl"
    snaps = sorted(CLEAN.glob("sites-*.json"))
    if not ttl.exists() or len(snaps) < 2:
        return None
    old = {s["id_no"]: s for s in json.loads(snaps[-2].read_text("utf-8"))}
    new = {s["id_no"]: s for s in json.loads(snaps[-1].read_text("utf-8"))}
    added = set(new) - set(old)
    removed = set(old) - set(new)
    changed = {i for i in set(old) & set(new) if old[i] != new[i]}

    g = new_graph()
    g.parse(ttl, format="turtle")
    for i in removed | changed:
        remove_site(g, i)
    auth = load_authorities()
    for i in added | changed:
        add_site(g, new[i], auth)
    print(f"incremental: {snaps[-2].name} -> {snaps[-1].name}  "
          f"(+{len(added)} added, -{len(removed)} removed, "
          f"~{len(changed)} changed)")
    return g


def main(incremental: bool = False) -> None:
    g = build_incremental() if incremental else None
    if g is None:
        if incremental:
            print("incremental build not possible "
                  "(no existing graph or <2 snapshots) - doing a full rebuild.")
        g = build_full()

    OUT.mkdir(exist_ok=True)
    g.serialize(OUT / "whs.ttl", format="turtle")
    g.serialize(OUT / "whs.nt", format="nt", encoding="utf-8")

    stats = graph_stats(g)
    print("\n".join(stats))
    (OUT / "stats.txt").write_text("\n".join(stats), encoding="utf-8")

    # ---- SHACL validation ---------------------------------------------------
    try:
        from pyshacl import validate
    except ImportError:
        print("pyshacl not installed - skipping validation")
        return
    conforms, _, report = validate(
        g,
        shacl_graph=str(Path("whs-shapes.ttl")),
        inference="none",
        meta_shacl=False,
        advanced=True,
    )
    (OUT / "shacl-report.txt").write_text(report, encoding="utf-8")
    print(f"conforms:            {conforms} "
          f"(report -> {OUT / 'shacl-report.txt'})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Build the WHS knowledge graph and validate it.")
    ap.add_argument(
        "--incremental", action="store_true",
        help="patch the existing out/whs.ttl using the two latest cleaned "
             "snapshots instead of rebuilding the whole graph from scratch")
    main(incremental=ap.parse_args().incremental)