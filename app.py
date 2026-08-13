import os
import random
import time
import threading

import requests
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
# API
# =========================================================

WAIFU_API = "https://api.waifu.im/images"

DANBOORU_API = (
    "https://danbooru.donmai.us"
)

PEXELS_API = (
    "https://api.pexels.com/v1"
)


# =========================================================
# HEADERS
# =========================================================

HEADERS = {
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
                f"[Danbooru] "
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
        headers=HEADERS,
        timeout=25
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
    # Другие ошибки
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
            "Danbooru не вернул "
            "подходящих изображений"
        )

    selected = random.choice(
        valid_images
    )

    print(
        f"[{source_name}] "
        f"Изображение получено. "
        f"Post ID: "
        f"{selected.get('post_id')}"
    )

    return selected


# =========================================================
# DANBOORU ANIME
# Mature / glamour, без explicit
# =========================================================

def get_danbooru_anime():

    tags = (
        "1girl "
        "solo "
        "mature "
        "rating:s "
        "-loli "
        "-lolicon "
        "-shota "
        "-shotacon "
        "-child "
        "-minor "
        "-young"
    )

    return get_random_danbooru(
        tags,
        "Danbooru Anime"
    )


# =========================================================
# DANBOORU GAMES
# Mature / glamour, без explicit
# =========================================================

def get_danbooru_games():

    tags = (
        "1girl "
        "video_games "
        "game_character "
        "mature "
        "rating:s "
        "-loli "
        "-lolicon "
        "-shota "
        "-shotacon "
        "-child "
        "-minor "
        "-young"
    )

    return get_random_danbooru(
        tags,
        "Danbooru Games"
    )


# =========================================================
# PEXELS
# Взрослый glamour/fashion, без explicit
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
        "adult woman glamour fashion",
        "adult woman elegant fashion",
        "adult woman beach fashion",
        "adult woman evening dress",
        "adult woman portrait fashion",
        "adult woman boudoir style",
        "adult woman luxury fashion",
        "adult woman editorial fashion"
    ]

    query = random.choice(
        queries
    )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }

    params = {
        "query": query,
        "per_page": 80,
        "page": random.randint(1, 10)
    }

    response = requests.get(
        f"{PEXELS_API}/search",
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    photos = data.get(
        "photos",
        []
    )

    if not photos:

        raise RuntimeError(
            "Pexels не вернул изображения"
        )

    photo = random.choice(
        photos
    )

    image_url = (
        photo
        .get("src", {})
        .get("original")
    )

    if not image_url:

        raise RuntimeError(
            "Pexels не вернул URL"
        )

    return {
        "url": image_url,
        "source": "Pexels"
    }


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=40
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
            "🎨 Mature Anime Art\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Danbooru Games":

        webhook_url = (
            DANBOORU_GAMES_WEBHOOK_URL
        )

        message = (
            "🎮 Mature Game Character Art\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Pexels":

        webhook_url = (
            PEXELS_WEBHOOK_URL
        )

        message = (
            "📷 Adult Glamour / Fashion\n"
            "📌 Источник: Pexels"
        )

    else:

        raise RuntimeError(
            f"Неизвестный источник: "
            f"{source}"
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
            f"[{name}] ОШИБКА: "
            f"{error}"
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
    # Waifu
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:

        sources.append(
            (
                "Waifu.im",
                get_random_waifu
            )
        )

    # -----------------------------------------------------
    # Danbooru Anime
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
    # Danbooru Games
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
    # Pexels
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

    # Каждый источник работает независимо.
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
