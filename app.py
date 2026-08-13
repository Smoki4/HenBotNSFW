import os
import random
import threading
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENV
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
# API
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
# GELBOORU LOCK
#
# Anime и Games не отправляют запросы одновременно.
# Это уменьшает вероятность 429.
# =========================================================

GELBOORU_LOCK = threading.Lock()


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

    if len(image_data) > 8 * 1024 * 1024:

        raise RuntimeError(
            "Image is larger than 8 MB"
        )

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg"
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
            f"{source_name}: webhook not configured"
        )

    if not image_url:

        raise RuntimeError(
            f"{source_name}: image URL missing"
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
            "Waifu.im не вернул изображение"
        )

    image_url = items[0].get(
        "url"
    )

    if not image_url:

        raise RuntimeError(
            "Waifu.im не вернул URL"
        )

    send_to_discord(
        WAIFU_WEBHOOK_URL,
        image_url,
        "🌸 Random Anime NSFW\n"
        "📌 Источник: Waifu.im",
        "Waifu.im"
    )

    print(
        "[Waifu.im] Успешно опубликовано"
    )


# =========================================================
# GELBOORU REQUEST
# =========================================================

def get_gelbooru_image(
    tags,
    source_name
):

    if not GELBOORU_API_KEY:

        raise RuntimeError(
            "GELBOORU_API_KEY не настроен"
        )

    if not GELBOORU_USER_ID:

        raise RuntimeError(
            "GELBOORU_USER_ID не настроен"
        )


    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "limit": 20,
        "tags": tags,
        "api_key": GELBOORU_API_KEY,
        "user_id": GELBOORU_USER_ID
    }


    # =====================================================
    # ВАЖНО:
    #
    # Anime и Games используют общий lock.
    # Но никакого долгого retry здесь нет.
    # =====================================================

    with GELBOORU_LOCK:

        try:

            response = requests.get(
                GELBOORU_API,
                params=params,
                headers=HEADERS,
                timeout=15
            )

        except requests.exceptions.Timeout:

            raise RuntimeError(
                f"{source_name}: "
                "Gelbooru timeout"
            )


        # =================================================
        # RATE LIMIT
        # =================================================

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After"
            )

            if retry_after:

                message = (
                    f"Gelbooru 429. "
                    f"Retry-After: {retry_after}"
                )

            else:

                message = (
                    "Gelbooru 429 Too Many Requests"
                )

            raise RuntimeError(
                f"{source_name}: {message}"
            )


        response.raise_for_status()


    # =====================================================
    # JSON
    # =====================================================

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            f"{source_name}: "
            "Gelbooru returned invalid JSON"
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
            "Gelbooru не вернул постов"
        )


    # =====================================================
    # RANDOM
    # =====================================================

    random.shuffle(
        posts
    )


    for post in posts:

        image_url = post.get(
            "file_url"
        )

        if not image_url:

            image_url = post.get(
                "sample_url"
            )

        if not image_url:
            continue


        return {
            "url": image_url,
            "post_id": post.get("id"),
            "rating": post.get("rating")
        }


    raise RuntimeError(
        f"{source_name}: "
        "у постов отсутствует URL"
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
        "rating:questionable "
        "sort:random "
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

    post_id = image.get(
        "post_id"
    )

    message = (
        "🔥 Random Anime Art\n"
        "📌 Источник: Gelbooru Anime"
    )

    if post_id:

        message += (
            f"\n🆔 Post ID: {post_id}"
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
        "rating:questionable "
        "{video_game game_character} "
        "sort:random "
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

    post_id = image.get(
        "post_id"
    )

    message = (
        "🎮 Random Game Art\n"
        "📌 Источник: Gelbooru Games"
    )

    if post_id:

        message += (
            f"\n🆔 Post ID: {post_id}"
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
            "PINTEREST_ACCESS_TOKEN не настроен"
        )

    headers = {
        "Authorization": (
            f"Bearer {PINTEREST_ACCESS_TOKEN}"
        ),
        "Content-Type": "application/json",
        "User-Agent": "AnimePoster/1.0"
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

            params["bookmark"] = bookmark

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

            params["bookmark"] = bookmark

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
            "Pinterest: доски не найдены"
        )

    board = random.choice(
        boards
    )

    board_id = board.get(
        "id"
    )

    board_name = board.get(
        "name",
        "Pinterest"
    )

    if not board_id:

        raise RuntimeError(
            "Pinterest: board ID отсутствует"
        )

    pins = get_board_pins(
        board_id
    )

    if not pins:

        raise RuntimeError(
            "Pinterest: в выбранной "
            "доске нет Pins"
        )

    random.shuffle(
        pins
    )

    image_url = None

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

            url = image_data.get(
                "url"
            )

            if url:

                image_url = url
                break

        if image_url:
            break


    if not image_url:

        raise RuntimeError(
            "Pinterest: "
            "изображение не найдено"
        )


    send_to_discord(
        PINTEREST_WEBHOOK_URL,
        image_url,
        "📌 Random Pinterest Art\n"
        f"📁 Доска: {board_name}",
        "Pinterest"
    )

    print(
        "[Pinterest] "
        "Успешно опубликовано"
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
            "PEXELS_API_KEY не настроен"
        )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }


    queries = [
        "woman portrait",
        "adult woman portrait",
        "fashion woman",
        "woman model",
        "beautiful woman"
    ]

    query = random.choice(
        queries
    )


    params = {
        "query": query,
        "per_page": 80,
        "page": random.randint(
            1,
            10
        )
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
            "Pexels не вернул изображения"
        )


    photo = random.choice(
        photos
    )

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
            "Pexels: URL отсутствует"
        )


    send_to_discord(
        PEXELS_WEBHOOK_URL,
        image_url,
        "📷 Random IRL Art\n"
        "📌 Источник: Pexels",
        "Pexels"
    )

    print(
        "[Pexels] "
        "Успешно опубликовано"
    )


# =========================================================
# STATUS
# =========================================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
        mimetype="text/plain"
    )


@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
        mimetype="text/plain"
    )


@app.route("/status")
def status():

    lines = [
        "Anime Poster status:",
        ""
    ]


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


    for name, enabled in (
        sources.items()
    ):

        if enabled:

            lines.append(
                f"✓ {name}"
            )

        else:

            lines.append(
                f"✗ {name}"
            )


    return Response(
        "\n".join(lines),
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# RUN ONE SOURCE SAFELY
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
            f"ОШИБКА: {error_text}"
        )

        return (
            source_name,
            False,
            error_text
        )


# =========================================================
# POST
#
# ВСЕ источники запускаются независимо.
#
# Если Gelbooru завис/получил 429,
# Pexels и Waifu НЕ ждут его.
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


    # =====================================================
    # WAIFU
    # =====================================================

    if WAIFU_WEBHOOK_URL:

        jobs.append(
            (
                "Waifu.im",
                post_waifu
            )
        )


    # =====================================================
    # GELBOORU ANIME
    # =====================================================

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


    # =====================================================
    # GELBOORU GAMES
    # =====================================================

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


    # =====================================================
    # PINTEREST
    # =====================================================

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


    # =====================================================
    # PEXELS
    # =====================================================

    if (
        PEXELS_API_KEY
        and PEXELS_WEBHOOK_URL
    ):

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


    # =====================================================
    # ПАРАЛЛЕЛЬНЫЙ ЗАПУСК
    # =====================================================

    max_workers = len(jobs)


    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = {}

        for source_name, function in jobs:

            future = executor.submit(
                run_source,
                source_name,
                function
            )

            futures[future] = (
                source_name
            )


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


    # =====================================================
    # LOG
    # =====================================================

    print(
        "=" * 55
    )

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
            f"POST: {name}: {error}"
        )


    print(
        "=" * 55
    )


    # =====================================================
    # HTTP RESPONSE
    # =====================================================

    if successful:

        return Response(
            (
                "OK - "
                f"successful: {len(successful)}, "
                f"errors: {len(failed)}"
            ),
            status=200,
            mimetype="text/plain"
        )


    return Response(
        "All sources failed",
        status=502,
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
