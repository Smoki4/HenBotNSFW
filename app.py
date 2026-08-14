import os
import random
import threading
import time

import requests
from flask import Flask, Response, jsonify

app = Flask(__name__)

# =========================================================
# ENV
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU", "").strip()
DANBOORU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_DANBOORU", "").strip()
PEXELS_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_PEXELS", "").strip()

DANBOORU_USERNAME = os.environ.get("DANBOORU_USERNAME", "").strip()
DANBOORU_API_KEY = os.environ.get("DANBOORU_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

# Rule34 credentials — НИКОГДА не вставляй значения прямо сюда.
RULE34_USER_ID = os.environ.get("RULE34_USER_ID", "").strip()
RULE34_API_KEY = os.environ.get("RULE34_API_KEY", "").strip()


# =========================================================
# API
# =========================================================

DANBOORU_API = "https://danbooru.donmai.us"
PEXELS_API = "https://api.pexels.com/v1"


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": "GamePoster/1.0"
}

DANBOORU_HEADERS = {
    "User-Agent": "GamePoster/1.0",
    "Accept": "application/json",
}


# =========================================================
# MEMORY
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

                if size and int(size) > 8 * 1024 * 1024:
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
                f"[Waifu.im] "
                f"Попытка {attempt + 1}: {error}"
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
        f"[{source_name}] HTTP: "
        f"{response.status_code}"
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
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:
        raise RuntimeError(
            "PEXELS_API_KEY не настроен"
        )

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
# RULE34 CREDENTIAL DIAGNOSTIC
# =========================================================

@app.route("/rule34-test")
def rule34_test():

    user_present = bool(RULE34_USER_ID)
    key_present = bool(RULE34_API_KEY)

    result = {
        "configured": (
            user_present
            and key_present
        ),
        "user_id_present": user_present,
        "api_key_present": key_present,
        "api_key_length": (
            len(RULE34_API_KEY)
            if RULE34_API_KEY
            else 0
        ),
    }

    if not user_present:

        result["error"] = (
            "RULE34_USER_ID отсутствует "
            "в Render Environment Variables"
        )

        return jsonify(result), 500

    if not key_present:

        result["error"] = (
            "RULE34_API_KEY отсутствует "
            "в Render Environment Variables"
        )

        return jsonify(result), 500

    result["message"] = (
        "Rule34 credentials загружены "
        "из Render Environment Variables."
    )

    return jsonify(result), 200


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
                f"POST: "
                f"{result['source']}: "
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

    return jsonify({
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

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
            ),

            "rule34_credentials": bool(
                RULE34_USER_ID
                and RULE34_API_KEY
            ),
        },
    })


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

