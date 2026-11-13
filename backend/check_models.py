
from sqlalchemy import inspect
from app.database.connection import engine, Base
import app.models

inspector = inspect(engine)

print("\n===== CARGOPILOT MODEL CHECK =====")

for table_name, model_table in Base.metadata.tables.items():

    db_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    model_columns = {
        column.name
        for column in model_table.columns
    }

    missing = db_columns - model_columns
    extra = model_columns - db_columns

    print(f"\nTable: {table_name}")

    if not missing and not extra:
        print("  SUCCESS: Column names match!")
    else:
        if missing:
            print("  Missing from model:", missing)

        if extra:
            print("  Not found in database:", extra)

print("\n===== CHECK COMPLETED =====")
