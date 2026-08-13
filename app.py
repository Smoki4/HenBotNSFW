import os
import json
import requests
from flask import Flask, jsonify, Response

app = Flask(__name__)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

WAIFU_API = "https://api.waifu.im/images"

HEADERS = {
    "Accept-Version": "v7",
    "User-Agent": "AnimePoster/1.0"
}


# ==========================================
# Получение случайного изображения
# ==========================================

def get_random_image():
    params = {
        "IsNsfw": "True",
        "OrderBy": "Random",
        "PageSize": 1
    }

    response = requests.get(
        WAIFU_API,
        params=params,
        headers=HEADERS,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    items = data.get("items", [])

    if not items:
        raise RuntimeError("Waifu.im не вернул изображение")

    return items[0]


# ==========================================
# Отправка изображения в Discord
# ==========================================

def send_to_discord(image):

    image_url = image.get("url")

    if not image_url:
        raise RuntimeError("У изображения отсутствует URL")

    image_response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=30
    )

    image_response.raise_for_status()

    content_type = image_response.headers.get(
        "Content-Type",
        "image/jpeg"
    )

    # Определяем расширение
    if "png" in content_type:
        extension = "png"
    elif "webp" in content_type:
        extension = "webp"
    elif "gif" in content_type:
        extension = "gif"
    else:
        extension = "jpg"

    filename = f"anime_art.{extension}"

    image_data = image_response.content

    # Защита от слишком больших файлов
    if len(image_data) > 8 * 1024 * 1024:
        raise RuntimeError("Изображение слишком большое для Discord")

    payload = {
        "username": "Anime Poster",
        "content": "🌸 Random Anime Art"
    }

    files = {
        "file": (
            filename,
            image_data,
            content_type
        )
    }

    response = requests.post(
        WEBHOOK_URL,
        data={
            "payload_json": json.dumps(payload)
        },
        files=files,
        timeout=30
    )

    response.raise_for_status()


# ==========================================
# Главная страница
# ==========================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
        mimetype="text/plain"
    )


# ==========================================
# PING
# Не делает ничего, кроме ответа OK
# ==========================================

@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
        mimetype="text/plain"
    )


# ==========================================
# POST
# Получает картинку и отправляет её в Discord
# ==========================================

@app.route("/post")
def post_image():

    if not WEBHOOK_URL:

        return Response(
            "Webhook not configured",
            status=500,
            mimetype="text/plain"
        )

    try:

        print("POST: получение изображения...")

        image = get_random_image()

        print("POST: изображение получено")

        send_to_discord(image)

        print("POST: изображение отправлено в Discord")

        return Response(
            "OK",
            status=200,
            mimetype="text/plain"
        )

    except requests.exceptions.Timeout:

        print("POST: timeout")

        return Response(
            "Request timeout",
            status=504,
            mimetype="text/plain"
        )

    except requests.exceptions.RequestException as error:

        print(f"POST: request error: {error}")

        return Response(
            "Request failed",
            status=502,
            mimetype="text/plain"
        )

    except Exception as error:

        print(f"POST: error: {error}")

        return Response(
            "Internal error",
            status=500,
            mimetype="text/plain"
        )


# ==========================================
# Запуск
# ==========================================

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
