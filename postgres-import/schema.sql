-- schema.sql
-- ============================================================
-- BDO Dictionary Entries Schema
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Für Fuzzy Search

-- Main Table
CREATE TABLE IF NOT EXISTS entries (
    -- Primary Key & Classification
    id TEXT PRIMARY KEY,
    wb TEXT NOT NULL,
    
    -- Core Fields (denormalized for fast queries)
    lemma TEXT NOT NULL,
    lemma_variants TEXT[],
    definitions TEXT[],
    regions TEXT[],
    
    -- Full TEI Lex-0 as JSONB
    data JSONB NOT NULL,
    
    -- Original TEI XML
    tei_xml TEXT,
    
    -- Full-Text Search
    search_text TEXT,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('german', coalesce(search_text, ''))
    ) STORED,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_wb ON entries(wb);
CREATE INDEX IF NOT EXISTS idx_lemma ON entries(lemma);
CREATE INDEX IF NOT EXISTS idx_lemma_trgm ON entries USING gin(lemma gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_variants ON entries USING gin(lemma_variants);
CREATE INDEX IF NOT EXISTS idx_definitions ON entries USING gin(definitions);
CREATE INDEX IF NOT EXISTS idx_regions ON entries USING gin(regions);
CREATE INDEX IF NOT EXISTS idx_data_gin ON entries USING gin(data);
CREATE INDEX IF NOT EXISTS idx_search ON entries USING gin(search_vector);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON entries;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Optional: Dictionary Metadata Table
CREATE TABLE IF NOT EXISTS dictionaries (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    full_name TEXT,
    language_code TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO dictionaries (code, name, full_name, language_code) VALUES
    ('bwb', 'BWB', 'Bayerisches Wörterbuch', 'bar'),
    ('dibs', 'DIBS', 'Dialektologisches Informationssystem Bayrisch-Schwaben', 'swa'),
    ('wbf', 'WBF', 'Fränkisches Wörterbuch', 'vmf')
ON CONFLICT (code) DO NOTHING;

-- Foreign Key (optional, für Integrität)
ALTER TABLE entries 
    DROP CONSTRAINT IF EXISTS fk_wb_dictionary;
ALTER TABLE entries 
    ADD CONSTRAINT fk_wb_dictionary 
    FOREIGN KEY (wb) REFERENCES dictionaries(code);