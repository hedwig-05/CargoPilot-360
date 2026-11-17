"""Manual MySQL connection smoke test."""
from .connection import engine


def main():
    try:
        with engine.connect():
            print("Successfully connected to MySQL!")
            print("CargoPilot database connection is working.")
    except Exception as e:
        print("Database connection failed!")
        print(e)
        raise


if __name__ == "__main__":
    main()
