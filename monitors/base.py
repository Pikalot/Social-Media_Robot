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
    @abstractmethod
    def get_reviews(self, business_names: list[str]) -> list[Review]:
        pass
