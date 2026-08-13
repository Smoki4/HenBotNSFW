import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

DISCORD_WEBHOOK_WAIFU = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

DISCORD_WEBHOOK_GELBOORU = os.environ.get(
    "DISCORD_WEBHOOK_GELBOORU"
)

DISCORD_WEBHOOK_GELBOORU_GAMES = os.environ.get(
    "DISCORD_WEBHOOK_GELBOORU_GAMES"
)

DISCORD_WEBHOOK_PINTEREST = os.environ.get(
    "DISCORD_WEBHOOK_PINTEREST"
)

DISCORD_WEBHOOK_PEXELS = os.environ.get(
    "DISCORD_WEBHOOK_PEXELS"
)

PINTEREST_ACCESS_TOKEN = os.environ.get(
    "PINTEREST_ACCESS_TOKEN"
)

PEXELS_API_KEY = os.environ.get(
    "PEXELS_API_KEY"
)

GELBOORU_API_KEY = os.environ.get(
    "GELBOORU_API_KEY"
)

GELBOORU_USER_ID = os.environ.get(
    "GELBOORU_USER_ID"
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
    "https://api.pexels.com/v1/search"
)


# =========================================================
# COMMON HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "AnimePoster/4.0"
}


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu():

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
# GELBOORU REQUEST
# =========================================================

def gelbooru_request(tags):

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "limit": "100",
        "tags": tags
    }

    if GELBOORU_API_KEY:
        params["api_key"] = GELBOORU_API_KEY

    if GELBOORU_USER_ID:
        params["user_id"] = GELBOORU_USER_ID

    response = requests.get(
        GELBOORU_API,
        params=params,
        headers=HEADERS,
        timeout=25
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):

        posts = data

    elif isinstance(data, dict):

        if data.get("success") is False:
            raise RuntimeError(
                data.get(
                    "message",
                    "Gelbooru API error"
                )
            )

        posts = data.get(
            "post",
            []
        )

        if isinstance(posts, dict):
            posts = [posts]

    else:
        posts = []

    if not posts:
        raise RuntimeError(
            "Gelbooru не вернул постов"
        )

    return posts


# =========================================================
# GELBOORU FILTER
# =========================================================

def choose_gelbooru_post(posts):

    forbidden_tags = {
        "loli",
        "lolicon",
        "shota",
        "shotacon",
        "child",
        "minor",
        "young"
    }

    valid_posts = []

    for post in posts:

        image_url = post.get(
            "file_url"
        )

        if not image_url:
            continue

        tags = set(
            str(
                post.get(
                    "tags",
                    ""
                )
            ).lower().split()
        )

        if tags.intersection(
            forbidden_tags
        ):
            continue

        rating = str(
            post.get(
                "rating",
                ""
            )
        ).lower()

        if rating and rating != "questionable":
            continue

        valid_posts.append(post)

    if not valid_posts:
        raise RuntimeError(
            "Gelbooru не нашёл подходящих постов"
        )

    return random.choice(
        valid_posts
    )


# =========================================================
# GELBOORU ANIME
# =========================================================

def get_random_gelbooru_anime():

    tags = (
        "rating:questionable "
        "-loli "
        "-lolicon "
        "-shota "
        "-shotacon "
        "-child "
        "-minor "
        "-young"
    )

    posts = gelbooru_request(tags)

    post = choose_gelbooru_post(posts)

    return {
        "url": post["file_url"],
        "source": "Gelbooru Anime",
        "post_id": post.get("id")
    }


# =========================================================
# GELBOORU GAMES
# =========================================================

def get_random_gelbooru_games():

    tags = (
        "rating:questionable "
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

    posts = gelbooru_request(tags)

    post = choose_gelbooru_post(posts)

    return {
        "url": post["file_url"],
        "source": "Gelbooru Games",
        "post_id": post.get("id")
    }


# =========================================================
# PINTEREST REQUEST
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
        "User-Agent": "AnimePoster/4.0"
    }

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=headers,
        params=params,
        timeout=25
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# PINTEREST BOARDS
# =========================================================

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


# =========================================================
# PINTEREST PINS
# =========================================================

def get_board_pins(board_id):

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


# =========================================================
# RANDOM PINTEREST
# =========================================================

def get_random_pinterest_pin():

    boards = get_pinterest_boards()

    if not boards:
        raise RuntimeError(
            "Pinterest не вернул досок"
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

                for image_data in images.values():

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

                    all_pins.append({
                        "url": image_url,
                        "source": "Pinterest",
                        "board_name": board_name,
                        "pin_id": pin.get("id")
                    })

        except Exception as error:

            print(
                f"Pinterest: ошибка доски "
                f"{board_name}: {error}"
            )

            continue

    if not all_pins:
        raise RuntimeError(
            "Pinterest не содержит изображений"
        )

    return random.choice(
        all_pins
    )


# =========================================================
# PEXELS
#
# Non-explicit adult/fashion content.
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:
        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

    queries = [
        "adult fashion portrait",
        "adult fashion model",
        "adult lifestyle portrait",
        "fashion model portrait",
        "elegant adult portrait",
        "adult glamour portrait"
    ]

    query = random.choice(
        queries
    )

    params = {
        "query": query,
        "per_page": 40,
        "orientation": "portrait"
    }

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/4.0"
    }

    response = requests.get(
        PEXELS_API,
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
            "Pexels не вернул фотографии"
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
        or src.get("portrait")
    )

    if not image_url:
        raise RuntimeError(
            "Pexels не вернул URL"
        )

    return {
        "url": image_url,
        "source": "Pexels",
        "photographer": photo.get(
            "photographer",
            "Unknown"
        ),
        "photo_url": photo.get(
            "url",
            "https://www.pexels.com/"
        )
    }


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=35
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg"
    ).lower()

    image_data = response.content

    if len(image_data) > 8 * 1024 * 1024:
        raise RuntimeError(
            "Изображение больше 8 MB"
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
# SEND TO DISCORD
# =========================================================

def send_to_discord(image):

    source = image.get(
        "source",
        "Unknown"
    )

    # -----------------------------------------------------
    # WEBHOOK
    # -----------------------------------------------------

    webhook_map = {
        "Waifu.im": DISCORD_WEBHOOK_WAIFU,
        "Gelbooru Anime": DISCORD_WEBHOOK_GELBOORU,
        "Gelbooru Games": DISCORD_WEBHOOK_GELBOORU_GAMES,
        "Pinterest": DISCORD_WEBHOOK_PINTEREST,
        "Pexels": DISCORD_WEBHOOK_PEXELS
    }

    webhook_url = webhook_map.get(
        source
    )

    if not webhook_url:
        raise RuntimeError(
            f"Webhook для {source} не настроен"
        )

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    if source == "Waifu.im":

        message = (
            "🌸 Random Anime NSFW\n"
            "📌 Источник: Waifu.im"
        )

    elif source == "Gelbooru Anime":

        post_id = image.get(
            "post_id"
        )

        message = (
            "🔥 Random Anime 18+\n"
            "📌 Источник: Gelbooru"
        )

        if post_id:
            message += (
                f"\n🆔 Post: {post_id}"
            )

    elif source == "Gelbooru Games":

        post_id = image.get(
            "post_id"
        )

        message = (
            "🎮 Random Game Art 18+\n"
            "📌 Источник: Gelbooru Games"
        )

        if post_id:
            message += (
                f"\n🆔 Post: {post_id}"
            )

    elif source == "Pinterest":

        board_name = image.get(
            "board_name",
            "Pinterest"
        )

        message = (
            "📌 Random Pinterest Art\n"
            f"📁 Доска: {board_name}"
        )

    elif source == "Pexels":

        photographer = image.get(
            "photographer",
            "Unknown"
        )

        photo_url = image.get(
            "photo_url",
            "https://www.pexels.com/"
        )

        message = (
            "📷 Random Adult "
            "Non-Explicit Art\n"
            "📌 Источник: Pexels\n"
            f"👤 Автор: {photographer}\n"
            f"🔗 {photo_url}"
        )

    else:

        raise RuntimeError(
            f"Неизвестный источник: {source}"
        )

    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    image_url = image.get(
        "url"
    )

    if not image_url:
        raise RuntimeError(
            "У изображения отсутствует URL"
        )

    filename, image_data, content_type = (
        download_image(
            image_url
        )
    )

    files = {
        "file": (
            filename,
            image_data,
            content_type
        )
    }

    # -----------------------------------------------------
    # DISCORD POST
    # -----------------------------------------------------

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
# SOURCE CONFIGURATION
# =========================================================

SOURCE_CONFIG = {
    "waifu": {
        "name": "Waifu.im",
        "webhook": lambda: DISCORD_WEBHOOK_WAIFU,
        "function": get_random_waifu
    },

    "gelbooru": {
        "name": "Gelbooru Anime",
        "webhook": lambda: DISCORD_WEBHOOK_GELBOORU,
        "function": get_random_gelbooru_anime
    },

    "gelbooru_games": {
        "name": "Gelbooru Games",
        "webhook": lambda: DISCORD_WEBHOOK_GELBOORU_GAMES,
        "function": get_random_gelbooru_games
    },

    "pinterest": {
        "name": "Pinterest",
        "webhook": lambda: DISCORD_WEBHOOK_PINTEREST,
        "function": get_random_pinterest_pin
    },

    "pexels": {
        "name": "Pexels",
        "webhook": lambda: DISCORD_WEBHOOK_PEXELS,
        "function": get_random_pexels
    }
}


# =========================================================
# SOURCE AVAILABILITY
# =========================================================

def is_source_available(source):

    config = SOURCE_CONFIG[source]

    if not config["webhook"]():
        return False

    if source == "pinterest":
        return bool(
            PINTEREST_ACCESS_TOKEN
        )

    if source in (
        "gelbooru",
        "gelbooru_games"
    ):
        return bool(
            GELBOORU_API_KEY
            and GELBOORU_USER_ID
        )

    if source == "pexels":
        return bool(
            PEXELS_API_KEY
        )

    return True


# =========================================================
# POST ONE SOURCE
# =========================================================

def post_source(source):

    config = SOURCE_CONFIG[
        source
    ]

    source_name = config["name"]

    print(
        f"[{source_name}] "
        "Начинаем публикацию..."
    )

    try:

        image = config["function"]()

        print(
            f"[{source_name}] "
            "Изображение получено"
        )

        send_to_discord(
            image
        )

        print(
            f"[{source_name}] "
            "Успешно опубликовано"
        )

        return {
            "source": source_name,
            "success": True,
            "error": None
        }

    except Exception as error:

        print(
            f"[{source_name}] "
            f"ОШИБКА: {error}"
        )

        return {
            "source": source_name,
            "success": False,
            "error": str(error)
        }


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

    available = []

    unavailable = []

    for source, config in SOURCE_CONFIG.items():

        if is_source_available(source):

            available.append(
                config["name"]
            )

        else:

            unavailable.append(
                config["name"]
            )

    text = (
        "Available sources:\n"
        + "\n".join(
            f"✓ {name}"
            for name in available
        )
    )

    if unavailable:

        text += (
            "\n\nUnavailable sources:\n"
            + "\n".join(
                f"✗ {name}"
                for name in unavailable
            )
        )

    return Response(
        text,
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# POST
#
# ВСЕ ДОСТУПНЫЕ ИСТОЧНИКИ ПУБЛИКУЮТСЯ
# ПАРАЛЛЕЛЬНО.
# =========================================================

@app.route("/post")
def post_image():

    available_sources = [
        source
        for source in SOURCE_CONFIG
        if is_source_available(source)
    ]

    if not available_sources:

        return Response(
            "No sources configured",
            status=500,
            mimetype="text/plain"
        )

    print(
        "================================================="
    )

    print(
        "POST: запускаем параллельную публикацию"
    )

    print(
        "POST: источники: "
        + ", ".join(
            SOURCE_CONFIG[source]["name"]
            for source in available_sources
        )
    )

    print(
        "================================================="
    )

    results = []

    # =====================================================
    # Каждый источник получает собственную задачу.
    #
    # max_workers=5 позволяет всем пяти источникам
    # работать одновременно.
    # =====================================================

    with ThreadPoolExecutor(
        max_workers=len(available_sources)
    ) as executor:

        futures = {
            executor.submit(
                post_source,
                source
            ): source

            for source in available_sources
        }

        for future in as_completed(
            futures
        ):

            source = futures[
                future
            ]

            try:

                result = future.result()

            except Exception as error:

                result = {
                    "source": SOURCE_CONFIG[
                        source
                    ]["name"],
                    "success": False,
                    "error": str(error)
                }

            results.append(
                result
            )

    # =====================================================
    # SUMMARY
    # =====================================================

    successful = [
        result
        for result in results
        if result["success"]
    ]

    failed = [
        result
        for result in results
        if not result["success"]
    ]

    print(
        "================================================="
    )

    print(
        "POST: публикация завершена"
    )

    print(
        f"POST: успешно: {len(successful)}"
    )

    print(
        f"POST: ошибок: {len(failed)}"
    )

    for result in failed:

        print(
            f"POST: {result['source']}: "
            f"{result['error']}"
        )

    print(
        "================================================="
    )

    # =====================================================
    # Если хотя бы один источник успешно отправил пост,
    # cron получает HTTP 200.
    #
    # Если абсолютно все источники упали — HTTP 502.
    # =====================================================

    if successful:

        return Response(
            f"OK: {len(successful)} "
            f"of {len(available_sources)} sources posted",
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
