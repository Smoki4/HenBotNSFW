import os
import random
import requests

from flask import Flask, Response

app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

PINTEREST_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PINTEREST"
)

PINTEREST_ACCESS_TOKEN = os.environ.get(
    "PINTEREST_ACCESS_TOKEN"
)

PEXELS_API_KEY = os.environ.get(
    "PEXELS_API_KEY"
)

# Gelbooru
GELBOORU_API_KEY = os.environ.get(
    "GELBOORU_API_KEY"
)

GELBOORU_USER_ID = os.environ.get(
    "GELBOORU_USER_ID"
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
    "https://api.pexels.com/v1/search"
)


# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "AnimePoster/1.0"
}

PINTEREST_HEADERS = {
    "Authorization": (
        f"Bearer {PINTEREST_ACCESS_TOKEN}"
    ),
    "Content-Type": "application/json",
    "User-Agent": "AnimePoster/1.0"
}

PEXELS_HEADERS = {
    "Authorization": PEXELS_API_KEY,
    "User-Agent": "AnimePoster/1.0"
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
# GELBOORU
#
# Anime NSFW 18+
# Используем rating:questionable
#
# Исключаем нежелательные возрастные теги.
# =========================================================

def get_random_gelbooru():

    tags = (
        "rating:questionable "
        "-loli "
        "-shota "
        "-lolicon "
        "-shotacon "
        "-child "
        "-young "
        "sort:random"
    )

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "limit": "100",
        "tags": tags
    }

    # Если Gelbooru выдал API credentials,
    # добавляем их к запросу.
    if GELBOORU_API_KEY:
        params["api_key"] = (
            GELBOORU_API_KEY
        )

    if GELBOORU_USER_ID:
        params["user_id"] = (
            GELBOORU_USER_ID
        )

    response = requests.get(
        GELBOORU_API,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    # Gelbooru может вернуть список
    # либо объект с ошибкой.
    if isinstance(data, dict):

        if data.get("success") is False:

            message = data.get(
                "message",
                "Gelbooru API error"
            )

            raise RuntimeError(
                message
            )

        posts = data.get(
            "post",
            []
        )

        if isinstance(
            posts,
            dict
        ):
            posts = [posts]

    elif isinstance(data, list):

        posts = data

    else:

        posts = []

    if not posts:

        raise RuntimeError(
            "Gelbooru не вернул изображений"
        )

    # Дополнительная фильтрация
    # непосредственно перед выбором.
    valid_posts = []

    for post in posts:

        file_url = post.get(
            "file_url"
        )

        if not file_url:
            continue

        tags = post.get(
            "tags",
            ""
        ).lower()

        # Дополнительная защита
        forbidden = [
            "loli",
            "shota",
            "lolicon",
            "shotacon",
            "child",
            "young"
        ]

        if any(
            tag in tags
            for tag in forbidden
        ):
            continue

        valid_posts.append(
            post
        )

    if not valid_posts:

        raise RuntimeError(
            "Gelbooru не нашёл "
            "подходящих изображений"
        )

    post = random.choice(
        valid_posts
    )

    image_url = post.get(
        "file_url"
    )

    return {
        "url": image_url,
        "source": "Gelbooru",
        "post_id": post.get(
            "id"
        )
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

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=PINTEREST_HEADERS,
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
                        "pin_id": pin.get(
                            "id"
                        )
                    })

        except Exception as error:

            print(
                f"Pinterest board "
                f"{board_name}: {error}"
            )

            continue

    if not all_pins:

        raise RuntimeError(
            "Pinterest не содержит "
            "доступных изображений"
        )

    return random.choice(
        all_pins
    )


# =========================================================
# REAL ADULT NON-EXPLICIT
# =========================================================

def get_random_real_adult():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

    queries = [
        "adult fashion portrait",
        "adult fashion model",
        "adult lifestyle portrait",
        "adult glamour portrait",
        "fashion model portrait",
        "elegant adult portrait"
    ]

    query = random.choice(
        queries
    )

    params = {
        "query": query,
        "per_page": 20,
        "orientation": "portrait"
    }

    response = requests.get(
        PEXELS_API,
        headers=PEXELS_HEADERS,
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
        )
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
        timeout=30
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg"
    )

    image_data = response.content

    if len(image_data) > (
        8 * 1024 * 1024
    ):

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
# DISCORD
# =========================================================

def send_to_discord(
    image
):

    source = image.get(
        "source",
        "Unknown"
    )

    # -----------------------------------------------------
    # WAIFU.IM
    # -----------------------------------------------------

    if source == "Waifu.im":

        webhook_url = (
            WAIFU_WEBHOOK_URL
        )

        message = (
            "🌸 Random Anime NSFW\n"
            "📌 Источник: Waifu.im"
        )

    # -----------------------------------------------------
    # GELBOORU
    # -----------------------------------------------------

    elif source == "Gelbooru":

        webhook_url = (
            WAIFU_WEBHOOK_URL
        )

        message = (
            "🔥 Random Anime 18+\n"
            "📌 Источник: Gelbooru"
        )

    # -----------------------------------------------------
    # PINTEREST
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # PEXELS
    # -----------------------------------------------------

    elif source == "Pexels":

        webhook_url = (
            PINTEREST_WEBHOOK_URL
        )

        photographer = image.get(
            "photographer",
            "Unknown"
        )

        message = (
            "📷 Random Adult Art\n"
            "📌 Источник: Pexels\n"
            f"👤 Автор: {photographer}"
        )

    else:

        raise RuntimeError(
            "Неизвестный источник"
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
# GET IMAGE
# =========================================================

def get_image_from_source(
    source
):

    if source == "waifu":

        return get_random_waifu()

    if source == "gelbooru":

        return get_random_gelbooru()

    if source == "pinterest":

        return get_random_pinterest_pin()

    if source == "real_adult":

        return get_random_real_adult()

    raise RuntimeError(
        f"Неизвестный source: {source}"
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
# POST
#
# 25% Waifu.im
# 25% Gelbooru
# 25% Pinterest
# 25% Pexels
# =========================================================

@app.route("/post")
def post_image():

    try:

        sources = []

        # -----------------------------
        # Waifu.im
        # -----------------------------

        if WAIFU_WEBHOOK_URL:

            sources.append(
                "waifu"
            )

        # -----------------------------
        # Gelbooru
        # -----------------------------

        if WAIFU_WEBHOOK_URL:

            sources.append(
                "gelbooru"
            )

        # -----------------------------
        # Pinterest
        # -----------------------------

        if (
            PINTEREST_WEBHOOK_URL
            and PINTEREST_ACCESS_TOKEN
        ):

            sources.append(
                "pinterest"
            )

        # -----------------------------
        # Real adult
        # -----------------------------

        if (
            PINTEREST_WEBHOOK_URL
            and PEXELS_API_KEY
        ):

            sources.append(
                "real_adult"
            )

        if not sources:

            return Response(
                "No sources configured",
                status=500,
                mimetype="text/plain"
            )

        # =================================================
        # РАВНЫЙ ШАНС
        # =================================================

        selected_source = random.choice(
            sources
        )

        print(
            "POST: выбран:",
            selected_source
        )

        # =================================================
        # FALLBACK
        # =================================================

        fallback_sources = [
            source
            for source in sources
            if source != selected_source
        ]

        random.shuffle(
            fallback_sources
        )

        attempt_order = [
            selected_source
        ] + fallback_sources

        last_error = None

        for source in attempt_order:

            try:

                print(
                    "POST: пробуем:",
                    source
                )

                image = (
                    get_image_from_source(
                        source
                    )
                )

                print(
                    "POST: найдено:",
                    image.get(
                        "source"
                    )
                )

                send_to_discord(
                    image
                )

                print(
                    "POST: успешно отправлено"
                )

                return Response(
                    "OK",
                    status=200,
                    mimetype="text/plain"
                )

            except Exception as error:

                last_error = error

                print(
                    f"POST: ошибка "
                    f"{source}: {error}"
                )

                continue

        print(
            "POST: все источники "
            f"не сработали: {last_error}"
        )

        return Response(
            "All sources failed",
            status=502,
            mimetype="text/plain"
        )

    except requests.exceptions.Timeout:

        return Response(
            "Request timeout",
            status=504,
            mimetype="text/plain"
        )

    except requests.exceptions.HTTPError as error:

        print(
            "POST HTTP error:",
            error
        )

        return Response(
            "HTTP request failed",
            status=502,
            mimetype="text/plain"
        )

    except Exception as error:

        print(
            "POST error:",
            error
        )

        return Response(
            "Internal error",
            status=500,
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
