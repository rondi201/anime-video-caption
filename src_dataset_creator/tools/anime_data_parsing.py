import concurrent.futures
import datetime
import json
import logging
import os
import time
import re
from dataclasses import asdict
from logging import exception
from pathlib import Path
from typing import Any

import hydra
from accelerate.commands.config.update import description
from tqdm.auto import tqdm

from core.logger import LoggerFactory
from core.shikimori_gql_dataloader import ShikimoriGQLOnlineDataloader
from core.mal_data_grabber import MALAnimeDataGrabber
from core.kodik_fast_downloader import KodikFastDownloader, TranslationEnum
from core.anime_filters import AbstractAnimeFilter
from models import AnimeData, ExtendedAnimeData, RelatedAnimeData

ROOT = Path(__file__).parents[1]
MAIN_LOGGER = logging.getLogger()


def parse_shikimori_anime_data(
        data: dict[str, Any],
        with_extended_data: bool = True
) -> tuple[AnimeData | None, ExtendedAnimeData | None]:
    """ Парсинг данных из базы shikimori в удобный формат """
    try:
        anime_data = AnimeData(
            id=str(data["id"]),
            mal_id=str(data["malId"]),
            name=data["name"],
            title=data["english"],
            rating=data["rating"],
            score=float(data["score"]),
            released=datetime.date(
                year=data["releasedOn"]["year"],
                month=data["releasedOn"]["month"],
                day=data["releasedOn"]["day"] or 1
            ),
            genres = [genre["name"] for genre in data["genres"]],
            main_characters = [
                ch_data["character"]["name"]
                for ch_data in data["characterRoles"]
                if "Main" in ch_data["rolesEn"]
            ],
            popularity = sum(score_data["count"] for score_data in data["scoresStats"]),
            description = "",
            video_path = ""
        )
    except Exception as e:
        anime_id = data["id"]
        MAIN_LOGGER.warning(f"Cannot parse anime data by id '{anime_id}'. Skipping. Reason: {type(e)}: {e}")
        return None, None
    if not with_extended_data:
        return anime_data, None

    # Получим расширенное представление данных (для фильтров)
    try:
        extended_anime_data = ExtendedAnimeData(
            related_animes=[
                RelatedAnimeData(
                    id=rel_data["anime"]["id"],
                    title=rel_data["anime"]["name"],
                    released=datetime.date(
                        year=rel_data["anime"]["releasedOn"]["year"],
                        month=rel_data["anime"]["releasedOn"]["month"],
                        day=rel_data["anime"]["releasedOn"]["day"] or 1
                    ),
                )
                for rel_data in data["related"]
                if (rel_data["anime"] is not None and
                    rel_data["anime"]["status"] == "released" and
                    rel_data["anime"]["releasedOn"]["year"] is not None and
                    rel_data["anime"]["releasedOn"]["month"] is not None
                    )
            ],
            **asdict(anime_data)
        )
    except Exception as e:
        anime_id = data["id"]
        MAIN_LOGGER.warning(f"Cannot parse extra anime data by id '{anime_id}'. Skipping. Reason: {type(e)}: {e}")
        return anime_data, None

    return anime_data, extended_anime_data


def expansion_anime_data_from_mal(
        data: AnimeData,
        mal_data_grabber: MALAnimeDataGrabber,
) -> AnimeData:
    """ Получение дополнительных сведений об Аниме из MyAnimeList """
    # Для каждого аниме получим аннотацию на английском
    mal_data = None
    retries = 0
    while retries < 5:
        retries += 1
        try:
            mal_data = mal_data_grabber.get_anime_by_id(
                data.mal_id,
                fields=["id", "title", "synopsis"]
            )
            break
        except Exception as e:
            if retries < 5:
                MAIN_LOGGER.warning(
                    f"Unable get data from MyAnimeList. Start trying after 1 sec. Reason: {type(e)}: {e}"
                )
                time.sleep(1)
            else:
                raise
    # Проверка на неожиданное поведение
    if mal_data is None:
        raise ValueError(f"`MALAnimeDataGrabber.get_anime_by_id` return None for mal_id = {data.mal_id}")
    # Получим хвост, связанный с автором описания
    description_text, _, source_line = mal_data["synopsis"].rpartition("\n")
    # Если строка окружена скобками - информация об источнике
    if source_line.startswith(("[", ")")) and source_line.endswith(("[", ")")):
        en_description = description_text
    else:
        en_description = mal_data["synopsis"]
    # Присвоим описание к данным
    data.description = en_description.strip()

    return data


def expansion_anime_data_from_kodik(
        data: AnimeData,
        kodik_downloader: KodikFastDownloader,
        save_path: Path,
        fps: int | float | None = None,
        with_audio: bool = False,
        quality: str = "720",
) -> AnimeData:
    """ Скачивание первой серии аниме с Kodik """
    # Сформируем путь для сохранения видео
    if not save_path.exists():
        # Получим допустимые трансляции и выберем первую (первые в списке - озвучки, с которых удалится аудио)
        available_translation = kodik_downloader.get_available_translations(
            id=data.id,
            id_type="shikimori"
        )
        # Получим только трансляции с озвучкой, чтобы не было текста на экране
        available_translation = [tr for tr in available_translation if tr.type == TranslationEnum.DUB]
        if not available_translation:
            raise RuntimeError(f"No found available sub translations for {data.name} with id {data.id}")
        translation_id = available_translation[0].id
        retries = 0
        kodik_save_path = None
        while retries < 2:
            retries += 1
            try:
                # Получим видеозапись первой серии
                kodik_save_path = kodik_downloader.fast_download(
                    id=data.id,
                    id_type="shikimori",
                    seria_num=1,
                    translation_id=translation_id,
                    quality=str(quality),
                    output_dir=save_path.parent,
                    output_name=save_path.stem,
                    fps=fps,
                    with_audio=with_audio
                )
            except Exception as e:
                if retries < 2:
                    MAIN_LOGGER.warning(
                        f"Unable get anime video from Kodik for {data.name} with id {data.id}. "
                        f"Skip sample. Reason: {type(e)}: {e}"
                    )
                    time.sleep(5)
                else:
                    raise
            else:
                # Очистим кеш
                kodik_downloader.clear_title_cache(
                    id=data.id,
                    id_type="shikimori",
                    seria_num=1,
                    translation_id=translation_id,
                    quality="720",
                )

            # Если видео не найдено
            if kodik_save_path is None:
                if len(available_translation) > 1:
                    # Очистим кеш
                    kodik_downloader.clear_title_cache(
                        id=data.id,
                        id_type="shikimori",
                        seria_num=1,
                        translation_id=translation_id,
                        quality="720",
                    )
                    # Попробуем поменять трансляцию
                    available_translation = available_translation[1:]
                    translation_id = available_translation[0].id
                    continue
            # Если видео найдено - закончим попытки
            else:
                break

        # Если все равно не удалось найти
        if kodik_save_path is None:
            raise RuntimeError(f"No found downloadable translation for {data.name} with id {data.id}")
        save_path = kodik_save_path

    data.video_path = save_path.as_posix()

    return data


def main(
        shiki_dataset: ShikimoriGQLOnlineDataloader ,
        mal_data_grabber: MALAnimeDataGrabber,
        kodik_downloader: KodikFastDownloader,
        anime_filters: list[AbstractAnimeFilter] | None = None,
        max_samples: int | None = None,
        save_root: str = "run/anime_dataset",
        fps: int | float | None = None,
        with_audio: bool = False,
        quality: str = "720",
        num_workers: int = 1,
        update_annotation: bool = False,
        video_download_timeout: int = 180,
):
    save_root: Path = Path(save_root)
    save_root.mkdir(parents=True, exist_ok=True)

    anime_dataset = {
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "language": "en",
        "animes": []
    }
    parsed_anime_ids: set[str] = set()

    annotation_path = Path(save_root / "annotation.json")
    # Если файл анатации уже существует
    if annotation_path.exists():
        if update_annotation:
            # Загрузим из него данные
            with open(annotation_path, "r", encoding="utf-8") as f:
                current_annotation = json.load(f)
            anime_dataset["created_at"] = current_annotation["created_at"]
            anime_dataset["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            anime_dataset["animes"] = current_annotation["animes"]
            for anime in anime_dataset["animes"]:
                parsed_anime_ids.add(str(anime["id"]))
        else:
            raise FileExistsError(f"Annotation file by path '{annotation_path}' already exists")

    current_batch = 0
    pbar = tqdm(initial=len(parsed_anime_ids), ncols=90, desc = "Start parsing...", unit="titles")
    while True:
        pbar.set_description(f"Querying data from Shikimori...")
        shiki_retries = 0
        try:
            # Получим партию данных
            shiki_data_batch = shiki_dataset[current_batch]["animes"]
            # Если нет данных - закончились страницы
            if len(shiki_data_batch) == 0:
                MAIN_LOGGER.info("Research end of Shikimori dataset.")
                break
        except Exception as e:
            if shiki_retries > 5:
                raise
            MAIN_LOGGER.warning(
                f"Unable get data from shikimori. Start trying after 1 sec. Reason: {type(e)}: {e}"
            )
            shiki_retries += 1
            time.sleep(1)
            continue

        # Отфильтруем аниме, для которых уже известны данные
        shiki_data_batch = [data for data in shiki_data_batch if str(data["id"]) not in parsed_anime_ids]
        # Распарсим данные
        anime_data_batch = []
        for data in shiki_data_batch:
            pbar.set_description(f"Parse Shikimori data for {data["name"]:20} (id {data["id"]})...")
            # Получим распарсенные данные для аниме на основе данных с Shikimori
            anime_data, extended_anime_data = parse_shikimori_anime_data(
                data,
                with_extended_data=bool(anime_filters)
            )
            # Проверим данные и отфильтруем
            if anime_filters:
                pbar.set_description(f"Filtering Shikimori data for {data["name"]:20} (id {data["id"]})...")
                # Если распарсить данные об аниме не получилось
                if extended_anime_data is None:
                    continue
                # Пройдёмся по каждому фильтру
                for a_filter in anime_filters:
                    valid = a_filter.filter(extended_anime_data)
                    # Если данные не валидны - удалим
                    if not valid:
                        MAIN_LOGGER.debug(
                            f"Anime {anime_data.name} with id {anime_data.id} has dropped by filter {a_filter}"
                        )
                        anime_data = None
                        break
            # Если распарсить или провалидировать данные об аниме не получилось - пропустим
            if anime_data is None:
                continue
            # Добавим данные аниме в список для дальнейшего использования
            anime_data_batch.append(anime_data)

        def _expansion_anime_data(data: AnimeData) -> AnimeData:
            """ Объединим несколько расширителей данных в единый конвеер для запуска в параллельных потоках """
            safety_name = re.sub(r'[\\/:"*?<>|.,]+', "", data.name)
            video_save_path = Path(save_root, "videos", str(data.id), f"{safety_name}_S1_E1_{quality}.mp4")

            # Переименовывание со старого формата на новый
            # old_save_dir = Path(save_root, "videos", safety_name)
            # if old_save_dir.exists():
            #     old_save_dir.rename(video_save_path.parent)
            #     MAIN_LOGGER.debug(f"Old folder {old_save_dir} successfully renamed to {video_save_path.parent}")
            # else:
            #     MAIN_LOGGER.debug(f"No found old save dir {old_save_dir} for {data.title} with id {data.id}")

            data = expansion_anime_data_from_mal(data, mal_data_grabber)
            data = expansion_anime_data_from_kodik(
                data,
                kodik_downloader,
                save_path=video_save_path,
                fps=fps,
                with_audio=with_audio,
                quality=quality,
            )
            return data

        pbar.set_description(f"Wait external data from extra source...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Запустим обработку всех данных в отдельных потоках
            futures = [executor.submit(_expansion_anime_data, data) for data in anime_data_batch]
            futures_data = {futures: data for futures, data in zip(futures, anime_data_batch)}
            # Пройдёмся по каждому завершенному
            try:
                for future in concurrent.futures.as_completed(
                        futures,
                        timeout=video_download_timeout*len(futures)/num_workers
                ):
                    # Получим результат
                    try:
                        anime_data = future.result()
                    except Exception as e:
                        future_data = futures_data[future]
                        MAIN_LOGGER.warning(
                            f"Cannot get external data for {future_data.name} with id {future_data.id}. Reason: {type(e)}: {e}"
                        )
                        continue

                    # Сделаем путь до файла видео относительным
                    anime_data.video_path = str(
                        Path(anime_data.video_path).relative_to(save_root)
                    )
                    # Добавим сохраненное аниме в список
                    parsed_anime_ids.add(anime_data.id)
                    # Сохраним данные об аниме
                    anime_dataset["animes"].append(anime_data.to_json())
                    # Сохраним данные во временный json
                    tmp_annotation_path = annotation_path.with_stem(f"{annotation_path.stem}~")
                    with open(tmp_annotation_path, "w") as f:
                        json.dump(anime_dataset, f, indent=4)
                    # Заменим исходный json временным
                    annotation_path.unlink(missing_ok=True)
                    tmp_annotation_path.rename(annotation_path)

                    pbar.set_description(f"Save {anime_data.name:20} (id {anime_data.id})...")
                    pbar.update(1)
            except TimeoutError as e:
                MAIN_LOGGER.warning(f'Several anime was dropped by preparing timeout')
        # Засчитаем успешность обработки партии
        current_batch += 1
        # Если собрано достаточно данных - завершим
        if max_samples and len(parsed_anime_ids) > max_samples:
            MAIN_LOGGER.info("Stop parsing after reaching the `max_samples` threshold.")
            break
    pbar.close()

if __name__ == "__main__":
    # Найстроим логирование
    LOG_FILE = Path(ROOT, 'logs' , f'{Path(__file__).stem}.txt')
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Saving logs to:", LOG_FILE)
    LoggerFactory.setting(
        log_level=logging.INFO,
        show=True,
        in_file=True,
        log_file=LOG_FILE,
    )
    MAIN_LOGGER = LoggerFactory.get_logger(Path(__file__).stem.capitalize())
    # Загрузим словарь конфигурации API
    config_dir = Path(ROOT, "data", "config").absolute()
    with hydra.initialize_config_dir(
            config_dir=str(config_dir),
            version_base=None
    ):
        api_config = hydra.compose(config_name="anime_data_parsing")
    # Инициализируем данные из конфигурации
    api_config = hydra.utils.instantiate(api_config)
    # Запустим главный цикл обработки
    main(**api_config)
