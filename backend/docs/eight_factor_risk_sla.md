# CargoPilot 360 — Eight-factor risk and exception SLA

## Risk configuration v2.0

The v2.0 configuration is created as a **DRAFT**. It must be evaluated before activation.

| Factor code | Weight | Response target |
|---|---:|---:|
| DAMAGE_SHORTAGE | 20 | 2 hours |
| DOCUMENT_MISMATCH | 20 | 2 hours |
| CUSTOMS_ISSUE | 15 | 4 hours |
| ROLLED_CARGO | 15 | 4 hours |
| ARRIVAL_DELAY | 10 | 24 hours |
| MISSING_MILESTONE | 10 | 24 hours |
| MISSING_DOCUMENT | 5 | 48 hours |
| STAKEHOLDER_DELAY | 5 | 48 hours |
| **Total** | **100** | |

The existing v1.1 configuration remains active until an administrator explicitly activates v2.0. Historical risk assessments retain their recorded `ruleset_version`.

### Create the v2.0 draft

Use the authenticated Admin account in Swagger:

`POST /api/risk-configurations/draft`

```json
{
  "configuration_name": "CargoPilot Eight-Factor Risk Model",
  "version": "2.0",
  "description": "Eight-factor operational risk model with response SLA targets.",
  "low_max_score": 29,
  "medium_max_score": 59,
  "high_max_score": 100,
  "rules": [
    {"factor_code": "DAMAGE_SHORTAGE", "factor_name": "Cargo Damage or Shortage", "weight": 20, "is_enabled": true, "description": "Reported cargo damage, loss or quantity shortage."},
    {"factor_code": "DOCUMENT_MISMATCH", "factor_name": "Document Mismatch", "weight": 20, "is_enabled": true, "description": "Conflicting or inconsistent shipping document values."},
    {"factor_code": "CUSTOMS_ISSUE", "factor_name": "Customs Issue", "weight": 15, "is_enabled": true, "description": "Customs holds, clearance problems or customs milestone delays."},
    {"factor_code": "ROLLED_CARGO", "factor_name": "Rolled Cargo", "weight": 15, "is_enabled": true, "description": "Cargo not loaded on its intended vessel or sailing."},
    {"factor_code": "ARRIVAL_DELAY", "factor_name": "Arrival Delay", "weight": 10, "is_enabled": true, "description": "Vessel arrival or shipment arrival delays."},
    {"factor_code": "MISSING_MILESTONE", "factor_name": "Missing Milestone", "weight": 10, "is_enabled": true, "description": "Required shipment milestone is missing or unrecorded."},
    {"factor_code": "MISSING_DOCUMENT", "factor_name": "Missing Document", "weight": 5, "is_enabled": true, "description": "A mandatory shipping document has not been received."},
    {"factor_code": "STAKEHOLDER_DELAY", "factor_name": "Stakeholder Delay", "weight": 5, "is_enabled": true, "description": "A required stakeholder response is overdue."}
  ]
}
```

Do **not** call the activate endpoint until v2.0 has been tested and approved.

## Exception lifecycle and clock definitions

- `detected_at` is the existing exception start time.
- The first transition to `INVESTIGATING` sets `acknowledged_at`; later transitions never overwrite it.
- `resolved_at` is set when the verified resolution workflow resolves the exception.
- `exception_status_history` records each new status, timestamp and operator. System-generated transitions use a NULL operator.
- Only `PENDING_3RD_PARTY` pauses the elapsed-time clock. `AWAITING_APPROVAL`, `IN_PROGRESS` and `AWAITING_RESPONSE` continue counting.
- TTA = `acknowledged_at - detected_at`.
- Gross TTR = `resolved_at - detected_at` (or current time while unresolved).
- Net TTR = gross TTR minus time in `PENDING_3RD_PARTY`.

The persisted `total_paused_minutes` column stores whole minutes. API metrics calculate elapsed pause time from the status-history ledger and return two decimal places.

Existing exceptions created before this feature may not have a reliable acknowledgement timestamp. Their TTA is intentionally left unrecorded rather than guessed; the API labels these `ACKNOWLEDGEMENT_NOT_RECORDED`.

## Exception type to risk factor mapping

- `DAMAGE_SHORTAGE` → `DAMAGE_SHORTAGE`
- `ROLLED_CARGO` → `ROLLED_CARGO`
- `DOCUMENT_MISMATCH` → `DOCUMENT_MISMATCH`
- `MISSING_DOCUMENT` → `MISSING_DOCUMENT`
- `CUSTOMS_HOLD` → `CUSTOMS_ISSUE`
- `SHIPMENT_DELAY` → `CUSTOMS_ISSUE` when linked to a customs-clearance delay; otherwise `ARRIVAL_DELAY`
- `MISSING_MILESTONE` and `CONTAINER_NOT_DISCHARGED` → `MISSING_MILESTONE`
- `STAKEHOLDER_RESPONSE_DELAY` → `STAKEHOLDER_DELAY`

Damage/shortage and rolled-cargo records can be entered through the authenticated manual exception endpoint. The current shipment-event schema does not contain authoritative physical inspection or carrier roll-over data, so the system does not invent automatic detections for those two categories.

## API endpoints

- `GET /api/exceptions` — exception list with SLA metrics.
- `GET /api/shipments/{shipment_id}/exceptions` — exceptions for a shipment.
- `GET /api/exceptions/{exception_id}/history` — append-only status history.
- `POST /api/shipments/{shipment_id}/exceptions` — authenticated manual exception report.
- `POST /api/exceptions/{exception_id}/status` — authenticated lifecycle transition. Use the resolution-verification workflow for RESOLVED; direct resolution through this endpoint is blocked.

The exception response includes response target, response elapsed minutes, SLA status, TTA, gross TTR, net TTR, pause duration and whether the clock is currently paused.

## Database migration

Run `backend/migrations/2026_11_14_eight_factor_risk_sla.sql` against the development database only. The script explicitly selects `cargopilot_test`. Back up the database first and run the migration once. Do not change the original `cargopilot` database during development.
