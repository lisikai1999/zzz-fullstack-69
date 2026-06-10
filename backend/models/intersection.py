from pydantic import BaseModel
from typing import Optional


class IntersectionCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    intersection_type: str = "signalized"
    total_lost_time: float = 12.0
    min_cycle: float = 30.0
    max_cycle: float = 180.0


class IntersectionUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    intersection_type: Optional[str] = None
    total_lost_time: Optional[float] = None
    min_cycle: Optional[float] = None
    max_cycle: Optional[float] = None


class IntersectionOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    intersection_type: str
    total_lost_time: float
    min_cycle: float
    max_cycle: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
