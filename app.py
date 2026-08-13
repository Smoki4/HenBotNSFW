# =========================================================
# REACTOR GAMES
# =========================================================

REACTOR_GAMES_URL = (
    "https://reactor.cc/tag/Игровая+эротика"
)

REACTOR_SEEN_FILE = "reactor_seen.json"

REACTOR_LOCK = threading.Lock()


def load_reactor_seen():
    """Загружает список уже опубликованных URL."""

    try:
        if not os.path.exists(REACTOR_SEEN_FILE):
            return set()

        with open(
            REACTOR_SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = file.read().strip()

            if not data:
                return set()

            import json

            values = json.loads(data)

            if not isinstance(values, list):
                return set()

            return set(values)

    except Exception as error:

        print(
            "[Reactor Games] "
            f"Не удалось загрузить историю: {error}"
        )

        return set()


def save_reactor_seen(seen):
    """Сохраняет историю опубликованных URL."""

    import json

    try:

        # Чтобы файл не разрастался бесконечно.
        # Храним последние 2000 URL.
        values = list(seen)[-2000:]

        with open(
            REACTOR_SEEN_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                values,
                file,
                ensure_ascii=False,
                indent=2,
            )

    except Exception as error:

        print(
            "[Reactor Games] "
            f"Не удалось сохранить историю: {error}"
        )


def extract_reactor_images(html):
    """Извлекает изображения из HTML Reactor."""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    for img in soup.find_all("img"):

        src = (
            img.get("data-src")
            or img.get("data-original")
            or img.get("src")
        )

        if not src:
            continue

        src = urljoin(
            REACTOR_GAMES_URL,
            src,
        )

        lowered = src.lower()

        # Отбрасываем служебные изображения.
        if any(
            value in lowered
            for value in (
                "avatar",
                "logo",
                "icon",
                "emoji",
                "banner",
                "smile",
            )
        ):
            continue

        # Убираем thumbnail, если Reactor дал
        # оригинальный URL в другом атрибуте.
        if "data-src" in img.attrs:
            original = img.get("data-src")

            if original:
                src = urljoin(
                    REACTOR_GAMES_URL,
                    original,
                )

        candidates.append(src)

    # Убираем дубликаты, сохраняя порядок.
    return list(
        dict.fromkeys(candidates)
    )


def get_reactor_page(page):
    """Получает конкретную страницу Reactor."""

    url = (
        f"{REACTOR_GAMES_URL}"
        f"/{page}"
    )

    print(
        "[Reactor Games] "
        f"Открываем страницу {page}"
    )

    response = requests.get(
        url,
        headers=REACTOR_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return extract_reactor_images(
        response.text
    )


def get_reactor_games():

    print(
        "[Reactor Games] "
        "Получаем случайный арт..."
    )

    # Важно: доступ к истории делаем под lock,
    # чтобы два одновременных запроса не выбрали
    # одну и ту же картинку.
    with REACTOR_LOCK:

        seen = load_reactor_seen()

        # Пробуем несколько случайных страниц.
        pages = list(
            range(1, 31)
        )

        random.shuffle(pages)

        all_unused = []

        for page in pages:

            try:

                candidates = get_reactor_page(
                    page
                )

                if not candidates:
                    continue

                unused = [
                    url
                    for url in candidates
                    if url not in seen
                ]

                print(
                    "[Reactor Games] "
                    f"Страница {page}: "
                    f"{len(candidates)} изображений, "
                    f"{len(unused)} новых"
                )

                all_unused.extend(
                    unused
                )

                # Если нашли достаточно новых
                # кандидатов, дальше можно не ходить.
                if len(all_unused) >= 20:
                    break

            except Exception as error:

                print(
                    "[Reactor Games] "
                    f"Ошибка страницы {page}: "
                    f"{error}"
                )

        # Убираем дубли между страницами.
        all_unused = list(
            dict.fromkeys(
                all_unused
            )
        )

        if not all_unused:

            # Если история слишком большая,
            # можно начать новый цикл.
            print(
                "[Reactor Games] "
                "Новых изображений не найдено. "
                "Очищаем историю."
            )

            seen.clear()

            save_reactor_seen(
                seen
            )

            # Ещё одна попытка.
            random.shuffle(pages)

            for page in pages[:10]:

                try:

                    candidates = get_reactor_page(
                        page
                    )

                    if candidates:
                        all_unused.extend(
                            candidates
                        )

                except Exception:
                    continue

                if len(all_unused) >= 20:
                    break

            all_unused = list(
                dict.fromkeys(
                    all_unused
                )
            )

        if not all_unused:

            raise RuntimeError(
                "Reactor не вернул новых изображений"
            )

        # Выбираем случайное изображение
        # среди ещё не опубликованных.
        random.shuffle(
            all_unused
        )

        image_url = all_unused[0]

        # Проверяем, что картинка действительно доступна.
        try:

            check = requests.head(
                image_url,
                headers=REACTOR_HEADERS,
                timeout=15,
                allow_redirects=True,
            )

            if check.status_code != 200:

                # Если HEAD запрещён сервером,
                # попробуем GET.
                check = requests.get(
                    image_url,
                    headers=REACTOR_HEADERS,
                    timeout=15,
                    stream=True,
                )

            if check.status_code != 200:

                raise RuntimeError(
                    f"HTTP {check.status_code}"
                )

        except Exception as error:

            print(
                "[Reactor Games] "
                f"Ошибка проверки изображения: "
                f"{error}"
            )

            # Пробуем несколько других кандидатов.
            for alternative in all_unused[1:10]:

                try:

                    check = requests.get(
                        alternative,
                        headers=REACTOR_HEADERS,
                        timeout=15,
                        stream=True,
                    )

                    if check.status_code == 200:

                        image_url = alternative
                        break

                except Exception:
                    continue

            else:

                raise RuntimeError(
                    "Не удалось получить "
                    "доступное изображение Reactor"
                )

        # Записываем URL в историю ДО возврата.
        # Благодаря этому параллельный запуск
        # не выберет тот же URL.
        seen.add(
            image_url
        )

        save_reactor_seen(
            seen
        )

        print(
            "[Reactor Games] "
            "Выбрано новое изображение"
        )

        print(
            "[Reactor Games] "
            f"URL: {image_url}"
        )

        return {
            "url": image_url,
            "source": "Reactor Games",
        }
