PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    downloaded_at TEXT NOT NULL,
    UNIQUE (source_name, sha256)
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY,
    ingredient_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE (ingredient_name)
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    application_number TEXT NOT NULL,
    product_number TEXT NOT NULL DEFAULT '',
    proprietary_name TEXT,
    sponsor_name TEXT,
    dosage_form TEXT,
    route TEXT,
    marketing_status TEXT,
    is_discontinued INTEGER NOT NULL DEFAULT 0 CHECK (is_discontinued IN (0, 1)),
    source_file_id INTEGER REFERENCES source_files(id),
    raw_json TEXT,
    UNIQUE (application_number, product_number)
);

CREATE TABLE IF NOT EXISTS product_ingredients (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    strength TEXT,
    raw_json TEXT,
    PRIMARY KEY (product_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS patents (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    patent_number TEXT NOT NULL,
    patent_expiry TEXT,
    use_code TEXT,
    source_file_id INTEGER REFERENCES source_files(id),
    raw_json TEXT,
    UNIQUE (product_id, patent_number, use_code)
);

CREATE TABLE IF NOT EXISTS exclusivities (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    exclusivity_code TEXT NOT NULL,
    exclusivity_expiry TEXT,
    source_file_id INTEGER REFERENCES source_files(id),
    raw_json TEXT,
    UNIQUE (product_id, exclusivity_code, exclusivity_expiry)
);

CREATE TABLE IF NOT EXISTS phase1_candidates (
    ingredient_id INTEGER PRIMARY KEY REFERENCES ingredients(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    product_count INTEGER NOT NULL,
    sponsor_count INTEGER NOT NULL,
    route_diversity_count INTEGER NOT NULL,
    dosage_form_diversity_count INTEGER NOT NULL,
    latest_patent_expiry TEXT,
    latest_exclusivity_expiry TEXT,
    has_discontinued_product INTEGER NOT NULL CHECK (has_discontinued_product IN (0, 1)),
    has_iv_only_or_injectable_only INTEGER NOT NULL CHECK (has_iv_only_or_injectable_only IN (0, 1)),
    score_ip_openness INTEGER NOT NULL,
    score_route_gap INTEGER NOT NULL,
    score_discontinued_or_fragile INTEGER NOT NULL,
    score_reformulation_white_space INTEGER NOT NULL,
    score_total INTEGER NOT NULL,
    phase1_notes TEXT NOT NULL,
    scored_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_product_ingredients_ingredient
    ON product_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_ingredients_normalized_name
    ON ingredients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_patents_product ON patents(product_id);
CREATE INDEX IF NOT EXISTS idx_exclusivities_product ON exclusivities(product_id);
