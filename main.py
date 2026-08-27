from dotenv import load_dotenv
from monitors.google import GoogleReviewMonitor

load_dotenv()

def main():
    monitor = GoogleReviewMonitor()
    reviews = monitor.get_reviews(["Metropolitan Bank San Jose CA", " Metropolitan Bank San Francisco CA", "Metropolitan Bank Oakland CA"])
    for r in reviews:
        print(f"[{r.platform}] {r.author} — {r.rating}★ on {r.time}")
        print(f"  {r.text}\n")

if __name__ == "__main__":
    main()
