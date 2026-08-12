import os
import json
import requests
from flask import Flask, jsonify

app = Flask(__name__)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

WAIFU_API = "https://api.waifu.im/images"

HEADERS = {
    "Accept-Version": "v7",
    "User-Agent": "AnimePoster/1.0"
}


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

    extension = "jpg"

    if "png" in content_type:
        extension = "png"
    elif "webp" in content_type:
        extension = "webp"
    elif "gif" in content_type:
        extension = "gif"

    filename = f"anime_art.{extension}"

    payload = {
        "username": "Anime Poster",
        "content": "🌸 Random Anime Art"
    }

    files = {
        "file": (
            filename,
            image_response.content,
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


@app.route("/")
def home():
    return "Anime Poster is running."


@app.route("/post")
def post_image():
    if not WEBHOOK_URL:
        return jsonify({
            "ok": False,
            "error": "DISCORD_WEBHOOK_URL не настроен"
        }), 500

    try:
        image = get_random_image()
        send_to_discord(image)

        return "OK", 200

    except Exception as error:
        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(
        host="0.0.0.0",
        port=port
    )
