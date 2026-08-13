import os
import json
import random
import requests

from flask import Flask, Response

app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN")

PINTEREST_API = "https://api.pinterest.com/v5"

WAIFU_API = "https://api.waifu.im/images"

HEADERS = {
    "User-Agent": "AnimePoster/1.0"
}

PINTEREST_HEADERS = {
    "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "AnimePoster/1.0"
}


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu():

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
        raise RuntimeError(
            "Waifu.im не вернул изображение"
        )

    image = items[0]

    image_url = image.get("url")

    if not image_url:
        raise RuntimeError(
            "У изображения Waifu.im отсутствует URL"
        )

    return {
        "url": image_url,
        "source": "Waifu.im"
    }


# =========================================================
# PINTEREST
# =========================================================

def pinterest_request(endpoint, params=None):

    if not PINTEREST_ACCESS_TOKEN:
        raise RuntimeError(
            "PINTEREST_ACCESS_TOKEN не настроен"
        )

    response = requests.get(
        f"{PINTEREST_API}{endpoint}",
        headers=PINTEREST_HEADERS,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Получить все доски пользователя
# =========================================================

def get_pinterest_boards():

    boards = []

    bookmark = None

    while True:

        params = {
            "page_size": 100
        }

        if bookmark:
            params["bookmark"] = bookmark

        data = pinterest_request(
            "/boards",
            params=params
        )

        items = data.get("items", [])

        boards.extend(items)

        bookmark = data.get("bookmark")

        if not bookmark:
            break

        # Защита от бесконечной пагинации
        if len(boards) >= 2000:
            break

    return boards


# =========================================================
# Получить Pins конкретной доски
# =========================================================

def get_board_pins(board_id):

    pins = []

    bookmark = None

    while True:

        params = {
            "page_size": 100
        }

        if bookmark:
            params["bookmark"] = bookmark

        data = pinterest_request(
            f"/boards/{board_id}/pins",
            params=params
        )

        items = data.get("items", [])

        pins.extend(items)

        bookmark = data.get("bookmark")

        if not bookmark:
            break

        # Чтобы один запрос /post не мог бесконечно
        # собирать огромное количество данных.
        if len(pins) >= 1000:
            break

    return pins


# =========================================================
# Получить случайный Pin из всех досок
# =========================================================

def get_random_pinterest_pin():

    boards = get_pinterest_boards()

    if not boards:
        raise RuntimeError(
            "Pinterest не вернул ни одной доски"
        )

    all_pins = []

    for board in boards:

        board_id = board.get("id")

        if not board_id:
            continue

        try:

            pins = get_board_pins(board_id)

            for pin in pins:

                image_url = None

                media = pin.get("media", {})

                images = media.get("images", {})

                # Pinterest обычно возвращает несколько
                # вариантов размера изображения.
                if images:

                    for image_data in images.values():

                        if isinstance(image_data, dict):

                            url = image_data.get("url")

                            if url:
                                image_url = url
                                break

                if image_url:

                    all_pins.append({
                        "url": image_url,
                        "source": "Pinterest",
                        "pin_id": pin.get("id"),
                        "board_id": board_id,
                        "board_name": board.get(
                            "name",
                            "Pinterest"
                        )
                    })

        except requests.exceptions.RequestException as error:

            print(
                f"Ошибка получения доски "
                f"{board_id}: {error}"
            )

            continue

    if not all_pins:
        raise RuntimeError(
            "В твоих Pinterest-досках не найдено "
            "изображений"
        )

    return random.choice(all_pins)


# =========================================================
# Скачать изображение
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "image/jpeg"
    )

    image_data = response.content

    # Discord webhook обычно принимает небольшие файлы.
    if len(image_data) > 8 * 1024 * 1024:

        raise RuntimeError(
            "Изображение больше 8 MB"
        )

    if "png" in content_type:
        extension = "png"

    elif "webp" in content_type:
        extension = "webp"

    elif "gif" in content_type:
        extension = "gif"

    else:
        extension = "jpg"

    filename = f"anime_art.{extension}"

    return (
        filename,
        image_data,
        content_type
    )


# =========================================================
# Отправка в Discord
# =========================================================

def send_to_discord(image):

    if not DISCORD_WEBHOOK_URL:

        raise RuntimeError(
            "DISCORD_WEBHOOK_URL не настроен"
        )

    image_url = image.get("url")

    if not image_url:

        raise RuntimeError(
            "У изображения отсутствует URL"
        )

    filename, image_data, content_type = \
        download_image(image_url)

    source = image.get(
        "source",
        "Unknown"
    )

    payload = {
        "username": "Anime Poster",
        "content": f"🌸 Random Anime Art\n📌 Источник: {source}"
    }

    # Если Pinterest — указываем доску
    if source == "Pinterest":

        board_name = image.get(
            "board_name",
            "Pinterest"
        )

        payload["content"] = (
            f"🌸 Random Anime Art\n"
            f"📌 Pinterest: {board_name}"
        )

    files = {
        "file": (
            filename,
            image_data,
            content_type
        )
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        data={
            "payload_json": json.dumps(
                payload,
                ensure_ascii=False
            )
        },
        files=files,
        timeout=30
    )

    response.raise_for_status()


# =========================================================
# / — проверка работы Render
# =========================================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# /ping — НЕ отправляет картинку
# Только держит Render активным
# =========================================================

@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# /post
#
# Случайно выбирает:
#
# 50% → Waifu.im
# 50% → Pinterest
#
# =========================================================

@app.route("/post")
def post_image():

    try:

        # Проверяем webhook
        if not DISCORD_WEBHOOK_URL:

            return Response(
                "DISCORD_WEBHOOK_URL not configured",
                status=500,
                mimetype="text/plain"
            )

        # Проверяем Pinterest только если он нужен
        use_pinterest = random.choice(
            [True, False]
        )

        if use_pinterest:

            print(
                "POST: выбран Pinterest"
            )

            if not PINTEREST_ACCESS_TOKEN:

                print(
                    "Pinterest token отсутствует. "
                    "Используем Waifu.im."
                )

                image = get_random_waifu()

            else:

                image = get_random_pinterest_pin()

        else:

            print(
                "POST: выбран Waifu.im"
            )

            image = get_random_waifu()

        print(
            f"POST: источник: "
            f"{image.get('source')}"
        )

        send_to_discord(image)

        print(
            "POST: изображение отправлено "
            "в Discord"
        )

        # Очень маленький ответ для cron-job.org
        return Response(
            "OK",
            status=200,
            mimetype="text/plain"
        )

    except requests.exceptions.Timeout:

        print(
            "POST: timeout"
        )

        return Response(
            "Request timeout",
            status=504,
            mimetype="text/plain"
        )

    except requests.exceptions.HTTPError as error:

        print(
            f"POST: HTTP error: {error}"
        )

        return Response(
            "HTTP request failed",
            status=502,
            mimetype="text/plain"
        )

    except Exception as error:

        print(
            f"POST: error: {error}"
        )

        return Response(
            "Internal error",
            status=500,
            mimetype="text/plain"
        )


# =========================================================
# Запуск
# =========================================================

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
