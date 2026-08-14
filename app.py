
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

# НОВЫЙ webhook именно для Rule34 Games
RULE34_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_RULE34_GAMES"
)

PEXELS_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_PEXELS"
)

DANBOORU_USERNAME = os.environ.get(
    "DANBOORU_USERNAME"
)

DANBOORU_API_KEY = os.environ.get(
    "DANBOORU_API_KEY"
)

PEXELS_API_KEY = os.environ.get(
    "PEXELS_API_KEY"
)


# =========================================================
# URL
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)

PEXELS_API = (
    "https://api.pexels.com/v1"
)

RULE34_API = (
    "https://api.rule34.xxx/"
    "index.php"
)


# =========================================================
# НАСТРОЙКИ ИГР
# =========================================================
#
# ВОТ ЗДЕСЬ добавляй или меняй игры.
#
# Используются реальные теги Rule34.
#
# Пример:
#
# "genshin_impact"
# "nier_automata"
# "street_fighter"
#
# Если по конкретному тегу результатов нет,
# бот автоматически попробует другую игру.
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
    "vampire_survivors",
    "cyberpunk_2077",
    "baldurs_gate_3",
    "the_witcher",
    "mass_effect",
    "dragon_age",
    "borderlands",
    "resident_evil",
    "silent_hill",
    "dead_by_daylight",
    "dark_souls",
    "elden_ring",
    "final_fantasy",
    "kingdom_hearts",
    "persona",
    "shin_megami_tensei",
    "fire_emblem",
    "pokemon",
    "zelda",
    "mario",
    "sonic_the_hedgehog",
    "street_fighter",
    "tekken",
    "soul_calibur",
    "guilty_gear",
]


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

RULE34_HEADERS = {
    "User-Agent": (
        "GamePoster/1.0"
    ),
    "Accept": (
        "application/json,"
        "text/plain,*/*"
    ),
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
        return post_id in RULE34_USED_IDS


def rule34_mark_used(post_id):

    if post_id is None:
        return

    with RULE34_LOCK:

        RULE34_USED_IDS.add(
            post_id
        )

        if (
            len(RULE34_USED_IDS)
            > MAX_RULE34_MEMORY
        ):

            old_id = random.choice(
                list(RULE34_USED_IDS)
            )

            RULE34_USED_IDS.discard(
                old_id
            )


# =========================================================
# DANBOORU RATE LIMITER
# =========================================================

DANBOORU_LOCK = threading.Lock()

LAST_DANBOORU_REQUEST = 0.0


def danbooru_wait():

    global LAST_DANBOORU_REQUEST

    with DANBOORU_LOCK:

        now = time.monotonic()

        elapsed = (
            now - LAST_DANBOORU_REQUEST
        )

        wait_time = (
            1.2 - elapsed
        )

        if wait_time > 0:

            print(
                "[Danbooru] "
                f"Ожидание "
                f"{wait_time:.1f} сек."
            )

            time.sleep(
                wait_time
            )

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

        raise RuntimeError(
            "Waifu.im "
            "не вернул изображение"
        )

    image_url = items[0].get(
        "url"
    )

    if not image_url:

        raise RuntimeError(
            "Waifu.im "
            "не вернул URL"
        )

    return {
        "url": image_url,
        "source": "Waifu.im",
    }


# =========================================================
# DANBOORU
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
        f"[{source_name}] "
        f"HTTP: "
        f"{response.status_code}"
    )

    if response.status_code == 422:

        print(
            response.text[:1000]
        )

        raise RuntimeError(
            f"{source_name}: "
            "Danbooru HTTP 422"
        )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            f"{source_name}: "
            "неожиданный ответ"
        )

    images = []

    for post in data:

        image_url = (
            post.get(
                "large_file_url"
            )
            or post.get(
                "file_url"
            )
        )

        if not image_url:
            continue

        images.append({
            "url": image_url,
            "source": source_name,
            "post_id": post.get(
                "id"
            ),
        })

    if not images:

        raise RuntimeError(
            f"{source_name}: "
            "изображения не найдены"
        )

    return random.choice(
        images
    )


def get_danbooru_anime():

    return get_random_danbooru(
        "rating:s 1girl",
        "Danbooru Anime",
    )


# =========================================================
# RULE34 GAMES
# =========================================================

def get_rule34_games():

    print(
        "[Rule34 Games] "
        "Ищем игровой арт..."
    )

    games = (
        RULE34_GAME_TAGS.copy()
    )

    random.shuffle(
        games
    )

    # Несколько попыток с разными играми,
    # чтобы одна пустая выдача не ломала /post.
    for game_tag in games:

        print(
            "[Rule34 Games] "
            f"Пробуем тег: "
            f"{game_tag}"
        )

        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",

            # Безопасный игровой арт.
            "tags": (
                f"{game_tag} "
                "rating:explicit "
                "sort:random"
            ),

            "limit": "100",
        }

        try:

            response = requests.get(
                RULE34_API,
                params=params,
                headers=RULE34_HEADERS,
                timeout=30,
            )

            print(
                "[Rule34 Games] "
                f"HTTP: "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

        except Exception as error:

            print(
                "[Rule34 Games] "
                f"Ошибка API: {error}"
            )

            continue

        if not isinstance(
            data,
            list,
        ):

            print(
                "[Rule34 Games] "
                "Некорректный ответ"
            )

            continue

        if not data:

            print(
                "[Rule34 Games] "
                f"Нет результатов "
                f"для {game_tag}"
            )

            continue

        random.shuffle(
            data
        )

        # Сначала ищем ещё не отправлявшийся пост.
        for post in data:

            post_id = post.get(
                "id"
            )

            if rule34_was_used(
                post_id
            ):
                continue

            image_url = (
                post.get(
                    "file_url"
                )
                or post.get(
                    "sample_url"
                )
            )

            if not image_url:
                continue

            rule34_mark_used(
                post_id
            )

            print(
                "[Rule34 Games] "
                f"Выбран {game_tag}, "
                f"post_id={post_id}"
            )

            return {
                "url": image_url,
                "source": (
                    "Rule34 Games"
                ),
                "post_id": post_id,
                "game_tag": game_tag,
            }

    raise RuntimeError(
        "Rule34 Games: "
        "не удалось найти "
        "новый игровой пост"
    )


# =========================================================
# PEXELS
# =========================================================

def get_random_pexels():

    if not PEXELS_API_KEY:

        raise RuntimeError(
            "PEXELS_API_KEY "
            "не настроен"
        )

    print(
        "[Pexels] "
        "Получаем изображение..."
    )

    queries = [
        "gaming",
        "video game",
        "game character",
        "fantasy game art",
        "cosplay",
        "gaming character",
    ]

    random.shuffle(
        queries
    )

    headers = {
        "Authorization":
            PEXELS_API_KEY,
        "User-Agent":
            "GamePoster/1.0",
    }

    for query in queries:

        response = requests.get(
            f"{PEXELS_API}/search",
            headers=headers,
            params={
                "query": query,
                "per_page": 80,
                "page": 1,
            },
            timeout=30,
        )

        if response.status_code == 429:

            raise RuntimeError(
                "Pexels HTTP 429"
            )

        response.raise_for_status()

        data = response.json()

        photos = data.get(
            "photos",
            [],
        )

        if not photos:
            continue

        photo = random.choice(
            photos
        )

        src = photo.get(
            "src",
            {},
        )

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

    raise RuntimeError(
        "Pexels "
        "не вернул изображения"
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    content = response.content

    if len(content) > (
        8 * 1024 * 1024
    ):

        raise RuntimeError(
            "Изображение "
            "больше 8 MB"
        )

    content_type = (
        response.headers.get(
            "Content-Type",
            "image/jpeg",
        )
    )

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

def send_to_discord(
    image
):

    source = image[
        "source"
    ]

    image_url = image[
        "url"
    ]

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
            "📷 Game / Fashion Art",
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

    (
        filename,
        image_data,
        content_type,
    ) = download_image(
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

def publish_source(
    name,
    getter,
):

    try:

        image = getter()

        send_to_discord(
            image
        )

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
# POST
# =========================================================

@app.route("/post")
def post_image():

    print(
        "======================================================="
    )

    print(
        "POST: запуск независимой публикации"
    )

    print(
        "======================================================="
    )

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
            ),

            "pexels": bool(
                PEXELS_WEBHOOK_URL
                and PEXELS_API_KEY
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
```
