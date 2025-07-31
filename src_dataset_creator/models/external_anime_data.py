from dataclasses import dataclass
from datetime import datetime

from .anime_data import AnimeData


@dataclass
class RelatedAnimeData:
    id: str
    title: str
    released: datetime.date


@dataclass
class ExtendedAnimeData(AnimeData):
    related_animes: list[RelatedAnimeData]

    def to_json(self):
        raise NotImplementedError("to_json not implemented")
