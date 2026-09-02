from datetime import date

import openpyxl
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

REPORT_PATH = "reports/Social Media Monitoring Log.xlsx"


def export_pending_reports(conn, path: str) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.branch_code, rv.platform, rv.link, r.status, r.description, rv.review_time
        FROM reports r
        JOIN reviews rv ON rv.id = r.review_id
        WHERE r.exported_at IS NULL
        ORDER BY r.created_at
    """)
    rows = cursor.fetchall()
    if not rows:
        cursor.close()
        return 0

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    report_ids = []
    for report_id, branch_code, platform, link, status, description, review_time in rows:
        ws.append([review_time, branch_code, platform, link, status])
        report_ids.append(report_id)
    wb.save(path)

    format_ids = ",".join(["%s"] * len(report_ids))
    cursor.execute(
        f"UPDATE reports SET exported_at = NOW() WHERE id IN ({format_ids})",
        report_ids,
    )
    conn.commit()
    cursor.close()
    return len(report_ids)


def main():
    conn = get_connection()
    exported = export_pending_reports(conn, REPORT_PATH)
    print(f"Exported {exported} new report(s) to {REPORT_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
