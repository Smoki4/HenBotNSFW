import os
import random
import threading
import time
import uuid

import requests
from flask import Flask, Response, jsonify


# =========================================================
# APP
# =========================================================

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
# SETTINGS
# =========================================================

# Discord
DISCORD_MAX_RETRIES = 4

# Минимальная пауза между Discord POST.
DISCORD_SEND_DELAY = 6.0

# Небольшой случайный интервал поверх основной задержки.
DISCORD_JITTER_MIN = 0.5
DISCORD_JITTER_MAX = 2.0


# Danbooru
DANBOORU_SEND_DELAY = 2.0


# Максимальный размер изображения.
MAX_IMAGE_SIZE = 19 * 1024 * 1024


# Отправлять картинки как spoiler.
DISCORD_SPOILER = True


# Сколько Danbooru ID помнить.
MAX_MEMORY = 3000


# =========================================================
# NUMBER OF POSTS
# =========================================================

WAIFU_POSTS = 1

DANBOORU_ANIME_POSTS = 1

DANBOORU_GAMES_POSTS = 2


# =========================================================
# API
# =========================================================

DANBOORU_API = (
    "https://danbooru.donmai.us"
)

WAIFU_API = (
    "https://api.waifu.im/images"
)


# =========================================================
# HTTP SESSION
# =========================================================

HTTP = requests.Session()


# =========================================================
# HEADERS
# =========================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "GamePoster/5.0"
    ),
    "Accept": "*/*",
}


DANBOORU_HEADERS = {
    "User-Agent": (
        "GamePoster/5.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


# =========================================================
# LOCKS
# =========================================================

PUBLICATION_LOCK = threading.Lock()

DISCORD_LOCK = threading.Lock()

DANBOORU_LOCK = threading.Lock()

DANBOORU_MEMORY_LOCK = threading.Lock()

CURRENT_RUN_LOCK = threading.Lock()

OUTGOING_IP_LOCK = threading.Lock()


# =========================================================
# GLOBAL STATE
# =========================================================

LAST_DISCORD_SEND = 0.0

LAST_DANBOORU_REQUEST = 0.0

DANBOORU_USED_IDS = set()

CURRENT_RUN_ID = None

CURRENT_RUN_STARTED = None

OUTGOING_IP = None


# =========================================================
# HELPERS
# =========================================================

def new_run_id():

    return uuid.uuid4().hex[:10]


def now_string():

    return time.strftime(
        "%Y-%m-%d %H:%M:%S UTC",
        time.gmtime(),
    )


# =========================================================
# OUTGOING IP
# =========================================================

def get_outgoing_ip():

    global OUTGOING_IP

    with OUTGOING_IP_LOCK:

        if OUTGOING_IP is not None:

            return OUTGOING_IP

        try:

            response = HTTP.get(
                "https://api.ipify.org",
                timeout=10,
            )

            response.raise_for_status()

            OUTGOING_IP = (
                response.text.strip()
            )

        except Exception as error:

            print(
                "[DEBUG] "
                f"Unable to determine outgoing IP: "
                f"{error}"
            )

            OUTGOING_IP = "unknown"

        return OUTGOING_IP


# =========================================================
# DANBOORU MEMORY
# =========================================================

def remember_id(post_id):

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


def was_used(post_id):

    if post_id is None:

        return False

    with DANBOORU_MEMORY_LOCK:

        return (
            str(post_id)
            in DANBOORU_USED_IDS
        )


# =========================================================
# DANBOORU WAIT
# =========================================================

def danbooru_wait():

    global LAST_DANBOORU_REQUEST

    with DANBOORU_LOCK:

        now = time.monotonic()

        elapsed = (
            now
            - LAST_DANBOORU_REQUEST
        )

        wait_time = (
            DANBOORU_SEND_DELAY
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
# DISCORD WAIT
# =========================================================

def discord_wait():

    global LAST_DISCORD_SEND

    with DISCORD_LOCK:

        now = time.monotonic()

        elapsed = (
            now
            - LAST_DISCORD_SEND
        )

        wait_time = (
            DISCORD_SEND_DELAY
            - elapsed
        )

        if wait_time > 0:

            time.sleep(
                wait_time
            )

        jitter = random.uniform(
            DISCORD_JITTER_MIN,
            DISCORD_JITTER_MAX,
        )

        time.sleep(
            jitter
        )

        LAST_DISCORD_SEND = (
            time.monotonic()
        )


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu(run_id):

    print(
        f"[{run_id}] "
        "[Waifu.im] "
        "Requesting image..."
    )

    for attempt in range(1, 6):

        try:

            response = HTTP.get(
                WAIFU_API,
                params={
                    "OrderBy": "Random",
                    "PageSize": 1,
                    "IsNsfw": "True",
                },
                headers=DEFAULT_HEADERS,
                timeout=30,
            )

            print(
                f"[{run_id}] "
                "[Waifu.im] HTTP "
                f"{response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            items = data.get(
                "items",
                [],
            )

            if not items:

                raise RuntimeError(
                    "Waifu.im returned "
                    "no images"
                )

            item = items[0]

            image_url = item.get(
                "url"
            )

            if not image_url:

                raise RuntimeError(
                    "Waifu.im returned "
                    "no image URL"
                )

            return {
                "url": image_url,
                "source": "Waifu.im",
                "tags": [],
            }

        except Exception as error:

            print(
                f"[{run_id}] "
                "[Waifu.im] "
                f"Attempt {attempt}: "
                f"{error}"
            )

            if attempt < 5:

                time.sleep(
                    2 + attempt
                )

    raise RuntimeError(
        "Waifu.im failed "
        "after 5 attempts"
    )


# =========================================================
# DANBOORU
# =========================================================

def get_random_danbooru(
    tags,
    source_name,
    run_id,
):

    if not DANBOORU_USERNAME:

        raise RuntimeError(
            "DANBOORU_USERNAME "
            "is not configured"
        )

    if not DANBOORU_API_KEY:

        raise RuntimeError(
            "DANBOORU_API_KEY "
            "is not configured"
        )

    print(
        f"[{run_id}] "
        f"[{source_name}] "
        f"Query: {tags}"
    )

    danbooru_wait()

    response = HTTP.get(
        f"{DANBOORU_API}/posts.json",
        params={
            "limit": 100,
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
        f"[{run_id}] "
        f"[{source_name}] HTTP "
        f"{response.status_code}"
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            f"{source_name}: "
            "invalid API response"
        )

    candidates = []

    for post in data:

        post_id = post.get(
            "id"
        )

        if was_used(post_id):

            continue

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

        lowered = (
            image_url.lower()
        )

        if not any(
            ext in lowered
            for ext in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        ):

            continue

        candidates.append(
            {
                "url": image_url,
                "source": source_name,
                "post_id": post_id,
                "tags": post.get(
                    "tag_string",
                    "",
                ),
            }
        )

    if not candidates:

        raise RuntimeError(
            f"{source_name}: "
            "no unused images found"
        )

    selected = random.choice(
        candidates
    )

    remember_id(
        selected["post_id"]
    )

    print(
        f"[{run_id}] "
        f"[{source_name}] "
        f"Selected Danbooru ID="
        f"{selected['post_id']}"
    )

    return selected


# =========================================================
# DANBOORU ANIME TAGS
# =========================================================

DANBOORU_ANIME_TAGS = [

    "rating:explicit anime",

    "rating:explicit 1girl",

    "rating:explicit 1boy",

    "rating:explicit solo",

    "rating:explicit 2girls",

    "rating:explicit scenery",

    "rating:explicit landscape",

    "rating:explicit fantasy",

    "rating:explicit school_uniform",

    "rating:explicit animal_ears",

    "rating:explicit furry",

    "rating:explicit vocaloid",

    "rating:explicit hatsune_miku",

    "rating:explicit megurine_luka",

    "rating:explicit naruto",

    "rating:explicit one_piece",

    "rating:explicit bleach",

    "rating:explicit re_zero",

    "rating:explicit konosuba",

    "rating:explicit genshin_impact",

    "rating:explicit honkai_star_rail",

    "rating:explicit zenless_zone_zero",

    "rating:explicit pokemon",

    "rating:explicit persona",

    "rating:explicit final_fantasy",

    "rating:explicit cyberpunk_2077",

    "rating:explicit minecraft",
]


# =========================================================
# DANBOORU GAME TAGS
# =========================================================

DANBOORU_GAME_TAGS = [

    "rating:explicit genshin_impact",

    "rating:explicit honkai_star_rail",

    "rating:explicit zenless_zone_zero",

    "rating:explicit minecraft",

    "rating:explicit apex_legends",

    "rating:explicit overwatch",

    "rating:explicit fortnite",

    "rating:explicit pokemon",

    "rating:explicit persona_5",

    "rating:explicit cyberpunk_2077",

    "rating:explicit resident_evil",

    "rating:explicit nier_automata",

    "rating:explicit devil_may_cry",

    "rating:explicit final_fantasy",

    "rating:explicit the_witcher",

    "rating:explicit elden_ring",

    "rating:explicit dark_souls",

    "rating:explicit mortal_kombat",

    "rating:explicit street_fighter",

    "rating:explicit tekken",

    "rating:explicit guilty_gear",

    "rating:explicit skullgirls",

    "rating:explicit arknights",

    "rating:explicit wuthering_waves",

    "rating:explicit dead_by_daylight",

    "rating:explicit dota_2",

    "rating:explicit pubg",

    "rating:explicit team_fortress_2",

    "rating:explicit fallout",

    "rating:explicit warhammer_40k",
]


# =========================================================
# DANBOORU GETTERS
# =========================================================

def get_danbooru_anime(
    run_id,
):

    tags = random.choice(
        DANBOORU_ANIME_TAGS
    )

    return get_random_danbooru(
        tags,
        "Danbooru Anime",
        run_id,
    )


def get_danbooru_games(
    run_id,
):

    tags = random.choice(
        DANBOORU_GAME_TAGS
    )

    return get_random_danbooru(
        tags,
        "Danbooru Games",
        run_id,
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(
    image_url,
    run_id,
):

    print(
        f"[{run_id}] "
        "[Image] "
        f"Downloading {image_url}"
    )

    response = HTTP.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=60,
        stream=True,
    )

    print(
        f"[{run_id}] "
        "[Image] HTTP "
        f"{response.status_code}"
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
                    "Image exceeds "
                    f"{MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB"
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
                    "Image exceeds "
                    f"{MAX_IMAGE_SIZE / 1024 / 1024:.0f} MB"
                )

            chunks.append(
                chunk
            )

    finally:

        response.close()

    image_data = b"".join(
        chunks
    )

    if not image_data:

        raise RuntimeError(
            "Downloaded image is empty"
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

    else:

        extension = "jpg"

    filename = (
        "SPOILER_image."
        if DISCORD_SPOILER
        else "image."
    )

    filename += extension

    return (
        filename,
        image_data,
        content_type,
    )


# =========================================================
# CLOUDFLARE DETECTION
# =========================================================

def is_cloudflare_response(
    response,
):

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
        .lower()
    )

    body = (
        response.text[:10000]
        .lower()
    )

    if (
        "text/html"
        not in content_type
    ):

        return False

    indicators = (
        "cloudflare",
        "access denied",
        "used cloudflare",
        "cf-ray",
        "attention required",
    )

    return any(
        item in body
        for item in indicators
    )


# =========================================================
# CLOUDFLARE DEBUG
# =========================================================

def print_cloudflare_debug(
    response,
    run_id,
    source_name,
):

    print()
    print(
        "======================================================="
    )

    print(
        f"[{run_id}] "
        f"[{source_name}] "
        "CLOUDFLARE DEBUG"
    )

    print(
        "-------------------------------------------------------"
    )

    print(
        f"[{run_id}] "
        f"HTTP: "
        f"{response.status_code}"
    )

    print(
        f"[{run_id}] "
        f"URL: "
        f"{response.url}"
    )

    print(
        f"[{run_id}] "
        f"Reason: "
        f"{response.reason}"
    )

    print(
        f"[{run_id}] "
        f"Content-Type: "
        f"{response.headers.get('Content-Type')}"
    )

    print(
        f"[{run_id}] "
        f"Server: "
        f"{response.headers.get('Server')}"
    )

    print(
        f"[{run_id}] "
        f"CF-Ray: "
        f"{response.headers.get('CF-Ray')}"
    )

    print(
        f"[{run_id}] "
        f"CF-Cache-Status: "
        f"{response.headers.get('CF-Cache-Status')}"
    )

    print(
        f"[{run_id}] "
        f"Retry-After: "
        f"{response.headers.get('Retry-After')}"
    )

    print(
        "-------------------------------------------------------"
    )

    print(
        f"[{run_id}] "
        "HEADERS:"
    )

    for key, value in response.headers.items():

        print(
            f"[{run_id}] "
            f"{key}: {value}"
        )

    print(
        "-------------------------------------------------------"
    )

    print(
        f"[{run_id}] "
        "BODY:"
    )

    print(
        response.text[:5000]
    )

    print(
        "======================================================="
    )

    print()


# =========================================================
# DISCORD RETRY DELAY
# =========================================================

def get_retry_delay(
    response,
    attempt,
):

    retry_after = (
        response.headers.get(
            "Retry-After"
        )
    )

    if retry_after:

        try:

            return max(
                float(retry_after),
                1.0,
            )

        except (
            ValueError,
            TypeError,
        ):

            pass

    try:

        body = response.json()

        if isinstance(
            body,
            dict,
        ):

            retry_after = body.get(
                "retry_after"
            )

            if retry_after is not None:

                return max(
                    float(retry_after),
                    1.0,
                )

    except Exception:

        pass

    return min(
        5.0 * (2 ** attempt),
        120.0,
    )


# =========================================================
# DISCORD REQUEST
# =========================================================

def discord_request(
    webhook_url,
    data,
    files,
    run_id,
    source_name,
):

    for attempt in range(
        1,
        DISCORD_MAX_RETRIES + 1,
    ):

        print(
            f"[{run_id}] "
            f"[{source_name}] "
            f"Discord attempt "
            f"{attempt}/"
            f"{DISCORD_MAX_RETRIES}"
        )

        discord_wait()

        try:

            response = HTTP.post(
                webhook_url,
                data=data,
                files=files,
                timeout=90,
            )

        except requests.RequestException as error:

            print(
                f"[{run_id}] "
                f"[{source_name}] "
                f"Network error: {error}"
            )

            if (
                attempt
                >= DISCORD_MAX_RETRIES
            ):

                raise RuntimeError(
                    f"Discord network error: "
                    f"{error}"
                )

            wait_time = min(
                10.0 * (
                    2 ** (attempt - 1)
                ),
                120.0,
            )

            time.sleep(
                wait_time
            )

            continue

        print(
            f"[{run_id}] "
            f"[{source_name}] "
            f"Discord HTTP "
            f"{response.status_code}"
        )

        print(
            f"[{run_id}] "
            f"[{source_name}] "
            f"CF-Ray="
            f"{response.headers.get('CF-Ray')}"
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        if response.status_code in (
            200,
            204,
        ):

            print(
                f"[{run_id}] "
                f"[{source_name}] "
                "DISCORD SUCCESS"
            )

            return {
                "success": True,
                "status": response.status_code,
            }

        # -------------------------------------------------
        # CLOUDFLARE
        # -------------------------------------------------

        if is_cloudflare_response(
            response
        ):

            print_cloudflare_debug(
                response,
                run_id,
                source_name,
            )

            raise RuntimeError(
                "Cloudflare blocked "
                "Discord request"
            )

        # -------------------------------------------------
        # RATE LIMIT
        # -------------------------------------------------

        if response.status_code == 429:

            wait_time = (
                get_retry_delay(
                    response,
                    attempt - 1,
                )
            )

            print(
                f"[{run_id}] "
                f"[{source_name}] "
                f"Discord 429. "
                f"Retry after "
                f"{wait_time:.1f}s"
            )

            if (
                attempt
                < DISCORD_MAX_RETRIES
            ):

                time.sleep(
                    wait_time
                )

                continue

        # -------------------------------------------------
        # OTHER ERROR
        # -------------------------------------------------

        print(
            f"[{run_id}] "
            f"[{source_name}] "
            "Discord response:"
        )

        print(
            response.text[:3000]
        )

        raise RuntimeError(
            f"Discord HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    raise RuntimeError(
        "Discord retry limit reached"
    )


# =========================================================
# SEND TO DISCORD
# =========================================================

def send_to_discord(
    image,
    run_id,
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

        "Danbooru Games": (
            DANBOORU_GAMES_WEBHOOK_URL,
            "🎮 Game Art",
        ),
    }

    if source not in webhook_map:

        raise RuntimeError(
            f"Unknown source: {source}"
        )

    webhook_url, message = (
        webhook_map[source]
    )

    if not webhook_url:

        raise RuntimeError(
            f"Webhook not configured "
            f"for {source}"
        )

    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    (
        filename,
        image_data,
        content_type,
    ) = download_image(
        image_url,
        run_id,
    )

    print(
        f"[{run_id}] "
        f"[{source}] "
        f"Image size="
        f"{len(image_data) / 1024 / 1024:.2f} MB"
    )

    # -----------------------------------------------------
    # TAGS
    # -----------------------------------------------------

    raw_tags = image.get(
        "tags",
        "",
    )

    if isinstance(
        raw_tags,
        str,
    ):

        tag_list = [
            tag.strip()
            for tag in raw_tags.split()
            if tag.strip()
        ]

    else:

        tag_list = []

    tag_list = tag_list[:30]

    if tag_list:

        tags_text = (
            "\n🏷️ Теги: "
            + ", ".join(
                f"`{tag}`"
                for tag in tag_list
            )
        )

    else:

        tags_text = ""

    # -----------------------------------------------------
    # DANBOORU ID
    # -----------------------------------------------------

    post_id = image.get(
        "post_id"
    )

    if post_id:

        source_text = (
            f"Источник: {source}\n"
            f"Post ID: {post_id}"
        )

    else:

        source_text = (
            f"Источник: {source}"
        )

    content = (
        f"{message}\n"
        f"{source_text}"
        f"{tags_text}"
    )

    # -----------------------------------------------------
    # FILE
    # -----------------------------------------------------

    files = {

        "file": (
            filename,
            image_data,
            content_type,
        )

    }

    data = {
        "content": content,
    }

    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    return discord_request(
        webhook_url,
        data,
        files,
        run_id,
        source,
    )


# =========================================================
# PUBLISH ONE
# =========================================================

def publish_one(
    label,
    source_name,
    getter,
    run_id,
):

    started = time.monotonic()

    print()
    print(
        "-------------------------------------------------------"
    )

    print(
        f"[{run_id}] "
        f"START {label}"
    )

    print(
        f"[{run_id}] "
        f"Source={source_name}"
    )

    try:

        image = getter(
            run_id
        )

        result = send_to_discord(
            image,
            run_id,
        )

        elapsed = (
            time.monotonic()
            - started
        )

        print(
            f"[{run_id}] "
            f"SUCCESS {label} "
            f"({elapsed:.2f}s)"
        )

        return {
            "label": label,
            "source": source_name,
            "success": True,
            "status": result.get(
                "status"
            ),
            "error": None,
            "elapsed": round(
                elapsed,
                2,
            ),
            "post_id": image.get(
                "post_id"
            ),
        }

    except Exception as error:

        elapsed = (
            time.monotonic()
            - started
        )

        print(
            f"[{run_id}] "
            f"ERROR {label}: "
            f"{error}"
        )

        return {
            "label": label,
            "source": source_name,
            "success": False,
            "status": None,
            "error": str(error),
            "elapsed": round(
                elapsed,
                2,
            ),
            "post_id": None,
        }

    finally:

        print(
            f"[{run_id}] "
            f"END {label}"
        )


# =========================================================
# POST
# =========================================================

@app.route(
    "/post",
    methods=["GET"],
)
def post_image():

    global CURRENT_RUN_ID
    global CURRENT_RUN_STARTED

    run_id = new_run_id()

    print()
    print(
        "======================================================="
    )

    print(
        f"[{run_id}] "
        "GAME POSTER START"
    )

    print(
        f"[{run_id}] "
        f"Time={now_string()}"
    )

    print(
        f"[{run_id}] "
        f"PID={os.getpid()}"
    )

    print(
        f"[{run_id}] "
        f"Outgoing IP="
        f"{get_outgoing_ip()}"
    )

    print(
        "======================================================="
    )

    # -----------------------------------------------------
    # GLOBAL LOCK
    # -----------------------------------------------------

    if not PUBLICATION_LOCK.acquire(
        blocking=False
    ):

        print(
            f"[{run_id}] "
            "Another publication is running."
        )

        return jsonify(
            {
                "status": "busy",
                "run_id": run_id,
            }
        ), 200

    with CURRENT_RUN_LOCK:

        CURRENT_RUN_ID = run_id

        CURRENT_RUN_STARTED = (
            time.time()
        )

    try:

        # -------------------------------------------------
        # BUILD JOB LIST
        # -------------------------------------------------

        jobs = []

        # -------------------------------------------------
        # WAIFU
        # -------------------------------------------------

        if WAIFU_WEBHOOK_URL:

            for index in range(
                1,
                WAIFU_POSTS + 1,
            ):

                jobs.append(
                    (
                        f"Waifu.im #{index}",
                        "Waifu.im",
                        get_random_waifu,
                    )
                )

        # -------------------------------------------------
        # DANBOORU ANIME
        # -------------------------------------------------

        if (
            DANBOORU_WEBHOOK_URL
            and DANBOORU_USERNAME
            and DANBOORU_API_KEY
        ):

            for index in range(
                1,
                DANBOORU_ANIME_POSTS + 1,
            ):

                jobs.append(
                    (
                        f"Danbooru Anime #{index}",
                        "Danbooru Anime",
                        get_danbooru_anime,
                    )
                )

        # -------------------------------------------------
        # DANBOORU GAMES
        # TWO POSTS
        # -------------------------------------------------

        if (
            DANBOORU_GAMES_WEBHOOK_URL
            and DANBOORU_USERNAME
            and DANBOORU_API_KEY
        ):

            for index in range(
                1,
                DANBOORU_GAMES_POSTS + 1,
            ):

                jobs.append(
                    (
                        f"Danbooru Games #{index}",
                        "Danbooru Games",
                        get_danbooru_games,
                    )
                )

        # -------------------------------------------------
        # EXPECTED
        # -------------------------------------------------

        expected = len(
            jobs
        )

        print(
            f"[{run_id}] "
            f"Expected publications="
            f"{expected}"
        )

        for index, job in enumerate(
            jobs,
            start=1,
        ):

            print(
                f"[{run_id}] "
                f"JOB {index}: "
                f"{job[0]}"
            )

        if not jobs:

            return jsonify(
                {
                    "status": "error",
                    "run_id": run_id,
                    "expected_sources": 0,
                    "processed": 0,
                    "successful": 0,
                    "errors": 0,
                    "results": [],
                }
            ), 500

        # -------------------------------------------------
        # EXECUTE ALL JOBS
        # -------------------------------------------------

        results = []

        for (
            label,
            source_name,
            getter,
        ) in jobs:

            result = publish_one(
                label,
                source_name,
                getter,
                run_id,
            )

            results.append(
                result
            )

            # IMPORTANT:
            #
            # Не останавливаем весь POST
            # после Cloudflare.
            #
            # Каждый webhook проверяется
            # отдельно.

        # -------------------------------------------------
        # STATS
        # -------------------------------------------------

        successful = sum(
            1
            for result in results
            if result["success"]
        )

        errors = sum(
            1
            for result in results
            if not result["success"]
        )

        processed = len(
            results
        )

        print()
        print(
            "======================================================="
        )

        print(
            f"[{run_id}] "
            "PUBLICATION FINISHED"
        )

        print(
            f"[{run_id}] "
            f"Expected={expected}"
        )

        print(
            f"[{run_id}] "
            f"Processed={processed}"
        )

        print(
            f"[{run_id}] "
            f"Successful={successful}"
        )

        print(
            f"[{run_id}] "
            f"Errors={errors}"
        )

        print(
            "-------------------------------------------------------"
        )

        for result in results:

            state = (
                "SUCCESS"
                if result["success"]
                else "ERROR"
            )

            print(
                f"[{run_id}] "
                f"{result['label']} -> "
                f"{state}"
            )

            if result.get(
                "post_id"
            ):

                print(
                    f"[{run_id}] "
                    f"  Post ID="
                    f"{result['post_id']}"
                )

            if result.get(
                "error"
            ):

                print(
                    f"[{run_id}] "
                    f"  Error="
                    f"{result['error']}"
                )

        print(
            "======================================================="
        )

        return jsonify(
            {
                "status": "completed",
                "run_id": run_id,
                "expected_sources": expected,
                "processed": processed,
                "successful": successful,
                "errors": errors,
                "results": results,
            }
        ), 200

    finally:

        with CURRENT_RUN_LOCK:

            CURRENT_RUN_ID = None

            CURRENT_RUN_STARTED = None

        PUBLICATION_LOCK.release()

        print(
            f"[{run_id}] "
            "Publication lock released."
        )


# =========================================================
# STATUS
# =========================================================

@app.route(
    "/status",
    methods=["GET"],
)
def status():

    with CURRENT_RUN_LOCK:

        current_run = (
            CURRENT_RUN_ID
        )

    configured = []

    if WAIFU_WEBHOOK_URL:

        configured.append(
            "Waifu.im"
        )

    if (
        DANBOORU_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        configured.append(
            "Danbooru Anime"
        )

    if (
        DANBOORU_GAMES_WEBHOOK_URL
        and DANBOORU_USERNAME
        and DANBOORU_API_KEY
    ):

        configured.append(
            "Danbooru Games #1"
        )

        configured.append(
            "Danbooru Games #2"
        )

    return jsonify(
        {
            "status": "online",
            "pid": os.getpid(),
            "outgoing_ip": get_outgoing_ip(),
            "publication_running": (
                current_run is not None
            ),
            "current_run_id": current_run,
            "planned_posts": {
                "waifu": WAIFU_POSTS,
                "danbooru_anime": (
                    DANBOORU_ANIME_POSTS
                ),
                "danbooru_games": (
                    DANBOORU_GAMES_POSTS
                ),
                "total": (
                    WAIFU_POSTS
                    + DANBOORU_ANIME_POSTS
                    + DANBOORU_GAMES_POSTS
                ),
            },
            "configured": configured,
        }
    )


# =========================================================
# PING
# =========================================================

@app.route(
    "/ping",
    methods=["GET"],
)
def ping():

    return Response(
        "OK",
        status=200,
    )


# =========================================================
# HOME
# =========================================================

@app.route(
    "/",
    methods=["GET"],
)
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

    print()
    print(
        "======================================================="
    )

    print(
        "GAME POSTER 5.0"
    )

    print(
        f"PORT={port}"
    )

    print(
        f"PID={os.getpid()}"
    )

    print(
        "Planned:"
    )

    print(
        f"  Waifu.im: {WAIFU_POSTS}"
    )

    print(
        f"  Danbooru Anime: "
        f"{DANBOORU_ANIME_POSTS}"
    )

    print(
        f"  Danbooru Games: "
        f"{DANBOORU_GAMES_POSTS}"
    )

    print(
        f"  TOTAL: "
        f"{WAIFU_POSTS + DANBOORU_ANIME_POSTS + DANBOORU_GAMES_POSTS}"
    )

    print(
        "======================================================="
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
    )
