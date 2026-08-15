
import os
import random
import threading
import time
import xml.etree.ElementTree as ET

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

RULE34_USERNAME = os.environ.get("RULE34_USERNAME")
RULE34_API_KEY = os.environ.get("RULE34_API_KEY")

# Теперь рейтинг можно менять прямо в Render.
# Если переменная отсутствует — используется SAFE.
RULE34_RATING = os.environ.get(
    "RULE34_RATING",
    "rating:explicit"
).strip()

DANBOORU_API = "https://danbooru.donmai.us"
PEXELS_API = "https://api.pexels.com/v1"
RULE34_API = "https://api.rule34.xxx/index.php"

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
    "Accept": "application/json, application/xml, text/xml, text/plain, */*",
}


# =========================================================
# RULE34 GAME TAGS
# =========================================================

RULE34_GAME_TAGS = [
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
    "furry",
    "risk_of_rain_2",
]


# =========================================================
# MEMORY
# =========================================================

RULE34_USED_IDS = set()
DANBOORU_USED_IDS = set()

RULE34_LOCK = threading.Lock()
DANBOORU_MEMORY_LOCK = threading.Lock()

MAX_MEMORY = 1000


def remember_id(memory_set, lock, post_id):
    if post_id is None:
        return

    post_id = str(post_id)

    with lock:
        memory_set.add(post_id)

        while len(memory_set) > MAX_MEMORY:
            old_id = random.choice(list(memory_set))
            memory_set.discard(old_id)


def was_used(memory_set, lock, post_id):
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
        elapsed = now - LAST_DANBOORU_REQUEST
        wait_time = 1.2 - elapsed

        if wait_time > 0:
            time.sleep(wait_time)

        LAST_DANBOORU_REQUEST = time.monotonic()


# =========================================================
# WAIFU.IM
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
        "Waifu.im: не удалось получить изображение"
    )


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(tags, source_name):
    if not DANBOORU_USERNAME:
        raise RuntimeError(
            "DANBOORU_USERNAME не настроен"
        )

    if not DANBOORU_API_KEY:
        raise RuntimeError(
            "DANBOORU_API_KEY не настроен"
        )

    print(f"[{source_name}] Запрос: {tags}")

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
            f"{source_name}: некорректный ответ"
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

    remember_id(
        DANBOORU_USED_IDS,
        DANBOORU_MEMORY_LOCK,
        selected.get("post_id"),
    )

    return selected


def get_danbooru_anime():
    tags = random.choice([
        "rating:safe anime",
        "rating:safe 1girl",
        "rating:safe 1boy",
        "rating:safe 2girls",
        "rating:safe solo",
        "rating:safe scenery",
        "rating:safe landscape",
        "rating:safe fantasy",
        "rating:safe school_uniform",
        "rating:safe animal_ears",
        "rating:safe bleach",
        "rating:safe furry",
        "rating:safe fnaf",
        "rating:safe re_zero",
        "rating:safe vocaloid",
        "rating:safe teto",
        "rating:safe miku",
        "rating:safe neru",
        "rating:safe games",
        "rating:safe risk_of_rain_2",
        "rating:safe dead_by_daylight",
        "rating:safe pubg",
        "rating:safe dota_2",
        "rating:safe zenless_zone_zero",
        "rating:safe genshin_impact",
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

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    print(
        "[Rule34 Debug] Content-Type: "
        f"{content_type}"
    )

    print(
        "[Rule34 Debug] Ответ: "
        f"{text[:500]}"
    )

    try:
        data = response.json()

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in (
                "posts",
                "items",
                "data",
            ):
                value = data.get(key)

                if isinstance(value, list):
                    return value

    except ValueError:
        pass

    lower_text = text.lower()

    if (
        "missing authentication" in lower_text
        or "authentication" in lower_text
        or "invalid api" in lower_text
        or "invalid credentials" in lower_text
    ):
        raise RuntimeError(
            "Rule34 API отклонил authentication credentials"
        )

    if (
        "xml" in content_type
        or text.startswith("<?xml")
        or "<posts" in lower_text
    ):
        try:
            root = ET.fromstring(text)

            posts = []

            for element in root.iter():
                if element.tag.lower().endswith("post"):
                    posts.append(dict(element.attrib))

            return posts

        except Exception as error:
            print(
                f"[Rule34 Games] XML error: {error}"
            )

    return []


# =========================================================
# RULE34 AUTH
# =========================================================

def rule34_auth_available():
    return bool(
        RULE34_USERNAME
        and RULE34_API_KEY
    )


def rule34_params():
    if not RULE34_USERNAME:
        raise RuntimeError(
            "RULE34_USERNAME не настроен"
        )

    if not RULE34_API_KEY:
        raise RuntimeError(
            "RULE34_API_KEY не настроен"
        )

    return {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "user_id": RULE34_USERNAME,
        "api_key": RULE34_API_KEY,
    }


# =========================================================
# RULE34 GAMES
# =========================================================

def get_rule34_games():
    print(
        "[Rule34 Games] "
        f"Ищем изображения с рейтингом: {RULE34_RATING}"
    )

    if not rule34_auth_available():
        raise RuntimeError(
            "RULE34_USERNAME или RULE34_API_KEY не настроен"
        )

    games = RULE34_GAME_TAGS.copy()
    random.shuffle(games)

    for game_tag in games:
        print(
            "[Rule34 Games] "
            f"Пробуем тег: {game_tag}"
        )

        params = rule34_params()

        # Рейтинг теперь полностью управляется
        # переменной RULE34_RATING в Render.
        params["tags"] = (
            f"{game_tag} {RULE34_RATING}"
        )

        params["limit"] = "100"

        try:
            response = requests.get(
                RULE34_API,
                params=params,
                headers=RULE34_HEADERS,
                timeout=30,
            )

            print(
                "[Rule34 Games] HTTP: "
                f"{response.status_code}"
            )

            print(
                "[Rule34 Games] URL: "
                f"{response.url}"
            )

            response.raise_for_status()

            posts = parse_rule34_response(
                response
            )

        except Exception as error:
            print(
                "[Rule34 Games] "
                f"Ошибка API: {error}"
            )

            if (
                "authentication" in str(error).lower()
                or "credentials" in str(error).lower()
            ):
                raise

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
                RULE34_USED_IDS,
                RULE34_LOCK,
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

            remember_id(
                RULE34_USED_IDS,
                RULE34_LOCK,
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
        "не удалось найти подходящий пост"
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
                continue

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
                f"[Pexels] Ошибка: {error}"
            )

    raise RuntimeError(
        "Pexels: не удалось получить изображение"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(image_url):
    max_size = 8 * 1024 * 1024

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
            if int(content_length) > max_size:
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

            if total > max_size:
                raise RuntimeError(
                    "Изображение больше 8 MB"
                )

            chunks.append(chunk)

    finally:
        response.close()

    content = b"".join(chunks)

    content_type_lower = content_type.lower()

    if "png" in content_type_lower:
        extension = "png"
    elif "webp" in content_type_lower:
        extension = "webp"
    elif "gif" in content_type_lower:
        extension = "gif"
    else:
        extension = "jpg"

    filename = f"image.{extension}"

    return (
        filename,
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
    print(
        "======================================================="
    )
    print("POST: запуск публикации")
    print(
        "======================================================="
    )

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

    if RULE34_GAMES_WEBHOOK_URL:
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

    errors = len(results) - successful

    print(
        "======================================================="
    )
    print("POST: публикация завершена")
    print(f"POST: успешно: {successful}")
    print(f"POST: ошибок: {errors}")

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
        f"OK - successful: {successful}, errors: {errors}",
        status=200,
    )


# =========================================================
# STATUS
# =========================================================

@app.route("/status")
def status():
    return {
        "status": "online",
        "rule34": {
            "configured": bool(
                RULE34_GAMES_WEBHOOK_URL
            ),
            "auth_configured": (
                rule34_auth_available()
            ),
            "rating": RULE34_RATING,
            "tags_count": len(
                RULE34_GAME_TAGS
            ),
        },
    }


@app.route("/ping")
def ping():
    return Response("OK", status=200)


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
        os.environ.get("PORT", "8080")
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )

