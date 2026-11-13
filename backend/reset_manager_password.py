from getpass import getpass

from pwdlib import PasswordHash

from app.database.connection import SessionLocal
from app.models.user import User


password_hash = PasswordHash.recommended()

db = SessionLocal()

try:
    manager = db.query(User).filter(
        User.email == "manager@cargopilot.example"
    ).first()

    if manager is None:
        print("Manager account not found.")
    else:
        password = input("Enter a new Manager password: ")
        confirm_password = input("Confirm the new password: ")

        if len(password) < 6:
            print("Password must contain at least 6 characters.")

        elif password != confirm_password:
            print("Passwords do not match.")

        else:
            manager.password_hash = password_hash.hash(password)
            db.commit()

            print("Manager password reset successfully.")

except Exception:
    db.rollback()
    raise

finally:
    db.close()