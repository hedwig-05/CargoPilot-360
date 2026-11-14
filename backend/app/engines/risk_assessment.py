
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Shipment,
    ShipmentEvent,
    DocumentValidation,
    Exception as ShipmentException,
    RiskAssessment,
    RiskAssessmentFactor,
    RiskConfiguration,
    RiskFactorRule
)


# ==================================================
# CONFIGURATION
# ==================================================

ACTIVE_EXCEPTION_STATUSES = [
    "OPEN",
    "INVESTIGATING",
    "AWAITING_APPROVAL",
    "IN_PROGRESS",
    "AWAITING_RESPONSE"
]

SEVERITY_WEIGHTS = {
    "UNCERTAIN": Decimal("0.15"),
    "LOW": Decimal("0.25"),
    "MEDIUM": Decimal("0.50"),
    "HIGH": Decimal("1.00"),
    "CRITICAL": Decimal("1.00")
}

SEVERITY_RANK = {
    "UNCERTAIN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4
}


# ==================================================
# LOAD ACTIVE RISK CONFIGURATION
# ==================================================

def get_active_risk_configuration(db: Session):
    """Load the currently active risk configuration and rules."""

    configuration = (
        db.query(RiskConfiguration)
        .filter(
            RiskConfiguration.status == "ACTIVE"
        )
        .first()
    )

    if not configuration:
        raise ValueError(
            "No active risk configuration found."
        )

    rules = (
        db.query(RiskFactorRule)
        .filter(
            RiskFactorRule.configuration_id
            == configuration.configuration_id,
            RiskFactorRule.is_enabled.is_(True)
        )
        .all()
    )

    if not rules:
        raise ValueError(
            "Active risk configuration has no enabled rules."
        )

    return configuration, rules


# ==================================================
# DETECT RISK FACTORS
# ==================================================

def detect_risk_factors(db: Session, shipment_id: int):
    """
    Collect evidence for the configured risk factors.

    Risk factors:
    - DOCUMENT_MISMATCH
    - ARRIVAL_DELAY
    - MISSING_MILESTONE
    - CUSTOMS_ISSUE
    - STAKEHOLDER_DELAY
    """

    evidence = {
        "DOCUMENT_MISMATCH": [],
        "ARRIVAL_DELAY": [],
        "MISSING_MILESTONE": [],
        "CUSTOMS_ISSUE": [],
        "STAKEHOLDER_DELAY": []
    }

    # --------------------------------------------------
    # 1. EXCEPTION-BASED EVIDENCE
    # --------------------------------------------------

    exceptions = (
        db.query(ShipmentException)
        .filter(
            ShipmentException.shipment_id == shipment_id,
            ShipmentException.status.in_(
                ACTIVE_EXCEPTION_STATUSES
            )
        )
        .all()
    )

    for item in exceptions:

        description = item.description or ""

        # DOCUMENT MISMATCH / MISSING DOCUMENT

        if item.exception_type in [
            "DOCUMENT_MISMATCH",
            "MISSING_DOCUMENT"
        ]:

            if item.exception_type == "DOCUMENT_MISMATCH":

                fields = []
                marker = "Affected fields:"

                if marker in description:

                    field_text = description.split(
                        marker,
                        1
                    )[1]

                    field_text = field_text.split(
                        ".",
                        1
                    )[0]

                    fields = [
                        field.strip().lower()
                        for field in field_text.split(",")
                        if field.strip()
                    ]

                if fields:

                    for field in fields:

                        evidence["DOCUMENT_MISMATCH"].append({
                            "detail": description,
                            "severity": item.severity,
                            "issue_key": f"field:{field}",
                            "exception_id": item.exception_id
                        })

                else:

                    evidence["DOCUMENT_MISMATCH"].append({
                        "detail": description,
                        "severity": item.severity,
                        "issue_key": (
                            f"exception:{item.exception_id}"
                        ),
                        "exception_id": item.exception_id
                    })

            else:

                evidence["DOCUMENT_MISMATCH"].append({
                    "detail": description,
                    "severity": item.severity,
                    "issue_key": (
                        f"exception:{item.exception_id}"
                    ),
                    "exception_id": item.exception_id
                })

        # SHIPMENT DELAY

        elif item.exception_type == "SHIPMENT_DELAY":

            # Identify the event responsible for the delay.

            delayed_event = None

            if item.event_id:

                delayed_event = (
                    db.query(ShipmentEvent)
                    .filter(
                        ShipmentEvent.event_id == item.event_id
                    )
                    .first()
                )

            # Customs clearance delay

            if (
                delayed_event
                and delayed_event.event_type == "CUSTOMS_CLEARED"
            ):

                evidence["CUSTOMS_ISSUE"].append({
                    "detail": description,
                    "severity": item.severity,
                    "issue_key": f"event:{item.event_id}",
                    "exception_id": item.exception_id,
                    "event_id": item.event_id
                })

            # Other shipment delays

            else:

                evidence["ARRIVAL_DELAY"].append({
                    "detail": description,
                    "severity": item.severity,
                    "issue_key": (
                        f"event:{item.event_id}"
                        if item.event_id
                        else f"exception:{item.exception_id}"
                    ),
                    "exception_id": item.exception_id,
                    "event_id": item.event_id
                })

        # MISSING MILESTONE

        elif item.exception_type == "MISSING_MILESTONE":

            evidence["MISSING_MILESTONE"].append({
                "detail": description,
                "severity": item.severity,
                "issue_key": (
                    f"event:{item.event_id}"
                    if item.event_id
                    else f"exception:{item.exception_id}"
                ),
                "exception_id": item.exception_id,
                "event_id": item.event_id
            })

        # CUSTOMS HOLD

        elif item.exception_type == "CUSTOMS_HOLD":

            evidence["CUSTOMS_ISSUE"].append({
                "detail": description,
                "severity": item.severity,
                "issue_key": (
                    f"event:{item.event_id}"
                    if item.event_id
                    else f"exception:{item.exception_id}"
                ),
                "exception_id": item.exception_id,
                "event_id": item.event_id
            })

        # STAKEHOLDER RESPONSE DELAY

        elif item.exception_type == "STAKEHOLDER_RESPONSE_DELAY":

            evidence["STAKEHOLDER_DELAY"].append({
                "detail": description,
                "severity": item.severity,
                "issue_key": (
                    f"exception:{item.exception_id}"
                ),
                "exception_id": item.exception_id
            })

        # CONTAINER NOT DISCHARGED

        elif item.exception_type == "CONTAINER_NOT_DISCHARGED":

            evidence["MISSING_MILESTONE"].append({
                "detail": description,
                "severity": item.severity,
                "issue_key": (
                    f"event:{item.event_id}"
                    if item.event_id
                    else f"exception:{item.exception_id}"
                ),
                "exception_id": item.exception_id,
                "event_id": item.event_id
            })

    # --------------------------------------------------
    # 2. DOCUMENT VALIDATION EVIDENCE
    # --------------------------------------------------

    validations = (
        db.query(DocumentValidation)
        .filter(
            DocumentValidation.shipment_id == shipment_id,
            DocumentValidation.validation_result.in_(
                ["MISMATCH", "MISSING", "UNCERTAIN"]
            )
        )
        .all()
    )

    for item in validations:

        if item.validation_result == "MISMATCH":
            severity = "MEDIUM"

        elif item.validation_result == "MISSING":
            severity = "HIGH"

        else:
            severity = "UNCERTAIN"

        field = (
            item.field_name or "unknown"
        ).strip().lower()

        evidence["DOCUMENT_MISMATCH"].append({
            "detail": (
                f"{item.field_name}: "
                f"{item.validation_result}"
            ),
            "severity": severity,
            "issue_key": f"field:{field}",
            "document_id": item.document_id,
            "validation_id": item.validation_id
        })

    # --------------------------------------------------
    # 3. SHIPMENT EVENT EVIDENCE
    # --------------------------------------------------

    events = (
        db.query(ShipmentEvent)
        .filter(
            ShipmentEvent.shipment_id == shipment_id
        )
        .all()
    )

    for item in events:

        # Late vessel arrival

        if (
            item.event_type == "VESSEL_ARRIVED"
            and item.event_status == "LATE"
        ):

            evidence["ARRIVAL_DELAY"].append({
                "detail": (
                    "Vessel arrival event is marked LATE."
                ),
                "severity": "MEDIUM",
                "issue_key": f"event:{item.event_id}",
                "event_id": item.event_id
            })

        # Missing milestone

        if item.event_status == "MISSING":

            evidence["MISSING_MILESTONE"].append({
                "detail": (
                    f"{item.event_type} milestone is missing."
                ),
                "severity": "MEDIUM",
                "issue_key": f"event:{item.event_id}",
                "event_id": item.event_id
            })

        # Customs inconsistency

        if (
            item.event_type == "CUSTOMS_CLEARED"
            and item.event_status == "INCONSISTENT"
        ):

            evidence["CUSTOMS_ISSUE"].append({
                "detail": (
                    "Customs milestone is inconsistent."
                ),
                "severity": "MEDIUM",
                "issue_key": f"event:{item.event_id}",
                "event_id": item.event_id
            })

    return evidence


# ==================================================
# EVIDENCE SEVERITY
# ==================================================

def get_evidence_severity(item):
    """Convert evidence severity into a scoring percentage."""

    severity = str(
        item.get("severity") or "MEDIUM"
    ).upper().strip()

    return SEVERITY_WEIGHTS.get(
        severity,
        Decimal("0.50")
    )


# ==================================================
# REMOVE DUPLICATE EVIDENCE
# ==================================================

def deduplicate_factor_evidence(factor_evidence):
    """
    Merge records describing the same underlying issue.

    Example:
    An exception and a document validation may describe
    the same container number mismatch.

    They should not count as two separate risk issues.
    """

    unique_evidence = {}

    for item in factor_evidence:

        issue_key = item.get("issue_key")

        if not issue_key:

            issue_key = (
                item.get("detail")
                or str(item.get("exception_id"))
            )

        if issue_key not in unique_evidence:

            unique_evidence[issue_key] = item.copy()
            continue

        existing = unique_evidence[issue_key]

        # Preserve source references.

        for source in [
            "event_id",
            "document_id",
            "validation_id",
            "exception_id"
        ]:

            if existing.get(source) is None:

                existing[source] = item.get(source)

        # Keep the strongest severity.

        old_severity = str(
            existing.get("severity") or "MEDIUM"
        ).upper()

        new_severity = str(
            item.get("severity") or "MEDIUM"
        ).upper()

        old_rank = SEVERITY_RANK.get(
            old_severity,
            2
        )

        new_rank = SEVERITY_RANK.get(
            new_severity,
            2
        )

        if new_rank > old_rank:

            existing["severity"] = new_severity

            existing["detail"] = (
                item.get("detail")
                or existing.get("detail")
            )

    return list(unique_evidence.values())


# ==================================================
# BUILD FACTOR EXPLANATION
# ==================================================

def build_factor_detail(factor_evidence):
    """Build a clean, duplicate-free factor explanation."""

    details = []
    seen_details = set()

    for item in factor_evidence:

        detail = str(
            item.get("detail") or ""
        ).strip()

        if detail and detail not in seen_details:

            details.append(detail)
            seen_details.add(detail)

    if not details:

        return "Evidence detected."

    result = "; ".join(details)

    if len(result) > 255:

        result = result[:252].rstrip() + "..."

    return result


# ==================================================
# CALCULATE RISK SCORE
# ==================================================

def calculate_risk_score(rules, evidence):
    """
    Calculate risk using configured factor weights.

    Each distinct issue contributes according to its severity.

    A factor cannot exceed its configured maximum weight.
    """

    factor_results = []

    total_score = Decimal("0.00")

    for rule in rules:

        raw_evidence = evidence.get(
            rule.factor_code,
            []
        )

        # Remove duplicate representations.

        factor_evidence = deduplicate_factor_evidence(
            raw_evidence
        )

        weight = Decimal(
            str(rule.weight)
        )

        if weight < Decimal("0.00"):

            raise ValueError(
                f"Invalid negative risk weight for "
                f"{rule.factor_code}."
            )

        # Calculate evidence contribution.

        points = Decimal("0.00")

        for item in factor_evidence:

            severity_percentage = get_evidence_severity(
                item
            )

            points += (
                weight * severity_percentage
            )

        # Apply the configured maximum.

        points = min(
            points,
            weight
        )

        points = points.quantize(
            Decimal("0.01")
        )

        total_score += points

        factor_results.append({
            "factor_code": rule.factor_code,
            "weight": weight,
            "points_awarded": points,
            "detail": (
                build_factor_detail(factor_evidence)
                if factor_evidence
                else "No evidence detected."
            ),
            "evidence": factor_evidence
        })

    # Risk score must remain between 0 and 100.

    total_score = min(
        total_score,
        Decimal("100.00")
    )

    total_score = total_score.quantize(
        Decimal("0.01")
    )

    return total_score, factor_results


# ==================================================
# DETERMINE RISK LEVEL
# ==================================================

def determine_risk_level(score, configuration):
    """Determine risk level using active configuration thresholds."""

    score = Decimal(str(score))

    low_max = Decimal(
        str(configuration.low_max_score)
    )

    medium_max = Decimal(
        str(configuration.medium_max_score)
    )

    if low_max >= medium_max:

        raise ValueError(
            "Invalid risk configuration: "
            "low threshold must be below medium threshold."
        )

    if score <= low_max:

        return "LOW"

    elif score <= medium_max:

        return "MEDIUM"

    return "HIGH"


# ==================================================
# ASSESS SHIPMENT RISK
# ==================================================
# ==================================================
# SELECT PRIMARY EVIDENCE SOURCE
# ==================================================

def select_primary_evidence_source(factor_evidence):
    """
    Select exactly one evidence source for a risk factor.

    The database permits a maximum of one source reference
    per risk_assessment_factors record.

    Priority:
    1. Validation
    2. Event
    3. Document
    4. Exception
    """

    for item in factor_evidence:

        # Validation is the most specific source for
        # document comparison results.

        if item.get("validation_id") is not None:

            return {
                "event_id": None,
                "document_id": None,
                "validation_id": item["validation_id"],
                "exception_id": None
            }

        # Event is the primary source for shipment milestones.

        if item.get("event_id") is not None:

            return {
                "event_id": item["event_id"],
                "document_id": None,
                "validation_id": None,
                "exception_id": None
            }

        # Document source.

        if item.get("document_id") is not None:

            return {
                "event_id": None,
                "document_id": item["document_id"],
                "validation_id": None,
                "exception_id": None
            }

        # Exception source.

        if item.get("exception_id") is not None:

            return {
                "event_id": None,
                "document_id": None,
                "validation_id": None,
                "exception_id": item["exception_id"]
            }

    # No evidence source available.

    return {
        "event_id": None,
        "document_id": None,
        "validation_id": None,
        "exception_id": None
    }
def assess_shipment_risk(
    db: Session,
    shipment_id: int,
    exception_id=None,
    workflow_id=None,
    run_id=None
):
    """
    Assess shipment risk.

    Steps:
    1. Retrieve shipment.
    2. Load active risk configuration.
    3. Collect risk evidence.
    4. Remove duplicate evidence.
    5. Calculate risk score.
    6. Determine risk level.
    7. Save assessment and factor records.
    8. Update shipment risk information.
    """

    try:

        # --------------------------------------------------
        # 1. RETRIEVE SHIPMENT
        # --------------------------------------------------

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == shipment_id
            )
            .with_for_update()
            .first()
        )

        if not shipment:

            raise ValueError(
                f"Shipment {shipment_id} was not found."
            )

        if shipment.status == "CANCELLED":

            raise ValueError(
                "Cannot assess risk for a cancelled shipment."
            )

        # --------------------------------------------------
        # 2. LOAD ACTIVE CONFIGURATION
        # --------------------------------------------------

        configuration, rules = (
            get_active_risk_configuration(db)
        )

        # --------------------------------------------------
        # 3. COLLECT EVIDENCE
        # --------------------------------------------------

        evidence = detect_risk_factors(
            db,
            shipment_id
        )

        # --------------------------------------------------
        # 4. CALCULATE RISK SCORE
        # --------------------------------------------------

        risk_score, factor_results = calculate_risk_score(
            rules,
            evidence
        )

        # --------------------------------------------------
        # 5. DETERMINE RISK LEVEL
        # --------------------------------------------------

        risk_level = determine_risk_level(
            risk_score,
            configuration
        )

        # --------------------------------------------------
        # 6. GET PREVIOUS ASSESSMENT
        # --------------------------------------------------

        previous_assessment = (
            db.query(RiskAssessment)
            .filter(
                RiskAssessment.shipment_id == shipment_id
            )
            .order_by(
                RiskAssessment.assessed_at.desc(),
                RiskAssessment.risk_id.desc()
            )
            .first()
        )

        previous_score = (
            previous_assessment.risk_score
            if previous_assessment
            else None
        )

        # --------------------------------------------------
        # 7. BUILD EXPLANATION
        # --------------------------------------------------

        explanation_parts = []

        for factor in factor_results:

            if factor["points_awarded"] > 0:

                explanation_parts.append(
                    f"{factor['factor_code']}: "
                    f"{factor['points_awarded']:.2f} points"
                )

        explanation = (
            "; ".join(explanation_parts)
            if explanation_parts
            else "No active risk evidence detected."
        )

        # --------------------------------------------------
        # 8. CREATE RISK ASSESSMENT
        # --------------------------------------------------

        assessment = RiskAssessment(
            shipment_id=shipment_id,
            exception_id=exception_id,
            workflow_id=workflow_id,
            run_id=run_id,
            risk_score=risk_score,
            previous_score=previous_score,
            risk_level=risk_level,
            ruleset_version=configuration.version,
            assessment_method="RULES",
            explanation=explanation
        )

        db.add(assessment)

        # Generate risk_id before saving factor records.

        db.flush()

                # --------------------------------------------------
        # 9. SAVE RISK FACTORS
        # --------------------------------------------------

        for factor in factor_results:

            factor_evidence = factor["evidence"]

            # Select only one source reference.

            primary_source = select_primary_evidence_source(
                factor_evidence
            )

            factor_record = RiskAssessmentFactor(
                risk_id=assessment.risk_id,
                factor_code=factor["factor_code"],
                weight=factor["weight"],
                points_awarded=factor["points_awarded"],
                detail=factor["detail"],

                event_id=primary_source["event_id"],
                document_id=primary_source["document_id"],
                validation_id=primary_source["validation_id"],
                exception_id=primary_source["exception_id"]
            )

            db.add(factor_record)

        # --------------------------------------------------
        # 10. UPDATE SHIPMENT
        # --------------------------------------------------

        shipment.current_risk_score = risk_score
        shipment.current_risk_level = risk_level

        # --------------------------------------------------
        # 11. COMMIT TRANSACTION
        # --------------------------------------------------

        db.commit()

        db.refresh(assessment)

        # --------------------------------------------------
        # 12. RETURN RESULT
        # --------------------------------------------------

        return {
            "success": True,
            "risk_id": assessment.risk_id,
            "shipment_id": shipment_id,
            "shipment_ref": shipment.shipment_ref,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "previous_score": previous_score,
            "ruleset_version": configuration.version,
            "assessment_method": "RULES",
            "explanation": explanation,
            "factors": factor_results
        }

    except Exception:

        db.rollback()

        raise
