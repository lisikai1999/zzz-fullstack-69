from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import aiosqlite

from database import get_db

router = APIRouter(tags=["detectors"])


class DetectorCreate(BaseModel):
    detector_name: Optional[str] = None
    approach: str
    lane_number: int = 1
    detector_type: str = "loop"


class DetectorOut(BaseModel):
    id: int
    intersection_id: int
    detector_name: Optional[str] = None
    approach: str
    lane_number: int
    detector_type: str


class FlowDataCreate(BaseModel):
    timestamp: str
    volume: int
    occupancy: Optional[float] = None
    speed: Optional[float] = None
    interval_seconds: int = 300


class FlowDataBatch(BaseModel):
    records: List[FlowDataCreate]


class FlowDataOut(BaseModel):
    id: int
    detector_id: int
    timestamp: str
    volume: int
    occupancy: Optional[float] = None
    speed: Optional[float] = None
    interval_seconds: int


@router.get("/intersections/{intersection_id}/detectors", response_model=list[DetectorOut])
async def list_detectors(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM detectors WHERE intersection_id = ? ORDER BY id", (intersection_id,)
    )
    return [dict(row) for row in await cursor.fetchall()]


@router.post("/intersections/{intersection_id}/detectors", response_model=DetectorOut, status_code=201)
async def create_detector(intersection_id: int, data: DetectorCreate, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT id FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Intersection not found")
    cursor = await db.execute(
        "INSERT INTO detectors (intersection_id, detector_name, approach, lane_number, detector_type) VALUES (?, ?, ?, ?, ?)",
        (intersection_id, data.detector_name, data.approach, data.lane_number, data.detector_type),
    )
    await db.commit()
    row = await (await db.execute("SELECT * FROM detectors WHERE id = ?", (cursor.lastrowid,))).fetchone()
    return dict(row)


@router.post("/detectors/{detector_id}/flow", status_code=201)
async def submit_flow(detector_id: int, data: FlowDataBatch, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT id FROM detectors WHERE id = ?", (detector_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Detector not found")
    for r in data.records:
        await db.execute(
            "INSERT INTO flow_data (detector_id, timestamp, volume, occupancy, speed, interval_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (detector_id, r.timestamp, r.volume, r.occupancy, r.speed, r.interval_seconds),
        )
    await db.commit()
    return {"inserted": len(data.records)}


@router.get("/detectors/{detector_id}/flow", response_model=list[FlowDataOut])
async def query_flow(
    detector_id: int,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    sql = "SELECT * FROM flow_data WHERE detector_id = ?"
    params: list = [detector_id]
    if start:
        sql += " AND timestamp >= ?"
        params.append(start)
    if end:
        sql += " AND timestamp <= ?"
        params.append(end)
    sql += " ORDER BY timestamp"
    cursor = await db.execute(sql, params)
    return [dict(row) for row in await cursor.fetchall()]
