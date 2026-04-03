"""
Инструмент для получения турнирной таблицы и расписания матчей РПЛ.
Источник расписания: sports.ru/rfpl/calendar/ (статический HTML).
Источник таблицы: premierliga.ru / championat.com (резерв).
"""
from __future__ import annotations

from typing import Optional
import datetime
import re

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# URLs
PL_TABLE_URL = "https://premierliga.ru/tournament-table/"
CHAMP_URL = "https://www.championat.com/football/_russiapl.html"
SPORTS_RU_CALENDAR_URL = "https://www.sports.ru/rfpl/calendar/"

# Локализация
MONTHS_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}
WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


# ──────────────────────────────────────────────
# Турнирная таблица
# ──────────────────────────────────────────────

def _parse_pl_table(html: str) -> list[dict] | None:
    """Парсит таблицу с premierliga.ru."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    table = soup.find("table")
    if not table:
        return None

    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        try:
            pos = tds[0].get_text(strip=True)
            team_tag = tds[1].find("a") or tds[1]
            team = team_tag.get_text(strip=True)
            games = tds[2].get_text(strip=True)
            pts = tds[-1].get_text(strip=True)
            gd = ""
            for td in tds:
                txt = td.get_text(strip=True)
                if (":" in txt or "-" in txt) and txt.replace(":", "").replace("-", "").isdigit():
                    gd = txt
                    break
            if pos.isdigit() and team:
                rows.append({"pos": pos, "team": team, "games": games, "pts": pts, "gd": gd})
        except Exception:
            continue

    return rows if rows else None


def _parse_champ_table(html: str) -> list[dict] | None:
    """Парсит таблицу с championat.com как резерв."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    table = soup.find("table", class_=lambda c: c and "table" in c)
    if not table:
        table = soup.find("table")
    if not table:
        return None

    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        try:
            pos = tds[0].get_text(strip=True)
            team_tag = tds[1].find("a") or tds[1]
            team = team_tag.get_text(strip=True)
            games = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            pts = tds[-1].get_text(strip=True)
            gd = ""
            for td in tds:
                txt = td.get_text(strip=True)
                if (":" in txt or "-" in txt) and txt.replace(":", "").replace("-", "").isdigit():
                    gd = txt
                    break
            if pos.isdigit() and team:
                rows.append({"pos": pos, "team": team, "games": games, "pts": pts, "gd": gd})
        except Exception:
            continue

    return rows if rows else None


async def handle_get_rpl_standings() -> str:
    """Получает турнирную таблицу РПЛ."""
    source = None
    rows = None

    try:
        resp = requests.get(PL_TABLE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        rows = _parse_pl_table(resp.text)
        if rows:
            source = "premierliga.ru"
    except Exception:
        pass

    if not rows:
        try:
            resp = requests.get(CHAMP_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            rows = _parse_champ_table(resp.text)
            if rows:
                source = "championat.com"
        except Exception:
            pass

    if not rows:
        return (
            "⚠️ Не удалось получить турнирную таблицу РПЛ.\n"
            "Попробуй вручную: https://premierliga.ru/tournament-table/"
        )

    lines = [f"📊 *Турнирная таблица РПЛ* (источник: {source})\n"]
    lines.append(f"{'#':<3} {'Команда':<25} {'И':>3} {'О':>4}  {'Г/П'}")
    lines.append("─" * 45)
    for r in rows:
        team = r["team"][:24]
        lines.append(f"{r['pos']:<3} {team:<25} {r['games']:>3} {r['pts']:>4}  {r['gd']}")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Расписание матчей — sports.ru
# ──────────────────────────────────────────────

def _extract_rounds(html: str) -> list[tuple[int, list[dict]]]:
    """
    Парсит все туры с sports.ru/rfpl/calendar/.
    Возвращает список (round_num, matches) отсортированных по номеру тура.
    matches — список dict: {date, time, home, away}.
    
    Страница содержит заголовки "23 ТУР", "24 ТУР" и т.д.,
    за каждым следует таблица class="stat-table" с матчами.
    """
    soup = BeautifulSoup(html, "html.parser")
    rounds = []

    # Ищем все заголовки туров: элемент содержащий текст "N ТУР"
    tour_pattern = re.compile(r'^(\d+)\s+ТУР$', re.IGNORECASE)

    # Перебираем все элементы в документе в порядке появления
    all_elements = soup.find_all(True)
    i = 0
    while i < len(all_elements):
        el = all_elements[i]
        text = el.get_text(strip=True)
        m = tour_pattern.match(text)
        if m:
            round_num = int(m.group(1))
            # Ищем следующую таблицу stat-table после этого элемента
            table = el.find_next("table", class_="stat-table")
            if table:
                matches = []
                for tr in table.find_all("tr")[1:]:  # пропускаем заголовок
                    tds = tr.find_all("td")
                    if len(tds) < 4:
                        continue
                    raw_dt = tds[0].get_text(strip=True)  # "04.04.2026|13:00"
                    home = tds[1].get_text(strip=True)
                    away = tds[3].get_text(strip=True)
                    if not home or not away:
                        continue
                    if "|" in raw_dt:
                        date_part, time_part = raw_dt.split("|", 1)
                    else:
                        date_part, time_part = raw_dt, ""
                    matches.append({"date": date_part, "time": time_part, "home": home, "away": away})
                if matches:
                    rounds.append((round_num, matches))
        i += 1

    # Дедупликация — оставляем уникальные туры
    seen = {}
    for rn, matches in rounds:
        if rn not in seen:
            seen[rn] = matches
    return sorted(seen.items())


def _find_next_round(rounds: list[tuple[int, list[dict]]]) -> tuple[int, list[dict]] | None:
    """
    Среди всех туров находит ближайший незавершённый
    (первый тур у которого есть матч с датой >= сегодня или счётом "- : -").
    """
    today_str = datetime.date.today().strftime("%d.%m.%Y")
    today = datetime.date.today()

    for rn, matches in rounds:
        for m in matches:
            # Если счёт "- : -" — матч не сыгран
            # Если дата >= сегодня — тоже подходит
            try:
                match_date = datetime.datetime.strptime(m["date"], "%d.%m.%Y").date()
                if match_date >= today:
                    return rn, matches
            except Exception:
                pass
    return None


def _format_date_ru(date_str: str) -> str:
    """Форматирует дату "04.04.2026" -> "04 апр (сб)"."""
    try:
        dt = datetime.datetime.strptime(date_str, "%d.%m.%Y")
        day = dt.day
        month = MONTHS_RU[dt.month]
        weekday = WEEKDAYS_RU[dt.weekday()]
        return f"{day:02d} {month} ({weekday})"
    except Exception:
        return date_str


def _format_fixtures(round_num: int, matches: list[dict]) -> str:
    """Форматирует расписание тура в читаемый текст."""
    # Группируем по дате
    by_date: dict[str, list[dict]] = {}
    for m in matches:
        by_date.setdefault(m["date"], []).append(m)

    lines = [f"📅 *{round_num}-й тур РПЛ* (источник: sports.ru)\n"]
    for date_str, day_matches in by_date.items():
        lines.append(f"\n📆 {_format_date_ru(date_str)}")
        for m in day_matches:
            time_str = m["time"] if m["time"] else "??:??"
            home = m["home"]
            away = m["away"]
            loko_marker = " 🚂" if "локомотив" in home.lower() or "локомотив" in away.lower() else ""
            lines.append(f"🕐 {time_str}  {home} — {away}{loko_marker}")

    return "\n".join(lines)


async def handle_get_rpl_fixtures(round_num: Optional[int] = None) -> str:
    """Получает расписание матчей РПЛ текущего или указанного тура. Источник: sports.ru"""
    try:
        resp = requests.get(SPORTS_RU_CALENDAR_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return (
            f"⚠️ Не удалось загрузить расписание: {e}\n"
            f"Смотри вручную: {SPORTS_RU_CALENDAR_URL}"
        )

    rounds = _extract_rounds(resp.text)
    if not rounds:
        return (
            "⚠️ Не удалось спарсить расписание матчей РПЛ.\n"
            f"Смотри актуальное расписание: {SPORTS_RU_CALENDAR_URL}"
        )

    if round_num is not None:
        # Ищем конкретный тур
        target = dict(rounds).get(round_num)
        if not target:
            available = [str(rn) for rn, _ in rounds]
            return (
                f"⚠️ Тур {round_num} не найден на странице. "
                f"Доступные туры: {', '.join(available)}.\n"
                f"Смотри: {SPORTS_RU_CALENDAR_URL}"
            )
        return _format_fixtures(round_num, target)
    else:
        # Находим ближайший незавершённый тур
        result = _find_next_round(rounds)
        if not result:
            # Если все туры завершены — показываем последний
            result = rounds[-1]
        rn, matches = result
        return _format_fixtures(rn, matches)


# ──────────────────────────────────────────────
# Tool registration
# ──────────────────────────────────────────────

def get_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_rpl_standings",
                "description": (
                    "Получает актуальную турнирную таблицу Российской Премьер-Лиги (РПЛ). "
                    "Источник: premierliga.ru (основной), championat.com (резерв)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_rpl_fixtures",
                "description": (
                    "Получает расписание матчей Российской Премьер-Лиги (РПЛ). "
                    "Без параметров — ближайший незавершённый тур. "
                    "Можно указать round_num — номер тура в сезоне (например 24). "
                    "Источник: sports.ru."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "round_num": {
                            "type": "integer",
                            "description": "Порядковый номер тура в сезоне (необязательно). Если не указан — ближайший тур.",
                        }
                    },
                    "required": [],
                },
            },
        },
    ]
