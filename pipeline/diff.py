"""Step 5 (optional) - Detect changes between the two most recent runs.

Compares the two latest cleaned snapshots (data/clean/sites-*.json) and
produces:

  out/changelog-<date>.txt   human-readable: sites added / removed / changed,
                             with the fields that changed (per Committee
                             session provenance)
  out/delta-<date>.ru        SPARQL UPDATE patch: DELETE the subtrees of
                             removed/changed sites, INSERT the regenerated
                             triples of added/changed sites. Apply it to a
                             triple store hosting the graph instead of
                             reloading the full dump.

The canonical published dump is still the full rebuild (build_graph.py);
this step adds provenance and cheap endpoint updates.
"""
import json
import sys
from pathlib import Path

from build_graph import (WHS_SITE, WHS_DANGER, add_site, load_authorities,
                         new_graph)

CLEAN = Path("data/clean")
OUT = Path("out")


def changed_fields(a: dict, b: dict) -> list[str]:
    return [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


def delete_block(id_no: int) -> str:
    """SPARQL UPDATE deleting everything about a site and its danger events."""
    site = f"<{WHS_SITE}{id_no}>"
    return (f"DELETE WHERE {{ {site} ?p ?o . }} ;\n"
            f"DELETE WHERE {{ ?ev ?p ?o .\n"
            f"  FILTER STRSTARTS(STR(?ev), \"{WHS_DANGER}{id_no}-\") }} ;\n")


def main() -> None:
    snaps = sorted(CLEAN.glob("sites-*.json"))
    if len(snaps) < 2:
        sys.exit("Need at least two cleaned snapshots to diff "
                 f"(found {len(snaps)} in {CLEAN}).")
    old_path, new_path = snaps[-2], snaps[-1]
    stamp = new_path.stem.replace("sites-", "")
    old = {s["id_no"]: s for s in json.loads(old_path.read_text("utf-8"))}
    new = {s["id_no"]: s for s in json.loads(new_path.read_text("utf-8"))}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = {i: changed_fields(old[i], new[i])
               for i in sorted(set(old) & set(new))
               if old[i] != new[i]}

    OUT.mkdir(exist_ok=True)
    lines = [f"diff {old_path.name} -> {new_path.name}",
             f"added:   {len(added)}", f"removed: {len(removed)}",
             f"changed: {len(changed)}", ""]
    lines += [f"+ {i}  {new[i]['names'].get('en', '?')}" for i in added]
    lines += [f"- {i}  {old[i]['names'].get('en', '?')}" for i in removed]
    lines += [f"~ {i}  {', '.join(fields)}" for i, fields in changed.items()]
    log = OUT / f"changelog-{stamp}.txt"
    log.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:5]))
    print(f"-> {log}")

    if not (added or removed or changed):
        print("No changes - no delta written.")
        return

    # SPARQL UPDATE patch
    auth = load_authorities()
    parts = ["# WHS KG delta " + stamp,
             "# apply with: update endpoint or `sparql --update`", ""]
    for i in removed + list(changed):
        parts.append(delete_block(i))
    g = new_graph()
    for i in added + list(changed):
        add_site(g, new[i], auth)
    if len(g):
        nt = g.serialize(format="nt")
        parts.append("INSERT DATA {\n" + nt + "} ;\n")
    delta = OUT / f"delta-{stamp}.ru"
    delta.write_text("\n".join(parts), encoding="utf-8")
    print(f"-> {delta}  (apply to a triple store to update in place)")


if __name__ == "__main__":
    main()
