
from pwdlib import PasswordHash

from app.database.connection import SessionLocal
from app.models.user import User


def create_admin():

    db = SessionLocal()

    try:
        name = "Demo Admin"
        email = "admin@cargopilot.example"

        # Check whether this account already exists
        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            print("Admin account already exists.")
            print("User ID:", existing_user.user_id)
            print("Role:", existing_user.role)
            return

        password = input("Enter Admin password: ")
        confirm_password = input("Confirm Admin password: ")

        if len(password) < 6:
            print("Password must contain at least 12 characters.")
            return

        if password != confirm_password:
            print("Passwords do not match.")
            return

        password_hash = PasswordHash.recommended().hash(password)

        admin = User(
            name=name,
            email=email,
            password_hash=password_hash,
            role="ADMIN",
            is_active=True
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\nAdmin account created successfully!")
        print("User ID:", admin.user_id)
        print("Email:", admin.email)
        print("Role:", admin.role)

    except Exception as e:
        db.rollback()
        print("Admin creation failed:", e)

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
