"""Interactive Databricks App for the Naza AI Trip Planner."""

import os
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request
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


def payload():
    return request.get_json(silent=True) or {}


def require_int(data, key):
    try:
        return int(data[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def require_app_request():
    if request.headers.get("X-Requested-With") != "NazaTripPlanner":
        raise ValueError("This action must originate from the Trip Planner interface")


@app.errorhandler(ValueError)
def bad_request(error):
    return jsonify({"ok": False, "error": str(error)}), 400


@app.errorhandler(Exception)
def server_error(error):
    app.logger.exception("Request failed")
    return jsonify({"ok": False, "error": str(error)}), 500


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
           WHERE i.trip_id = %s AND i.status <> 'cancelled' ORDER BY i.scheduled_at""",
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
    return jsonify({"trip": rows_to_json([trip])[0], "weather": rows_to_json(weather),
                    "itinerary": rows_to_json(itinerary), "activities": rows_to_json(activities),
                    "packing": rows_to_json(packing), "summary": summary,
                    "generated_at": datetime.now().isoformat()})


@app.get("/api/activities/search")
def search_activities():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"ok": True, "results": []})
    rows = lakebase.query(
        """SELECT a.activity_id, a.name, a.category, a.indoor, a.description,
                  (d.embedding IS NOT NULL) AS embedded,
                  ts_rank_cd(to_tsvector('english', d.document_text),
                             websearch_to_tsquery('english', %s)) AS relevance
           FROM activities a JOIN activity_documents d ON d.activity_id = a.activity_id
           WHERE to_tsvector('english', d.document_text) @@ websearch_to_tsquery('english', %s)
              OR a.name ILIKE %s OR a.category ILIKE %s
           ORDER BY relevance DESC, a.name LIMIT 6""",
        (term, term, f"%{term}%", f"%{term}%"),
    )
    return jsonify({"ok": True, "query": term, "results": rows_to_json(rows)})


@app.post("/api/itinerary/generate")
def generate_itinerary():
    require_app_request()
    trip_id = require_int(payload(), "trip_id")
    with lakebase.transaction() as cursor:
        cursor.execute(
            """WITH trip AS (
                   SELECT trip_id, destination_name, start_date FROM trips WHERE trip_id = %s
               ), ranked AS (
                   SELECT a.activity_id, a.name, a.category, a.indoor,
                          row_number() OVER (ORDER BY
                            CASE WHEN a.indoor THEN 1 ELSE 0 END,
                            CASE WHEN a.category IN ('history','food','culture') THEN 0 ELSE 1 END,
                            a.activity_id) AS rn
                   FROM activities a, trip t
                   WHERE lower(a.destination_name) = lower(t.destination_name)
               )
               INSERT INTO itinerary_items
                   (trip_id, activity_id, scheduled_at, duration_minutes, rationale, status)
               SELECT t.trip_id, r.activity_id,
                      (t.start_date + ((r.rn - 1) / 2)::int)::timestamp
                        + CASE WHEN r.rn %% 2 = 1 THEN time '10:00' ELSE time '15:00' END,
                      120,
                      CASE WHEN r.indoor
                        THEN 'AI-selected indoor option resilient to rain.'
                        ELSE 'AI-selected outdoor experience aligned with the forecast.' END,
                      'planned'
               FROM ranked r CROSS JOIN trip t
               WHERE r.rn <= 6
                 AND NOT EXISTS (
                   SELECT 1 FROM itinerary_items i
                   WHERE i.trip_id=t.trip_id AND i.activity_id=r.activity_id
                     AND i.status <> 'cancelled'
                 )
               RETURNING itinerary_item_id""",
            (trip_id,),
        )
        created = len(cursor.fetchall())
    return jsonify({"ok": True, "message": f"AI itinerary saved with {created} activities", "created": created})


@app.post("/api/itinerary/items")
def add_itinerary_item():
    require_app_request()
    data = payload()
    trip_id, activity_id = require_int(data, "trip_id"), require_int(data, "activity_id")
    rows = lakebase.execute_returning(
        """INSERT INTO itinerary_items (trip_id, activity_id, scheduled_at, duration_minutes, rationale)
           SELECT t.trip_id, a.activity_id,
                  COALESCE((SELECT max(scheduled_at) + interval '3 hours' FROM itinerary_items WHERE trip_id=t.trip_id),
                           t.start_date::timestamp + time '10:00'),
                  120, 'Added from semantic activity discovery in the Databricks App.'
           FROM trips t JOIN activities a ON lower(a.destination_name)=lower(t.destination_name)
           WHERE t.trip_id=%s AND a.activity_id=%s
             AND NOT EXISTS (
               SELECT 1 FROM itinerary_items i
               WHERE i.trip_id=t.trip_id AND i.activity_id=a.activity_id AND i.status <> 'cancelled'
             )
           RETURNING itinerary_item_id""",
        (trip_id, activity_id),
    )
    if not rows:
        return jsonify({"ok": False, "error": "Trip or activity not found"}), 404
    return jsonify({"ok": True, "message": "Activity persisted to Lakebase", "item": rows_to_json(rows)[0]}), 201


@app.patch("/api/itinerary/items/<int:item_id>/cancel")
def cancel_itinerary_item(item_id):
    require_app_request()
    rows = lakebase.execute_returning(
        "UPDATE itinerary_items SET status='cancelled' WHERE itinerary_item_id=%s RETURNING itinerary_item_id, status",
        (item_id,),
    )
    if not rows:
        return jsonify({"ok": False, "error": "Itinerary item not found"}), 404
    return jsonify({"ok": True, "message": "Itinerary item cancelled; history preserved"})


@app.post("/api/packing/generate")
def generate_packing():
    require_app_request()
    trip_id = require_int(payload(), "trip_id")
    rows = lakebase.execute_returning(
        """WITH forecast AS (
             SELECT max(COALESCE(precipitation_probability,0)) rain,
                    min(temperature_c) min_temp FROM weather_snapshots WHERE trip_id=%s
           ), suggestions(item_name, reason) AS (
             VALUES ('Comfortable walking shoes','Recommended for city walks and sightseeing'),
                    ('Reusable water bottle','Useful throughout the three-day itinerary'),
                    ('Light jacket','Prepared for cooler mornings and evenings'),
                    ('Compact umbrella','Weather-aware protection when rain risk increases'),
                    ('Phone charger','Keeps maps and travel information available')
           )
           INSERT INTO packing_items(trip_id,item_name,reason)
           SELECT %s, s.item_name,
                  CASE WHEN s.item_name='Compact umbrella'
                       THEN s.reason || ' (maximum forecast risk: ' || COALESCE(f.rain,0) || '%%)'
                       ELSE s.reason END
           FROM suggestions s CROSS JOIN forecast f
           ON CONFLICT (trip_id,item_name) DO UPDATE SET reason=EXCLUDED.reason
           RETURNING packing_item_id""",
        (trip_id, trip_id),
    )
    return jsonify({"ok": True, "message": f"Weather-aware packing list saved ({len(rows)} items)"})


@app.patch("/api/packing/<int:item_id>")
def toggle_packing(item_id):
    require_app_request()
    data = payload()
    if not isinstance(data.get("packed"), bool):
        raise ValueError("packed must be true or false")
    rows = lakebase.execute_returning(
        "UPDATE packing_items SET packed=%s WHERE packing_item_id=%s RETURNING packing_item_id, packed",
        (data["packed"], item_id),
    )
    if not rows:
        return jsonify({"ok": False, "error": "Packing item not found"}), 404
    return jsonify({"ok": True, "message": "Packing status persisted", "item": rows_to_json(rows)[0]})


@app.get("/health")
def health():
    return {"status": "ok", "service": "naza-ai-trip-planner", "database": "Lakebase OAuth"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")))
