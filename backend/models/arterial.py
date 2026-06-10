from pydantic import BaseModel
from typing import Optional, List


class ArterialCreate(BaseModel):
    name: str
    design_speed: float
    intersections: List[dict] = []


class ArterialUpdate(BaseModel):
    name: Optional[str] = None
    design_speed: Optional[float] = None


class ArterialIntersectionOut(BaseModel):
    intersection_id: int
    sequence_order: int
    distance_from_start: float
    phase_for_coordination: int
    offset: float
    name: Optional[str] = None


class ArterialOut(BaseModel):
    id: int
    name: str
    design_speed: float
    created_at: Optional[str] = None


class ArterialDetail(BaseModel):
    id: int
    name: str
    design_speed: float
    created_at: Optional[str] = None
    intersections: List[ArterialIntersectionOut] = []
