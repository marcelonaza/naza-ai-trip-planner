CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    destination_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    interests TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id BIGSERIAL PRIMARY KEY,
    destination_name TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    indoor BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NOT NULL,
    source_url TEXT,
    min_temperature_c NUMERIC(5,2),
    max_precipitation_probability INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (destination_name, name),
    CHECK (max_precipitation_probability BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    weather_snapshot_id BIGSERIAL PRIMARY KEY,
    trip_id BIGINT NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    forecast_time TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(5,2),
    precipitation_probability INTEGER,
    weather_code INTEGER,
    source TEXT NOT NULL DEFAULT 'Open-Meteo',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trip_id, forecast_time)
);

CREATE TABLE IF NOT EXISTS itinerary_items (
    itinerary_item_id BIGSERIAL PRIMARY KEY,
    trip_id BIGINT NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(activity_id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 120,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (duration_minutes > 0),
    CHECK (status IN ('planned', 'completed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS packing_items (
    packing_item_id BIGSERIAL PRIMARY KEY,
    trip_id BIGINT NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    packed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trip_id, item_name)
);

CREATE TABLE IF NOT EXISTS activity_documents (
    document_id BIGSERIAL PRIMARY KEY,
    activity_id BIGINT NOT NULL UNIQUE REFERENCES activities(activity_id) ON DELETE CASCADE,
    document_text TEXT NOT NULL,
    embedding VECTOR(384),
    embedding_model TEXT NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_trip_time ON weather_snapshots(trip_id, forecast_time);
CREATE INDEX IF NOT EXISTS idx_itinerary_trip_time ON itinerary_items(trip_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_activity_documents_embedding
    ON activity_documents USING hnsw (embedding vector_cosine_ops);

INSERT INTO users (email, display_name)
VALUES ('demo.user@example.com', 'Demo User')
ON CONFLICT (email) DO NOTHING;

INSERT INTO trips (user_id, name, destination_name, latitude, longitude, start_date, end_date, interests)
SELECT user_id, 'Lisbon Adventure', 'Lisbon', 38.7223, -9.1393,
       CURRENT_DATE + 1, CURRENT_DATE + 3,
       ARRAY['history', 'food', 'outdoors']
FROM users WHERE email = 'demo.user@example.com'
  AND NOT EXISTS (SELECT 1 FROM trips WHERE name = 'Lisbon Adventure');

INSERT INTO activities
    (destination_name, name, category, indoor, description, source_url, min_temperature_c, max_precipitation_probability)
VALUES
    ('Lisbon', 'Belém Riverside Walk', 'outdoors', FALSE,
     'A scenic walk beside the Tagus passing Belém Tower and the Monument to the Discoveries.',
     'https://en.wikipedia.org/wiki/Bel%C3%A9m,_Lisbon', 12, 25),
    ('Lisbon', 'Jerónimos Monastery', 'history', TRUE,
     'Explore Manueline architecture and Portuguese maritime history inside the historic monastery.',
     'https://en.wikipedia.org/wiki/Jer%C3%B3nimos_Monastery', NULL, 100),
    ('Lisbon', 'Calouste Gulbenkian Museum', 'culture', TRUE,
     'An indoor art collection covering ancient objects and modern European works.',
     'https://en.wikipedia.org/wiki/Calouste_Gulbenkian_Museum', NULL, 100),
    ('Lisbon', 'Alfama Walking Tour', 'history', FALSE,
     'Walk through Lisbon''s oldest neighborhood, viewpoints, narrow streets, and traditional architecture.',
     'https://en.wikipedia.org/wiki/Alfama', 10, 20),
    ('Lisbon', 'Time Out Market Food Tour', 'food', TRUE,
     'Sample Portuguese dishes from multiple local vendors in a covered food hall.',
     'https://en.wikipedia.org/wiki/Time_Out_Market_Lisboa', NULL, 100),
    ('Lisbon', 'Oceanário de Lisboa', 'family', TRUE,
     'Visit a large public aquarium featuring marine ecosystems and a central ocean tank.',
     'https://en.wikipedia.org/wiki/Lisbon_Oceanarium', NULL, 100)
ON CONFLICT (destination_name, name) DO NOTHING;
