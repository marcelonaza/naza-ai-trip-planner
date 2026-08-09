# Databricks notebook source
# MAGIC %md
# MAGIC # Open-Meteo + Wikimedia -> Spark -> Delta -> Lakebase + pgvector
# MAGIC
# MAGIC This capstone pipeline performs real Spark transformations and preserves
# MAGIC Bronze/Silver Delta evidence before synchronizing operational data to Lakebase.

# COMMAND ----------

# MAGIC %pip install -q 'databricks-sdk>=0.61.0' psycopg2-binary requests sentence-transformers

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import base64
from datetime import date, timedelta
from urllib.parse import urlparse

import psycopg2
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
secret = workspace.secrets.get_secret(scope="database", key="lakebase-url")
lakebase_url = base64.b64decode(secret.value).decode("utf-8")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

with psycopg2.connect(lakebase_url) as conn, conn.cursor() as cursor:
    cursor.execute("SELECT trip_id FROM trips WHERE name = 'Lisbon Adventure' ORDER BY trip_id LIMIT 1")
    trip_id = cursor.fetchone()[0]
    for row in silver_df.select("forecast_time", "temperature_c", "precipitation_probability", "weather_code").collect():
        cursor.execute(
            """
            INSERT INTO weather_snapshots
                (trip_id, forecast_time, temperature_c, precipitation_probability, weather_code)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (trip_id, forecast_time) DO UPDATE SET
                temperature_c = EXCLUDED.temperature_c,
                precipitation_probability = EXCLUDED.precipitation_probability,
                weather_code = EXCLUDED.weather_code,
                fetched_at = NOW()
            """,
            (trip_id, row.forecast_time, row.temperature_c, row.precipitation_probability, row.weather_code),
        )

    for article in wiki_df.collect():
        cursor.execute(
            "SELECT activity_id, name, category, description FROM activities WHERE destination_name = %s AND lower(name) = lower(%s)",
            (DESTINATION, article.activity_name),
        )
        activity = cursor.fetchone()
        if not activity:
            continue
        document_text = f"{activity[1]}. Category: {activity[2]}. {activity[3]}\n\n{article.text}"
        embedding = model.encode(document_text).tolist()
        vector_literal = "[" + ",".join(str(value) for value in embedding) + "]"
        cursor.execute(
            """
            INSERT INTO activity_documents (activity_id, document_text, embedding)
            VALUES (%s, %s, %s::vector)
            ON CONFLICT (activity_id) DO UPDATE SET
                document_text = EXCLUDED.document_text,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
            """,
            (activity[0], document_text, vector_literal),
        )
    conn.commit()

print("Pipeline completed: Open-Meteo + Wikimedia -> Spark Delta -> Lakebase + pgvector")
