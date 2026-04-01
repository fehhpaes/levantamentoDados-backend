from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class BaseDocument(Document):
    """Base document with timestamps."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        use_state_management = True
    
    async def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return await super().save(*args, **kwargs)
