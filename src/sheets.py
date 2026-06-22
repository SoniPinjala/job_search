"""Google Sheets output.

Appends new postings to a private Sheet, sets up the Applied? dropdown via data
validation, hides the dedupe key column, and never overwrites your edits.
Auth: service-account JSON from GOOGLE_SERVICE_ACCOUNT_JSON (CI Secret) or a
local service_account.json file. The Sheet must be shared (Editor) with the
service account's email.
"""
from __future__ import annotations

import json
import logging

import gspread
from google.oauth2.service_account import Credentials

from .config import env
from .models import SHEET_HEADERS, JobPosting

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
WORKSHEET_NAME = "Jobs"
APPLIED_OPTIONS = ["Applied", "Not applied"]
MAX_ROWS = 5000

_APPLIED_IDX = SHEET_HEADERS.index("Applied?")
_KEY_IDX = SHEET_HEADERS.index("_key")


def _credentials() -> Credentials:
    raw = env("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    path = env("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=SCOPES)


def service_account_email() -> str:
    try:
        return _credentials().service_account_email
    except Exception:  # pragma: no cover
        return "(could not read service account email)"


class JobSheet:
    def __init__(self, sheet_id: str | None = None):
        self.sheet_id = sheet_id or env("GOOGLE_SHEET_ID")
        if not self.sheet_id:
            raise RuntimeError("GOOGLE_SHEET_ID is not set")
        gc = gspread.authorize(_credentials())
        self.sh = gc.open_by_key(self.sheet_id)
        self.ws = self._get_or_create_ws()
        self.ensure_headers()

    def _get_or_create_ws(self) -> "gspread.Worksheet":
        try:
            return self.sh.worksheet(WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            return self.sh.add_worksheet(
                title=WORKSHEET_NAME, rows=MAX_ROWS, cols=len(SHEET_HEADERS)
            )

    def ensure_headers(self) -> None:
        if self.ws.row_values(1)[: len(SHEET_HEADERS)] != SHEET_HEADERS:
            self.ws.update(range_name="A1", values=[SHEET_HEADERS])
            self.apply_formatting()

    def apply_formatting(self) -> None:
        """Freeze + bold the header, add the Applied? dropdown, hide _key."""
        gid = self.ws.id
        requests = [
            {"updateSheetProperties": {
                "properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {
                "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold"}},
            {"setDataValidation": {
                "range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": MAX_ROWS,
                          "startColumnIndex": _APPLIED_IDX, "endColumnIndex": _APPLIED_IDX + 1},
                "rule": {
                    "condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": o} for o in APPLIED_OPTIONS]},
                    "showCustomUi": True, "strict": False}}},
            {"updateDimensionProperties": {
                "range": {"sheetId": gid, "dimension": "COLUMNS",
                          "startIndex": _KEY_IDX, "endIndex": _KEY_IDX + 1},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        ]
        self.sh.batch_update({"requests": requests})

    def existing_keys(self) -> set[str]:
        values = self.ws.col_values(_KEY_IDX + 1)  # 1-based column
        return {v for v in values[1:] if v}

    def append(self, postings: list[JobPosting]) -> int:
        if not postings:
            return 0
        rows = [p.to_row() for p in postings]
        self.ws.append_rows(rows, value_input_option="USER_ENTERED")
        log.info("sheet: appended %d rows", len(rows))
        return len(rows)
