import os
import random
import threading
import time
import json
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENV
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

DANBOORU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU"
)

REACTOR_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_REACTOR_GAMES"
)

PEXELS_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PEXELS"
)

DANBOORU_USERNAME = os.environ.get(
    "DANBOORU_USERNAME"
)

DANBOORU_API_KEY = os.environ.get(
    "DANBOORU_API_KEY"
)

PEXELS_API_KEY = os.environ.get(
    "PEXELS_API_KEY"
)


# =========================================================
# URL
# =========================================================

DANBOORU_API = "https://danbooru.donmai.us"

PEXELS_API = "https://api.pexels.com/v1"

REACTOR_BASE_URL = "https://reactor.cc/tag/"


# =========================================================
# REACTOR SETTINGS
# =========================================================

# Максимальная страница, которую бот будет пробовать.
# Если страница не существует, бот попробует другую.
REACTOR_MAX_PAGE = 100


# Сколько картинок хранить в памяти.
# На Render память файла может сбрасываться после
# перезапуска сервиса.
MAX_REACTOR_MEMORY = 1000


REACTOR_MEMORY_FILE = "reactor_seen.json"


# =========================================================
# REACTOR TAGS
# English + Russian
# =========================================================

REACTOR_GAME_TAGS = [

    # -----------------------------------------------------
    # Warhammer
    # -----------------------------------------------------

    "Warhammer 40000",
    "Warhammer 40k",
    "Вархаммер 40000",
    "Вархаммер",

    # -----------------------------------------------------
    # Genshin
    # -----------------------------------------------------

    "Genshin Impact",
    "Геншин Импакт",

    # -----------------------------------------------------
    # Nier
    # -----------------------------------------------------

    "Nier Automata",
    "NieR Automata",
    "Nier",
    "Ниер Автомата",

    # -----------------------------------------------------
    # Street Fighter
    # -----------------------------------------------------

    "Street Fighter",
    "Стрит Файтер",

    # -----------------------------------------------------
    # Furry
    # -----------------------------------------------------

    "Furry",
    "Фурри",

    # -----------------------------------------------------
    # VTubers
    # -----------------------------------------------------

    "VTuber",
    "VTubers",
    "Витубер",
    "Витуберы",

    # -----------------------------------------------------
    # Dota
    # -----------------------------------------------------

    "Dota 2",
    "Dota",
    "Дота 2",
    "Дота",

    # -----------------------------------------------------
    # Apex
    # -----------------------------------------------------

    "Apex Legends",
    "Apex",
    "Апекс Легендс",

    # -----------------------------------------------------
    # Team Fortress
    # -----------------------------------------------------

    "Team Fortress 2",
    "Team Fortress",
    "Тим Фортресс 2",

    # -----------------------------------------------------
    # Mortal Kombat
    # -----------------------------------------------------

    "Mortal Kombat",
    "Mortal Kombat 1",
    "Mortal Kombat X",
    "Mortal Kombat 11",
    "Mortal Kombat 12",
    "Мортал Комбат",

    # -----------------------------------------------------
    # Resident Evil
    # -----------------------------------------------------

    "Resident Evil",
    "Resident Evil 2",
    "Resident Evil 3",
    "Resident Evil 4",
    "Resident Evil 5",
    "Resident Evil 6",
    "Resident Evil 7",
    "Resident Evil Village",
    "Резидент Ивел",

    # -----------------------------------------------------
    # Game Art
    # -----------------------------------------------------

    "Game Art",
    "Gaming Art",
    "Video Game Art",
    "Игровой арт",
    "Игровой арт",

    # -----------------------------------------------------
    # Zenless Zone Zero
    # -----------------------------------------------------

    "Zenless Zone Zero",
    "ZZZ",
    "Zenless",
    "Зенлесс Зон Зеро",

    # -----------------------------------------------------
    # Metal Gear
    # -----------------------------------------------------

    "Metal Gear Solid",
    "Metal Gear Rising",
    "Metal Gear",
    "Метал Гир Солид",
    "Метал Гир Райзинг",

    # -----------------------------------------------------
    # Everlasting Summer
    # -----------------------------------------------------

    "Everlasting Summer",
    "Бесконечное лето",

    # -----------------------------------------------------
    # Doki Doki
    # -----------------------------------------------------

    "Doki Doki Literature Club",
    "Doki Doki",
    "DDLC",
    "Доки Доки Литературный Клуб",

    # -----------------------------------------------------
    # Minecraft
    # -----------------------------------------------------

    "Minecraft",
    "Майнкрафт",

    # -----------------------------------------------------
    # Skullgirls
    # -----------------------------------------------------

    "Skullgirls",
    "Skull Girls",
    "Скаллгерлс",

    # -----------------------------------------------------
    # Vermintide
    # -----------------------------------------------------

    "Warhammer Vermintide",
    "Vermintide",
    "Warhammer Vermintide 2",
    "Вархаммер Вермінтайд",
    "Вермінтайд",

    # -----------------------------------------------------
    # DOOM
    # -----------------------------------------------------

    "DOOM",
    "Doom",
    "Дум",

    # -----------------------------------------------------
    # Project Zomboid
    # -----------------------------------------------------

    "Project Zomboid",
    "Зомбоид",
    "Проект Зомбоид",

    # -----------------------------------------------------
    # Portal
    # -----------------------------------------------------

    "Portal",
    "Portal 2",
    "Портал",

    # -----------------------------------------------------
    # Mass Effect
    # -----------------------------------------------------

    "Mass Effect",
    "Mass Effect 2",
    "Mass Effect 3",
    "Масс Эффект",

    # -----------------------------------------------------
    # World of Warcraft
    # -----------------------------------------------------

    "World of Warcraft",
    "WoW",
    "Warcraft",
    "Варкрафт",
    "Ворлд оф Варкрафт",

    # -----------------------------------------------------
    # Deadlock
    # -----------------------------------------------------

    "Deadlock",
    "Дедлок",

    # -----------------------------------------------------
    # Helldivers
    # -----------------------------------------------------

    "Helldivers",
    "Helldivers 2",
    "Хеллдайверс",

    # -----------------------------------------------------
    # Wuthering Waves
    # -----------------------------------------------------

    "Wuthering Waves",
    "Wuwa",
    "Ватеринг Вейвс",

    # -----------------------------------------------------
    # Arknights
    # -----------------------------------------------------

    "Arknights",
    "Arknight",
    "Аркнайтс",

    # -----------------------------------------------------
    # Arknights Endfield
    # -----------------------------------------------------

    "Arknights Endfield",
    "Endfield",
    "Аркнайтс Эндфилд",

    # -----------------------------------------------------
    # Batman
    # -----------------------------------------------------

    "Batman",
    "Batman Arkham",
    "Бэтмен",

    # -----------------------------------------------------
    # Darksiders
    # -----------------------------------------------------

    "Darksiders",
    "Darksiders II",
    "Darksiders III",
    "Darksiders Genesis",
    "Дарксайдерс",

    # -----------------------------------------------------
    # Devil May Cry
    # -----------------------------------------------------

    "Devil May Cry",
    "DMC",
    "Devil May Cry 5",
    "Девил Май Край",

    # -----------------------------------------------------
    # Fallout
    # -----------------------------------------------------

    "Fallout",
    "Fallout 3",
    "Fallout 4",
    "Fallout New Vegas",
    "Фоллаут",

    # -----------------------------------------------------
    # FNAF
    # -----------------------------------------------------

    "Five Nights at Freddy's",
    "FNAF",
    "Five Nights at Freddys",
    "Фнаф",

    # -----------------------------------------------------
    # Halo
    # -----------------------------------------------------

    "Halo",
    "Halo Infinite",
    "Halo 4",
    "Halo 5",
    "Хало",

    # -----------------------------------------------------
    # Overwatch
    # -----------------------------------------------------

    "Overwatch",
    "Overwatch 2",
    "Овервотч",

    # -----------------------------------------------------
    # Fortnite
    # -----------------------------------------------------

    "Fortnite",
    "Фортнайт",

    # -----------------------------------------------------
    # Far Cry
    # -----------------------------------------------------

    "Far Cry",
    "Far Cry 3",
    "Far Cry 4",
    "Far Cry 5",
    "Far Cry 6",
    "Фар Край",

    # -----------------------------------------------------
    # PUBG
    # -----------------------------------------------------

    "PUBG",
    "PlayerUnknown's Battlegrounds",
    "Пабг",

    # -----------------------------------------------------
    # Helltaker
    # -----------------------------------------------------

    "Helltaker",
    "Хеллтейкер",

    # -----------------------------------------------------
    # Awaria
    # -----------------------------------------------------

    "Awaria",

]


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; AnimePoster/1.0)"
    )
}


DANBOORU_HEADERS = {
    "User-Agent": (
        "AnimePoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


REACTOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; ReactorPoster/1.0)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en;q=0.8"
    ),
    "Cache-Control": "no-cache",
}


# =========================================================
# REACTOR MEMORY
# =========================================================

REACTOR_LOCK = threading.Lock()


def load_reactor_memory():

    try:

        if not os.path.exists(
            REACTOR_MEMORY_FILE
        ):

            return set()

        with open(
            REACTOR_MEMORY_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if not isinstance(
            data,
            list,
        ):

            return set()

        return set(data)

    except Exception as error:

        print(
            "[Reactor Memory] "
            f"Ошибка чтения: {error}"
        )

        return set()


REACTOR_USED = load_reactor_memory()


def save_reactor_memory():

    try:

        with open(
            REACTOR_MEMORY_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                list(REACTOR_USED)[
                    -MAX_REACTOR_MEMORY:
                ],
                file,
                ensure_ascii=False,
                indent=2,
            )

    except Exception as error:

        print(
            "[Reactor Memory] "
            f"Ошибка сохранения: {error}"
        )


def reactor_was_used(url):

    with REACTOR_LOCK:

        return (
            url in REACTOR_USED
        )


def reactor_mark_used(url):

    with REACTOR_LOCK:

        REACTOR_USED.add(url)

        while len(
            REACTOR_USED
        ) > MAX_REACTOR_MEMORY:

            REACTOR_USED.pop()

        save_reactor_memory()


# =========================================================
# DANBOORU RATE LIMITER
# =========================================================

DANBOORU_LOCK = threading.Lock()

LAST_DANBOORU_REQUEST = 0.0


def danbooru_wait():

    global LAST_DANBOORU_REQUEST

    with DANBOORU_LOCK:

        now = time.monotonic()

        elapsed = (
            now - LAST_DANBOORU_REQUEST
        )

        wait_time = (
            1.2 - elapsed
        )

        if wait_time > 0:

            print(
                "[Danbooru] "
                f"Ожидание "
                f"{wait_time:.1f} сек."
            )

            time.sleep(
                wait_time
            )

        LAST_DANBOORU_REQUEST = (
            time.monotonic()
        )


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu():

    print(
        "[Waifu.im] "
        "Получаем изображение..."
    )

    params = {
        "IsNsfw": "True",
        "OrderBy": "Random",
        "PageSize": 1,
    }

    response = requests.get(
        "https://api.waifu.im/images",
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    items = data.get(
        "items",
        [],
    )

    if not items:

        raise RuntimeError(
            "Waifu.im "
            "не вернул изображение"
        )

    image_url = items[0].get(
        "url"
    )

    if not image_url:

        raise RuntimeError(
            "Waifu.im "
            "не вернул URL"
        )

    return {
        "url": image_url,
        "source": "Waifu.im",
    }


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(
    tags,
    source_name,
):

    if not DANBOORU_USERNAME:

        raise RuntimeError(
            "DANBOORU_USERNAME "
            "не настроен"
        )

    if not DANBOORU_API_KEY:

        raise RuntimeError(
            "DANBOORU_API_KEY "
            "не настроен"
        )

    print(
        f"[{source_name}] "
        f"Запрос: {tags}"
    )

    danbooru_wait()

    response = requests.get(
        f"{DANBOORU_API}/posts.json",
        params={
            "limit": 20,
            "tags": tags,
        },
        auth=(
            DANBOORU_USERNAME,
            DANBOORU_API_KEY,
        ),
        headers=DANBOORU_HEADERS,
        timeout=30,
    )

    print(
        f"[{source_name}] "
        f"Danbooru HTTP: "
        f"{response.status_code}"
    )

    if response.status_code == 429:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 429"
        )

    if response.status_code in (
        401,
        403,
    ):

        raise RuntimeError(
            f"{source_name}: "
            f"Danbooru HTTP "
            f"{response.status_code}"
        )

    if response.status_code == 422:

        body = response.text[:1000]

        print(
            f"[{source_name}] "
            f"Danbooru 422: "
            f"{body}"
        )

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 422"
        )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            f"{source_name}: "
            "неожиданный ответ "
            "Danbooru"
        )

    images = []

    for post in data:

        image_url = (
            post.get(
                "large_file_url"
            )
            or post.get(
                "file_url"
            )
        )

        if not image_url:
            continue

        images.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post.get(
                    "id"
                ),
            }
        )

    if not images:

        raise RuntimeError(
            f"{source_name}: "
            "изображения "
            "не найдены"
        )

    return random.choice(
        images
    )


def get_danbooru_anime():

    return get_random_danbooru(
        "rating:s 1girl",
        "Danbooru Anime",
    )


# =========================================================
# REACTOR URL
# =========================================================

def reactor_page_url(
    tag,
    page=1,
):

    encoded_tag = quote(
        tag,
        safe="",
    )

    if page <= 1:

        return (
            f"{REACTOR_BASE_URL}"
            f"{encoded_tag}"
        )

    return (
        f"{REACTOR_BASE_URL}"
        f"{encoded_tag}/new/{page}"
    )


# =========================================================
# REACTOR IMAGE EXTRACTION
# =========================================================

def extract_reactor_images(
    html,
    page_url,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    for img in soup.find_all(
        "img"
    ):

        possible_urls = [

            img.get(
                "data-src"
            ),

            img.get(
                "data-original"
            ),

            img.get(
                "data-lazy-src"
            ),

            img.get(
                "src"
            ),

        ]

        for src in possible_urls:

            if not src:
                continue

            src = src.strip()

            if not src:
                continue

            src = urljoin(
                page_url,
                src,
            )

            lowered = src.lower()

            # Только картинки постов.
            if "/pics/post/" not in lowered:
                continue

            # Исключаем служебные изображения.
            if any(
                value in lowered
                for value in (
                    "/avatar/",
                    "/static/",
                    "/emoji/",
                    "/icon/",
                    "/logo/",
                    "favicon",
                )
            ):

                continue

            candidates.append(
                src
            )

    # Убираем дубликаты.
    candidates = list(
        dict.fromkeys(
            candidates
        )
    )

    return candidates


# =========================================================
# REACTOR IMAGE CHECK
# =========================================================

def check_reactor_image(
    image_url
):

    try:

        response = requests.get(
            image_url,
            headers={
                "User-Agent":
                    REACTOR_HEADERS[
                        "User-Agent"
                    ],
                "Accept":
                    "image/avif,image/webp,"
                    "image/apng,image/*,*/*;q=0.8",
            },
            timeout=20,
            stream=True,
        )

        status = (
            response.status_code
        )

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            ).lower()
        )

        response.close()

        if status != 200:
            return False

        if (
            content_type.startswith(
                "image/"
            )
        ):

            return True

        return any(
            extension in image_url.lower()
            for extension in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        )

    except requests.RequestException:

        return False


# =========================================================
# REACTOR
# =========================================================

def get_reactor_games():

    print(
        "[Reactor Games] "
        "Выбираем случайный тег..."
    )

    tags = (
        REACTOR_GAME_TAGS.copy()
    )

    random.shuffle(
        tags
    )

    # Пробуем несколько разных тегов.
    for tag in tags:

        # Не всегда большая страница существует.
        # Поэтому случайно выбираем страницу.
        page = random.randint(
            1,
            REACTOR_MAX_PAGE,
        )

        page_url = reactor_page_url(
            tag,
            page,
        )

        print(
            "[Reactor Games] "
            f"Тег: {tag}"
        )

        print(
            "[Reactor Games] "
            f"Страница: {page_url}"
        )

        try:

            response = requests.get(
                page_url,
                headers=REACTOR_HEADERS,
                timeout=30,
            )

            print(
                "[Reactor Games] "
                f"HTTP: "
                f"{response.status_code}"
            )

            if response.status_code != 200:
                continue

            candidates = (
                extract_reactor_images(
                    response.text,
                    page_url,
                )
            )

            print(
                "[Reactor Games] "
                f"Кандидатов: "
                f"{len(candidates)}"
            )

            if not candidates:
                continue

            # Сначала только новые картинки.
            unused = [
                url
                for url in candidates
                if not reactor_was_used(
                    url
                )
            ]

            if not unused:

                print(
                    "[Reactor Games] "
                    "Все картинки этой "
                    "страницы уже использованы"
                )

                continue

            random.shuffle(
                unused
            )

            # Проверяем до 20 кандидатов.
            for image_url in unused[:20]:

                if not check_reactor_image(
                    image_url
                ):

                    continue

                reactor_mark_used(
                    image_url
                )

                print(
                    "[Reactor Games] "
                    "Выбрано новое "
                    "изображение"
                )

                return {
                    "url": image_url,
                    "source": (
                        "Reactor Games"
                    ),
                    "tag": tag,
                }

        except requests.RequestException as error:

            print(
                "[Reactor Games] "
                f"Ошибка запроса: "
                f"{error}"
            )

        except Exception as error:

            print(
                "[Reactor Games] "
                f"Ошибка: "
                f"{error}"
            )

    raise RuntimeError(
        "Reactor: "
        "не удалось найти "
        "новое изображение"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY "
            "не настроен"
        )

    print(
        "[Pexels] "
        "Получаем изображение..."
    )

    queries = [
        "gaming",
        "video game",
        "game character",
        "fantasy game art",
        "cosplay",
        "gaming character",
        "digital game art",
    ]

    random.shuffle(
        queries
    )

    headers = {
        "Authorization":
            PEXELS_API_KEY,

        "User-Agent":
            "AnimePoster/1.0",
    }

    for query in queries:

        response = requests.get(
            f"{PEXELS_API}/search",
            headers=headers,
            params={
                "query": query,
                "per_page": 80,
                "page": 1,
            },
            timeout=30,
        )

        if response.status_code == 429:

            raise RuntimeError(
                "Pexels HTTP 429"
            )

        response.raise_for_status()

        data = response.json()

        photos = data.get(
            "photos",
            [],
        )

        if not photos:
            continue

        random.shuffle(
            photos
        )

        for photo in photos:

            src = photo.get(
                "src",
                {},
            )

            image_url = (
                src.get(
                    "large2x"
                )
                or src.get(
                    "large"
                )
                or src.get(
                    "original"
                )
            )

            if image_url:

                return {
                    "url": image_url,
                    "source": "Pexels",
                }

    raise RuntimeError(
        "Pexels не вернул "
        "изображения"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    content = response.content

    if len(content) > (
        8 * 1024 * 1024
    ):

        raise RuntimeError(
            "Изображение "
            "больше 8 MB"
        )

    content_type = (
        response.headers.get(
            "Content-Type",
            "image/jpeg",
        )
    )

    if "png" in content_type:

        extension = "png"

    elif "webp" in content_type:

        extension = "webp"

    elif "gif" in content_type:

        extension = "gif"

    else:

        extension = "jpg"

    return (
        f"image.{extension}",
        content,
        content_type,
    )


# =========================================================
# DISCORD
# =========================================================

def send_to_discord(
    image
):

    source = image[
        "source"
    ]

    image_url = image[
        "url"
    ]

    webhook_map = {

        "Waifu.im": (
            WAIFU_WEBHOOK_URL,
            "🌸 Anime",
        ),

        "Danbooru Anime": (
            DANBOORU_WEBHOOK_URL,
            "🎨 Anime Art",
        ),

        "Reactor Games": (
            REACTOR_GAMES_WEBHOOK_URL,
            "🎮 Game Art",
        ),

        "Pexels": (
            PEXELS_WEBHOOK_URL,
            "📷 Fashion / Glamour",
        ),

    }

    if source not in webhook_map:

        raise RuntimeError(
            f"Неизвестный источник: "
            f"{source}"
        )

    webhook_url, message = (
        webhook_map[source]
    )

    if not webhook_url:

        raise RuntimeError(
            f"Webhook для "
            f"{source} "
            "не настроен"
        )

    (
        filename,
        image_data,
        content_type,
    ) = download_image(
        image_url
    )

    response = requests.post(
        webhook_url,
        data={
            "content": (
                f"{message}\n"
                f"Источник: {source}"
            )
        },
        files={
            "file": (
                filename,
                image_data,
                content_type,
            )
        },
        timeout=45,
    )

    response.raise_for_status()


# =========================================================
# PUBLISH
# =========================================================

def publish_source(
    name,
    getter,
):

    try:

        image = getter()

        send_to_discord(
            image
        )

        print(
            f"[{name}] "
            "Успешно опубликовано"
        )

        return {
            "source": name,
            "success": True,
            "error": None,
        }

    except Exception as error:

        print(
            f"[{name}] "
            f"ОШИБКА: {error}"
        )

        return {
            "source": name,
            "success": False,
            "error": str(error),
        }


# =========================================================
# POST
# =========================================================

@app.route("/post")
def post_image():

    print(
        "======================================================="
    )

    print(
        "POST: запуск независимой публикации"
    )

    print(
        "======================================================="
    )

    sources = []

    # -----------------------------------------------------
    # Waifu
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:

        sources.append(
            (
                "Waifu.im",
                get_random_waifu,
            )
        )

    # -----------------------------------------------------
    # Danbooru
    # -----------------------------------------------------

    if (
        DANBOORU_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        sources.append(
            (
                "Danbooru Anime",
                get_danbooru_anime,
            )
        )

    # -----------------------------------------------------
    # Reactor
    # -----------------------------------------------------

    if REACTOR_GAMES_WEBHOOK_URL:

        sources.append(
            (
                "Reactor Games",
                get_reactor_games,
            )
        )

    # -----------------------------------------------------
    # Pexels
    # -----------------------------------------------------

    if (
        PEXELS_WEBHOOK_URL
        and PEXELS_API_KEY
    ):

        sources.append(
            (
                "Pexels",
                get_random_pexels,
            )
        )

    if not sources:

        return Response(
            "No sources configured",
            status=500,
        )

    results = []

    # Источники запускаются независимо.
    for name, getter in sources:

        results.append(
            publish_source(
                name,
                getter,
            )
        )

    successful = sum(
        1
        for result in results
        if result["success"]
    )

    errors = (
        len(results)
        - successful
    )

    print(
        "======================================================="
    )

    print(
        "POST: публикация завершена"
    )

    print(
        f"POST: успешно: "
        f"{successful}"
    )

    print(
        f"POST: ошибок: "
        f"{errors}"
    )

    for result in results:

        if not result["success"]:

            print(
                f"POST: "
                f"{result['source']}: "
                f"{result['error']}"
            )

    print(
        "======================================================="
    )

    return Response(
        f"OK - successful: "
        f"{successful}, errors: "
        f"{errors}",
        status=200,
    )


# =========================================================
# STATUS
# =========================================================

@app.route("/status")
def status():

    return {
        "status": "online",

        "sources": {

            "waifu": bool(
                WAIFU_WEBHOOK_URL
            ),

            "danbooru_anime": bool(
                DANBOORU_WEBHOOK_URL
                and DANBOORU_USERNAME
                and DANBOORU_API_KEY
            ),

            "reactor_games": bool(
                REACTOR_GAMES_WEBHOOK_URL
            ),

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
            ),

        },

        "reactor_tags": len(
            REACTOR_GAME_TAGS
        ),

        "reactor_memory": len(
            REACTOR_USED
        ),
    }


# =========================================================
# PING
# =========================================================

@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "8080",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
```
