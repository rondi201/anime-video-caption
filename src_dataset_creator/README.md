# Модуль сбора данных об аниме

## О модуле

Модуль предназначен для сбора информации о всех выпущенных аниме, размещаемых в открытом доступе.

Для сбора информации используются следующие источники:
- [Shikimori API](https://shikimori.one/api/doc/graphql) (вся информация об аниме)
- [MyAnimeList API](https://myanimelist.net/apiconfig/references/api/v2#operation/anime_ranking_get) (описание на английсокм)
- API плеера Kodik (поиск и загрузка видеозаписей)

## Собираемые данные

В рамках модуля производится сбор следующей информации об каждом выпущенном произведении:
- Название (оригинальный и английский)
- Описание (английский)
- Видеозапись первой серии (без аудио с частотой 10 кадров в минуту продолжительностью ~24 минуты)
- Статистика (популярность, пользовательский рейтинг)
- Список главных персонажей
- Список жанров

Описание написаны людьми и в большинстве случаев представляют описание первой серии.

Собираемые данные дополнительно фильтруются по следующим признаком:
- Возрастной рейтинг (0-13 лет)
- Первый сезон (если у произведение несколько сезонов - описание зачастую дублируется)

## Формат данных

```json
{    
  "created_at": "2025-07-28 12:43:30",
  "language": "en",
  "animes": [
    {
        "id": "31964",  # ID на Shikimori
        "mal_id": "31964",  # ID на MyAnimeList
        "name": "Boku no Hero Academia",  # Исходное имя
        "title": "My Hero Academia",  # Имя на `language` языке
        "rating": "pg_13",  # Возрастной рейтинг
        "score": 7.84,  # Пользовательский рейтинг
        "released": "2016-06-26 00:00:00",  # Дата выхода
        "genres": [  # Жанры
            "Shounen",
            "Action",
            "School",
            "Super Power"
        ],
        "main_characters": [  # Главные герои
            "All Might",
            "Katsuki Bakugou",
            "Tenya Iida",
            "Izuku Midoriya",
            "Ochako Uraraka"
        ],
        "popularity": 90940,  # Количество оценок,
        # Описание на `language` языке
        "description": "The appearance of \"quirks,\" newly discovered super powers, has been steadily increasing over the years, with 80 percent of humanity possessing various abilities from manipulation of elements to shapeshifting. This leaves the remainder of the world completely powerless, and Izuku Midoriya is one such individual.\n\nSince he was a child, the ambitious middle schooler has wanted nothing more than to be a hero. Izuku's unfair fate leaves him admiring heroes and taking notes on them whenever he can. But it seems that his persistence has borne some fruit: Izuku meets the number one hero and his personal idol, All Might. All Might's quirk is a unique ability that can be inherited, and he has chosen Izuku to be his successor!\n\nEnduring many months of grueling training, Izuku enrolls in UA High, a prestigious high school famous for its excellent hero training program, and this year's freshmen look especially promising. With his bizarre but talented classmates and the looming threat of a villainous organization, Izuku will soon learn what it really means to be a hero.",
        # Путь до сохраненного видео относительно корня набора данных  
        "video_path": "videos/31964/Boku no Hero Academia_S1_E1_720.mp4"
    }, 
    ...
  ]
}
```
## Загрузка

Собранный набор данных из 614 произведений можно загрузить [здесь](https://drive.google.com/file/d/1ujlUoBU4QYXx06d_Yp_zEnpx_VaxlTFp/view?usp=sharing).

## Предназнаение

Данный набор данных в первую очередь нацелен генерацию описание первой серии аниме по видео (в рамках длинного контекста). 
Дополнительно набор данных может быть использован для:
- Классификация (жанр, оценка) аниме по видео/описанию.

## Запуск сборки данных

Для самостоятельного запуска данных необходимо выполнить следующие шаги.
#### 1. Установить зависимости
```shell
pip install -r requirements.txt
```
#### 2. Получить токен приложения для API MyAnimeList

Для получения токена необходимо зарегестрироваться на сайте и создать собственное приложение [здесь](https://myanimelist.net/apiconfig).

После регистрации приложения будет выдан client id, который будет необходим в дальнейшем.

#### 3. Настроить конфигурацию запуска

Для запуска скрипта необходимо будет указать свой `client_id` в переменную среды `MYANIMELIST_CLIENT_ID` или в [файле конфигурации](data/config/anime_data_parsing.yaml).
См. описание параметров в файле конфигурации для изменения параметров запуска.

#### 4. Запустить скрипт

Запуск скрипта осуществляется следующей командой.

```shell
python -m tools.anime_data_parsing
```

Во время работы все ошибки получения данных и истечение времени ожидания от сервера обёрнуты в warning и не прерывают работу скрипта. 
Если в процессе работы возникли неполадки - запустите скрипт заново для продолжения сбора информации (данные будут дозаписываться в уже созданные).
