"""Weather-aware trip-planning MCP server for Databricks Agent Bricks."""

import logging
import os
from datetime import datetime

from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

import lakebase
import weather_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trip-planner-mcp")

EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
_model = None
mcp = FastMCP("naza-ai-trip-planner")


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


@mcp.tool
def search_destination(name: str) -> dict:
    """Resolve a destination name to coordinates using Open-Meteo Geocoding."""
    return weather_client.search_destination(name)


@mcp.tool
def get_weather_forecast(trip_id: int) -> list[dict]:
    """Get the current daily Open-Meteo forecast for a stored trip."""
    trips = lakebase.run_query(
        "SELECT latitude, longitude, start_date, end_date FROM trips WHERE trip_id = %s",
        (trip_id,),
    )
    if not trips:
        raise ValueError(f"Trip {trip_id} does not exist")
    trip = trips[0]
    return weather_client.get_daily_forecast(
        trip["latitude"], trip["longitude"], trip["start_date"], trip["end_date"]
    )


@mcp.tool
def semantic_search_activities(query: str, destination_name: str = "Lisbon", limit: int = 5) -> list[dict]:
    """Find activities by semantic meaning using Lakebase pgvector cosine distance."""
    safe_limit = max(1, min(limit, 10))
    vector = get_embedding_model().encode(query).tolist()
    vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
    return lakebase.run_query(
        """
        SELECT a.activity_id, a.name, a.category, a.indoor, a.description,
               ROUND((1 - (d.embedding <=> %s::vector))::numeric, 4) AS similarity
        FROM activity_documents d
        JOIN activities a ON a.activity_id = d.activity_id
        WHERE a.destination_name = %s AND d.embedding IS NOT NULL
        ORDER BY d.embedding <=> %s::vector
        LIMIT %s
        """,
        (vector_literal, destination_name, vector_literal, safe_limit),
    )


@mcp.tool
def get_itinerary(trip_id: int) -> list[dict]:
    """Read the current persisted itinerary for a trip."""
    return lakebase.run_query(
        """
        SELECT i.itinerary_item_id, i.scheduled_at, i.duration_minutes,
               i.rationale, i.status, a.activity_id, a.name AS activity_name,
               a.category, a.indoor
        FROM itinerary_items i
        JOIN activities a ON a.activity_id = i.activity_id
        WHERE i.trip_id = %s
        ORDER BY i.scheduled_at
        """,
        (trip_id,),
    )


@mcp.tool
def add_itinerary_item(
    trip_id: int,
    activity_id: int,
    scheduled_at: str,
    duration_minutes: int = 120,
    rationale: str = "Added by the travel agent",
) -> dict:
    """Add an activity to the itinerary and persist the change in Lakebase."""
    parsed_time = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    if duration_minutes <= 0 or duration_minutes > 1440:
        raise ValueError("duration_minutes must be between 1 and 1440")
    return lakebase.run_write_returning(
        """
        INSERT INTO itinerary_items
            (trip_id, activity_id, scheduled_at, duration_minutes, rationale)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING itinerary_item_id, trip_id, activity_id, scheduled_at,
                  duration_minutes, rationale, status
        """,
        (trip_id, activity_id, parsed_time, duration_minutes, rationale),
    )


@mcp.tool
def move_itinerary_item(itinerary_item_id: int, new_scheduled_at: str, reason: str) -> dict:
    """Reschedule an itinerary item and record the weather-aware reason."""
    parsed_time = datetime.fromisoformat(new_scheduled_at.replace("Z", "+00:00"))
    row = lakebase.run_write_returning(
        """
        UPDATE itinerary_items
        SET scheduled_at = %s, rationale = %s
        WHERE itinerary_item_id = %s
        RETURNING itinerary_item_id, trip_id, activity_id, scheduled_at, rationale, status
        """,
        (parsed_time, reason, itinerary_item_id),
    )
    if row is None:
        raise ValueError(f"Itinerary item {itinerary_item_id} does not exist")
    return row


@mcp.tool
def remove_itinerary_item(itinerary_item_id: int) -> dict:
    """Remove an itinerary item from Lakebase."""
    row = lakebase.run_write_returning(
        "DELETE FROM itinerary_items WHERE itinerary_item_id = %s RETURNING itinerary_item_id, trip_id, activity_id",
        (itinerary_item_id,),
    )
    if row is None:
        raise ValueError(f"Itinerary item {itinerary_item_id} does not exist")
    return {"removed": True, **row}


@mcp.tool
def generate_packing_list(trip_id: int) -> list[dict]:
    """Create and persist a deterministic packing list from stored weather data."""
    weather = lakebase.run_query(
        """
        SELECT MAX(precipitation_probability) AS max_rain,
               MIN(temperature_c) AS min_temperature
        FROM weather_snapshots WHERE trip_id = %s
        """,
        (trip_id,),
    )[0]
    items = [("Comfortable walking shoes", "Useful for city walking and outdoor activities")]
    if weather["max_rain"] is not None and weather["max_rain"] >= 40:
        items.append(("Compact umbrella", "Rain probability is at least 40%"))
    if weather["min_temperature"] is not None and float(weather["min_temperature"]) < 15:
        items.append(("Light jacket", "Forecast temperature falls below 15°C"))

    for item_name, reason in items:
        lakebase.run_write(
            """
            INSERT INTO packing_items (trip_id, item_name, reason)
            VALUES (%s, %s, %s)
            ON CONFLICT (trip_id, item_name) DO UPDATE SET reason = EXCLUDED.reason
            """,
            (trip_id, item_name, reason),
        )
    return lakebase.run_query(
        "SELECT packing_item_id, item_name, reason, packed FROM packing_items WHERE trip_id = %s ORDER BY item_name",
        (trip_id,),
    )


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")))
