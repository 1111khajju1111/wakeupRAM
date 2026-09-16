import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    content: str
    source: str
    confidence: float
    relevance: float
    status: str
    last_used_at: datetime | None
    created_at: datetime
