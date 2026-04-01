from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func
from app.core.database import Base


class TimestampMixin:
    """Mixin for adding timestamp columns."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BaseModel(Base, TimestampMixin):
    """Base model with ID and timestamps."""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
