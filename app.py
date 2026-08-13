import os
import random
import requests

from flask import Flask, Response

app = Flask(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_WAIFU")
PINTEREST_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_PINTEREST")
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN")

WAIFU_API = "https://api.waifu.im/images"
PINTEREST_API = "https://api.pinterest.com/v5"

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
            "Waifu.im не вернул URL изображения"
        )

    return {
        "url": image_url,
        "source": "Waifu.im"
    }


# =========================================================
# PINTEREST API
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
# ПОЛУЧЕНИЕ ВСЕХ ДОСОК
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

        # Защита от слишком большого количества запросов
        if len(boards) >= 500:
            break

    return boards


# =========================================================
# ПОЛУЧЕНИЕ PINS ДОСКИ
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

        # Не собираем бесконечное количество Pins
        if len(pins) >= 1000:
            break

    return pins


# =========================================================
# ПОЛУЧЕНИЕ СЛУЧАЙНОГО PIN
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

        board_name = board.get(
            "name",
            "Pinterest"
        )

        try:

            pins = get_board_pins(board_id)

            for pin in pins:

                media = pin.get(
                    "media",
                    {}
                )

                images = media.get(
                    "images",
                    {}
                )

                image_url = None

                # Берём URL любого доступного
                # варианта изображения
                if images:

                    for image_data in images.values():

                        if isinstance(
                            image_data,
                            dict
                        ):

                            url = image_data.get(
                                "url"
                            )

                            if url:

                                image_url = url
                                break

                if image_url:

                    all_pins.append({
                        "url": image_url,
                        "source": "Pinterest",
                        "board_name": board_name,
                        "pin_id": pin.get("id")
                    })

        except Exception as error:

            print(
                f"Ошибка доски "
                f"{board_name}: {error}"
            )

            continue

    if not all_pins:

        raise RuntimeError(
            "В Pinterest не найдено изображений"
        )

    return random.choice(all_pins)


# =========================================================
# СКАЧИВАНИЕ ИЗОБРАЖЕНИЯ
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

    # Защита от слишком большого файла
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
# ОТПРАВКА В DISCORD
# =========================================================

def send_to_discord(image):

    source = image.get(
        "source",
        "Unknown"
    )

    # Выбираем webhook в зависимости
    # от источника изображения
    if source == "Waifu.im":

        webhook_url = WAIFU_WEBHOOK_URL

        if not webhook_url:
            raise RuntimeError(
                "DISCORD_WEBHOOK_WAIFU не настроен"
            )

        message = "🌸 Random Anime Art\n📌 Источник: Waifu.im"

    elif source == "Pinterest":

        webhook_url = PINTEREST_WEBHOOK_URL

        if not webhook_url:
            raise RuntimeError(
                "DISCORD_WEBHOOK_PINTEREST не настроен"
            )

        board_name = image.get(
            "board_name",
            "Pinterest"
        )

        message = (
            "📌 Random Pinterest Art\n"
            f"📁 Доска: {board_name}"
        )

    else:

        raise RuntimeError(
            "Неизвестный источник изображения"
        )

    image_url = image.get("url")

    if not image_url:
        raise RuntimeError(
            "У изображения отсутствует URL"
        )

    filename, image_data, content_type = \
        download_image(image_url)

    files = {
        "file": (
            filename,
            image_data,
            content_type
        )
    }

    response = requests.post(
        webhook_url,
        data={
            "content": message
        },
        files=files,
        timeout=30
    )

    response.raise_for_status()


# =========================================================
# ГЛАВНАЯ
# =========================================================

@app.route("/")
def home():

    return Response(
        "Anime Poster is running.",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# PING
# =========================================================

@app.route("/ping")
def ping():

    return Response(
        "OK",
        status=200,
        mimetype="text/plain"
    )


# =========================================================
# POST
#
# 50% Waifu.im
# 50% Pinterest
# =========================================================

@app.route("/post")
def post_image():

    try:

        # Проверяем наличие хотя бы одного webhook
        if (
            not WAIFU_WEBHOOK_URL
            and not PINTEREST_WEBHOOK_URL
        ):

            return Response(
                "No Discord webhooks configured",
                status=500,
                mimetype="text/plain"
            )

        # Проверяем доступные источники
        sources = []

        if WAIFU_WEBHOOK_URL:
            sources.append("waifu")

        if (
            PINTEREST_WEBHOOK_URL
            and PINTEREST_ACCESS_TOKEN
        ):
            sources.append("pinterest")

        if not sources:

            return Response(
                "No sources configured",
                status=500,
                mimetype="text/plain"
            )

        # Случайный источник
        source = random.choice(sources)

        print(
            f"POST: выбран источник: {source}"
        )

        # =================================================
        # WAIFU
        # =================================================

        if source == "waifu":

            try:

                image = get_random_waifu()

            except Exception as error:

                print(
                    f"Waifu.im ошибка: {error}"
                )

                # Если Pinterest доступен,
                # пробуем его
                if "pinterest" in sources:

                    print(
                        "Пробуем Pinterest..."
                    )

                    image = (
                        get_random_pinterest_pin()
                    )

                else:

                    raise

        # =================================================
        # PINTEREST
        # =================================================

        else:

            try:

                image = get_random_pinterest_pin()

            except Exception as error:

                print(
                    f"Pinterest ошибка: {error}"
                )

                # Если Waifu доступен,
                # пробуем его
                if "waifu" in sources:

                    print(
                        "Пробуем Waifu.im..."
                    )

                    image = get_random_waifu()

                else:

                    raise

        print(
            f"POST: найдено изображение "
            f"из {image.get('source')}"
        )

        # Отправляем в соответствующий канал
        send_to_discord(image)

        print(
            "POST: отправлено в Discord"
        )

        # Маленький ответ для cron-job.org
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
# ЗАПУСК
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
