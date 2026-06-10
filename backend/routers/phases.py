from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.phase import PhaseCreate, PhaseUpdate, PhaseOut, PhaseBulkCreate

router = APIRouter(tags=["phases"])


@router.get("/intersections/{intersection_id}/phases", response_model=list[PhaseOut])
async def list_phases(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM phases WHERE intersection_id = ? ORDER BY phase_number", (intersection_id,)
    )
    return [dict(row) for row in await cursor.fetchall()]


@router.post("/intersections/{intersection_id}/phases", response_model=list[PhaseOut], status_code=201)
async def create_phases(intersection_id: int, data: PhaseBulkCreate, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT id FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Intersection not found")
    await db.execute("DELETE FROM phases WHERE intersection_id = ?", (intersection_id,))
    for p in data.phases:
        await db.execute(
            """INSERT INTO phases (intersection_id, phase_number, phase_name, phase_type,
               min_green, max_green, yellow_time, all_red_time, lost_time, flow_rate, saturation_flow)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (intersection_id, p.phase_number, p.phase_name, p.phase_type,
             p.min_green, p.max_green, p.yellow_time, p.all_red_time,
             p.lost_time, p.flow_rate, p.saturation_flow),
        )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM phases WHERE intersection_id = ? ORDER BY phase_number", (intersection_id,)
    )
    return [dict(row) for row in await cursor.fetchall()]


@router.put("/phases/{phase_id}", response_model=PhaseOut)
async def update_phase(phase_id: int, data: PhaseUpdate, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT * FROM phases WHERE id = ?", (phase_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Phase not found")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [phase_id]
        await db.execute(f"UPDATE phases SET {set_clause} WHERE id = ?", values)
        await db.commit()
    row = await (await db.execute("SELECT * FROM phases WHERE id = ?", (phase_id,))).fetchone()
    return dict(row)
