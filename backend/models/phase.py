from pydantic import BaseModel
from typing import Optional, List


class PhaseCreate(BaseModel):
    phase_number: int
    phase_name: Optional[str] = None
    phase_type: str = "vehicle"
    min_green: float = 7.0
    max_green: float = 60.0
    yellow_time: float = 3.0
    all_red_time: float = 2.0
    lost_time: float = 3.0
    flow_rate: float = 0.0
    saturation_flow: float = 1800.0


class PhaseUpdate(BaseModel):
    phase_name: Optional[str] = None
    phase_type: Optional[str] = None
    min_green: Optional[float] = None
    max_green: Optional[float] = None
    yellow_time: Optional[float] = None
    all_red_time: Optional[float] = None
    lost_time: Optional[float] = None
    flow_rate: Optional[float] = None
    saturation_flow: Optional[float] = None


class PhaseOut(BaseModel):
    id: int
    intersection_id: int
    phase_number: int
    phase_name: Optional[str] = None
    phase_type: str
    min_green: float
    max_green: float
    yellow_time: float
    all_red_time: float
    lost_time: float
    flow_rate: float
    saturation_flow: float


class PhaseBulkCreate(BaseModel):
    phases: List[PhaseCreate]
