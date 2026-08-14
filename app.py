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

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU", "")
DANBOORU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_DANBOORU", "")
RULE34_GAMES_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_RULE34_GAMES", "")
PEXELS_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_PEXELS", "")

DANBOORU_USERNAME = os.environ.get("DANBOORU_USERNAME", "")
DANBOORU_API_KEY = os.environ.get("DANBOORU_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

RULE34_API_KEY = os.environ.get("RULE34_API_KEY", "").strip()
RULE34_USER_ID = os.environ.get("RULE34_USER_ID", "").strip()

# =========================================================
# API
# =========================================================

DANBOORU_API = "https://danbooru.donmai.us"
PEXELS_API = "https://api.pexels.com/v1"
RULE34_API = "https://api.rule34.xxx/index.php"

# =========================================================
# RULE34
# =========================================================
# ВАЖНО:
# Этот бот ищет ТОЛЬКО explicit-контент.
# Не меняй это значение на explicit.
# =========================================================

RULE34_RATING = "rating:explicit"

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
]

# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GamePoster/1.0)",
}

DANBOORU_HEADERS = {
    "User-Agent": "GamePoster/1.0",
    "Accept": "application/json",
}

RULE34_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GamePoster/1.0)",
    "Accept": "application/json, application/xml, text/xml, text/plain, */*",
}

# =========================================================
# MEMORY
# =========================================================

RULE34_USED_IDS = set()
RULE34_LOCK = threading.Lock()
MAX_RULE34_MEMORY = 500


def rule34_was_used(post_id):
    if post_id is None:
        return False

    with RULE34_LOCK:
        return str(post_id) in RULE34_USED_IDS


def rule34_mark_used(post_id):
    if post_id is None:
        return

    post_id = str(post_id)

    with RULE34_LOCK:
        RULE34_USED_IDS.add(post_id)

        while len(RULE34_USED_IDS) > MAX_RULE34_MEMORY:
            old_id = random.choice(list(RULE34_USED_IDS))
            RULE34_USED_IDS.discard(old_id)


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

            try:
                head = requests.head(
                    image_url,
                    headers=DEFAULT_HEADERS,
                    timeout=15,
                    allow_redirects=True,
                )

                size = head.headers.get("Content-Length")

                if size:
                    if int(size) > 8 * 1024 * 1024:
                        print("[Waifu.im] Файл больше 8 MB")
                        continue

            except Exception:
                pass

            return {
                "url": image_url,
                "source": "Waifu.im",
            }

        except Exception as error:
            print(
                f"[Waifu.im] Попытка {attempt + 1}: {error}"
            )

    raise RuntimeError(
        "Waifu.im: не удалось получить изображение"
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
        f"[{source_name}] HTTP: {response.status_code}"
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"{source_name}: некорректный ответ"
        )

    images = []

    for post in data:
        image_url = (
            post.get("large_file_url")
            or post.get("file_url")
        )

        if not image_url:
            continue

        images.append({
            "url": image_url,
            "source": source_name,
            "post_id": post.get("id"),
        })

    if not images:
        raise RuntimeError(
            f"{source_name}: изображения не найдены"
        )

    return random.choice(images)


def get_danbooru_anime():
    return get_random_danbooru(
        "rating:explicit 1girl",
        "Danbooru Anime",
    )


# =========================================================
# RULE34 AUTH CHECK
# =========================================================

def check_rule34_auth():
    if not RULE34_API_KEY:
        return False, "RULE34_API_KEY отсутствует"

    if not RULE34_USER_ID:
        return False, "RULE34_USER_ID отсутствует"

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "tags": RULE34_RATING,
        "limit": "1",
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
            f"[Rule34 Auth] HTTP: {response.status_code}"
        )

        text = response.text.strip()

        if "Missing authentication" in text:
            return False, "Rule34 отклонил API credentials"

        if response.status_code >= 400:
            return False, (
                f"HTTP {response.status_code}: "
                f"{text[:200]}"
            )

        return True, "OK"

    except Exception as error:
        return False, str(error)


# =========================================================
# RULE34 RESPONSE PARSER
# =========================================================

def parse_rule34_response(response):
    text = response.text.strip()

    if not text:
        return []

    # JSON
    try:
        data = response.json()

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("posts", "items", "data"):
                value = data.get(key)

                if isinstance(value, list):
                    return value

    except ValueError:
        pass

    # XML
    if "<posts" in text or "<?xml" in text:
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
                f"[Rule34 Games] XML parse error: {error}"
            )

    print(
        "[Rule34 Games] Не удалось распознать ответ."
    )

    print(
        "[Rule34 Games] Content-Type:",
        response.headers.get("Content-Type", ""),
    )

    # Не печатаем потенциальные credentials.
    print(
        "[Rule34 Games] Ответ:",
        text[:300],
    )

    return []


# =========================================================
# RULE34 explicit GAME ART
# =========================================================

def get_rule34_games():
    print("[Rule34 Games] Ищем explicit игровой арт...")

    auth_ok, auth_message = check_rule34_auth()

    if not auth_ok:
        raise RuntimeError(
            f"Rule34 authentication error: {auth_message}"
        )

    games = RULE34_GAME_TAGS.copy()
    random.shuffle(games)

    for game_tag in games:
        print(
            f"[Rule34 Games] Пробуем тег: {game_tag}"
        )

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
            "tags": f"{game_tag} {RULE34_RATING}",
            "limit": "100",

            # Авторизация
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
                f"[Rule34 Games] HTTP: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            # Явно ловим проблему авторизации.
            if "Missing authentication" in response.text:
                raise RuntimeError(
                    "Rule34 API сообщает Missing authentication"
                )

            posts = parse_rule34_response(response)

        except Exception as error:
            print(
                f"[Rule34 Games] Ошибка API: {error}"
            )
            continue

        if not posts:
            print(
                f"[Rule34 Games] Нет результатов для {game_tag}"
            )
            continue

        random.shuffle(posts)

        for post in posts:
            post_id = post.get("id")

            if rule34_was_used(post_id):
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

            rule34_mark_used(post_id)

            print(
                f"[Rule34 Games] Выбран тег: {game_tag}"
            )

            print(
                f"[Rule34 Games] post_id: {post_id}"
            )

            return {
                "url": image_url,
                "source": "Rule34 Games",
                "post_id": post_id,
                "game_tag": game_tag,
            }

    raise RuntimeError(
        "Rule34 Games: не удалось найти подходящий explicit игровой пост"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY не настроен")

    print("[Pexels] Получаем изображение...")

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
                raise RuntimeError("Pexels HTTP 429")

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
            print(f"[Pexels] Ошибка: {error}")

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
            "🎨 Adult Anime Art",
        ),
        "Rule34 Games": (
            RULE34_GAMES_WEBHOOK_URL,
            "🎮 explicit Game Art",
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

    filename, image_data, content_type = download_image(
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
        f"OK - successful: {successful}, errors: {errors}",
        status=200,
    )


# =========================================================
# STATUS
# =========================================================

@app.route("/status")
def status():
    rule34_credentials_present = bool(
        RULE34_API_KEY
        and RULE34_USER_ID
    )

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
            ),

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
            ),
        },

        "rule34": {
            "credentials_present": rule34_credentials_present,
            "rating": RULE34_RATING,
        },
    }


# =========================================================
# RULE34 AUTH TEST
# =========================================================

@app.route("/rule34-test")
def rule34_test():
    ok, message = check_rule34_auth()

    if ok:
        return {
            "ok": True,
            "message": "Rule34 API authentication accepted",
            "rating": RULE34_RATING,
        }

    return {
        "ok": False,
        "message": message,
        "rating": RULE34_RATING,
    }, 502


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
