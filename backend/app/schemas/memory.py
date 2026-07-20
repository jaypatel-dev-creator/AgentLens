from datetime import datetime
from pydantic import BaseModel

#response schema for all routes in memory.py except delete (delete dont have body, so no response schema ) and get all enteries 
class ProfileEntry(BaseModel):
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True} #since here model_config,, so in routes using this as response schema, they should have model_validate 

#response schema  for get all enteries 
class ProfileRead(BaseModel):
    entries: list[ProfileEntry]

#request schema for upsert 
class ProfileUpsert(BaseModel):
    key: str
    value: str

#request schema for update 
class ProfileEntryUpdate(BaseModel):
    value: str
    