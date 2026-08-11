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
        """SELECT forecast_time, temperature_c, precipitation_probability,
                  weather_code, source
           FROM weather_snapshots WHERE trip_id = %s ORDER BY forecast_time""",
        (trip_id,),
    )
    itinerary = lakebase.query(
        """SELECT i.itinerary_item_id, i.scheduled_at, i.duration_minutes,
                  i.rationale, i.status, a.name, a.category, a.indoor
           FROM itinerary_items i JOIN activities a ON a.activity_id = i.activity_id
           WHERE i.trip_id = %s ORDER BY i.scheduled_at""",
        (trip_id,),
    )
    activities = lakebase.query(
        """SELECT a.activity_id, a.name, a.category, a.indoor, a.description,
                  a.source_url, (d.embedding IS NOT NULL) AS embedded
           FROM activities a
           LEFT JOIN activity_documents d ON d.activity_id = a.activity_id
           WHERE lower(a.destination_name) = lower(%s) ORDER BY a.name""",
        (trip["destination_name"],),
    )
    packing = lakebase.query(
        """SELECT packing_item_id, item_name, reason, packed
           FROM packing_items WHERE trip_id = %s ORDER BY packed, item_name""",
        (trip_id,),
    )
    temperatures = [float(x["temperature_c"]) for x in weather if x["temperature_c"] is not None]
    rain = [int(x["precipitation_probability"] or 0) for x in weather]
    summary = {
        "forecast_hours": len(weather),
        "min_temperature_c": min(temperatures) if temperatures else None,
        "max_temperature_c": max(temperatures) if temperatures else None,
        "max_rain_probability": max(rain) if rain else None,
        "embedded_activities": sum(1 for x in activities if x["embedded"]),
        "indoor_activities": sum(1 for x in activities if x["indoor"]),
        "planned_items": len(itinerary),
        "packing_progress": round(100 * sum(1 for x in packing if x["packed"]) / len(packing)) if packing else 0,
    }
    return jsonify({
        "trip": rows_to_json([trip])[0],
        "weather": rows_to_json(weather),
        "itinerary": rows_to_json(itinerary),
        "activities": rows_to_json(activities),
        "packing": rows_to_json(packing),
        "summary": summary,
        "generated_at": datetime.now().isoformat(),
    })


@app.get("/health")
def health():
    return {"status": "ok", "service": "naza-ai-trip-planner", "database": "Lakebase OAuth"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")))
