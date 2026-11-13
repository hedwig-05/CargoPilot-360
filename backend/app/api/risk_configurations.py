
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import get_current_user, require_roles

from app.models import (
    User,
    RiskConfiguration,
    RiskFactorRule,
    AuditLog
)


router = APIRouter(
    prefix="/api/risk-configurations",
    tags=["Risk Configuration"]
)


# --------------------------------------------------
# ALLOWED RISK FACTORS
# --------------------------------------------------

ALLOWED_FACTORS = {
    "DOCUMENT_MISMATCH",
    "ARRIVAL_DELAY",
    "MISSING_MILESTONE",
    "CUSTOMS_ISSUE",
    "STAKEHOLDER_DELAY"
}


# --------------------------------------------------
# REQUEST SCHEMAS
# --------------------------------------------------

class RiskFactorInput(BaseModel):
    factor_code: str
    factor_name: str
    weight: Decimal = Field(ge=0, le=100)
    is_enabled: bool = True
    description: str | None = None


class RiskConfigurationCreate(BaseModel):
    configuration_name: str
    version: str
    description: str | None = None

    low_max_score: Decimal = Field(ge=0, le=100)
    medium_max_score: Decimal = Field(ge=0, le=100)
    high_max_score: Decimal = Field(ge=0, le=100)

    rules: list[RiskFactorInput]


class RiskConfigurationSettings(BaseModel):
    configuration_name: str
    description: str | None = None

    low_max_score: Decimal = Field(ge=0, le=100)
    medium_max_score: Decimal = Field(ge=0, le=100)
    high_max_score: Decimal = Field(ge=0, le=100)


class RiskRulesUpdate(BaseModel):
    rules: list[RiskFactorInput]


# --------------------------------------------------
# VALIDATION HELPERS
# --------------------------------------------------

def validate_thresholds(low, medium, high):

    if not (low < medium < high):
        raise HTTPException(
            status_code=400,
            detail="Risk thresholds must be in increasing order."
        )

    if high != Decimal("100"):
        raise HTTPException(
            status_code=400,
            detail="The HIGH maximum score must be 100."
        )


def validate_rules(rules):

    if not rules:
        raise HTTPException(
            status_code=400,
            detail="At least one risk factor is required."
        )

    factor_codes = [rule.factor_code for rule in rules]

    if len(factor_codes) != len(set(factor_codes)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate risk factors are not allowed."
        )

    for rule in rules:
        if rule.factor_code not in ALLOWED_FACTORS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk factor: {rule.factor_code}"
            )

    enabled_total = sum(
        (rule.weight for rule in rules if rule.is_enabled),
        Decimal("0")
    )

    if enabled_total != Decimal("100"):
        raise HTTPException(
            status_code=400,
            detail="The total weight of enabled risk factors must equal 100."
        )


# --------------------------------------------------
# AUDIT LOG HELPER
# --------------------------------------------------

def create_audit_log(
    db,
    user,
    action,
    entity_id,
    details
):

    audit = AuditLog(
        actor_type="USER",
        actor_user_id=user.user_id,
        actor_name=user.name,
        action=action,
        entity_type="RISK_CONFIGURATION",
        entity_id=entity_id,
        details=details
    )

    db.add(audit)


# --------------------------------------------------
# GET ALL CONFIGURATIONS
# --------------------------------------------------

@router.get("")
def get_configurations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    configurations = (
        db.query(RiskConfiguration)
        .order_by(RiskConfiguration.configuration_id.desc())
        .all()
    )

    return [
        {
            "configuration_id": config.configuration_id,
            "configuration_name": config.configuration_name,
            "version": config.version,
            "description": config.description,
            "low_max_score": float(config.low_max_score),
            "medium_max_score": float(config.medium_max_score),
            "high_max_score": float(config.high_max_score),
            "status": config.status,
            "created_at": config.created_at
        }
        for config in configurations
    ]


# --------------------------------------------------
# GET ACTIVE CONFIGURATION
# --------------------------------------------------

@router.get("/active")
def get_active_configuration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    config = (
        db.query(RiskConfiguration)
        .filter(RiskConfiguration.status == "ACTIVE")
        .first()
    )

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="No active risk configuration exists."
        )

    return {
        "configuration_id": config.configuration_id,
        "configuration_name": config.configuration_name,
        "version": config.version,
        "status": config.status,
        "low_max_score": float(config.low_max_score),
        "medium_max_score": float(config.medium_max_score),
        "high_max_score": float(config.high_max_score),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "factor_code": rule.factor_code,
                "factor_name": rule.factor_name,
                "weight": float(rule.weight),
                "is_enabled": rule.is_enabled,
                "description": rule.description
            }
            for rule in config.rules
        ]
    }


# --------------------------------------------------
# GET CONFIGURATION DETAILS
# --------------------------------------------------

@router.get("/{configuration_id}")
def get_configuration(
    configuration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    config = db.query(RiskConfiguration).filter(
        RiskConfiguration.configuration_id == configuration_id
    ).first()

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Risk configuration not found."
        )

    return {
        "configuration_id": config.configuration_id,
        "configuration_name": config.configuration_name,
        "version": config.version,
        "description": config.description,
        "status": config.status,
        "low_max_score": float(config.low_max_score),
        "medium_max_score": float(config.medium_max_score),
        "high_max_score": float(config.high_max_score),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "factor_code": rule.factor_code,
                "factor_name": rule.factor_name,
                "weight": float(rule.weight),
                "is_enabled": rule.is_enabled,
                "description": rule.description
            }
            for rule in config.rules
        ]
    }


# --------------------------------------------------
# CREATE DRAFT CONFIGURATION
# ADMIN ONLY
# --------------------------------------------------

@router.post("/draft", status_code=status.HTTP_201_CREATED)
def create_configuration(
    data: RiskConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):

    validate_thresholds(
        data.low_max_score,
        data.medium_max_score,
        data.high_max_score
    )

    validate_rules(data.rules)

    existing = db.query(RiskConfiguration).filter(
        RiskConfiguration.version == data.version
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This configuration version already exists."
        )

    try:
        config = RiskConfiguration(
            configuration_name=data.configuration_name,
            version=data.version,
            description=data.description,
            low_max_score=data.low_max_score,
            medium_max_score=data.medium_max_score,
            high_max_score=data.high_max_score,
            status="DRAFT",
            created_by=current_user.user_id
        )

        db.add(config)
        db.flush()

        for rule_data in data.rules:
            db.add(
                RiskFactorRule(
                    configuration_id=config.configuration_id,
                    factor_code=rule_data.factor_code,
                    factor_name=rule_data.factor_name,
                    weight=rule_data.weight,
                    is_enabled=rule_data.is_enabled,
                    description=rule_data.description
                )
            )

        create_audit_log(
            db,
            current_user,
            "CREATE_RISK_CONFIGURATION",
            config.configuration_id,
            {
                "version": data.version,
                "status": "DRAFT",
                "total_weight": 100
            }
        )

        db.commit()

        return {
            "message": "Risk configuration draft created successfully.",
            "configuration_id": config.configuration_id,
            "version": config.version,
            "status": config.status
        }

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# UPDATE DRAFT RISK RULES
# ADMIN ONLY
# --------------------------------------------------

@router.put("/{configuration_id}/rules")
def update_risk_rules(
    configuration_id: int,
    data: RiskRulesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):

    config = db.query(RiskConfiguration).filter(
        RiskConfiguration.configuration_id == configuration_id
    ).with_for_update().first()

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Risk configuration not found."
        )

    if config.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only DRAFT configurations can be modified."
        )

    validate_rules(data.rules)

    try:
        old_rules = [
            {
                "factor_code": rule.factor_code,
                "weight": str(rule.weight),
                "is_enabled": rule.is_enabled
            }
            for rule in config.rules
        ]

        config.rules.clear()

        for rule_data in data.rules:
            config.rules.append(
                RiskFactorRule(
                    factor_code=rule_data.factor_code,
                    factor_name=rule_data.factor_name,
                    weight=rule_data.weight,
                    is_enabled=rule_data.is_enabled,
                    description=rule_data.description
                )
            )

        new_rules = [
            {
                "factor_code": rule.factor_code,
                "weight": str(rule.weight),
                "is_enabled": rule.is_enabled
            }
            for rule in data.rules
        ]

        create_audit_log(
            db,
            current_user,
            "UPDATE_RISK_RULES",
            config.configuration_id,
            {
                "old_rules": old_rules,
                "new_rules": new_rules
            }
        )

        db.commit()

        return {
            "message": "Risk rules updated successfully.",
            "configuration_id": config.configuration_id,
            "status": config.status
        }

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# UPDATE DRAFT SETTINGS
# ADMIN ONLY
# --------------------------------------------------

@router.put("/{configuration_id}/settings")
def update_configuration_settings(
    configuration_id: int,
    data: RiskConfigurationSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):

    config = db.query(RiskConfiguration).filter(
        RiskConfiguration.configuration_id == configuration_id
    ).with_for_update().first()

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Risk configuration not found."
        )

    if config.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only DRAFT configurations can be modified."
        )

    validate_thresholds(
        data.low_max_score,
        data.medium_max_score,
        data.high_max_score
    )

    old_settings = {
        "configuration_name": config.configuration_name,
        "low_max_score": str(config.low_max_score),
        "medium_max_score": str(config.medium_max_score),
        "high_max_score": str(config.high_max_score)
    }

    try:
        config.configuration_name = data.configuration_name
        config.description = data.description
        config.low_max_score = data.low_max_score
        config.medium_max_score = data.medium_max_score
        config.high_max_score = data.high_max_score

        create_audit_log(
            db,
            current_user,
            "UPDATE_RISK_CONFIGURATION_SETTINGS",
            config.configuration_id,
            {
                "old_settings": old_settings,
                "new_settings": data.model_dump(mode="json")
            }
        )

        db.commit()

        return {
            "message": "Risk configuration settings updated successfully.",
            "configuration_id": config.configuration_id,
            "status": config.status
        }

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# ACTIVATE CONFIGURATION
# ADMIN ONLY
# --------------------------------------------------

@router.post("/{configuration_id}/activate")
def activate_configuration(
    configuration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):

    try:
        # Lock the configuration being activated.
        config = db.query(RiskConfiguration).filter(
            RiskConfiguration.configuration_id == configuration_id
        ).with_for_update().first()

        if config is None:
            raise HTTPException(
                status_code=404,
                detail="Risk configuration not found."
            )

        if config.status != "DRAFT":
            raise HTTPException(
                status_code=400,
                detail="Only DRAFT configurations can be activated."
            )

        validate_thresholds(
            config.low_max_score,
            config.medium_max_score,
            config.high_max_score
        )

        # Validate the saved rules.
        validate_rules([
            RiskFactorInput(
                factor_code=rule.factor_code,
                factor_name=rule.factor_name,
                weight=rule.weight,
                is_enabled=rule.is_enabled,
                description=rule.description
            )
            for rule in config.rules
        ])

        # Archive the previous active configuration.
        active_configs = (
            db.query(RiskConfiguration)
            .filter(RiskConfiguration.status == "ACTIVE")
            .with_for_update()
            .all()
        )

        previous_versions = []

        for old_config in active_configs:
            old_config.status = "ARCHIVED"
            previous_versions.append(old_config.version)

        # Activate the selected configuration.
        config.status = "ACTIVE"
        config.activated_by = current_user.user_id
        from datetime import datetime, timezone
        config.activated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        create_audit_log(
            db,
            current_user,
            "ACTIVATE_RISK_CONFIGURATION",
            config.configuration_id,
            {
                "version": config.version,
                "previous_active_versions": previous_versions
            }
        )

        db.commit()

        return {
            "message": "Risk configuration activated successfully.",
            "configuration_id": config.configuration_id,
            "version": config.version,
            "status": config.status,
            "previous_versions_archived": previous_versions
        }

    except Exception:
        db.rollback()
        raise
