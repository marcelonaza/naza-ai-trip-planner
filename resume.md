# Naza AI Trip Planner — Test Summary

## Validation overview

The final end-to-end validation was completed on **11 August 2026** in the deployed **Naza AI Trip Planner** Databricks App.

The goal was to verify the full flow from external data and embeddings to interactive user actions persisted in Lakebase.

## Test history

| # | Test | Expected result | Final result |
|---:|---|---|---|
| 1 | Application startup | The Databricks App starts and reads dashboard data from Lakebase | **Passed** after enabling the binary Psycopg implementation and granting the App service principal access to Lakebase |
| 2 | Dashboard data | Trip, 72-hour weather summary, activities, itinerary, and packing data are displayed | **Passed** |
| 3 | Generate itinerary | The application creates a weather-aware multi-day itinerary and persists it | **Passed** — 6 activities were organized across 11–13 August and stored in Lakebase |
| 4 | Add itinerary activity | A semantic-search result can be added and remains after refresh | **Passed** — Belém Riverside Walk was added and persisted |
| 5 | Remove itinerary activity | A removed activity remains absent after refresh | **Passed** — the itinerary count returned from 5 to 4 and the deleted activity did not reappear |
| 6 | Semantic activity search | A natural-language query retrieves relevant embedded content | **Passed** — `museum` returned Calouste Gulbenkian Museum |
| 7 | Semantic result to itinerary | A retrieved activity can be added to the operational itinerary | **Passed** — the museum was added and remained after refresh |
| 8 | Packing-item persistence | A checked item and progress remain after refresh | **Passed** — 1 of 5 items remained packed, showing 20% |
| 9 | Generate packing list | The application generates a contextual list without losing persisted state | **Passed** — 5 items remained visible and 2 packed items produced 40% progress |
| 10 | Lakebase read/write cycle | Create, update, delete, and reload operations persist across page refreshes | **Passed** |

## Issues found and resolved

### Psycopg startup failure

The first frontend deployment failed because the application forced the Psycopg `python` implementation without the runtime `libpq` dependency.

Resolution:

- installed `psycopg[binary]`;
- removed all `PSYCOPG_IMPL=python` configuration, including the remaining value in `frontend/app.yaml`.

### Lakebase OAuth role

After the application started, Lakebase rejected the App identity because its service principal did not yet have a PostgreSQL role.

Resolution:

- created the Lakebase role for the Databricks App service principal;
- granted database connection, schema usage, and the permissions required by the application.

### Static first version

The initial dashboard exposed read-only data. It did not provide actions that demonstrated persisted agent/application behavior.

Resolution:

- added interactive endpoints and controls for itinerary generation, semantic search, add/remove actions, packing-list generation, and packed-state updates;
- implemented transactional Lakebase writes and JSON success/error responses.

## Final validated state

- Databricks App deployed successfully;
- OAuth connection to Lakebase working;
- 72 weather hours available;
- 6 of 6 activity documents embedded;
- semantic search operating through `pgvector`;
- 6 itinerary activities generated and persisted;
- 5 packing-list items generated;
- 2 of 5 packing items persisted as packed (40%);
- create, update, delete, and refresh persistence verified.

## Conclusion

The project passed its principal functional tests and demonstrates the complete AI data application flow:

```text
External APIs -> Spark/Delta -> Lakebase + pgvector -> semantic retrieval
-> interactive AI actions -> persisted operational state
```

The remaining delivery work is evidence capture: screenshots of the deployed application, Databricks resources, pipeline outputs, Lakebase tables, embeddings/vector results, and repository documentation.
