from datetime import date
import unittest
from unittest.mock import Mock, patch

import sys
from pathlib import Path

sys.modules.setdefault("requests", Mock())
sys.path.insert(0, str(Path(__file__).parents[1] / "mcp_server"))
import weather_client


class WeatherClientTests(unittest.TestCase):
    @patch("weather_client.requests.get")
    def test_search_destination(self, mock_get):
        response = Mock()
        response.json.return_value = {"results": [{"name": "Lisbon", "country": "Portugal", "latitude": 38.72, "longitude": -9.14, "timezone": "Europe/Lisbon"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        result = weather_client.search_destination("Lisbon")
        self.assertEqual(result["country"], "Portugal")
        self.assertEqual(result["latitude"], 38.72)

    @patch("weather_client.requests.get")
    def test_daily_forecast_is_normalized(self, mock_get):
        response = Mock()
        response.json.return_value = {"daily": {"time": ["2026-08-10"], "weather_code": [61], "temperature_2m_max": [23.0], "temperature_2m_min": [17.0], "precipitation_probability_max": [70]}}
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        rows = weather_client.get_daily_forecast(38.72, -9.14, date(2026, 8, 10), date(2026, 8, 10))
        self.assertEqual(rows, [{"date": "2026-08-10", "weather_code": 61, "temperature_max_c": 23.0, "temperature_min_c": 17.0, "precipitation_probability": 70}])


if __name__ == "__main__":
    unittest.main()
