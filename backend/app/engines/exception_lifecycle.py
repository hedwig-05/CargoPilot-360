from copy import deepcopy
from datetime import datetime
import re
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Exception as ShipmentException,
    ExceptionStatusHistory,
    AuditLog,
)


ACTIVE_EXCEPTION_STATUSES = [
    "OPEN", "INVESTIGATING", "AWAITING_APPROVAL", "IN_PROGRESS",
    "AWAITING_RESPONSE", "PENDING_3RD_PARTY"
]
PROTECTED_EXCEPTION_STATUSES = [
    "INVESTIGATING", "AWAITING_APPROVAL", "IN_PROGRESS",
    "AWAITING_RESPONSE", "PENDING_3RD_PARTY"
]
ALL_EXCEPTION_STATUSES = ACTIVE_EXCEPTION_STATUSES + ["RESOLVED", "CLOSED"]

# Keep source identifiers centralized. Add new monitoring sources here.
OVERDUE_MILESTONE = "OVERDUE_MILESTONE"
EXPECTED_ARRIVAL = "EXPECTED_ARRIVAL"
LEGACY_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"
SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def get_active_exception(db: Session, shipment_id: int, exception_type: str):
    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.exception_type == exception_type,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .first()
    )


def get_active_exceptions_for_shipment(db: Session, shipment_id: int):
    return (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
        )
        .order_by(ShipmentException.detected_at.desc())
        .all()
    )


def _minutes_between(start, end):
    if start is None or end is None:
        return 0
    return max(0, int((end - start).total_seconds() // 60))


def _max_active_source_severity(sources):
    active = [
        item.get("severity", "MEDIUM")
        for item in sources.values()
        if item.get("active", True)
    ]
    return max(active, key=lambda value: SEVERITY_RANK.get(value, 0), default=None)


def _initial_source_map(exception):
    """Preserve source-less legacy evidence before the first structured update."""
    if isinstance(exception.sources, dict):
        return deepcopy(exception.sources)

    sources = {}
    if exception.exception_type == "SHIPMENT_DELAY":
        matches = re.findall(
            r"([A-Z_]+)\s+\(Event ID:\s*(\d+)",
            exception.description or "",
        )
        events = [
            {"event_type": event_type, "event_id": int(event_id)}
            for event_type, event_id in matches
        ]
        if not events and exception.event_id:
            events = [{"event_type": None, "event_id": exception.event_id}]
        if events:
            now = datetime.now().isoformat()
            sources[OVERDUE_MILESTONE] = {
                "evidence": {"events": events},
                "severity": exception.severity,
                "active": True,
                "created_at": now,
                "updated_at": now,
                "cleared_at": None,
            }

    if not sources:
        now = datetime.now().isoformat()
        sources[LEGACY_UNCLASSIFIED] = {
            "evidence": {"description": exception.description},
            "severity": exception.severity,
            "active": True,
            "created_at": now,
            "updated_at": now,
            "cleared_at": None,
        }
    return sources


def _render_source_description(sources):
    """Render a stable human-readable projection without becoming source of truth."""
    sections = []
    for key, source in sources.items():
        if not source.get("active", True):
            continue
        evidence = source.get("evidence") or {}
        if key == OVERDUE_MILESTONE:
            events = evidence.get("events", [])
            if not events and evidence.get("event_ids"):
                events = [{"event_id": event_id} for event_id in evidence["event_ids"]]
            for event in events:
                event_id = event.get("event_id")
                event_type = event.get("event_type") or "SHIPMENT_EVENT"
                expected = event.get("expected_time")
                details = f"{event_type} (Event ID: {event_id}"
                if expected:
                    details += f", Expected: {expected}"
                details += ")"
                sections.append(details)
            if not events:
                sections.append("Overdue shipment milestone evidence is active.")
        elif key == EXPECTED_ARRIVAL:
            expected = evidence.get("expected_arrival")
            status = evidence.get("shipment_status")
            detail = "Expected shipment arrival is overdue"
            if expected:
                detail += f" (Expected: {expected})"
            if status == "ON_HOLD":
                detail += "; shipment is ON_HOLD"
            sections.append(detail + ".")
        else:
            sections.append(str(evidence.get("description") or key.replace("_", " ").title()))
    if not sections:
        return "No active shipment-delay evidence sources remain; resolution verification is eligible."
    return "Active shipment-delay evidence: " + "; ".join(sections)


def _source_snapshot(source):
    return {
        "evidence": deepcopy(source.get("evidence")),
        "severity": source.get("severity", "MEDIUM"),
        "active": source.get("active", True),
    }


def _write_source_audit(db, exception, source_key, old_source, new_source,
                        old_severity, new_severity, operator_id=None):
    db.add(AuditLog(
        actor_type="USER" if operator_id is not None else "AGENT",
        actor_user_id=operator_id,
        actor_name=None if operator_id is not None else "CargoPilot Exception Lifecycle",
        action="EXCEPTION_SOURCE_EVIDENCE_UPDATED",
        entity_type="EXCEPTION",
        entity_id=exception.exception_id,
        shipment_id=exception.shipment_id,
        details={
            "source_key": source_key,
            "old_source": deepcopy(old_source),
            "new_source": deepcopy(new_source),
            "old_severity": old_severity,
            "new_severity": new_severity,
        },
    ))


def _merge_source_evidence(db, exception, source_key, evidence, severity,
                           active, operator_id=None):
    """Merge one source without changing any other source's evidence."""
    now = datetime.now()
    sources = _initial_source_map(exception)
    old_source = deepcopy(sources.get(source_key))
    old_snapshot = _source_snapshot(old_source) if old_source else None

    new_source = deepcopy(old_source) if old_source else {
        "evidence": None,
        "severity": severity,
        "active": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "cleared_at": None,
    }
    new_source["evidence"] = deepcopy(evidence)
    new_source["severity"] = severity
    new_source["active"] = bool(active)
    new_source["updated_at"] = now.isoformat()
    if active:
        new_source["cleared_at"] = None
    elif new_source.get("active") is False and old_source and old_source.get("active") is False:
        new_source["cleared_at"] = old_source.get("cleared_at")
    else:
        new_source["cleared_at"] = now.isoformat()

    new_snapshot = _source_snapshot(new_source)
    changed = old_snapshot != new_snapshot
    if changed:
        sources[source_key] = deepcopy(new_source)
        # Assign a fresh top-level and nested dictionary for SQLAlchemy JSON tracking.
        exception.sources = deepcopy(sources)
        if exception.exception_type == "SHIPMENT_DELAY":
            exception.description = _render_source_description(sources)

    eligible = bool(sources) and all(not item.get("active", True) for item in sources.values())
    if exception.eligible_for_verification != eligible:
        exception.eligible_for_verification = eligible
        changed = True

    old_severity = exception.severity
    target_severity = _max_active_source_severity(sources)
    if target_severity is not None:
        if exception.status in PROTECTED_EXCEPTION_STATUSES:
            if SEVERITY_RANK.get(target_severity, 0) > SEVERITY_RANK.get(old_severity, 0):
                exception.severity = target_severity
                exception.severity_recalculation_pending = False
            elif SEVERITY_RANK.get(target_severity, 0) < SEVERITY_RANK.get(old_severity, 0):
                exception.severity_recalculation_pending = True
        else:
            exception.severity = target_severity
            exception.severity_recalculation_pending = False

    if changed or old_severity != exception.severity:
        _write_source_audit(
            db, exception, source_key, old_snapshot, new_snapshot,
            old_severity, exception.severity, operator_id
        )
    return changed or old_severity != exception.severity


def transition_exception_status(
    db: Session,
    exception_id: int,
    new_status: str,
    operator_id: int = None,
    commit: bool = True,
    resolution_notes: str = None
):
    if new_status not in ALL_EXCEPTION_STATUSES:
        raise ValueError(f"Unsupported exception status: {new_status}")

    exception = (
        db.query(ShipmentException)
        .filter(ShipmentException.exception_id == exception_id)
        .with_for_update()
        .first()
    )
    if exception is None:
        raise ValueError(f"Exception ID {exception_id} not found.")

    old_status = exception.status
    if old_status == new_status:
        return {
            "success": True, "message": "Exception already has the requested status.",
            "exception_id": exception_id, "status": old_status
        }
    if old_status in ("RESOLVED", "CLOSED"):
        raise ValueError("A resolved or closed exception cannot be reopened.")

    changed_at = datetime.now()
    if old_status == "PENDING_3RD_PARTY":
        pause_started = (
            db.query(ExceptionStatusHistory)
            .filter(
                ExceptionStatusHistory.exception_id == exception_id,
                ExceptionStatusHistory.new_status == "PENDING_3RD_PARTY"
            )
            .order_by(ExceptionStatusHistory.changed_at.desc(),
                      ExceptionStatusHistory.log_id.desc())
            .first()
        )
        if pause_started:
            exception.total_paused_minutes = (
                (exception.total_paused_minutes or 0)
                + _minutes_between(pause_started.changed_at, changed_at)
            )

    if new_status == "INVESTIGATING" and exception.acknowledged_at is None:
        exception.acknowledged_at = changed_at

    exception.status = new_status

    # Apply deferred severity recalculation exactly when work returns to OPEN.
    if new_status == "OPEN" and exception.severity_recalculation_pending:
        target = _max_active_source_severity(exception.sources or {})
        if target is not None:
            exception.severity = target
        exception.severity_recalculation_pending = False

    if new_status == "RESOLVED":
        exception.resolved_at = changed_at
        if resolution_notes is not None:
            exception.resolution_notes = resolution_notes.strip()

    db.add(ExceptionStatusHistory(
        exception_id=exception_id, old_status=old_status, new_status=new_status,
        changed_at=changed_at, operator_id=operator_id
    ))
    if commit:
        db.commit()
        db.refresh(exception)
    else:
        db.flush()

    return {
        "success": True, "exception_id": exception.exception_id,
        "old_status": old_status, "status": exception.status,
        "changed_at": changed_at, "acknowledged_at": exception.acknowledged_at,
        "resolved_at": exception.resolved_at,
        "total_paused_minutes": exception.total_paused_minutes
    }


def create_or_update_exception(
    db: Session,
    shipment_id: int,
    exception_type: str,
    description: str,
    severity: str = "MEDIUM",
    document_id: int = None,
    event_id: int = None,
    detected_by: str = "MONITORING_AGENT",
    commit: bool = True,
    operator_id: int = None,
    source_key: str = None,
    source_evidence: dict = None,
    source_active: bool = True,
):
    """Create/update an exception, optionally merging one structured source.

    Legacy callers retain their existing description format. For source-aware
    callers, description remains unchanged until verification reads structured
    evidence, avoiding a regex compatibility break.
    """
    try:
        existing = (
            db.query(ShipmentException)
            .filter(
                ShipmentException.shipment_id == shipment_id,
                ShipmentException.exception_type == exception_type,
                ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
            )
            .with_for_update()
            .first()
        )

        if existing is not None:
            if source_key:
                changed = _merge_source_evidence(
                    db, existing, source_key, source_evidence, severity,
                    source_active, operator_id
                )
                # Do not replace the legacy description while verifier migration
                # is pending. Preserve old regex markers byte-for-byte.
                if document_id is not None:
                    existing.document_id = document_id
                if event_id is not None:
                    existing.event_id = event_id
                if commit:
                    db.commit()
                    db.refresh(existing)
                else:
                    db.flush()
                return {
                    "success": True,
                    "operation": "UPDATED" if changed else "UNCHANGED",
                    "exception_id": existing.exception_id,
                    "exception": existing,
                }

            if existing.status in PROTECTED_EXCEPTION_STATUSES:
                return {
                    "success": True, "operation": "SKIPPED",
                    "exception_id": existing.exception_id, "exception": existing,
                    "message": "Existing exception is being handled by another workflow."
                }
            existing.description = description
            existing.severity = severity
            if document_id is not None:
                existing.document_id = document_id
            if event_id is not None:
                existing.event_id = event_id
            if commit:
                db.commit()
                db.refresh(existing)
            else:
                db.flush()
            return {
                "success": True, "operation": "UPDATED",
                "exception_id": existing.exception_id, "exception": existing
            }

        new_exception = ShipmentException(
            shipment_id=shipment_id, exception_type=exception_type,
            description=description, severity=severity, status="OPEN",
            document_id=document_id, event_id=event_id, detected_by=detected_by,
            sources=({} if source_key else None),
            eligible_for_verification=False,
            severity_recalculation_pending=False,
        )
        if source_key:
            # New rows are created in the savepoint so a duplicate open_key race
            # can be recovered without discarding the caller's outer transaction.
            try:
                with db.begin_nested():
                    db.add(new_exception)
                    db.flush()
            except IntegrityError:
                existing = (
                    db.query(ShipmentException)
                    .filter(
                        ShipmentException.shipment_id == shipment_id,
                        ShipmentException.exception_type == exception_type,
                        ShipmentException.status.in_(ACTIVE_EXCEPTION_STATUSES)
                    )
                    .with_for_update()
                    .first()
                )
                if existing is None:
                    raise
                _merge_source_evidence(
                    db, existing, source_key, source_evidence, severity,
                    source_active, operator_id
                )
                if commit:
                    db.commit()
                    db.refresh(existing)
                else:
                    db.flush()
                return {
                    "success": True, "operation": "UPDATED",
                    "exception_id": existing.exception_id, "exception": existing,
                    "message": "Concurrent create recovered; source evidence merged."
                }
            _merge_source_evidence(
                db, new_exception, source_key, source_evidence, severity,
                source_active, operator_id
            )
        else:
            db.add(new_exception)
            db.flush()

        db.add(ExceptionStatusHistory(
            exception_id=new_exception.exception_id,
            old_status=None, new_status="OPEN",
            changed_at=new_exception.detected_at or datetime.now(),
            operator_id=operator_id
        ))
        if commit:
            db.commit()
            db.refresh(new_exception)
        else:
            db.flush()
        return {
            "success": True, "operation": "CREATED",
            "exception_id": new_exception.exception_id, "exception": new_exception
        }
    except Exception:
        db.rollback()
        raise


def resolve_exception(
    db: Session,
    exception_id: int,
    resolution_notes: str,
    verified: bool = False,
    commit: bool = True,
    operator_id: int = None
):
    if not verified:
        raise ValueError("Exception cannot be resolved without verification.")
    if not resolution_notes or not resolution_notes.strip():
        raise ValueError("Resolution notes are required.")
    try:
        exception = (
            db.query(ShipmentException)
            .filter(ShipmentException.exception_id == exception_id)
            .with_for_update()
            .first()
        )
        if exception is None:
            raise ValueError(f"Exception ID {exception_id} not found.")
        if exception.status in ("RESOLVED", "CLOSED"):
            return {
                "success": True, "message": "Exception is already resolved.",
                "exception_id": exception_id, "status": exception.status
            }
        exception.resolution_notes = resolution_notes.strip()
        result = transition_exception_status(
            db=db, exception_id=exception_id, new_status="RESOLVED",
            operator_id=operator_id, commit=commit,
            resolution_notes=resolution_notes.strip()
        )
        result["message"] = "Exception resolved successfully."
        return result
    except Exception:
        db.rollback()
        raise
