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

# Минимальное время между POST в Discord.
DISCORD_SEND_DELAY = 6.0

# Дополнительный случайный интервал.
DISCORD_JITTER_MIN = 0.5
DISCORD_JITTER_MAX = 2.0


# Danbooru
DANBOORU_SEND_DELAY = 2.0


# Image
MAX_IMAGE_SIZE = 19 * 1024 * 1024

DISCORD_SPOILER = True


# Memory
MAX_MEMORY = 3000


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
        "GamePoster/3.0 "
        "(https://render.com)"
    ),
    "Accept": "*/*",
}


DANBOORU_HEADERS = {
    "User-Agent": (
        "GamePoster/3.0 "
        f"(user {DANBOORU_USERNAME or 'unknown'})"
    ),
    "Accept": "application/json",
}


# =========================================================
# GLOBAL STATE
# =========================================================

# ---------------------------------------------------------
# Publication lock
#
# Защищает один Python process.
# На Render всё равно рекомендуется 1 instance / 1 worker.
# ---------------------------------------------------------

PUBLICATION_LOCK = threading.Lock()


# ---------------------------------------------------------
# Discord rate lock
# ---------------------------------------------------------

DISCORD_LOCK = threading.Lock()

LAST_DISCORD_SEND = 0.0


# ---------------------------------------------------------
# Danbooru rate lock
# ---------------------------------------------------------

DANBOORU_LOCK = threading.Lock()

LAST_DANBOORU_REQUEST = 0.0


# ---------------------------------------------------------
# Used IDs
# ---------------------------------------------------------

DANBOORU_USED_IDS = set()

DANBOORU_MEMORY_LOCK = threading.Lock()


# ---------------------------------------------------------
# Current publication information
# ---------------------------------------------------------

CURRENT_RUN_LOCK = threading.Lock()

CURRENT_RUN_ID = None

CURRENT_RUN_STARTED = None


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
# MEMORY
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

            old_id = next(
                iter(DANBOORU_USED_IDS)
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
# DANBOORU RATE LIMIT
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
# DISCORD RATE LIMIT
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
# RENDER DEBUG
# =========================================================

OUTGOING_IP = None

OUTGOING_IP_LOCK = threading.Lock()


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
                "[DEBUG] IP error:",
                error,
            )

            OUTGOING_IP = "unknown"

        return OUTGOING_IP


# =========================================================
# WAIFU.IM
# =========================================================

def get_random_waifu(run_id):

    print(
        f"[{run_id}] "
        "[Waifu.im] получение изображения"
    )

    for attempt in range(5):

        try:

            response = HTTP.get(
                WAIFU_API,
                params={
                    "OrderBy": "Random",
                    "PageSize": 1,
                },
                headers=DEFAULT_HEADERS,
                timeout=30,
            )

            print(
                f"[{run_id}] "
                f"[Waifu.im] HTTP "
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
                    "empty items"
                )

            item = items[0]

            image_url = item.get(
                "url"
            )

            if not image_url:

                raise RuntimeError(
                    "Waifu.im image URL "
                    "is missing"
                )

            return {
                "url": image_url,
                "source": "Waifu.im",
                "tags": [],
            }

        except Exception as error:

            print(
                f"[{run_id}] "
                f"[Waifu.im] attempt "
                f"{attempt + 1}: "
                f"{error}"
            )

            if attempt < 4:

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
            "not configured"
        )

    if not DANBOORU_API_KEY:

        raise RuntimeError(
            "DANBOORU_API_KEY "
            "not configured"
        )

    print(
        f"[{run_id}] "
        f"[{source_name}] "
        f"tags={tags}"
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
            "no new images found"
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
        f"selected post "
        f"{selected['post_id']}"
    )

    return selected


# =========================================================
# DANBOORU TAGS
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
        f"[Image] download"
    )

    response = HTTP.get(
        image_url,
        headers=DEFAULT_HEADERS,
        timeout=60,
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

            size = int(
                content_length
            )

            if size > MAX_IMAGE_SIZE:

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

            chunks.append(chunk)

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
# DISCORD RESPONSE ANALYSIS
# =========================================================

def get_response_body(
    response,
):

    try:

        return response.json()

    except Exception:

        return None


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
    )

    return any(
        indicator in body
        for indicator in indicators
    )


# =========================================================
# DISCORD RETRY DELAY
# =========================================================

def get_retry_after(
    response,
    attempt,
):

    # Header
    header_value = (
        response.headers.get(
            "Retry-After"
        )
    )

    if header_value:

        try:

            return max(
                float(header_value),
                1.0,
            )

        except (
            TypeError,
            ValueError,
        ):

            pass

    # JSON body
    body = get_response_body(
        response
    )

    if isinstance(
        body,
        dict,
    ):

        value = body.get(
            "retry_after"
        )

        if value is not None:

            try:

                return max(
                    float(value),
                    1.0,
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

    # Fallback
    return min(
        5.0 * (2 ** attempt),
        120.0,
    )


# =========================================================
# DISCORD POST
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
                f"network error: "
                f"{error}"
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
                10.0 * (2 ** (attempt - 1)),
                120.0,
            )

            wait_time += random.uniform(
                1.0,
                3.0,
            )

            print(
                f"[{run_id}] "
                f"retry in "
                f"{wait_time:.1f}s"
            )

            time.sleep(
                wait_time
            )

            continue

        # -------------------------------------------------
        # Response information
        # -------------------------------------------------

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
        )

        retry_after = (
            response.headers.get(
                "Retry-After"
            )
        )

        cf_ray = (
            response.headers.get(
                "CF-Ray"
            )
        )

        print(
            f"[{run_id}] "
            f"[{source_name}] "
            f"HTTP {response.status_code}"
        )

        print(
            f"[{run_id}] "
            f"Content-Type: "
            f"{content_type}"
        )

        if retry_after:

            print(
                f"[{run_id}] "
                f"Retry-After: "
                f"{retry_after}"
            )

        if cf_ray:

            print(
                f"[{run_id}] "
                f"CF-Ray: "
                f"{cf_ray}"
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
                "Discord SUCCESS"
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

            print(
                f"[{run_id}] "
                f"[{source_name}] "
                "CLOUDFLARE BLOCK"
            )

            print(
                response.text[:1000]
            )

            raise RuntimeError(
                "Cloudflare blocked "
                "Discord request"
            )

        # -------------------------------------------------
        # 429
        # -------------------------------------------------

        if response.status_code == 429:

            wait_time = get_retry_after(
                response,
                attempt - 1,
            )

            wait_time += random.uniform(
                1.0,
                3.0,
            )

            print(
                f"[{run_id}] "
                f"[{source_name}] "
                f"Discord 429"
            )

            print(
                f"[{run_id}] "
                f"waiting "
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
            "Discord error body:"
        )

        print(
            response.text[:1500]
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
            f"Webhook missing "
            f"for {source}"
        )

    # -----------------------------------------------------
    # IMAGE
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
        f"image size="
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

    content = (
        f"{message}\n"
        f"Источник: {source}"
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
    # DISCORD
    # -----------------------------------------------------

    result = discord_request(
        webhook_url,
        data,
        files,
        run_id,
        source,
    )

    return result


# =========================================================
# PUBLISH ONE SOURCE
# =========================================================

def publish_one(
    source_name,
    getter,
    run_id,
):

    started = time.monotonic()

    print(
        f"[{run_id}] "
        f"========== "
        f"{source_name} START =========="
    )

    try:

        # -------------------------------------------------
        # GET IMAGE
        # -------------------------------------------------

        image = getter(
            run_id
        )

        # -------------------------------------------------
        # SEND
        # -------------------------------------------------

        discord_result = send_to_discord(
            image,
            run_id,
        )

        elapsed = (
            time.monotonic()
            - started
        )

        result = {
            "source": source_name,
            "success": True,
            "status": discord_result.get(
                "status"
            ),
            "error": None,
            "elapsed": round(
                elapsed,
                2,
            ),
        }

        print(
            f"[{run_id}] "
            f"{source_name} "
            f"SUCCESS "
            f"({elapsed:.2f}s)"
        )

        return result

    except Exception as error:

        elapsed = (
            time.monotonic()
            - started
        )

        result = {
            "source": source_name,
            "success": False,
            "status": None,
            "error": str(error),
            "elapsed": round(
                elapsed,
                2,
            ),
        }

        print(
            f"[{run_id}] "
            f"{source_name} "
            f"ERROR: "
            f"{error}"
        )

        return result

    finally:

        print(
            f"[{run_id}] "
            f"========== "
            f"{source_name} END =========="
        )


# =========================================================
# SOURCE LIST
# =========================================================

def get_configured_sources():

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

    return sources


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

    # -----------------------------------------------------
    # Generate run ID
    # -----------------------------------------------------

    run_id = new_run_id()

    print()
    print(
        "======================================================="
    )
    print(
        f"[{run_id}] POST REQUEST"
    )
    print(
        f"[{run_id}] PID={os.getpid()}"
    )
    print(
        f"[{run_id}] THREAD="
        f"{threading.get_ident()}"
    )
    print(
        f"[{run_id}] TIME="
        f"{now_string()}"
    )
    print(
        "======================================================="
    )

    # -----------------------------------------------------
    # Lock
    # -----------------------------------------------------

    acquired = PUBLICATION_LOCK.acquire(
        blocking=False
    )

    if not acquired:

        print(
            f"[{run_id}] "
            "ANOTHER PUBLICATION "
            "IS ALREADY RUNNING"
        )

        return jsonify(
            {
                "status": "busy",
                "run_id": run_id,
                "message": (
                    "Another publication "
                    "is already running"
                ),
            }
        ), 200

    # -----------------------------------------------------
    # Current run
    # -----------------------------------------------------

    with CURRENT_RUN_LOCK:

        CURRENT_RUN_ID = run_id

        CURRENT_RUN_STARTED = (
            time.time()
        )

    try:

        # -------------------------------------------------
        # IP
        # -------------------------------------------------

        outgoing_ip = (
            get_outgoing_ip()
        )

        print(
            f"[{run_id}] "
            f"OUTGOING IP="
            f"{outgoing_ip}"
        )

        # -------------------------------------------------
        # SOURCES
        # -------------------------------------------------

        sources = (
            get_configured_sources()
        )

        print(
            f"[{run_id}] "
            f"Configured sources="
            f"{len(sources)}"
        )

        for source_name, _ in sources:

            print(
                f"[{run_id}] "
                f"Source: "
                f"{source_name}"
            )

        if not sources:

            print(
                f"[{run_id}] "
                "NO SOURCES CONFIGURED"
            )

            return jsonify(
                {
                    "status": "error",
                    "run_id": run_id,
                    "successful": 0,
                    "errors": 0,
                    "results": [],
                    "message": (
                        "No sources configured"
                    ),
                }
            ), 500

        # -------------------------------------------------
        # PROCESS SEQUENTIALLY
        # -------------------------------------------------

        results = []

        for source_name, getter in sources:

            print(
                f"[{run_id}] "
                f"Starting source "
                f"{source_name}"
            )

            result = publish_one(
                source_name,
                getter,
                run_id,
            )

            results.append(
                result
            )

            print(
                f"[{run_id}] "
                f"RESULT "
                f"{source_name}: "
                f"{'SUCCESS' if result['success'] else 'ERROR'}"
            )

            # -------------------------------------------------
            # IMPORTANT:
            #
            # Если Cloudflare заблокировал Discord,
            # прекращаем этот запуск.
            # -------------------------------------------------

            if (
                not result["success"]
                and "Cloudflare" in (
                    result["error"]
                    or ""
                )
            ):

                print(
                    f"[{run_id}] "
                    "CLOUDFLARE BLOCK "
                    "DETECTED."
                )

                print(
                    f"[{run_id}] "
                    "STOPPING remaining sources."
                )

                break

        # -------------------------------------------------
        # FINAL STATS
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

        total = len(
            results
        )

        print()
        print(
            "======================================================="
        )
        print(
            f"[{run_id}] FINAL RESULT"
        )
        print(
            f"[{run_id}] "
            f"successful={successful}"
        )
        print(
            f"[{run_id}] "
            f"errors={errors}"
        )
        print(
            f"[{run_id}] "
            f"processed={total}"
        )
        print(
            "-------------------------------------------------------"
        )

        for result in results:

            status = (
                "SUCCESS"
                if result["success"]
                else "ERROR"
            )

            print(
                f"[{run_id}] "
                f"{result['source']}: "
                f"{status} "
                f"elapsed={result['elapsed']}s"
            )

            if not result["success"]:

                print(
                    f"[{run_id}] "
                    f"ERROR DETAILS: "
                    f"{result['error']}"
                )

        print(
            "======================================================="
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return jsonify(
            {
                "status": "completed",
                "run_id": run_id,
                "successful": successful,
                "errors": errors,
                "processed": total,
                "expected_sources": len(
                    sources
                ),
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
            "LOCK RELEASED"
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

        started = (
            CURRENT_RUN_STARTED
        )

    sources = (
        get_configured_sources()
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
            "current_run_started": started,
            "configured_sources": [
                name
                for name, _ in sources
            ],
            "source_count": len(
                sources
            ),
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
        "GAME POSTER 3.0"
    )
    print(
        f"PORT={port}"
    )
    print(
        f"PID={os.getpid()}"
    )
    print(
        "======================================================="
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
    )
