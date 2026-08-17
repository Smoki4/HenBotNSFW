```python
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

# Старый webhook Rule34 Games сохраняем,
# но теперь он используется для Danbooru Games.
DANBOORU_GAMES_WEBHOOK_URL = (
    os.environ.get(
        "DISCORD_WEBHOOK_RULE34_GAMES"
    )
    or os.environ.get(
        "DISCORD_WEBHOOK_DANBOORU_GAMES"
    )
)

DANBOORU_USERNAME = os.environ.get(
    "DANBOORU_USERNAME"
)

DANBOORU_API_KEY = os.environ.get(
    "DANBOORU_API_KEY"
)


# =========================================================
# API
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)


# =========================================================
# SETTINGS
# =========================================================

# Discord spoiler для всех изображений.
DISCORD_IMAGE_SPOILER = True

# Максимальный размер файла для Discord.
MAX_IMAGE_SIZE = 8 * 1024 * 1024

# Сколько запросов Danbooru максимум
# пробовать перед fallback.
DANBOORU_MAX_ATTEMPTS = 12


# =========================================================
# НЕЖЕЛАТЕЛЬНЫЕ ТЕГИ
# =========================================================
#
# Здесь можно самому добавлять/удалять теги.
#
# В Danbooru перед тегом ставится "-",
# поэтому:
#
# gore -> -gore
# blood -> -blood
#
# Они автоматически добавляются ко всем
# запросам Danbooru.
# =========================================================

DANBOORU_EXCLUDE_TAGS = [
    "gore",
    "blood",
    "scat",
    "feces",
    "vomit",
    "vore",
]


def get_exclude_tags():
    result = []

    for tag in DANBOORU_EXCLUDE_TAGS:
        tag = str(tag).strip()

        if not tag:
            continue

        if tag.startswith("-"):
            result.append(tag)
        else:
            result.append(
                f"-{tag}"
            )

    return result


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; GamePoster/1.0)"
    )
}


DANBOORU_HEADERS = {
    "User-Agent": (
        "GamePoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


# =========================================================
# MEMORY
# =========================================================

DANBOORU_USED_IDS = set()

DANBOORU_MEMORY_LOCK = (
    threading.Lock()
)

MAX_MEMORY = 1000


def remember_id(
    memory_set,
    lock,
    post_id,
):
    if post_id is None:
        return

    post_id = str(post_id)

    with lock:
        memory_set.add(post_id)

        while len(memory_set) > MAX_MEMORY:
            old_id = random.choice(
                list(memory_set)
            )

            memory_set.discard(old_id)


def was_used(
    memory_set,
    lock,
    post_id,
):
    if post_id is None:
        return False

    with lock:
        return str(post_id) in memory_set


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

        wait_time = (
            1.2 - elapsed
        )

        if wait_time > 0:
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

    for attempt in range(5):
        try:
            response = requests.get(
                "https://api.waifu.im/images",
                params={
                    "IsNsfw": "True",
                    "OrderBy": "Random",
                    "PageSize": 1,
                },
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
                continue

            image_url = items[0].get(
                "url"
            )

            if not image_url:
                continue

            return {
                "url": image_url,
                "source": "Waifu.im",
            }

        except Exception as error:
            print(
                f"[Waifu.im] "
                f"Попытка {attempt + 1}: "
                f"{error}"
            )

    raise RuntimeError(
        "Waifu.im: "
        "не удалось получить изображение"
    )


# =========================================================
# DANBOORU BASE
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

    exclude_tags = (
        get_exclude_tags()
    )

    final_tags = (
        f"{tags} "
        f"{' '.join(exclude_tags)}"
    ).strip()

    print(
        f"[{source_name}] "
        f"Запрос: {final_tags}"
    )

    danbooru_wait()

    response = requests.get(
        f"{DANBOORU_API}/posts.json",
        params={
            "limit": 100,
            "tags": final_tags,
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
        post_id = post.get(
            "id"
        )

        if was_used(
            DANBOORU_USED_IDS,
            DANBOORU_MEMORY_LOCK,
            post_id,
        ):
            continue

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

        candidates.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post_id,
            }
        )

    if not candidates:
        raise RuntimeError(
            f"{source_name}: "
            "новых изображений "
            "не найдено"
        )

    selected = random.choice(
        candidates
    )

    return selected


# =========================================================
# DANBOORU ANIME
# =========================================================

DANBOORU_ANIME_TAGS = [
    "rating:explicit anime",
    "rating:explicit 1girl",
    "rating:explicit 1boy",
    "rating:explicit solo",
    "rating:explicit scenery",
    "rating:explicit landscape",
    "rating:explicit fantasy",
    "rating:explicit school_uniform",
    "rating:explicit animal_ears",
    "rating:explicit furry",
    "rating:explicit vocaloid",
    "rating:explicit hatsune_miku",
    "rating:explicit teto",
    "rating:explicit neru",
    "rating:explicit fnaf",
    "rating:explicit genshin_impact",
    "rating:explicit league_of_legends",
    "rating:explicit overwatch",
    "rating:explicit valorant",
    "rating:explicit minecraft",
]


def get_danbooru_anime():
    tags_list = (
        DANBOORU_ANIME_TAGS[:]
    )

    random.shuffle(tags_list)

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for tags in tags_list[:attempts]:
        try:
            print(
                "[Danbooru Anime] "
                f"Пробуем: {tags}"
            )

            result = get_random_danbooru(
                tags,
                "Danbooru Anime",
            )

            if result:
                remember_id(
                    DANBOORU_USED_IDS,
                    DANBOORU_MEMORY_LOCK,
                    result.get(
                        "post_id"
                    ),
                )

                print(
                    "[Danbooru Anime] "
                    "Новый пост найден"
                )

                return result

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Anime] "
                f"Запрос пропущен: "
                f"{error}"
            )

    # Широкий SAFE fallback.
    try:
        print(
            "[Danbooru Anime] "
            "Пробуем SAFE fallback..."
        )

        result = get_random_danbooru(
            "rating:explicit anime",
            "Danbooru Anime",
        )

        if result:
            remember_id(
                DANBOORU_USED_IDS,
                DANBOORU_MEMORY_LOCK,
                result.get(
                    "post_id"
                ),
            )

            return result

    except Exception as error:
        last_error = error

        print(
            "[Danbooru Anime] "
            f"Fallback ошибка: "
            f"{error}"
        )

    raise RuntimeError(
        "Danbooru Anime: "
        "не удалось найти новый SAFE пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
    )


# =========================================================
# DANBOORU GAMES
# =========================================================

DANBOORU_GAME_TAGS = [
    "rating:explicit genshin_impact",
    "rating:explicit honkai:_star_rail",
    "rating:explicit zenless_zone_zero",
    "rating:explicit league_of_legends",
    "rating:explicit overwatch",
    "rating:explicit valorant",
    "rating:explicit apex_legends",
    "rating:explicit fortnite",
    "rating:explicit minecraft",
    "rating:explicit pokemon",
    "rating:explicit final_fantasy",
    "rating:explicit resident_evil",
    "rating:explicit nier_automata",
    "rating:explicit cyberpunk_2077",
    "rating:explicit the_witcher",
    "rating:explicit baldurs_gate_3",
    "rating:explicit elden_ring",
    "rating:explicit dark_souls",
    "rating:explicit devil_may_cry",
    "rating:explicit guilty_gear",
    "rating:explicit street_fighter",
    "rating:explicit tekken",
    "rating:explicit persona",
    "rating:explicit dota_2",
    "rating:explicit dead_by_daylight",
    "rating:explicit risk_of_rain_2",
    "rating:explicit fnaf",
    "rating:explicit portal",
    "rating:explicit halo",
    "rating:explicit fallout",
    "rating:explicit furry game_character",
]


def get_danbooru_games():
    tags_list = (
        DANBOORU_GAME_TAGS[:]
    )

    random.shuffle(tags_list)

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for tags in tags_list[:attempts]:
        try:
            print(
                "[Danbooru Games] "
                f"Пробуем: {tags}"
            )

            result = get_random_danbooru(
                tags,
                "Danbooru Games",
            )

            if result:
                remember_id(
                    DANBOORU_USED_IDS,
                    DANBOORU_MEMORY_LOCK,
                    result.get(
                        "post_id"
                    ),
                )

                print(
                    "[Danbooru Games] "
                    "Новый пост найден"
                )

                return result

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Games] "
                f"Запрос пропущен: "
                f"{error}"
            )

    # Общий игровой SAFE fallback.
    try:
        print(
            "[Danbooru Games] "
            "Пробуем SAFE game fallback..."
        )

        result = get_random_danbooru(
            "rating:explicit game",
            "Danbooru Games",
        )

        if result:
            remember_id(
                DANBOORU_USED_IDS,
                DANBOORU_MEMORY_LOCK,
                result.get(
                    "post_id"
                ),
            )

            return result

    except Exception as error:
        last_error = error

        print(
            "[Danbooru Games] "
            f"Fallback ошибка: "
            f"{error}"
        )

    raise RuntimeError(
        "Danbooru Games: "
        "не удалось найти новый SAFE "
        "игровой пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
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
        stream=True,
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "image/jpeg",
        )
    )

    content_length = (
        response.headers.get(
            "Content-Length"
        )
    )

    if content_length:
        try:
            if (
                int(content_length)
                > MAX_IMAGE_SIZE
            ):
                response.close()

                raise RuntimeError(
                    "Изображение "
                    "больше 8 MB"
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
                    "Изображение "
                    "больше 8 MB"
                )

            chunks.append(chunk)

    finally:
        response.close()

    content = b"".join(
        chunks
    )

    content_type_lower = (
        content_type.lower()
    )

    if "png" in content_type_lower:
        extension = "png"

    elif "webp" in content_type_lower:
        extension = "webp"

    elif "gif" in content_type_lower:
        extension = "gif"

    elif "jpeg" in content_type_lower:
        extension = "jpg"

    else:
        extension = "jpg"

    filename = (
        f"image.{extension}"
    )

    return (
        filename,
        content,
        content_type,
    )


# =========================================================
# DISCORD
# =========================================================

def send_to_discord(
    image,
):
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
            "🎮 Danbooru Game Art",
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

    # =====================================================
    # DISCORD SPOILER
    # =====================================================

    if DISCORD_IMAGE_SPOILER:
        filename = (
            f"SPOILER_{filename}"
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

    print(
        "[Discord] HTTP: "
        f"{response.status_code}"
    )

    if not response.ok:
        print(
            "[Discord] Ответ: "
            f"{response.text[:1000]}"
        )

        raise RuntimeError(
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    print(
        "[Discord] "
        f"Успешно отправлено: "
        f"{source}"
    )


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
        f"{successful}, "
        f"errors: {errors}",
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

            "danbooru_games": bool(
                DANBOORU_GAMES_WEBHOOK_URL
                and DANBOORU_USERNAME
                and DANBOORU_API_KEY
            ),
        },

        "settings": {
            "discord_spoiler": (
                DISCORD_IMAGE_SPOILER
            ),

            "excluded_tags": (
                get_exclude_tags()
            ),

            "danbooru_max_attempts": (
                DANBOORU_MAX_ATTEMPTS
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
```
