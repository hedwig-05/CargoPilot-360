
from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import (
    Integer, String, Text, Enum, Boolean,
    DateTime, Numeric, JSON
)

from app.database.connection import engine, Base
import app.models


# Inspect the existing MySQL database
inspector = inspect(engine)


def compatible(db_type, model_type):

    # Integer types
    if isinstance(db_type, Integer) and isinstance(model_type, Integer):
        return True

    # Boolean / MySQL TINYINT
    if isinstance(model_type, Boolean) and isinstance(db_type, Integer):
        return True

    # String types
    if isinstance(db_type, String) and isinstance(model_type, String):
        return db_type.length == model_type.length

    # ENUM types
    if isinstance(db_type, Enum) and isinstance(model_type, Enum):
        return set(db_type.enums) == set(model_type.enums)

    # DATETIME types
    if isinstance(db_type, DateTime) and isinstance(model_type, DateTime):
        return True

    # DECIMAL / NUMERIC types
    if isinstance(db_type, Numeric) and isinstance(model_type, Numeric):
        return (
            db_type.precision == model_type.precision
            and db_type.scale == model_type.scale
        )

    # TEXT types
    if isinstance(db_type, Text) and isinstance(model_type, Text):
        return True

    # JSON types
    if isinstance(db_type, JSON) and isinstance(model_type, JSON):
        return True

    # Fallback: compare SQLAlchemy types
    return type(db_type) == type(model_type)


print("\n===== IMPROVED COLUMN TYPE CHECK =====")

total_matches = 0
total_reviews = 0

for table_name, model_table in Base.metadata.tables.items():

    db_columns = {
        column["name"]: column["type"]
        for column in inspector.get_columns(table_name)
    }

    print(f"\nTable: {table_name}")

    for column in model_table.columns:

        db_type = db_columns.get(column.name)

        if db_type is None:
            continue

        model_type = column.type

        if compatible(db_type, model_type):
            print(f"  MATCH: {column.name}")
            total_matches += 1

        else:
            print(
                f"  REVIEW: {column.name} | "
                f"Database: {db_type} | "
                f"Model: {model_type}"
            )
            total_reviews += 1


print("\n===== CHECK COMPLETED =====")
print(f"Total matching columns: {total_matches}")
print(f"Total columns requiring review: {total_reviews}")
