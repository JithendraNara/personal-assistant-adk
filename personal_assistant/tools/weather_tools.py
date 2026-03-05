"""
Weather tools for workflow and briefing agents.

Uses OpenWeatherMap when OPENWEATHER_KEY is configured.
Falls back to deterministic mock data for local/dev environments.
"""

import os
from datetime import datetime, timezone

import httpx

OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")


def get_current_weather(location: str, units: str = "imperial") -> dict:
    """
    Get current weather conditions for a location.

    Args:
        location: City/area string (e.g. "Fort Wayne, IN").
        units: "imperial", "metric", or "standard".

    Returns:
        A dict with weather summary fields and provider metadata.
    """
    if not location or not location.strip():
        return {"status": "error", "message": "location is required"}

    units = (units or "imperial").strip().lower()
    if units not in {"imperial", "metric", "standard"}:
        units = "imperial"

    if OPENWEATHER_KEY:
        try:
            with httpx.Client(timeout=10.0) as client:
                geo_resp = client.get(
                    "https://api.openweathermap.org/geo/1.0/direct",
                    params={
                        "q": location.strip(),
                        "limit": 1,
                        "appid": OPENWEATHER_KEY,
                    },
                )
                geo_resp.raise_for_status()
                geo_data = geo_resp.json()
                if not geo_data:
                    return {
                        "status": "error",
                        "message": f"No matching location found for '{location}'.",
                    }

                loc = geo_data[0]
                weather_resp = client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": loc["lat"],
                        "lon": loc["lon"],
                        "units": units,
                        "appid": OPENWEATHER_KEY,
                    },
                )
                weather_resp.raise_for_status()
                weather = weather_resp.json()

            main = weather.get("main", {})
            wind = weather.get("wind", {})
            condition = (weather.get("weather") or [{}])[0]
            unit_label = "F" if units == "imperial" else ("C" if units == "metric" else "K")

            return {
                "status": "success",
                "location": f"{loc.get('name')}, {loc.get('state', '')}, {loc.get('country')}".replace(", ,", ","),
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
                "temperature": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "humidity_pct": main.get("humidity"),
                "wind_speed": wind.get("speed"),
                "condition": condition.get("main"),
                "description": condition.get("description"),
                "units": units,
                "unit_label": unit_label,
                "source": "openweathermap",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"OpenWeather request failed: {exc}",
                "source": "openweathermap",
            }

    # Mock fallback
    return {
        "status": "success",
        "location": location.strip(),
        "temperature": 49,
        "feels_like": 45,
        "humidity_pct": 71,
        "wind_speed": 11,
        "condition": "Clouds",
        "description": "broken clouds",
        "units": units,
        "unit_label": "F" if units == "imperial" else ("C" if units == "metric" else "K"),
        "source": "mock — configure OPENWEATHER_KEY for live weather",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
