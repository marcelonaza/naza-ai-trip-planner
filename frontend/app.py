"""Databricks App frontend for the Naza AI Trip Planner."""

import os
from datetime import date, datetime

from flask import Flask, jsonify, render_template

import lakebase

app = Flask(__name__)


def json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "as_tuple"):
        return float(value)
    return value


def rows_to_json(rows):
    return [{key: json_safe(value) for key, value in row.items()} for row in rows]


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/dashboard")
def dashboard():
    trips = lakebase.query("SELECT * FROM trips ORDER BY trip_id LIMIT 1")
    if not trips:
        return jsonify({"error": "Run sql/setup.sql before opening the app"}), 404
    trip = trips[0]
    trip_id = trip["trip_id"]
    weather = lakebase.query(
        """
        SELECT forecast_time, temperature_c, precipitation_probability, weather_code
        FROM weather_snapshots WHERE trip_id = %s ORDER BY forecast_time LIMIT 24
        """,
        (trip_id,),
    )
    itinerary = lakebase.query(
        """
        SELECT i.itinerary_item_id, i.scheduled_at, i.duration_minutes, i.rationale,
               i.status, a.name, a.category, a.indoor
        FROM itinerary_items i JOIN activities a ON a.activity_id = i.activity_id
        WHERE i.trip_id = %s ORDER BY i.scheduled_at
        """,
        (trip_id,),
    )
    activities = lakebase.query(
        "SELECT activity_id, name, category, indoor, description FROM activities WHERE destination_name = %s ORDER BY name",
        (trip["destination_name"],),
    )
    packing = lakebase.query(
        "SELECT packing_item_id, item_name, reason, packed FROM packing_items WHERE trip_id = %s ORDER BY item_name",
        (trip_id,),
    )
    return jsonify({
        "trip": rows_to_json([trip])[0],
        "weather": rows_to_json(weather),
        "itinerary": rows_to_json(itinerary),
        "activities": rows_to_json(activities),
        "packing": rows_to_json(packing),
    })


@app.get("/health")
def health():
    return {"status": "ok", "service": "naza-ai-trip-planner"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")))
