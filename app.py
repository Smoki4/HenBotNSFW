import os
import threading
import time

import requests

from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

GELBOORU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_GELBOORU"
)

GELBOORU_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_GELBOORU_GAMES"
)

PINTEREST_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PINTEREST"
)

PEXELS_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PEXELS"
)


GELBOORU_API_KEY = os.environ.get(
    "GELBOORU_API_KEY"
)

GELBOORU_USER_ID = os.environ.get(
    "GELBOORU_USER_ID"
)

PINTEREST_ACCESS_TOKEN = os.environ.get(
    "PINTEREST_ACCESS_TOKEN"
)

PEXELS_API_KEY = os.environ.get(
    "PEXELS_API_KEY"
)


# =========================================================
# API URLS
# =========================================================

WAIFU_API = (
    "https://api.waifu.im/images"
)

GELBOORU_API = (
    "https://gelbooru.com/index.php"
)

PINTEREST_API = (
    "https://api.pinterest.com/v5"
)

PEXELS_API = (
    "https://api.pexels.com/v1"
)


# =========================================================
# HTTP
# =========================================================

HEADERS = {
    "User-Agent": "AnimePoster/1.0"
}


# =========================================================
# GELBOORU LIMITER
# =========================================================

GELBOORU_LOCK = threading.Lock()

GELBOORU_MIN_INTERVAL = 3.0

gelbooru_last_request = 0.0


def gelbooru_wait():

    global gelbooru_last_request

    with GELBOORU_LOCK:

        now = time.monotonic()

        elapsed = (
            now - gelbooru_last_request
        )

        if elapsed < GELBOORU_MIN_INTERVAL:

            wait_time = (
                GELBOORU_MIN_INTERVAL
                - elapsed
            )

            print(
                f"[Gelbooru] "
                f"Пауза {wait_time:.1f} сек."
            )

            time.sleep(
                wait_time
            )

        gelbooru_last_request = (
            time.monotonic()
        )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=20
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
    webhook_url,
    image_url,
    message,
    source_name
):

    if not webhook_url:

        raise RuntimeError(
            f"{source_name}: "
            "webhook не настроен"
        )

    if not image_url:

        raise RuntimeError(
            f"{source_name}: "
            "URL изображения отсутствует"
        )

    filename, image_data, content_type = (
        download_image(image_url)
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
        timeout=30
    )

    response.raise_for_status()


# =========================================================
# WAIFU.IM
# =========================================================

def post_waifu():

    print(
        "[Waifu.im] "
        "Получаем изображение..."
    )

    params = {
        "OrderBy": "Random",
        "PageSize": 1
    }

    response = requests.get(
        WAIFU_API,
        params=params,
        headers=HEADERS,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    items = data.get(
        "items",
        []
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

    send_to_discord(
        WAIFU_WEBHOOK_URL,
        image_url,
        (
            "🌸 Random Anime Art\n"
            "📌 Источник: Waifu.im"
        ),
        "Waifu.im"
    )

    print(
        "[Waifu.im] "
        "Успешно опубликовано"
    )


# =========================================================
# GELBOORU API
# =========================================================

def get_gelbooru_image(
    tags,
    source_name
):

    if not GELBOORU_API_KEY:

        raise RuntimeError(
            "GELBOORU_API_KEY "
            "не настроен"
        )

    if not GELBOORU_USER_ID:

        raise RuntimeError(
            "GELBOORU_USER_ID "
            "не настроен"
        )

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "limit": 1,
        "tags": tags,
        "api_key": GELBOORU_API_KEY,
        "user_id": GELBOORU_USER_ID
    }

    print(
        f"[{source_name}] "
        "Ожидание лимитера Gelbooru..."
    )

    gelbooru_wait()

    print(
        f"[{source_name}] "
        "Запрос Gelbooru..."
    )

    response = requests.get(
        GELBOORU_API,
        params=params,
        headers=HEADERS,
        timeout=15
    )

    if response.status_code == 429:

        raise RuntimeError(
            f"{source_name}: "
            "Gelbooru 429 "
            "Too Many Requests"
        )

    response.raise_for_status()

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            f"{source_name}: "
            "Gelbooru вернул "
            "невалидный JSON"
        )

    if isinstance(
        data,
        dict
    ):

        posts = data.get(
            "post",
            []
        )

    elif isinstance(
        data,
        list
    ):

        posts = data

    else:

        posts = []

    if not posts:

        raise RuntimeError(
            f"{source_name}: "
            "Gelbooru не вернул "
            "постов"
        )

    for post in posts:

        image_url = post.get(
            "file_url"
        )

        if not image_url:

            image_url = post.get(
                "sample_url"
            )

        if image_url:

            return {
                "url": image_url,
                "post_id": post.get(
                    "id"
                )
            }

    raise RuntimeError(
        f"{source_name}: "
        "изображение не найдено"
    )


# =========================================================
# GELBOORU ANIME
# =========================================================

def post_gelbooru_anime():

    print(
        "[Gelbooru Anime] "
        "Получаем изображение..."
    )

    tags = (
        "anime "
        "-loli "
        "-lolicon "
        "-shota "
        "-shotacon "
        "-child "
        "-minor "
        "-young"
    )

    image = get_gelbooru_image(
        tags,
        "Gelbooru Anime"
    )

    message = (
        "🌸 Random Anime Art\n"
        "📌 Источник: Gelbooru Anime"
    )

    if image.get("post_id"):

        message += (
            f"\n🆔 Post ID: "
            f"{image['post_id']}"
        )

    send_to_discord(
        GELBOORU_WEBHOOK_URL,
        image["url"],
        message,
        "Gelbooru Anime"
    )

    print(
        "[Gelbooru Anime] "
        "Успешно опубликовано"
    )


# =========================================================
# GELBOORU GAMES
# =========================================================

def post_gelbooru_games():

    print(
        "[Gelbooru Games] "
        "Получаем изображение..."
    )

    tags = (
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

    image = get_gelbooru_image(
        tags,
        "Gelbooru Games"
    )

    message = (
        "🎮 Random Game Art\n"
        "📌 Источник: Gelbooru Games"
    )

    if image.get("post_id"):

        message += (
            f"\n🆔 Post ID: "
            f"{image['post_id']}"
        )

    send_to_discord(
        GELBOORU_GAMES_WEBHOOK_URL,
        image["url"],
        message,
        "Gelbooru Games"
    )

    print(
        "[Gelbooru Games] "
        "Успешно опубликовано"
    )


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
        "Authorization": (
            f"Bearer "
            f"{PINTEREST_ACCESS_TOKEN}"
        ),
        "Content-Type": (
            "application/json"
        ),
        "User-Agent": (
            "AnimePoster/1.0"
        )
    }

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=headers,
        params=params,
        timeout=20
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
            params=params
        )

        boards.extend(
            data.get(
                "items",
                []
            )
        )

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
            params=params
        )

        pins.extend(
            data.get(
                "items",
                []
            )
        )

        bookmark = data.get(
            "bookmark"
        )

        if not bookmark:
            break

        if len(pins) >= 1000:
            break

    return pins


def post_pinterest():

    print(
        "[Pinterest] "
        "Получаем изображение..."
    )

    boards = get_pinterest_boards()

    if not boards:

        raise RuntimeError(
            "Pinterest: "
            "доски не найдены"
        )

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

        except Exception as error:

            print(
                f"[Pinterest] "
                f"Ошибка доски "
                f"{board_name}: "
                f"{error}"
            )

            continue

        for pin in pins:

            media = pin.get(
                "media",
                {}
            )

            images = media.get(
                "images",
                {}
            )

            for image_data in (
                images.values()
            ):

                if not isinstance(
                    image_data,
                    dict
                ):
                    continue

                image_url = image_data.get(
                    "url"
                )

                if not image_url:
                    continue

                send_to_discord(
                    PINTEREST_WEBHOOK_URL,
                    image_url,
                    (
                        "📌 Random "
                        "Pinterest Art\n"
                        f"📁 Доска: "
                        f"{board_name}"
                    ),
                    "Pinterest"
                )

                print(
                    "[Pinterest] "
                    "Успешно опубликовано"
                )

                return

    raise RuntimeError(
        "Pinterest: "
        "изображение не найдено"
    )


# =========================================================
# PEXELS
# =========================================================

def post_pexels():

    print(
        "[Pexels] "
        "Получаем изображение..."
    )

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY "
            "не настроен"
        )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }

    params = {
        "query": "woman portrait",
        "per_page": 20
    }

    response = requests.get(
        f"{PEXELS_API}/search",
        headers=headers,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    photos = data.get(
        "photos",
        []
    )

    if not photos:

        raise RuntimeError(
            "Pexels "
            "не вернул изображения"
        )

    photo = photos[
        int(time.time()) % len(photos)
    ]

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

        raise RuntimeError(
            "Pexels: "
            "URL изображения отсутствует"
        )

    send_to_discord(
        PEXELS_WEBHOOK_URL,
        image_url,
        (
            "📷 Random IRL Art\n"
            "📌 Источник: Pexels"
        ),
        "Pexels"
    )

    print(
        "[Pexels] "
        "Успешно опубликовано"
    )


# =========================================================
# SOURCE WRAPPER
# =========================================================

def run_source(
    source_name,
    function
):

    try:

        function()

        return (
            source_name,
            True,
            None
        )

    except Exception as error:

        error_text = str(
            error
        )

        print(
            f"[{source_name}] "
            f"ОШИБКА: "
            f"{error_text}"
        )

        return (
            source_name,
            False,
            error_text
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
# STATUS
# =========================================================

@app.route("/status")
def status():

    sources = {

        "Waifu.im": bool(
            WAIFU_WEBHOOK_URL
        ),

        "Gelbooru Anime": bool(
            GELBOORU_API_KEY
            and GELBOORU_USER_ID
            and GELBOORU_WEBHOOK_URL
        ),

        "Gelbooru Games": bool(
            GELBOORU_API_KEY
            and GELBOORU_USER_ID
            and GELBOORU_GAMES_WEBHOOK_URL
        ),

        "Pinterest": bool(
            PINTEREST_ACCESS_TOKEN
            and PINTEREST_WEBHOOK_URL
        ),

        "Pexels": bool(
            PEXELS_API_KEY
            and PEXELS_WEBHOOK_URL
        )
    }

    lines = [
        "Anime Poster status:",
        ""
    ]

    for name, enabled in sources.items():

        prefix = (
            "✓ "
            if enabled
            else "✗ "
        )

        lines.append(
            prefix + name
        )

    return Response(
        "\n".join(lines),
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# GELBOORU DIAGNOSTIC TEST
#
# Делает только ОДИН запрос.
#
# API KEY НИКОГДА НЕ ВЫВОДИМ.
# =========================================================

@app.route("/test-gelbooru")
def test_gelbooru():

    try:

        if not GELBOORU_API_KEY:

            return Response(
                "GELBOORU_API_KEY is missing",
                status=500,
                mimetype="text/plain"
            )

        if not GELBOORU_USER_ID:

            return Response(
                "GELBOORU_USER_ID is missing",
                status=500,
                mimetype="text/plain"
            )

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
            "limit": 1,
            "tags": "anime",
            "api_key": GELBOORU_API_KEY,
            "user_id": GELBOORU_USER_ID
        }

        diagnostic_headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/150.0 Safari/537.36"
            ),
            "Accept": (
                "application/json,"
                "text/plain,*/*"
            )
        }

        print(
            "[Gelbooru TEST] "
            "Отправляем одиночный запрос..."
        )

        response = requests.get(
            GELBOORU_API,
            params=params,
            headers=diagnostic_headers,
            timeout=15
        )

        print(
            "[Gelbooru TEST] STATUS:",
            response.status_code
        )

        print(
            "[Gelbooru TEST] HEADERS:"
        )

        for key, value in (
            response.headers.items()
        ):

            # Не выводим ничего похожего
            # на секреты.
            if key.lower() in [
                "authorization",
                "cookie",
                "set-cookie"
            ]:
                continue

            print(
                f"  {key}: {value}"
            )

        print(
            "[Gelbooru TEST] BODY:"
        )

        print(
            response.text[:3000]
        )

        retry_after = (
            response.headers.get(
                "Retry-After"
            )
        )

        server = (
            response.headers.get(
                "Server"
            )
        )

        body = response.text[:3000]

        return Response(
            (
                f"HTTP: "
                f"{response.status_code}\n\n"
                f"Server: "
                f"{server}\n"
                f"Retry-After: "
                f"{retry_after}\n\n"
                "Response:\n"
                f"{body}"
            ),
            status=200,
            mimetype="text/plain"
        )

    except requests.exceptions.Timeout:

        return Response(
            "Gelbooru test timeout",
            status=504,
            mimetype="text/plain"
        )

    except Exception as error:

        print(
            "[Gelbooru TEST] ERROR:",
            error
        )

        return Response(
            f"Test error: {error}",
            status=500,
            mimetype="text/plain"
        )


# =========================================================
# POST
# =========================================================

@app.route("/post")
def post_image():

    print("")
    print("=" * 55)
    print(
        "POST: запуск независимой публикации"
    )
    print("=" * 55)

    jobs = []

    if WAIFU_WEBHOOK_URL:

        jobs.append(
            (
                "Waifu.im",
                post_waifu
            )
        )

    if (
        GELBOORU_API_KEY
        and GELBOORU_USER_ID
        and GELBOORU_WEBHOOK_URL
    ):

        jobs.append(
            (
                "Gelbooru Anime",
                post_gelbooru_anime
            )
        )

    if (
        GELBOORU_API_KEY
        and GELBOORU_USER_ID
        and GELBOORU_GAMES_WEBHOOK_URL
    ):

        jobs.append(
            (
                "Gelbooru Games",
                post_gelbooru_games
            )
        )

    if (
        PINTEREST_ACCESS_TOKEN
        and PINTEREST_WEBHOOK_URL
    ):

        jobs.append(
            (
                "Pinterest",
                post_pinterest
            )
        )

    if PEXELS_API_KEY and PEXELS_WEBHOOK_URL:

        jobs.append(
            (
                "Pexels",
                post_pexels
            )
        )

    if not jobs:

        return Response(
            "No sources configured",
            status=500,
            mimetype="text/plain"
        )

    successful = []
    failed = []

    with ThreadPoolExecutor(
        max_workers=len(jobs)
    ) as executor:

        futures = {}

        for source_name, function in jobs:

            future = executor.submit(
                run_source,
                source_name,
                function
            )

            futures[
                future
            ] = source_name

        for future in as_completed(
            futures
        ):

            source_name = futures[
                future
            ]

            try:

                name, success, error = (
                    future.result()
                )

                if success:

                    successful.append(
                        name
                    )

                else:

                    failed.append(
                        (
                            name,
                            error
                        )
                    )

            except Exception as error:

                failed.append(
                    (
                        source_name,
                        str(error)
                    )
                )

    print("=" * 55)

    print(
        "POST: публикация завершена"
    )

    print(
        f"POST: успешно: "
        f"{len(successful)}"
    )

    print(
        f"POST: ошибок: "
        f"{len(failed)}"
    )

    for name, error in failed:

        print(
            f"POST: {name}: "
            f"{error}"
        )

    print("=" * 55)

    return Response(
        (
            "OK - "
            f"successful: "
            f"{len(successful)}, "
            f"errors: "
            f"{len(failed)}"
        ),
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# START SERVER
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
