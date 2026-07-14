"""Step 1 - Extract the UNESCO World Heritage syndication export.

Downloads the official XLS export from https://whc.unesco.org/en/syndication
and stores a dated raw CSV snapshot in data/raw/.
"""
from datetime import date
from pathlib import Path
import sys

try:
    import pandas as pd
    import requests
except ImportError:
    raise SystemExit("Dependencies missing - run: pip install -r requirements.txt")

# Official syndication export (XLS). If UNESCO changes the URL, take it from
# https://whc.unesco.org/en/syndication
XLS_URL = "https://whc.unesco.org/en/list/xls/"
RAW_DIR = Path("data/raw")


def main() -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    xls_path = RAW_DIR / f"whc-sites-{stamp}.xls"
    csv_path = RAW_DIR / f"whc-sites-{stamp}.csv"

    print(f"Downloading {XLS_URL} ...")
    resp = requests.get(XLS_URL, timeout=120,
                        headers={"User-Agent": "whs-kg-pipeline/1.0"})
    resp.raise_for_status()
    xls_path.write_bytes(resp.content)
    print(f"  saved {xls_path} ({len(resp.content):,} bytes)")

    # Convert to CSV so every later step is diffable and format-independent.
    df = pd.read_excel(xls_path)
    df.to_csv(csv_path, index=False)
    print(f"  snapshot {csv_path}: {len(df)} rows, {len(df.columns)} columns")
    return csv_path


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        sys.exit(f"Download failed: {exc}\n"
                 "Check the current export URL on the syndication page.")
