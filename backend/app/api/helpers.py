
from fastapi.encoders import jsonable_encoder


def serialize_records(records, model):
    """
    Convert SQLAlchemy model records into JSON-compatible dictionaries.
    """

    result = []

    for record in records:
        data = {
            column.name: getattr(record, column.name)
            for column in model.__table__.columns
        }

        result.append(data)

    return jsonable_encoder(result)


def get_all_records(db, model):
    """
    Retrieve all records, ordered by primary key descending.
    """

    primary_keys = list(model.__table__.primary_key.columns)

    query = db.query(model)

    if primary_keys:
        query = query.order_by(primary_keys[0].desc())

    return query.all()
