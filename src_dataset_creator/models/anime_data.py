from typing import Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AnimeData:
    id: str
    mal_id: str
    name: str
    title: str
    rating: str
    score: float
    released: datetime.date
    genres: list[str]
    main_characters: list[str]
    popularity: int
    description: str
    video_path: str

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data['released'] = data['released'].strftime("%Y-%m-%d %H:%M:%S")
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AnimeData":
        data['released'] = datetime.strptime(data['released'], "%Y-%m-%d %H:%M:%S")
        return cls(**data)