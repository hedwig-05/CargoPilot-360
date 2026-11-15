"""Manual exception-resolution verification dry-run."""
import json
from app.database.connection import SessionLocal
from app.engines.resolution_verification import verify_exception_resolution


def main():
    db = SessionLocal()
    try:
        result = verify_exception_resolution(db, exception_id=4, commit=False)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
