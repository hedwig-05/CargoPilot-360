
from decimal import Decimal

from app.database.connection import SessionLocal
from app.models import RiskConfiguration, RiskFactorRule, AuditLog


def create_initial_configuration():
    db = SessionLocal()

    try:
        # Prevent accidental duplicate initial configurations.
        existing = (
            db.query(RiskConfiguration)
            .filter(RiskConfiguration.version == "1.0")
            .first()
        )

        if existing:
            print("Initial risk configuration already exists.")
            print("Configuration ID:", existing.configuration_id)
            return

        # Find the Admin account.
        admin = (
            db.query(__import__(
                "app.models.user", fromlist=["User"]
            ).User)
            .filter_by(email="admin@cargopilot.example")
            .first()
        )

        if admin is None:
            print("Admin account not found.")
            return

        # Create the first draft configuration.
        configuration = RiskConfiguration(
            configuration_name="Default Logistics Risk Configuration",
            version="1.0",
            description="Initial configurable risk assessment rules.",
            low_max_score=Decimal("29"),
            medium_max_score=Decimal("59"),
            high_max_score=Decimal("100"),
            status="DRAFT",
            created_by=admin.user_id
        )

        db.add(configuration)
        db.flush()

        # Define the initial risk factors.
        factors = [
            {
                "factor_code": "DOCUMENT_MISMATCH",
                "factor_name": "Document Mismatch",
                "weight": Decimal("30.00"),
                "description": "Inconsistencies between shipment documents."
            },
            {
                "factor_code": "ARRIVAL_DELAY",
                "factor_name": "Arrival Delay",
                "weight": Decimal("25.00"),
                "description": "Shipment arrival later than expected."
            },
            {
                "factor_code": "MISSING_MILESTONE",
                "factor_name": "Missing Milestone",
                "weight": Decimal("20.00"),
                "description": "An expected shipment milestone is missing."
            },
            {
                "factor_code": "CUSTOMS_ISSUE",
                "factor_name": "Customs Issue",
                "weight": Decimal("15.00"),
                "description": "Customs clearance or inspection problems."
            },
            {
                "factor_code": "STAKEHOLDER_DELAY",
                "factor_name": "Stakeholder Delay",
                "weight": Decimal("10.00"),
                "description": "Delayed response from a responsible stakeholder."
            }
        ]

        for factor in factors:
            rule = RiskFactorRule(
                configuration_id=configuration.configuration_id,
                factor_code=factor["factor_code"],
                factor_name=factor["factor_name"],
                weight=factor["weight"],
                is_enabled=True,
                description=factor["description"]
            )

            db.add(rule)

        # Record the creation in the existing audit log.
        audit = AuditLog(
            actor_type="USER",
            actor_user_id=admin.user_id,
            actor_name=admin.name,
            action="CREATE_RISK_CONFIGURATION",
            entity_type="RISK_CONFIGURATION",
            entity_id=configuration.configuration_id,
            details={
                "version": "1.0",
                "status": "DRAFT",
                "total_weight": 100,
                "factor_count": len(factors)
            }
        )

        db.add(audit)

        db.commit()

        print("Initial risk configuration created successfully.")
        print("Configuration ID:", configuration.configuration_id)
        print("Version:", configuration.version)
        print("Status:", configuration.status)
        print("Risk factors:", len(factors))
        print("Total weight: 100")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_initial_configuration()
