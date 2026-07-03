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
    raw_active_ingredient TEXT,
    raw_strength TEXT,
    mapping_quality TEXT NOT NULL DEFAULT 'unknown',
    raw_json TEXT,
    PRIMARY KEY (product_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS product_observations (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id),
    source_name TEXT NOT NULL,
    active_in_latest_snapshot INTEGER NOT NULL DEFAULT 1
        CHECK (active_in_latest_snapshot IN (0, 1)),
    application_type TEXT,
    sponsor_name TEXT,
    dosage_form_raw TEXT,
    route_raw TEXT,
    canonical_dosage_form TEXT,
    canonical_route TEXT,
    parenteral_route_signal INTEGER NOT NULL DEFAULT 0
        CHECK (parenteral_route_signal IN (0, 1)),
    unknown_dosage_form INTEGER NOT NULL DEFAULT 0
        CHECK (unknown_dosage_form IN (0, 1)),
    unknown_route INTEGER NOT NULL DEFAULT 0 CHECK (unknown_route IN (0, 1)),
    marketing_status TEXT,
    marketing_status_class TEXT NOT NULL DEFAULT 'unknown',
    raw_active_ingredient TEXT,
    raw_strength TEXT,
    mapping_quality TEXT NOT NULL DEFAULT 'unknown',
    observed_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE(product_id, source_file_id)
);

CREATE TABLE IF NOT EXISTS patents (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    patent_number TEXT NOT NULL,
    patent_expiry TEXT,
    use_code TEXT,
    ip_active_in_latest_snapshot INTEGER NOT NULL DEFAULT 1
        CHECK (ip_active_in_latest_snapshot IN (0, 1)),
    ip_first_seen_at TEXT,
    ip_last_seen_at TEXT,
    delist_requested_signal INTEGER NOT NULL DEFAULT 0
        CHECK (delist_requested_signal IN (0, 1)),
    pediatric_extension_signal INTEGER NOT NULL DEFAULT 0
        CHECK (pediatric_extension_signal IN (0, 1)),
    source_file_id INTEGER REFERENCES source_files(id),
    raw_json TEXT,
    UNIQUE (product_id, patent_number, use_code)
);

CREATE TABLE IF NOT EXISTS exclusivities (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    exclusivity_code TEXT NOT NULL,
    exclusivity_expiry TEXT,
    ip_active_in_latest_snapshot INTEGER NOT NULL DEFAULT 1
        CHECK (ip_active_in_latest_snapshot IN (0, 1)),
    ip_first_seen_at TEXT,
    ip_last_seen_at TEXT,
    pediatric_extension_signal INTEGER NOT NULL DEFAULT 0
        CHECK (pediatric_extension_signal IN (0, 1)),
    source_file_id INTEGER REFERENCES source_files(id),
    raw_json TEXT,
    UNIQUE (product_id, exclusivity_code, exclusivity_expiry)
);

CREATE TABLE IF NOT EXISTS phase1_candidates (
    ingredient_id INTEGER PRIMARY KEY REFERENCES ingredients(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    product_count INTEGER NOT NULL,
    active_product_count INTEGER NOT NULL,
    discontinued_product_count INTEGER NOT NULL,
    tentative_or_nonmarketed_count INTEGER NOT NULL,
    unknown_marketing_status_count INTEGER NOT NULL,
    all_products_discontinued INTEGER NOT NULL,
    mixed_active_discontinued INTEGER NOT NULL,
    sponsor_count INTEGER NOT NULL,
    sponsor_list TEXT NOT NULL,
    application_no_list TEXT NOT NULL,
    application_type_list TEXT NOT NULL,
    route_list_raw TEXT NOT NULL,
    canonical_route_list TEXT NOT NULL,
    dosage_form_list_raw TEXT NOT NULL,
    canonical_dosage_form_list TEXT NOT NULL,
    unknown_route_count INTEGER NOT NULL,
    unknown_dosage_form_count INTEGER NOT NULL,
    parenteral_route_signal INTEGER NOT NULL,
    route_diversity_count INTEGER NOT NULL,
    dosage_form_diversity_count INTEGER NOT NULL,
    latest_patent_expiry TEXT,
    latest_exclusivity_expiry TEXT,
    patent_count INTEGER NOT NULL,
    exclusivity_count INTEGER NOT NULL,
    delist_requested_signal INTEGER NOT NULL,
    pediatric_extension_signal INTEGER NOT NULL,
    source_conflict_flags TEXT NOT NULL,
    mapping_quality_flags TEXT NOT NULL,
    has_discontinued_product INTEGER NOT NULL CHECK (has_discontinued_product IN (0, 1)),
    has_iv_only_or_injectable_only INTEGER NOT NULL CHECK (has_iv_only_or_injectable_only IN (0, 1)),
    score_ip_openness INTEGER NOT NULL,
    score_route_gap INTEGER NOT NULL,
    score_discontinued_or_fragile INTEGER NOT NULL,
    score_reformulation_white_space INTEGER NOT NULL,
    score_confidence TEXT NOT NULL,
    data_completeness_score INTEGER NOT NULL,
    score_total INTEGER NOT NULL,
    phase1_notes TEXT NOT NULL,
    evidence_completeness_notes TEXT NOT NULL,
    triage_class TEXT NOT NULL,
    triage_subclass TEXT NOT NULL,
    exclude_from_top_science_review INTEGER NOT NULL
        CHECK (exclude_from_top_science_review IN (0, 1)),
    exclusion_reason TEXT NOT NULL,
    science_review_priority TEXT NOT NULL,
    scored_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dailymed_label_evidence (
    ingredient_id INTEGER PRIMARY KEY REFERENCES ingredients(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    retrieval_status TEXT NOT NULL,
    label_match_quality TEXT NOT NULL,
    label_source_setid_or_id TEXT,
    label_title TEXT,
    label_last_updated_if_available TEXT,
    metadata_path TEXT,
    label_path TEXT,
    has_boxed_warning INTEGER NOT NULL DEFAULT 0,
    has_serious_warning_signal INTEGER NOT NULL DEFAULT 0,
    has_infusion_or_injection_reaction_signal INTEGER NOT NULL DEFAULT 0,
    has_hypersensitivity_signal INTEGER NOT NULL DEFAULT 0,
    has_reconstitution_signal INTEGER NOT NULL DEFAULT 0,
    has_special_preparation_signal INTEGER NOT NULL DEFAULT 0,
    has_storage_burden_signal INTEGER NOT NULL DEFAULT 0,
    has_light_protection_signal INTEGER NOT NULL DEFAULT 0,
    has_refrigeration_signal INTEGER NOT NULL DEFAULT 0,
    has_short_post_reconstitution_stability_signal INTEGER NOT NULL DEFAULT 0,
    has_pediatric_gap_signal INTEGER NOT NULL DEFAULT 0,
    has_renal_hepatic_adjustment_signal INTEGER NOT NULL DEFAULT 0,
    administration_burden_terms TEXT NOT NULL DEFAULT '',
    safety_burden_terms TEXT NOT NULL DEFAULT '',
    formulation_burden_terms TEXT NOT NULL DEFAULT '',
    score_administration_burden INTEGER NOT NULL DEFAULT 0,
    score_safety_burden INTEGER NOT NULL DEFAULT 0,
    score_formulation_handling_burden INTEGER NOT NULL DEFAULT 0,
    score_pediatric_gap INTEGER NOT NULL DEFAULT 0,
    score_route_conversion_opportunity INTEGER NOT NULL DEFAULT 0,
    score_label_evidence_confidence INTEGER NOT NULL DEFAULT 0,
    scientific_rescue_signal_score INTEGER NOT NULL DEFAULT 0,
    scientific_review_rationale TEXT NOT NULL DEFAULT '',
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_product_ingredients_ingredient
    ON product_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_ingredients_normalized_name
    ON ingredients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_patents_product ON patents(product_id);
CREATE INDEX IF NOT EXISTS idx_exclusivities_product ON exclusivities(product_id);
CREATE INDEX IF NOT EXISTS idx_product_observations_latest
    ON product_observations(source_name, active_in_latest_snapshot, product_id);
