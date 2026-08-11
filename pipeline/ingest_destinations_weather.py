# Databricks notebook source
# MAGIC %md
# MAGIC # Open-Meteo + Wikimedia -> Spark -> Delta -> Lakebase + pgvector
# MAGIC
# MAGIC This capstone pipeline performs real Spark transformations and preserves
# MAGIC Bronze/Silver Delta evidence before synchronizing operational data to Lakebase.

# COMMAND ----------

# MAGIC %pip uninstall -y psycopg2 psycopg2-binary psycopg-binary psycopg-c
# MAGIC %pip install -q --no-cache-dir 'databricks-sdk>=0.89.0' 'psycopg>=3.2,<3.3' requests sentence-transformers

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os

# Force Psycopg's pure-Python implementation. The binary implementation
# aborts the Python process on the current Databricks compute.
os.environ["PSYCOPG_IMPL"] = "python"

from datetime import date, timedelta

import psycopg
import requests
from databricks.sdk import WorkspaceClient
from sentence_transformers import SentenceTransformer
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, DoubleType, IntegerType, StringType, StructField, StructType

DESTINATION = "Lisbon"
START_DATE = date.today() + timedelta(days=1)
END_DATE = START_DATE + timedelta(days=2)
BRONZE_TABLE = "workspace.default.trip_weather_bronze"
SILVER_TABLE = "workspace.default.trip_weather_silver"
WIKIMEDIA_ACTIVITIES = {
    "Belém, Lisbon": "Belém Riverside Walk",
    "Jerónimos Monastery": "Jerónimos Monastery",
    "Calouste Gulbenkian Museum": "Calouste Gulbenkian Museum",
    "Alfama": "Alfama Walking Tour",
    "Time Out Market Lisboa": "Time Out Market Food Tour",
    "Lisbon Oceanarium": "Oceanário de Lisboa",
}

# COMMAND ----------

geocoding = requests.get(
    "https://geocoding-api.open-meteo.com/v1/search",
    params={"name": DESTINATION, "count": 1, "language": "en", "format": "json"},
    timeout=20,
).json()["results"][0]

forecast_payload = requests.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": geocoding["latitude"], "longitude": geocoding["longitude"],
        "start_date": START_DATE.isoformat(), "end_date": END_DATE.isoformat(),
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "timezone": "auto",
    },
    timeout=20,
).json()

# COMMAND ----------

# A Spark DataFrame is created from raw API arrays, then transformed with Spark.
raw_rows = list(zip(
    forecast_payload["hourly"]["time"],
    forecast_payload["hourly"]["temperature_2m"],
    forecast_payload["hourly"]["precipitation_probability"],
    forecast_payload["hourly"]["weather_code"],
))
raw_schema = StructType([
    StructField("forecast_time_raw", StringType(), False),
    StructField("temperature_c", DoubleType(), True),
    StructField("precipitation_probability", IntegerType(), True),
    StructField("weather_code", IntegerType(), True),
])
bronze_df = spark.createDataFrame(raw_rows, raw_schema).withColumn("ingested_at", F.current_timestamp())
bronze_df.write.mode("overwrite").format("delta").saveAsTable(BRONZE_TABLE)

silver_df = (
    bronze_df
    .withColumn("forecast_time", F.to_timestamp("forecast_time_raw"))
    .withColumn("destination_name", F.lit(DESTINATION))
    .withColumn(
        "weather_label",
        F.when(F.col("weather_code") == 0, "clear")
         .when(F.col("weather_code").between(1, 3), "cloudy")
         .when(F.col("weather_code").between(51, 67), "rain")
         .otherwise("other"),
    )
    .drop("forecast_time_raw")
)
silver_df.write.mode("overwrite").format("delta").saveAsTable(SILVER_TABLE)
display(silver_df.groupBy("weather_label").agg(F.count("*").alias("hours"), F.round(F.avg("temperature_c"), 1).alias("avg_temperature_c")))

# COMMAND ----------

def wikipedia_extract(title: str) -> dict:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query", "prop": "extracts|info", "exintro": 1,
            "explaintext": 1, "inprop": "url", "redirects": 1,
            "titles": title, "format": "json", "origin": "*",
        },
        headers={"User-Agent": "NazaAITripPlanner/1.0 educational-capstone"},
        timeout=20,
    )
    response.raise_for_status()
    page = next(iter(response.json()["query"]["pages"].values()))
    return {"title": page.get("title", title), "text": page.get("extract", ""), "source_url": page.get("fullurl")}


wiki_rows = [
    {**wikipedia_extract(title), "activity_name": activity_name}
    for title, activity_name in WIKIMEDIA_ACTIVITIES.items()
]
wiki_df = spark.createDataFrame(wiki_rows).filter(F.length("text") > 100).dropDuplicates(["title"])
display(wiki_df.select("title", F.length("text").alias("text_length"), "source_url"))

# COMMAND ----------

workspace = WorkspaceClient()

if not hasattr(workspace, "postgres"):
    raise RuntimeError(
        "The loaded databricks-sdk does not expose workspace.postgres. "
        "Run the %pip cell, restart Python, and then resume from the imports cell."
    )

current_user = workspace.current_user.me()

print("Databricks SDK:", __import__("databricks.sdk").sdk.__version__)
print("Psycopg:", psycopg.__version__)
print("Psycopg implementation:", psycopg.pq.__impl__)
print("Lakebase Postgres API available:", hasattr(workspace, "postgres"))

LAKEBASE_ENDPOINT = (
    "projects/naza-ai-trip-planner/"
    "branches/production/"
    "endpoints/primary"
)
LAKEBASE_HOST = (
    "ep-winter-moon-d839l59e."
    "database.us-east-2.cloud.databricks.com"
)

credential = workspace.postgres.generate_database_credential(
    endpoint=LAKEBASE_ENDPOINT
)
if not credential.token:
    raise RuntimeError("Lakebase OAuth credential could not be generated.")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
if model.get_sentence_embedding_dimension() != 384:
    raise RuntimeError("The embedding model must produce 384-dimensional vectors.")

weather_rows = silver_df.select(
    "forecast_time",
    "temperature_c",
    "precipitation_probability",
    "weather_code",
).collect()
article_rows = wiki_df.collect()

with psycopg.connect(
    host=LAKEBASE_HOST,
    port=5432,
    dbname="databricks_postgres",
    user=current_user.user_name,
    password=credential.token,
    sslmode="require",
) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT trip_id
            FROM trips
            WHERE lower(destination_name) = lower(%s)
            ORDER BY trip_id
            LIMIT 1
            """,
            (DESTINATION,),
        )
        trip = cursor.fetchone()
        if not trip:
            raise RuntimeError(f"No trip was found for {DESTINATION}.")
        trip_id = trip[0]

        for row in weather_rows:
            cursor.execute(
                """
                INSERT INTO weather_snapshots (
                    trip_id,
                    forecast_time,
                    temperature_c,
                    precipitation_probability,
                    weather_code,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, 'Open-Meteo')
                ON CONFLICT (trip_id, forecast_time) DO UPDATE SET
                    temperature_c = EXCLUDED.temperature_c,
                    precipitation_probability = EXCLUDED.precipitation_probability,
                    weather_code = EXCLUDED.weather_code,
                    source = EXCLUDED.source,
                    fetched_at = NOW()
                """,
                (
                    trip_id,
                    row.forecast_time,
                    row.temperature_c,
                    row.precipitation_probability,
                    row.weather_code,
                ),
            )

        for article in article_rows:
            cursor.execute(
                """
                SELECT activity_id, name, category, description
                FROM activities
                WHERE lower(destination_name) = lower(%s)
                  AND lower(name) = lower(%s)
                LIMIT 1
                """,
                (DESTINATION, article.activity_name),
            )
            activity = cursor.fetchone()
            if not activity:
                print(f"Activity not matched: {article.activity_name}")
                continue

            document_text = (
                f"{activity[1]}. Category: {activity[2]}. "
                f"{activity[3] or ''}\n\n{article.text}"
            )
            embedding = model.encode(
                document_text,
                normalize_embeddings=True,
            ).tolist()
            vector_literal = "[" + ",".join(map(str, embedding)) + "]"

            cursor.execute(
                """
                INSERT INTO activity_documents (
                    activity_id,
                    document_text,
                    embedding
                )
                VALUES (%s, %s, %s::vector)
                ON CONFLICT (activity_id) DO UPDATE SET
                    document_text = EXCLUDED.document_text,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                """,
                (activity[0], document_text, vector_literal),
            )

    conn.commit()

with psycopg.connect(
    host=LAKEBASE_HOST,
    port=5432,
    dbname="databricks_postgres",
    user=current_user.user_name,
    password=credential.token,
    sslmode="require",
) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM weather_snapshots WHERE trip_id = %s",
            (trip_id,),
        )
        weather_count = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM activity_documents
            WHERE embedding IS NOT NULL
            """
        )
        document_count = cursor.fetchone()[0]

assert weather_count > 0, "No weather snapshots were stored."
assert document_count > 0, "No activity embeddings were stored."

print("Lakebase OAuth connection: OK")
print("Psycopg implementation:", psycopg.pq.__impl__)
print("Weather snapshots for trip:", weather_count)
print("Documents with embeddings:", document_count)

print("Pipeline completed: Open-Meteo + Wikimedia -> Spark Delta -> Lakebase + pgvector")
