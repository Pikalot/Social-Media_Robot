import os
from copy import copy
from datetime import datetime

import openpyxl
from dotenv import load_dotenv

from db import get_connection, init_schema
from reporting import CLOSED_STATUSES

load_dotenv()

REPORT_PATH = "reports/Social Media Monitoring Log.xlsx"

# Existing sheet layout: Date | Branch / Admin | Site | Link | Status | Description | Comments
COL_DATE, COL_BRANCH, COL_SITE, COL_LINK, COL_STATUS, COL_DESC, COL_COMMENTS = range(1, 8)
COL_REPORT_ID = 8
REPORT_ID_HEADER = "Report ID"


def _last_used_row(ws) -> int:
    """Last row with any value (ws.max_row counts formatted-but-empty rows)."""
    for row in range(ws.max_row, 1, -1):
        if any(ws.cell(row, c).value not in (None, "") for c in range(1, COL_REPORT_ID + 1)):
            return row
    return 1


def _copy_row_style(ws, src_row: int, dst_row: int) -> None:
    """Make a new row look like the row above it (font, borders, date format)."""
    for col in range(COL_DATE, COL_COMMENTS + 1):
        src, dst = ws.cell(src_row, col), ws.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)


def _to_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return value


def excel_is_open(path: str) -> bool:
    """Excel keeps a '~$<name>' lock file next to a workbook while it is open."""
    folder, name = os.path.split(path)
    return os.path.exists(os.path.join(folder, "~$" + name))


def pull_statuses_from_excel(conn, path: str) -> int:
    """Step 1 of every run: copy each Excel row's Status into the DB, so the
    scan decides with the statuses people set by hand. Excel is only read.

    Excel wins, except over a bot change not yet written to Excel (synced = 0)
    unless Excel says Done/Closed, which is final. Returns rows updated."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    excel_status = {}
    for row in ws.iter_rows(min_row=2, max_col=COL_REPORT_ID, values_only=True):
        rid, status = row[COL_REPORT_ID - 1], row[COL_STATUS - 1]
        if rid is not None and isinstance(status, str) and status.strip():
            excel_status[int(rid)] = status.strip()
    wb.close()
    if not excel_status:
        return 0

    cursor = conn.cursor()
    placeholders = ",".join(["%s"] * len(excel_status))
    cursor.execute(
        f"SELECT id, status, synced FROM reports WHERE id IN ({placeholders})",
        list(excel_status),
    )
    changes = []
    for report_id, db_status, synced in cursor.fetchall():
        new = excel_status[report_id]
        if new == db_status:
            continue
        if synced == 0 and new not in CLOSED_STATUSES:
            continue  # bot change pending; it will be written to Excel this run
        changes.append((new, report_id))
        print(f"[Excel] Report {report_id}: {db_status} -> {new}")
    if changes:
        cursor.executemany("UPDATE reports SET status = %s WHERE id = %s", changes)
        conn.commit()
    cursor.close()
    return len(changes)


def sync_reports_to_excel(conn, path: str) -> tuple[int, int]:
    """Write only the reports that differ from Excel (synced = 0):
    new ones are appended, changed ones are updated in place by Report ID.
    On an existing row only Status and Date are rewritten; Description,
    Comments and rows without a Report ID are never touched. A row already
    'Done'/'Closed' in Excel is never touched (its status is copied to the DB).
    Returns (appended, updated)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.branch_code, rv.platform, rv.link, r.status, r.description, rv.review_time
        FROM reports r
        JOIN reviews rv ON rv.id = r.review_id
        WHERE r.synced = 0
        ORDER BY r.created_at, r.id
    """)
    rows = cursor.fetchall()
    if not rows:
        cursor.close()
        return 0, 0
    if excel_is_open(path):
        # Saving now would be lost (or clash) when Excel saves its own copy.
        # The changes stay pending (synced = 0) and go out on the next run.
        print(f"[Excel] {path} is open in Excel - close it and run again. "
              f"{len(rows)} change(s) waiting.")
        cursor.close()
        return 0, 0

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    if ws.cell(1, COL_REPORT_ID).value != REPORT_ID_HEADER:
        ws.cell(1, COL_REPORT_ID).value = REPORT_ID_HEADER

    # Report ID -> Excel row, for rows this script wrote earlier.
    last_row = _last_used_row(ws)
    row_by_id = {}
    for row in range(2, last_row + 1):
        rid = ws.cell(row, COL_REPORT_ID).value
        if rid is not None:
            row_by_id[int(rid)] = row

    appended = updated = 0
    closed_in_excel = []
    for report_id, branch_code, platform, link, status, description, review_time in rows:
        row = row_by_id.get(report_id)
        if row is None:
            last_row += 1
            row = last_row
            _copy_row_style(ws, row - 1, row)
            ws.cell(row, COL_BRANCH).value = branch_code
            ws.cell(row, COL_SITE).value = platform
            ws.cell(row, COL_LINK).value = link
            ws.cell(row, COL_DESC).value = description
            ws.cell(row, COL_REPORT_ID).value = report_id
            appended += 1
            ws.cell(row, COL_DATE).value = _to_date(review_time)
        else:
            excel_status = ws.cell(row, COL_STATUS).value
            if excel_status in CLOSED_STATUSES:
                # Closed in Excel (possibly by hand): done is done. Leave the
                # row alone and record the closure in the DB.
                if status != excel_status:
                    closed_in_excel.append((excel_status, report_id))
                continue
            updated += 1
            if status not in CLOSED_STATUSES:
                ws.cell(row, COL_DATE).value = _to_date(review_time)
        ws.cell(row, COL_STATUS).value = status

    wb.save(path)

    if closed_in_excel:
        cursor.executemany("UPDATE reports SET status = %s WHERE id = %s", closed_in_excel)
    ids = [r[0] for r in rows]
    placeholders = ",".join(["%s"] * len(ids))
    cursor.execute(
        f"UPDATE reports SET synced = 1, exported_at = COALESCE(exported_at, NOW()) "
        f"WHERE id IN ({placeholders})",
        ids,
    )
    conn.commit()
    cursor.close()
    return appended, updated


def main():
    conn = get_connection()
    init_schema(conn)
    pull_statuses_from_excel(conn, REPORT_PATH)
    appended, updated = sync_reports_to_excel(conn, REPORT_PATH)
    print(f"Excel: {appended} new row(s), {updated} updated row(s) in {REPORT_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
