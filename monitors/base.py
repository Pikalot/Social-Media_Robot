from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Review:
    author: str
    rating: int
    text: str
    time: str
    platform: str


class Platform(ABC):
    @abstractmethod
    def get_reviews(self, business_name: str) -> list[Review]:
        pass
