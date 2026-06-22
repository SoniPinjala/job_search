#!/usr/bin/env python3
"""One-time Google Sheet setup + connectivity check.

Run this after creating the Sheet, the service account, and setting
GOOGLE_SHEET_ID + credentials. It creates the Jobs worksheet, writes headers,
adds the Applied? dropdown, and tells you which email to share the Sheet with.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.sheets import JobSheet, service_account_email  # noqa: E402


def main() -> None:
    print(f"Service account email: {service_account_email()}")
    print("→ Share your Google Sheet with that email as an EDITOR if you haven't.\n")
    try:
        sheet = JobSheet()
    except Exception as exc:
        sys.exit(f"❌ Could not open the sheet: {exc}\n"
                 "Check GOOGLE_SHEET_ID, the credentials, and that the sheet is shared.")
    sheet.apply_formatting()
    print(f"✅ Connected. Worksheet '{sheet.ws.title}' is ready with headers + dropdown.")
    print(f"   Existing rows tracked: {len(sheet.existing_keys())}")
    print(f"   https://docs.google.com/spreadsheets/d/{sheet.sheet_id}")


if __name__ == "__main__":
    main()
