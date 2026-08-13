import os
import random
import threading
import time
from urllib.parse import urljoin

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

REACTOR_GAMES_URL = (
    "https://reactor.cc/tag/"
    "Игровая+эротика"
)


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
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


# =========================================================
# REACTOR DUPLICATE MEMORY
# =========================================================

REACTOR_USED = set()

REACTOR_LOCK = threading.Lock()

MAX_REACTOR_MEMORY = 300


def reactor_was_used(url):

    with REACTOR_LOCK:
        return url in REACTOR_USED


def reactor_mark_used(url):

    with REACTOR_LOCK:

        REACTOR_USED.add(url)

        if len(REACTOR_USED) > MAX_REACTOR_MEMORY:

            # Удаляем случайный старый URL.
            old_url = random.choice(
                list(REACTOR_USED)
            )

            REACTOR_USED.discard(
                old_url
            )


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

        LAST_DANBOORU_REQUEST = (
            time.monotonic()
        )


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

    items = data.get(
        "items",
        [],
    )

    if not items:

        raise RuntimeError(
            "Waifu.im не вернул изображение"
        )

    image_url = items[0].get(
        "url"
    )

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

    return random.choice(
        images
    )


def get_danbooru_anime():

    return get_random_danbooru(
        "rating:s 1girl",
        "Danbooru Anime",
    )


# =========================================================
# REACTOR
# =========================================================

def get_reactor_games():

    print(
        "[Reactor Games] "
        "Получаем страницу..."
    )

    response = requests.get(
        REACTOR_GAMES_URL,
        headers=REACTOR_HEADERS,
        timeout=30,
    )

    print(
        "[Reactor Games] "
        f"HTTP: {response.status_code}"
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    candidates = []

    # =====================================================
    # Собираем URL изображений
    # =====================================================

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

            src = src.strip()

            if not src:
                continue

            src = urljoin(
                REACTOR_GAMES_URL,
                src,
            )

            lowered = src.lower()

            # Только изображения постов.
            if "/pics/post/" not in lowered:
                continue

            # Служебные изображения пропускаем.
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

            # =================================================
            # Полная версия
            # =================================================

            if (
                "/pics/post/"
                in src
                and
                "/pics/post/full/"
                not in src
            ):

                src = src.replace(
                    "/pics/post/",
                    "/pics/post/full/",
                    1,
                )

            candidates.append(src)

    # =====================================================
    # Удаляем дубли
    # =====================================================

    candidates = list(
        dict.fromkeys(
            candidates
        )
    )

    print(
        "[Reactor Games] "
        f"Найдено изображений: "
        f"{len(candidates)}"
    )

    if not candidates:

        raise RuntimeError(
            "Reactor не вернул "
            "изображения постов"
        )

    # =====================================================
    # Сначала выбираем неиспользованные
    # =====================================================

    unused = [
        url
        for url in candidates
        if not reactor_was_used(url)
    ]

    if unused:

        candidates = unused

    random.shuffle(
        candidates
    )

    # =====================================================
    # Проверяем несколько URL
    # =====================================================

    for image_url in candidates[:15]:

        try:

            check = requests.get(
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
                check.status_code
            )

            content_type = (
                check.headers.get(
                    "Content-Type",
                    "",
                ).lower()
            )

            check.close()

            if status != 200:
                continue

            is_image = (
                content_type.startswith(
                    "image/"
                )
                or any(
                    ext in image_url.lower()
                    for ext in (
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp",
                        ".gif",
                    )
                )
            )

            if not is_image:
                continue

            reactor_mark_used(
                image_url
            )

            print(
                "[Reactor Games] "
                "Выбрано новое изображение"
            )

            return {
                "url": image_url,
                "source": "Reactor Games",
            }

        except requests.RequestException as error:

            print(
                "[Reactor Games] "
                f"Проверка не удалась: "
                f"{error}"
            )

    # =====================================================
    # Fallback
    # =====================================================

    image_url = random.choice(
        candidates
    )

    reactor_mark_used(
        image_url
    )

    print(
        "[Reactor Games] "
        "Используем fallback"
    )

    return {
        "url": image_url,
        "source": "Reactor Games",
    }


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
    image_url
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
