import os
import random
import threading
import time

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

DANBOORU_USERNAME = os.environ.get(
    "DANBOORU_USERNAME"
)

DANBOORU_API_KEY = os.environ.get(
    "DANBOORU_API_KEY"
)


# =========================================================
# SETTINGS
# =========================================================

# Discord
DISCORD_MAX_RETRIES = 6
DISCORD_SEND_DELAY = 3.0

# Максимальный размер скачиваемого изображения.
# Если Discord у твоего аккаунта принимает меньше,
# уменьши это значение.
MAX_IMAGE_SIZE = 19 * 1024 * 1024

# Отправлять изображения спойлером.
DISCORD_SPOILER = True

# Сколько ID помнить для защиты от повторов.
MAX_MEMORY = 3000


# =========================================================
# API
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)

WAIFU_API = (
    "https://api.waifu.im/images"
)


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; GamePoster/2.0)"
    )
}

DANBOORU_HEADERS = {
    "User-Agent": (
        "GamePoster/2.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


# =========================================================
# MEMORY
# =========================================================

DANBOORU_USED_IDS = set()

DANBOORU_MEMORY_LOCK = threading.Lock()


def remember_id(post_id):
    if post_id is None:
        return

    post_id = str(post_id)

    with DANBOORU_MEMORY_LOCK:
        DANBOORU_USED_IDS.add(post_id)

        while len(DANBOORU_USED_IDS) > MAX_MEMORY:
            old_id = random.choice(
                list(DANBOORU_USED_IDS)
            )
            DANBOORU_USED_IDS.discard(old_id)


def was_used(post_id):
    if post_id is None:
        return False

    with DANBOORU_MEMORY_LOCK:
        return str(post_id) in DANBOORU_USED_IDS


# =========================================================
# DANBOORU RATE LIMIT
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

        wait_time = 1.5 - elapsed

        if wait_time > 0:
            time.sleep(wait_time)

        LAST_DANBOORU_REQUEST = (
            time.monotonic()
        )


# =========================================================
# DISCORD SERIALIZATION
# =========================================================

DISCORD_LOCK = threading.Lock()

LAST_DISCORD_SEND = 0.0


def discord_wait():
    global LAST_DISCORD_SEND

    with DISCORD_LOCK:
        now = time.monotonic()

        elapsed = (
            now - LAST_DISCORD_SEND
        )

        wait_time = (
            DISCORD_SEND_DELAY - elapsed
        )

        if wait_time > 0:
            time.sleep(wait_time)

        LAST_DISCORD_SEND = (
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

    for attempt in range(5):

        try:

            response = requests.get(
                WAIFU_API,
                params={
                    "OrderBy": "Random",
                    "PageSize": 1,
                },
                headers=DEFAULT_HEADERS,
                timeout=30,
            )

            print(
                "[Waifu.im] HTTP: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            items = data.get(
                "items",
                []
            )

            if not items:
                continue

            item = items[0]

            image_url = item.get(
                "url"
            )

            if not image_url:
                continue

            return {
                "url": image_url,
                "source": "Waifu.im",
                "tags": [],
            }

        except Exception as error:

            print(
                "[Waifu.im] "
                f"Попытка {attempt + 1}: "
                f"{error}"
            )

            time.sleep(2)

    raise RuntimeError(
        "Waifu.im: "
        "не удалось получить изображение"
    )


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(
    tags,
    source_name
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
            "limit": 100,
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
        f"[{source_name}] HTTP: "
        f"{response.status_code}"
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"{source_name}: "
            "некорректный ответ API"
        )

    candidates = []

    for post in data:

        post_id = post.get("id")

        if was_used(post_id):
            continue

        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        # Берём только изображения.
        lowered = image_url.lower()

        if not any(
            ext in lowered
            for ext in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        ):
            continue

        candidates.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post_id,
                "tags": post.get(
                    "tag_string",
                    ""
                ),
            }
        )

    if not candidates:
        raise RuntimeError(
            f"{source_name}: "
            "новых изображений не найдено"
        )

    selected = random.choice(
        candidates
    )

    remember_id(
        selected.get("post_id")
    )

    print(
        f"[{source_name}] "
        "Новый SAFE пост найден"
    )

    return selected


# =========================================================
# DANBOORU ANIME
# =========================================================

DANBOORU_ANIME_TAGS = [

    "rating:safe anime",

    "rating:safe 1girl",

    "rating:safe 1boy",

    "rating:safe solo",

    "rating:safe 2girls",

    "rating:safe scenery",

    "rating:safe landscape",

    "rating:safe fantasy",

    "rating:safe school_uniform",

    "rating:safe animal_ears",

    "rating:safe furry",

    "rating:safe vocaloid",

    "rating:safe hatsune_miku",

    "rating:safe megurine_luka",

    "rating:safe naruto",

    "rating:safe one_piece",

    "rating:safe bleach",

    "rating:safe re_zero",

    "rating:safe konosuba",

    "rating:safe genshin_impact",

    "rating:safe honkai_star_rail",

    "rating:safe zenless_zone_zero",

    "rating:safe pokemon",

    "rating:safe persona",

    "rating:safe final_fantasy",

    "rating:safe cyberpunk_2077",

    "rating:safe minecraft",

]


def get_danbooru_anime():

    tags = random.choice(
        DANBOORU_ANIME_TAGS
    )

    return get_random_danbooru(
        tags,
        "Danbooru Anime",
    )


# =========================================================
# DANBOORU GAMES
# =========================================================

DANBOORU_GAME_TAGS = [

    "rating:safe genshin_impact",

    "rating:safe honkai_star_rail",

    "rating:safe zenless_zone_zero",

    "rating:safe minecraft",

    "rating:safe apex_legends",

    "rating:safe overwatch",

    "rating:safe fortnite",

    "rating:safe pokemon",

    "rating:safe persona_5",

    "rating:safe cyberpunk_2077",

    "rating:safe resident_evil",

    "rating:safe nier_automata",

    "rating:safe devil_may_cry",

    "rating:safe final_fantasy",

    "rating:safe the_witcher",

    "rating:safe elden_ring",

    "rating:safe dark_souls",

    "rating:safe mortal_kombat",

    "rating:safe street_fighter",

    "rating:safe tekken",

    "rating:safe guilty_gear",

    "rating:safe skullgirls",

    "rating:safe arknights",

    "rating:safe wuthering_waves",

    "rating:safe dead_by_daylight",

    "rating:safe dota_2",

    "rating:safe pubg",

    "rating:safe team_fortress_2",

    "rating:safe fallout",

    "rating:safe warhammer_40k",

]


def get_danbooru_games():

    tags = random.choice(
        DANBOORU_GAME_TAGS
    )

    return get_random_danbooru(
        tags,
        "Danbooru Games",
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=60,
        stream=True,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg",
    )

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:

        try:

            if (
                int(content_length)
                > MAX_IMAGE_SIZE
            ):

                response.close()

                raise RuntimeError(
                    "Изображение больше "
                    f"{MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB"
                )

        except ValueError:
            pass

    chunks = []

    total = 0

    try:

        for chunk in response.iter_content(
            chunk_size=64 * 1024
        ):

            if not chunk:
                continue

            total += len(chunk)

            if total > MAX_IMAGE_SIZE:

                raise RuntimeError(
                    "Изображение больше "
                    f"{MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB"
                )

            chunks.append(chunk)

    finally:

        response.close()

    image_data = b"".join(chunks)

    content_type_lower = (
        content_type.lower()
    )

    if "png" in content_type_lower:
        extension = "png"

    elif "webp" in content_type_lower:
        extension = "webp"

    elif "gif" in content_type_lower:
        extension = "gif"

    else:
        extension = "jpg"

    filename = (
        "SPOILER_image."
        if DISCORD_SPOILER
        else "image."
    )

    filename += extension

    return (
        filename,
        image_data,
        content_type,
    )


# =========================================================
# DISCORD RETRY
# =========================================================

def get_retry_delay(
    response,
    attempt
):

    retry_after = response.headers.get(
        "Retry-After"
    )

    if retry_after:

        try:
            return max(
                float(retry_after),
                1.0,
            )
        except ValueError:
            pass

    # Если Cloudflare отдаёт HTML
    # без Retry-After.
    return min(
        5.0 * (2 ** attempt),
        60.0,
    )


def discord_request(
    webhook_url,
    data,
    files
):

    for attempt in range(
        DISCORD_MAX_RETRIES
    ):

        discord_wait()

        try:

            response = requests.post(
                webhook_url,
                data=data,
                files=files,
                timeout=90,
            )

        except requests.RequestException as error:

            if attempt >= (
                DISCORD_MAX_RETRIES - 1
            ):
                raise

            wait_time = min(
                5.0 * (2 ** attempt),
                60.0,
            )

            print(
                "[Discord] Сетевая ошибка: "
                f"{error}"
            )

            print(
                "[Discord] Повтор через "
                f"{wait_time:.1f} сек."
            )

            time.sleep(wait_time)

            continue

        print(
            "[Discord] HTTP: "
            f"{response.status_code}"
        )

        if response.status_code in (
            200,
            204,
        ):
            return response

        if response.status_code == 429:

            wait_time = get_retry_delay(
                response,
                attempt,
            )

            print(
                "[Discord] 429 — "
                "слишком много запросов "
                "или временное ограничение."
            )

            print(
                "[Discord] Повтор через "
                f"{wait_time:.1f} сек."
            )

            if attempt < (
                DISCORD_MAX_RETRIES - 1
            ):
                time.sleep(wait_time)
                continue

        print(
            "[Discord] Ответ: "
            f"{response.text[:1000]}"
        )

        raise RuntimeError(
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    raise RuntimeError(
        "Discord: превышено количество "
        "попыток после 429"
    )


# =========================================================
# DISCORD
# =========================================================

def send_to_discord(image):

    source = image["source"]

    image_url = image["url"]

    webhook_map = {

        "Waifu.im": (
            WAIFU_WEBHOOK_URL,
            "🌸 Anime",
        ),

        "Danbooru Anime": (
            DANBOORU_WEBHOOK_URL,
            "🎨 Anime Art",
        ),

        "Danbooru Games": (
            DANBOORU_GAMES_WEBHOOK_URL,
            "🎮 Game Art",
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

    filename, image_data, content_type = (
        download_image(image_url)
    )

    print(
        f"[Discord] Отправка: "
        f"{source}"
    )

    print(
        f"[Discord] Файл: "
        f"{filename}"
    )

    print(
        "[Discord] Размер: "
        f"{len(image_data) / 1024 / 1024:.2f} MB"
    )

    # -----------------------------------------------------
    # Теги
    # -----------------------------------------------------

    raw_tags = image.get(
        "tags",
        ""
    )

    if isinstance(
        raw_tags,
        str
    ):

        tag_list = [
            tag.strip()
            for tag in raw_tags.split()
            if tag.strip()
        ]

    else:

        tag_list = []

    # Не отправляем бесконечное
    # количество тегов.
    tag_list = tag_list[:30]

    if tag_list:

        tags_text = (
            "\n🏷️ Теги: "
            + ", ".join(
                f"`{tag}`"
                for tag in tag_list
            )
        )

    else:

        tags_text = ""

    content = (
        f"{message}\n"
        f"Источник: {source}"
        f"{tags_text}"
    )

    files = {
        "file": (
            filename,
            image_data,
            content_type,
        )
    }

    data = {
        "content": content,
    }

    discord_request(
        webhook_url,
        data,
        files,
    )

    print(
        "[Discord] Успешно отправлено: "
        f"{source}"
    )


# =========================================================
# PUBLISH
# =========================================================

def publish_source(
    name,
    getter
):

    try:

        image = getter()

        send_to_discord(image)

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
            f"[{name}] ОШИБКА: "
            f"{error}"
        )

        return {
            "source": name,
            "success": False,
            "error": str(error),
        }


# =========================================================
# GLOBAL POST LOCK
# =========================================================

POST_LOCK = threading.Lock()


# =========================================================
# POST
# =========================================================

@app.route("/post")
def post_image():

    # Не позволяем двум cron/manual
    # запускам одновременно публиковать
    # одинаковый набор источников.

    if not POST_LOCK.acquire(
        blocking=False
    ):

        print(
            "[POST] Публикация уже "
            "идёт — второй запуск пропущен."
        )

        return Response(
            "OK - publication already running",
            status=200,
        )

    try:

        print(
            "======================================================="
        )

        print(
            "POST: запуск публикации"
        )

        print(
            "======================================================="
        )

        sources = []

        if WAIFU_WEBHOOK_URL:

            sources.append(
                (
                    "Waifu.im",
                    get_random_waifu,
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
                    get_danbooru_anime,
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
                    get_danbooru_games,
                )
            )

        if not sources:

            return Response(
                "No sources configured",
                status=500,
            )

        results = []

        # Источники идут строго один
        # за другим, а между Discord
        # отправками есть задержка.

        for name, getter in sources:

            result = publish_source(
                name,
                getter,
            )

            results.append(result)

        successful = sum(
            1
            for result in results
            if result["success"]
        )

        errors = (
            len(results) - successful
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
                    "POST: "
                    f"{result['source']}: "
                    f"{result['error']}"
                )

        print(
            "======================================================="
        )

        return Response(
            f"OK - successful: "
            f"{successful}, "
            f"errors: {errors}",
            status=200,
        )

    finally:

        POST_LOCK.release()


# =========================================================
# STATUS
# =========================================================

@app.route("/status")
def status():

    return {
        "status": "online",

        "pinterest": {
            "token_configured": bool(
                os.environ.get(
                    "PINTEREST_ACCESS_TOKEN"
                )
            )
        },

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
        "Game Poster is running.",
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
