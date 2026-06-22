#!/usr/bin/env python3
"""Build data/h1b_sponsors.csv from the official H1B disclosure data.

You only need to run this occasionally (the data updates ~yearly). It replaces
the shipped seed list with real filing counts so the sheet shows e.g.
"✅ Strong sponsor (4,812 filings)" instead of "(known)".

Free official sources (download the CSV, then point this script at it):

  • USCIS H-1B Employer Data Hub  (recommended — approvals per employer/year)
      https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub
      Export the data file; columns include the employer name + Initial/Continuing
      Approval counts.

  • DOL OFLC LCA Disclosure Data  (every LCA filed; bigger files)
      https://www.dol.gov/agencies/eta/foreign-labor/performance

Usage:
    python scripts/build_h1b_dataset.py --input ~/Downloads/Employer_Data_Hub.csv
    python scripts/build_h1b_dataset.py --input lca.csv --min-filings 5

The script auto-detects the employer-name column and any approval/count columns;
if there's no count column it counts one filing per row.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

OUT_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "h1b_sponsors.csv"

EMPLOYER_HINTS = ("employer", "petitioner", "company name", "company", "sponsor")
COUNT_HINTS = ("initial approval", "continuing approval", "approval", "count",
               "filings", "petitions", "number of")


def _find_columns(header: list[str]) -> tuple[str | None, list[str]]:
    lower = {h: h.lower().strip() for h in header}
    employer_col = next(
        (h for h in header if any(k in lower[h] for k in EMPLOYER_HINTS)), None
    )
    count_cols = [h for h in header if any(k in lower[h] for k in COUNT_HINTS)]
    return employer_col, count_cols


def _to_int(value: str) -> int:
    try:
        return int(float(str(value).replace(",", "").strip() or 0))
    except ValueError:
        return 0


def build(input_path: pathlib.Path, source_label: str, min_filings: int) -> None:
    with open(input_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            sys.exit("Could not read a header row from the input file.")
        employer_col, count_cols = _find_columns(reader.fieldnames)
        if not employer_col:
            sys.exit(f"No employer column found. Headers seen: {reader.fieldnames}")
        print(f"employer column: {employer_col!r}; count columns: {count_cols or '(row count)'}")

        totals: dict[str, int] = {}
        for row in reader:
            name = (row.get(employer_col) or "").strip()
            if not name:
                continue
            filings = sum(_to_int(row.get(c, 0)) for c in count_cols) if count_cols else 1
            totals[name] = totals.get(name, 0) + max(filings, 0)

    rows = sorted(
        ((emp, n) for emp, n in totals.items() if n >= min_filings),
        key=lambda x: x[1], reverse=True,
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["employer", "filings", "source"])
        for emp, n in rows:
            writer.writerow([emp, n, source_label])
    print(f"Wrote {len(rows):,} sponsors to {OUT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, type=pathlib.Path,
                    help="Path to the downloaded USCIS/DOL CSV file.")
    ap.add_argument("--source", default="uscis",
                    help="Label stored in the 'source' column (e.g. uscis-2024).")
    ap.add_argument("--min-filings", type=int, default=1,
                    help="Drop employers with fewer than this many filings.")
    args = ap.parse_args()
    if not args.input.exists():
        sys.exit(f"Input not found: {args.input}")
    build(args.input, args.source, args.min_filings)


if __name__ == "__main__":
    main()
