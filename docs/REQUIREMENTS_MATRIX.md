# Capstone Requirements Matrix

| ID | Requirement | Code artifact | Acceptance test | Screenshot |
|---|---|---|---|---|
| R1 | Spark pipeline | `pipeline/ingest_destinations_weather.py` | Bronze and Silver Delta tables contain rows | Spark results and table counts |
| R2 | Third-party API | Open-Meteo and Wikimedia calls in pipeline | Lisbon coordinates, forecast, and article text returned | Notebook API output |
| R3 | Unstructured data | Wikimedia text in `activity_documents` | Documents contain meaningful text | Lakebase query |
| R4 | Semantic retrieval | Embeddings plus cosine search in MCP | Natural-language query returns ranked activities | Agent tool response |
| R5 | Lakebase relational data | `sql/setup.sql` | PKs, FKs, seed data, and multiple related tables | SQL results and constraints |
| R6 | Frontend | `frontend/app.py` and template | Trip dashboard loads in Databricks Apps | App overview |
| R7 | Agent reads | Weather, itinerary, and semantic-search tools | Agent answers using current stored data | Agent conversation |
| R8 | Agent writes | Add, move, remove, and packing tools | Database state changes and persists after refresh | Before/after SQL and app |

## Scope guardrails

- One demo user and one three-day Lisbon trip.
- No authentication UI, booking engine, maps, or payment integration.
- No custom model-serving endpoint.
- Agent Bricks consumes the FastMCP server using the same pattern as Day 3.
- Lakebase secrets, Flask deployment, and `pgvector` follow the validated Days 1 and 2 patterns.
