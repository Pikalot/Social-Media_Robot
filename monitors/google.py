import os
import requests
from datetime import datetime
from .base import Platform, Review


class GoogleReviewMonitor(Platform):
    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")

    def _find_place_id(self, business_name: str) -> str | None:
        resp = requests.get(
            f"{self.BASE_URL}/findplacefromtext/json",
            params={
                "input": business_name,
                "inputtype": "textquery",
                "fields": "place_id,name,formatted_address",
                "key": self.api_key,
            },
        )
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return None
        place = candidates[0]
        print(f"[Google] Found: {place.get('name')} — {place.get('formatted_address')}")
        return place["place_id"]

    def get_reviews(self, business_name: str) -> list[Review]:
        place_id = self._find_place_id(business_name)
        if not place_id:
            print(f"[Google] No business found for: {business_name}")
            return []

        resp = requests.get(
            f"{self.BASE_URL}/details/json",
            params={
                "place_id": place_id,
                "fields": "reviews",
                "reviews_sort": "newest",
                "key": self.api_key,
            },
        )
        resp.raise_for_status()
        raw_reviews = resp.json().get("result", {}).get("reviews", [])

        reviews = []
        for r in raw_reviews:
            reviews.append(Review(
                author=r.get("author_name", "Anonymous"),
                rating=r.get("rating", 0),
                text=r.get("text", ""),
                time=datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d") if "time" in r else "",
                platform="Google",
            ))
        return reviews
