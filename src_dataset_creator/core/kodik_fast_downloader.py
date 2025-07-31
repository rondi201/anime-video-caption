"""
Based on https://github.com/YaNesyTortiK/Kodik-Download-Watch/blob/main/fast_download.py
"""
import enum
import shutil
from dataclasses import dataclass
from typing import List, Literal

import requests
import os
import concurrent.futures
import subprocess
from hashlib import md5
from pathlib import Path

from anime_parsers_ru import KodikParser

# Проверим доступность lxml
try:
    import lxml
    USE_LXML = True
except ImportError:
    USE_LXML = False


def check_ffmpeg():
    """
    Raises ModuleNotFound error if ffmpeg isn't installed or can't be used by subprocess
    """
    try:
        subprocess.call('ffmpeg', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        raise ModuleNotFoundError('Ffmpeg is required to use fast download.')


class TranslationEnum(enum.Enum):
    """ Варианты перевода трансляции """
    DUB = 'Озвучка'
    SUB = 'Субтитры'
    UNK = 'Неизвестно'

@dataclass
class TranslationInfo:
    """ Информация о трансляции """
    id: str
    """ ID Трансляции """
    type: TranslationEnum
    """ Тип трансляции """
    name: str
    """ Имя команды озвучки/перевода с количеством серий """


class KodikFastDownloader:
    def __init__(
            self,
            tmp_root: str | Path = 'tmp',
            segment_timeout: int = 40,
    ):
        self.tmp_root = Path(tmp_root)
        self.kodik_parser = KodikParser(use_lxml=USE_LXML)
        self.segment_timeout = segment_timeout

    @staticmethod
    def _get_url_data(url: str, headers: dict = None):
        return requests.get(url, headers=headers, timeout=10).text

    def _get_download_link(self, id: str, id_type: str, seria_num: int, translation_id: str):
        return self.kodik_parser.get_link(id, id_type, seria_num, translation_id)[0]

    def get_available_translations(self, id: str, id_type: str) -> list[TranslationInfo]:
        """
        Получить виды доступных трансляций.

        Args:
            id (str): Id сериала на Шикимори/Кинопоиске
            id_type (str): тип id 'shikimori' или 'kinopoisk' ('sh' или 'kp')

        Returns:
            (list[TranslationInfo]): Информация о доступных переводах
        """
        player_data = self.kodik_parser.get_info(id, id_type)
        result = [
            TranslationInfo(
                id=data['id'],
                type=TranslationEnum(data['type']),
                name=data['name']
            ) for data in player_data['translations']
        ]
        return result

    @staticmethod
    def _get_segments(manifest: str, original_link: str) -> list[str]:
        res = []
        manifest = manifest.split('\n')[7:]
        for i in range(0, len(manifest), 2):
            if manifest[i].strip() != '':
                res.append([original_link + manifest[i][2:], manifest[i].split('-')[1]])
        return res

    @staticmethod
    def _download_segment(link: str, path: str | Path, timeout=None):
        try:
            res = requests.get(link, timeout=timeout)
        except requests.exceptions.SSLError:
            # Sometimes this error can appear. Possibly because of high count of downloads at the same time
            res = requests.get(link, timeout=timeout)
        with open(path, 'wb') as f:
            f.write(res.content)

    @staticmethod
    def _combine_segments(
            directory: str | Path,
            output_path: str | Path,
            fps: str | None = None,
            with_audio: bool = True,
            hwaccel: str | None = 'cuda'
    ):
        directory: Path = Path(directory)
        files = list(path for path in directory.iterdir() if path.suffix == '.ts')
        r = ''
        for file in sorted(files, key=lambda path: int(path.stem)):
            r += f"file {file.name}\n"
        with open(directory / 'files.txt', 'w') as f:
            f.write(r)
        ffmpeg_output_param = []
        if not with_audio:
            ffmpeg_output_param.append('-an')
        if fps is not None:
            ffmpeg_output_param.append(f'-r {fps}')
        else:
            ffmpeg_output_param.append(f'-c copy')
        try:
            subprocess.run(
                f'ffmpeg '
                f'-y {"-hwaccel " + hwaccel if not hwaccel is None else ""} '
                f'-f concat '
                f'-safe 0 '
                f'-i {directory / "files.txt"} '
                f'{" ".join(ffmpeg_output_param)} '
                f'"{output_path}"',
                # capture_output=True,
                check=True,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            print(e.stderr.decode())
            raise

    @staticmethod
    def _translation_hash(
            id: str,
            id_type: Literal['shikimori', 'kinopoisk'],
            seria_num: int,
            translation_id: str,
            quality: str,
    ) -> str:
        return md5(str(id+id_type+translation_id+str(seria_num)+quality).encode('utf-8')).hexdigest()

    def fast_download(
            self,
            id: str,
            id_type: Literal['shikimori', 'kinopoisk'],
            seria_num: int,
            translation_id: str,
            quality: str,
            output_dir: str | Path | None = None,
            output_name: str = "output",
            fps: float | int | None = None,
            with_audio: bool = True,
    ) -> Path | None:
        """
        Быстрая загрузка видео с Kodik. Загрузка выполняется сегментами параллельно с последующим склеиванием для
        увеличения скорости загрузки.
            id (str): Id сериала на Шикимори/Кинопоиске
            id_type (str): тип id 'shikimori' или 'kinopoisk'
            seria_num (int): номер серии
            translation_id (str): id переода/субтитров (Прим: 640 - Anilibria.TV)
            quality (str): Желаемое качество видео. Допустимы варианты: "480", "720", "1080"
            output_dir (str | Path | None): Директория для сохранения видео (None - во временной директории)
            output_name (str): Имя сохраняемого видео (без расширения)
            fps (float | int | None): FPS выходного файла (None - автоматически)
            with_audio (bool): Следует ли экспортировать вместе с аудио

        Returns:
            save_path (Path | None): Путь до сохраненного видео. Если не удалось найти трансляции - None
        """
        check_ffmpeg() # Проверка на досутпность ffmpeg из модуля subprocess
        hsh = self._translation_hash(
            id=id,
            id_type=id_type,
            seria_num=seria_num,
            translation_id=translation_id,
            quality=quality
        )
        # Путь для временного сохранения
        tmp_dir = Path(self.tmp_root, f"{hsh}~")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        # Путь до выходного файла
        output_dir = Path(output_dir) if output_dir is not None else tmp_dir
        output_path = Path(output_dir, f"{output_name}.mp4")
        # Если файл уже есть - пропустим
        if output_path.exists():
            return output_path

        link = self._get_download_link(id, id_type, seria_num, translation_id)
        manifest = self._get_url_data(f'https:{link}{quality}.mp4:hls:manifest.m3u8')
        segments = self._get_segments(manifest, f'https:{link}')
        thr = len(segments)
        # Если не найдено сегментов
        if not thr:
            return None
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tasks = {}
            for i in range(thr):
                segment_path = Path(tmp_dir, f'{segments[i][1]}.ts')
                # Если сегмент скачен - пропустим
                if os.path.exists(segment_path):
                    continue
                # Скачаем сегмент во временный файл
                tmp_segment_path = segment_path.with_stem(f'{segment_path.stem}~')
                tmp_segment_path.unlink(missing_ok=True)
                future = executor.submit(
                    self._download_segment,
                    segments[i][0],
                    tmp_segment_path,
                    timeout=self.segment_timeout
                )
                tasks[future] = (tmp_segment_path, segment_path)
            # Пройдёмся по всем запущенным задачам
            for future in concurrent.futures.as_completed(tasks.keys(), timeout=2*len(segments)):
                # Проверим результат на ошибки
                future.result()
                # Переименуем сегмент
                tmp_segment_path, segment_path = tasks[future]
                tmp_segment_path.rename(segment_path)
        # Соединим сегменты
        tmp_output_path = Path(tmp_dir, f"{output_name}~.mp4")
        tmp_output_path.unlink(missing_ok=True)
        try:
            self._combine_segments(
                tmp_dir,
                output_path=tmp_output_path,
                fps=fps,
                with_audio=with_audio,
            )
        except Exception:
            tmp_output_path.unlink(missing_ok=True)
            raise
        # Если успешно - переименуем в нужный файл
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path = tmp_output_path.rename(output_path)

        return output_path

    def clear_title_cache(
            self,
            id: str,
            id_type: Literal['shikimori', 'kinopoisk'],
            seria_num: int,
            translation_id: str,
            quality: str,
    ):
        # Получим хеш
        hsh = self._translation_hash(
            id=id,
            id_type=id_type,
            seria_num=seria_num,
            translation_id=translation_id,
            quality=quality
        )
        # Удалим папку аниме вместе с данными
        tmp_dir = Path(self.tmp_root, f"{hsh}~")
        shutil.rmtree(tmp_dir, ignore_errors=True)
