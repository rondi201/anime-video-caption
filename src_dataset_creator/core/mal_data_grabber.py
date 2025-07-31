import requests
from typing import Any


class MALAnimeDataGrabber:
    ALL_FIELDS = ['id', 'title', 'main_picture', 'alternative_titles', 'start_date', 'end_date', 'synopsis', 'mean', 'rank', 'popularity', 'num_list_users', 'num_scoring_users', 'nsfw', 'created_at', 'updated_at', 'media_type', 'status', 'genres', 'my_list_status', 'num_episodes', 'start_season', 'broadcast', 'source', 'average_episode_duration', 'rating', 'pictures', 'background', 'related_anime', 'related_manga', 'recommendations', 'studios', 'statistics']

    def __init__(
            self,
            client_id: str,
            url = "https://api.myanimelist.net/v2",
    ):
        self.client_id = client_id
        self.url = url

        self.session = requests.Session()
        # Добавим id клиента в заголовок
        self.session.headers.update(
            {'X-MAL-Client-ID': client_id}
        )

    def get_anime_by_id(
            self,
            id: int | str,
            fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Получение информации об аниме по MAL id.

        Args:
            id (int | str): id аниме в базе MAL.
            fields (list[str]): Список полей, запрашиваемых из базы MAL. Если не заданно - запрашиваются все.
                Доступные элементы списка: id, title,main_picture, alternative_titles, start_date, end_date, synopsis,
                mean,rank,popularity, num_list_users, num_scoring_users, nsfw, created_at, updated_at, media_type,
                status, genres, my_list_status, num_episodes, start_season, broadcast, source, average_episode_duration,
                rating, pictures, background, related_anime, related_manga, recommendations, studios, statistics.

        Returns:
            Данные об аниме с сайта MAL со списком `fields` полей вида:
            {
                "id": 52991,
                "title": "Sousou no Frieren",
                "main_picture": {
                    "medium": "https://cdn.myanimelist.net/images/anime/1015/138006.jpg",
                    "large": "https://cdn.myanimelist.net/images/anime/1015/138006l.jpg"
                },
                "alternative_titles": {
                    "synonyms": [
                        "Frieren at the Funeral",
                        "Frieren The Slayer"
                    ],
                    "en": "Frieren: Beyond Journey's End",
                    "ja": "葬送のフリーレン"
                },
                "start_date": "2023-09-29",
                "end_date": "2024-03-22",
                "synopsis": "...",
                "mean": 9.3,
                "rank": 1,
                "popularity": 137,
                "num_list_users": 1178622,
                "num_scoring_users": 701605,
                "nsfw": "white",
                "created_at": "2022-09-09T10:01:30+00:00",
                "updated_at": "2025-06-05T23:31:41+00:00",
                "media_type": "tv",
                "status": "finished_airing",
                "genres": [
                    {
                        "id": 2,
                        "name": "Adventure"
                    },
                    ...
                ],
                "num_episodes": 28,
                "start_season": {
                    "year": 2023,
                    "season": "fall"
                },
                "broadcast": {
                    "day_of_the_week": "friday",
                    "start_time": "23:00"
                },
                "source": "manga",
                "average_episode_duration": 1470,
                "rating": "pg_13",
                "pictures": [
                    {
                        "medium": "https://cdn.myanimelist.net/images/anime/1675/127908.jpg",
                        "large": "https://cdn.myanimelist.net/images/anime/1675/127908l.jpg"
                    },
                    ...
                ],
                "background": "Sousou no Frieren was released on Blu-ray and DVD in seven volumes from January 24, 2024, to July 17, 2024.",
                "related_anime": [
                    {
                        "node": {
                            "id": 56805,
                            "title": "Yuusha",
                            "main_picture": {
                                "medium": "https://cdn.myanimelist.net/images/anime/1947/138863.jpg",
                                "large": "https://cdn.myanimelist.net/images/anime/1947/138863l.jpg"
                            }
                        },
                        "relation_type": "other",
                        "relation_type_formatted": "Other"
                    },
                    ...
                ],
                "related_manga": [],
                "recommendations": [
                    {
                        "node": {
                            "id": 33352,
                            "title": "Violet Evergarden",
                            "main_picture": {
                                "medium": "https://cdn.myanimelist.net/images/anime/1795/95088.webp",
                                "large": "https://cdn.myanimelist.net/images/anime/1795/95088l.webp"
                            }
                        },
                        "num_recommendations": 26
                    },
                    ...
                ],
                "studios": [
                    {
                        "id": 11,
                        "name": "Madhouse"
                    }
                ],
                "statistics": {
                    "status": {
                        "watching": "220233",
                        "completed": "727307",
                        "on_hold": "23115",
                        "dropped": "15565",
                        "plan_to_watch": "192171"
                    },
                    "num_list_users": 1178391
                }
            }
        """
        response = self.session.get(
            "/".join([self.url.rstrip('/'), "anime", str(id)]),
            params={"fields": fields or self.ALL_FIELDS},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data