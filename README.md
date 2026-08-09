# Naza AI Trip Planner

Weather-aware travel planning capstone for the Rise of the AI Data Engineer boot camp.

## Capstone coverage

| Requirement | Implementation | Evidence |
|---|---|---|
| Spark data pipeline | `pipeline/ingest_destinations_weather.py` | Spark transformations and Delta writes |
| Third-party API | Open-Meteo Geocoding/Forecast and Wikimedia | Raw API responses and pipeline output |
| Unstructured data | Wikimedia destination and attraction text | `activity_documents` and embeddings |
| Databricks App frontend | Flask app in `frontend/` | Deployed application walkthrough |
| AI agent with actions | FastMCP server in `mcp_server/` | Read, semantic search, add/move/remove itinerary items |
| Operational database | Lakebase PostgreSQL | Trips, activities, itinerary, weather and packing data |
| Semantic retrieval | `all-MiniLM-L6-v2` + Lakebase `pgvector` | Natural-language activity search |

## Architecture

1. The Spark notebook calls Open-Meteo and Wikimedia.
2. Spark normalizes the API payloads and writes Bronze/Silver Delta tables.
3. Curated records are synchronized to Lakebase.
4. Unstructured activity documents are embedded and stored with `pgvector`.
5. A FastMCP server exposes retrieval and write tools to Agent Bricks.
6. A Flask Databricks App presents the trip, weather, itinerary, and packing list.

## Repository layout

```text
pipeline/       Databricks Spark ingestion notebook
sql/            Lakebase schema and deterministic demo seed
mcp_server/     FastMCP application for Agent Bricks
frontend/       Flask Databricks App
tests/          Unit tests for deterministic business rules
docs/           Requirement, test, and screenshot checklist
```

## Deployment order

1. Run `sql/setup.sql` in the Lakebase SQL editor.
2. Configure the existing `database/lakebase-url` Databricks secret.
3. Import and run `pipeline/ingest_destinations_weather.py`.
4. Deploy `mcp_server/` as a Databricks App and connect its MCP URL to Agent Bricks.
5. Deploy `frontend/` as a second Databricks App.
6. Execute the tests in `docs/VALIDATION.md` and capture every required screenshot.

No credentials or personal access tokens belong in this repository.
