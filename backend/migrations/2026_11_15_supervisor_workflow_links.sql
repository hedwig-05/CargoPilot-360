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
