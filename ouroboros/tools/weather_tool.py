"""
Weather tool — текущая погода через wttr.in API.
Код написан с помощью GigaChat-Max, проверен и доработан Ouroboros.

Источник данных: wttr.in (открытый сервис, без токена).
Запасной вариант для Гисметео: добавить GISMETEO_TOKEN в env и переключить SOURCE.
"""

import requests
from typing import Optional

WEATHER_TRANSLATIONS = {
    "Clear": "ясно",
    "Sunny": "солнечно",
    "Partly cloudy": "облачно с прояснениями",
    "Partly Cloudy": "облачно с прояснениями",
    "Cloudy": "облачно",
    "Overcast": "пасмурно",
    "Mist": "дымка",
    "Fog": "туман",
    "Freezing fog": "ледяной туман",
    "Patchy rain possible": "возможен небольшой дождь",
    "Patchy snow possible": "возможен небольшой снег",
    "Patchy sleet possible": "возможен мокрый снег",
    "Patchy freezing drizzle possible": "возможен ледяной дождь",
    "Thundery outbreaks possible": "возможны грозы",
    "Blowing snow": "метёт снег",
    "Blizzard": "метель",
    "Patchy light drizzle": "небольшая морось",
    "Light drizzle": "морось",
    "Freezing drizzle": "ледяной дождь",
    "Heavy freezing drizzle": "сильный ледяной дождь",
    "Patchy light rain": "небольшой дождь",
    "Light rain": "дождь",
    "Moderate rain at times": "временами умеренный дождь",
    "Moderate rain": "умеренный дождь",
    "Heavy rain at times": "временами сильный дождь",
    "Heavy rain": "сильный дождь",
    "Light freezing rain": "лёгкий замерзающий дождь",
    "Moderate or heavy freezing rain": "умеренный или сильный замерзающий дождь",
    "Light sleet": "лёгкий мокрый снег",
    "Moderate or heavy sleet": "умеренный или сильный мокрый снег",
    "Light snow": "лёгкий снег",
    "Patchy moderate snow": "местами умеренный снег",
    "Moderate snow": "умеренный снег",
    "Patchy heavy snow": "местами сильный снег",
    "Heavy snow": "сильный снег",
    "Ice pellets": "ледяная крупа",
    "Light rain shower": "небольшой ливень",
    "Moderate or heavy rain shower": "умеренный или сильный ливень",
    "Torrential rain shower": "ливень",
    "Light sleet showers": "небольшой мокрый снег",
    "Moderate or heavy sleet showers": "умеренный или сильный мокрый снег",
    "Light snow showers": "небольшой снегопад",
    "Moderate or heavy snow showers": "умеренный или сильный снегопад",
    "Patchy light rain with thunder": "небольшой дождь с грозой",
    "Moderate or heavy rain with thunder": "умеренный или сильный дождь с грозой",
    "Patchy light snow with thunder": "небольшой снег с грозой",
    "Moderate or heavy snow with thunder": "умеренный или сильный снег с грозой",
}

WEATHER_EMOJI = {
    "Clear": "☀️",
    "Sunny": "☀️",
    "Partly cloudy": "⛅",
    "Partly Cloudy": "⛅",
    "Cloudy": "☁️",
    "Overcast": "☁️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Blizzard": "❄️",
    "Blowing snow": "🌨️",
}


def _translate(desc: str) -> str:
    return WEATHER_TRANSLATIONS.get(desc, desc)


def _emoji(desc: str) -> str:
    if "rain" in desc.lower() or "drizzle" in desc.lower():
        return "🌧️"
    if "snow" in desc.lower() or "blizzard" in desc.lower():
        return "❄️"
    if "thunder" in desc.lower():
        return "⛈️"
    if "fog" in desc.lower() or "mist" in desc.lower():
        return "🌫️"
    return WEATHER_EMOJI.get(desc, "🌤️")


def get_weather(city: Optional[str] = None) -> str:
    """Получить текущую погоду через wttr.in."""
    if not city:
        city = "Москва"

    try:
        resp = requests.get(
            f"https://wttr.in/{city}?format=j1",
            timeout=10,
            headers={"Accept-Language": "ru"},
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return f"❗ Сервис погоды не отвечает (timeout). Попробуй позже."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return f'❗ Город «{city}» не найден.'
        return f"❗ Ошибка HTTP {e.response.status_code} при запросе погоды."
    except Exception as e:
        return f"❗ Не удалось получить погоду: {e}"

    try:
        curr = data["current_condition"][0]
        temp = int(curr["temp_C"])
        feels = int(curr["FeelsLikeC"])
        humidity = curr["humidity"]
        wind_kmph = float(curr["windspeedKmph"])
        wind_ms = round(wind_kmph / 3.6, 1)
        precip = float(curr["precipMM"])
        desc_en = curr["weatherDesc"][0]["value"]
        desc_ru = _translate(desc_en)
        icon = _emoji(desc_en)

        lines = [
            f"{icon} **{city}:** {desc_ru}",
            f"🌡️ {temp}°C, ощущается как {feels}°C",
            f"💧 Влажность {humidity}%",
            f"💨 Ветер {wind_ms} м/с",
        ]
        if precip > 0:
            lines.append(f"🌧️ Осадки {precip} мм")

        return "\n".join(lines)
    except (KeyError, IndexError, ValueError) as e:
        return f"❗ Не удалось разобрать данные погоды: {e}"


def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": (
                    "Получить текущую погоду в указанном городе. "
                    "По умолчанию — Москва. "
                    "Используй когда пользователь спрашивает про погоду."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "Название города на русском или английском",
                        }
                    },
                    "required": [],
                },
            },
        }
    ]
