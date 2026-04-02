"""
Инструмент для получения турнирной таблицы и расписания матчей РПЛ.
Источник: premierliga.ru (основной), championat.com (резерв).
"""
from __future__ import annotations

from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# URLs
PL_TABLE_URL = "https://premierliga.ru/tournament-table/"
PL_MATCHES_URL = "https://premierliga.ru/matches/"
CHAMP_URL = "https://www.championat.com/football/_russiapl.html"


# ──────────────────────────────────────────────
# Турнирная таблица
# ──────────────────────────────────────────────

def _parse_pl_table(html: str) -> list[dict] | None:
    """Парсит таблицу с premierliga.ru."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    # premierliga.ru — таблица в <table> с классом содержащим 'table'
    table = soup.find("table")
    if not table:
        return None

    for tr in table.find_all("tr")[1:]:  # пропускаем заголовок
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        try:
            pos = tds[0].get_text(strip=True)
            team_tag = tds[1].find("a") or tds[1]
            team = team_tag.get_text(strip=True)
            games = tds[2].get_text(strip=True)
            pts = tds[-1].get_text(strip=True)  # очки обычно последний столбец
            # голы ищем по формату "X:Y" или "X-Y"
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
        # попробуем любую таблицу
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

    # Сначала premierliga.ru
    try:
        resp = requests.get(PL_TABLE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        rows = _parse_pl_table(resp.text)
        if rows:
            source = "premierliga.ru"
    except Exception:
        pass

    # Резерв — championat.com
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
# Расписание матчей
# ──────────────────────────────────────────────

def _parse_pl_matches(html: str, limit: int) -> list[dict] | None:
    """Парсит ближайшие матчи с premierliga.ru."""
    soup = BeautifulSoup(html, "html.parser")
    matches = []

    # premierliga.ru — матчи в div/article с датой и командами
    for item in soup.find_all(["div", "article"], class_=lambda c: c and "match" in str(c).lower())[:limit * 2]:
        try:
            teams_tags = item.find_all(class_=lambda c: c and "team" in str(c).lower())
            if len(teams_tags) < 2:
                continue
            home = teams_tags[0].get_text(strip=True)
            away = teams_tags[-1].get_text(strip=True)
            date_tag = item.find(class_=lambda c: c and ("date" in str(c).lower() or "time" in str(c).lower()))
            date_str = date_tag.get_text(strip=True) if date_tag else ""
            if home and away and home != away:
                matches.append({"home": home, "away": away, "date": date_str})
                if len(matches) >= limit:
                    break
        except Exception:
            continue

    return matches if matches else None


async def handle_get_rpl_fixtures(round_num: Optional[int] = None) -> str:
    """Получает расписание ближайших матчей РПЛ."""
    source = None
    matches = None
    limit = 10

    # Сначала premierliga.ru
    try:
        resp = requests.get(PL_MATCHES_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        matches = _parse_pl_matches(resp.text, limit)
        if matches:
            source = "premierliga.ru"
    except Exception:
        pass

    if not matches:
        return (
            "⚠️ Не удалось спарсить расписание матчей РПЛ автоматически.\n"
            "Смотри актуальное расписание здесь: https://premierliga.ru/matches/\n"
            "Также: https://www.championat.com/football/_russiapl.html"
        )

    round_info = f" (тур {round_num})" if round_num else ""
    lines = [f"📅 *Расписание матчей РПЛ{round_info}* (источник: {source})\n"]
    for i, m in enumerate(matches, 1):
        date_part = f"  📆 {m['date']}" if m["date"] else ""
        lines.append(f"{i}. {m['home']} — {m['away']}{date_part}")

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
                    "Получает расписание ближайших матчей Российской Премьер-Лиги (РПЛ). "
                    "Можно указать номер тура."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "round_num": {
                            "type": "integer",
                            "description": "Номер тура (необязательно). Если не указан — ближайшие матчи.",
                        }
                    },
                    "required": [],
                },
            },
        },
    ]
