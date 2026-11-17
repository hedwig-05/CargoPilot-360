-- CargoPilot 360: structured exception source evidence.
-- Development target only. Apply to cargopilot_test first, after backup.
-- Legacy rows intentionally remain sources=NULL; they retain their existing
-- descriptions and continue using the legacy verification parser.

USE cargopilot_test;

ALTER TABLE exceptions
    ADD COLUMN sources JSON NULL,
    ADD COLUMN eligible_for_verification BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN severity_recalculation_pending BOOLEAN NOT NULL DEFAULT FALSE;

SHOW COLUMNS FROM exceptions LIKE 'sources';
SHOW COLUMNS FROM exceptions LIKE 'eligible_for_verification';
SHOW COLUMNS FROM exceptions LIKE 'severity_recalculation_pending';
