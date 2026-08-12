import os
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
        "IsNsfw": "False",
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

    payload = {
        "username": "Anime Poster",
        "embeds": [
            {
                "title": "🌸 Random Anime Art",
                "image": {
                    "url": image_url
                },
                "color": 16745472,
                "footer": {
                    "text": "Random anime art • Waifu.im"
                }
            }
        ]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=15
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

        return jsonify({
            "ok": True,
            "image_id": image.get("id"),
            "url": image.get("url")
        })

    except Exception as error:
        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
