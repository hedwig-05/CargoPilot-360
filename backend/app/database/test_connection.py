
from connection import engine

try:
    with engine.connect() as connection:
        print("Successfully connected to MySQL!")
        print("CargoPilot database connection is working.")

except Exception as e:
    print("Database connection failed!")
    print(e)
