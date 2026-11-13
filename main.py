from dotenv import load_dotenv
from db import get_connection, init_schema
from monitors.google import GoogleReviewMonitor
from generate_report import REPORT_PATH, pull_statuses_from_excel, sync_reports_to_excel
from reporting import sync_reviews

load_dotenv()

BRANCH_CODES = {
    "Metropolitan Bank San Jose CA": "Br 02",
    "Metropolitan Bank San Francisco CA": "Br 03",
    "Metropolitan Bank Oakland CA": "Br 01",
    "Metropolitan Bank Oakland Chinatown CA": "Br 04",
}

# Fixed Google place IDs. Searching by name is unreliable: Google sometimes
# matches "Oakland CA" to the Chinatown branch. A branch without an ID here
# falls back to a name search.
GOOGLE_PLACE_IDS = {
    "Metropolitan Bank San Jose CA": "ChIJZW-EGr0yjoAR6IC9I4nSPrc",             # 1816 Tully Rd #192
    "Metropolitan Bank San Francisco CA": "ChIJ3byETvKAhYARjwRestYERhk",        # 1355 Stockton St
    "Metropolitan Bank Oakland CA": "ChIJr9RpkzmHj4AR6a1j9owxIu8",              # 250 E 18th St 3rd floor
    "Metropolitan Bank Oakland Chinatown CA": "ChIJA8c8E7aAj4ARRq6cjpuIFGI",    # 360 8th St
}

def main():
    conn = get_connection()
    init_schema(conn)

    # 1. Excel -> DB: pick up statuses people changed by hand.
    pulled = pull_statuses_from_excel(conn, REPORT_PATH)
    print(f"Excel: {pulled} status change(s) copied to the database.")

    # 2. Scan reviews -> DB.
    monitor = GoogleReviewMonitor(GOOGLE_PLACE_IDS)
    reviews = monitor.get_reviews(list(BRANCH_CODES.keys()))
    new_reviews = sync_reviews(conn, reviews, BRANCH_CODES, monitor.complete)
    for r in new_reviews:
        print(f"[{r.platform}] {r.author} — {r.rating}★ on {r.time}")
        print(f"  {r.text}\n")
    print(f"Saved {len(new_reviews)} new review(s).")

    # 3. DB -> Excel: write only what changed.
    appended, updated = sync_reports_to_excel(conn, REPORT_PATH)
    print(f"Excel: {appended} new row(s), {updated} updated row(s).")
    conn.close()

if __name__ == "__main__":
    main()
