from typing import Any
from sqlmodel import SQLModel

def normalize_result(data: Any) -> Any:
    """
    Recursively converts database objects (SQLModel, SQLAlchemy Rows) 
    into standard Python dicts and lists for serialization.
    """
    if isinstance(data, list):
        return [normalize_result(item) for item in data]
    if isinstance(data, SQLModel):
        return data.model_dump()
    if hasattr(data, "_asdict"):  # Handle SQLAlchemy Row objects
        return data._asdict()
    if isinstance(data, dict):
        return {k: normalize_result(v) for k, v in data.items()}
    return data
