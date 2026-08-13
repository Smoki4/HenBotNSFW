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
# API URL
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
# HTTP HEADERS
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


# =========================================================
# GELBOORU LOCK
#
# Anime и Games НЕ обращаются к Gelbooru одновременно.
# =========================================================

GELBOORU_LOCK = threading.Lock()


# =========================================================
# ОБЩАЯ ФУНКЦИЯ ОТПРАВКИ WEBHOOK
# =========================================================

def send_webhook(
    webhook_url,
    image_url,
    message,
    source_name
):

    if not webhook_url:

        raise RuntimeError(
            f"{source_name}: webhook не настроен"
        )

    if not image_url:

        raise RuntimeError(
            f"{source_name}: отсутствует URL изображения"
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
        timeout=40
    )

    response.raise_for_status()


# =========================================================
# СКАЧИВАНИЕ ИЗОБРАЖЕНИЯ
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=40
    )

    response.raise_for_status()

    image_data = response.content

    # Discord webhook
    # ограничиваем размер файла
    if len(image_data) > 8 * 1024 * 1024:

        raise RuntimeError(
            "Изображение больше 8 MB"
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


def post_waifu():

    print(
        "[Waifu.im] Получаем изображение..."
    )

    image = get_random_waifu()

    send_webhook(
        WAIFU_WEBHOOK_URL,
        image["url"],
        "🌸 Random Anime NSFW\n"
        "📌 Источник: Waifu.im",
        "Waifu.im"
    )

    print(
        "[Waifu.im] Успешно опубликовано"
    )


# =========================================================
# GELBOORU
# =========================================================

def get_gelbooru_image(
    tags,
    source_name,
    retries=4
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

        # Нам не нужно 100 картинок
        "limit": 20,

        "tags": tags,

        "api_key": GELBOORU_API_KEY,
        "user_id": GELBOORU_USER_ID
    }


    # =====================================================
    # Общая очередь для Gelbooru
    # =====================================================

    with GELBOORU_LOCK:

        # Небольшая пауза перед запросом
        # чтобы Anime и Games не били API подряд
        time.sleep(2)


        for attempt in range(
            retries
        ):

            try:

                print(
                    f"[{source_name}] "
                    f"Запрос Gelbooru "
                    f"(попытка {attempt + 1}/{retries})"
                )

                response = requests.get(
                    GELBOORU_API,
                    params=params,
                    headers=HEADERS,
                    timeout=30
                )


                # =================================================
                # RATE LIMIT
                # =================================================

                if response.status_code == 429:

                    retry_after = (
                        response.headers.get(
                            "Retry-After"
                        )
                    )

                    if retry_after:

                        try:
                            wait_seconds = float(
                                retry_after
                            )
                        except ValueError:
                            wait_seconds = (
                                5 * (attempt + 1)
                            )

                    else:

                        # Экспоненциальная задержка
                        wait_seconds = (
                            5 * (2 ** attempt)
                        )


                    # Ограничиваем ожидание
                    wait_seconds = min(
                        wait_seconds,
                        60
                    )

                    print(
                        f"[{source_name}] "
                        f"Gelbooru вернул 429. "
                        f"Ждём {wait_seconds:.1f} сек."
                    )

                    time.sleep(
                        wait_seconds
                    )

                    continue


                response.raise_for_status()


                data = response.json()


                # =================================================
                # Gelbooru иногда может вернуть объект ошибки
                # =================================================

                if isinstance(
                    data,
                    dict
                ):

                    if data.get(
                        "success"
                    ) is False:

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


                # =================================================
                # Выбираем случайный пост
                # =================================================

                random.shuffle(
                    posts
                )


                for post in posts:

                    image_url = (
                        post.get("file_url")
                    )

                    if not image_url:

                        image_url = (
                            post.get("sample_url")
                        )

                    if not image_url:
                        continue


                    return {
                        "url": image_url,
                        "source": source_name,
                        "post_id": post.get("id"),
                        "rating": post.get("rating")
                    }


                raise RuntimeError(
                    f"{source_name}: "
                    "у постов нет URL изображения"
                )


            except requests.exceptions.HTTPError:

                # 429 уже обработан выше
                if (
                    response.status_code
                    == 429
                ):
                    continue

                raise


        raise RuntimeError(
            f"{source_name}: "
            "Gelbooru продолжает возвращать 429 "
            f"после {retries} попыток"
        )


# =========================================================
# GELBOORU ANIME
# =========================================================

def get_gelbooru_anime():

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

    return get_gelbooru_image(
        tags,
        "Gelbooru Anime"
    )


def post_gelbooru_anime():

    print(
        "[Gelbooru Anime] "
        "Получаем изображение..."
    )

    image = get_gelbooru_anime()

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

    send_webhook(
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

def get_gelbooru_games():

    # Более широкий игровой поиск.
    #
    # Gelbooru поддерживает группировку
    # альтернативных тегов через { }.
    #
    # Например:
    # video_game ИЛИ game_character
    #

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

    return get_gelbooru_image(
        tags,
        "Gelbooru Games"
    )


def post_gelbooru_games():

    print(
        "[Gelbooru Games] "
        "Получаем изображение..."
    )

    image = get_gelbooru_games()

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

    send_webhook(
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
        "Content-Type": "application/json",
        "User-Agent": "AnimePoster/1.0"
    }

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=headers,
        params=params,
        timeout=30
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

                if images:

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
                        "pin_id": pin.get("id")
                    })


        except Exception as error:

            print(
                f"[Pinterest] "
                f"Ошибка доски "
                f"{board_name}: {error}"
            )

            continue


    if not all_pins:

        raise RuntimeError(
            "Pinterest: "
            "изображения не найдены"
        )

    return random.choice(
        all_pins
    )


def post_pinterest():

    print(
        "[Pinterest] "
        "Получаем изображение..."
    )

    image = get_random_pinterest_pin()

    board_name = image.get(
        "board_name",
        "Pinterest"
    )

    message = (
        "📌 Random Pinterest Art\n"
        f"📁 Доска: {board_name}"
    )

    send_webhook(
        PINTEREST_WEBHOOK_URL,
        image["url"],
        message,
        "Pinterest"
    )

    print(
        "[Pinterest] "
        "Успешно опубликовано"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "AnimePoster/1.0"
    }


    # Pexels не является NSFW API.
    # Здесь ищем обычные adult/anime-style
    # фотографии/арт без explicit-фильтра.
    queries = [
        "adult woman",
        "beautiful woman",
        "fashion woman",
        "portrait woman",
        "model woman"
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
        "source": "Pexels"
    }


def post_pexels():

    print(
        "[Pexels] "
        "Получаем изображение..."
    )

    image = get_random_pexels()

    send_webhook(
        PEXELS_WEBHOOK_URL,
        image["url"],
        "📷 Random IRL Art\n"
        "📌 Источник: Pexels",
        "Pexels"
    )

    print(
        "[Pexels] "
        "Успешно опубликовано"
    )


# =========================================================
# ПРОВЕРКА ИСТОЧНИКОВ
# =========================================================

def get_source_status():

    status = {}

    status["Waifu.im"] = bool(
        WAIFU_WEBHOOK_URL
    )

    status["Gelbooru Anime"] = bool(
        GELBOORU_API_KEY
        and GELBOORU_USER_ID
        and GELBOORU_WEBHOOK_URL
    )

    status["Gelbooru Games"] = bool(
        GELBOORU_API_KEY
        and GELBOORU_USER_ID
        and GELBOORU_GAMES_WEBHOOK_URL
    )

    status["Pinterest"] = bool(
        PINTEREST_ACCESS_TOKEN
        and PINTEREST_WEBHOOK_URL
    )

    status["Pexels"] = bool(
        PEXELS_API_KEY
        and PEXELS_WEBHOOK_URL
    )

    return status


# =========================================================
# ГЛАВНАЯ
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

    source_status = (
        get_source_status()
    )

    lines = [
        "Anime Poster status:",
        ""
    ]

    for name, available in (
        source_status.items()
    ):

        if available:

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
# POST
#
# Все доступные источники публикуются.
#
# Waifu
# Gelbooru Anime
# Gelbooru Games
# Pinterest
# Pexels
#
# Каждый источник имеет отдельный webhook.
# =========================================================

@app.route("/post")
def post_image():

    print("")
    print("=" * 55)
    print(
        "POST: запуск публикации"
    )
    print("=" * 55)


    jobs = []


    # =====================================================
    # WAIFU
    # =====================================================

    if (
        WAIFU_WEBHOOK_URL
    ):

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


    results = []

    errors = []


    # =====================================================
    # ПОСЛЕДОВАТЕЛЬНО
    #
    # ВАЖНО:
    #
    # Gelbooru имеет собственный lock,
    # поэтому даже если позже мы сделаем
    # threading для остальных источников,
    # Anime и Games не будут обращаться
    # к Gelbooru одновременно.
    #
    # =====================================================

    for source_name, function in jobs:

        try:

            function()

            results.append(
                source_name
            )

        except Exception as error:

            error_text = str(
                error
            )

            errors.append(
                (
                    source_name,
                    error_text
                )
            )

            print(
                f"[{source_name}] "
                f"ОШИБКА: {error_text}"
            )


    # =====================================================
    # ИТОГ
    # =====================================================

    print(
        "=" * 55
    )

    print(
        "POST: публикация завершена"
    )

    print(
        f"POST: успешно: {len(results)}"
    )

    print(
        f"POST: ошибок: {len(errors)}"
    )


    for source_name, error in errors:

        print(
            f"POST: {source_name}: {error}"
        )


    print(
        "=" * 55
    )


    # Если хотя бы один источник сработал —
    # возвращаем 200.
    #
    # Это удобно для cron-job.org:
    # один временно недоступный API
    # не делает весь запуск failed.

    if results:

        return Response(
            (
                f"OK - successful: "
                f"{len(results)}, "
                f"errors: {len(errors)}"
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
# ЗАПУСК
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
