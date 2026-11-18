-- PostgreSQL schema (the SQLite fallback is derived from this file at runtime).

CREATE TABLE IF NOT EXISTS phones (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,            -- e.g. "Samsung Galaxy S23 Ultra"
    brand       TEXT NOT NULL DEFAULT 'Samsung',
    url         TEXT,
    image_url   TEXT,
    announced   TEXT,
    scraped_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full raw specification sheet, one row per (category, key) exactly as on GSMArena.
CREATE TABLE IF NOT EXISTS specifications (
    id          SERIAL PRIMARY KEY,
    phone_id    INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,                   -- Display, Platform, Main Camera, Battery ...
    spec_key    TEXT NOT NULL,                   -- Size, Chipset, Type ...
    spec_value  TEXT NOT NULL,
    UNIQUE (phone_id, category, spec_key)
);

-- Normalised numeric facts parsed from the raw specs; used for ranking/comparison.
CREATE TABLE IF NOT EXISTS key_specs (
    phone_id         INTEGER PRIMARY KEY REFERENCES phones(id) ON DELETE CASCADE,
    display_size_in  REAL,
    display_type     TEXT,
    resolution       TEXT,
    refresh_rate_hz  INTEGER,
    chipset          TEXT,
    os               TEXT,
    ram_gb_max       INTEGER,
    storage_gb_max   INTEGER,
    main_camera_mp   REAL,
    camera_summary   TEXT,
    battery_mah      INTEGER,
    charging_w       INTEGER,
    weight_g         REAL
);

CREATE TABLE IF NOT EXISTS prices (
    id          SERIAL PRIMARY KEY,
    phone_id    INTEGER NOT NULL REFERENCES phones(id) ON DELETE CASCADE,
    currency    TEXT NOT NULL,                   -- USD, EUR, GBP, INR
    amount      REAL NOT NULL,
    note        TEXT NOT NULL DEFAULT '',        -- e.g. "GSMArena Misc/Price"
    UNIQUE (phone_id, currency, note)
);

CREATE INDEX IF NOT EXISTS idx_specs_phone ON specifications(phone_id);
CREATE INDEX IF NOT EXISTS idx_prices_phone ON prices(phone_id);
