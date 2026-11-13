from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Review:
    author: str
    rating: int
    text: str
    time: str
    platform: str
    business: str = ""
    link: str = ""


class Platform(ABC):
    def __init__(self):
        # (business, platform) pairs where get_reviews() returned EVERY review,
        # so a review missing from the result really was removed.
        self.complete: set[tuple[str, str]] = set()

    @abstractmethod
    def get_reviews(self, business_names: list[str]) -> list[Review]:
        pass
