-- User OCR corrections for training data collection
CREATE TABLE IF NOT EXISTS ocr_corrections (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    line_index SMALLINT NOT NULL,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    confidence NUMERIC,
    section TEXT,
    ocr_model TEXT,
    fm_applied BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending → approved → trained
    image_filename TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trained_version TEXT                            -- set when merged into training data
);

CREATE INDEX IF NOT EXISTS idx_ocr_corrections_status ON ocr_corrections(status);
CREATE INDEX IF NOT EXISTS idx_ocr_corrections_session ON ocr_corrections(session_id);
