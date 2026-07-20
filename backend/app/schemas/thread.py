from datetime import datetime
from pydantic import BaseModel


class ThreadCreate(BaseModel):
    title: str = "New Chat"


class ThreadRead(BaseModel):
    id: str
    title: str
    is_titled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThreadUpdate(BaseModel):
    title: str
    