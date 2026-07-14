"""Step 3 - Build / refresh the authority files.

Deterministic reconciliation via identifier crosswalks (no fuzzy matching):

  wikidata_sites.csv  id_no -> QID          via Wikidata P757 (WHS ID)
  states_tgn.csv      iso2  -> QID, TGN id  via Wikidata P297 -> P1667
  regions.csv         hand-curated (created once with known rows, then yours)
  danger_types.csv    hand-curated seed; unmapped sites listed for review

Everything that cannot be resolved deterministically is written to
authority/review_needed.txt for a human decision.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import requests

WDQS = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "whs-kg-pipeline/1.0 (research; contact author)",
           "Accept": "application/sparql-results+json"}
AUTH = Path("authority")
CLEAN = Path("data/clean/sites.json")
REVIEW: list[str] = []


def sparql(query: str) -> list[dict]:
    resp = requests.get(WDQS, params={"query": query}, headers=HEADERS,
                        timeout=180)
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def build_wikidata_sites(site_ids: set[int]) -> None:
    """id_no -> QID via P757. Deterministic; duplicates/missing flagged."""
    rows = sparql("""
        SELECT ?item ?whsId WHERE { ?item wdt:P757 ?whsId . }""")
    mapping = defaultdict(list)
    for b in rows:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        raw = b["whsId"]["value"].strip()
        # P757 values may carry suffixes like '755bis' - keep the number
        num = "".join(ch for ch in raw if ch.isdigit())
        if num:
            mapping[int(num)].append(qid)

    out = AUTH / "wikidata_sites.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id_no", "wikidata_qid", "status"])
        for id_no in sorted(site_ids):
            qids = sorted(set(mapping.get(id_no, [])))
            if len(qids) == 1:
                w.writerow([id_no, qids[0], "ok"])
            elif not qids:
                w.writerow([id_no, "", "MISSING"])
                REVIEW.append(f"wikidata: site {id_no} has no item with P757")
            else:
                w.writerow([id_no, qids[0], f"AMBIGUOUS:{'|'.join(qids)}"])
                REVIEW.append(f"wikidata: site {id_no} matches {qids}")
    print(f"  {out}: {len(site_ids)} sites "
          f"({sum(1 for i in site_ids if len(set(mapping.get(i, [])))==1)} ok)")


def build_states_tgn(iso_codes: set[str]) -> None:
    """iso2 -> country QID (P297) -> Getty TGN id (P1667)."""
    rows = sparql("""
        SELECT ?iso ?item ?tgn WHERE {
          ?item wdt:P297 ?iso .
          OPTIONAL { ?item wdt:P1667 ?tgn . }
        }""")
    found = {}
    for b in rows:
        iso = b["iso"]["value"].strip().lower()
        found[iso] = (b["item"]["value"].rsplit("/", 1)[-1],
                      b.get("tgn", {}).get("value", ""))
    out = AUTH / "states_tgn.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["iso2", "wikidata_qid", "tgn_id", "status"])
        for iso in sorted(iso_codes):
            qid, tgn = found.get(iso, ("", ""))
            status = "ok" if tgn else "MISSING_TGN" if qid else "MISSING"
            if status != "ok":
                REVIEW.append(f"states: {iso} -> qid={qid or '?'} "
                              f"tgn={tgn or '?'}")
            w.writerow([iso, qid, tgn, status])
    print(f"  {out}: {len(iso_codes)} states")


def seed_regions() -> None:
    """Hand-curated; created only if absent so your edits are never lost."""
    out = AUTH / "regions.csv"
    if out.exists():
        print(f"  {out}: kept (hand-curated)")
        return
    rows = [
        ["Europe and North America", "http://vocabularies.unesco.org/thesaurus/mt7.2"],
        ["Asia and the Pacific", "http://vocabularies.unesco.org/thesaurus/mt7.15"],
        ["Africa", ""],            # TODO fill from the thesaurus browser
        ["Arab States", ""],       # TODO
        ["Latin America and the Caribbean", ""],  # TODO
    ]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["region_en", "unescot_uri"])
        w.writerows(rows)
    REVIEW.append("regions: fill the three empty mt7.x URIs in regions.csv")
    print(f"  {out}: seeded - fill the empty rows")


def seed_danger_types(sites: list[dict]) -> None:
    """Hand-curated editorial mapping; unmapped danger-listed sites flagged."""
    out = AUTH / "danger_types.csv"
    known = {}
    if out.exists():
        with out.open(encoding="utf-8") as fh:
            known = {int(r["id_no"]): r for r in csv.DictReader(fh)}
    else:
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id_no", "label"])
            w.writerow([338, "War"])
        known = {338: {}}
        print(f"  {out}: seeded")
    for s in sites:
        if s["danger"] and s["id_no"] not in known:
            REVIEW.append(f"danger_types: site {s['id_no']} is danger-listed "
                          f"but has no threat concept - add a row")


def main() -> None:
    if not CLEAN.exists():
        sys.exit("data/clean/sites.json not found - run clean.py first.")
    sites = json.loads(CLEAN.read_text(encoding="utf-8"))
    AUTH.mkdir(exist_ok=True)

    build_wikidata_sites({s["id_no"] for s in sites})
    build_states_tgn({c for s in sites for c in s["iso_codes"]})
    seed_regions()
    seed_danger_types(sites)

    review = AUTH / "review_needed.txt"
    review.write_text("\n".join(REVIEW), encoding="utf-8")
    print(f"  {len(REVIEW)} items for human review -> {review}")


if __name__ == "__main__":
    main()
