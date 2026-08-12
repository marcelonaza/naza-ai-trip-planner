# Naza AI Trip Planner

An interactive, weather-aware AI travel planner built as the capstone project for **The Rise of the AI Data Engineer** Databricks boot camp.

The project combines a Spark data pipeline, external APIs, Lakebase PostgreSQL, vector embeddings, semantic retrieval, MCP tools, and a Databricks App that reads and writes operational data.

## Project status

**Completed and functionally validated — 11 August 2026**

The deployed application successfully supports:

- weather-aware itinerary generation;
- semantic activity discovery with embeddings and `pgvector`;
- adding and removing activities from an itinerary;
- persisted itinerary changes in Lakebase;
- contextual packing-list generation;
- packing-item state updates preserved after page refresh;
- Databricks App OAuth authentication to Lakebase.

See [`resume.md`](resume.md) for the concise test history and results.

## Capstone coverage

| Requirement | Implementation | Evidence |
|---|---|---|
| Spark data pipeline | `pipeline/ingest_destinations_weather.py` | Spark transformations and Delta writes |
| Third-party APIs | Open-Meteo Geocoding/Forecast and Wikimedia | Raw API responses and pipeline output |
| Unstructured data | Wikimedia destination and attraction descriptions | `activity_documents` and generated embeddings |
| Operational database | Lakebase PostgreSQL | Trips, activities, itinerary, weather, and packing data |
| Semantic retrieval | `all-MiniLM-L6-v2` + Lakebase `pgvector` | Natural-language activity search |
| AI actions | FastMCP server in `mcp_server/` | Retrieval and persisted itinerary operations |
| Interactive application | Flask application in `frontend/` | Deployed Databricks App walkthrough |
| Evaluation | Deterministic unit tests and end-to-end functional tests | Test history in `resume.md` |

## Architecture

1. The Spark pipeline calls Open-Meteo and Wikimedia.
2. Spark normalizes the API payloads and writes Bronze and Silver Delta tables.
3. Curated records are synchronized to Lakebase.
4. Unstructured activity documents are embedded and stored with `pgvector`.
5. A FastMCP server exposes retrieval and write tools for agent workflows.
6. The Flask Databricks App presents the trip, weather, semantic results, itinerary, and packing list.
7. User actions are written transactionally to Lakebase and reloaded after refresh.

## End-to-end data flow

```text
Open-Meteo + Wikimedia
          |
          v
 Spark / Delta pipeline
          |
          v
Lakebase PostgreSQL + pgvector
          |
          +-------------------+
          |                   |
          v                   v
  FastMCP tools       Flask Databricks App
                              |
                              v
              Interactive itinerary and packing list
```

## Key features

### Weather intelligence

- 72-hour forecast loaded from Open-Meteo;
- temperature and conditions displayed in the application;
- weather context used when generating the itinerary and packing list.

### Semantic activity discovery

- six activity documents enriched with Wikimedia content;
- embeddings generated with `all-MiniLM-L6-v2`;
- vectors stored and queried through Lakebase `pgvector`;
- natural-language queries return relevant activities, such as the Calouste Gulbenkian Museum for `museum`.

### Interactive itinerary

- generate a multi-day itinerary;
- add an activity returned by semantic search;
- remove an activity;
- persist every change in Lakebase;
- reload the same state after a browser refresh.

### Weather-aware packing list

- generate a contextual list;
- mark or unmark individual items;
- calculate packing progress;
- preserve item state after refresh.

## Verified demo data

| Metric | Validated value |
|---|---:|
| Forecast horizon | 72 hours |
| Embedded activity documents | 6/6 |
| Generated itinerary | 6 persisted activities |
| Packing-list items | 5 |
| Persisted packed state | 2/5 (40%) |
| Demo destination | Lisbon, Portugal |

These values describe the final validation session and may change when the demo data is regenerated.

## Repository layout

```text
pipeline/       Databricks Spark ingestion notebook
sql/            Lakebase schema and deterministic demo seed
mcp_server/     FastMCP application and agent tools
frontend/       Interactive Flask Databricks App
tests/          Unit tests for deterministic business rules
docs/           Setup, validation, and evidence checklists
resume.md       Concise test history and final results
```

## Deployment order

1. Run `sql/setup.sql` in the Lakebase SQL editor.
2. Import `pipeline/ingest_destinations_weather.py` into the Databricks Git Folder.
3. Run the dependency cell, restart Python when prompted, and continue from the imports cell.
4. Synchronize the curated records and embeddings to Lakebase.
5. Deploy `mcp_server/` as a Databricks App and connect its MCP URL to Agent Bricks when required.
6. Deploy `frontend/` as the **Naza AI Trip Planner** Databricks App.
7. Grant the Databricks App service principal the required Lakebase role and read/write permissions.
8. Execute the validation checklist and capture the required evidence.

Lakebase authentication uses a temporary OAuth credential generated at runtime. No database password or personal access token is stored in the repository.

Detailed agent instructions are available in [`docs/AGENT_SETUP.md`](docs/AGENT_SETUP.md). The workspace validation procedure is available in [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Local verification

The deterministic tests do not require Lakebase, Databricks credentials, or network access:

```bash
python -m unittest discover -s tests -v
python -m compileall -q frontend mcp_server pipeline tests
```

External APIs, Spark and Delta writes, Lakebase synchronization, OAuth, vector retrieval, MCP discovery, and Databricks App rendering are integration tests and must be verified in the Databricks workspace.

## Final functional validation

The following user-facing flows were tested successfully in the deployed application:

1. application startup and OAuth connection to Lakebase;
2. itinerary generation and persistence;
3. semantic search for `museum`;
4. adding a semantic result to the itinerary and preserving it after refresh;
5. removing an itinerary item and preserving the deletion after refresh;
6. generating a weather-aware packing list;
7. marking packing items and preserving the 40% progress after refresh.

Full results are documented in [`resume.md`](resume.md).

## Security

- no hardcoded secrets;
- no personal access tokens in source control;
- short-lived Databricks OAuth credentials;
- application identity mapped to a Lakebase PostgreSQL role;
- parameterized database operations and transactional mutations.

## Demo scope

- one demo user;
- one three-day Lisbon trip;
- six Wikimedia-enriched activities;
- 72 hours of Open-Meteo weather;
- seven related Lakebase tables;
- eight MCP tools for retrieval and persisted actions;
- an interactive Databricks App backed by Lakebase and `pgvector`.

## Future development — Phase 2

Phase 1 was completed as a validated capstone MVP and received **86/100**. Future work will focus on Databricks Job operationalization, resilient API integration, pgvector search in the frontend, Agent Bricks evidence, runtime consistency, and guarded integration testing.

See [`PHASE_2_ROADMAP.md`](PHASE_2_ROADMAP.md) for the planned milestones and acceptance criteria.

## Author

**Marcelo Naza**  
AI Data Engineer | Data Engineering, Databricks, Lakebase, RAG, Agents, and MCP

