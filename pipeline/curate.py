"""curate.py - list everything that still blocks a fully conformant graph.

Reads data/clean/sites.json plus the authority files and writes:

  authority/curation_todo.txt        human-readable checklist (3 sections)
  authority/danger_types_todo.csv    danger_types.csv pre-filled with every
                                     danger-listed site; fill the `label`
                                     column, then replace danger_types.csv
                                     with this file (extra columns are fine,
                                     build_graph.py only reads id_no+label).

Run:  python curate.py
"""
import csv
import json
from pathlib import Path

AUTH = Path("authority")
ALLOWED = ["War", "Pollution", "Natural hazards", "Materials", "Urbanization"]


def load(name: str, key: str) -> dict:
    path = AUTH / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {r[key].strip(): {k: (v or "").strip() for k, v in r.items()}
                for r in csv.DictReader(fh)}


def site_name(s: dict) -> str:
    names = s.get("names") or {}
    return names.get("en") or next(iter(names.values()), "?")


def main() -> None:
    sites = json.loads(Path("data/clean/sites.json").read_text("utf-8"))
    danger_types = load("danger_types.csv", "id_no")
    states = load("states_tgn.csv", "iso2")
    regions = load("regions.csv", "region_en")

    lines: list[str] = []

    # ---- 1) danger types --------------------------------------------------
    dangerous = [s for s in sites if s.get("danger")]
    missing_dt = [s for s in dangerous
                  if not danger_types.get(str(s["id_no"]), {}).get("label")]
    lines.append(f"== 1) DANGER TYPES: {len(missing_dt)} of {len(dangerous)} "
                 "danger-listed sites lack a type ==")
    lines.append(f"   fill the label column in danger_types_todo.csv, "
                 f"allowed: {' | '.join(ALLOWED)}")
    rows = []
    for s in sorted(dangerous, key=lambda x: x["id_no"]):
        sid = str(s["id_no"])
        label = danger_types.get(sid, {}).get("label", "")
        intervals = "; ".join(iv for l in s["danger"] for iv in l["intervals"])
        url = f"https://whc.unesco.org/en/list/{sid}"
        rows.append({"id_no": sid, "label": label, "name_en": site_name(s),
                     "intervals": intervals, "whc_url": url})
        if not label:
            lines.append(f"   {sid:>5}  {site_name(s)}  [{intervals}]  {url}")

    with (AUTH / "danger_types_todo.csv").open("w", encoding="utf-8",
                                               newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id_no", "label", "name_en",
                                           "intervals", "whc_url"])
        w.writeheader()
        w.writerows(rows)

    # ---- 2) states without a TGN id ---------------------------------------
    lines.append("")
    missing_tgn: dict[str, list[str]] = {}
    for s in sites:
        for iso in s.get("iso_codes", []):
            if not states.get(iso, {}).get("tgn_id"):
                missing_tgn.setdefault(iso, []).append(
                    f"{s['id_no']} {site_name(s)}")
    lines.append(f"== 2) STATES WITHOUT TGN: {len(missing_tgn)} iso codes ==")
    lines.append("   add/complete the tgn_id column in states_tgn.csv "
                 "(numeric id from vocab.getty.edu/tgn/)")
    for iso, ss in sorted(missing_tgn.items()):
        head = "; ".join(ss[:3]) + (" ..." if len(ss) > 3 else "")
        lines.append(f"   {iso}: {len(ss)} site(s) -> {head}")

    # ---- 3) regions that do not match regions.csv -------------------------
    lines.append("")
    unmatched: dict[str, int] = {}
    for s in sites:
        reg = s.get("region_en", "")
        if not regions.get(reg, {}).get("unescot_uri"):
            unmatched[reg] = unmatched.get(reg, 0) + 1
    lines.append(f"== 3) REGION STRINGS NOT IN regions.csv: {len(unmatched)} ==")
    lines.append("   add a row per string (transboundary double-regions may "
                 "need their own row)")
    for reg, n in sorted(unmatched.items(), key=lambda kv: -kv[1]):
        lines.append(f"   {n:>4} site(s): {reg!r}")

    out = AUTH / "curation_todo.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {len(missing_dt)} danger types, {len(missing_tgn)} TGN states, "
          f"{len(unmatched)} region strings to fix")
    print(f"  checklist -> {out}")
    print(f"  fill-in sheet -> {AUTH / 'danger_types_todo.csv'}")


if __name__ == "__main__":
    main()
