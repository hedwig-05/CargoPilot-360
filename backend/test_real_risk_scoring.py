
from app.database.connection import SessionLocal
from app.engines.risk_assessment import (
    get_active_risk_configuration,
    detect_risk_factors,
    calculate_risk_score,
    determine_risk_level
)

from app.models import Shipment


def main():

    db = SessionLocal()

    try:
        configuration, rules = get_active_risk_configuration(db)

        shipments = (
            db.query(Shipment)
            .order_by(Shipment.shipment_id)
            .all()
        )

        print("ACTIVE CONFIGURATION:", configuration.version)

        print("\nSHIPMENT RISK PREVIEW")
        print("-" * 75)

        for shipment in shipments:

            evidence = detect_risk_factors(
                db,
                shipment.shipment_id
            )

            score, factors = calculate_risk_score(
                rules,
                evidence
            )

            level = determine_risk_level(
                score,
                configuration
            )

            print(
                f"\nShipment: {shipment.shipment_ref}"
            )

            print("Risk score:", score)
            print("Risk level:", level)

            for factor in factors:
                if factor["points_awarded"] > 0:
                    print(
                        factor["factor_code"],
                        "->",
                        factor["points_awarded"],
                        "points"
                    )

        print("\nREAD-ONLY PREVIEW COMPLETED.")

    except Exception as error:
        print("TEST FAILED:", str(error))

    finally:
        db.close()


if __name__ == "__main__":
    main()
