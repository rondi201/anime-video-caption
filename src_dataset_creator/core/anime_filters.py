from abc import ABC, abstractmethod

from models import ExtendedAnimeData


class AbstractAnimeFilter(ABC):
    @abstractmethod
    def filter(self, data: ExtendedAnimeData) -> bool:
        pass


class FirstSeasonAnimeFilter(AbstractAnimeFilter):
    """
    Фильтр для сохранения аниме, являющихся первым сезоном.

    Основан на поиске связанного аниме, вышедшего раньше, чем текущее.
    В таком случае текущее аниме - сиквел и отбрасывается.
    """
    def filter(self, data: ExtendedAnimeData) -> bool:
        # Пройдемся по всем связанным аниме
        for rel_data in data.related_animes:
            # Если есть более раннее аниме - значит это сиквел
            if rel_data.released < data.released:
                return False
        return True

    def __str__(self):
        return self.__class__.__name__