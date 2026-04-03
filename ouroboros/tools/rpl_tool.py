"""
Инструмент для получения турнирной таблицы и расписания матчей РПЛ.
Источник расписания: sports.ru/rfpl/calendar/ (статический HTML).
Источник таблицы: premierliga.ru / championat.com (резерв).
"""
from __future__ import annotations

from typing import Optional
import datetime

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

def _parse_sports_ru_fixtures(html: str, round_idx: int = 0) -> list[dict]:
    """
    Парсит расписание с sports.ru/rfpl/calendar/.
    round_idx=0 — текущий/ближайший тур, 1 — следующий и т.д.
    Возвращает список dict: {date, time, home, away}.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="stat-table")
    if not tables or round_idx >= len(tables):
        return []

    table = tables[round_idx]
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

    return matches


def _format_date_ru(date_str: str) -> str:
    """
    Форматирует дату "04.04.2026" -> "04 апр (сб)".
    """
    try:
        dt = datetime.datetime.strptime(date_str, "%d.%m.%Y")
        day = dt.day
        month = MONTHS_RU[dt.month]
        weekday = WEEKDAYS_RU[dt.weekday()]
        return f"{day:02d} {month} ({weekday})"
    except Exception:
        return date_str


async def handle_get_rpl_fixtures(round_num: Optional[int] = None) -> str:
    """Получает расписание матчей РПЛ текущего или указанного тура. Источник: sports.ru"""
    # round_num — номер тура (1-based), round_idx для парсера (0-based, относительно первой таблицы)
    round_idx = max(0, (round_num - 1) if round_num else 0)

    try:
        resp = requests.get(SPORTS_RU_CALENDAR_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return (
            f"⚠️ Не удалось загрузить расписание: {e}\n"
            f"Смотри вручную: {SPORTS_RU_CALENDAR_URL}"
        )

    matches = _parse_sports_ru_fixtures(resp.text, round_idx)

    if not matches:
        return (
            "⚠️ Не удалось спарсить расписание матчей РПЛ.\n"
            f"Смотри актуальное расписание: {SPORTS_RU_CALENDAR_URL}"
        )

    # Группируем по дате
    by_date: dict[str, list[dict]] = {}
    for m in matches:
        by_date.setdefault(m["date"], []).append(m)

    # Определяем номер тура по данным на странице (первая таблица — текущий тур)
    # Пытаемся угадать номер тура из заголовка над таблицей
    tour_label = ""
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table", class_="stat-table")
        if tables and round_idx < len(tables):
            # ищем заголовок h2/h3/div рядом с таблицей
            heading = tables[round_idx].find_previous(["h2", "h3", "h4"])
            if heading:
                tour_label = heading.get_text(strip=True)
    except Exception:
        pass

    if tour_label:
        header = f"📅 *{tour_label}* (источник: sports.ru)\n"
    else:
        round_info = f" тур" if not round_num else f" {round_num}-й тур"
        header = f"📅 *Расписание РПЛ —{round_info}* (источник: sports.ru)\n"

    lines = [header]
    for date_str, day_matches in by_date.items():
        lines.append(f"\n📆 {_format_date_ru(date_str)}")
        for m in day_matches:
            time_str = m["time"] if m["time"] else "??:??"
            # Выделяем Локомотив
            home = m["home"]
            away = m["away"]
            loko_marker = " 🚂" if "локомотив" in home.lower() or "локомотив" in away.lower() else ""
            lines.append(f"  🕐 {time_str}  {home} — {away}{loko_marker}")

    return "\n".join(lines)


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
                    "Получает расписание матчей текущего тура Российской Премьер-Лиги (РПЛ). "
                    "Источник: sports.ru. Можно указать порядковый номер тура в сезоне."
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
