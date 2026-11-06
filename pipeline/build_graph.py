"""Step 4 - Build the knowledge graph per the MAP and validate it.

Reads data/clean/sites.json + the authority files, emits out/whs.ttl and
out/whs.nt, validates with pySHACL against whs-shapes.ttl, and prints the
statistics block used in the paper's Results section.

v2 (MAP 2.0, resubmission): DCMI Terms is the primary target vocabulary;
three local refinements (whs:stateParty, whs:region, whs:justification) plus
one class (whs:CriterionJustification) are declared in ../vocab/whs-terms.ttl
as sub-properties of DCMI terms; edm:country and schema:description are no
longer used; area is xsd:decimal in square metres (dbo:areaTotal semantics);
every site links to its official UNESCO page with dcterms:source.
"""
import re
from decimal import Decimal
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
WHS = Namespace("https://w3id.org/whs/terms/")
WHS_JUST = Namespace("https://w3id.org/whs/justification/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
WD = Namespace("http://www.wikidata.org/entity/")
DBO = Namespace("http://dbpedia.org/ontology/")
TGN = Namespace("http://vocab.getty.edu/tgn/")

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
         "viii": 8, "ix": 9, "x": 10}
# "Criterion (ii):", "Critère (iv) :", "Criteria (ii) and (iii):" ...
CRIT_MARK = re.compile(
    r"Crit(?:erion|eria|\u00e8re|\u00e8res)\s*"
    r"((?:\(\s*[ivx]+\s*\)[\s,&]*(?:and|et)?\s*)+)\s*:")
UNESCO_PAGE = "https://whc.unesco.org/en/list/{}"

CRITERIA_QIDS = ["Q23038972", "Q23038976", "Q23038977", "Q23038978",
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
                       ("crm", CRM), ("whs", WHS), ("whs-just", WHS_JUST),
                       ("wdt", WDT), ("wd", WD),
                       ("dbo", DBO), ("tgn", TGN)]:
        g.bind(prefix, ns)
    return g


def split_justification(text: str) -> dict[int, str]:
    """Split a structured justification ("Criterion (ii): ... Criterion (iv):
    ...") into {criterion number: text}. Returns {} when the text has no
    criterion markers (about a third of the records): those keep only the
    full whs:justification literal."""
    marks = list(CRIT_MARK.finditer(text))
    out: dict[int, str] = {}
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        for roman in re.findall(r"[ivx]+", m.group(1)):
            if roman in ROMAN and body:
                out[ROMAN[roman]] = body
    return out


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
        # actionable link to the authoritative record (provenance, R1)
        g.add((site, DCTERMS.source,
               URIRef(UNESCO_PAGE.format(s["id_no"]))))

        if s.get("version"):
            g.add((site, SCHEMA.version,
                   Literal(s["version"], datatype=XSD.integer)))

        for lang, text in s["names"].items():
            g.add((site, DCTERMS.title, Literal(text, lang=lang)))
        for lang, text in s["descriptions"].items():
            g.add((site, DCTERMS.description, Literal(text, lang=lang)))
        # justification: full text with a DCMI refinement (whs:justification
        # rdfs:subPropertyOf dcterms:description) + one structured node per
        # criterion when the text is segmented by criterion markers
        for lang, text in s["justifications"].items():
            g.add((site, WHS.justification, Literal(text, lang=lang)))
            for c, body in split_justification(text).items():
                if c not in s["criteria"]:
                    continue  # marker for a criterion the site does not meet
                node = WHS_JUST[f"{s['id_no']}-{c}"]
                g.add((site, WHS.criterionJustification, node))
                g.add((node, RDF.type, WHS.CriterionJustification))
                g.add((node, DCTERMS.subject, WD[CRITERIA_QIDS[c - 1]]))
                g.add((node, WHS.justification, Literal(body, lang=lang)))

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
        # dbo:areaTotal is defined in square metres: convert ha -> m2 exactly
        # and use xsd:decimal (no exponential notation)
        if s.get("area_hectares"):
            try:
                lex = format((Decimal(str(s["area_hectares"])) * 10000)
                             .normalize(), "f")
            except ArithmeticError:   # unparsable raw value (ablation run):
                lex = str(s["area_hectares"])  # keep it so SHACL flags it
            g.add((site, DBO.areaTotal, Literal(lex, datatype=XSD.decimal)))

        for c in s["criteria"]:
            g.add((site, WDT.P2614, WD[CRITERIA_QIDS[c - 1]]))

        for iso in s["iso_codes"]:                        # states via TGN
            row = states.get(iso, {})
            if row.get("tgn_id"):
                g.add((site, WHS.stateParty, TGN[row["tgn_id"]]))
                n_tgn_links += 1

        # transboundary sites may carry several comma-separated regions
        for reg_name in [r.strip() for r in
                         s.get("region_en", "").split(",") if r.strip()]:
            reg = regions.get(reg_name, {})
            # v2: WH regions are a local SKOS scheme (../vocab/whs-regions.ttl)
            # mapped to the UNESCO Thesaurus; mt7.x URIs do not dereference
            if reg.get("region_uri"):
                g.add((site, WHS.region, URIRef(reg["region_uri"])))

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
    country = list(g.triples((None, WHS.stateParty, None)))
    n_sites = len(set(g.subjects(RDF.type, CRM["E18_Physical_Thing"])))
    n_events = len(set(g.subjects(RDF.type, CRM["E5_Event"])))
    n_wd = sum(1 for _ in g.triples((None, SCHEMA.sameAs, None)))
    return [
        f"triples:              {len(g):,}",
        f"site resources:       {n_sites:,}",
        f"danger events:        {n_events}",
        f"whs:stateParty links: {len(country)} (distinct TGN entries: "
        f"{len({o for _, _, o in country})})",
        f"wikidata sameAs:      {n_wd}",
        f"criterion justif.:    "
        f"{len(set(g.subjects(RDF.type, WHS.CriterionJustification)))}",
    ]


def build_full() -> Graph:
    """Rebuild the whole graph from the current cleaned snapshot."""
    sites = json.loads((CLEAN / "sites.json").read_text("utf-8"))
    auth = load_authorities()
    g = new_graph()
    for s in sites:
        add_site(g, s, auth)
    return g


def build_removed(current_ids: set) -> Graph:
    """Properties that were in an earlier snapshot but are no longer on the
    List (e.g. removed by the World Heritage Committee). Their URIs must keep
    resolving, so their LAST description is kept, in a separate graph
    (out/whs-removed.ttl -> named graph .../graph/removed), with the period of
    inscription as an EDTF interval in dcterms:valid. Queries over the current
    List (the core graph) are unaffected.

    The removal year defaults to the year of the first snapshot in which the
    site is missing; authority/removed.csv (id_no,year_removed,note) can
    override it with the official decision year."""
    g = new_graph()
    snaps = sorted(CLEAN.glob("sites-*.json"))
    last_seen: dict = {}
    first_missing: dict = {}
    for snap in snaps:
        stamp = snap.stem.replace("sites-", "")
        records = {r["id_no"]: r for r in json.loads(snap.read_text("utf-8"))}
        for i, r in records.items():
            last_seen[i] = r
            first_missing.pop(i, None)
        for i in last_seen:
            if i not in records and i not in first_missing:
                first_missing[i] = stamp[:4]
    removed = {i for i in last_seen if i not in current_ids}
    if not removed:
        return g
    override = {}
    path = AUTH / "removed.csv"
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            override = {int(r["id_no"]): r for r in csv.DictReader(fh)}
    auth = load_authorities()
    for i in sorted(removed):
        rec = last_seen[i]
        add_site(g, rec, auth)
        year = override.get(int(i), {}).get("year_removed") or first_missing[i]
        start = (rec.get("date_inscribed") or "")[:4]
        g.add((WHS_SITE[str(i)], DCTERMS.valid, Literal(f"{start}/{year}")))
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

    current_ids = {int(str(s).rsplit("/", 1)[-1])
                   for s in g.subjects(RDF.type, CRM["E18_Physical_Thing"])}
    removed = build_removed(current_ids)
    removed.serialize(OUT / "whs-removed.ttl", format="turtle")

    stats = graph_stats(g)
    stats.append(f"removed from List:    "
                 f"{len(set(removed.subjects(RDF.type, CRM['E18_Physical_Thing'])))}"
                 f" (kept in out/whs-removed.ttl)")
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
        ont_graph=str(Path("../vocab/whs-terms.ttl")),
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