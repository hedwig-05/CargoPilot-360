-- CargoPilot 360: eight-factor risk model and exception SLA foundation
-- Target database: cargopilot_test ONLY during development.
-- BACK UP THE DATABASE before running this migration.
-- Run once. Review the selected database before executing.

USE cargopilot_test;

-- 1. Extend exception categories while preserving existing categories.
ALTER TABLE exceptions
MODIFY COLUMN exception_type ENUM(
    'DOCUMENT_MISMATCH',
    'MISSING_DOCUMENT',
    'SHIPMENT_DELAY',
    'MISSING_MILESTONE',
    'CUSTOMS_HOLD',
    'STAKEHOLDER_RESPONSE_DELAY',
    'CONTAINER_NOT_DISCHARGED',
    'DAMAGE_SHORTAGE',
    'ROLLED_CARGO'
) NOT NULL;

-- 2. Preserve existing lifecycle statuses and add the explicit third-party pause.
ALTER TABLE exceptions
MODIFY COLUMN status ENUM(
    'OPEN',
    'INVESTIGATING',
    'AWAITING_APPROVAL',
    'IN_PROGRESS',
    'AWAITING_RESPONSE',
    'PENDING_3RD_PARTY',
    'RESOLVED',
    'CLOSED'
) NOT NULL DEFAULT 'OPEN';

-- detected_at is the existing TTA/TTR start timestamp.
ALTER TABLE exceptions
ADD COLUMN acknowledged_at DATETIME NULL,
ADD COLUMN total_paused_minutes INT NOT NULL DEFAULT 0;

-- Backfill acknowledgement timestamps for records already being actively handled.
-- This is a conservative migration: historical acknowledgement times are unknown,
-- so leave them NULL rather than inventing timestamps.

-- 3. Extend risk factor enums in both rules and historical factor snapshots.
ALTER TABLE risk_factor_rules
MODIFY COLUMN factor_code ENUM(
    'DOCUMENT_MISMATCH',
    'MISSING_DOCUMENT',
    'ARRIVAL_DELAY',
    'MISSING_MILESTONE',
    'CUSTOMS_ISSUE',
    'STAKEHOLDER_DELAY',
    'DAMAGE_SHORTAGE',
    'ROLLED_CARGO'
) NOT NULL;

ALTER TABLE risk_assessment_factors
MODIFY COLUMN factor_code ENUM(
    'DOCUMENT_MISMATCH',
    'MISSING_DOCUMENT',
    'ARRIVAL_DELAY',
    'MISSING_MILESTONE',
    'CUSTOMS_ISSUE',
    'STAKEHOLDER_DELAY',
    'DAMAGE_SHORTAGE',
    'ROLLED_CARGO'
) NOT NULL;

-- 4. Append-only transition ledger. Integer IDs preserve CargoPilot's existing FK design.
CREATE TABLE IF NOT EXISTS exception_status_history (
    log_id INT NOT NULL AUTO_INCREMENT,
    exception_id INT NOT NULL,
    old_status ENUM(
        'OPEN',
        'INVESTIGATING',
        'AWAITING_APPROVAL',
        'IN_PROGRESS',
        'AWAITING_RESPONSE',
        'PENDING_3RD_PARTY',
        'RESOLVED',
        'CLOSED'
    ) NULL,
    new_status ENUM(
        'OPEN',
        'INVESTIGATING',
        'AWAITING_APPROVAL',
        'IN_PROGRESS',
        'AWAITING_RESPONSE',
        'PENDING_3RD_PARTY',
        'RESOLVED',
        'CLOSED'
    ) NOT NULL,
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operator_id INT NULL,
    PRIMARY KEY (log_id),
    KEY ix_exception_status_history_exception_time (exception_id, changed_at),
    CONSTRAINT fk_exception_status_history_exception
        FOREIGN KEY (exception_id) REFERENCES exceptions(exception_id),
    CONSTRAINT fk_exception_status_history_operator
        FOREIGN KEY (operator_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- 5. Verify the migrated schema before starting the application.
SHOW COLUMNS FROM exceptions LIKE 'acknowledged_at';
SHOW COLUMNS FROM exceptions LIKE 'total_paused_minutes';
SHOW CREATE TABLE exception_status_history;
SHOW COLUMNS FROM risk_factor_rules LIKE 'factor_code';
SHOW COLUMNS FROM risk_assessment_factors LIKE 'factor_code';
