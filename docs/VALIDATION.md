# Validation and Evidence Checklist

## 1. Lakebase schema

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users','trips','activities','weather_snapshots','itinerary_items','packing_items','activity_documents')
ORDER BY table_name;
```

Capture the seven tables, then capture PK/FK constraints.

```sql
SELECT tc.table_name, tc.constraint_type, kcu.column_name,
       ccu.table_name AS referenced_table
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
ORDER BY tc.table_name, tc.constraint_type, kcu.column_name;
```

## 2. Spark pipeline

- Capture the Bronze table write.
- Capture the Silver `groupBy` result.
- Capture the Wikimedia text-length result.
- Capture the final successful pipeline message.

```sql
SELECT COUNT(*) AS weather_rows FROM weather_snapshots;
SELECT COUNT(*) AS embedded_documents FROM activity_documents WHERE embedding IS NOT NULL;
```

## 3. Frontend

- Overview showing the trip and activities.
- Weather cards populated from Lakebase.
- Itinerary and packing list after agent writes.

## 4. Agent read tests

Use these prompts in Agent Bricks:

```text
Find two indoor activities in Lisbon suitable for a rainy afternoon. Explain why they match.
```

```text
Show the current weather forecast and itinerary for trip 1.
```

## 5. Agent write and persistence tests

```text
Add Jerónimos Monastery to trip 1 on the trip's first date at 14:00, for 120 minutes. Explain that it is an indoor alternative if rain is likely.
```

Refresh the frontend and capture the new item. Then:

```text
Move that itinerary item to 16:00 on the same date because the earlier period is better for outdoor activities.
```

```text
Generate and save a packing list for trip 1 using the stored forecast.
```

Capture the agent response, refreshed frontend, and these SQL results:

```sql
SELECT * FROM itinerary_items ORDER BY created_at DESC;
SELECT * FROM packing_items ORDER BY item_name;
```

## 6. Final submission gate

- Databricks frontend App URL
- MCP App URL
- GitHub repository URL
- Spark notebook and successful-run evidence
- Lakebase data and constraint evidence
- Semantic retrieval evidence
- Agent read/write evidence
- Persistence-after-refresh evidence
- README and project reflection
- No secrets in repository or screenshots
