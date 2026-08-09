"""Unit tests for MCP business rules without external services."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import unittest


class _FakeFastMCP:
    def __init__(self, _name):
        pass

    def tool(self, function):
        return function


sys.modules.setdefault("fastmcp", SimpleNamespace(FastMCP=_FakeFastMCP))
sys.modules.setdefault(
    "sentence_transformers",
    SimpleNamespace(SentenceTransformer=Mock),
)
sys.modules.setdefault("requests", Mock())
sys.modules.setdefault("psycopg2", Mock())
sys.modules.setdefault("psycopg2.extras", SimpleNamespace(RealDictCursor=Mock()))
sys.modules.setdefault("databricks", SimpleNamespace())
sys.modules.setdefault("databricks.sdk", SimpleNamespace(WorkspaceClient=Mock))
sys.path.insert(0, str(Path(__file__).parents[1] / "mcp_server"))

import trip_mcp_server


class TripMcpServerTests(unittest.TestCase):
    @patch("trip_mcp_server.weather_client.get_daily_forecast")
    @patch("trip_mcp_server.lakebase.run_query")
    def test_weather_uses_stored_trip_coordinates(self, run_query, get_forecast):
        run_query.return_value = [{
            "latitude": 38.72,
            "longitude": -9.14,
            "start_date": date(2026, 8, 10),
            "end_date": date(2026, 8, 12),
        }]
        get_forecast.return_value = [{"date": "2026-08-10"}]

        result = trip_mcp_server.get_weather_forecast(1)

        self.assertEqual(result, [{"date": "2026-08-10"}])
        get_forecast.assert_called_once_with(
            38.72, -9.14, date(2026, 8, 10), date(2026, 8, 12)
        )

    @patch("trip_mcp_server.lakebase.run_write_returning")
    def test_add_itinerary_rejects_invalid_duration(self, run_write):
        with self.assertRaisesRegex(ValueError, "between 1 and 1440"):
            trip_mcp_server.add_itinerary_item(1, 2, "2026-08-10T14:00:00", 0)
        run_write.assert_not_called()

    @patch("trip_mcp_server.lakebase.run_write_returning")
    def test_remove_missing_itinerary_item_fails_clearly(self, run_write):
        run_write.return_value = None
        with self.assertRaisesRegex(ValueError, "does not exist"):
            trip_mcp_server.remove_itinerary_item(999)

    @patch("trip_mcp_server.lakebase.run_query")
    @patch("trip_mcp_server.lakebase.run_write")
    def test_packing_list_uses_weather_thresholds(self, run_write, run_query):
        run_query.side_effect = [
            [{"max_rain": 70, "min_temperature": 11}],
            [{"item_name": "Compact umbrella"}],
        ]

        result = trip_mcp_server.generate_packing_list(1)

        self.assertEqual(result, [{"item_name": "Compact umbrella"}])
        saved_names = [call.args[1][1] for call in run_write.call_args_list]
        self.assertEqual(
            saved_names,
            ["Comfortable walking shoes", "Compact umbrella", "Light jacket"],
        )


if __name__ == "__main__":
    unittest.main()
