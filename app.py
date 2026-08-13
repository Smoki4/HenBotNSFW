import os
import random
import threading
import time

import requests
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

DANBOORU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU"
)

DANBOORU_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU_GAMES"
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
# API URLS
# =========================================================

WAIFU_API = "https://api.waifu.im/images"

DANBOORU_API = "https://danbooru.donmai.us"

PEXELS_API = "https://api.pexels.com/v1"


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": "AnimePoster/1.0"
}


DANBOORU_HEADERS = {
    "User-Agent": (
        "AnimePoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json"
}


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
        "PageSize": 1
    }

    response = requests.get(
        WAIFU_API,
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    items = data.get(
        "items",
        []
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
        "source": "Waifu.im"
    }


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(
    tags,
    source_name
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
        "Получаем изображение..."
    )

    danbooru_wait()

    params = {
        "limit": 20,
        "tags": tags
    }

    try:

        response = requests.get(
            f"{DANBOORU_API}/posts.json",
            params=params,
            auth=(
                DANBOORU_USERNAME,
                DANBOORU_API_KEY
            ),
            headers=DANBOORU_HEADERS,
            timeout=30
        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            f"{source_name}: "
            "таймаут Danbooru"
        )

    except requests.exceptions.RequestException as error:

        raise RuntimeError(
            f"{source_name}: "
            f"ошибка соединения: {error}"
        )

    print(
        f"[{source_name}] "
        f"Danbooru HTTP: "
        f"{response.status_code}"
    )

    # -----------------------------------------------------
    # 429
    # -----------------------------------------------------

    if response.status_code == 429:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 429 "
            "Too Many Requests"
        )

    # -----------------------------------------------------
    # 401
    # -----------------------------------------------------

    if response.status_code == 401:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 401. "
            "Проверь логин и API key."
        )

    # -----------------------------------------------------
    # 403
    # -----------------------------------------------------

    if response.status_code == 403:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 403. "
            "Доступ запрещён."
        )

    # -----------------------------------------------------
    # 422
    # -----------------------------------------------------

    if response.status_code == 422:

        body = response.text[:1000]

        print(
            f"[{source_name}] "
            "Danbooru 422 response:"
        )

        print(body)

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 422. "
            f"Ответ: {body[:300]}"
        )

    # -----------------------------------------------------
    # Other errors
    # -----------------------------------------------------

    if response.status_code != 200:

        body = response.text[:500]

        raise RuntimeError(
            f"{source_name}: "
            f"Danbooru HTTP "
            f"{response.status_code}: "
            f"{body}"
        )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru вернул не JSON"
        )

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            f"{source_name}: "
            "неожиданный ответ Danbooru"
        )

    valid_images = []

    for post in data:

        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        valid_images.append({
            "url": image_url,
            "source": source_name,
            "post_id": post.get("id")
        })

    if not valid_images:

        raise RuntimeError(
            f"{source_name}: "
            f"нет результатов для: {tags}"
        )

    selected = random.choice(
        valid_images
    )

    print(
        f"[{source_name}] "
        "Изображение получено. "
        f"Post ID: {selected.get('post_id')}"
    )

    return selected


# =========================================================
# DANBOORU ANIME
#
# Danbooru в твоём случае разрешает максимум 2 тега.
# =========================================================

def get_danbooru_anime():

    tags = "rating:s 1girl"

    return get_random_danbooru(
        tags,
        "Danbooru Anime"
    )


# =========================================================
# DANBOORU GAMES
#
# Используем несколько вариантов, каждый максимум
# с двумя тегами. Если один вариант пустой,
# пробуем следующий.
# =========================================================

def get_danbooru_games():

    queries = [
        "rating:s game_character",
        "rating:s video_game",
        "rating:s game_cg",
        "rating:s video_games"
    ]

    random.shuffle(
        queries
    )

    last_error = None

    for tags in queries:

        try:

            print(
                "[Danbooru Games] "
                f"Пробуем запрос: {tags}"
            )

            return get_random_danbooru(
                tags,
                "Danbooru Games"
            )

        except RuntimeError as error:

            last_error = error

            print(
                "[Danbooru Games] "
                f"Запрос не подошёл: {error}"
            )

            # Небольшая пауза перед следующим
            # запросом, чтобы не создавать
            # лишнюю нагрузку на API.
            time.sleep(1.2)

    raise RuntimeError(
        "Danbooru Games: "
        "не удалось получить изображение. "
        f"Последняя ошибка: {last_error}"
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
    "adult boudoir model",
    "boudoir photography",
    "lingerie fashion model",
    "adult glamour portrait",
    "luxury lingerie",
    "sensual fashion portrait",
    "glamour photoshoot",
    "swimwear model",
    "adult fashion model",
    "elegant lingerie model",
     "sexy woman"
]

    random.shuffle(
        queries
    )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }

    for query in queries:

        try:

            params = {
                "query": query,
                "per_page": 80,
                "page": 1
            }

            response = requests.get(
                f"{PEXELS_API}/search",
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 429:

                raise RuntimeError(
                    "Pexels HTTP 429 "
                    "Too Many Requests"
                )

            response.raise_for_status()

            data = response.json()

            photos = data.get(
                "photos",
                []
            )

            if not photos:

                print(
                    "[Pexels] "
                    f"Нет результатов: {query}"
                )

                continue

            random.shuffle(
                photos
            )

            for photo in photos:

                src = photo.get(
                    "src",
                    {}
                )

                image_url = (
                    src.get("original")
                    or src.get("large2x")
                    or src.get("large")
                )

                if not image_url:
                    continue

                print(
                    "[Pexels] "
                    f"Запрос сработал: {query}"
                )

                return {
                    "url": image_url,
                    "source": "Pexels"
                }

        except RuntimeError:

            raise

        except Exception as error:

            print(
                "[Pexels] "
                f"Ошибка запроса "
                f"'{query}': {error}"
            )

            continue

    raise RuntimeError(
        "Pexels не вернул изображения "
        "ни по одному запросу"
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45
    )

    response.raise_for_status()

    image_data = response.content

    if len(image_data) > (
        8 * 1024 * 1024
    ):

        raise RuntimeError(
            "Изображение больше 8 MB"
        )

    content_type = (
        response.headers.get(
            "Content-Type",
            "image/jpeg"
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

    filename = (
        f"image.{extension}"
    )

    return (
        filename,
        image_data,
        content_type
    )


# =========================================================
# DISCORD
# =========================================================

def send_to_discord(
    image
):

    source = image.get(
        "source"
    )

    if source == "Waifu.im":

        webhook_url = (
            WAIFU_WEBHOOK_URL
        )

        message = (
            "🌸 Random Anime\n"
            "📌 Источник: Waifu.im"
        )

    elif source == "Danbooru Anime":

        webhook_url = (
            DANBOORU_WEBHOOK_URL
        )

        message = (
            "🎨 Anime Art\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Danbooru Games":

        webhook_url = (
            DANBOORU_GAMES_WEBHOOK_URL
        )

        message = (
            "🎮 Game Character Art\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Pexels":

        webhook_url = (
            PEXELS_WEBHOOK_URL
        )

        message = (
            "📷 Fashion / Glamour\n"
            "📌 Источник: Pexels"
        )

    else:

        raise RuntimeError(
            f"Неизвестный источник: {source}"
        )

    if not webhook_url:

        raise RuntimeError(
            f"Webhook для {source} "
            "не настроен"
        )

    image_url = image.get(
        "url"
    )

    if not image_url:

        raise RuntimeError(
            "У изображения нет URL"
        )

    (
        filename,
        image_data,
        content_type
    ) = download_image(
        image_url
    )

    files = {
        "file": (
            filename,
            image_data,
            content_type
        )
    }

    response = requests.post(
        webhook_url,
        data={
            "content": message
        },
        files=files,
        timeout=45
    )

    response.raise_for_status()


# =========================================================
# PUBLISH ONE SOURCE
# =========================================================

def publish_source(
    name,
    getter
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
            "error": None
        }

    except Exception as error:

        print(
            f"[{name}] "
            f"ОШИБКА: {error}"
        )

        return {
            "source": name,
            "success": False,
            "error": str(error)
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
    # WAIFU
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:

        sources.append(
            (
                "Waifu.im",
                get_random_waifu
            )
        )

    # -----------------------------------------------------
    # DANBOORU ANIME
    # -----------------------------------------------------

    if (
        DANBOORU_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        sources.append(
            (
                "Danbooru Anime",
                get_danbooru_anime
            )
        )

    # -----------------------------------------------------
    # DANBOORU GAMES
    # -----------------------------------------------------

    if (
        DANBOORU_GAMES_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        sources.append(
            (
                "Danbooru Games",
                get_danbooru_games
            )
        )

    # -----------------------------------------------------
    # PEXELS
    # -----------------------------------------------------

    if (
        PEXELS_WEBHOOK_URL
        and PEXELS_API_KEY
    ):

        sources.append(
            (
                "Pexels",
                get_random_pexels
            )
        )

    if not sources:

        return Response(
            "No sources configured",
            status=500,
            mimetype="text/plain"
        )

    results = []

    # -----------------------------------------------------
    # Источники полностью независимы:
    # ошибка одного не останавливает остальные.
    # -----------------------------------------------------

    for name, getter in sources:

        result = publish_source(
            name,
            getter
        )

        results.append(
            result
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
        f"POST: успешно: {successful}"
    )

    print(
        f"POST: ошибок: {errors}"
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
        mimetype="text/plain"
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

            "danbooru_games": bool(
                DANBOORU_GAMES_WEBHOOK_URL
                and DANBOORU_USERNAME
                and DANBOORU_API_KEY
            ),

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
            )
        }
    }


# =========================================================
# PING
# =========================================================

@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "8080"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
