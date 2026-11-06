"""Step 7 - Run the competency questions (paper Section 7, Table 8) locally.

Loads out/whs-all.trig (core + entailed + CRM view + schema) with rdflib,
runs the published queries in ../queries/ against it, and computes the two
Wikidata comparisons (CQ8, CQ11) by querying the Wikidata Query Service
directly in batches (more robust than a federated SERVICE clause).

Writes everything to out/cq-results.txt.
"""
import csv
import io
import time
from collections import Counter
from pathlib import Path

import requests
from rdflib import Dataset, Graph, URIRef

OUT = Path("out")
QUERIES = Path("..") / "queries"
WDQS = "https://query.wikidata.org/sparql"
UA = "WHS-KG research script (FEUP / INESC TEC; mailto:mariana.c.malta@inesctec.pt)"
CRIT = {"Q23038972", "Q23038976", "Q23038977", "Q23038978", "Q23038979",
        "Q23038980", "Q23038981", "Q23038983", "Q23038985", "Q23038986"}

lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    lines.append(text)


def rows(ds: Graph, name: str) -> list:
    return list(ds.query((QUERIES / name).read_text("utf-8")))


def wikidata(query: str) -> list[dict]:
    for attempt in range(4):
        r = requests.get(WDQS, params={"query": query, "format": "json"},
                         headers={"User-Agent": UA}, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["results"]["bindings"]
    r.raise_for_status()
    return []


def main() -> None:
    full = Dataset()
    full.parse(OUT / "whs-all.trig", format="trig")
    G = "https://w3id.org/whs/graph/"
    # query each named graph separately: some triples (e.g. P12i) occur in
    # both the core graph and the CRM view, and a union would count them twice
    ds = full.graph(URIRef(G + "core"))
    entailed = full.graph(URIRef(G + "entailed"))
    crm = full.graph(URIRef(G + "crm"))
    say(f"loaded core {len(ds):,}, entailed {len(entailed):,}, "
        f"crm {len(crm):,} triples")

    r = rows(ds, "cq01-currently-in-danger.rq")
    say(f"\nCQ1  currently in danger: {len(r)} properties; "
        f"earliest since {min(str(x.since) for x in r)}, "
        f"latest {max(str(x.since) for x in r)}")

    r = rows(ds, "cq02-danger-entries-by-decade.rq")
    by_dec, by_type = Counter(), Counter()
    for x in r:
        by_dec[str(x.decade)] += int(x.n)
        by_type[str(x.type).rsplit("/", 1)[-1]] += int(x.n)
    say(f"CQ2  periods by decade: {dict(sorted(by_dec.items()))}")
    say(f"     periods by type:   {dict(by_type)}")

    r = rows(ds, "cq03-listed-more-than-once.rq")
    say(f"CQ3  listed more than once: {len(r)}: "
        + "; ".join(f"{x.name} ({x.periods})" for x in r))

    r = rows(ds, "cq04-criteria-by-region.rq")
    tot = Counter()
    for x in r:
        tot[str(x.criterion).rsplit("/", 1)[-1]] += int(x.n)
    say(f"CQ4  {len(r)} region x criterion cells; most used criterion overall: "
        f"{tot.most_common(1)}")

    r = rows(ds, "cq05-transboundary-by-state.rq")
    say(f"CQ5  States Parties with transboundary properties: {len(r)}; "
        f"top: {[(str(x.state), int(x.n)) for x in r[:3]]}")

    r = rows(ds, "cq06-category-derived.rq")
    say(f"CQ6  categories: {{{', '.join(f'{x.category}: {x.n}' for x in r)}}}")

    r = rows(ds, "cq07-from-wikidata-item.rq")
    say(f"CQ7  rows for wd:Q3848157: {len(r)}")

    r = rows(ds, "cq09-sites-in-country.rq")
    say(f"CQ9  properties in TGN 1000090 (Portugal), French names: {len(r)}")

    r = rows(ds, "cq10-no-wikidata-link.rq")
    say(f"CQ10 properties without a Wikidata link: {len(r)}")

    r = rows(entailed, "cq12-dcmi-only-consumer.rq")
    say(f"I1   dcterms:spatial statements (entailed): {r[0][0]}")
    n_ts = list(crm.query("""PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
        SELECT (COUNT(?ts) AS ?n) (COUNT(?e) AS ?closed) WHERE {
          ?ev crm:P9_consists_of/crm:P4_has_time-span ?ts .
          OPTIONAL { ?ts crm:P82b_end_of_the_end ?e } }"""))[0]
    say(f"I2   danger time-spans in CRM view: {n_ts[0]} (with P82b: {n_ts[1]})")

    # ---- Wikidata comparisons (CQ8, CQ11) ---------------------------------
    site_wd = {str(s): str(o).rsplit("/", 1)[-1] for s, o in ds.query(
        "SELECT ?s ?o WHERE { ?s <http://schema.org/sameAs> ?o }")}
    official = {}
    for s, c in ds.query("SELECT ?s ?c WHERE { ?s "
                         "<http://www.wikidata.org/prop/direct/P2614> ?c }"):
        official.setdefault(str(s), set()).add(str(c).rsplit("/", 1)[-1])

    qids = sorted(set(site_wd.values()))
    img, web, wd_crit = set(), set(), {}
    for i in range(0, len(qids), 150):
        values = " ".join(f"wd:{q}" for q in qids[i:i + 150])
        for b in wikidata(f"""SELECT ?item ?p ?v WHERE {{
              VALUES ?item {{ {values} }}
              VALUES ?p {{ wdt:P18 wdt:P856 wdt:P2614 }}
              ?item ?p ?v }}"""):
            q = b["item"]["value"].rsplit("/", 1)[-1]
            p = b["p"]["value"].rsplit("/", 1)[-1]
            v = b["v"]["value"].rsplit("/", 1)[-1]
            if p == "P18":
                img.add(q)
            elif p == "P856":
                web.add(q)
            elif v in CRIT:
                wd_crit.setdefault(q, set()).add(v)
        time.sleep(1)
    say(f"\nCQ8  of {len(qids)} linked Wikidata items: {len(img)} with an image "
        f"(P18), {len(web)} with an official website (P856)")

    diff_sites, missing, extra, no_crit = 0, 0, 0, 0
    detail = io.StringIO()
    w = csv.writer(detail)
    w.writerow(["site", "wikidata", "official_only", "wikidata_only"])
    for s, q in site_wd.items():
        off, wdc = official.get(s, set()), wd_crit.get(q, set())
        if not wdc:
            no_crit += 1
        if off != wdc:
            diff_sites += 1
            missing += len(off - wdc)
            extra += len(wdc - off)
            w.writerow([s, q, " ".join(sorted(off - wdc)),
                        " ".join(sorted(wdc - off))])
    say(f"CQ11 properties whose criteria differ: {diff_sites} "
        f"({no_crit} with no P2614 at all); "
        f"statements official-not-in-Wikidata: {missing}, "
        f"in-Wikidata-not-official: {extra}")
    (OUT / "cq11-criteria-differences.csv").write_text(detail.getvalue(),
                                                       encoding="utf-8")

    (OUT / "cq-results.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwritten: {OUT / 'cq-results.txt'} and "
          f"{OUT / 'cq11-criteria-differences.csv'}")


if __name__ == "__main__":
    main()
