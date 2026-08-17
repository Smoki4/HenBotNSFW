
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

# Можно оставить старое имя переменной Render.
# Теперь этот webhook используется для Danbooru Games.
DANBOORU_GAMES_WEBHOOK_URL = (
    os.environ.get(
        "DISCORD_WEBHOOK_DANBOORU_GAMES"
    )
    or os.environ.get(
        "DISCORD_WEBHOOK_RULE34_GAMES"
    )
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

# Максимальный размер файла Discord.
MAX_IMAGE_SIZE = 8 * 1024 * 1024

# Сколько запросов максимум пробовать
# при поиске Danbooru.
DANBOORU_MAX_ATTEMPTS = 20

# Сколько ID помнить в памяти.
MAX_MEMORY = 1500


# =========================================================
# НЕЖЕЛАТЕЛЬНЫЕ ТЕГИ
# =========================================================
#
# Эти теги автоматически добавляются
# как отрицательные Danbooru-теги.
#
# Например:
# gore -> -gore
# =========================================================

DANBOORU_EXCLUDE_TAGS = [
    "gore",
    "blood",
    "scat",
    "feces",
    "vomit",
    "vore",
]


def get_exclude_tags():
    result = []

    for tag in DANBOORU_EXCLUDE_TAGS:
        tag = str(tag).strip()

        if not tag:
            continue

        if tag.startswith("-"):
            result.append(tag)
        else:
            result.append(
                f"-{tag}"
            )

    return result


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

DANBOORU_MEMORY_LOCK = (
    threading.Lock()
)


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
            1.2 - elapsed
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

    exclude_tags = (
        get_exclude_tags()
    )

    final_tags = (
        f"{base_tags} "
        f"{' '.join(exclude_tags)}"
    ).strip()

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

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(
            f"{source_name}: "
            "некорректный ответ API"
        )

    candidates = []

    for post in data:
        post_id = post.get("id")

        if danbooru_id_used(
            post_id
        ):
            continue

        # -------------------------------------------------
        # SAFE ONLY
        # -------------------------------------------------

        rating = str(
            post.get(
                "rating",
                "",
            )
        ).lower()

        if rating != "s":
            continue

        # -------------------------------------------------
        # IMAGE URL
        # -------------------------------------------------

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

        # -------------------------------------------------
        # TAGS
        # -------------------------------------------------

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
        selected.get("post_id")
    )

    return selected


# =========================================================
# DANBOORU ANIME
# =========================================================

DANBOORU_ANIME_TAGS = [
    # Общие
    "rating:explicit anime",
    "rating:explicit 1girl",
    "rating:explicit 1boy",
    "rating:explicit solo",
    "rating:explicit duo",
    "rating:explicit multiple_girls",
    "rating:explicit scenery",
    "rating:explicit landscape",
    "rating:explicit fantasy",
    "rating:explicit school_uniform",
    "rating:explicit animal_ears",
    "rating:explicit furry",

    # Naruto
    "rating:explicit naruto",
    "rating:explicit naruto_shippuden",

    # One Piece
    "rating:explicit one_piece",

    # Bleach
    "rating:explicit bleach",

    # Dragon Ball
    "rating:explicit dragon_ball",
    "rating:explicit dragon_ball_z",
    "rating:explicit dragon_ball_super",

    # My Hero Academia
    "rating:explicit my_hero_academia",

    # Jujutsu Kaisen
    "rating:explicit jujutsu_kaisen",

    # Demon Slayer
    "rating:explicit kimetsu_no_yaiba",

    # Chainsaw Man
    "rating:explicit chainsaw_man",

    # Attack on Titan
    "rating:explicit shingeki_no_kyojin",

    # Sword Art Online
    "rating:explicit sword_art_online",

    # Re:Zero
    "rating:explicit re_zero_kara_hajimeru_isekai_seikatsu",

    # KonoSuba
    "rating:explicit konosuba",

    # Spy x Family
    "rating:explicit spy_x_family",

    # One Punch Man
    "rating:explicit one_punch_man",

    # Mob Psycho
    "rating:explicit mob_psycho_100",

    # Fullmetal Alchemist
    "rating:explicit fullmetal_alchemist",

    # Hunter x Hunter
    "rating:explicit hunter_x_hunter",

    # JoJo
    "rating:explicit jojo_no_kimyou_na_bouken",

    # Evangelion
    "rating:explicit neon_genesis_evangelion",

    # Cowboy Bebop
    "rating:explicit cowboy_bebop",

    # Code Geass
    "rating:explicit code_geass",

    # Death Note
    "rating:explicit death_note",

    # Fairy Tail
    "rating:explicit fairy_tail",

    # Black Clover
    "rating:explicit black_clover",

    # Tokyo Ghoul
    "rating:explicit tokyo_ghoul",

    # Blue Lock
    "rating:explicit blue_lock",

    # Haikyuu
    "rating:explicit haikyuu",

    # Frieren
    "rating:explicit sousou_no_frieren",

    # Oshi no Ko
    "rating:explicit oshi_no_ko",

    # Bocchi
    "rating:explicit bocchi_the_rock",

    # Kaguya
    "rating:explicit kaguya-sama_wa_kokurasetai",

    # Horimiya
    "rating:explicit horimiya",

    # Vocaloid
    "rating:explicit vocaloid",
    "rating:explicit hatsune_miku",
    "rating:explicit megurine_luka",
    "rating:explicit kagamine_rin",
    "rating:explicit kagamine_len",
    "rating:explicit kasane_teto",

    # VTubers
    "rating:explicit hololive",
    "rating:explicit nijisanji",

    # Уши / furry
    "rating:explicit kemonomimi",
    "rating:explicit animal_ears",
    "rating:explicit cat_ears",
    "rating:explicit fox_ears",
    "rating:explicit bunny_ears",
    "rating:explicit furry",

    # Fantasy
    "rating:explicit magic",
    "rating:explicit knight",
    "rating:explicit samurai",
    "rating:explicit ninja",
    "rating:explicit vampire",
    "rating:explicit witch",
    "rating:explicit dragon",

    # Sci-fi
    "rating:explicit cyberpunk",
    "rating:explicit steampunk",
    "rating:explicit mecha",
    "rating:explicit robot",

    # Атмосфера
    "rating:explicit beach",
    "rating:explicit cityscape",
    "rating:explicit night",
    "rating:explicit sunset",
]


def get_danbooru_anime():
    tags_list = (
        DANBOORU_ANIME_TAGS[:]
    )

    random.shuffle(tags_list)

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for base_tags in tags_list[
        :attempts
    ]:
        try:
            result = (
                get_random_danbooru(
                    base_tags,
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

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    fallback_queries = [
        "rating:explicit anime",
        "rating:explicit solo",
        "rating:explicit 1girl",
        "rating:explicit 1boy",
        "rating:explicit scenery",
    ]

    for base_tags in fallback_queries:
        try:
            return get_random_danbooru(
                base_tags,
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
    # -----------------------------------------------------
    # HOYOVERSE
    # -----------------------------------------------------

    "rating:explicit genshin_impact",
    "rating:explicit honkai_star_rail",
    "rating:explicit honkai_impact_3rd",
    "rating:explicit zenless_zone_zero",
    "rating:explicit tears_of_themis",

    # -----------------------------------------------------
    # POKEMON / NINTENDO
    # -----------------------------------------------------

    "rating:explicit pokemon",
    "rating:explicit super_mario",
    "rating:explicit the_legend_of_zelda",
    "rating:explicit fire_emblem",
    "rating:explicit splatoon",
    "rating:explicit animal_crossing",
    "rating:explicit kirby",
    "rating:explicit metroid",

    # -----------------------------------------------------
    # RPG
    # -----------------------------------------------------

    "rating:explicit final_fantasy",
    "rating:explicit final_fantasy_vii",
    "rating:explicit final_fantasy_xiv",
    "rating:explicit persona",
    "rating:explicit persona_5",
    "rating:explicit shin_megami_tensei",
    "rating:explicit nier_automata",
    "rating:explicit nier_reincarnation",
    "rating:explicit dragon_quest",
    "rating:explicit kingdom_hearts",
    "rating:explicit octopath_traveler",
    "rating:explicit baldurs_gate_3",
    "rating:explicit divinity_original_sin",
    "rating:explicit pathfinder",

    # -----------------------------------------------------
    # SOULS / ACTION
    # -----------------------------------------------------

    "rating:explicit elden_ring",
    "rating:explicit dark_souls",
    "rating:explicit bloodborne",
    "rating:explicit sekiro",
    "rating:explicit armored_core",
    "rating:explicit devil_may_cry",
    "rating:explicit bayonetta",
    "rating:explicit monster_hunter",

    # -----------------------------------------------------
    # FIGHTING
    # -----------------------------------------------------

    "rating:explicit street_fighter",
    "rating:explicit tekken",
    "rating:explicit guilty_gear",
    "rating:explicit mortal_kombat",
    "rating:explicit king_of_fighters",
    "rating:explicit soulcalibur",

    # -----------------------------------------------------
    # SHOOTERS
    # -----------------------------------------------------

    "rating:explicit overwatch",
    "rating:explicit valorant",
    "rating:explicit apex_legends",
    "rating:explicit fortnite",
    "rating:explicit halo",
    "rating:explicit destiny",
    "rating:explicit doom",
    "rating:explicit quake",
    "rating:explicit borderlands",
    "rating:explicit team_fortress_2",
    "rating:explicit counter-strike",

    # -----------------------------------------------------
    # MOBA
    # -----------------------------------------------------

    "rating:explicit league_of_legends",
    "rating:explicit dota_2",
    "rating:explicit heroes_of_the_storm",

    # -----------------------------------------------------
    # HORROR
    # -----------------------------------------------------

    "rating:explicit resident_evil",
    "rating:explicit silent_hill",
    "rating:explicit fatal_frame",
    "rating:explicit dead_by_daylight",
    "rating:explicit five_nights_at_freddys",
    "rating:explicit fnaf",

    # -----------------------------------------------------
    # SURVIVAL / SANDBOX
    # -----------------------------------------------------

    "rating:explicit minecraft",
    "rating:explicit terraria",
    "rating:explicit stardew_valley",
    "rating:explicit dont_starve",
    "rating:explicit subnautica",
    "rating:explicit valheim",
    "rating:explicit rust",
    "rating:explicit ark_survival_evolved",

    # -----------------------------------------------------
    # SCI-FI
    # -----------------------------------------------------

    "rating:explicit cyberpunk_2077",
    "rating:explicit fallout",
    "rating:explicit starfield",
    "rating:explicit mass_effect",
    "rating:explicit warframe",
    "rating:explicit starcraft",

    # -----------------------------------------------------
    # RPG / ADVENTURE
    # -----------------------------------------------------

    "rating:explicit the_witcher",
    "rating:explicit skyrim",
    "rating:explicit the_elder_scrolls",
    "rating:explicit dragon_age",
    "rating:explicit tales_of_series",
    "rating:explicit xenoblade_chronicles",

    # -----------------------------------------------------
    # INDIE
    # -----------------------------------------------------

    "rating:explicit undertale",
    "rating:explicit deltarune",
    "rating:explicit omori",
    "rating:explicit hollow_knight",
    "rating:explicit cuphead",
    "rating:explicit hotline_miami",
    "rating:explicit risk_of_rain",
    "rating:explicit hades",
    "rating:explicit hades_ii",

    # -----------------------------------------------------
    # OTHER
    # -----------------------------------------------------

    "rating:explicit portal",
    "rating:explicit half-life",
    "rating:explicit sonic_the_hedgehog",
    "rating:explicit ace_attorney",
    "rating:explicit danganronpa",
    "rating:explicit project_sekai",
    "rating:explicit blue_archive",
    "rating:explicit arknights",
    "rating:explicit azur_lane",
    "rating:explicit girls_frontline",
    "rating:explicit nikke",
    "rating:explicit punishing_gray_raven",

    # -----------------------------------------------------
    # Общие игровые теги
    # -----------------------------------------------------

    "rating:explicit game",
    "rating:explicit video_games",
    "rating:explicit game_character",
    "rating:explicit game_art",
    "rating:explicit furry",
]


def get_danbooru_games():
    tags_list = (
        DANBOORU_GAME_TAGS[:]
    )

    random.shuffle(tags_list)

    last_error = None

    attempts = min(
        DANBOORU_MAX_ATTEMPTS,
        len(tags_list),
    )

    for base_tags in tags_list[
        :attempts
    ]:
        try:
            result = (
                get_random_danbooru(
                    base_tags,
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

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    fallback_queries = [
        "rating:explicit game",
        "rating:explicit video_games",
        "rating:explicit game_character",
        "rating:explicit furry",
    ]

    for base_tags in fallback_queries:
        try:
            return get_random_danbooru(
                base_tags,
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

            if (
                total
                > MAX_IMAGE_SIZE
            ):
                raise RuntimeError(
                    "Изображение "
                    "больше 8 MB"
                )

            chunks.append(chunk)

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

    # Убираем rating:explicit и прочие
    # технические rating-теги.
    tags = [
        tag
        for tag in tags
        if not tag.startswith(
            "rating:"
        )
    ]

    # Максимум 30 тегов,
    # чтобы сообщение Discord
    # не получилось огромным.
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

    # -----------------------------------------------------
    # DISCORD SPOILER
    # -----------------------------------------------------

    if DISCORD_SPOILER:
        filename = (
            f"SPOILER_{filename}"
        )

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    lines = [
        title
    ]

    # -----------------------------------------------------
    # TAGS
    # -----------------------------------------------------

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
    # WAIFU.IM
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:
        sources.append(
            (
                "Waifu.im",
                get_random_waifu,
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

        "settings": {
            "discord_spoiler": (
                DISCORD_SPOILER
            ),

            "excluded_tags": (
                get_exclude_tags()
            ),

            "max_attempts": (
                DANBOORU_MAX_ATTEMPTS
            ),

            "memory_size": (
                MAX_MEMORY
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

