"""Small Open-Meteo client used by MCP tools."""

from datetime import date

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def search_destination(name: str) -> dict:
    response = requests.get(
        GEOCODING_URL,
        params={"name": name, "count": 1, "language": "en", "format": "json"},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError(f"Destination not found: {name}")
    item = results[0]
    return {
        "name": item["name"],
        "country": item.get("country"),
        "latitude": item["latitude"],
        "longitude": item["longitude"],
        "timezone": item.get("timezone"),
    }


def get_daily_forecast(latitude: float, longitude: float, start_date: date, end_date: date) -> list[dict]:
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
        },
        timeout=20,
    )
    response.raise_for_status()
    daily = response.json()["daily"]
    return [
        {
            "date": day,
            "weather_code": daily["weather_code"][index],
            "temperature_max_c": daily["temperature_2m_max"][index],
            "temperature_min_c": daily["temperature_2m_min"][index],
            "precipitation_probability": daily["precipitation_probability_max"][index],
        }
        for index, day in enumerate(daily["time"])
    ]
