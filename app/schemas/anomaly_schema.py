from pydantic import BaseModel

class AnomalyTrigger(BaseModel):
    month: str # Format: "2023-10"