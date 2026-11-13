
from app.database.connection import SessionLocal
from app.engines.investigation import investigate_exception


def test_investigation():

    db = SessionLocal()

    try:
        # Existing document mismatch exception
        exception_id = 4

        print("\nStarting Investigation Engine...")
        print(f"Testing Exception ID: {exception_id}")

        result = investigate_exception(
            db,
            exception_id
        )

        print("\nINVESTIGATION RESULT")
        print("====================")

        for key, value in result.items():
            print(f"\n{key}: {value}")

        print("\nInvestigation test completed.")

    except Exception as e:
        print("\nINVESTIGATION FAILED")
        print("====================")
        print(f"Error: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    test_investigation()
