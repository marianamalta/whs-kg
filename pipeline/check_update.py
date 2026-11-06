"""Step 0 - Has the UNESCO export changed since the last snapshot?

Downloads the current syndication export (via extract.py) and compares its
CONTENT with the most recent snapshot in data/raw/. The XLS file is
regenerated on every download, so byte comparison is useless: both snapshots
are normalised (rows sorted by id_no, columns in a fixed order, values as
text) and hashed.

* unchanged -> the new download is deleted; prints "changed=false"
* changed   -> the new snapshot is kept;    prints "changed=true"

When run inside GitHub Actions the result is also written to $GITHUB_OUTPUT,
so the workflow can skip the rest of the pipeline when nothing changed.
"""
import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

import extract

RAW = Path("data/raw")


def content_hash(csv_path: Path) -> str:
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df = df.reindex(sorted(df.columns), axis=1)
    df = df.sort_values(by=["id_no"] + [c for c in df.columns if c != "id_no"])
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()


def main() -> bool:
    previous = sorted(RAW.glob("whc-sites-*.csv"))
    new_csv = extract.main()
    previous = [p for p in previous if p != new_csv]
    new_xls = new_csv.with_suffix(".xls")
    if new_xls.exists():
        new_xls.unlink()  # keep only the diffable CSV snapshot
    if not previous:
        print("no previous snapshot: treating as changed")
        return True
    old_h, new_h = content_hash(previous[-1]), content_hash(new_csv)
    if old_h == new_h:
        new_csv.unlink()
        print(f"unchanged since {previous[-1].name}")
        return False
    print(f"CHANGED: {previous[-1].name} -> {new_csv.name}")
    return True


if __name__ == "__main__":
    changed = main()
    print(f"changed={'true' if changed else 'false'}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")
    sys.exit(0)
