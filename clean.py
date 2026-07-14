"""Step 2 - Clean the raw export following paper section 4.1.

Applies the ten documented operations (HTML stripping, entity unescaping,
rev_bis -> integer version, language consolidation, danger_list parsing to
EDTF intervals, secondary_dates splitting, criteria harmonisation, category /
transboundary derivability checks, state/region preparation) and writes
data/clean/sites.json. Anything suspicious goes to data/clean/issues.txt
instead of being silently 'fixed'.
"""
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
CLEAN_DIR = Path("data/clean")

LANGS = ["en", "fr", "es", "ru", "ar", "zh"]

# (3) rev_bis -> integer version of the entry (P2 in the paper).
SUFFIX_VERSION = {"": 1, "bis": 2, "ter": 3, "quater": 4, "quinquies": 5,
                  "rev": 2}  # editorial default, see README

# Manual corrections for malformed rev_bis values, checked against the
# World Heritage Centre records (paper section 4.1, operation 3).
# Map id_no -> suffix string ('' for none).
REV_BIS_OVERRIDES: dict[int, str] = {
    893: "rev",
    205: "",
    155: "",
}

TAG_RE = re.compile(r"<[^>]*>")
ISSUES: list[str] = []


def issue(msg: str) -> None:
    ISSUES.append(msg)


def strip_html(value):
    """(1) remove markup + (2) unescape entities."""
    if not isinstance(value, str):
        return value
    return html.unescape(TAG_RE.sub("", value)).strip()


def clean_rev_bis(value, id_no) -> int | None:
    """(3) suffix -> version integer; invalid values are flagged, not guessed."""
    if id_no in REV_BIS_OVERRIDES:
        return SUFFIX_VERSION[REV_BIS_OVERRIDES[id_no]]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text in ("", "nan"):
        return None
    if text in SUFFIX_VERSION:
        return SUFFIX_VERSION[text]
    issue(f"site {id_no}: unexpected rev_bis value {value!r} - fix manually "
          f"against the World Heritage Centre record")
    return None


def parse_danger(row) -> list[dict]:
    """(5) danger fields -> EDTF intervals.

    Source encodings seen in the export:
      danger_list: 'P 2002-2006' (previous, closed), 'Y 1992' (current, open),
                   possibly several segments separated by commas.
      danger:      'Y'/'N' flag; date_end: year the site left the List.
    Output: [{'intervals': ['1992/..']}, ...] - the danger *type* is not in
    the source; it is added from authority/danger_types.csv at build time.
    """
    intervals: list[str] = []
    raw = row.get("danger_list")
    if isinstance(raw, str) and raw.strip():
        # segments are separated by spaces or commas, each starting with a
        # P (previous, closed) or Y (current, open) flag,
        # e.g. 'Y 1996 P 1984-1992' or 'P 1984-1988 P 2000-2006'
        matches = list(re.finditer(
            r"(P|Y)?\s*(\d{4})(?:\s*-\s*(\d{4}))?", raw))
        matched_digits = sum(len(m.group(0).strip()) for m in matches)
        if not matches:
            issue(f"site {row['id_no']}: unparsed danger_list {raw!r}")
        for m in matches:
            flag, start, end = m.groups()
            if end:
                intervals.append(f"{start}/{end}")
            elif flag == "P":
                issue(f"site {row['id_no']}: previous listing "
                      f"{m.group(0).strip()!r} without end year")
                intervals.append(f"{start}/..")
            else:
                intervals.append(f"{start}/..")
    # consistency: 'danger' flag says currently listed <-> one open interval
    currently = str(row.get("danger", "")).strip() in ("1", "Y", "y", "True")
    open_ivs = [i for i in intervals if i.endswith("/..")]
    if currently and not open_ivs:
        issue(f"site {row['id_no']}: danger flag set but no open interval")
    if not currently and open_ivs:
        issue(f"site {row['id_no']}: open interval {open_ivs} but danger flag "
              f"not set (check date_end={row.get('date_end')})")
    return [{"intervals": intervals}] if intervals else []


def derive_category(criteria: list[int], stated: str, id_no) -> str:
    """(8) category is derivable from the criteria (P3); source value is used
    only as a consistency check and then dropped."""
    cultural = any(c <= 6 for c in criteria)
    natural = any(c >= 7 for c in criteria)
    derived = "Mixed" if cultural and natural else \
              "Cultural" if cultural else "Natural"
    if stated and stated.strip() and stated.strip() != derived:
        issue(f"site {id_no}: stated category {stated!r} != derived {derived!r}")
    return derived


def main() -> None:
    raw_files = sorted(RAW_DIR.glob("whc-sites-*.csv"))
    if not raw_files:
        sys.exit("No raw snapshot found - run extract.py first.")
    src = raw_files[-1]
    print(f"Cleaning {src} ...")
    df = pd.read_csv(src)
    df.columns = [c.strip().lower() for c in df.columns]

    sites = []
    for _, row in df.iterrows():
        id_no = int(row["id_no"])

        # (1)+(2) textual artefacts in descriptive fields
        names, descs, justs = {}, {}, {}
        for lang in LANGS:                                   # (4) consolidate
            v = row.get(f"name_{lang}")
            if isinstance(v, str) and v.strip():
                names[lang] = strip_html(v)
            v = row.get(f"short_description_{lang}")
            if isinstance(v, str) and v.strip():
                descs[lang] = strip_html(v)
            v = row.get(f"justification_{lang}")
            if isinstance(v, str) and v.strip():
                justs[lang] = strip_html(v)
        if not names:
            issue(f"site {id_no}: no name in any language")

        # (7) criteria C1..C6 + N7..N10 -> C1..C10 booleans
        criteria = []
        for i in range(1, 11):
            col = f"c{i}" if i <= 6 else f"n{i}"
            v = row.get(col, row.get(f"c{i}"))
            if v in (1, "1", True, 1.0):
                criteria.append(i)
        if not criteria:
            issue(f"site {id_no}: no inscription criteria")

        # (9) multi-valued states; transboundary derivable (P3)
        iso = row.get("iso_code")
        iso_codes = [c.strip().lower() for c in str(iso).split(",")
                     if c.strip()] if isinstance(iso, str) else []
        trans = row.get("transboundary")
        if trans in (1, "1", True, 1.0) and len(iso_codes) < 2:
            issue(f"site {id_no}: transboundary flag but a single state")

        sites.append({
            "id_no": id_no,
            "version": clean_rev_bis(row.get("rev_bis"), id_no),      # (3)
            "names": names, "descriptions": descs,
            "justifications": justs,
            "date_inscribed": str(int(row["date_inscribed"]))
                              if pd.notna(row.get("date_inscribed")) else None,
            "secondary_dates": [d.strip() for d in                    # (6)
                                str(row.get("secondary_dates") or "").split(",")
                                if d.strip() and d.strip().lower() != "nan"],
            "latitude": float(row["latitude"])
                        if pd.notna(row.get("latitude")) else None,
            "longitude": float(row["longitude"])
                         if pd.notna(row.get("longitude")) else None,
            "area_hectares": float(row["area_hectares"])
                             if pd.notna(row.get("area_hectares")) else None,
            "criteria": criteria,
            "category_derived": derive_category(                      # (8)
                criteria, str(row.get("category") or ""), id_no),
            "iso_codes": iso_codes,
            "region_en": strip_html(str(row.get("region_en") or "")).strip(),
            "danger": parse_danger(row),                              # (5)
        })

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out = CLEAN_DIR / "sites.json"
    payload = json.dumps(sites, ensure_ascii=False, indent=1)
    out.write_text(payload, encoding="utf-8")
    # dated copy so diff.py can compare runs
    stamp = src.stem.replace("whc-sites-", "")
    (CLEAN_DIR / f"sites-{stamp}.json").write_text(payload, encoding="utf-8")
    (CLEAN_DIR / "issues.txt").write_text("\n".join(ISSUES), encoding="utf-8")
    print(f"  {len(sites)} sites -> {out}")
    print(f"  {len(ISSUES)} issues flagged -> {CLEAN_DIR/'issues.txt'}")


if __name__ == "__main__":
    main()
