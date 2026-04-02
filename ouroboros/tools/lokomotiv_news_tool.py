"""
Инструмент для получения новостей ФК Локомотив Москва со sports.ru.
Написан с помощью GigaChat Max.
"""
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.sports.ru"
NEWS_URL = f"{BASE_URL}/football/club/lokomotiv/news/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _parse_news(html_content: str, limit: int) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html_content, "html.parser")
    news_items = []

    for item in soup.find_all("p", {"class": "one_news"}, limit=limit):
        time_str = item.get("data-news-dtime", "")
        try:
            # Формат: "2026-04-02 16:47:00+03"
            timestamp = datetime.strptime(time_str[:19], "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
        except Exception:
            timestamp = time_str[:16]

        link_tag = item.find("a", {"class": "short-text"})
        if not link_tag:
            continue
        strong = link_tag.find("strong")
        if not strong:
            continue

        title = strong.get_text(strip=True)
        href = link_tag.get("href", "")
        if href.startswith("/"):
            href = BASE_URL + href

        news_items.append((timestamp, title, href))

    return news_items


async def handle_get_lokomotiv_news(count: Optional[int] = 10) -> str:
    """Парсит свежие новости Локомотива с sports.ru и возвращает форматированный список."""
    try:
        resp = requests.get(NEWS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        news = _parse_news(resp.text, count or 10)

        if not news:
            return "⚠️ Новости Локомотива не найдены — возможно, изменилась структура сайта."

        lines = ["🚂 *Новости Локомотив Москва* (sports.ru)\n"]
        for idx, (ts, title, url) in enumerate(news, start=1):
            lines.append(f"{idx}. [{ts}] {title}\n   🔗 {url}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Ошибка при получении новостей Локомотива: {e}"


def get_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_lokomotiv_news",
                "description": "Получает актуальные новости о ФК Локомотив Москва со sports.ru",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Количество последних новостей (по умолчанию 10)",
                        }
                    },
                    "required": [],
                },
            },
        }
    ]
