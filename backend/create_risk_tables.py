
from sqlalchemy import inspect

# Import Base and the existing database engine
from app.database.connection import Base, engine

# Import all models so SQLAlchemy knows about their tables
from app.models import (
    User,
    Shipment,
    ShipmentEvent,
    Document,
    DocumentValidation,
    Exception,
    AgentWorkflow,
    AgentRun,
    Investigation,
    InvestigationEvidence,
    RiskAssessment,
    RiskAssessmentFactor,
    ResolutionPlan,
    Action,
    ActionExecution,
    AuditLog,
    RiskConfiguration,
    RiskFactorRule
)


def create_risk_tables():
    inspector = inspect(engine)

    existing_tables = inspector.get_table_names()

    new_tables = [
        "risk_configurations",
        "risk_factor_rules"
    ]

    for table_name in new_tables:
        if table_name in existing_tables:
            print(f"{table_name} already exists. Skipping.")
        else:
            print(f"{table_name} will be created.")

    # Create only the two new tables.
    Base.metadata.create_all(
        bind=engine,
        tables=[
            RiskConfiguration.__table__,
            RiskFactorRule.__table__
        ],
        checkfirst=True
    )

    print("\nRisk configuration table setup completed.")

    # Verify the result
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()

    for table_name in new_tables:
        if table_name in final_tables:
            print(f"VERIFIED: {table_name}")
        else:
            print(f"ERROR: {table_name} was not created.")


if __name__ == "__main__":
    create_risk_tables()
