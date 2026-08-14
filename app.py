import os
import random
import threading
import time
import json
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

# Reactor:
# случайные страницы будут иметь вид:
# /tag/Игровая+эротика/new/1
# /tag/Игровая+эротика/new/2
# /tag/Игровая+эротика/new/3
# и т.д.

REACTOR_TAG_URL = (
    "https://reactor.cc/tag/"
    "Игровая+эротика"
)

REACTOR_MAX_PAGE = 500


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "AnimePoster/1.0 "
        "(Discord image poster)"
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
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en;q=0.8"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# =========================================================
# REACTOR HISTORY
# =========================================================

REACTOR_HISTORY_FILE = "reactor_seen.json"

REACTOR_LOCK = threading.Lock()

REACTOR_SEEN = set()

MAX_REACTOR_HISTORY = 5000


def load_reactor_history():

    global REACTOR_SEEN

    try:

        if not os.path.exists(
            REACTOR_HISTORY_FILE
        ):
            return

        with open(
            REACTOR_HISTORY_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(data, list):

            REACTOR_SEEN = set(
                str(item)
                for item in data
                if item
            )

        print(
            "[Reactor] "
            f"Загружено из истории: "
            f"{len(REACTOR_SEEN)}"
        )

    except Exception as error:

        print(
            "[Reactor] "
            f"Не удалось загрузить историю: "
            f"{error}"
        )

        REACTOR_SEEN = set()


def save_reactor_history():

    try:

        data = list(
            REACTOR_SEEN
        )

        if len(data) > MAX_REACTOR_HISTORY:

            data = data[
                -MAX_REACTOR_HISTORY:
            ]

        temp_file = (
            REACTOR_HISTORY_FILE
            + ".tmp"
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_file,
            REACTOR_HISTORY_FILE,
        )

    except Exception as error:

        print(
            "[Reactor] "
            f"Не удалось сохранить историю: "
            f"{error}"
        )


def reactor_was_used(url):

    with REACTOR_LOCK:

        return url in REACTOR_SEEN


def reactor_mark_used(url):

    with REACTOR_LOCK:

        REACTOR_SEEN.add(url)

        # Обрезаем историю, если она стала
        # слишком большой.
        if len(REACTOR_SEEN) > (
            MAX_REACTOR_HISTORY + 500
        ):

            items = list(
                REACTOR_SEEN
            )

            REACTOR_SEEN.clear()

            REACTOR_SEEN.update(
                items[
                    -MAX_REACTOR_HISTORY:
                ]
            )

        save_reactor_history()


# Загружаем историю при запуске приложения.
load_reactor_history()


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
                f"Ожидание "
                f"{wait_time:.1f} сек."
            )

            time.sleep(
                wait_time
            )

        LAST_DANBOORU_REQUEST = (
            time.monotonic()
        )


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu():

    print(
        "[Waifu.im] "
        "Получаем изображение..."
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
            "DANBOORU_USERNAME "
            "не настроен"
        )

    if not DANBOORU_API_KEY:

        raise RuntimeError(
            "DANBOORU_API_KEY "
            "не настроен"
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

        body = response.text[:1500]

        print(
            f"[{source_name}] "
            f"Danbooru 422: "
            f"{body}"
        )

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 422"
        )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            f"{source_name}: "
            "неожиданный ответ "
            "Danbooru"
        )

    images = []

    for post in data:

        image_url = (
            post.get(
                "large_file_url"
            )
            or post.get(
                "file_url"
            )
        )

        if not image_url:
            continue

        images.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post.get(
                    "id"
                ),
            }
        )

    if not images:

        raise RuntimeError(
            f"{source_name}: "
            "изображения "
            "не найдены"
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
# REACTOR HELPERS
# =========================================================

def reactor_page_url(page):

    if page <= 1:

        return (
            REACTOR_TAG_URL
            + "/new"
        )

    return (
        REACTOR_TAG_URL
        + "/new/"
        + str(page)
    )


def extract_reactor_images(
    html,
    page_url,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    # -----------------------------------------------------
    # 1. img
    # -----------------------------------------------------

    for img in soup.find_all(
        "img"
    ):

        possible_urls = [
            img.get(
                "data-src"
            ),
            img.get(
                "data-original"
            ),
            img.get(
                "data-lazy-src"
            ),
            img.get(
                "src"
            ),
        ]

        for src in possible_urls:

            if not src:
                continue

            src = src.strip()

            if not src:
                continue

            src = urljoin(
                page_url,
                src,
            )

            lowered = src.lower()

            if not lowered.startswith(
                (
                    "http://",
                    "https://",
                )
            ):
                continue

            # Не берём аватарки,
            # логотипы и интерфейс.
            if any(
                value in lowered
                for value in (
                    "avatar",
                    "/static/",
                    "/emoji/",
                    "/icon/",
                    "/logo/",
                    "favicon",
                )
            ):

                continue

            # Reactor CDN.
            if (
                "/pics/post/"
                not in lowered
            ):
                continue

            candidates.append(
                src
            )

    # -----------------------------------------------------
    # 2. Ссылки на изображения
    # -----------------------------------------------------

    for link in soup.find_all(
        "a"
    ):

        href = link.get(
            "href"
        )

        if not href:
            continue

        href = urljoin(
            page_url,
            href,
        )

        lowered = href.lower()

        if (
            "/pics/post/"
            not in lowered
        ):
            continue

        if any(
            value in lowered
            for value in (
                "avatar",
                "/static/",
                "/emoji/",
                "/icon/",
                "/logo/",
            )
        ):

            continue

        candidates.append(
            href
        )

    # -----------------------------------------------------
    # Удаляем дубли
    # -----------------------------------------------------

    unique = []

    seen = set()

    for url in candidates:

        # Убираем query-параметры
        # для сравнения.
        clean_url = url.split(
            "?",
            1
        )[0]

        if clean_url in seen:
            continue

        seen.add(
            clean_url
        )

        unique.append(
            clean_url
        )

    return unique


def check_reactor_image(
    image_url,
):

    try:

        response = requests.get(
            image_url,
            headers={
                "User-Agent":
                    REACTOR_HEADERS[
                        "User-Agent"
                    ],
                "Accept":
                    "image/avif,image/webp,"
                    "image/apng,image/*,"
                    "*/*;q=0.8",
            },
            timeout=20,
            stream=True,
        )

        status = (
            response.status_code
        )

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            ).lower()
        )

        response.close()

        if status != 200:
            return False

        if (
            content_type.startswith(
                "image/"
            )
        ):
            return True

        lowered = image_url.lower()

        return lowered.endswith(
            (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        )

    except requests.RequestException:

        return False


# =========================================================
# REACTOR GAMES
# =========================================================

def get_reactor_games():

    print(
        "[Reactor Games] "
        "Ищем новую страницу..."
    )

    # Берём несколько случайных страниц.
    pages = list(
        range(
            1,
            REACTOR_MAX_PAGE + 1,
        )
    )

    random.shuffle(
        pages
    )

    # Проверяем до 8 страниц за один запуск.
    pages_to_try = pages[:8]

    for page in pages_to_try:

        page_url = reactor_page_url(
            page
        )

        print(
            "[Reactor Games] "
            f"Страница: {page_url}"
        )

        try:

            response = requests.get(
                page_url,
                headers=REACTOR_HEADERS,
                timeout=30,
            )

            print(
                "[Reactor Games] "
                f"HTTP: "
                f"{response.status_code}"
            )

            if response.status_code != 200:

                continue

            candidates = (
                extract_reactor_images(
                    response.text,
                    page_url,
                )
            )

            print(
                "[Reactor Games] "
                f"Страница {page}: "
                f"найдено "
                f"{len(candidates)} "
                f"кандидатов"
            )

            if not candidates:

                continue

            # -------------------------------------------------
            # Сначала только новые изображения.
            # -------------------------------------------------

            unused = [
                url
                for url in candidates
                if not reactor_was_used(
                    url
                )
            ]

            print(
                "[Reactor Games] "
                f"Новых: "
                f"{len(unused)}"
            )

            if not unused:

                continue

            random.shuffle(
                unused
            )

            # -------------------------------------------------
            # Проверяем несколько кандидатов.
            # -------------------------------------------------

            for image_url in unused[:20]:

                print(
                    "[Reactor Games] "
                    "Проверяем: "
                    f"{image_url}"
                )

                if not check_reactor_image(
                    image_url
                ):
                    continue

                print(
                    "[Reactor Games] "
                    "Выбрано новое "
                    "изображение"
                )

                return {
                    "url": image_url,
                    "source":
                        "Reactor Games",
                }

        except requests.RequestException as error:

            print(
                "[Reactor Games] "
                f"Ошибка страницы: "
                f"{error}"
            )

        except Exception as error:

            print(
                "[Reactor Games] "
                f"Ошибка парсинга: "
                f"{error}"
            )

    # -----------------------------------------------------
    # Если все случайные страницы уже просмотрены,
    # сообщаем об этом вместо повторной картинки.
    # -----------------------------------------------------

    raise RuntimeError(
        "Reactor: "
        "не найдено новое изображение "
        "на проверенных страницах"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY "
            "не настроен"
        )

    print(
        "[Pexels] "
        "Получаем изображение..."
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
                "page": random.randint(
                    1,
                    5,
                ),
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
                src.get(
                    "large2x"
                )
                or src.get(
                    "large"
                )
                or src.get(
                    "original"
                )
            )

            if image_url:

                return {
                    "url": image_url,
                    "source": "Pexels",
                }

    raise RuntimeError(
        "Pexels "
        "не вернул изображения"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(
    image_url,
):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    content = response.content

    if len(content) > (
        8 * 1024 * 1024
    ):

        raise RuntimeError(
            "Изображение "
            "больше 8 MB"
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
    image,
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

        # ВАЖНО:
        # отмечаем Reactor как использованный
        # только после успешной отправки
        # в Discord.

        if (
            name
            == "Reactor Games"
        ):

            reactor_mark_used(
                image["url"]
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

        "reactor": {
            "tag": (
                "Игровая эротика"
            ),
            "max_page":
                REACTOR_MAX_PAGE,
            "seen":
                len(REACTOR_SEEN),
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
