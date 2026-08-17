import os
import random
import threading
import time

import requests
from flask import Flask, Response


app = Flask(__name__)


# =========================================================
# ENV / RENDER
# =========================================================

WAIFU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_WAIFU"
)

DANBOORU_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU"
)

DANBOORU_GAMES_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_DANBOORU_GAMES"
)

DANBOORU_USERNAME = os.environ.get(
    "DANBOORU_USERNAME"
)

DANBOORU_API_KEY = os.environ.get(
    "DANBOORU_API_KEY"
)


# =========================================================
# API
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)


# =========================================================
# SETTINGS
# =========================================================

# Discord spoiler
DISCORD_SPOILER = True

# Максимальный размер файла
MAX_IMAGE_SIZE = 8 * 1024 * 1024

# Максимум попыток поиска Danbooru
DANBOORU_MAX_ATTEMPTS = 30

# Сколько ID помнить
MAX_MEMORY = 1500

# ---------------------------------------------------------
# СКОЛЬКО ПОСТОВ ПУБЛИКОВАТЬ ЗА /post
# ---------------------------------------------------------

WAIFU_POSTS = 1

DANBOORU_ANIME_POSTS = 1

DANBOORU_GAMES_POSTS = 2


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
        f"(user "
        f"{DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


# =========================================================
# MEMORY
# =========================================================

DANBOORU_USED_IDS = set()

DANBOORU_MEMORY_LOCK = threading.Lock()


def remember_danbooru_id(post_id):
    if post_id is None:
        return

    post_id = str(post_id)

    with DANBOORU_MEMORY_LOCK:
        DANBOORU_USED_IDS.add(
            post_id
        )

        while (
            len(DANBOORU_USED_IDS)
            > MAX_MEMORY
        ):
            old_id = random.choice(
                list(DANBOORU_USED_IDS)
            )

            DANBOORU_USED_IDS.discard(
                old_id
            )


def danbooru_id_used(post_id):
    if post_id is None:
        return False

    with DANBOORU_MEMORY_LOCK:
        return (
            str(post_id)
            in DANBOORU_USED_IDS
        )


# =========================================================
# DANBOORU RATE LIMIT
# =========================================================

DANBOORU_LOCK = threading.Lock()

LAST_DANBOORU_REQUEST = 0.0


def danbooru_wait():
    global LAST_DANBOORU_REQUEST

    with DANBOORU_LOCK:
        now = time.monotonic()

        elapsed = (
            now
            - LAST_DANBOORU_REQUEST
        )

        wait_time = (
            1.2
            - elapsed
        )

        if wait_time > 0:
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
        "Получаем SAFE изображение..."
    )

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

            print(
                "[Waifu.im] HTTP: "
                f"{response.status_code}"
            )

            if not response.ok:
                print(
                    "[Waifu.im] BODY: "
                    f"{response.text[:1000]}"
                )

            response.raise_for_status()

            data = response.json()

            items = data.get(
                "items",
                [],
            )

            if not items:
                continue

            image_url = (
                items[0].get("url")
            )

            if not image_url:
                continue

            return {
                "url": image_url,
                "source": "Waifu.im",
            }

        except Exception as error:

            print(
                "[Waifu.im] "
                f"Попытка "
                f"{attempt + 1}: "
                f"{error}"
            )

    raise RuntimeError(
        "Waifu.im: "
        "не удалось получить "
        "SAFE изображение"
    )


# =========================================================
# DANBOORU QUERY
# =========================================================

def build_safe_query(base_tags):
    """
    Danbooru может отклонять запросы,
    содержащие слишком много тегов.

    Поэтому здесь разрешено максимум
    2 тега на запрос.

    rating:explicit и другие rating-теги
    удаляются.
    """

    if isinstance(
        base_tags,
        (list, tuple),
    ):
        tags = []

        for tag in base_tags:

            tag = str(tag).strip()

            if not tag:
                continue

            tags.extend(
                tag.split()
            )

    else:
        tags = str(
            base_tags
        ).split()

    safe_tags = []

    for tag in tags:

        lowered = tag.lower()

        # Не позволяем добавлять
        # rating:explicit / rating:q
        # / rating:s и т.д.
        if lowered.startswith(
            "rating:"
        ):
            continue

        # Не используем отрицательные
        # теги в запросе.
        if tag.startswith("-"):
            continue

        safe_tags.append(tag)

    # КРИТИЧЕСКИ ВАЖНО:
    # максимум 2 тега.
    safe_tags = safe_tags[:2]

    return " ".join(
        safe_tags
    )


# =========================================================
# DANBOORU CORE
# =========================================================

def get_random_danbooru(
    base_tags,
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

    final_tags = build_safe_query(
        base_tags
    )

    if not final_tags:

        raise RuntimeError(
            f"{source_name}: "
            "пустой безопасный запрос"
        )

    print(
        f"[{source_name}] "
        f"Запрос: {final_tags}"
    )

    danbooru_wait()

    response = requests.get(
        f"{DANBOORU_API}/posts.json",
        params={
            "limit": 100,
            "tags": final_tags,
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

    if not response.ok:

        print(
            f"[{source_name}] "
            "BODY: "
            f"{response.text[:2000]}"
        )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            f"{source_name}: "
            "некорректный ответ API"
        )

    candidates = []

    for post in data:

        post_id = post.get(
            "id"
        )

        if danbooru_id_used(
            post_id
        ):
            continue

        # =================================================
        # SAFE ONLY
        # =================================================

        rating = str(
            post.get(
                "rating",
                "",
            )
        ).lower()

        # Оставляем ТОЛЬКО safe.
        #
        # s = safe
        # q = questionable -> удаляем
        # e = explicit -> удаляем
        #
        if rating != "e":
            continue

        # =================================================
        # IMAGE URL
        # =================================================

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

        # =================================================
        # TAGS
        # =================================================

        tag_string = post.get(
            "tag_string",
            "",
        )

        candidates.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post_id,
                "tags": tag_string,
            }
        )

    if not candidates:

        raise RuntimeError(
            f"{source_name}: "
            "новых SAFE "
            "изображений не найдено"
        )

    selected = random.choice(
        candidates
    )

    remember_danbooru_id(
        selected.get(
            "post_id"
        )
    )

    return selected


# =========================================================
# DANBOORU ANIME
# =========================================================
#
# ВАЖНО:
#
# Здесь НЕТ rating:explicit.
#
# Все запросы safe-only.
# =========================================================

DANBOORU_ANIME_TAGS = [

    "anime",
    "1girl",
    "1boy",
    "solo",
    "duo",
    "multiple_girls",
    "scenery",
    "landscape",
    "fantasy",
    "school_uniform",
    "animal_ears",
    "kemonomimi",

    "naruto",
    "naruto_shippuden",
    "one_piece",
    "bleach",

    "dragon_ball",
    "dragon_ball_z",
    "dragon_ball_super",

    "my_hero_academia",
    "jujutsu_kaisen",
    "kimetsu_no_yaiba",
    "chainsaw_man",
    "shingeki_no_kyojin",

    "sword_art_online",
    "konosuba",
    "spy_x_family",
    "one_punch_man",

    "mob_psycho_100",
    "fullmetal_alchemist",
    "hunter_x_hunter",

    "jojo_no_kimyou_na_bouken",
    "neon_genesis_evangelion",
    "cowboy_bebop",

    "code_geass",
    "death_note",
    "fairy_tail",
    "black_clover",

    "tokyo_ghoul",
    "blue_lock",
    "haikyuu",

    "sousou_no_frieren",
    "oshi_no_ko",
    "bocchi_the_rock",

    "horimiya",

    "vocaloid",
    "hatsune_miku",
    "megurine_luka",
    "kasane_teto",

    "hololive",
    "nijisanji",

    "cat_ears",
    "fox_ears",
    "bunny_ears",

    "magic",
    "knight",
    "samurai",
    "ninja",
    "vampire",
    "witch",
    "dragon",

    "cyberpunk",
    "steampunk",
    "mecha",
    "robot",

    "beach",
    "cityscape",
    "night",
    "sunset",
]


def get_danbooru_anime():

    tags_list = (
        DANBOORU_ANIME_TAGS[:]
    )

    random.shuffle(
        tags_list
    )

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for tag in tags_list[
        :attempts
    ]:

        try:

            result = (
                get_random_danbooru(
                    tag,
                    "Danbooru Anime",
                )
            )

            print(
                "[Danbooru Anime] "
                "Новый SAFE пост найден"
            )

            return result

        except Exception as error:

            last_error = error

            print(
                "[Danbooru Anime] "
                f"Запрос пропущен: "
                f"{error}"
            )

    fallback_queries = [
        "anime",
        "solo",
        "1girl",
        "1boy",
        "scenery",
        "2girls",
        "lesbians",
    ]

    for tag in fallback_queries:

        try:

            return get_random_danbooru(
                tag,
                "Danbooru Anime",
            )

        except Exception as error:

            last_error = error

    raise RuntimeError(
        "Danbooru Anime: "
        "не удалось найти новый "
        "SAFE пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
    )


# =========================================================
# DANBOORU GAMES
# =========================================================

DANBOORU_GAME_TAGS = [

    "genshin_impact",
    "honkai_star_rail",
    "honkai_impact_3rd",
    "zenless_zone_zero",

    "pokemon",
    "super_mario",
    "the_legend_of_zelda",
    "fire_emblem",
    "splatoon",
    "animal_crossing",
    "kirby",
    "metroid",

    "final_fantasy",
    "final_fantasy_vii",
    "final_fantasy_xiv",
    "persona",
    "persona_5",
    "nier_automata",
    "kingdom_hearts",

    "elden_ring",
    "dark_souls",
    "bloodborne",
    "sekiro",
    "armored_core",
    "devil_may_cry",
    "bayonetta",
    "monster_hunter",

    "street_fighter",
    "tekken",
    "guilty_gear",
    "mortal_kombat",
    "king_of_fighters",
    "soulcalibur",

    "overwatch",
    "valorant",
    "apex_legends",
    "fortnite",
    "halo",
    "destiny",
    "doom",
    "quake",
    "borderlands",

    "league_of_legends",
    "dota_2",
    "heroes_of_the_storm",

    "resident_evil",
    "silent_hill",
    "fatal_frame",
    "dead_by_daylight",

    "minecraft",
    "terraria",
    "stardew_valley",
    "dont_starve",
    "subnautica",
    "valheim",

    "cyberpunk_2077",
    "fallout",
    "starfield",
    "mass_effect",
    "warframe",

    "the_witcher",
    "skyrim",
    "the_elder_scrolls",
    "dragon_age",

    "undertale",
    "deltarune",
    "omori",
    "hollow_knight",
    "cuphead",
    "hades",

    "portal",
    "half-life",
    "sonic_the_hedgehog",
    "ace_attorney",
    "danganronpa",

    "project_sekai",
    "blue_archive",
    "arknights",
    "azur_lane",
    "girls_frontline",
    "nikke",

    "game",
    "video_games",
    "game_character",
]


def get_danbooru_games():

    tags_list = (
        DANBOORU_GAME_TAGS[:]
    )

    random.shuffle(
        tags_list
    )

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for tag in tags_list[
        :attempts
    ]:

        try:

            result = (
                get_random_danbooru(
                    tag,
                    "Danbooru Games",
                )
            )

            print(
                "[Danbooru Games] "
                "Новый SAFE игровой "
                "пост найден"
            )

            return result

        except Exception as error:

            last_error = error

            print(
                "[Danbooru Games] "
                f"Запрос пропущен: "
                f"{error}"
            )

    fallback_queries = [
        "game",
        "video_games",
        "game_character",
    ]

    for tag in fallback_queries:

        try:

            return get_random_danbooru(
                tag,
                "Danbooru Games",
            )

        except Exception as error:

            last_error = error

    raise RuntimeError(
        "Danbooru Games: "
        "не удалось найти новый "
        "SAFE игровой пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=45,
        stream=True,
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "image/jpeg",
        )
    )

    content_length = (
        response.headers.get(
            "Content-Length"
        )
    )

    if content_length:

        try:

            if (
                int(content_length)
                > MAX_IMAGE_SIZE
            ):

                response.close()

                raise RuntimeError(
                    "Изображение "
                    "больше 8 MB"
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

            if total > MAX_IMAGE_SIZE:

                raise RuntimeError(
                    "Изображение "
                    "больше 8 MB"
                )

            chunks.append(
                chunk
            )

    finally:

        response.close()

    content = b"".join(
        chunks
    )

    content_type_lower = (
        content_type.lower()
    )

    if "png" in content_type_lower:

        extension = "png"

    elif "webp" in content_type_lower:

        extension = "webp"

    elif "gif" in content_type_lower:

        extension = "gif"

    elif "jpeg" in content_type_lower:

        extension = "jpg"

    else:

        extension = "jpg"

    filename = (
        f"image.{extension}"
    )

    return (
        filename,
        content,
        content_type,
    )


# =========================================================
# DANBOORU TAGS FOR DISCORD
# =========================================================

def format_danbooru_tags(
    tag_string,
):

    if not tag_string:
        return ""

    tags = tag_string.split()

    tags = [
        tag
        for tag in tags
        if not tag.startswith(
            "rating:"
        )
    ]

    tags = tags[:30]

    if not tags:
        return ""

    return " ".join(
        f"`{tag}`"
        for tag in tags
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
            "🎨 Danbooru Anime",
        ),

        "Danbooru Games": (
            DANBOORU_GAMES_WEBHOOK_URL,
            "🎮 Danbooru Games",
        ),
    }

    if source not in webhook_map:

        raise RuntimeError(
            f"Неизвестный источник: "
            f"{source}"
        )

    webhook_url, title = (
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

    if DISCORD_SPOILER:

        filename = (
            f"SPOILER_{filename}"
        )

    lines = [
        title
    ]

    if source in (
        "Danbooru Anime",
        "Danbooru Games",
    ):

        tags = format_danbooru_tags(
            image.get(
                "tags",
                "",
            )
        )

        if tags:

            lines.append(
                f"🏷️ Теги: {tags}"
            )

    lines.append(
        f"📌 Источник: {source}"
    )

    message = "\n".join(
        lines
    )

    print(
        f"[Discord] "
        f"Отправка: {source}"
    )

    print(
        f"[Discord] "
        f"Файл: {filename}"
    )

    print(
        "[Discord] Размер: "
        f"{len(image_data) / 1024 / 1024:.2f} MB"
    )

    response = requests.post(
        webhook_url,
        data={
            "content": message,
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
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    print(
        "[Discord] "
        f"Успешно отправлено: "
        f"{source}"
    )


# =========================================================
# PUBLISH SOURCE
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
        "POST: запуск публикации"
    )

    print(
        "======================================================="
    )

    sources = []

    # -----------------------------------------------------
    # WAIFU
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:

        sources.append(
            (
                "Waifu.im",
                get_random_waifu,
                WAIFU_POSTS,
            )
        )

    # -----------------------------------------------------
    # DANBOORU ANIME
    # -----------------------------------------------------

    if (
        DANBOORU_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        sources.append(
            (
                "Danbooru Anime",
                get_danbooru_anime,
                DANBOORU_ANIME_POSTS,
            )
        )

    # -----------------------------------------------------
    # DANBOORU GAMES
    # -----------------------------------------------------

    if (
        DANBOORU_GAMES_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        sources.append(
            (
                "Danbooru Games",
                get_danbooru_games,
                DANBOORU_GAMES_POSTS,
            )
        )

    if not sources:

        return Response(
            "No sources configured",
            status=500,
        )

    results = []

    # =====================================================
    # ПУБЛИКАЦИЯ
    # =====================================================

    for (
        name,
        getter,
        posts_count,
    ) in sources:

        print(
            f"[{name}] "
            f"Планируется постов: "
            f"{posts_count}"
        )

        for number in range(
            posts_count
        ):

            print(
                f"[{name}] "
                f"Пост {number + 1}/"
                f"{posts_count}"
            )

            result = publish_source(
                name,
                getter,
            )

            results.append(
                result
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
        f"{successful}, "
        f"errors: {errors}",
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

            "danbooru_games": bool(
                DANBOORU_GAMES_WEBHOOK_URL
                and DANBOORU_USERNAME
                and DANBOORU_API_KEY
            ),
        },

        "posts_per_run": {

            "waifu": WAIFU_POSTS,

            "danbooru_anime":
                DANBOORU_ANIME_POSTS,

            "danbooru_games":
                DANBOORU_GAMES_POSTS,
        },

        "danbooru": {

            "max_query_tags": 2,

            "safe_only": True,

            "explicit_queries": False,
        },

        "settings": {

            "discord_spoiler":
                DISCORD_SPOILER,

            "max_attempts":
                DANBOORU_MAX_ATTEMPTS,

            "memory_size":
                MAX_MEMORY,
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
