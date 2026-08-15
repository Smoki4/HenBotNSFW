import os
import random
import threading
import time
import hashlib

import requests
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENV
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU")
DANBOORU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_DANBOORU")
RULE34_GAMES_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_RULE34_GAMES")
PEXELS_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_PEXELS")

DANBOORU_USERNAME = os.environ.get("DANBOORU_USERNAME")
DANBOORU_API_KEY = os.environ.get("DANBOORU_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

RULE34_API_KEY = os.environ.get("RULE34_API_KEY")
RULE34_USER_ID = os.environ.get("RULE34_USER_ID")


# =========================================================
# API
# =========================================================

DANBOORU_API = "https://danbooru.donmai.us"
PEXELS_API = "https://api.pexels.com/v1"
RULE34_API = "https://api.rule34.xxx/index.php"


# =========================================================
# SETTINGS
# =========================================================

MAX_DISCORD_FILE_SIZE = 8 * 1024 * 1024

# Только безопасный рейтинг.
RULE34_RATING = "rating:explicit"


RULE34_GAME_TAGS = [
    "furry",
    "genshin_impact",
    "nier_automata",
    "street_fighter",
    "skullgirls",
    "overwatch",
    "resident_evil",
    "warhammer_40k",
    "doom",
    "fallout",
    "fortnite",
    "apex_legends",
    "team_fortress_2",
    "mortal_kombat",
    "metal_gear",
    "metal_gear_rising",
    "dota_2",
    "minecraft",
    "portal",
    "mass_effect",
    "world_of_warcraft",
    "deadlock",
    "helldivers",
    "wuthering_waves",
    "arknights",
    "arknights_endfield",
    "batman",
    "darksiders",
    "devil_may_cry",
    "fnaf",
    "halo",
    "far_cry",
    "pubg",
    "helltaker",
    "project_zomboid",
    "cyberpunk_2077",
    "baldurs_gate_3",
    "the_witcher",
    "dragon_age",
    "borderlands",
    "silent_hill",
    "dead_by_daylight",
    "dark_souls",
    "elden_ring",
    "final_fantasy",
    "persona",
    "pokemon",
    "zelda",
    "sonic_the_hedgehog",
    "tekken",
    "soul_calibur",
    "guilty_gear",
]


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GamePoster/1.0)"
}

DANBOORU_HEADERS = {
    "User-Agent": (
        "GamePoster/1.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}

RULE34_HEADERS = {
    "User-Agent": "GamePoster/1.0",
    "Accept": "application/json, application/xml, text/xml, */*",
}


# =========================================================
# MEMORY
# =========================================================

USED_LOCK = threading.Lock()

DANBOORU_USED = set()
RULE34_USED = set()

MAX_MEMORY = 1000


def remember_item(storage, value):
    if value is None:
        return

    value = str(value)

    with USED_LOCK:
        storage.add(value)

        while len(storage) > MAX_MEMORY:
            storage.pop()


def was_used(storage, value):
    if value is None:
        return False

    with USED_LOCK:
        return str(value) in storage


# =========================================================
# DANBOORU RATE LIMIT
# =========================================================

DANBOORU_LOCK = threading.Lock()
LAST_DANBOORU_REQUEST = 0.0


def danbooru_wait():
    global LAST_DANBOORU_REQUEST

    with DANBOORU_LOCK:
        now = time.monotonic()
        elapsed = now - LAST_DANBOORU_REQUEST
        wait_time = 1.2 - elapsed

        if wait_time > 0:
            time.sleep(wait_time)

        LAST_DANBOORU_REQUEST = time.monotonic()


# =========================================================
# WAIFU
# =========================================================

def get_random_waifu():
    print("[Waifu.im] Получаем изображение...")

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
            items = data.get("items", [])

            if not items:
                continue

            image_url = items[0].get("url")

            if not image_url:
                continue

            return {
                "url": image_url,
                "source": "Waifu.im",
            }

        except Exception as error:
            print(
                f"[Waifu.im] Попытка "
                f"{attempt + 1}: {error}"
            )

    raise RuntimeError(
        "Waifu.im: изображение не найдено"
    )


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(tags, source_name):
    if not DANBOORU_USERNAME:
        raise RuntimeError("DANBOORU_USERNAME не настроен")

    if not DANBOORU_API_KEY:
        raise RuntimeError("DANBOORU_API_KEY не настроен")

    print(f"[{source_name}] Запрос: {tags}")

    danbooru_wait()

    response = requests.get(
        f"{DANBOORU_API}/posts.json",
        params={
            "limit": 50,
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
            f"{source_name}: некорректный ответ"
        )

    candidates = []

    for post in data:
        post_id = post.get("id")

        if was_used(DANBOORU_USED, post_id):
            continue

        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        candidates.append({
            "url": image_url,
            "source": source_name,
            "post_id": post_id,
        })

    if not candidates:
        raise RuntimeError(
            f"{source_name}: "
            "новых изображений не найдено"
        )

    selected = random.choice(candidates)

    remember_item(
        DANBOORU_USED,
        selected.get("post_id"),
    )

    return selected

def get_danbooru_anime():
    tags = random.choice([
        "rating:explicit anime",
        "rating:explicit 1girl",
        "rating:explicit 1boy",
        "rating:explicit 2girls",
        "rating:explicit solo",
        "rating:explicit scenery",
        "rating:explicit landscape",
        "rating:explicit fantasy",
        "rating:explicit school_uniform",
        "rating:explicit animal_ears",
        "rating:explicit hentai",
        "rating:explicit lesbian",
        "rating:explicit futanari",
        "rating:explicit bleach",
        "rating:explicit re:zero",
        "rating:explicit yani neko",
    ])

    return get_random_danbooru(
        tags,
        "Danbooru Anime",
    )

# =========================================================
# RULE34 PARSER
# =========================================================

def parse_rule34_response(response):
    text = response.text.strip()

    if not text:
        return []

    try:
        data = response.json()

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("posts", "items", "data"):
                value = data.get(key)

                if isinstance(value, list):
                    return value

        # API иногда возвращает строку с ошибкой.
        if isinstance(data, str):
            print(
                "[Rule34 Games] API:",
                data[:500],
            )

            return []

    except ValueError:
        pass

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if (
        "xml" in content_type
        or text.startswith("<?xml")
        or "<posts" in text
    ):
        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(text)

            posts = []

            for element in root.iter():
                if element.tag.lower().endswith("post"):
                    posts.append(dict(element.attrib))

            return posts

        except Exception as error:
            print(
                "[Rule34 Games] XML error:",
                error,
            )

    print(
        "[Rule34 Games] Не удалось распознать ответ."
    )
    print(
        "[Rule34 Games] Content-Type:",
        content_type,
    )
    print(
        "[Rule34 Games] Ответ:",
        text[:500],
    )

    return []


# =========================================================
# RULE34
# =========================================================

def get_rule34_games():
    print(
        "[Rule34 Games] "
        "Ищем safe игровой арт..."
    )

    if not RULE34_API_KEY or not RULE34_USER_ID:
        raise RuntimeError(
            "RULE34_API_KEY или RULE34_USER_ID не настроен"
        )

    games = RULE34_GAME_TAGS.copy()
    random.shuffle(games)

    for game_tag in games:
        print(
            "[Rule34 Games] "
            f"Пробуем тег: {game_tag}"
        )

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
            "tags": (
                f"{game_tag} "
                f"{RULE34_RATING}"
            ),
            "limit": "100",
            "api_key": RULE34_API_KEY,
            "user_id": RULE34_USER_ID,
        }

        try:
            response = requests.get(
                RULE34_API,
                params=params,
                headers=RULE34_HEADERS,
                timeout=30,
            )

            print(
                "[Rule34 Games] HTTP:",
                response.status_code,
            )

            response.raise_for_status()

            posts = parse_rule34_response(
                response
            )

        except Exception as error:
            print(
                "[Rule34 Games] Ошибка API:",
                error,
            )
            continue

        if not posts:
            print(
                "[Rule34 Games] "
                f"Нет результатов для {game_tag}"
            )
            continue

        random.shuffle(posts)

        for post in posts:
            post_id = post.get("id")

            if was_used(
                RULE34_USED,
                post_id,
            ):
                continue

            image_url = (
                post.get("file_url")
                or post.get("sample_url")
                or post.get("preview_url")
            )

            if not image_url:
                continue

            lowered = image_url.lower()

            if not any(
                extension in lowered
                for extension in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".gif",
                )
            ):
                continue

            remember_item(
                RULE34_USED,
                post_id,
            )

            print(
                "[Rule34 Games] "
                f"Выбран тег: {game_tag}"
            )

            print(
                "[Rule34 Games] "
                f"post_id: {post_id}"
            )

            return {
                "url": image_url,
                "source": "Rule34 Games",
                "post_id": post_id,
                "game_tag": game_tag,
            }

    raise RuntimeError(
        "Rule34 Games: "
        "не удалось найти подходящий safe игровой пост"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():
    if not PEXELS_API_KEY:
        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
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

    random.shuffle(queries)

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "GamePoster/1.0",
    }

    for query in queries:
        try:
            response = requests.get(
                f"{PEXELS_API}/search",
                headers=headers,
                params={
                    "query": query,
                    "per_page": 80,
                    "page": random.randint(1, 5),
                },
                timeout=30,
            )

            if response.status_code == 429:
                raise RuntimeError(
                    "Pexels HTTP 429"
                )

            response.raise_for_status()

            data = response.json()
            photos = data.get("photos", [])

            if not photos:
                continue

            random.shuffle(photos)

            for photo in photos:
                src = photo.get("src", {})

                image_url = (
                    src.get("large2x")
                    or src.get("large")
                    or src.get("original")
                )

                if image_url:
                    return {
                        "url": image_url,
                        "source": "Pexels",
                    }

        except Exception as error:
            print(
                "[Pexels] Ошибка:",
                error,
            )

    raise RuntimeError(
        "Pexels: изображение не найдено"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(image_url):
    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
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
            if int(content_length) > MAX_DISCORD_FILE_SIZE:
                response.close()

                raise RuntimeError(
                    "Изображение больше 8 MB"
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

            if total > MAX_DISCORD_FILE_SIZE:
                raise RuntimeError(
                    "Изображение больше 8 MB"
                )

            chunks.append(chunk)

    finally:
        response.close()

    content = b"".join(chunks)

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
        "Rule34 Games": (
            RULE34_GAMES_WEBHOOK_URL,
            "🎮 Game Art",
        ),
        "Pexels": (
            PEXELS_WEBHOOK_URL,
            "📷 Game Art",
        ),
    }

    if source not in webhook_map:
        raise RuntimeError(
            f"Неизвестный источник: {source}"
        )

    webhook_url, message = webhook_map[source]

    if not webhook_url:
        raise RuntimeError(
            f"Webhook для {source} не настроен"
        )

    filename, image_data, content_type = (
        download_image(image_url)
    )

    print(
        f"[Discord] Отправка: {source}"
    )

    print(
        f"[Discord] Файл: {filename}"
    )

    print(
        f"[Discord] Размер: "
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
        f"[Discord] HTTP: "
        f"{response.status_code}"
    )

    if not response.ok:
        print(
            "[Discord] Ответ:",
            response.text[:1000],
        )

        raise RuntimeError(
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    print(
        f"[Discord] Успешно отправлено: "
        f"{source}"
    )


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
    f"[Discord] HTTP: {response.status_code}"
)

if not response.ok:
    print(
        "[Discord] Ответ:",
        response.text[:1000]
    )

    raise RuntimeError(
        f"Discord HTTP {response.status_code}: "
        f"{response.text[:500]}"
    )


# =========================================================
# PUBLISH
# =========================================================

def publish_source(name, getter):
    try:
        image = getter()

        send_to_discord(image)

        print(
            f"[{name}] Успешно опубликовано"
        )

        return {
            "source": name,
            "success": True,
            "error": None,
        }

    except Exception as error:
        print(
            f"[{name}] ОШИБКА: {error}"
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
    print("=" * 55)
    print("POST: запуск публикации")
    print("=" * 55)

    sources = []

    if WAIFU_WEBHOOK_URL:
        sources.append(
            ("Waifu.im", get_random_waifu)
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
        RULE34_GAMES_WEBHOOK_URL
        and RULE34_API_KEY
        and RULE34_USER_ID
    ):
        sources.append(
            (
                "Rule34 Games",
                get_rule34_games,
            )
        )

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

    # Каждый источник запускается отдельно.
    # Ошибка Rule34 не мешает остальным.
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

    errors = len(results) - successful

    print("=" * 55)
    print("POST: публикация завершена")
    print(f"POST: успешно: {successful}")
    print(f"POST: ошибок: {errors}")

    for result in results:
        if not result["success"]:
            print(
                f"POST: {result['source']}: "
                f"{result['error']}"
            )

    print("=" * 55)

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

            "rule34_games": bool(
                RULE34_GAMES_WEBHOOK_URL
                and RULE34_API_KEY
                and RULE34_USER_ID
            ),

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
            ),
        },

        "rule34_rating": RULE34_RATING,

        "rule34_tags": len(
            RULE34_GAME_TAGS
        ),

        "danbooru_memory": len(
            DANBOORU_USED
        ),

        "rule34_memory": len(
            RULE34_USED
        ),
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

