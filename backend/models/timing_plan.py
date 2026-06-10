from pydantic import BaseModel
from typing import Optional, List


class TimingPlanCreate(BaseModel):
    intersection_id: int
    plan_name: Optional[str] = None
    cycle_length: float
    total_lost_time: Optional[float] = None
    method: str = "manual"
    phase_greens: List[dict] = []


class TimingPlanOut(BaseModel):
    id: int
    intersection_id: int
    plan_name: Optional[str] = None
    cycle_length: float
    total_lost_time: Optional[float] = None
    is_active: int
    method: str
    created_at: Optional[str] = None


class PlanPhaseOut(BaseModel):
    phase_number: int
    green_time: float
    offset: float


class TimingPlanDetail(BaseModel):
    id: int
    intersection_id: int
    plan_name: Optional[str] = None
    cycle_length: float
    total_lost_time: Optional[float] = None
    is_active: int
    method: str
    created_at: Optional[str] = None
    phases: List[PlanPhaseOut] = []
