from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.timing_plan import TimingPlanCreate, TimingPlanOut, TimingPlanDetail, PlanPhaseOut

router = APIRouter(tags=["timing_plans"])


@router.get("/intersections/{intersection_id}/timing-plans", response_model=list[TimingPlanOut])
async def list_plans(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM timing_plans WHERE intersection_id = ? ORDER BY created_at DESC", (intersection_id,)
    )
    return [dict(row) for row in await cursor.fetchall()]


@router.get("/timing-plans/{plan_id}", response_model=TimingPlanDetail)
async def get_plan(plan_id: int, db: aiosqlite.Connection = Depends(get_db)):
    row = await (await db.execute("SELECT * FROM timing_plans WHERE id = ?", (plan_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Timing plan not found")
    plan = dict(row)
    phase_cursor = await db.execute(
        "SELECT phase_number, green_time, offset FROM plan_phases WHERE timing_plan_id = ? ORDER BY phase_number",
        (plan_id,),
    )
    plan["phases"] = [dict(r) for r in await phase_cursor.fetchall()]
    return plan


@router.post("/timing-plans", response_model=TimingPlanOut, status_code=201)
async def create_plan(data: TimingPlanCreate, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """INSERT INTO timing_plans (intersection_id, plan_name, cycle_length, total_lost_time, method)
           VALUES (?, ?, ?, ?, ?)""",
        (data.intersection_id, data.plan_name, data.cycle_length, data.total_lost_time, data.method),
    )
    plan_id = cursor.lastrowid
    for pg in data.phase_greens:
        await db.execute(
            "INSERT INTO plan_phases (timing_plan_id, phase_number, green_time, offset) VALUES (?, ?, ?, ?)",
            (plan_id, pg["phase_number"], pg["green_time"], pg.get("offset", 0)),
        )
    await db.commit()
    row = await (await db.execute("SELECT * FROM timing_plans WHERE id = ?", (plan_id,))).fetchone()
    return dict(row)


@router.put("/timing-plans/{plan_id}/activate", response_model=TimingPlanOut)
async def activate_plan(plan_id: int, db: aiosqlite.Connection = Depends(get_db)):
    row = await (await db.execute("SELECT * FROM timing_plans WHERE id = ?", (plan_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Timing plan not found")
    await db.execute(
        "UPDATE timing_plans SET is_active = 0 WHERE intersection_id = ?", (row["intersection_id"],)
    )
    await db.execute("UPDATE timing_plans SET is_active = 1 WHERE id = ?", (plan_id,))
    await db.commit()
    row = await (await db.execute("SELECT * FROM timing_plans WHERE id = ?", (plan_id,))).fetchone()
    return dict(row)
