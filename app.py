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

DANBOORU_GAMES_WEBHOOK_URL = (
    os.environ.get("DISCORD_WEBHOOK_RULE34_GAMES")
    or os.environ.get("DISCORD_WEBHOOK_DANBOORU_GAMES")
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

MAX_FILE_SIZE = 8 * 1024 * 1024

# Сколько разных Danbooru Games постов
# пробовать при ошибке Discord 20009.
MAX_DISCORD_RETRIES = 5


# =========================================================
# API
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)


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
            now
            - LAST_DANBOORU_REQUEST
        )

        wait_time = (
            1.2
            - elapsed
        )

        if wait_time > 0:
            time.sleep(wait_time)

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

            print(
                "[Waifu.im] "
                "Изображение найдено"
            )

            return {
                "url": image_url,
                "source": "Waifu.im",
                "tags": None,
                "post_id": None,
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

    print(
        f"[{source_name}] "
        f"Запрос: {tags}"
    )

    print(
        f"[{source_name}] "
        f"Использованный тег: {tags}"
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

        if was_used(
            DANBOORU_USED_IDS,
            DANBOORU_MEMORY_LOCK,
            post_id,
        ):
            continue

        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        candidates.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post_id,
                "tags": tags,
            }
        )

    if not candidates:
        raise RuntimeError(
            f"{source_name}: "
            "новых изображений "
            "не найдено"
        )

    random.shuffle(candidates)

    selected = candidates[0]

    remember_id(
        DANBOORU_USED_IDS,
        DANBOORU_MEMORY_LOCK,
        selected.get("post_id"),
    )

    print(
        f"[{source_name}] "
        f"Найден ID: "
        f"{selected.get('post_id')}"
    )

    print(
        f"[{source_name}] "
        f"Тег: "
        f"{selected.get('tags')}"
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
]


def get_danbooru_anime():
    tags_list = (
        DANBOORU_ANIME_TAGS[:]
    )

    random.shuffle(tags_list)

    last_error = None

    for tags in tags_list:
        try:
            print(
                "[Danbooru Anime] "
                f"Пробуем: {tags}"
            )

            result = (
                get_random_danbooru(
                    tags,
                    "Danbooru Anime",
                )
            )

            if result:
                print(
                    "[Danbooru Anime] "
                    "Новый пост найден"
                )

                return result

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Anime] "
                f"Запрос не подошёл: "
                f"{error}"
            )

            continue

    # =====================================================
    # EXPLICIT FALLBACK
    # =====================================================

    try:
        print(
            "[Danbooru Anime] "
            "Пробуем общий EXPLICIT fallback"
        )

        result = (
            get_random_danbooru(
                "rating:explicit",
                "Danbooru Anime",
            )
        )

        if result:
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
        "не удалось найти новый "
        "EXPLICIT пост"
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
    "rating:explicit mortal_kombat",
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

    for tags in tags_list:
        try:
            print(
                "[Danbooru Games] "
                f"Пробуем: {tags}"
            )

            result = (
                get_random_danbooru(
                    tags,
                    "Danbooru Games",
                )
            )

            if result:
                print(
                    "[Danbooru Games] "
                    "Новый игровой пост найден"
                )

                return result

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Games] "
                f"Запрос не подошёл: "
                f"{error}"
            )

            continue

    # =====================================================
    # EXPLICIT FALLBACK
    # =====================================================

    try:
        print(
            "[Danbooru Games] "
            "Пробуем общий EXPLICIT fallback"
        )

        result = (
            get_random_danbooru(
                "rating:explicit",
                "Danbooru Games",
            )
        )

        if result:
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
        "не удалось найти новый "
        "EXPLICIT пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(image_url):
    from io import BytesIO
    from PIL import Image

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
            size_mb = (
                int(content_length)
                / 1024
                / 1024
            )

            print(
                "[Download] "
                "Размер исходника: "
                f"{size_mb:.2f} MB"
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

            chunks.append(chunk)

    finally:
        response.close()

    original_data = (
        b"".join(chunks)
    )

    print(
        "[Download] Получено: "
        f"{len(original_data) / 1024 / 1024:.2f} MB"
    )

    # =====================================================
    # FILE <= 8 MB
    # =====================================================

    if len(original_data) <= MAX_FILE_SIZE:
        content_type_lower = (
            content_type.lower()
        )

        if "png" in content_type_lower:
            extension = "png"

        elif "webp" in content_type_lower:
            extension = "webp"

        elif "gif" in content_type_lower:
            extension = "gif"

        elif (
            "jpeg" in content_type_lower
            or "jpg" in content_type_lower
        ):
            extension = "jpg"

        else:
            extension = "jpg"

        filename = (
            f"image.{extension}"
        )

        print(
            "[Download] "
            "Файл подходит по размеру."
        )

        if extension == "gif":
            print(
                "[Download] "
                "GIF отправляется "
                "без изменения."
            )

        return (
            filename,
            original_data,
            content_type,
        )

    # =====================================================
    # FILE > 8 MB
    # =====================================================

    print(
        "[Download] "
        "Изображение больше 8 MB."
    )

    print(
        "[Download] "
        "Начинаем сжатие..."
    )

    try:
        image = Image.open(
            BytesIO(original_data)
        )

        print(
            "[Download] Формат: "
            f"{image.format}"
        )

        print(
            "[Download] Разрешение: "
            f"{image.width}x{image.height}"
        )

        # =================================================
        # ANIMATION
        # =================================================

        if getattr(
            image,
            "is_animated",
            False,
        ):
            print(
                "[Download] "
                "Обнаружена анимация."
            )

            print(
                "[Download] "
                "Файл больше 8 MB."
            )

            print(
                "[Download] "
                "Для сжатия используется "
                "первый кадр."
            )

            image.seek(0)

        # =================================================
        # RGB
        # =================================================

        if image.mode in (
            "RGBA",
            "LA",
            "P",
        ):
            background = Image.new(
                "RGB",
                image.size,
                "white",
            )

            if image.mode == "P":
                image = image.convert(
                    "RGBA"
                )

            if image.mode in (
                "RGBA",
                "LA",
            ):
                background.paste(
                    image,
                    (0, 0),
                    image.getchannel(
                        "A"
                    ),
                )

                image = background

            else:
                image = image.convert(
                    "RGB"
                )

        else:
            image = image.convert(
                "RGB"
            )

        # =================================================
        # QUALITY
        # =================================================

        qualities = [
            90,
            85,
            80,
            75,
            70,
            65,
            60,
            55,
            50,
            45,
            40,
        ]

        for quality in qualities:
            output = BytesIO()

            image.save(
                output,
                format="JPEG",
                quality=quality,
                optimize=True,
            )

            compressed_data = (
                output.getvalue()
            )

            print(
                "[Download] "
                f"JPEG quality {quality}: "
                f"{len(compressed_data) / 1024 / 1024:.2f} MB"
            )

            if (
                len(compressed_data)
                <= MAX_FILE_SIZE
            ):
                print(
                    "[Download] "
                    "Сжатие успешно."
                )

                return (
                    "image.jpg",
                    compressed_data,
                    "image/jpeg",
                )

        # =================================================
        # RESIZE
        # =================================================

        print(
            "[Download] "
            "Quality недостаточно."
        )

        print(
            "[Download] "
            "Уменьшаем разрешение..."
        )

        for scale in [
            0.90,
            0.80,
            0.70,
            0.60,
            0.50,
            0.40,
            0.30,
        ]:
            new_width = max(
                1,
                int(
                    image.width
                    * scale
                ),
            )

            new_height = max(
                1,
                int(
                    image.height
                    * scale
                ),
            )

            current_image = (
                image.resize(
                    (
                        new_width,
                        new_height,
                    ),
                    Image.LANCZOS,
                )
            )

            for quality in [
                85,
                75,
                65,
                55,
                45,
                35,
            ]:
                output = BytesIO()

                current_image.save(
                    output,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )

                compressed_data = (
                    output.getvalue()
                )

                print(
                    "[Download] "
                    f"{new_width}x"
                    f"{new_height}, "
                    f"quality {quality}: "
                    f"{len(compressed_data) / 1024 / 1024:.2f} MB"
                )

                if (
                    len(compressed_data)
                    <= MAX_FILE_SIZE
                ):
                    print(
                        "[Download] "
                        "Изображение "
                        "успешно сжато."
                    )

                    return (
                        "image.jpg",
                        compressed_data,
                        "image/jpeg",
                    )

        raise RuntimeError(
            "Не удалось сжать "
            "изображение до 8 MB"
        )

    except Exception as error:
        raise RuntimeError(
            "Изображение больше 8 MB "
            "и не удалось его сжать: "
            f"{error}"
        )


# =========================================================
# DISCORD ERROR
# =========================================================

def get_discord_error(response):
    discord_code = None
    discord_message = None

    try:
        data = response.json()

        discord_code = data.get(
            "code"
        )

        discord_message = data.get(
            "message"
        )

    except ValueError:
        discord_message = (
            response.text
        )

    return (
        discord_code,
        discord_message,
    )


# =========================================================
# DISCORD SEND
# =========================================================

def send_to_discord(image):
    source = image.get(
        "source",
        "Unknown",
    )

    image_url = image.get(
        "url"
    )

    tags = image.get(
        "tags"
    )

    post_id = image.get(
        "post_id"
    )

    if not tags:
        tags = "—"

    if post_id is None:
        post_id = "—"

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

    # =====================================================
    # LOG
    # =====================================================

    print(
        "[Discord] "
        f"Источник: {source}"
    )

    print(
        "[Discord] "
        f"Тег: {tags}"
    )

    print(
        "[Discord] "
        f"ID поста: {post_id}"
    )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    (
        filename,
        image_data,
        content_type,
    ) = download_image(
        image_url
    )

    print(
        "[Discord] "
        f"Файл: {filename}"
    )

    print(
        "[Discord] Размер: "
        f"{len(image_data) / 1024 / 1024:.2f} MB"
    )

    # =====================================================
    # MESSAGE
    # =====================================================

    message_content = (
        f"{message}\n"
        f"Источник: {source}\n"
        f"Тег: {tags}\n"
        f"ID поста: {post_id}"
    )

    # =====================================================
    # SEND
    # =====================================================

    try:
        response = requests.post(
            webhook_url,
            data={
                "content": message_content
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

    except requests.RequestException as error:
        print(
            "[Discord] "
            f"Ошибка соединения: {error}"
        )

        raise RuntimeError(
            "Discord connection error: "
            f"{error}"
        )

    # =====================================================
    # HTTP
    # =====================================================

    print(
        "[Discord] HTTP: "
        f"{response.status_code}"
    )

    # =====================================================
    # SUCCESS
    # =====================================================

    if response.ok:
        print(
            "[Discord] "
            "Успешно отправлено."
        )

        print(
            "[Discord] "
            f"Источник: {source}"
        )

        print(
            "[Discord] "
            f"Тег: {tags}"
        )

        print(
            "[Discord] "
            f"ID: {post_id}"
        )

        return

    # =====================================================
    # ERROR
    # =====================================================

    (
        discord_code,
        discord_message,
    ) = get_discord_error(
        response
    )

    print(
        "[Discord] "
        f"Код ошибки: {discord_code}"
    )

    print(
        "[Discord] "
        f"Сообщение: {discord_message}"
    )

    # =====================================================
    # 20009
    # =====================================================

    if (
        response.status_code == 400
        and discord_code == 20009
    ):
        print(
            "======================================================="
        )

        print(
            "[Discord] "
            "ОШИБКА 20009"
        )

        print(
            "[Discord] "
            "Контент отклонён "
            "получателем."
        )

        print(
            "[Discord] "
            f"Источник: {source}"
        )

        print(
            "[Discord] "
            f"Тег: {tags}"
        )

        print(
            "[Discord] "
            f"ID поста: {post_id}"
        )

        print(
            "======================================================="
        )

        raise RuntimeError(
            "DISCORD_20009"
        )

    # =====================================================
    # OTHER DISCORD ERROR
    # =====================================================

    print(
        "[Discord] Ответ:"
    )

    print(
        response.text[:1000]
    )

    raise RuntimeError(
        f"Discord HTTP "
        f"{response.status_code}: "
        f"{response.text[:500]}"
    )


# =========================================================
# PUBLISH NORMAL SOURCE
# =========================================================

def publish_source(
    name,
    getter,
):
    try:
        image = getter()

        print(
            "-------------------------------------------------------"
        )

        print(
            f"[{name}] "
            f"Источник: "
            f"{image.get('source')}"
        )

        print(
            f"[{name}] "
            f"Тег: "
            f"{image.get('tags') or '—'}"
        )

        print(
            f"[{name}] "
            f"ID поста: "
            f"{image.get('post_id') or '—'}"
        )

        print(
            "-------------------------------------------------------"
        )

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
            f"[{name}] "
            f"ОШИБКА: {error}"
        )

        return {
            "source": name,
            "success": False,
            "error": str(error),
        }


# =========================================================
# PUBLISH DANBOORU GAMES WITH RETRIES
# =========================================================

def publish_danbooru_games():
    print(
        "======================================================="
    )

    print(
        "[Danbooru Games] "
        "Запуск публикации"
    )

    print(
        f"[Danbooru Games] "
        f"Максимум попыток: "
        f"{MAX_DISCORD_RETRIES}"
    )

    last_error = None

    for attempt in range(
        1,
        MAX_DISCORD_RETRIES + 1,
    ):
        print(
            "-------------------------------------------------------"
        )

        print(
            "[Danbooru Games] "
            f"Попытка {attempt}/"
            f"{MAX_DISCORD_RETRIES}"
        )

        try:
            # Получаем новый пост.
            image = (
                get_danbooru_games()
            )

            print(
                "[Danbooru Games] "
                f"Источник: "
                f"{image.get('source')}"
            )

            print(
                "[Danbooru Games] "
                f"Тег: "
                f"{image.get('tags')}"
            )

            print(
                "[Danbooru Games] "
                f"ID: "
                f"{image.get('post_id')}"
            )

            # Пытаемся отправить.
            send_to_discord(
                image
            )

            print(
                "[Danbooru Games] "
                "Успешно опубликовано"
            )

            return {
                "source": (
                    "Danbooru Games"
                ),
                "success": True,
                "error": None,
            }

        except RuntimeError as error:
            last_error = error

            error_text = str(error)

            # =================================================
            # DISCORD 20009
            # =================================================

            if error_text == "DISCORD_20009":
                print(
                    "[Danbooru Games] "
                    "Discord отклонил пост "
                    "кодом 20009."
                )

                print(
                    "[Danbooru Games] "
                    "Пост помечен как использованный."
                )

                print(
                    "[Danbooru Games] "
                    "Берём следующий пост..."
                )

                continue

            # =================================================
            # OTHER ERROR
            # =================================================

            print(
                "[Danbooru Games] "
                f"Ошибка: {error}"
            )

            break

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Games] "
                f"Неожиданная ошибка: "
                f"{error}"
            )

            break

    print(
        "[Danbooru Games] "
        "Не удалось опубликовать пост "
        f"за {MAX_DISCORD_RETRIES} попыток."
    )

    return {
        "source": "Danbooru Games",
        "success": False,
        "error": str(
            last_error
            or "Неизвестная ошибка"
        ),
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

    results = []

    # =====================================================
    # WAIFU
    # =====================================================

    if WAIFU_WEBHOOK_URL:
        results.append(
            publish_source(
                "Waifu.im",
                get_random_waifu,
            )
        )

    # =====================================================
    # DANBOORU ANIME
    # =====================================================

    if (
        DANBOORU_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):
        results.append(
            publish_source(
                "Danbooru Anime",
                get_danbooru_anime,
            )
        )

    # =====================================================
    # DANBOORU GAMES
    # =====================================================

    if (
        DANBOORU_GAMES_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):
        results.append(
            publish_danbooru_games()
        )

    # =====================================================
    # NO SOURCES
    # =====================================================

    if not results:
        return Response(
            "No sources configured",
            status=500,
        )

    # =====================================================
    # RESULTS
    # =====================================================

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
