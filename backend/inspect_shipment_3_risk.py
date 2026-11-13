
from app.database.connection import SessionLocal
from app.engines.risk_assessment import (
    detect_risk_factors,
    deduplicate_factor_evidence,
    calculate_risk_score,
    get_active_risk_configuration
)

def main():
    db = SessionLocal()

    try:
        configuration, rules = get_active_risk_configuration(db)

        evidence = detect_risk_factors(db, 3)

        print("SHIPMENT: CP-SHP-2026-003")
        print("CONFIGURATION:", configuration.version)

        print("\nRAW EVIDENCE")
        print("-" * 60)

        for factor_code, items in evidence.items():
            print(f"\n{factor_code}")

            for item in items:
                print("  Issue:", item.get("issue_key"))
                print("  Severity:", item.get("severity"))
                print("  Detail:", item.get("detail"))
                print("  Exception ID:", item.get("exception_id"))
                print("  Validation ID:", item.get("validation_id"))
                print()

        print("\nDEDUPLICATED EVIDENCE")
        print("-" * 60)

        for factor_code, items in evidence.items():
            unique = deduplicate_factor_evidence(items)

            print(
                factor_code,
                "Original:", len(items),
                "Unique:", len(unique)
            )

        score, factors = calculate_risk_score(rules, evidence)

        print("\nFINAL SCORE:", score)

        for factor in factors:
            print(
                factor["factor_code"],
                "->",
                factor["points_awarded"]
            )

        print("\nREAD-ONLY INSPECTION COMPLETED.")

    except Exception as error:
        print("TEST FAILED:", str(error))

    finally:
        db.close()


if __name__ == "__main__":
    main()
