-- CargoPilot 360: explicit Supervisor-to-exception workflow tracking
-- Target database: cargopilot_test ONLY during development.
-- Safe to re-run: the table is created only when it does not already exist.
--
-- parent_workflow_id remains reserved for workflow dependencies.
-- This table records the separate coordination relationship.

USE cargopilot_test;

CREATE TABLE IF NOT EXISTS supervisor_workflow_links (
    link_id INT NOT NULL AUTO_INCREMENT,
    supervisor_workflow_id INT NOT NULL,
    exception_workflow_id INT NOT NULL,
    exception_id INT NOT NULL,
    action_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (link_id),
    CONSTRAINT uq_supervisor_exception_workflow
        UNIQUE (supervisor_workflow_id, exception_workflow_id),
    KEY ix_supervisor_workflow_links_action (action_id),
    CONSTRAINT fk_swl_supervisor_workflow
        FOREIGN KEY (supervisor_workflow_id)
        REFERENCES agent_workflows(workflow_id),
    CONSTRAINT fk_swl_exception_workflow
        FOREIGN KEY (exception_workflow_id)
        REFERENCES agent_workflows(workflow_id),
    CONSTRAINT fk_swl_exception
        FOREIGN KEY (exception_id)
        REFERENCES exceptions(exception_id),
    CONSTRAINT fk_swl_action
        FOREIGN KEY (action_id)
        REFERENCES actions(action_id)
);


-- Backfill associations from existing Supervisor-linked actions.
-- The unique key makes this safe to re-run.
INSERT INTO supervisor_workflow_links (
    supervisor_workflow_id,
    exception_workflow_id,
    exception_id,
    action_id
)
SELECT
    CAST(JSON_UNQUOTE(JSON_EXTRACT(action_payload, '$.supervisor_workflow_id')) AS UNSIGNED),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(action_payload, '$.exception_workflow_id')) AS UNSIGNED),
    CAST(JSON_UNQUOTE(JSON_EXTRACT(action_payload, '$.exception_id')) AS UNSIGNED),
    action_id
FROM actions
WHERE action_payload IS NOT NULL
  AND JSON_VALID(action_payload)
  AND JSON_EXTRACT(action_payload, '$.supervisor_workflow_id') IS NOT NULL
  AND JSON_EXTRACT(action_payload, '$.exception_workflow_id') IS NOT NULL
  AND JSON_EXTRACT(action_payload, '$.exception_id') IS NOT NULL
ON DUPLICATE KEY UPDATE
    action_id = VALUES(action_id);
