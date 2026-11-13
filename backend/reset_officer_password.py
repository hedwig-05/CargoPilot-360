from pwdlib import PasswordHash

from app.database.connection import SessionLocal
from app.models.user import User


password_hash = PasswordHash.recommended()
db = SessionLocal()

try:
    officer = db.query(User).filter(
        User.email == "officer@cargopilot.example"
    ).first()

    if officer is None:
        print("Officer account not found.")

    else:
        password = input("Enter a new Officer password: ")
        confirm_password = input("Confirm the new password: ")

        if len(password) < 6:
            print("Password must contain at least 6 characters.")

        elif password != confirm_password:
            print("Passwords do not match.")

        else:
            officer.password_hash = password_hash.hash(password)
            db.commit()
            print("Officer password reset successfully.")

except Exception:
    db.rollback()
    raise

finally:
    db.close()