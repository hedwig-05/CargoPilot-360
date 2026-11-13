import json

# Copy this import line from one of your existing test_*.py files if
# your session factory has a different name than SessionLocal.
from app.database.connection import SessionLocal
from app.engines.resolution_verification import verify_exception_resolution

db = SessionLocal()
try:
    result = verify_exception_resolution(db, exception_id=4, commit=False)
    print(json.dumps(result, indent=2, default=str))
finally:
    db.rollback()   # discard everything the dry run flushed
    db.close()