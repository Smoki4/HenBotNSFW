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

DISCORD_SPOILER = True

MAX_IMAGE_SIZE = 8 * 1024 * 1024

DANBOORU_MAX_ATTEMPTS = 30

MAX_MEMORY = 1500

# Games публикует 2 картинки
GAMES_POST_COUNT = 2


# =========================================================
# EXCLUDED TAGS
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
# RATE LIMIT
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
        "Получаем изображение..."
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
        "не удалось получить изображение"
    )


# =========================================================
# DANBOORU SEARCH
# =========================================================
#
# ВАЖНО:
#
# Danbooru на твоём аккаунте/endpoint сейчас
# разрешает максимум 2 TAGS за запрос.
#
# Поэтому мы НИКОГДА не отправляем:
#
# rating:e 1girl blue_lock
#
# Это 3 тега.
#
# Разрешены:
#
# rating:e
# rating:e 1girl
# rating:e blue_lock
#
# =========================================================

def get_random_danbooru(
    search_tags,
    source_name,
):
    if not DANBOORU_USERNAME:
        raise RuntimeError(
            "DANBOORU_USERNAME не настроен"
        )

    if not DANBOORU_API_KEY:
        raise RuntimeError(
            "DANBOORU_API_KEY не настроен"
        )

    # -----------------------------------------------------
    # Нормализуем теги
    # -----------------------------------------------------

    if isinstance(
        search_tags,
        str,
    ):
        tags = search_tags.split()

    else:
        tags = list(search_tags)

    tags = [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]

    # -----------------------------------------------------
    # Удаляем дубликаты
    # -----------------------------------------------------

    clean_tags = []

    for tag in tags:
        if tag not in clean_tags:
            clean_tags.append(tag)

    # -----------------------------------------------------
    # SAFE ONLY
    # -----------------------------------------------------
    #
    # rating:e — единственный rating,
    # который мы используем.
    #
    # ВАЖНО:
    # Не добавляем сюда excluded tags,
    # потому что это снова превысило бы
    # лимит в 2 тега.
    #
    # -----------------------------------------------------

    clean_tags = [
        tag
        for tag in clean_tags
        if not tag.startswith(
            "rating:"
        )
    ]

    # Максимум ОДИН дополнительный тег.
    #
    # В результате всегда:
    #
    # rating:e
    #
    # или
    #
    # rating:e 1girl
    #
    # или
    #
    # rating:e blue_lock

    selected_extra = None

    if clean_tags:
        selected_extra = clean_tags[0]

    if selected_extra:
        final_tags = (
            f"rating:e "
            f"{selected_extra}"
        )

    else:
        final_tags = "rating:e"

    print(
        f"[{source_name}] "
        f"Запрос: {final_tags}"
    )

    danbooru_wait()

    try:
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

    except Exception as error:
        print(
            f"[{source_name}] "
            f"REQUEST ERROR: {error}"
        )

        raise

    print(
        f"[{source_name}] "
        f"HTTP: "
        f"{response.status_code}"
    )

    # -----------------------------------------------------
    # DEBUG BODY
    # -----------------------------------------------------

    if response.status_code != 200:
        print(
            f"[{source_name}] BODY: "
            f"{response.text[:1500]}"
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

        if rating != "e":
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

        # -------------------------------------------------
        # EXTRA LOCAL FILTER
        # -------------------------------------------------
        #
        # Даже если API вернул что-то неожиданное,
        # проверяем запрещённые теги локально.
        #
        # -------------------------------------------------

        post_tags = set(
            tag_string.split()
        )

        forbidden = False

        for excluded in (
            DANBOORU_EXCLUDE_TAGS
        ):
            if excluded in post_tags:
                forbidden = True
                break

        if forbidden:
            continue

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
            "новых SAFE изображений "
            "не найдено"
        )

    selected = random.choice(
        candidates
    )

    remember_danbooru_id(
        selected.get("post_id")
    )

    return selected


# =========================================================
# ANIME FEMALE TAGS
# =========================================================

FEMALE_TAGS = [
    "1girl",
    "2girls",
    "3girls",
    "4girls",
    "multiple_girls",
]


# =========================================================
# ANIME FANDOMS
# =========================================================

ANIME_FANDOMS = [

    # Naruto
    "naruto",
    "naruto_shippuden",

    # One Piece
    "one_piece",

    # Bleach
    "bleach",

    # Dragon Ball
    "dragon_ball",
    "dragon_ball_z",
    "dragon_ball_super",

    # My Hero Academia
    "my_hero_academia",

    # Jujutsu Kaisen
    "jujutsu_kaisen",

    # Demon Slayer
    "kimetsu_no_yaiba",

    # Chainsaw Man
    "chainsaw_man",

    # Attack on Titan
    "shingeki_no_kyojin",

    # Sword Art Online
    "sword_art_online",

    # Re:Zero
    "re_zero_kara_hajimeru_isekai_seikatsu",

    # KonoSuba
    "konosuba",

    # Spy x Family
    "spy_x_family",

    # One Punch Man
    "one_punch_man",

    # Mob Psycho
    "mob_psycho_100",

    # Fullmetal Alchemist
    "fullmetal_alchemist",

    # Hunter x Hunter
    "hunter_x_hunter",

    # JoJo
    "jojo_no_kimyou_na_bouken",

    # Evangelion
    "neon_genesis_evangelion",

    # Cowboy Bebop
    "cowboy_bebop",

    # Code Geass
    "code_geass",

    # Death Note
    "death_note",

    # Fairy Tail
    "fairy_tail",

    # Black Clover
    "black_clover",

    # Tokyo Ghoul
    "tokyo_ghoul",

    # Blue Lock
    "blue_lock",

    # Haikyuu
    "haikyuu",

    # Frieren
    "sousou_no_frieren",

    # Oshi no Ko
    "oshi_no_ko",

    # Bocchi
    "bocchi_the_rock",

    # Kaguya
    "kaguya-sama_wa_kokurasetai",

    # Horimiya
    "horimiya",

    # Toradora
    "toradora",

    # Sailor Moon
    "sailor_moon",

    # Cardcaptor Sakura
    "cardcaptor_sakura",

    # Madoka
    "mahou_shoujo_madoka_magica",

    # Fate
    "fate/stay_night",
    "fate/grand_order",

    # Love Live
    "love_live!",

    # Idolmaster
    "the_idolm@ster",

    # Revue Starlight
    "shoujo_kageki_revue_starlight",

    # Violet Evergarden
    "violet_evergarden",

    # Mushoku Tensei
    "mushoku_tensei",

    # Overlord
    "overlord",

    # That Time I Got Reincarnated as a Slime
    "tensei_shitara_slime_datta_ken",

    # No Game No Life
    "no_game_no_life",

    # DanMachi
    "dungeon_ni_deai_wo_motomeru_no_wa_machigatteiru_darou_ka",

    # Date A Live
    "date_a_live",

    # Quintessential Quintuplets
    "5-toubun_no_hanayome",

    # Nagatoro
    "ijiranaide_nagatoro-san",

    # Komi
    "komi-san_wa_komyushou_desu",

    # Dress-Up Darling
    "sono_bisque_doll_wa_koi_wo_suru",

    # Rent-a-Girlfriend
    "kanojo_okarishimasu",

    # Spy Family
    "spy_x_family",

    # Lycoris Recoil
    "lycoris_recoil",

    # Frieren
    "sousou_no_frieren",

    # Apothecary Diaries
    "kusuriya_no_hitorigoto",

    # My Dress-Up Darling
    "sono_bisque_doll_wa_koi_wo_suru",

    # Vocaloid
    "vocaloid",
    "hatsune_miku",
    "megurine_luka",
    "kagamine_rin",
    "kagamine_len",
    "kasane_teto",

    # Hololive
    "hololive",

    # Nijisanji
    "nijisanji",

    # Touhou
    "touhou",

    # Kemono Friends
    "kemono_friends",

    # General
    "anime",
]


# =========================================================
# ANIME GETTER
# =========================================================

def get_danbooru_anime():
    attempts = []

    # -----------------------------------------------------
    # Основной вариант:
    #
    # rating:e + female tag
    #
    # -----------------------------------------------------

    for female in FEMALE_TAGS:
        attempts.append(
            female
        )

    # -----------------------------------------------------
    # Фандомы
    #
    # rating:e + fandom
    # -----------------------------------------------------

    for fandom in ANIME_FANDOMS:
        attempts.append(
            fandom
        )

    # -----------------------------------------------------
    # Перемешиваем
    # -----------------------------------------------------

    random.shuffle(
        attempts
    )

    attempts = attempts[
        :DANBOORU_MAX_ATTEMPTS
    ]

    last_error = None

    for tag in attempts:
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

    # -----------------------------------------------------
    # Последний fallback
    # -----------------------------------------------------

    fallback = [
        "1girl",
        "2girls",
        "multiple_girls",
        "anime",
    ]

    for tag in fallback:
        try:
            return get_random_danbooru(
                tag,
                "Danbooru Anime",
            )

        except Exception as error:
            last_error = error

    raise RuntimeError(
        "Danbooru Anime: "
        "не удалось найти SAFE пост"
        + (
            f": {last_error}"
            if last_error
            else ""
        )
    )


# =========================================================
# GAMES FEMALE TAGS
# =========================================================

GAME_FEMALE_TAGS = [
    "1girl",
    "2girls",
    "3girls",
    "multiple_girls",
]


# =========================================================
# GAME FANDOMS
# =========================================================

GAME_FANDOMS = [

    # -----------------------------------------------------
    # HOYOVERSE
    # -----------------------------------------------------

    "genshin_impact",
    "honkai_star_rail",
    "honkai_impact_3rd",
    "zenless_zone_zero",
    "tears_of_themis",

    # -----------------------------------------------------
    # NINTENDO
    # -----------------------------------------------------

    "pokemon",
    "super_mario",
    "the_legend_of_zelda",
    "fire_emblem",
    "splatoon",
    "animal_crossing",
    "kirby",
    "metroid",

    # -----------------------------------------------------
    # RPG
    # -----------------------------------------------------

    "final_fantasy",
    "final_fantasy_vii",
    "final_fantasy_xiv",
    "persona",
    "persona_5",
    "shin_megami_tensei",
    "nier_automata",
    "nier_reincarnation",
    "dragon_quest",
    "kingdom_hearts",
    "octopath_traveler",
    "baldurs_gate_3",
    "divinity_original_sin",
    "pathfinder",

    # -----------------------------------------------------
    # SOULS
    # -----------------------------------------------------

    "elden_ring",
    "dark_souls",
    "bloodborne",
    "sekiro",
    "armored_core",
    "devil_may_cry",
    "bayonetta",
    "monster_hunter",

    # -----------------------------------------------------
    # FIGHTING
    # -----------------------------------------------------

    "street_fighter",
    "tekken",
    "guilty_gear",
    "mortal_kombat",
    "king_of_fighters",
    "soulcalibur",

    # -----------------------------------------------------
    # SHOOTERS
    # -----------------------------------------------------

    "overwatch",
    "valorant",
    "apex_legends",
    "fortnite",
    "halo",
    "destiny",
    "doom",
    "quake",
    "borderlands",
    "team_fortress_2",
    "counter-strike",

    # -----------------------------------------------------
    # MOBA
    # -----------------------------------------------------

    "league_of_legends",
    "dota_2",
    "heroes_of_the_storm",

    # -----------------------------------------------------
    # HORROR
    # -----------------------------------------------------

    "resident_evil",
    "silent_hill",
    "fatal_frame",
    "dead_by_daylight",
    "five_nights_at_freddys",
    "fnaf",

    # -----------------------------------------------------
    # SURVIVAL
    # -----------------------------------------------------

    "minecraft",
    "terraria",
    "stardew_valley",
    "dont_starve",
    "subnautica",
    "valheim",
    "rust",
    "ark_survival_evolved",

    # -----------------------------------------------------
    # SCI-FI
    # -----------------------------------------------------

    "cyberpunk_2077",
    "fallout",
    "starfield",
    "mass_effect",
    "warframe",
    "starcraft",

    # -----------------------------------------------------
    # RPG / ADVENTURE
    # -----------------------------------------------------

    "the_witcher",
    "skyrim",
    "the_elder_scrolls",
    "dragon_age",
    "tales_of_series",
    "xenoblade_chronicles",

    # -----------------------------------------------------
    # INDIE
    # -----------------------------------------------------

    "undertale",
    "deltarune",
    "omori",
    "hollow_knight",
    "cuphead",
    "hotline_miami",
    "risk_of_rain",
    "hades",
    "hades_ii",

    # -----------------------------------------------------
    # OTHER
    # -----------------------------------------------------

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
    "punishing_gray_raven",

    # -----------------------------------------------------
    # GENERAL
    # -----------------------------------------------------

    "video_games",
    "game_character",
    "game_art",
]


# =========================================================
# GAME GETTER
# =========================================================

def get_danbooru_games():
    attempts = []

    # Женские запросы
    for tag in GAME_FEMALE_TAGS:
        attempts.append(tag)

    # Игровые фандомы
    for fandom in GAME_FANDOMS:
        attempts.append(fandom)

    random.shuffle(
        attempts
    )

    attempts = attempts[
        :DANBOORU_MAX_ATTEMPTS
    ]

    last_error = None

    for tag in attempts:
        try:
            result = (
                get_random_danbooru(
                    tag,
                    "Danbooru Games",
                )
            )

            print(
                "[Danbooru Games] "
                "Новый SAFE пост найден"
            )

            return result

        except Exception as error:
            last_error = error

            print(
                "[Danbooru Games] "
                f"Запрос пропущен: "
                f"{error}"
            )

    fallback = [
        "1girl",
        "2girls",
        "multiple_girls",
        "video_games",
    ]

    for tag in fallback:
        try:
            return get_random_danbooru(
                tag,
                "Danbooru Games",
            )

        except Exception as error:
            last_error = error

    raise RuntimeError(
        "Danbooru Games: "
        "не удалось найти SAFE пост"
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

            if (
                total
                > MAX_IMAGE_SIZE
            ):
                raise RuntimeError(
                    "Изображение больше 8 MB"
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
# DISCORD TAGS
# =========================================================

def format_danbooru_tags(
    tag_string
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
        "POST: запуск публикации"
    )

    print(
        "======================================================="
    )

    results = []

    # -----------------------------------------------------
    # WAIFU
    # -----------------------------------------------------

    if WAIFU_WEBHOOK_URL:
        results.append(
            publish_source(
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
        results.append(
            publish_source(
                "Danbooru Anime",
                get_danbooru_anime,
            )
        )

    # -----------------------------------------------------
    # DANBOORU GAMES
    # -----------------------------------------------------
    #
    # Публикуем 2 раза.
    #
    # -----------------------------------------------------

    if (
        DANBOORU_GAMES_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):
        for game_index in range(
            GAMES_POST_COUNT
        ):
            print(
                "[Danbooru Games] "
                f"Публикация "
                f"{game_index + 1}/"
                f"{GAMES_POST_COUNT}"
            )

            results.append(
                publish_source(
                    "Danbooru Games",
                    get_danbooru_games,
                )
            )

    # -----------------------------------------------------
    # RESULTS
    # -----------------------------------------------------

    if not results:
        return Response(
            "No sources configured",
            status=500,
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
            "safe_only": True,

            "allowed_rating": "s",

            "female_tags": [
                "1girl",
                "2girls",
                "3girls",
                "4girls",
                "multiple_girls",
            ],

            "excluded_tags": (
                get_exclude_tags()
            ),

            "games_posts_per_request": (
                GAMES_POST_COUNT
            ),

            "max_attempts": (
                DANBOORU_MAX_ATTEMPTS
            ),

            "memory_size": (
                MAX_MEMORY
            ),

            "danbooru_max_tags": 2,
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
