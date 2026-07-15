"""Ablation study: how many SHACL violations does the cleaning step prevent?

Isolates the *cleaning* operations of Section 4.1 from everything else in the
pipeline. It builds a graph from the RAW export with the data-quality cleaning
turned OFF, but keeps the structural mapping and, crucially, RECONCILIATION ON
(the same authority files: Wikidata, Getty TGN, UNESCO regions, danger types).
That way every violation counted is attributable to *cleaning*, not to missing
links -- otherwise every site would fail edm:country / dcterms:spatial for lack
of a reconciled URI and swamp the signal.

It then reports, side by side:
  * BASELINE  -- the cleaned graph (out/whs.ttl), i.e. the published dataset
  * ABLATED   -- cleaning disabled
with a breakdown of the ablated violations by constraint path, so the numbers
drop straight into the paper's validation table.

Cleaning operations DISABLED (ablated):
  (3) rev_bis -> integer version   -> raw suffix kept  (schema:version datatype)
  (5) danger_list -> EDTF interval -> raw string kept  (dcterms:temporal pattern)
  (6) secondary_dates split        -> raw cell kept    (dcterms:date pattern)
  -- area = 0 ("not reported") omission -> raw 0 kept  (dbo:areaTotal minExclusive)
  (1)(2) HTML strip / entity unescape -> kept (no SHACL effect; included for honesty)

Kept ON (so the comparison isolates cleaning):
  (4) language tagging by column, (7) criteria harmonisation,
  (9)(10) state/region/Wikidata reconciliation via the authority files.

Run from the repository root, in the venv that has rdflib + pyshacl + pandas:
    python ablate_cleaning.py
"""
import logging
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Namespace, RDF

# The ablated graph deliberately contains ill-typed integer literals (raw
# rev_bis suffixes); rdflib warns on each one. That is the signal we are
# measuring, not an error, so quieten the noise for a clean report.
logging.getLogger("rdflib.term").setLevel(logging.ERROR)

import build_graph as bg  # reuse the exact MAP logic (new_graph, add_site, ...)

SH = Namespace("http://www.w3.org/ns/shacl#")
SHAPES = "whs-shapes.ttl"
RAW_DIR = Path("data/raw")
LANGS = ["en", "fr", "es", "ru", "ar", "zh"]


def raw_records(df) -> list[dict]:
    """Build the record dicts add_site() expects, from RAW values, with the
    data-quality cleaning switched off (see module docstring)."""
    df.columns = [c.strip().lower() for c in df.columns]
    records = []
    for _, row in df.iterrows():
        idv = (row.get("id_no") or "").strip()
        if not idv:
            continue
        try:
            id_no = int(float(idv))
        except ValueError:
            continue

        def val(col):
            v = row.get(col)
            return v.strip() if isinstance(v, str) and v.strip() else None

        # (4) languages kept, but (1)(2) HTML/entity cleaning OFF: raw text kept
        names = {lg: row.get(f"name_{lg}").strip()
                 for lg in LANGS
                 if isinstance(row.get(f"name_{lg}"), str) and row.get(f"name_{lg}").strip()}
        descs = {lg: row.get(f"short_description_{lg}").strip()
                 for lg in LANGS
                 if isinstance(row.get(f"short_description_{lg}"), str) and row.get(f"short_description_{lg}").strip()}
        justs = {lg: row.get(f"justification_{lg}").strip()
                 for lg in ("en", "fr")
                 if isinstance(row.get(f"justification_{lg}"), str) and row.get(f"justification_{lg}").strip()}

        # (7) criteria harmonisation kept (structural, not a cleaning fix)
        criteria = []
        for i in range(1, 11):
            col = f"c{i}" if i <= 6 else f"n{i}"
            if (row.get(col) or "").strip() in ("1", "1.0"):
                criteria.append(i)

        # (9) states/regions kept -> reconciliation resolves the URIs
        iso = row.get("iso_code")
        iso_codes = [c.strip().lower() for c in str(iso).split(",")
                     if c.strip()] if isinstance(iso, str) else []

        # (5) danger_list parsing OFF: keep the raw cell as a single "interval"
        danger = []
        dl = val("danger_list")
        if dl:
            danger = [{"intervals": [dl]}]

        # (6) secondary_dates split OFF: keep the raw cell as one value
        sec = val("secondary_dates")
        secondary_dates = [sec] if sec else []

        records.append({
            "id_no": id_no,
            "version": val("rev_bis"),          # (3) OFF: raw suffix, not an int
            "names": names, "descriptions": descs, "justifications": justs,
            "date_inscribed": val("date_inscribed"),
            "secondary_dates": secondary_dates,
            "latitude": val("latitude"),
            "longitude": val("longitude"),
            "area_hectares": val("area_hectares"),   # area="0" kept -> minExclusive
            "criteria": criteria,
            "iso_codes": iso_codes,
            "region_en": val("region_en") or "",
            "danger": danger,
        })
    return records


def violations(graph: Graph):
    """Validate a data graph against the shapes; return (conforms, results_graph)."""
    from pyshacl import validate
    conforms, results_graph, _ = validate(
        graph, shacl_graph=SHAPES, inference="none",
        meta_shacl=False, advanced=True)
    return conforms, results_graph


def summarise(results_graph: Graph) -> tuple[int, Counter]:
    results = list(results_graph.subjects(RDF.type, SH.ValidationResult))
    by_path = Counter(str(results_graph.value(r, SH.resultPath)) for r in results)
    return len(results), by_path


def main() -> None:
    # --- BASELINE: the published (cleaned) graph -----------------------------
    clean_path = Path("out/whs.ttl")
    if not clean_path.exists():
        sys.exit("out/whs.ttl not found - run build_graph.py first.")
    clean_graph = Graph().parse(clean_path, format="turtle")
    _, clean_results = violations(clean_graph)
    clean_total, clean_by_path = summarise(clean_results)

    # --- ABLATED: cleaning disabled, reconciliation kept ---------------------
    raw_files = sorted(RAW_DIR.glob("whc-sites-*.csv"))
    if not raw_files:
        sys.exit("No raw snapshot found in data/raw/ - run extract.py first.")
    df = pd.read_csv(raw_files[-1], dtype=str, keep_default_na=False)
    records = raw_records(df)

    auth = bg.load_authorities()
    g = bg.new_graph()
    for rec in records:
        bg.add_site(g, rec, auth)
    _, abl_results = violations(g)
    abl_total, abl_by_path = summarise(abl_results)

    # --- Report --------------------------------------------------------------
    print(f"\nsites built (ablated): {len(records)}")
    print("=" * 60)
    print(f"BASELINE  (cleaned graph)   SHACL violations: {clean_total}")
    for path, n in clean_by_path.most_common():
        print(f"    {n:>5}  {path}")
    print("-" * 60)
    print(f"ABLATED   (cleaning OFF)    SHACL violations: {abl_total}")
    for path, n in abl_by_path.most_common():
        print(f"    {n:>5}  {path}")
    print("=" * 60)
    print(f"Violations prevented by the cleaning step: "
          f"{abl_total - clean_total}")


if __name__ == "__main__":
    main()
