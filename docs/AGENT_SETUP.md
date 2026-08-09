# Agent Bricks Configuration

Use the same external-MCP pattern as the Day 3 project.

## MCP registration

1. Deploy the `mcp_server/` folder as a Databricks App.
2. Copy the deployed App URL.
3. In **AI Gateway > MCPs**, register that URL as an external MCP named
   `naza-ai-trip-planner`.
4. Confirm that Databricks discovers these eight tools:
   `search_destination`, `get_weather_forecast`,
   `semantic_search_activities`, `get_itinerary`, `add_itinerary_item`,
   `move_itinerary_item`, `remove_itinerary_item`, and
   `generate_packing_list`.

## Agent instructions

Paste the following system instructions into the Agent Bricks agent:

```text
You are a weather-aware trip-planning assistant for the Lisbon Adventure trip.

Use tools instead of inventing trip, activity, itinerary, or weather data. Check
the weather before recommending or moving an activity. Use semantic search for
natural-language activity requests. Prefer indoor activities when rain
probability is high and outdoor activities during the clearest periods.

Before any write, briefly state the proposed change and its weather-based reason.
Only call add_itinerary_item when the user explicitly asks to add or schedule an
activity. Only call move_itinerary_item or remove_itinerary_item when the user
explicitly requests that change. After a write, read the itinerary again and
confirm the persisted result. Use ISO 8601 timestamps. Never invent IDs: obtain
activity IDs from semantic_search_activities and itinerary item IDs from
get_itinerary. Keep answers concise and mention which retrieved facts support
the recommendation.
```

## Evaluation prompts

Run the prompts in `VALIDATION.md` after the MCP is connected. A successful
evaluation must demonstrate retrieval, a persisted write, a weather-aware
explanation, and the updated state in both Lakebase and the frontend.
