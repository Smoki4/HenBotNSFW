import os
import random
import requests

from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

DISCORD_WEBHOOK_WAIFU = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

DISCORD_WEBHOOK_PINTEREST = os.environ.get(
    "DISCORD_WEBHOOK_PINTEREST"
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
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": "AnimePoster/2.0"
}

PEXELS_HEADERS = {
    "Authorization": PEXELS_API_KEY or "",
    "User-Agent": "AnimePoster/2.0"
}


# =========================================================
# WAIFU.IM
#
# Anime NSFW
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
# Anime NSFW / Questionable
#
# ВАЖНО:
# Используем только rating:questionable.
# Explicit здесь НЕ запрашивается.
# =========================================================

def get_random_gelbooru():

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",

        # Получаем пул результатов,
        # а случайный выбираем локально.
        "limit": "100",

        # Только Questionable.
        #
        # Дополнительно исключаем возрастные
        # категории/теги.
        "tags": (
            "rating:questionable "
            "-loli "
            "-lolicon "
            "-shota "
            "-shotacon "
            "-child "
            "-minor "
            "-young"
        )
    }

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
        timeout=25
    )

    response.raise_for_status()

    data = response.json()

    # -----------------------------------------------------
    # Gelbooru может вернуть:
    #
    # list
    # или
    # объект
    # -----------------------------------------------------

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

        if isinstance(
            posts,
            dict
        ):
            posts = [posts]

    else:

        posts = []

    if not posts:

        raise RuntimeError(
            "Gelbooru не вернул постов"
        )

    # -----------------------------------------------------
    # Дополнительная локальная фильтрация
    # -----------------------------------------------------

    forbidden_tokens = {
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

        file_url = post.get(
            "file_url"
        )

        if not file_url:
            continue

        post_tags = str(
            post.get(
                "tags",
                ""
            )
        ).lower()

        tag_set = set(
            post_tags.split()
        )

        if tag_set.intersection(
            forbidden_tokens
        ):
            continue

        # Если API вернул рейтинг поста,
        # проверяем его ещё раз.
        rating = str(
            post.get(
                "rating",
                ""
            )
        ).lower()

        if rating and rating != "questionable":
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

    return {
        "url": post.get(
            "file_url"
        ),
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

    headers = {
        "Authorization": (
            f"Bearer "
            f"{PINTEREST_ACCESS_TOKEN}"
        ),
        "Content-Type": "application/json",
        "User-Agent": "AnimePoster/2.0"
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

        items = data.get(
            "items",
            []
        )

        boards.extend(
            items
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
# PINTEREST BOARD PINS
# =========================================================

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

        items = data.get(
            "items",
            []
        )

        pins.extend(
            items
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
# RANDOM PINTEREST PIN
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

                # Ищем первый доступный URL.
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
                        "board_name": (
                            board_name
                        ),
                        "pin_id": pin.get(
                            "id"
                        )
                    })

        except Exception as error:

            print(
                f"Pinterest: ошибка "
                f"доски {board_name}: "
                f"{error}"
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
# PEXELS
#
# Real adult / non-explicit
#
# Только обычные fashion / portrait /
# lifestyle запросы.
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

    response = requests.get(
        PEXELS_API,
        headers=PEXELS_HEADERS,
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

def download_image(
    image_url
):

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

    # Discord webhook limit.
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
# DISCORD WEBHOOK
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
            DISCORD_WEBHOOK_WAIFU
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
            DISCORD_WEBHOOK_WAIFU
        )

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

    # -----------------------------------------------------
    # PINTEREST
    # -----------------------------------------------------

    elif source == "Pinterest":

        webhook_url = (
            DISCORD_WEBHOOK_PINTEREST
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
            DISCORD_WEBHOOK_PINTEREST
        )

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

    response = requests.post(
        webhook_url,
        data={
            "content": message
        },
        files=files,
        timeout=35
    )

    response.raise_for_status()


# =========================================================
# SOURCE DISPATCHER
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
        f"Unknown source: {source}"
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
# При наличии всех 4 источников:
#
# Waifu.im   = 25%
# Gelbooru   = 25%
# Pinterest  = 25%
# Pexels     = 25%
#
# ВАЖНО:
# random.choice() происходит ДО API-запроса.
# Поэтому рабочие источники действительно
# получают одинаковый первоначальный шанс.
# =========================================================

@app.route("/post")
def post_image():

    try:

        sources = []

        # -------------------------------------------------
        # WAIFU.IM
        # -------------------------------------------------

        if DISCORD_WEBHOOK_WAIFU:

            sources.append(
                "waifu"
            )

        # -------------------------------------------------
        # GELBOORU
        # -------------------------------------------------

        if (
            DISCORD_WEBHOOK_WAIFU
            and GELBOORU_API_KEY
            and GELBOORU_USER_ID
        ):

            sources.append(
                "gelbooru"
            )

        # -------------------------------------------------
        # PINTEREST
        # -------------------------------------------------

        if (
            DISCORD_WEBHOOK_PINTEREST
            and PINTEREST_ACCESS_TOKEN
        ):

            sources.append(
                "pinterest"
            )

        # -------------------------------------------------
        # PEXELS
        # -------------------------------------------------

        if (
            DISCORD_WEBHOOK_PINTEREST
            and PEXELS_API_KEY
        ):

            sources.append(
                "real_adult"
            )

        # -------------------------------------------------
        # НЕТ ИСТОЧНИКОВ
        # -------------------------------------------------

        if not sources:

            return Response(
                "No sources configured",
                status=500,
                mimetype="text/plain"
            )

        # -------------------------------------------------
        # РАВНЫЙ ВЫБОР
        # -------------------------------------------------

        selected_source = random.choice(
            sources
        )

        print(
            f"POST: выбран источник: "
            f"{selected_source}"
        )

        # -------------------------------------------------
        # FALLBACK
        #
        # Только если выбранный источник
        # не смог вернуть изображение.
        # -------------------------------------------------

        remaining_sources = [
            source
            for source in sources
            if source != selected_source
        ]

        random.shuffle(
            remaining_sources
        )

        attempt_order = (
            [selected_source]
            + remaining_sources
        )

        last_error = None

        # -------------------------------------------------
        # ATTEMPTS
        # -------------------------------------------------

        for source in attempt_order:

            try:

                print(
                    f"POST: пробуем {source}"
                )

                image = (
                    get_image_from_source(
                        source
                    )
                )

                print(
                    "POST: изображение получено "
                    f"из {image.get('source')}"
                )

                send_to_discord(
                    image
                )

                print(
                    "POST: успешно отправлено "
                    f"из {image.get('source')}"
                )

                return Response(
                    "OK",
                    status=200,
                    mimetype="text/plain"
                )

            except Exception as error:

                last_error = error

                print(
                    f"POST: {source} ошибка: "
                    f"{error}"
                )

                continue

        # -------------------------------------------------
        # ВСЕ ИСТОЧНИКИ FAILED
        # -------------------------------------------------

        print(
            "POST: все источники не сработали: "
            f"{last_error}"
        )

        return Response(
            "All sources failed",
            status=502,
            mimetype="text/plain"
        )

    # -----------------------------------------------------
    # TIMEOUT
    # -----------------------------------------------------

    except requests.exceptions.Timeout:

        print(
            "POST: timeout"
        )

        return Response(
            "Request timeout",
            status=504,
            mimetype="text/plain"
        )

    # -----------------------------------------------------
    # HTTP ERROR
    # -----------------------------------------------------

    except requests.exceptions.HTTPError as error:

        print(
            f"POST: HTTP error: {error}"
        )

        return Response(
            "HTTP request failed",
            status=502,
            mimetype="text/plain"
        )

    # -----------------------------------------------------
    # OTHER ERROR
    # -----------------------------------------------------

    except Exception as error:

        print(
            f"POST: error: {error}"
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
