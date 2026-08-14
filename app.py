import os
import random
import threading
import time
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENV
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU")
DANBOORU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_DANBOORU")
REACTOR_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_REACTOR_GAMES"
)
PEXELS_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_PEXELS")

DANBOORU_USERNAME = os.environ.get("DANBOORU_USERNAME")
DANBOORU_API_KEY = os.environ.get("DANBOORU_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")


# =========================================================
# URL
# =========================================================

DANBOORU_API = "https://danbooru.donmai.us"
PEXELS_API = "https://api.pexels.com/v1"
REACTOR_BASE_URL = "https://reactor.cc"


# =========================================================
# GAME TAGS
# =========================================================

GAME_TAGS = [
    # Warhammer
    "Warhammer 40,000",
    "Warhammer 40000",
    "Вархаммер 40000",
    "Warhammer",
    "Вархаммер",
    "Warhammer Vermintide",
    "Vermintide",

    # Genshin / Hoyoverse
    "Genshin Impact",
    "Геншин Импакт",
    "Zenless Zone Zero",
    "ZZZ",
    "Wuthering Waves",
    "Arknights",
    "Arknights Endfield",

    # Fighting games
    "Street Fighter",
    "Стрит Файтер",
    "Mortal Kombat",
    "Мортал Комбат",
    "Skullgirls",
    "Скуллгерлс",

    # Anime / JRPG
    "NieR Automata",
    "Nier Automata",
    "Ниер Автомата",
    "Metal Gear Solid",
    "Метал Гир Солид",
    "Metal Gear Rising",
    "Метал Гир Райзинг",
    "Everlasting Summer",
    "Бесконечное лето",
    "Doki Doki Literature Club",
    "Доки Доки Литературный Клуб",

    # Multiplayer
    "Dota 2",
    "Дота 2",
    "Apex Legends",
    "Апекс Легендс",
    "Team Fortress 2",
    "Тим Фортресс",
    "Deadlock",
    "Overwatch",
    "Овервотч",
    "Fortnite",
    "Фортнайт",
    "PUBG",
    "Helldivers",

    # Horror
    "Resident Evil",
    "Резидент Ивил",
    "Silent Hill",
    "Fallout",
    "Фоллаут",
    "FNAF",
    "Five Nights at Freddy's",

    # Other
    "Furry",
    "Фурри",
    "VTuber",
    "Витуберы",
    "Gaming Art",
    "Игровой арт",
    "Minecraft",
    "Майнкрафт",
    "Doom",
    "Дум",
    "Project Zomboid",
    "Portal",
    "Портал",
    "Mass Effect",
    "Масс Эффект",
    "World of Warcraft",
    "Deadlock",
    "Batman",
    "Бэтмен",
    "Darksiders",
    "Devil May Cry",
    "Девил Мей Край",
    "Halo",
    "Хало",
    "Far Cry",
    "Фар Край",
    "Helltaker",
    "Хеллтейкер",
    "Awaria",
]


# =========================================================
# MATURE / SUGGESTIVE TAGS
# =========================================================

MATURE_GAME_TAGS = [
    "mature",
    "adult",
    "suggestive",
    "ecchi",
    "lewd",
    "lingerie",
    "swimsuit",
    "bikini",
    "pinup",
    "glamour",
    "sensual",
    "risque",
    "revealing",
    "thigh_highs",
    "stockings",
    "bodysuit",
    "latex",
    "cosplay",
    "fanservice",
    "mature_fanart",
    "suggestive_fanart",
]


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; GameArtPoster/1.0)"
    )
}

DANBOORU_HEADERS = {
    "User-Agent": (
        "GameArtPoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}

REACTOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; GameArtPoster/1.0)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


# =========================================================
# REACTOR MEMORY
# =========================================================

REACTOR_USED = set()
REACTOR_LOCK = threading.Lock()

MAX_REACTOR_MEMORY = 1000


def reactor_was_used(key):

    with REACTOR_LOCK:
        return key in REACTOR_USED


def reactor_mark_used(key):

    with REACTOR_LOCK:

        REACTOR_USED.add(key)

        if len(REACTOR_USED) > MAX_REACTOR_MEMORY:

            old_key = random.choice(
                list(REACTOR_USED)
            )

            REACTOR_USED.discard(old_key)


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

        wait_time = 1.2 - elapsed

        if wait_time > 0:

            print(
                "[Danbooru] "
                f"Ожидание {wait_time:.1f} сек."
            )

            time.sleep(wait_time)

        LAST_DANBOORU_REQUEST = time.monotonic()


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu():

    print(
        "[Waifu.im] Получаем изображение..."
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

    items = data.get("items", [])

    if not items:

        raise RuntimeError(
            "Waifu.im не вернул изображение"
        )

    image_url = items[0].get("url")

    if not image_url:

        raise RuntimeError(
            "Waifu.im не вернул URL"
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
            "DANBOORU_USERNAME не настроен"
        )

    if not DANBOORU_API_KEY:

        raise RuntimeError(
            "DANBOORU_API_KEY не настроен"
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
            f"{source_name}: Danbooru HTTP 429"
        )

    if response.status_code in (401, 403):

        raise RuntimeError(
            f"{source_name}: "
            f"Danbooru HTTP "
            f"{response.status_code}"
        )

    if response.status_code == 422:

        body = response.text[:1500]

        print(
            f"[{source_name}] "
            f"Danbooru 422: {body}"
        )

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 422"
        )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):

        raise RuntimeError(
            f"{source_name}: "
            "неожиданный ответ Danbooru"
        )

    images = []

    for post in data:

        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        images.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post.get("id"),
            }
        )

    if not images:

        raise RuntimeError(
            f"{source_name}: "
            "изображения не найдены"
        )

    return random.choice(images)


def get_danbooru_anime():

    return get_random_danbooru(
        "rating:s 1girl",
        "Danbooru Anime",
    )


# =========================================================
# REACTOR HELPERS
# =========================================================

def normalize_reactor_url(url):

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    return urljoin(
        REACTOR_BASE_URL,
        url,
    )


def extract_reactor_post_links(
    soup,
):

    links = []

    for a in soup.find_all("a"):

        href = a.get("href")

        if not href:
            continue

        href = normalize_reactor_url(href)

        if not href:
            continue

        if "/post/" not in href.lower():
            continue

        if href not in links:
            links.append(href)

    return links


def extract_images_from_post(
    soup,
):

    images = []

    for img in soup.find_all("img"):

        possible_urls = [
            img.get("data-src"),
            img.get("data-original"),
            img.get("data-lazy-src"),
            img.get("src"),
        ]

        for src in possible_urls:

            if not src:
                continue

            src = normalize_reactor_url(src)

            if not src:
                continue

            lowered = src.lower()

            if any(
                x in lowered
                for x in (
                    "/avatar/",
                    "/static/",
                    "/emoji/",
                    "/icon/",
                    "/logo/",
                    "favicon",
                )
            ):

                continue

            if not any(
                ext in lowered
                for ext in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".gif",
                )
            ):

                continue

            if src not in images:
                images.append(src)

    return images


def reactor_check_image(
    image_url,
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

        status = response.status_code

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            .lower()
        )

        response.close()

        if status != 200:
            return False

        if content_type.startswith("image/"):
            return True

        return any(
            ext in image_url.lower()
            for ext in (
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
# REACTOR SEARCH
# =========================================================

def get_reactor_games():

    print(
        "[Reactor Games] "
        "Начинаем поиск mature game art..."
    )

    # Перемешиваем игры, чтобы не было постоянного
    # порядка и одной и той же игры.
    game_tags = list(GAME_TAGS)

    random.shuffle(game_tags)

    # Каждый запуск пробует несколько игровых тегов.
    games_to_try = game_tags[:20]

    for game_tag in games_to_try:

        mature_tags = list(
            MATURE_GAME_TAGS
        )

        random.shuffle(
            mature_tags
        )

        # Пробуем несколько mature-вариантов
        # для конкретной игры.
        mature_to_try = mature_tags[:5]

        for mature_tag in mature_to_try:

            search_tag = (
                f"{game_tag} {mature_tag}"
            )

            print(
                "[Reactor Games] "
                f"Поиск: {search_tag}"
            )

            encoded_tag = quote(
                search_tag,
                safe="",
            )

            tag_url = (
                f"{REACTOR_BASE_URL}/tag/"
                f"{encoded_tag}"
            )

            try:

                response = requests.get(
                    tag_url,
                    headers=REACTOR_HEADERS,
                    timeout=30,
                )

                print(
                    "[Reactor Games] "
                    f"HTTP {response.status_code}"
                )

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(
                    response.text,
                    "html.parser",
                )

                post_links = (
                    extract_reactor_post_links(
                        soup
                    )
                )

                if not post_links:
                    continue

                random.shuffle(
                    post_links
                )

                for post_url in post_links[:10]:

                    if reactor_was_used(
                        post_url
                    ):
                        continue

                    try:

                        post_response = requests.get(
                            post_url,
                            headers=REACTOR_HEADERS,
                            timeout=30,
                        )

                        if (
                            post_response.status_code
                            != 200
                        ):
                            continue

                        post_soup = BeautifulSoup(
                            post_response.text,
                            "html.parser",
                        )

                        image_urls = (
                            extract_images_from_post(
                                post_soup
                            )
                        )

                        if not image_urls:
                            continue

                        random.shuffle(
                            image_urls
                        )

                        for image_url in image_urls:

                            image_key = (
                                f"{post_url}|"
                                f"{image_url}"
                            )

                            if reactor_was_used(
                                image_key
                            ):
                                continue

                            if not reactor_check_image(
                                image_url
                            ):
                                continue

                            reactor_mark_used(
                                post_url
                            )

                            reactor_mark_used(
                                image_key
                            )

                            print(
                                "[Reactor Games] "
                                "Найден новый пост"
                            )

                            print(
                                f"[Reactor Games] "
                                f"Игра: {game_tag}"
                            )

                            print(
                                f"[Reactor Games] "
                                f"Mature tag: "
                                f"{mature_tag}"
                            )

                            return {
                                "url": image_url,
                                "source":
                                    "Reactor Games",
                                "tag":
                                    search_tag,
                                "game_tag":
                                    game_tag,
                                "mature_tag":
                                    mature_tag,
                                "post_url":
                                    post_url,
                            }

                    except requests.RequestException as error:

                        print(
                            "[Reactor Games] "
                            f"Ошибка поста: "
                            f"{error}"
                        )

            except requests.RequestException as error:

                print(
                    "[Reactor Games] "
                    f"Ошибка запроса: "
                    f"{error}"
                )

            time.sleep(0.4)

    raise RuntimeError(
        "Reactor: "
        "не найден новый пост "
        "по проверенным игровым/mature тегам"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

    print(
        "[Pexels] Получаем изображение..."
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
            "GameArtPoster/1.0",
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
                src.get("large2x")
                or src.get("large")
                or src.get("original")
            )

            if image_url:

                return {
                    "url": image_url,
                    "source": "Pexels",
                }

    raise RuntimeError(
        "Pexels не вернул изображения"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(
    image_url,
):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    content = response.content

    if len(content) > 8 * 1024 * 1024:

        raise RuntimeError(
            "Изображение больше 8 MB"
        )

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg",
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
    image,
):

    source = image["source"]
    image_url = image["url"]

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
            "🎮 Mature Game Art",
        ),

        "Pexels": (
            PEXELS_WEBHOOK_URL,
            "📷 Game / Fashion",
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
            f"Webhook для {source} "
            "не настроен"
        )

    (
        filename,
        image_data,
        content_type,
    ) = download_image(
        image_url
    )

    content = (
        f"{message}\n"
        f"Источник: {source}"
    )

    if image.get("game_tag"):

        content += (
            f"\nИгра: "
            f"{image['game_tag']}"
        )

    if image.get("mature_tag"):

        content += (
            f"\nТег: "
            f"{image['mature_tag']}"
        )

    response = requests.post(
        webhook_url,
        data={
            "content": content
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

    if WAIFU_WEBHOOK_URL:

        sources.append(
            (
                "Waifu.im",
                get_random_waifu,
            )
        )

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

    if REACTOR_GAMES_WEBHOOK_URL:

        sources.append(
            (
                "Reactor Games",
                get_reactor_games,
            )
        )

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
        f"{successful}, errors: {errors}",
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

            "game_tags": len(
                GAME_TAGS
            ),

            "mature_tags": len(
                MATURE_GAME_TAGS
            ),
        },
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
        "Game Art Poster is running.",
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
