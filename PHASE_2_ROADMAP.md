# Phase 2 Roadmap — Production and Agentic Intelligence

## Purpose

Phase 1 of **Naza AI Trip Planner** was completed as the capstone project for *The Rise of the AI Data Engineer* boot camp and received a final score of **86/100**.

The first phase delivered a working end-to-end solution:

- Spark ingestion and Delta Bronze/Silver processing;
- Open-Meteo and Wikimedia integrations;
- Lakebase PostgreSQL operational storage;
- Wikimedia document embeddings stored with `pgvector`;
- FastMCP tools with real read and write actions;
- an interactive Databricks App with persisted itinerary and packing-list flows.

Phase 2 is a future evolution of the project. Its goal is to strengthen production readiness, operational evidence, vector retrieval in the frontend, and observable agent behavior.

## Phase 2 objectives

1. Operationalize the Spark pipeline as a reusable Databricks Job.
2. Improve resilience when calling external APIs.
3. Expose true vector similarity search in the frontend.
4. Demonstrate the Agent Bricks workflow with traceable read and write actions.
5. Align runtime dependencies across the pipeline, MCP server, and frontend.
6. Add integration tests and clearer operational error reporting.

## Workstreams

### 1. Databricks Job operationalization

Convert the Spark pipeline into a parameterized Databricks Job.

Planned work:

- create a Databricks Job for `pipeline/ingest_destinations_weather.py`;
- parameterize destination, country, latitude, longitude, start date, and forecast horizon;
- define retries, timeout, and failure notifications;
- optionally add a schedule for regular weather refreshes;
- retain idempotent Lakebase synchronization through `ON CONFLICT` upserts;
- capture job configuration, run URL, lineage, logs, and successful execution evidence.

Acceptance criteria:

- the pipeline runs successfully as a Databricks Job;
- Bronze and Silver Delta outputs are refreshed;
- Lakebase counts remain correct after repeated execution;
- a failed task exposes a clear operational error.

### 2. External API resilience

Strengthen Open-Meteo and Wikimedia calls for production-style failure handling.

Planned work:

- call `response.raise_for_status()` for every geocoding and forecast request;
- define explicit connection and read timeouts;
- add bounded retries with exponential backoff;
- handle HTTP 429 and temporary 5xx responses;
- validate empty geocoding results and incomplete forecast payloads;
- return actionable messages for network, API, and validation failures;
- add structured logging without exposing secrets.

Acceptance criteria:

- all HTTP calls validate response status;
- temporary failures are retried safely;
- empty or invalid responses do not create partial Lakebase records;
- users and operators receive clear error messages.

### 3. Vector search in the frontend

The Phase 1 MCP tool performs cosine similarity search with `pgvector`. The Phase 1 frontend search endpoint uses PostgreSQL full-text search with an `ILIKE` fallback.

Phase 2 will make the application panel use the same vector retrieval approach as the MCP tool.

Planned work:

- generate a query embedding with the same `all-MiniLM-L6-v2` model;
- query `activity_documents.embedding` using pgvector cosine distance;
- return a normalized similarity score;
- order results from most to least relevant;
- apply a configurable relevance threshold;
- display similarity scores and retrieval metadata in the interface;
- retain a documented keyword fallback for unavailable embedding services.

Acceptance criteria:

- natural-language queries use vector similarity by default;
- results display similarity scores;
- low-relevance results are filtered;
- frontend and MCP retrieval behavior are consistent;
- tests distinguish vector retrieval from keyword fallback.

### 4. Agent Bricks demonstration and observability

Provide direct evidence of the agent selecting and using MCP tools.

Planned evaluation flow:

1. ask the agent to inspect the trip and weather forecast;
2. request a suitable indoor or outdoor activity using semantic search;
3. require a weather-aware explanation;
4. ask the agent to add or move an itinerary activity;
5. have the agent reread the itinerary;
6. confirm that the write was persisted in Lakebase.

Planned evidence:

- external MCP registration;
- discovered MCP tool list;
- Agent Bricks conversation transcript;
- tool-call traces and execution results;
- post-write read-back confirmation;
- Lakebase query showing the persisted change.

Acceptance criteria:

- the agent chooses appropriate tools without invented data;
- its recommendation references retrieved weather and activity context;
- write operations are followed by read-back verification;
- the transcript clearly distinguishes retrieved facts from generated explanation.

### 5. Runtime consistency

Standardize PostgreSQL connectivity across all components.

Planned work:

- remove remaining reliance on `PSYCOPG_IMPL=python`;
- use the validated `psycopg[binary]` dependency where supported;
- document the final runtime and dependency versions;
- keep OAuth credentials short-lived and generated at runtime;
- verify the pipeline, MCP App, and frontend independently.

Acceptance criteria:

- all deployed components use a documented Psycopg configuration;
- no component requires an unavailable system `libpq`;
- OAuth authentication works without stored database passwords or personal access tokens.

### 6. Integration testing and operational UX

Add guarded tests for real infrastructure while keeping deterministic unit tests fast.

Planned work:

- add an environment-controlled Lakebase integration test;
- validate one read and one transactional write with rollback or isolated test data;
- add an API integration test for vector search;
- verify idempotent pipeline reruns;
- distinguish validation, database, authentication, API, and rate-limit errors in the frontend;
- add correlation IDs and concise structured logs.

Acceptance criteria:

- unit tests continue to run without external services;
- integration tests run only when explicitly enabled;
- one real read path and one real write path are automatically validated;
- frontend errors are actionable and do not expose credentials or stack traces.

## Proposed delivery sequence

| Milestone | Scope | Expected outcome |
|---|---|---|
| M1 | API resilience and runtime consistency | Stable ingestion and deployment environment |
| M2 | Databricks Job operationalization | Repeatable, observable pipeline executions |
| M3 | Frontend pgvector retrieval | True semantic search across both UI and MCP |
| M4 | Agent Bricks evidence | Verified tool selection, reasoning, and persisted writes |
| M5 | Integration tests and operational UX | Safer regression testing and clearer failures |

## Phase 2 definition of done

Phase 2 will be considered complete when:

- the Spark pipeline runs as a parameterized Databricks Job;
- API requests include status validation, timeouts, and bounded retries;
- the frontend uses pgvector similarity with visible relevance scores;
- an Agent Bricks transcript demonstrates weather lookup, semantic retrieval, a persisted write, and read-back confirmation;
- all components use a consistent, documented Psycopg runtime;
- guarded integration tests validate a real Lakebase read and write;
- technical evidence is stored in the repository without secrets.

## Out of scope

The following ideas may be evaluated after Phase 2:

- multi-user authentication and authorization;
- multiple destinations per trip;
- live booking and payment integrations;
- real-time streaming ingestion;
- mobile-native applications;
- production SLAs and multi-region deployment.

## Expected outcome

Phase 2 will evolve the project from a validated capstone MVP into a stronger portfolio reference for production-oriented AI Data Engineering, demonstrating not only a working application but also orchestration, resilience, retrieval quality, agent observability, and operational verification.
