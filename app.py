import os
import random
import time
import threading
import requests

from flask import Flask, Response

app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU")

DANBOORU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU"
)

DANBOORU_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU_GAMES"
)

PINTEREST_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PINTEREST"
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

PINTEREST_ACCESS_TOKEN = os.environ.get(
    "PINTEREST_ACCESS_TOKEN"
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

PINTEREST_API = (
    "https://api.pinterest.com/v5"
)


# =========================================================
# HTTP HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "AnimePoster/1.0"
}


# Danbooru требует уникальный User-Agent.
# Если знаешь свой числовой ID, можешь добавить его:
#
# AnimePoster/1.0 (user #123456)
#
# Username оставляем для идентификации бота.

DANBOORU_HEADERS = {
    "User-Agent": (
        f"AnimePoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json"
}


# =========================================================
# DANBOORU LIMITER
# =========================================================

# Не делаем частые запросы к Danbooru.
# Один запрос примерно раз в 1.2 секунды.

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
        timeout=20
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

    image = items[0]

    image_url = image.get(
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
        f"Получаем изображение..."
    )

    danbooru_wait()

    params = {
        "login": DANBOORU_USERNAME,
        "api_key": DANBOORU_API_KEY,

        # Получаем несколько результатов,
        # затем случайно выбираем один.
        "limit": 20,

        "tags": tags
    }

    response = requests.get(
        f"{DANBOORU_API}/posts.json",
        params=params,
        headers=DANBOORU_HEADERS,
        timeout=25
    )

    if response.status_code == 429:

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 429"
        )

    response.raise_for_status()

    data = response.json()

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

        # У Danbooru могут быть разные
        # варианты файлов.

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
            "Danbooru не вернул изображения"
        )

    return random.choice(
        valid_images
    )


# =========================================================
# DANBOORU ANIME
# =========================================================

def get_danbooru_anime():

    tags = (
        "rating:e "
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
# =========================================================

def get_danbooru_games():

    tags = (
        "rating:e "
        "video_games "
        "game_character "
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
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

    print(
        "[Pexels] Получаем изображение..."
    )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }

    params = {
        "query": "adult woman fashion",
        "per_page": 80,
        "page": random.randint(1, 10)
    }

    response = requests.get(
        f"{PEXELS_API}/search",
        headers=headers,
        params=params,
        timeout=25
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
# PINTEREST
# =========================================================

def pinterest_request(
    endpoint,
    params=None
):

    if not PINTEREST_ACCESS_TOKEN:

        raise RuntimeError(
            "PINTEREST_ACCESS_TOKEN "
            "не настроен"
        )

    headers = {
        "Authorization":
            f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type":
            "application/json",
        "User-Agent":
            "AnimePoster/1.0"
    }

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=headers,
        params=params,
        timeout=25
    )

    response.raise_for_status()

    return response.json()


def get_pinterest_boards():

    boards = []

    bookmark = None

    while True:

        params = {
            "page_size": 100
        }

        if bookmark:

            params[
                "bookmark"
            ] = bookmark

        data = pinterest_request(
            "/boards",
            params
        )

        items = data.get(
            "items",
            []
        )

        boards.extend(items)

        bookmark = data.get(
            "bookmark"
        )

        if not bookmark:
            break

        if len(boards) >= 500:
            break

    return boards


def get_board_pins(
    board_id
):

    pins = []

    bookmark = None

    while True:

        params = {
            "page_size": 100
        }

        if bookmark:

            params[
                "bookmark"
            ] = bookmark

        data = pinterest_request(
            f"/boards/{board_id}/pins",
            params
        )

        items = data.get(
            "items",
            []
        )

        pins.extend(items)

        bookmark = data.get(
            "bookmark"
        )

        if not bookmark:
            break

        if len(pins) >= 1000:
            break

    return pins


def get_random_pinterest_pin():

    boards = get_pinterest_boards()

    if not boards:

        raise RuntimeError(
            "Pinterest не вернул доски"
        )

    all_pins = []

    for board in boards:

        board_id = board.get(
            "id"
        )

        if not board_id:
            continue

        board_name = board.get(
            "name",
            "Pinterest"
        )

        try:

            pins = get_board_pins(
                board_id
            )

            for pin in pins:

                media = pin.get(
                    "media",
                    {}
                )

                images = media.get(
                    "images",
                    {}
                )

                image_url = None

                for image_data in (
                    images.values()
                ):

                    if isinstance(
                        image_data,
                        dict
                    ):

                        url = image_data.get(
                            "url"
                        )

                        if url:

                            image_url = url
                            break

                if image_url:

                    all_pins.append({
                        "url": image_url,
                        "source": "Pinterest",
                        "board_name":
                            board_name,
                        "pin_id":
                            pin.get("id")
                    })

        except Exception as error:

            print(
                f"[Pinterest] "
                f"Ошибка доски "
                f"{board_name}: {error}"
            )

    if not all_pins:

        raise RuntimeError(
            "Pinterest не найден"
        )

    return random.choice(
        all_pins
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=35
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
        f"anime_art.{extension}"
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
            "🌸 Random Anime NSFW\n"
            "📌 Источник: Waifu.im"
        )

    elif source == "Danbooru Anime":

        webhook_url = (
            DANBOORU_WEBHOOK_URL
        )

        message = (
            "🎨 Random Anime\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Danbooru Games":

        webhook_url = (
            DANBOORU_GAMES_WEBHOOK_URL
        )

        message = (
            "🎮 Random Game Art\n"
            "📌 Источник: Danbooru"
        )

    elif source == "Pexels":

        webhook_url = (
            PEXELS_WEBHOOK_URL
        )

        message = (
            "📷 Random IRL Art\n"
            "📌 Источник: Pexels"
        )

    elif source == "Pinterest":

        webhook_url = (
            PINTEREST_WEBHOOK_URL
        )

        board_name = image.get(
            "board_name",
            "Pinterest"
        )

        message = (
            "📌 Random Pinterest Art\n"
            f"📁 Доска: {board_name}"
        )

    else:

        raise RuntimeError(
            f"Неизвестный источник: "
            f"{source}"
        )

    if not webhook_url:

        raise RuntimeError(
            f"Webhook для "
            f"{source} не настроен"
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
        timeout=40
    )

    response.raise_for_status()


# =========================================================
# INDEPENDENT SOURCE WORKER
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
            f"[{name}] ОШИБКА: {error}"
        )

        return {
            "source": name,
            "success": False,
            "error": str(error)
        }


# =========================================================
# POST
#
# Каждый источник работает НЕЗАВИСИМО.
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
                get_random_waifu
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
                get_danbooru_anime
            )
        )

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

    if (
        PINTEREST_WEBHOOK_URL
        and PINTEREST_ACCESS_TOKEN
    ):

        sources.append(
            (
                "Pinterest",
                get_random_pinterest_pin
            )
        )

    if not sources:

        return Response(
            "No sources configured",
            status=500,
            mimetype="text/plain"
        )

    results = []

    # =====================================================
    # ПОСЛЕДОВАТЕЛЬНО
    #
    # Это специально:
    # Danbooru имеет собственный rate limit.
    # =====================================================

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

    errors = len(results) - successful

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

    # ВАЖНО:
    # /post возвращает 200 даже если один источник
    # временно упал. Поэтому cron-job.org не будет
    # считать весь запуск неудачным.

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
            ),
            "pinterest": bool(
                PINTEREST_WEBHOOK_URL
                and PINTEREST_ACCESS_TOKEN
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
