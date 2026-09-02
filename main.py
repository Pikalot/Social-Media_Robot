from dotenv import load_dotenv
from db import get_connection, init_schema
from monitors.google import GoogleReviewMonitor
from reporting import save_new_reviews

load_dotenv()

BRANCH_CODES = {
    "Metropolitan Bank San Jose CA": "Br 02",
    "Metropolitan Bank San Francisco CA": "Br 03",
    "Metropolitan Bank Oakland CA": "Br 01",
}

def main():
    monitor = GoogleReviewMonitor()
    reviews = monitor.get_reviews(list(BRANCH_CODES.keys()))

    conn = get_connection()
    init_schema(conn)

    new_reviews = save_new_reviews(conn, reviews, BRANCH_CODES)
    for r in new_reviews:
        print(f"[{r.platform}] {r.author} — {r.rating}★ on {r.time}")
        print(f"  {r.text}\n")

    print(f"Saved {len(new_reviews)} new review(s). Run generate_report.py to export flagged ones to Excel.")
    conn.close()

if __name__ == "__main__":
    main()
