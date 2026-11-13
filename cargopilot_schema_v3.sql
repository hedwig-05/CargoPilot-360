
-- =====================================================================
-- CargoPilot 360 - Database Schema v3 (Corrected)
-- MySQL / InnoDB
--
-- LangGraph's own checkpoint tables are created by the library.
--
-- !! DESTRUCTIVE: uncomment ONLY for a clean rebuild. It deletes ALL data. !!
-- DROP DATABASE IF EXISTS cargopilot;

CREATE DATABASE IF NOT EXISTS cargopilot
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE cargopilot;

-- ---------------------------------------------------------------------
-- 1. users
-- ---------------------------------------------------------------------

CREATE TABLE users (
  user_id        INT AUTO_INCREMENT PRIMARY KEY,
  name           VARCHAR(100) NOT NULL,
  email          VARCHAR(150) NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  role           ENUM('MANAGER','OFFICER') NOT NULL DEFAULT 'OFFICER',
  is_active      TINYINT(1) NOT NULL DEFAULT 1,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 2. shipments
-- ---------------------------------------------------------------------

CREATE TABLE shipments (
  shipment_id        INT AUTO_INCREMENT PRIMARY KEY,
  shipment_ref       VARCHAR(50) NOT NULL,
  origin             VARCHAR(100) NOT NULL,
  destination        VARCHAR(100) NOT NULL,
  shipper            VARCHAR(150) NOT NULL,
  consignee          VARCHAR(150) NOT NULL,
  container_no       VARCHAR(50) NULL,
  container_type     ENUM('20FT','40FT','40HC','OTHER') NOT NULL DEFAULT '40FT',
  expected_arrival   DATETIME NOT NULL,
  actual_arrival     DATETIME NULL,
  status             ENUM('BOOKED','DOCUMENTATION','IN_TRANSIT','ARRIVED',
                          'CUSTOMS','DELIVERED','ON_HOLD','CANCELLED')
                     NOT NULL DEFAULT 'BOOKED',
  current_risk_score DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  current_risk_level ENUM('LOW','MEDIUM','HIGH') NOT NULL DEFAULT 'LOW',
  assigned_user_id   INT NULL,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_shipments_ref (shipment_ref),
  KEY idx_shipments_status (status),
  KEY idx_shipments_expected_arrival (expected_arrival),
  KEY idx_shipments_risk (current_risk_level),
  KEY idx_shipments_assigned (assigned_user_id),

  CONSTRAINT fk_shipments_user
    FOREIGN KEY (assigned_user_id)
    REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_shipments_risk
    CHECK (current_risk_score BETWEEN 0 AND 100)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 3. shipment_events
-- ---------------------------------------------------------------------

CREATE TABLE shipment_events (
  event_id           INT AUTO_INCREMENT PRIMARY KEY,
  shipment_id        INT NOT NULL,
  event_type         ENUM('VESSEL_DEPARTED','VESSEL_ARRIVED','CONTAINER_DISCHARGED',
                          'CUSTOMS_CLEARED','DOCUMENTATION_COMPLETE','DELIVERED') NOT NULL,
  event_description  TEXT NULL,
  expected_time      DATETIME NOT NULL,
  actual_time        DATETIME NULL,
  event_status       ENUM('PENDING','COMPLETED','LATE','MISSING','INCONSISTENT')
                     NOT NULL DEFAULT 'PENDING',
  source             VARCHAR(50) NOT NULL DEFAULT 'SIMULATOR',
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_event_dedupe (shipment_id, event_type, source, expected_time),
  UNIQUE KEY uq_events_id_shipment (event_id, shipment_id),

  KEY idx_events_shipment (shipment_id),
  KEY idx_events_status (event_status),
  KEY idx_events_expected (expected_time),

  CONSTRAINT fk_events_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 4. documents
-- extraction_run_id FK added after agent_runs exists
-- ---------------------------------------------------------------------

CREATE TABLE documents (
  document_id        INT AUTO_INCREMENT PRIMARY KEY,
  shipment_id        INT NOT NULL,
  document_type      ENUM('COMMERCIAL_INVOICE','PACKING_LIST','BILL_OF_LADING','OTHER') NOT NULL,
  file_name          VARCHAR(255) NOT NULL,
  file_path          VARCHAR(500) NOT NULL,
  file_hash          CHAR(64) NULL,
  extracted_text     LONGTEXT NULL,
  extracted_fields   JSON NULL,
  extraction_status  ENUM('PENDING','EXTRACTED','FAILED','NEEDS_REVIEW')
                     NOT NULL DEFAULT 'PENDING',
  extraction_run_id  INT NULL,
  validation_status  ENUM('NOT_VALIDATED','VALID','MISMATCH','INCOMPLETE')
                     NOT NULL DEFAULT 'NOT_VALIDATED',
  version_no         INT NOT NULL DEFAULT 1,
  uploaded_by        INT NULL,
  upload_date        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_documents_id_shipment (document_id, shipment_id),

  KEY idx_documents_shipment (shipment_id),
  KEY idx_documents_type (shipment_id, document_type),

  CONSTRAINT fk_documents_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_documents_user
    FOREIGN KEY (uploaded_by)
    REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_documents_version
    CHECK (version_no >= 1)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 5. document_validations
-- Both documents must belong to the same shipment.
-- ---------------------------------------------------------------------

CREATE TABLE document_validations (
  validation_id        INT AUTO_INCREMENT PRIMARY KEY,
  document_id          INT NOT NULL,
  compared_document_id INT NULL,
  shipment_id          INT NOT NULL,
  validation_run_id    INT NULL,
  field_name           VARCHAR(100) NOT NULL,
  extracted_value      VARCHAR(255) NULL,
  expected_value       VARCHAR(255) NULL,
  validation_result    ENUM('MATCH','MISMATCH','MISSING','UNCERTAIN') NOT NULL,
  explanation          TEXT NULL,
  validated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_val_id_shipment (validation_id, shipment_id),

  KEY idx_val_document (document_id, shipment_id),
  KEY idx_val_compared (compared_document_id, shipment_id),
  KEY idx_val_shipment (shipment_id),
  KEY idx_val_result (validation_result),

  CONSTRAINT fk_val_document
    FOREIGN KEY (document_id, shipment_id)
    REFERENCES documents(document_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_val_compared
    FOREIGN KEY (compared_document_id, shipment_id)
    REFERENCES documents(document_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_val_distinct_docs
    CHECK (compared_document_id IS NULL OR compared_document_id <> document_id)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 6. exceptions
-- ---------------------------------------------------------------------

CREATE TABLE exceptions (
  exception_id        INT AUTO_INCREMENT PRIMARY KEY,
  shipment_id         INT NOT NULL,
  exception_type      ENUM('DOCUMENT_MISMATCH','MISSING_DOCUMENT','SHIPMENT_DELAY',
                           'MISSING_MILESTONE','CUSTOMS_HOLD','STAKEHOLDER_RESPONSE_DELAY',
                           'CONTAINER_NOT_DISCHARGED') NOT NULL,
  description         TEXT NOT NULL,
  severity            ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
  status              ENUM('OPEN','INVESTIGATING','AWAITING_APPROVAL','IN_PROGRESS',
                           'AWAITING_RESPONSE','RESOLVED','CLOSED') NOT NULL DEFAULT 'OPEN',
  event_id            INT NULL,
  document_id         INT NULL,
  assigned_to         INT NULL,
  detected_by         VARCHAR(50) NOT NULL DEFAULT 'MONITORING_AGENT',
  detected_by_run_id  INT NULL,
  detected_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at         DATETIME NULL,
  resolution_notes    TEXT NULL,

  open_key VARCHAR(120) GENERATED ALWAYS AS (
    CASE
      WHEN status IN ('RESOLVED','CLOSED') THEN NULL
      ELSE CONCAT(shipment_id, ':', exception_type)
    END
  ) STORED,

  UNIQUE KEY uq_exceptions_open (open_key),
  UNIQUE KEY uq_exceptions_id_shipment (exception_id, shipment_id),

  KEY idx_exceptions_shipment (shipment_id),
  KEY idx_exceptions_status (status),
  KEY idx_exceptions_type (exception_type),
  KEY idx_exceptions_detected (detected_at),
  KEY idx_exceptions_event (event_id, shipment_id),
  KEY idx_exceptions_document (document_id, shipment_id),

  CONSTRAINT fk_exc_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_exc_event
    FOREIGN KEY (event_id, shipment_id)
    REFERENCES shipment_events(event_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_exc_document
    FOREIGN KEY (document_id, shipment_id)
    REFERENCES documents(document_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_exc_user
    FOREIGN KEY (assigned_to)
    REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_exceptions_resolved CHECK (
       (status IN ('RESOLVED','CLOSED') AND resolved_at IS NOT NULL)
    OR (status NOT IN ('RESOLVED','CLOSED') AND resolved_at IS NULL)
  )
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 7. agent_workflows
-- ONE row per LangGraph graph invocation.
-- A LangGraph thread can span multiple invocations.
-- ---------------------------------------------------------------------

CREATE TABLE agent_workflows (
  workflow_id         INT AUTO_INCREMENT PRIMARY KEY,
  workflow_public_id  VARCHAR(40) NOT NULL,
  thread_id           VARCHAR(80) NOT NULL,
  shipment_id         INT NOT NULL,
  exception_id        INT NULL,
  trigger_type        ENUM('SIMULATOR_EVENT','DOCUMENT_UPLOAD','MONITORING_CYCLE',
                           'MANUAL','SCHEDULED') NOT NULL,
  trigger_ref         VARCHAR(100) NULL,
  graph_name          VARCHAR(60) NOT NULL DEFAULT 'cargopilot_main',
  graph_version       VARCHAR(20) NULL,
  status              ENUM('RUNNING','WAITING_FOR_APPROVAL','COMPLETED','FAILED','CANCELLED')
                      NOT NULL DEFAULT 'RUNNING',
  current_node        VARCHAR(60) NULL,
  last_checkpoint_id  VARCHAR(100) NULL,
  error_message       TEXT NULL,
  triggered_by        INT NULL,
  started_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at        DATETIME NULL,

  UNIQUE KEY uq_wf_public (workflow_public_id),
  UNIQUE KEY uq_wf_id_exception (workflow_id, exception_id),
  UNIQUE KEY uq_wf_id_shipment (workflow_id, shipment_id),

  KEY idx_wf_thread (thread_id),
  KEY idx_wf_shipment (shipment_id),
  KEY idx_wf_exception (exception_id),
  KEY idx_wf_status (status),

  CONSTRAINT fk_wf_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_wf_exception
    FOREIGN KEY (exception_id)
    REFERENCES exceptions(exception_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT fk_wf_user
    FOREIGN KEY (triggered_by)
    REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 8. agent_runs
-- ONE row per agent/node step inside a workflow.
-- ---------------------------------------------------------------------

CREATE TABLE agent_runs (
  run_id            INT AUTO_INCREMENT PRIMARY KEY,
  run_public_id     VARCHAR(40) NOT NULL,
  workflow_id       INT NOT NULL,
  parent_run_id     INT NULL,
  step_no           INT NOT NULL DEFAULT 1,
  agent_type        ENUM('SUPERVISOR','MONITORING','DOCUMENT','INVESTIGATION',
                         'DECISION','ACTION') NOT NULL,
  node_name         VARCHAR(60) NULL,
  input_data        JSON NULL,
  output_data       JSON NULL,
  model_name        VARCHAR(60) NULL,
  prompt_version    VARCHAR(30) NULL,
  prompt_tokens     INT NULL,
  completion_tokens INT NULL,
  latency_ms        INT NULL,
  retry_count       INT NOT NULL DEFAULT 0,
  execution_status  ENUM('PROCESSING','WAITING_FOR_APPROVAL','COMPLETED','FAILED','SKIPPED')
                    NOT NULL DEFAULT 'PROCESSING',
  error_message     TEXT NULL,
  started_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at      DATETIME NULL,

  UNIQUE KEY uq_runs_public (run_public_id),
  UNIQUE KEY uq_runs_step (workflow_id, step_no),
  UNIQUE KEY uq_runs_id_workflow (run_id, workflow_id),

  KEY idx_runs_workflow (workflow_id),
  KEY idx_runs_parent (parent_run_id, workflow_id),
  KEY idx_runs_agent (agent_type),
  KEY idx_runs_status (execution_status),

  CONSTRAINT fk_runs_workflow
    FOREIGN KEY (workflow_id)
    REFERENCES agent_workflows(workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_runs_parent
    FOREIGN KEY (parent_run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT chk_runs_nonneg CHECK (
       (prompt_tokens IS NULL OR prompt_tokens >= 0)
   AND (completion_tokens IS NULL OR completion_tokens >= 0)
   AND (latency_ms IS NULL OR latency_ms >= 0)
   AND retry_count >= 0
   AND step_no >= 1
  )
) ENGINE=InnoDB;


-- Add run references after agent_runs exists.

ALTER TABLE documents
  ADD CONSTRAINT fk_documents_run
  FOREIGN KEY (extraction_run_id)
  REFERENCES agent_runs(run_id)
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE document_validations
  ADD CONSTRAINT fk_val_run
  FOREIGN KEY (validation_run_id)
  REFERENCES agent_runs(run_id)
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE exceptions
  ADD CONSTRAINT fk_exc_run
  FOREIGN KEY (detected_by_run_id)
  REFERENCES agent_runs(run_id)
  ON DELETE SET NULL ON UPDATE CASCADE;


-- ---------------------------------------------------------------------
-- 9. investigations
-- Run must belong to the same workflow.
-- Workflow must be tied to the same exception.
-- ---------------------------------------------------------------------

CREATE TABLE investigations (
  investigation_id  INT AUTO_INCREMENT PRIMARY KEY,
  exception_id      INT NOT NULL,
  workflow_id       INT NOT NULL,
  run_id            INT NOT NULL,
  summary           TEXT NOT NULL,
  possible_cause    TEXT NULL,
  affected_process  VARCHAR(100) NULL,
  urgency           ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
  recommended_next  TEXT NULL,
  status            ENUM('COMPLETED','SUPERSEDED') NOT NULL DEFAULT 'COMPLETED',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_inv_id_exception (investigation_id, exception_id),

  KEY idx_inv_exception (exception_id),
  KEY idx_inv_workflow (workflow_id),
  KEY idx_inv_run (run_id, workflow_id),
  KEY idx_inv_wf_exception (workflow_id, exception_id),

  CONSTRAINT fk_inv_exception
    FOREIGN KEY (exception_id)
    REFERENCES exceptions(exception_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_inv_run
    FOREIGN KEY (run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_inv_workflow_exception
    FOREIGN KEY (workflow_id, exception_id)
    REFERENCES agent_workflows(workflow_id, exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 10. investigation_evidence
-- Exactly one source record per evidence item.
-- ---------------------------------------------------------------------

CREATE TABLE investigation_evidence (
  evidence_id       INT AUTO_INCREMENT PRIMARY KEY,
  investigation_id  INT NOT NULL,
  evidence_class    ENUM('CONFIRMED_FACT','POSSIBLE_EXPLANATION') NOT NULL,
  statement         TEXT NOT NULL,
  shipment_id       INT NULL,
  event_id          INT NULL,
  document_id       INT NULL,
  validation_id     INT NULL,
  exception_id      INT NULL,
  risk_id           INT NULL,
  action_id         INT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  KEY idx_evid_investigation (investigation_id),

  CONSTRAINT fk_evid_investigation
    FOREIGN KEY (investigation_id)
    REFERENCES investigations(investigation_id)
    ON DELETE CASCADE ON UPDATE CASCADE,

  CONSTRAINT fk_evid_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_evid_event
    FOREIGN KEY (event_id)
    REFERENCES shipment_events(event_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_evid_document
    FOREIGN KEY (document_id)
    REFERENCES documents(document_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_evid_validation
    FOREIGN KEY (validation_id)
    REFERENCES document_validations(validation_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_evid_exception
    FOREIGN KEY (exception_id)
    REFERENCES exceptions(exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_evid_one_source CHECK (
       (shipment_id IS NOT NULL)
     + (event_id IS NOT NULL)
     + (document_id IS NOT NULL)
     + (validation_id IS NOT NULL)
     + (exception_id IS NOT NULL)
     + (risk_id IS NOT NULL)
     + (action_id IS NOT NULL) = 1
  )
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 11. risk_assessments
-- Composite FKs enforce shipment / exception / workflow consistency.
-- ---------------------------------------------------------------------

CREATE TABLE risk_assessments (
  risk_id             INT AUTO_INCREMENT PRIMARY KEY,
  shipment_id         INT NOT NULL,
  exception_id        INT NULL,
  workflow_id         INT NULL,
  run_id              INT NULL,
  risk_score          DECIMAL(5,2) NOT NULL,
  previous_score      DECIMAL(5,2) NULL,
  risk_level          ENUM('LOW','MEDIUM','HIGH') NOT NULL,
  ruleset_version     VARCHAR(20) NULL,
  assessment_method   ENUM('RULES','RULES_PLUS_LLM') NOT NULL DEFAULT 'RULES',
  explanation         TEXT NULL,
  assessed_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_risk_id_workflow_exception
    (risk_id, workflow_id, exception_id),

  KEY idx_risk_shipment (shipment_id, assessed_at),
  KEY idx_risk_exception_shipment (exception_id, shipment_id),
  KEY idx_risk_workflow (workflow_id),
  KEY idx_risk_workflow_shipment (workflow_id, shipment_id),
  KEY idx_risk_run (run_id, workflow_id),

  CONSTRAINT fk_risk_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_risk_exception_shipment
    FOREIGN KEY (exception_id, shipment_id)
    REFERENCES exceptions(exception_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_risk_workflow_shipment
    FOREIGN KEY (workflow_id, shipment_id)
    REFERENCES agent_workflows(workflow_id, shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_risk_workflow_exception
    FOREIGN KEY (workflow_id, exception_id)
    REFERENCES agent_workflows(workflow_id, exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_risk_run
    FOREIGN KEY (run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_risk_score
    CHECK (risk_score BETWEEN 0 AND 100),

  CONSTRAINT chk_risk_prev
    CHECK (previous_score IS NULL OR previous_score BETWEEN 0 AND 100),

  CONSTRAINT chk_risk_run_needs_wf
    CHECK (run_id IS NULL OR workflow_id IS NOT NULL)
) ENGINE=InnoDB;


-- Add risk reference to investigation evidence.

ALTER TABLE investigation_evidence
  ADD CONSTRAINT fk_evid_risk
  FOREIGN KEY (risk_id)
  REFERENCES risk_assessments(risk_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;


-- ---------------------------------------------------------------------
-- 12. risk_assessment_factors
-- One factor of each type per risk assessment.
-- ---------------------------------------------------------------------

CREATE TABLE risk_assessment_factors (
  factor_id       INT AUTO_INCREMENT PRIMARY KEY,
  risk_id         INT NOT NULL,
  factor_code     ENUM('DOCUMENT_MISMATCH','ARRIVAL_DELAY','MISSING_MILESTONE',
                       'CUSTOMS_ISSUE','STAKEHOLDER_DELAY') NOT NULL,
  weight          DECIMAL(5,2) NOT NULL,
  points_awarded  DECIMAL(5,2) NOT NULL,
  detail          VARCHAR(255) NULL,
  event_id        INT NULL,
  document_id     INT NULL,
  validation_id   INT NULL,
  exception_id    INT NULL,

  UNIQUE KEY uq_factor_per_risk (risk_id, factor_code),

  CONSTRAINT fk_factor_risk
    FOREIGN KEY (risk_id)
    REFERENCES risk_assessments(risk_id)
    ON DELETE CASCADE ON UPDATE CASCADE,

  CONSTRAINT fk_factor_event
    FOREIGN KEY (event_id)
    REFERENCES shipment_events(event_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_factor_document
    FOREIGN KEY (document_id)
    REFERENCES documents(document_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_factor_validation
    FOREIGN KEY (validation_id)
    REFERENCES document_validations(validation_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_factor_exception
    FOREIGN KEY (exception_id)
    REFERENCES exceptions(exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_factor_nonneg
    CHECK (weight >= 0 AND points_awarded >= 0),

  CONSTRAINT chk_factor_one_source CHECK (
       (event_id IS NOT NULL)
     + (document_id IS NOT NULL)
     + (validation_id IS NOT NULL)
     + (exception_id IS NOT NULL) <= 1
  )
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 13. resolution_plans
-- Risk assessment must match the plan's workflow and exception.
-- ---------------------------------------------------------------------

CREATE TABLE resolution_plans (
  plan_id              INT AUTO_INCREMENT PRIMARY KEY,
  exception_id         INT NOT NULL,
  workflow_id          INT NOT NULL,
  run_id               INT NOT NULL,
  investigation_id     INT NULL,
  risk_id              INT NULL,
  version_no           INT NOT NULL DEFAULT 1,
  supersedes_plan_id   INT NULL,
  proposed_solution    TEXT NOT NULL,
  reasoning            TEXT NULL,
  priority             ENUM('LOW','MEDIUM','HIGH','URGENT') NOT NULL DEFAULT 'MEDIUM',
  status               ENUM('DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','SUPERSEDED',
                            'EXECUTING','COMPLETED','FAILED') NOT NULL DEFAULT 'DRAFT',
  created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uq_plan_version (exception_id, version_no),
  UNIQUE KEY uq_plans_id_workflow (plan_id, workflow_id),

  KEY idx_plans_workflow (workflow_id),
  KEY idx_plans_run (run_id, workflow_id),
  KEY idx_plans_investigation (investigation_id, exception_id),
  KEY idx_plans_wf_exception (workflow_id, exception_id),
  KEY idx_plans_status (status),

  CONSTRAINT fk_plans_exception
    FOREIGN KEY (exception_id)
    REFERENCES exceptions(exception_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_plans_risk_context
    FOREIGN KEY (risk_id, workflow_id, exception_id)
    REFERENCES risk_assessments(risk_id, workflow_id, exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_plans_run
    FOREIGN KEY (run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_plans_workflow_exception
    FOREIGN KEY (workflow_id, exception_id)
    REFERENCES agent_workflows(workflow_id, exception_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_plans_investigation
    FOREIGN KEY (investigation_id, exception_id)
    REFERENCES investigations(investigation_id, exception_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_plans_supersedes
    FOREIGN KEY (supersedes_plan_id)
    REFERENCES resolution_plans(plan_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_plans_version
    CHECK (version_no >= 1)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- 14. actions
-- ---------------------------------------------------------------------

CREATE TABLE actions (
  action_id           INT AUTO_INCREMENT PRIMARY KEY,
  plan_id             INT NOT NULL,
  workflow_id         INT NOT NULL,
  created_by_run_id   INT NOT NULL,
  action_type         ENUM('REQUEST_DOCUMENT_CORRECTION','REQUEST_MISSING_DOCUMENT',
                           'SEND_FOLLOW_UP_EMAIL','NOTIFY_OPERATIONS_OFFICER',
                           'ESCALATE_TO_MANAGER','UPDATE_SHIPMENT_STATUS',
                           'CREATE_NOTIFICATION') NOT NULL,
  action_description  TEXT NOT NULL,
  action_payload      JSON NULL,
  requires_approval   TINYINT(1) NOT NULL DEFAULT 1,
  approval_status     ENUM('NOT_REQUIRED','PENDING','APPROVED','REJECTED')
                      NOT NULL DEFAULT 'PENDING',
  approved_by         INT NULL,
  approved_at         DATETIME NULL,
  rejection_reason    TEXT NULL,
  execution_status    ENUM('NOT_STARTED','EXECUTING','SUCCEEDED','FAILED','SKIPPED')
                      NOT NULL DEFAULT 'NOT_STARTED',
  idempotency_key     VARCHAR(100) NOT NULL,
  executed_at         DATETIME NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_actions_idempotency (idempotency_key),
  UNIQUE KEY uq_actions_id_workflow (action_id, workflow_id),

  KEY idx_actions_plan (plan_id, workflow_id),
  KEY idx_actions_run (created_by_run_id, workflow_id),
  KEY idx_actions_workflow (workflow_id),
  KEY idx_actions_approval (approval_status),
  KEY idx_actions_execution (execution_status),

  CONSTRAINT fk_actions_plan
    FOREIGN KEY (plan_id, workflow_id)
    REFERENCES resolution_plans(plan_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_actions_run
    FOREIGN KEY (created_by_run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_actions_approver
    FOREIGN KEY (approved_by)
    REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_actions_approval_consistent CHECK (
       (requires_approval = 0 AND approval_status = 'NOT_REQUIRED')
    OR (requires_approval = 1 AND approval_status IN ('PENDING','APPROVED','REJECTED'))
  ),

  CONSTRAINT chk_actions_approved_has_approver CHECK (
    approval_status <> 'APPROVED'
    OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
  ),

  CONSTRAINT chk_actions_rejected_has_reason CHECK (
    approval_status <> 'REJECTED'
    OR rejection_reason IS NOT NULL
  ),

  CONSTRAINT chk_actions_execution_gate CHECK (
    execution_status NOT IN ('EXECUTING','SUCCEEDED')
    OR approval_status IN ('NOT_REQUIRED','APPROVED')
  )
) ENGINE=InnoDB;


-- Add action reference to investigation evidence.

ALTER TABLE investigation_evidence
  ADD CONSTRAINT fk_evid_action
  FOREIGN KEY (action_id)
  REFERENCES actions(action_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;


-- ---------------------------------------------------------------------
-- 15. action_executions
-- Every execution attempt is recorded separately.
-- ---------------------------------------------------------------------

CREATE TABLE action_executions (
  execution_id    INT AUTO_INCREMENT PRIMARY KEY,
  action_id       INT NOT NULL,
  workflow_id     INT NOT NULL,
  run_id          INT NULL,
  attempt_no      INT NOT NULL DEFAULT 1,
  status          ENUM('STARTED','SUCCEEDED','FAILED') NOT NULL DEFAULT 'STARTED',
  request_data    JSON NULL,
  response_data   JSON NULL,
  error_message   TEXT NULL,
  started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at    DATETIME NULL,

  UNIQUE KEY uq_exec_attempt (action_id, attempt_no),

  KEY idx_exec_action (action_id, workflow_id),
  KEY idx_exec_run (run_id, workflow_id),

  CONSTRAINT fk_exec_action
    FOREIGN KEY (action_id, workflow_id)
    REFERENCES actions(action_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_exec_run
    FOREIGN KEY (run_id, workflow_id)
    REFERENCES agent_runs(run_id, workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT chk_exec_attempt
    CHECK (attempt_no >= 1)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- Action execution approval triggers
-- ---------------------------------------------------------------------

DELIMITER $$

CREATE TRIGGER trg_exec_approval_ins
BEFORE INSERT ON action_executions
FOR EACH ROW
BEGIN
  DECLARE v_approval VARCHAR(20);

  SELECT approval_status
  INTO v_approval
  FROM actions
  WHERE action_id = NEW.action_id;

  IF v_approval IS NOT NULL
     AND v_approval NOT IN ('NOT_REQUIRED','APPROVED') THEN

    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Cannot record an execution attempt: action is not approved';
  END IF;
END$$


CREATE TRIGGER trg_exec_approval_upd
BEFORE UPDATE ON action_executions
FOR EACH ROW
BEGIN
  DECLARE v_approval VARCHAR(20);

  IF NEW.status = 'SUCCEEDED' THEN

    SELECT approval_status
    INTO v_approval
    FROM actions
    WHERE action_id = NEW.action_id;

    IF v_approval IS NOT NULL
       AND v_approval NOT IN ('NOT_REQUIRED','APPROVED') THEN

      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot mark attempt SUCCEEDED: action is not approved';
    END IF;
  END IF;
END$$

DELIMITER ;


-- ---------------------------------------------------------------------
-- 16. audit_logs
-- Append-only, enforced by triggers.
-- ---------------------------------------------------------------------

CREATE TABLE audit_logs (
  log_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  actor_type     ENUM('USER','AGENT','SYSTEM') NOT NULL,
  actor_user_id  INT NULL,
  actor_name     VARCHAR(100) NULL,
  action         VARCHAR(100) NOT NULL,
  entity_type    VARCHAR(50) NOT NULL,
  entity_id      INT NULL,
  shipment_id    INT NULL,
  workflow_id    INT NULL,
  run_id         INT NULL,
  details        JSON NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  KEY idx_audit_entity (entity_type, entity_id),
  KEY idx_audit_shipment (shipment_id),
  KEY idx_audit_workflow (workflow_id),
  KEY idx_audit_created (created_at),

  CONSTRAINT fk_audit_user
    FOREIGN KEY (actor_user_id)
    REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_audit_shipment
    FOREIGN KEY (shipment_id)
    REFERENCES shipments(shipment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_audit_workflow
    FOREIGN KEY (workflow_id)
    REFERENCES agent_workflows(workflow_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_audit_run
    FOREIGN KEY (run_id)
    REFERENCES agent_runs(run_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------
-- Audit log protection triggers
-- ---------------------------------------------------------------------

CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
SIGNAL SQLSTATE '45000'
SET MESSAGE_TEXT = 'audit_logs is append-only: UPDATE not allowed';


CREATE TRIGGER trg_audit_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
SIGNAL SQLSTATE '45000'
SET MESSAGE_TEXT = 'audit_logs is append-only: DELETE not allowed';


-- =====================================================================
-- VIEWS
-- =====================================================================


-- ---------------------------------------------------------------------
-- View 1: Exception trace
-- ---------------------------------------------------------------------

CREATE VIEW v_exception_trace AS
SELECT
  e.exception_id,
  e.exception_type,
  e.status AS exception_status,
  p.plan_id,
  p.version_no AS plan_version,
  p.status AS plan_status,
  w.workflow_public_id,
  w.status AS workflow_status,
  i.investigation_id,
  i.summary AS investigation_summary,
  r.risk_id,
  r.risk_score,
  r.risk_level,
  a.action_id,
  a.action_type,
  a.approval_status,
  a.approved_by,
  a.execution_status,
  ex.attempt_no AS latest_attempt_no,
  ex.status AS latest_attempt_status

FROM exceptions e

LEFT JOIN resolution_plans p
  ON p.exception_id = e.exception_id

LEFT JOIN agent_workflows w
  ON w.workflow_id = p.workflow_id

LEFT JOIN investigations i
  ON i.investigation_id = p.investigation_id

LEFT JOIN risk_assessments r
  ON r.risk_id = p.risk_id

LEFT JOIN actions a
  ON a.plan_id = p.plan_id

LEFT JOIN action_executions ex
  ON ex.action_id = a.action_id
  AND ex.attempt_no = (
    SELECT MAX(x.attempt_no)
    FROM action_executions x
    WHERE x.action_id = a.action_id
  );


-- ---------------------------------------------------------------------
-- View 2: Workflow history
-- One row per workflow.
-- ---------------------------------------------------------------------

CREATE VIEW v_workflow_history AS
SELECT
  w.workflow_id,
  w.workflow_public_id,
  w.shipment_id,
  w.exception_id,
  w.trigger_type,
  w.status,
  w.current_node,
  w.started_at,
  w.completed_at,

  (SELECT COUNT(*)
   FROM agent_runs x
   WHERE x.workflow_id = w.workflow_id) AS step_count,

  (SELECT COUNT(*)
   FROM investigations x
   WHERE x.workflow_id = w.workflow_id) AS investigation_count,

  (SELECT COUNT(*)
   FROM resolution_plans x
   WHERE x.workflow_id = w.workflow_id) AS plan_count,

  (SELECT COUNT(*)
   FROM actions x
   WHERE x.workflow_id = w.workflow_id) AS action_count

FROM agent_workflows w;


-- ---------------------------------------------------------------------
-- View 3: Action execution history
-- One row per execution attempt.
-- ---------------------------------------------------------------------

CREATE VIEW v_action_execution_history AS
SELECT
  a.action_id,
  a.plan_id,
  a.workflow_id,
  a.action_type,
  a.approval_status,
  ex.execution_id,
  ex.attempt_no,
  ex.status AS attempt_status,
  ex.error_message,
  ex.started_at,
  ex.completed_at

FROM actions a

JOIN action_executions ex
  ON ex.action_id = a.action_id;


-- ---------------------------------------------------------------------
-- View 4: KPI overview
-- ---------------------------------------------------------------------

CREATE VIEW v_kpi_overview AS
SELECT

  (SELECT COUNT(*)
   FROM shipments) AS total_shipments,

  (SELECT COUNT(*)
   FROM shipments
   WHERE status NOT IN ('DELIVERED','CANCELLED')) AS active_shipments,

  (SELECT COUNT(*)
   FROM shipments
   WHERE current_risk_level = 'HIGH'
     AND status NOT IN ('DELIVERED','CANCELLED')) AS high_risk_shipments,

  (SELECT COUNT(*)
   FROM exceptions
   WHERE status NOT IN ('RESOLVED','CLOSED')) AS open_exceptions,

  (SELECT COUNT(*)
   FROM exceptions
   WHERE status IN ('RESOLVED','CLOSED')) AS resolved_exceptions,

  (SELECT COALESCE(
      ROUND(AVG(TIMESTAMPDIFF(MINUTE, detected_at, resolved_at)), 1),
      0)
   FROM exceptions
   WHERE resolved_at IS NOT NULL) AS avg_resolution_minutes;


-- ---------------------------------------------------------------------
-- View 5: KPI automation
-- ---------------------------------------------------------------------

CREATE VIEW v_kpi_automation AS
SELECT

  COUNT(*) AS total_actions,

  COALESCE(
    SUM(requires_approval = 0 AND execution_status = 'SUCCEEDED'),
    0
  ) AS auto_executed,

  COALESCE(
    SUM(requires_approval = 1 AND approval_status = 'APPROVED'),
    0
  ) AS human_approved,

  COALESCE(
    SUM(approval_status = 'REJECTED'),
    0
  ) AS rejected,

  COALESCE(
    ROUND(
      100 * SUM(requires_approval = 0 AND execution_status = 'SUCCEEDED')
      / NULLIF(COUNT(*), 0),
      1
    ),
    0
  ) AS automation_rate_pct

FROM actions;


-- ---------------------------------------------------------------------
-- View 6: Exception statistics
-- ---------------------------------------------------------------------

CREATE VIEW v_exception_stats AS
SELECT
  exception_type,
  status,
  COUNT(*) AS total

FROM exceptions

GROUP BY exception_type, status;


-- =====================================================================
-- END OF CARGOPILOT 360 DATABASE SCHEMA
-- 16 TABLES
-- 6 VIEWS
-- 4 TRIGGERS
-- =====================================================================
